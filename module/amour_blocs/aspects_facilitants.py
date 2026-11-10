"""Règle locale validée : sextiles/trigones à 3° maximum, sans compensation."""
import math


def est_facilitant(aspect):
    return str(aspect).strip().casefold() in ('sextile', 'trigone')


def orbe_facilitant(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        orbe = float(valeur)
    except (ValueError, TypeError):
        return None
    return orbe if math.isfinite(orbe) and 0 <= orbe <= 3 else None


def ressource_factuelle(planete, aspect, autre, orbe):
    return (f'Ressource à examiner : {planete} {aspect} {autre} (orbe {orbe:.2f}°). '
            'Décris sa portée dans ce chapitre sans annuler les tensions ni inventer un vécu.')
