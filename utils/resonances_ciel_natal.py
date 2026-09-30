"""Détecte les configurations du ciel qui répètent un aspect natal."""

from __future__ import annotations

from itertools import combinations


ASPECTS = (
    ("conjonction", 0, 3),
    ("sextile", 60, 3),
    ("carré", 90, 3),
    ("trigone", 120, 3),
    ("quinconce", 150, 3),
    ("opposition", 180, 3),
)
PLANETES = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton",
}
PLANETES_PERSONNELLES = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}


def _normaliser_aspect(nom: str | None) -> str:
    return (nom or "").lower().replace("é", "e").replace("è", "e")


def _aspect(longitude_a: float, longitude_b: float) -> dict | None:
    distance = abs((longitude_a - longitude_b + 180) % 360 - 180)
    for nom, angle, maximum in ASPECTS:
        orbe = abs(distance - angle)
        if orbe <= maximum:
            return {"aspect": nom, "orbe": round(orbe, 3)}
    return None


def _aspects_ciel(positions: dict) -> list[dict]:
    resultat = []
    points = {
        nom: float(donnees["longitude"])
        for nom, donnees in positions.items()
        if nom in PLANETES and donnees.get("longitude") is not None
    }
    for premiere, seconde in combinations(sorted(points), 2):
        aspect = _aspect(points[premiere], points[seconde])
        if aspect:
            resultat.append({"planete1": premiere, "planete2": seconde, **aspect})
    return resultat


def _aspects_natals(theme_natal: dict) -> list[dict]:
    resultat = []
    for aspect in theme_natal.get("aspects") or []:
        premiere, seconde = aspect.get("planete1"), aspect.get("planete2")
        if premiere not in PLANETES or seconde not in PLANETES:
            continue
        resultat.append({
            "planete1": premiere,
            "planete2": seconde,
            "aspect": _normaliser_aspect(aspect.get("aspect")),
            "orbe": aspect.get("orbe"),
        })
    return resultat


def detecter_resonances_configurations_ciel_natal(
    photo_transits: dict,
    theme_natal: dict,
) -> list[dict]:
    """Répétition d'un duo/aspect natal dans le ciel, avec activation directe.

    Une répétition seule est une résonance. Elle devient « renforcée » quand
    l'un des deux transits touche aussi ce duo natal ou un angle natal.
    """
    aspects_ciel = _aspects_ciel(photo_transits.get("positions") or {})
    aspects_natals = _aspects_natals(theme_natal)
    transits = photo_transits.get("transits") or []
    resultat = []
    for ciel in aspects_ciel:
        duo = frozenset((ciel["planete1"], ciel["planete2"]))
        # Une configuration entre lentes décrit le climat collectif. Pour une
        # résonance d'abonné, elle doit rencontrer au moins une planète
        # personnelle du thème et ne sera donc pas remontée seule.
        if not duo.intersection(PLANETES_PERSONNELLES):
            continue
        for natal in aspects_natals:
            if frozenset((natal["planete1"], natal["planete2"])) != duo:
                continue
            meme_aspect = _normaliser_aspect(ciel["aspect"]) == natal["aspect"]
            activations = [
                {
                    "planete_transit": transit.get("planete_transit"),
                    "point_natal": transit.get("planete_natale"),
                    "aspect": transit.get("aspect"),
                    "orbe": transit.get("orbe"),
                }
                for transit in transits
                if (
                    transit.get("planete_transit") in duo
                    and transit.get("planete_natale") in (*duo, "Ascendant", "Descendant", "Milieu du Ciel", "Fond du Ciel")
                )
            ]
            resultat.append({
                "planetes": sorted(duo),
                "aspect_ciel": ciel["aspect"],
                "orbe_ciel": ciel["orbe"],
                "aspect_natal": natal["aspect"],
                "orbe_natal": natal["orbe"],
                "repetition_exacte": meme_aspect,
                "activations_directes": activations,
                "niveau": "renforcee" if activations else "resonance",
            })
    return sorted(
        resultat,
        key=lambda item: (item["niveau"] != "renforcee", item["orbe_ciel"]),
    )
