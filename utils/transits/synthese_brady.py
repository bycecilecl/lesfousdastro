# utils/transits/synthese_brady.py

THEMES_MAISONS = {
    1: "identité, corps, affirmation de soi",
    2: "ressources, sécurité matérielle, valeurs",
    3: "communication, apprentissages, fratrie",
    4: "foyer, racines, vie privée",
    5: "création, désir, enfants, plaisir",
    6: "travail quotidien, santé, service",
    7: "relation, engagement, l’autre",
    8: "transformation, intimité, ressources partagées",
    9: "croyances, études, voyages, vision du monde",
    10: "carrière, réputation, direction de vie",
    11: "réseaux, projets, collectif",
    12: "intériorité, retrait, inconscient, dissolution",
}


def extraire_maisons_activees(transit) -> list[int]:
    ctx = transit.contexte or {}
    maisons = set()

    for key in [
        "maison_transit",
        "maison_natale_transit",
        "maison_natale_planete",
    ]:
        value = ctx.get(key)
        if isinstance(value, int):
            maisons.add(value)

    for key in [
        "maisons_gouvernees_transit",
        "maisons_gouvernees_natale",
    ]:
        values = ctx.get(key) or []
        for v in values:
            if isinstance(v, int):
                maisons.add(v)

    return sorted(maisons)


def synthese_brady(transit) -> str:
    maisons = extraire_maisons_activees(transit)

    if not maisons:
        return "Aucun champ de maison clairement identifié pour ce transit."

    themes = [
        f"maison {m} : {THEMES_MAISONS.get(m, 'thème non défini')}"
        for m in maisons
    ]

    return "Champs activés : " + " ; ".join(themes) + "."
