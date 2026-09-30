"""Recherche de l'instant exact d'un retour solaire tropical.

Ce module ne calcule pas de thème et ne produit aucune interprétation.
Le thème natal et le thème de révolution solaire seront ensuite calculés par
``utils.calcul_theme.calcul_theme``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import swisseph as swe


EPHEMERIS_PATH = Path(__file__).resolve().parents[2] / "ephe"


def _jour_julien_utc(date_utc: datetime) -> float:
    """Convertit un datetime UTC conscient en jour julien UT."""
    if date_utc.tzinfo is None:
        raise ValueError("La date doit inclure le fuseau UTC.")
    utc = date_utc.astimezone(timezone.utc)
    heure = (
        utc.hour
        + utc.minute / 60
        + utc.second / 3600
        + utc.microsecond / 3_600_000_000
    )
    return swe.julday(utc.year, utc.month, utc.day, heure)


def _datetime_utc(jour_julien: float) -> datetime:
    annee, mois, jour, heure = swe.revjul(jour_julien, swe.GREG_CAL)
    return datetime(annee, mois, jour, tzinfo=timezone.utc) + timedelta(hours=heure)


def trouver_retour_solaire(
    naissance_utc: datetime,
    annee: int,
) -> dict:
    """Trouve le retour tropical du Soleil pour ``annee``.

    ``naissance_utc`` est un instant conscient. Son année civile détermine
    le nombre de retours : conserver le fuseau de naissance si sa date locale
    et sa date UTC sont dans deux années différentes. Les calculs sont en UTC.
    Le résultat fournit l'instant UTC et les longitudes utilisées, sans les
    arrondir. L'appelant doit convertir l'instant dans le fuseau du lieu de
    présence, puis le transmettre à ``calcul_theme``.
    """
    if naissance_utc.tzinfo is None:
        raise ValueError("L'instant de naissance doit inclure son fuseau horaire.")
    if isinstance(annee, bool) or not isinstance(annee, int):
        raise ValueError("L'année doit être un entier.")
    if annee <= naissance_utc.year:
        raise ValueError("L'année du retour doit être postérieure à l'année de naissance.")

    swe.set_ephe_path(str(EPHEMERIS_PATH))
    flags = swe.FLG_SWIEPH
    longitude_natale = swe.calc_ut(
        _jour_julien_utc(naissance_utc), swe.SUN, flags
    )[0][0] % 360

    # Viser le cycle anniversaire, pas le premier passage après le 25 décembre.
    # L'estimation sert uniquement à encadrer la recherche exacte ; elle gère
    # aussi le 29 février et les anniversaires proches du changement d'année.
    age = annee - naissance_utc.year
    estimation = naissance_utc.astimezone(timezone.utc) + timedelta(days=365.2422 * age)
    debut_recherche = _jour_julien_utc(estimation - timedelta(days=7))
    retour_julien = swe.solcross_ut(longitude_natale, debut_recherche, flags)
    retour_utc = _datetime_utc(retour_julien)
    if abs((retour_utc - estimation).total_seconds()) > 7 * 86400:
        raise RuntimeError("Le retour solaire trouvé est hors du cycle anniversaire demandé.")
    longitude_retour = swe.calc_ut(retour_julien, swe.SUN, flags)[0][0] % 360
    ecart = abs((longitude_retour - longitude_natale + 180) % 360 - 180)

    if ecart > 0.000001:
        raise RuntimeError(
            f"Retour solaire imprécis : écart de {ecart:.9f}° avec le Soleil natal."
        )

    return {
        "retour_utc": retour_utc,
        "longitude_soleil_natale": longitude_natale,
        "longitude_soleil_retour": longitude_retour,
        "ecart_degres": ecart,
        "ephemerides": "Swiss Ephemeris",
    }
