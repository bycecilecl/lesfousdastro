"""Calcul astronomique de l'instant d'une révolution lunaire tropicale."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from zoneinfo import ZoneInfo

import swisseph as swe

from utils.transits.calcul_transits import PLANETES_SWISSEPH, longitude_to_signe
from utils.transits.maisons import trouver_maison
from utils.calculs_astrologiques import get_maitre_ascendant


_EPHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ephe")
_PAS_RECHERCHE = timedelta(hours=2)
_DUREE_MAX_RECHERCHE = timedelta(days=32)
_PRECISION_TEMPORELLE = timedelta(seconds=1)
_ASPECTS_MAJEURS = {
    "conjonction": (0, 5),
    "sextile": (60, 3),
    "carré": (90, 4),
    "trigone": (120, 4),
    "opposition": (180, 5),
}
_ASPECTS_RL_RS = {
    **_ASPECTS_MAJEURS,
    "quinconce": (150, 3),
}


def _en_utc(date_heure: datetime) -> datetime:
    """Normalise une date consciente de son fuseau en UTC."""
    if date_heure.tzinfo is None:
        raise ValueError("La date de recherche doit contenir un fuseau horaire.")
    return date_heure.astimezone(timezone.utc)


def _jour_julien(date_heure_utc: datetime) -> float:
    heure_decimale = (
        date_heure_utc.hour
        + date_heure_utc.minute / 60
        + date_heure_utc.second / 3600
        + date_heure_utc.microsecond / 3_600_000_000
    )
    return swe.julday(
        date_heure_utc.year,
        date_heure_utc.month,
        date_heure_utc.day,
        heure_decimale,
    )


def longitude_lune(date_heure: datetime) -> float:
    """Retourne la longitude tropicale géocentrique de la Lune, entre 0 et 360°."""
    date_heure_utc = _en_utc(date_heure)
    swe.set_ephe_path(_EPHE_PATH)
    coordonnees = swe.calc_ut(_jour_julien(date_heure_utc), swe.MOON)[0]
    return coordonnees[0] % 360


def _ecart_signe(longitude: float, cible: float) -> float:
    """Écart angulaire signé dans l'intervalle [-180°, 180°[."""
    return (longitude - cible + 180) % 360 - 180


def _distance_angulaire(longitude_a: float, longitude_b: float) -> float:
    distance = abs(longitude_a - longitude_b) % 360
    return min(distance, 360 - distance)


def _detecter_aspect(
    longitude_a: float,
    longitude_b: float,
    aspects: dict[str, tuple[int, int]] | None = None,
) -> dict | None:
    distance = _distance_angulaire(longitude_a, longitude_b)
    for nom, (angle, orbe_max) in (aspects or _ASPECTS_MAJEURS).items():
        orbe = abs(distance - angle)
        if orbe <= orbe_max:
            return {"aspect": nom, "orbe": round(orbe, 3)}
    return None


def _aspects_internes(positions: dict) -> list[dict]:
    aspects = []
    noms = list(positions)
    for index, nom_a in enumerate(noms):
        for nom_b in noms[index + 1:]:
            aspect = _detecter_aspect(
                positions[nom_a]["longitude"],
                positions[nom_b]["longitude"],
            )
            if aspect:
                aspects.append({"point_1": nom_a, "point_2": nom_b, **aspect})
    return sorted(aspects, key=lambda item: item["orbe"])


def _aspects_avec_natal(positions: dict, theme_natal: dict | None) -> list[dict]:
    if not theme_natal:
        return []

    points_nataux = {}
    for nom, donnees in (theme_natal.get("planetes") or {}).items():
        longitude = donnees.get("longitude", donnees.get("degre"))
        if longitude is not None:
            points_nataux[nom] = float(longitude)
    for nom, longitude in (theme_natal.get("angles_deg") or {}).items():
        if longitude is not None:
            points_nataux[nom] = float(longitude)

    aspects = []
    for nom_revolution, donnees in positions.items():
        for nom_natal, longitude_natale in points_nataux.items():
            # Cette conjonction exacte définit la révolution lunaire elle-même ;
            # elle ne constitue donc pas un facteur interprétatif supplémentaire.
            if nom_revolution == "Lune" and nom_natal == "Lune":
                continue
            aspect = _detecter_aspect(donnees["longitude"], longitude_natale)
            if aspect:
                aspects.append({
                    "planete_revolution": nom_revolution,
                    "point_natal": nom_natal,
                    **aspect,
                })
    return sorted(aspects, key=lambda item: item["orbe"])


def _points_rs(theme_rs: dict) -> dict[str, float]:
    """Extrait les planètes et angles de RS utilisables pour un contact RL→RS."""
    points = {}
    for nom, donnees in (theme_rs.get("planetes") or {}).items():
        longitude = donnees.get("longitude", donnees.get("degre"))
        if longitude is not None:
            points[nom] = float(longitude) % 360
    for nom, longitude in (theme_rs.get("angles_deg") or {}).items():
        if longitude is not None:
            points[nom] = float(longitude) % 360
    return points


def _aspects_rl_vers_rs(positions_rl: dict, angles_rl: dict, theme_rs: dict | None) -> list[dict]:
    """Aspects de la RL vers la RS, sans confondre les deux cartes."""
    if not theme_rs:
        return []
    points_rl = {
        nom: float(donnees["longitude"]) % 360
        for nom, donnees in positions_rl.items()
        if donnees.get("longitude") is not None
    }
    points_rl.update({nom: float(longitude) % 360 for nom, longitude in angles_rl.items()})
    resultat = []
    for point_rl, longitude_rl in points_rl.items():
        for point_rs, longitude_rs in _points_rs(theme_rs).items():
            aspect = _detecter_aspect(longitude_rl, longitude_rs, _ASPECTS_RL_RS)
            if aspect:
                resultat.append({
                    "point_rl": point_rl,
                    "point_rs": point_rs,
                    **aspect,
                })
    return sorted(resultat, key=lambda item: item["orbe"])


def _superpositions_rl_dans_rs(positions_rl: dict, angles_rl: dict, theme_rs: dict | None) -> list[dict]:
    """Indique dans quelle maison RS tombent les facteurs de la RL."""
    if not theme_rs:
        return []
    try:
        cuspides = [
            float((theme_rs.get("maisons") or {})[f"Maison {numero}"]["degre"])
            for numero in range(1, 13)
        ]
    except (KeyError, TypeError, ValueError):
        return []
    points_rl = {
        nom: float(donnees["longitude"]) % 360
        for nom, donnees in positions_rl.items()
        if donnees.get("longitude") is not None
    }
    points_rl.update({nom: float(longitude) % 360 for nom, longitude in angles_rl.items()})
    return [
        {"point_rl": nom, "maison_rs": trouver_maison(longitude, cuspides)}
        for nom, longitude in points_rl.items()
    ]


def prochaine_revolution_lunaire(
    longitude_natale: float,
    apres: datetime | None = None,
) -> datetime:
    """Trouve le prochain retour de la Lune sur sa longitude natale.

    Le résultat est exprimé en UTC et précis à environ une seconde. Le lieu
    n'intervient pas dans l'instant du retour ; il servira ensuite au calcul
    des maisons et des angles du thème de révolution.
    """
    try:
        cible = float(longitude_natale) % 360
    except (TypeError, ValueError) as exc:
        raise ValueError("La longitude lunaire natale doit être un nombre.") from exc

    debut = _en_utc(apres or datetime.now(timezone.utc)) + timedelta(seconds=1)
    borne_gauche = debut
    ecart_gauche = _ecart_signe(longitude_lune(borne_gauche), cible)
    limite = debut + _DUREE_MAX_RECHERCHE

    while borne_gauche < limite:
        borne_droite = min(borne_gauche + _PAS_RECHERCHE, limite)
        ecart_droite = _ecart_signe(longitude_lune(borne_droite), cible)

        # Au retour sur la cible, l'écart passe de négatif à positif. Le saut
        # opposé (+180 vers -180) ne peut donc pas être confondu avec le retour.
        if ecart_gauche <= 0 <= ecart_droite:
            while borne_droite - borne_gauche > _PRECISION_TEMPORELLE:
                milieu = borne_gauche + (borne_droite - borne_gauche) / 2
                ecart_milieu = _ecart_signe(longitude_lune(milieu), cible)
                if ecart_milieu < 0:
                    borne_gauche = milieu
                else:
                    borne_droite = milieu
            return borne_gauche + (borne_droite - borne_gauche) / 2

        borne_gauche = borne_droite
        ecart_gauche = ecart_droite

    raise RuntimeError("Aucune révolution lunaire trouvée dans les 32 jours.")


def calculer_theme_revolution_lunaire(
    longitude_natale_lune: float,
    latitude: float,
    longitude: float,
    apres: datetime | None = None,
    theme_natal: dict | None = None,
    theme_revolution_solaire: dict | None = None,
    tzid: str = "UTC",
) -> dict:
    """Calcule le thème technique complet du prochain retour lunaire."""
    latitude = float(latitude)
    longitude = float(longitude)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Les coordonnées du lieu ne sont pas valides.")

    try:
        fuseau = ZoneInfo(tzid)
    except Exception as exc:
        raise ValueError("Le fuseau horaire du lieu n’est pas valide.") from exc

    instant_utc = prochaine_revolution_lunaire(longitude_natale_lune, apres=apres)
    jour_julien = _jour_julien(instant_utc)
    cuspides_brutes, ascmc = swe.houses(
        jour_julien,
        latitude,
        longitude,
        b"P",
    )
    cuspides = [float(cuspide % 360) for cuspide in cuspides_brutes]

    positions = {}
    for nom, identifiant in PLANETES_SWISSEPH.items():
        coordonnees = swe.calc_ut(jour_julien, identifiant)[0]
        position = longitude_to_signe(coordonnees[0] % 360)
        positions[nom] = {
            **position,
            "maison": trouver_maison(position["longitude"], cuspides),
            "retrograde": coordonnees[3] < 0,
            "vitesse": round(coordonnees[3], 6),
        }

    angles = {
        "Ascendant": round(ascmc[0] % 360, 4),
        "MC": round(ascmc[1] % 360, 4),
        "Descendant": round((ascmc[0] + 180) % 360, 4),
        "FC": round((ascmc[1] + 180) % 360, 4),
    }
    maisons = {
        f"Maison {numero}": {
            **longitude_to_signe(cuspide),
            "degre": round(cuspide, 4),
        }
        for numero, cuspide in enumerate(cuspides, start=1)
    }

    return {
        "instant_utc": instant_utc.isoformat(),
        "instant_local": instant_utc.astimezone(fuseau).isoformat(),
        "lieu": {
            "latitude": latitude,
            "longitude": longitude,
            "tzid": tzid,
        },
        "longitude_lunaire_natale": round(float(longitude_natale_lune) % 360, 6),
        "planetes": positions,
        "angles_deg": angles,
        "maisons": maisons,
        "aspects_revolution": _aspects_internes(positions),
        "aspects_avec_natal": _aspects_avec_natal(positions, theme_natal),
        "aspects_avec_rs": _aspects_rl_vers_rs(
            positions, angles, theme_revolution_solaire,
        ),
        "superpositions_dans_rs": _superpositions_rl_dans_rs(
            positions, angles, theme_revolution_solaire,
        ),
    }


def priorites_interpretation(theme_revolution: dict) -> dict:
    """Hiérarchise les facteurs techniques utiles avant toute interprétation."""
    from utils.adaptateur_revolution_lunaire import (
        enrichir_priorites_avec_moteurs_existants,
    )

    planetes = theme_revolution.get("planetes") or {}
    angles = theme_revolution.get("angles_deg") or {}
    ascendant = longitude_to_signe(float(angles["Ascendant"]))

    planetes_angulaires = []
    for nom_planete, donnees in planetes.items():
        for nom_angle, longitude_angle in angles.items():
            orbe = _distance_angulaire(
                float(donnees["longitude"]),
                float(longitude_angle),
            )
            if orbe <= 5:
                planetes_angulaires.append({
                    "planete": nom_planete,
                    "angle": nom_angle,
                    "orbe": round(orbe, 3),
                })

    occupations = {}
    for nom_planete, donnees in planetes.items():
        maison = donnees.get("maison")
        if maison is not None:
            occupations.setdefault(maison, []).append(nom_planete)
    maisons_occupees = [
        {"maison": maison, "planetes": noms, "nombre": len(noms)}
        for maison, noms in occupations.items()
    ]
    maisons_occupees.sort(key=lambda item: (-item["nombre"], item["maison"]))

    aspects_nataux = theme_revolution.get("aspects_avec_natal") or []
    points_nataux_majeurs = {"Soleil", "Lune", "Ascendant", "MC"}

    priorites = {
        "ascendant": ascendant,
        "maitre_ascendant": get_maitre_ascendant(ascendant["signe"]),
        "lune": planetes.get("Lune"),
        "planetes_angulaires": sorted(
            planetes_angulaires,
            key=lambda item: item["orbe"],
        ),
        "maisons_occupees": maisons_occupees,
        "aspects_internes_serres": [
            aspect
            for aspect in (theme_revolution.get("aspects_revolution") or [])
            if aspect["orbe"] <= 3
        ],
        "aspects_nataux_serres": [
            aspect for aspect in aspects_nataux if aspect["orbe"] <= 2
        ],
        "contacts_nataux_majeurs": [
            aspect
            for aspect in aspects_nataux
            if aspect["point_natal"] in points_nataux_majeurs
            and aspect["orbe"] <= 4
        ],
    }
    priorites.update(
        enrichir_priorites_avec_moteurs_existants(theme_revolution)
    )
    return priorites
