"""Noyau natal utilisé comme grille de lecture d'une révolution solaire."""

from __future__ import annotations


LUMINAIRES = ("Soleil", "Lune")
PLANETES_PERSONNELLES = ("Mercure", "Vénus", "Mars")
ANGLES = {"Ascendant", "MC", "Descendant", "FC"}


def _copie_point(theme: dict, nom: str) -> dict | None:
    donnees = (theme.get("planetes") or {}).get(nom)
    return dict(donnees) if donnees else None


def extraire_portrait_natal_rs(theme_natal: dict, *, orbe_configuration: float = 3.0) -> dict:
    """Retourne les repères natals à mettre en résonance avec une RS.

    Il ne produit pas d'interprétation et ne prétend pas résumer tout le thème
    natal. Son rôle est de préserver les éléments qui donnent son sens propre
    à une même révolution solaire selon la personne.
    """
    maitre = dict(theme_natal.get("maitre_ascendant") or {})
    nom_maitre = maitre.get("nom")
    if nom_maitre:
        maitre["maisons_gouvernees"] = list(
            (theme_natal.get("house_rulers_map") or {}).get(nom_maitre, [])
        )

    facteurs = {"Ascendant", *LUMINAIRES, *PLANETES_PERSONNELLES}
    if nom_maitre:
        facteurs.add(nom_maitre)
    configurations = []
    for aspect in theme_natal.get("aspects_avec_angles") or []:
        if (
            float(aspect.get("orbe", 999)) <= orbe_configuration
            and ({aspect.get("planete1"), aspect.get("planete2")} & facteurs)
        ):
            configurations.append(dict(aspect))

    return {
        "ascendant": _copie_point(theme_natal, "Ascendant"),
        "maitre_ascendant": maitre,
        "luminaires": {
            nom: _copie_point(theme_natal, nom) for nom in LUMINAIRES
        },
        "planetes_personnelles": {
            nom: _copie_point(theme_natal, nom) for nom in PLANETES_PERSONNELLES
        },
        "configurations_structurantes": configurations,
        "points_forts_calcules": list(theme_natal.get("points_forts") or []),
        "orbe_configuration": orbe_configuration,
    }
