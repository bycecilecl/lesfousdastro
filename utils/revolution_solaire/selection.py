"""Hiérarchisation des facteurs pour la lecture de la RS seule.

Ce filtre prépare les faits prioritaires. Il ne produit aucune interprétation.
"""

from __future__ import annotations


PLANETES_MAJEURES = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton",
}
TYPES_FIGURES_MAJEURES = {"stellium", "t_carre", "grand_trigone", "grand_carre", "diamant"}
POINTS_ASPECTS_DIRECTEURS = PLANETES_MAJEURES | {"Ascendant", "MC", "Descendant", "FC"}
ANGLES = {"Ascendant", "MC", "Descendant", "FC"}
PLANETES_NATALES_PRIORITAIRES = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}


def _implique(aspect: dict, points: set[str]) -> bool:
    return aspect.get("planete1") in points or aspect.get("planete2") in points


def _est_axe_automatique(aspect: dict) -> bool:
    return {aspect.get("planete1"), aspect.get("planete2")} in (
        {"Ascendant", "Descendant"},
        {"MC", "FC"},
    )


def _selectionner_resonances_natales(
    donnees: dict,
    points_rs: set[str],
) -> dict:
    """Hiérarchise les contacts RS–natal sans encore les interpréter."""
    portrait = donnees.get("portrait_natal") or {}
    maitre_natal = (portrait.get("maitre_ascendant") or {}).get("nom")
    points_natals = set(PLANETES_NATALES_PRIORITAIRES)
    if maitre_natal:
        points_natals.add(maitre_natal)

    contacts = []
    for aspect in donnees.get("aspects_rs_natal") or []:
        point_rs = aspect.get("point_rs")
        point_natal = aspect.get("point_natal")
        # Un angle RS au contact d'une planète natale est aussi un signal fort,
        # même si l'angle ne figurait pas parmi les planètes directrices.
        est_prioritaire = (
            (point_rs in points_rs and (point_natal in points_natals or point_natal in ANGLES))
            or (point_rs in ANGLES and point_natal in points_natals)
        )
        if est_prioritaire:
            contacts.append(dict(aspect))

    contacts.sort(key=lambda item: float(item.get("orbe", 99)))

    configurations_reactivees = []
    for configuration in portrait.get("configurations_structurantes") or []:
        membres = {configuration.get("planete1"), configuration.get("planete2")}
        activations = [
            contact for contact in contacts
            if contact.get("point_natal") in membres
        ]
        if activations:
            configurations_reactivees.append({
                "configuration_natale": dict(configuration),
                "contacts_rs_natal": activations,
            })

    return {
        "contacts_prioritaires": contacts,
        "configurations_natales_reactivees": configurations_reactivees,
    }


def _orbe_directeur(aspect: dict) -> float:
    points = {aspect.get("planete1"), aspect.get("planete2")}
    return 6.0 if points & {"Soleil", "Lune"} else 5.0


def selectionner_facteurs_directeurs_rs(donnees: dict) -> dict:
    """Sélectionne les facteurs de premier rang avant tout lien au natal.

    Les aspects ne sont retenus que s'ils impliquent l'Ascendant RS, un de ses
    maîtres, le Soleil ou la Lune. Les points symboliques restent secondaires.
    """
    placements = donnees.get("placements_rs") or {}
    maitres = donnees.get("maitres_ascendant_rs") or []
    noms_maitres = {fiche["nom"] for fiche in maitres if fiche.get("nom")}
    points_directeurs = {"Ascendant", "Soleil", "Lune", *noms_maitres}

    maisons_chargees = []
    for maison, noms in (donnees.get("maisons_rs_occupees") or {}).items():
        planetes = [nom for nom in noms if nom in PLANETES_MAJEURES]
        if len(planetes) >= 2:
            maisons_chargees.append({"maison": maison, "planetes": planetes})

    aspects = [
        dict(aspect)
        for aspect in donnees.get("aspects_internes_rs", [])
        if (
            _implique(aspect, points_directeurs)
            and not _est_axe_automatique(aspect)
            and {aspect.get("planete1"), aspect.get("planete2")} <= POINTS_ASPECTS_DIRECTEURS
            and float(aspect.get("orbe", 999)) <= _orbe_directeur(aspect)
        )
    ]
    aspects.sort(key=lambda aspect: float(aspect.get("orbe", 99)))

    figures = [
        configuration
        for configuration in donnees.get("configurations_majeures_rs", [])
        if configuration.get("type") in TYPES_FIGURES_MAJEURES
        and set(configuration.get("planetes") or []) & points_directeurs
    ]

    angularites = [
        dict(item)
        for item in donnees.get("points_angulaires_rs", [])
        if item.get("point") in PLANETES_MAJEURES
    ]

    noms_gouvernance = []

    def ajouter_gouvernance(nom: str) -> None:
        if nom in PLANETES_MAJEURES and nom not in noms_gouvernance:
            noms_gouvernance.append(nom)

    for fiche in maitres:
        ajouter_gouvernance(fiche.get("nom"))
    ajouter_gouvernance("Soleil")
    ajouter_gouvernance("Lune")
    for figure in figures:
        for nom in figure.get("planetes") or []:
            ajouter_gouvernance(nom)
    for maison in maisons_chargees:
        for nom in maison.get("planetes") or []:
            ajouter_gouvernance(nom)

    # Saturne, Uranus et Neptune sont toujours étudiés dans la RS. Leurs
    # maîtrises RS et natales doivent donc être transmises au contrat factuel,
    # même lorsqu'ils ne sont ni maîtres d'Ascendant ni sommets d'une figure.
    # Sans cela, le modèle reçoit leur placement mais invente parfois les
    # maisons qu'ils gouvernent pour compléter son interprétation.
    for nom in ("Saturne", "Uranus", "Neptune"):
        ajouter_gouvernance(nom)

    gouvernance_directeurs = []
    for nom in noms_gouvernance:
        placement = placements.get(nom)
        if not placement:
            continue
        gouvernance_directeurs.append({
            "planete": nom,
            "maison_placement_rs": placement.get("maison"),
            "maisons_gouvernees_rs": list(placement.get("maisons_gouvernees_rs") or []),
            "maisons_gouvernees_interceptees_rs": list(placement.get("maisons_gouvernees_interceptees_rs") or []),
            "maison_placement_natale": placement.get("maison_natale"),
            "maisons_gouvernees_natales": list(placement.get("maisons_gouvernees_natales") or []),
            "maisons_gouvernees_interceptees_natales": list(placement.get("maisons_gouvernees_interceptees_natales") or []),
        })

    # Les lentes qui ne portent pas le noyau directeur restent indispensables :
    # leur maison RS décrit les domaines durablement colorés par l'année.
    planetes_contextuelles = []
    for nom in ("Saturne", "Uranus", "Neptune"):
        placement = placements.get(nom)
        if not placement:
            continue
        aspects_contextuels = [
            dict(aspect) for aspect in donnees.get("aspects_internes_rs", [])
            if (
                nom in {aspect.get("planete1"), aspect.get("planete2")}
                and float(aspect.get("orbe", 999)) <= 5.0
                and not _est_axe_automatique(aspect)
            )
        ]
        planetes_contextuelles.append({
            "planete": nom,
            "placement_rs": dict(placement),
            "aspects_internes_rs": aspects_contextuels,
        })

    # Les lentes contextualisent durablement l'année. Leurs contacts au natal
    # doivent donc être transmis au chapitre des résonances, même lorsqu'elles
    # ne sont ni maître d'Ascendant ni dans une figure géométrique.
    noms_contextuels = {
        item.get("planete") for item in planetes_contextuelles if item.get("planete")
    }
    points_rs_resonance = {
        "Ascendant", "MC", "Descendant", "FC", *noms_gouvernance, *noms_contextuels
    }
    resonances_natales = _selectionner_resonances_natales(donnees, points_rs_resonance)

    return {
        "ascendant_rs": donnees.get("ascendant_rs"),
        "maitres_ascendant_rs": maitres,
        "soleil_rs": placements.get("Soleil"),
        "lune_rs": placements.get("Lune"),
        "figures_majeures": figures,
        "maisons_chargees": maisons_chargees,
        "planetes_angulaires": angularites,
        "aspects_directeurs": aspects,
        "gouvernance_directeurs": gouvernance_directeurs,
        "interceptions_rs": donnees.get("interceptions_rs") or {},
        "planetes_contextuelles": planetes_contextuelles,
        "resonances_natales": resonances_natales,
    }
