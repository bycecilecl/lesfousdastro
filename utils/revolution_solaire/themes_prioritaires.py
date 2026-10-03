"""Détection factuelle des domaines majeurs d'une révolution solaire.

Le module ne produit aucune interprétation. Il rassemble seulement des
convergences indépendantes afin que le rapport ne laisse pas disparaître un
domaine surchargé (relation, vocation, foyer...) au profit d'une figure ou
d'un unique fil narratif.
"""

from __future__ import annotations

from collections import defaultdict


THEMES = {
    "relation": {"libelle": "Vie relationnelle et amoureuse", "maisons": {5, 7}},
    "vocation": {"libelle": "Travail, vocation et visibilité", "maisons": {10}},
    "foyer": {"libelle": "Foyer, racines et lieu de vie", "maisons": {4}},
    "ressources": {"libelle": "Ressources, argent et transformations", "maisons": {2, 8}},
    "quotidien": {"libelle": "Quotidien, travail et santé", "maisons": {6}},
    "creation": {"libelle": "Créativité, désir et enfants", "maisons": {5}},
    "mobilite": {"libelle": "Communication, mobilité et horizons", "maisons": {3, 9}},
}

ANGLES_RELATIONNELS = {"Ascendant", "Descendant"}
ANGLES_VOCATION = {"MC", "FC"}
PLANETES_RELATIONNELLES = {"Vénus", "Uranus", "Neptune"}
PLANETES_DOMAINES = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton",
}


def _numero(maison) -> int | None:
    try:
        return int(maison)
    except (TypeError, ValueError):
        return None


def _nom_aspect(aspect: dict) -> str:
    return (
        f"{aspect.get('planete1')} {str(aspect.get('aspect', '')).lower()} "
        f"{aspect.get('planete2')} ({float(aspect.get('orbe', 0)):.2f}°)"
    )


def _ajouter(preuves: dict[str, list[dict]], theme: str, cle: str, texte: str) -> None:
    if cle not in {item["cle"] for item in preuves[theme]}:
        preuves[theme].append({"cle": cle, "texte": texte})


def _planetes_actives(donnees: dict) -> set[str]:
    """Planètes assez engagées pour que leur maîtrise compte comme répétition."""
    actives = {
        item.get("point")
        for item in donnees.get("points_angulaires_rs") or []
        if item.get("point")
    }
    actives.update(
        fiche.get("nom")
        for fiche in donnees.get("maitres_ascendant_rs") or []
        if fiche.get("nom")
    )
    for figure in donnees.get("configurations_majeures_rs") or []:
        actives.update(figure.get("planetes") or [])
    for aspect in donnees.get("aspects_internes_rs") or []:
        if float(aspect.get("orbe", 99)) <= 4.0:
            actives.update({aspect.get("planete1"), aspect.get("planete2")})
    for aspect in donnees.get("aspects_rs_natal") or []:
        if float(aspect.get("orbe", 99)) <= 3.0:
            actives.add(aspect.get("point_rs"))
    return {nom for nom in actives if nom}


def detecter_themes_prioritaires_rs(donnees: dict, *, seuil: int = 3) -> list[dict]:
    """Retourne les thèmes ayant au moins ``seuil`` convergences calculées.

    Une même planète peut soutenir plusieurs domaines, mais une même preuve ne
    peut être comptée qu'une fois dans un domaine. Les thèmes ne sont pas des
    prédictions : ce sont des obligations de couverture pour le rapport.
    """
    placements = donnees.get("placements_rs") or {}
    actifs = _planetes_actives(donnees)
    preuves: dict[str, list[dict]] = defaultdict(list)

    for code, definition in THEMES.items():
        maisons = definition["maisons"]
        for nom, placement in placements.items():
            if nom not in PLANETES_DOMAINES:
                continue
            maison = _numero(placement.get("maison"))
            if maison in maisons:
                _ajouter(
                    preuves,
                    code,
                    f"placement:{nom}:M{maison}",
                    f"{nom} RS est placé en M{maison} RS.",
                )
            gouvernees = {_numero(item) for item in placement.get("maisons_gouvernees_rs") or []}
            concernees = sorted(maisons & gouvernees)
            if concernees and nom in actifs:
                _ajouter(
                    preuves,
                    code,
                    f"maitrise:{nom}:{','.join(map(str, concernees))}",
                    f"{nom} RS gouverne " + " et ".join(f"la M{numero}" for numero in concernees)
                    + " et constitue un facteur actif de la RS.",
                )

    for angularite in donnees.get("points_angulaires_rs") or []:
        nom = angularite.get("point")
        angle = angularite.get("angle")
        if nom not in PLANETES_DOMAINES:
            continue
        texte = f"{nom} RS est à {float(angularite.get('orbe', 0)):.2f}° de {angle} RS."
        if angle == "FC":
            _ajouter(preuves, "foyer", f"angularite_foyer:{nom}:FC", texte)
        elif angle == "MC":
            _ajouter(preuves, "vocation", f"angularite_vocation:{nom}:MC", texte)
        elif angle == "Descendant" and nom in PLANETES_RELATIONNELLES:
            _ajouter(preuves, "relation", f"angularite_relation:{nom}:Dsc", texte)

    for aspect in donnees.get("aspects_internes_rs") or []:
        if float(aspect.get("orbe", 99)) > 3.0:
            continue
        points = {aspect.get("planete1"), aspect.get("planete2")}
        texte = "Aspect interne RS : " + _nom_aspect(aspect) + "."
        if {"Vénus", "Uranus"} <= points:
            _ajouter(preuves, "relation", f"aspect_relation:{_nom_aspect(aspect)}", texte)
        if points & {"Vénus", "Neptune"} == {"Vénus", "Neptune"}:
            _ajouter(preuves, "relation", f"aspect_venus_neptune:{_nom_aspect(aspect)}", texte)

    contacts_axe_relationnel: dict[str, list[dict]] = defaultdict(list)
    for aspect in donnees.get("aspects_rs_natal") or []:
        if float(aspect.get("orbe", 99)) > 3.0:
            continue
        point_rs = aspect.get("point_rs")
        point_natal = aspect.get("point_natal")
        texte = (
            f"Contact RS–natal : {point_rs} RS {str(aspect.get('aspect', '')).lower()} "
            f"{point_natal} natal ({float(aspect.get('orbe', 0)):.2f}°)."
        )
        if point_natal in ANGLES_RELATIONNELS and point_rs in PLANETES_RELATIONNELLES | {"Mercure"}:
            contacts_axe_relationnel[point_rs].append(aspect)
        if point_natal == "Vénus" and point_rs in {"Uranus", "Neptune", "Pluton", "Saturne"}:
            _ajouter(preuves, "relation", f"venus_natale:{point_rs}:{aspect.get('aspect')}", texte)
        if point_natal in ANGLES_VOCATION and point_rs in {"Soleil", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Pluton"}:
            _ajouter(preuves, "vocation", f"angle_vocation:{point_rs}:{point_natal}:{aspect.get('aspect')}", texte)
        if point_natal == "FC" and point_rs in {"Lune", "Vénus", "Mars", "Saturne", "Uranus", "Neptune", "Pluton"}:
            _ajouter(preuves, "foyer", f"angle_foyer:{point_rs}:{aspect.get('aspect')}", texte)

    for point_rs, contacts in contacts_axe_relationnel.items():
        details = ", ".join(
            f"{str(item.get('aspect', '')).lower()} {item.get('point_natal')} natal ({float(item.get('orbe', 0)):.2f}°)"
            for item in contacts
        )
        _ajouter(
            preuves,
            "relation",
            f"axe_relation:{point_rs}",
            f"{point_rs} RS active l'axe Ascendant–Descendant natal : {details}.",
        )

    resultat = []
    for code, definition in THEMES.items():
        elements = preuves[code]
        if len(elements) >= seuil:
            resultat.append({
                "code": code,
                "libelle": definition["libelle"],
                "repetitions": len(elements),
                "preuves": elements,
            })
    return sorted(resultat, key=lambda item: (-item["repetitions"], item["libelle"]))
