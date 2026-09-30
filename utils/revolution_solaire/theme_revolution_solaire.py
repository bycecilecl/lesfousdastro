"""Pont entre le calcul du retour solaire et le calcul de thème existant."""

from __future__ import annotations

from datetime import datetime

import pytz

from utils.calcul_theme import calcul_theme
from .calcul_retour_solaire import trouver_retour_solaire


_MAITRE_MODERNE = {"Scorpion": "Pluton", "Verseau": "Uranus", "Poissons": "Neptune"}


def _harmoniser_maitre_ascendant(theme: dict) -> None:
    """Conserve la maîtrise moderne RS sans modifier calcul_theme partagé."""
    signe = ((theme.get("maisons") or {}).get("Maison 1") or {}).get("signe")
    nom = _MAITRE_MODERNE.get(signe)
    position = (theme.get("planetes") or {}).get(nom) if nom else None
    if not position:
        return
    from utils.calculs_astrologiques import get_maison_planete

    cuspides = [theme["maisons"][f"Maison {numero}"]["degre"] for numero in range(1, 13)]
    theme["maitre_ascendant"] = {
        "nom": nom,
        "degre": position.get("degre"),
        "signe": position.get("signe"),
        "degre_dans_signe": position.get("degre_dans_signe"),
        "maison": position.get("maison") or get_maison_planete(float(position["degre"]), cuspides),
    }


CHAMPS_NAISSANCE = ("date", "heure", "lieu", "lat", "lon", "tzid")
CHAMPS_LIEU_RS = ("lieu", "lat", "lon", "tzid")


def _verifier_champs(donnees: dict, champs: tuple[str, ...], contexte: str) -> None:
    manquants = [champ for champ in champs if donnees.get(champ) in (None, "")]
    if manquants:
        raise ValueError(f"{contexte} incomplet : {', '.join(manquants)}.")
    try:
        float(donnees["lat"])
        float(donnees["lon"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Coordonnées invalides pour {contexte.lower()}.") from exc


def _instant_naissance_utc(naissance: dict) -> datetime:
    """Convertit l'heure locale de naissance en UTC sans deviner une heure DST."""
    try:
        locale_naive = datetime.strptime(
            f"{naissance['date']} {naissance['heure']}", "%Y-%m-%d %H:%M"
        )
        fuseau = pytz.timezone(naissance["tzid"])
        return fuseau.localize(locale_naive, is_dst=None).astimezone(pytz.UTC)
    except (ValueError, pytz.UnknownTimeZoneError) as exc:
        raise ValueError("Date, heure ou fuseau de naissance invalide.") from exc
    except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError) as exc:
        raise ValueError(
            "L'heure de naissance est ambiguë ou inexistante à cause du changement d'heure. "
            "Il faut la préciser avant le calcul."
        ) from exc


def calculer_theme_revolution_solaire(
    nom: str,
    naissance: dict,
    lieu_rs: dict,
    annee: int,
) -> dict:
    """Calcule le thème natal et le thème RS via ``calcul_theme``.

    Les dictionnaires attendent les champs ``date``, ``heure``, ``lieu``,
    ``lat``, ``lon`` et ``tzid`` pour la naissance, et tous sauf date/heure
    pour le lieu de présence au retour solaire.
    """
    _verifier_champs(naissance, CHAMPS_NAISSANCE, "Données de naissance")
    _verifier_champs(lieu_rs, CHAMPS_LIEU_RS, "Lieu de révolution solaire")
    naissance_utc = _instant_naissance_utc(naissance)
    naissance_locale = naissance_utc.astimezone(pytz.timezone(naissance["tzid"]))
    retour = trouver_retour_solaire(naissance_locale, annee)

    try:
        fuseau_rs = pytz.timezone(lieu_rs["tzid"])
    except pytz.UnknownTimeZoneError as exc:
        raise ValueError("Fuseau du lieu de révolution solaire invalide.") from exc

    retour_local = retour["retour_utc"].astimezone(fuseau_rs)
    theme_natal = calcul_theme(
        nom=nom,
        date_naissance=naissance["date"],
        heure_naissance=naissance["heure"],
        lieu_naissance=naissance["lieu"],
        lat=float(naissance["lat"]),
        lon=float(naissance["lon"]),
        dt_naissance_utc=naissance_utc,
        tzid=naissance["tzid"],
    )
    theme_rs = calcul_theme(
        nom=nom,
        date_naissance=retour_local.strftime("%Y-%m-%d"),
        heure_naissance=retour_local.strftime("%H:%M"),
        lieu_naissance=lieu_rs["lieu"],
        lat=float(lieu_rs["lat"]),
        lon=float(lieu_rs["lon"]),
        dt_naissance_utc=retour["retour_utc"],
        tzid=lieu_rs["tzid"],
    )
    _harmoniser_maitre_ascendant(theme_natal)
    _harmoniser_maitre_ascendant(theme_rs)

    return {
        "retour": retour,
        "naissance_utc": naissance_utc,
        "retour_local": retour_local,
        "naissance_locale": naissance_locale,
        "annee_rs": annee,
        "age_au_retour": annee - naissance_locale.year,
        "theme_natal": theme_natal,
        "theme_revolution_solaire": theme_rs,
        "lieu_revolution_solaire": dict(lieu_rs),
    }
