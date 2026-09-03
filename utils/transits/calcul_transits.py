# utils/transits/calcul_transits.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any
import swisseph as swe

from .config import PLANETES_TRANSIT
import logging

logger = logging.getLogger(__name__)


PLANETES_SWISSEPH = {
    "Soleil": swe.SUN,
    "Lune": swe.MOON,
    "Mercure": swe.MERCURY,
    "Vénus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturne": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluton": swe.PLUTO,
}


SIGNES = [
    "Bélier",
    "Taureau",
    "Gémeaux",
    "Cancer",
    "Lion",
    "Vierge",
    "Balance",
    "Scorpion",
    "Sagittaire",
    "Capricorne",
    "Verseau",
    "Poissons",
]


def longitude_to_signe(longitude: float) -> dict:
    """
    Convertit une longitude zodiacale 0-360 en signe + degré dans le signe.
    """
    signe_index = int(longitude // 30)
    degre_signe = longitude % 30

    return {
        "signe": SIGNES[signe_index],
        "degre": round(degre_signe, 2),
        "longitude": round(longitude, 4),
    }


def calculer_positions_transits(date_transit: datetime | None = None) -> Dict[str, Any]:
    """
    Calcule les positions des planètes en transit pour une date donnée.

    V1 :
    - positions géocentriques
    - longitude zodiacale tropicale
    - pas encore les maisons
    - pas encore les aspects au natal
    """

    if date_transit is None:
        date_transit = datetime.now()

    jd = swe.julday(
        date_transit.year,
        date_transit.month,
        date_transit.day,
        date_transit.hour + date_transit.minute / 60 + date_transit.second / 3600,
    )

    positions = {}

    for nom_planete in PLANETES_TRANSIT:
        swe_id = PLANETES_SWISSEPH.get(nom_planete)

        if swe_id is None:
            logger.warning(
                "Planète inconnue dans PLANETES_SWISSEPH : %s",
                nom_planete,
            )
            continue

        result = swe.calc_ut(jd, swe_id)

        # Selon pyswisseph : result = ((lon, lat, dist, speed_lon...), flags)
        coords = result[0]
        longitude = coords[0] % 360
        vitesse = coords[3]

        positions[nom_planete] = {
            **longitude_to_signe(longitude),
            "retrograde": vitesse < 0,
            "vitesse": round(vitesse, 6),
        }

    return {
        "date_transit": date_transit.isoformat(),
        "julian_day": jd,
        "positions": positions,
    }

if __name__ == "__main__":
    resultat = calculer_positions_transits()
    for planete, infos in resultat["positions"].items():
        print(planete, infos)
