from .config import (
    ASPECTS_MAJEURS,
    ASPECTS_MARS_FLASH,
    CIBLES_MARS_ORBE_ELARGI,
    IMPORTANCE_MIN_AFFICHAGE,
    MAX_TRANSITS_AFFICHES,
    MAX_TRANSITS_MARS_AFFICHES,
    ORBE_MARS_FLASH,
    ORBE_MARS_FLASH_CIBLES_MAJEURES,
    PLANETES_LENTES,
)


def est_transit_mars_flash_pertinent(transit) -> bool:
    """Garde uniquement les activations brèves et nettes de Mars."""
    if transit.planete_transit != "Mars":
        return False
    if transit.aspect not in ASPECTS_MARS_FLASH:
        return False

    orbe_max = (
        ORBE_MARS_FLASH_CIBLES_MAJEURES
        if transit.planete_natale in CIBLES_MARS_ORBE_ELARGI
        else ORBE_MARS_FLASH
    )
    return transit.orbe <= orbe_max


def selectionner_transits_flash(aspects: list) -> list:
    """Sélectionne les transits de fond et au plus un déclencheur martien."""
    transits_lents = [
        transit for transit in aspects
        if transit.planete_transit in PLANETES_LENTES
        and transit.aspect in ASPECTS_MAJEURS
        and transit.importance >= IMPORTANCE_MIN_AFFICHAGE
    ]
    transits_mars = [
        transit for transit in aspects
        if est_transit_mars_flash_pertinent(transit)
        and transit.importance >= IMPORTANCE_MIN_AFFICHAGE
    ][:MAX_TRANSITS_MARS_AFFICHES]

    places_transits_lents = MAX_TRANSITS_AFFICHES - len(transits_mars)
    selection = transits_lents[:places_transits_lents] + transits_mars
    return sorted(selection, key=lambda transit: (-transit.importance, transit.orbe))
