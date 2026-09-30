"""Calcul des nouvelles lunes et pleines lunes, reliées au natal et à la RS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

from utils.transits.calcul_transits import longitude_to_signe
from utils.transits.maisons import trouver_maison


EPHEMERIS_PATH = Path(__file__).resolve().parents[1] / "ephe"
PAS_RECHERCHE = timedelta(hours=2)
PRECISION = timedelta(seconds=1)
DUREE_MAX = timedelta(days=32)
ASPECTS = (
    ("conjonction", 0, 3),
    ("sextile", 60, 3),
    ("carré", 90, 3),
    ("trigone", 120, 3),
    ("quinconce", 150, 3),
    ("opposition", 180, 3),
)


def _utc(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValueError("L'instant doit inclure un fuseau horaire.")
    return instant.astimezone(timezone.utc)


def _jour_julien(instant: datetime) -> float:
    instant = _utc(instant)
    heure = (
        instant.hour + instant.minute / 60 + instant.second / 3600
        + instant.microsecond / 3_600_000_000
    )
    return swe.julday(instant.year, instant.month, instant.day, heure)


def _longitudes_luminaires(instant: datetime) -> tuple[float, float]:
    swe.set_ephe_path(str(EPHEMERIS_PATH))
    jd = _jour_julien(instant)
    soleil = swe.calc_ut(jd, swe.SUN)[0][0] % 360
    lune = swe.calc_ut(jd, swe.MOON)[0][0] % 360
    return soleil, lune


def _phase(instant: datetime) -> float:
    soleil, lune = _longitudes_luminaires(instant)
    return (lune - soleil) % 360


def _est_eclipse(type_lunaison: str, instant: datetime) -> dict | None:
    """Indique une éclipse globale coïncidant avec la lunaison calculée.

    L'information est astronomique et globale : elle ne prétend pas que
    l'éclipse est visible depuis le lieu du client.
    """
    swe.set_ephe_path(str(EPHEMERIS_PATH))
    jd = _jour_julien(instant)
    if type_lunaison == "nouvelle_lune":
        indicateurs, instants = swe.sol_eclipse_when_glob(jd - 0.5)
        genres = (
            (swe.ECL_TOTAL, "solaire totale"),
            (swe.ECL_ANNULAR, "solaire annulaire"),
            (swe.ECL_PARTIAL, "solaire partielle"),
        )
    else:
        indicateurs, instants = swe.lun_eclipse_when(jd - 0.5)
        genres = (
            (swe.ECL_TOTAL, "lunaire totale"),
            (swe.ECL_PARTIAL, "lunaire partielle"),
            (swe.ECL_PENUMBRAL, "lunaire pénombrale"),
        )
    # Une éclipse liée à la lunaison a son maximum à quelques minutes de
    # l'instant de phase. Une journée de marge absorbe les arrondis sans
    # rattacher l'éclipse suivante à la mauvaise lunaison.
    if abs(instants[0] - jd) > 1:
        return None
    nature = next((libelle for masque, libelle in genres if indicateurs & masque), None)
    if nature is None:
        return None
    return {"nature": nature, "portee": "globale"}


def _ecart_signe(longitude: float, cible: float) -> float:
    return (longitude - cible + 180) % 360 - 180


def prochain_instant_lunaison(
    type_lunaison: str,
    *,
    apres: datetime | None = None,
) -> datetime:
    """Trouve la prochaine nouvelle ou pleine lune après un instant UTC."""
    cibles = {"nouvelle_lune": 0.0, "pleine_lune": 180.0}
    if type_lunaison not in cibles:
        raise ValueError("Type de lunaison attendu : nouvelle_lune ou pleine_lune.")
    debut = _utc(apres or datetime.now(timezone.utc)) + timedelta(seconds=1)
    cible = cibles[type_lunaison]
    gauche = debut
    ecart_gauche = _ecart_signe(_phase(gauche), cible)
    limite = debut + DUREE_MAX
    while gauche < limite:
        droite = min(gauche + PAS_RECHERCHE, limite)
        ecart_droite = _ecart_signe(_phase(droite), cible)
        if ecart_gauche <= 0 <= ecart_droite:
            while droite - gauche > PRECISION:
                milieu = gauche + (droite - gauche) / 2
                if _ecart_signe(_phase(milieu), cible) < 0:
                    gauche = milieu
                else:
                    droite = milieu
            return gauche + (droite - gauche) / 2
        gauche, ecart_gauche = droite, ecart_droite
    raise RuntimeError("Aucune lunaison trouvée dans les 32 jours.")


def _cuspides(theme: dict | None) -> list[float] | None:
    if not theme:
        return None
    try:
        return [
            float(theme["maisons"][f"Maison {numero}"]["degre"])
            for numero in range(1, 13)
        ]
    except (KeyError, TypeError, ValueError):
        return None


def _points(theme: dict | None) -> dict[str, float]:
    if not theme:
        return {}
    resultat = {}
    for nom, donnees in (theme.get("planetes") or {}).items():
        longitude = donnees.get("longitude", donnees.get("degre"))
        if longitude is not None:
            resultat[nom] = float(longitude) % 360
    for nom, longitude in (theme.get("angles_deg") or {}).items():
        if longitude is not None:
            resultat[nom] = float(longitude) % 360
    return resultat


def _aspects(longitude: float, theme: dict | None, cle_point: str) -> list[dict]:
    resultat = []
    for nom, longitude_cible in _points(theme).items():
        distance = abs((longitude - longitude_cible + 180) % 360 - 180)
        for nom_aspect, angle, orbe_max in ASPECTS:
            orbe = abs(distance - angle)
            if orbe <= orbe_max:
                resultat.append({
                    cle_point: nom,
                    "aspect": nom_aspect,
                    "orbe": round(orbe, 3),
                })
                break
    return sorted(resultat, key=lambda item: item["orbe"])


def calculer_lunaison(
    type_lunaison: str,
    *,
    apres: datetime,
    theme_natal: dict | None = None,
    theme_rs: dict | None = None,
    tzid: str = "UTC",
) -> dict:
    """Calcule une lunaison et ses résonances, sans l'interpréter."""
    try:
        fuseau = ZoneInfo(tzid)
    except Exception as exc:
        raise ValueError("Fuseau de lunaison invalide.") from exc
    instant = prochain_instant_lunaison(type_lunaison, apres=apres)
    soleil, lune = _longitudes_luminaires(instant)
    longitude = soleil if type_lunaison == "nouvelle_lune" else lune
    cuspides_natales = _cuspides(theme_natal)
    cuspides_rs = _cuspides(theme_rs)
    return {
        "type": type_lunaison,
        "instant_utc": instant.isoformat(),
        "instant_local": instant.astimezone(fuseau).isoformat(),
        "position": longitude_to_signe(longitude),
        "maison_natale": trouver_maison(longitude, cuspides_natales) if cuspides_natales else None,
        "maison_rs": trouver_maison(longitude, cuspides_rs) if cuspides_rs else None,
        "aspects_natal": _aspects(longitude, theme_natal, "point_natal"),
        "aspects_rs": _aspects(longitude, theme_rs, "point_rs"),
        "eclipse": _est_eclipse(type_lunaison, instant),
    }


def prochaines_lunaisons(
    *,
    apres: datetime,
    theme_natal: dict | None = None,
    theme_rs: dict | None = None,
    tzid: str = "UTC",
    nombre: int = 2,
) -> list[dict]:
    """Retourne les prochaines nouvelles/pleines lunes dans l'ordre réel."""
    if nombre < 1:
        raise ValueError("Le nombre de lunaisons doit être positif.")
    resultat = []
    curseur = _utc(apres)
    while len(resultat) < nombre:
        candidates = [
            calculer_lunaison(
                type_lunaison, apres=curseur, theme_natal=theme_natal,
                theme_rs=theme_rs, tzid=tzid,
            )
            for type_lunaison in ("nouvelle_lune", "pleine_lune")
        ]
        prochaine = min(candidates, key=lambda item: item["instant_utc"])
        resultat.append(prochaine)
        curseur = datetime.fromisoformat(prochaine["instant_utc"]) + timedelta(seconds=1)
    return resultat


def dernieres_lunaisons(
    *,
    avant: datetime,
    theme_natal: dict | None = None,
    theme_rs: dict | None = None,
    tzid: str = "UTC",
    nombre: int = 1,
) -> list[dict]:
    """Retourne les dernières lunaisons antérieures à un instant donné."""
    if nombre < 1:
        raise ValueError("Le nombre de lunaisons doit être positif.")
    limite = _utc(avant)
    # Deux mois couvrent largement les deux phases précédentes, tout en
    # conservant le même calcul précis que pour les phases à venir.
    curseur = limite - timedelta(days=65)
    resultat = []
    while True:
        candidates = [
            calculer_lunaison(
                type_lunaison, apres=curseur, theme_natal=theme_natal,
                theme_rs=theme_rs, tzid=tzid,
            )
            for type_lunaison in ("nouvelle_lune", "pleine_lune")
        ]
        prochaine = min(candidates, key=lambda item: item["instant_utc"])
        instant = datetime.fromisoformat(prochaine["instant_utc"])
        if instant >= limite:
            break
        resultat.append(prochaine)
        curseur = instant + timedelta(seconds=1)
    return resultat[-nombre:]
