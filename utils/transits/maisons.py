# utils/transits/maisons.py

import logging

logger = logging.getLogger(__name__)


def extraire_cuspides(theme: dict) -> list[float]:
    """
    Transforme theme['maisons'] en liste de 12 cuspides.
    Ordre : Maison 1 → Maison 12.
    """
    maisons = theme.get("maisons", {})
    cuspides = []

    for i in range(1, 13):
        cle = f"Maison {i}"

        if cle not in maisons:
            raise ValueError(f"{cle} manquante dans le thème")

        degre = maisons[cle].get("degre")

        if degre is None:
            raise ValueError(f"{cle} sans degré dans le thème")

        cuspides.append(float(degre))

    return cuspides


def trouver_maison(longitude: float, cuspides: list[float]) -> int | None:
    """
    Trouve dans quelle maison tombe une longitude.
    Les cuspides sont en ordre Maison 1 → Maison 12.
    On teste les arcs maison par maison en avançant dans le zodiaque.
    """
    if not cuspides or len(cuspides) != 12:
        logger.warning("trouver_maison: cuspides invalides (%s)", cuspides)
        return None

    lon = longitude % 360

    for i in range(12):
        debut = cuspides[i] % 360
        fin = cuspides[(i + 1) % 12] % 360

        distance_maison = (fin - debut) % 360
        distance_lon = (lon - debut) % 360

        if 0 <= distance_lon < distance_maison:
            return i + 1

    logger.warning("trouver_maison: aucune maison trouvée pour lon=%.2f", longitude)
    return None


def maisons_gouvernees(planete: str, house_rulers_map: dict) -> list[int]:
    """
    Récupère les maisons gouvernées par une planète depuis ton thème.
    """
    return house_rulers_map.get(planete, [])
