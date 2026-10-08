"""Attribue chaque facteur calculé à un seul développement du rapport."""
from __future__ import annotations

FIGURES_DEVELOPPEES = {"t_carre", "grand_trigone", "grand_carre", "cerf_volant", "yod", "diamant"}
DOMAINES = {
    1: ("orientation", "Ta façon d’aborder cette année"),
    2: ("ressources", "Ressources et engagements"),
    3: ("mobilite", "Échanges, déplacements et horizons"),
    4: ("foyer", "Foyer et ancrage"),
    5: ("creation", "Création et désirs personnels"),
    6: ("quotidien", "Travail quotidien et rythme de vie"),
    7: ("relation", "Relations et partenariats"),
    8: ("ressources", "Ressources et engagements"),
    9: ("mobilite", "Échanges, déplacements et horizons"),
    10: ("vocation", "Direction professionnelle et place publique"),
    11: ("projets", "Projets et liens collectifs"),
    12: ("retrait", "Recul et vie intérieure"),
}


def construire_plan_chapitres(donnees: dict) -> list[dict]:
    """Les identifiants renvoient aux données, sans créer de faits astrologiques.

    Figures et contacts natals rejoignent les domaines : ils ne constituent plus
    de nouveaux chapitres qui réinterprètent les mêmes planètes.
    """
    placements = donnees.get("placements_rs") or {}
    chapitres = {}

    def chapitre(code, titre):
        if code not in chapitres:
            chapitres[code] = {"titre": titre, "facteurs_a_developper": [],
                "angle": "Développer ensemble les facteurs attribués ici : leur convergence, leurs contradictions, leurs liens natals et des exemples distincts. Un facteur attribué ailleurs peut être nommé comme lien, sans réexpliquer son interprétation ni reprendre son scénario."}
        return chapitres[code]

    ouverture = chapitre("orientation", "Ascendant RS, ses maîtres et les luminaires")
    ouverture["angle"] = "Ouvrir par le signe de l’Ascendant RS, ses maîtres et leur placement, puis situer les luminaires. Cette orientation est brève : les développements des planètes attribuées aux domaines suivants sont réservés à ces domaines."
    ouverture["facteurs_a_developper"].append("ascendant_rs")
    for theme in donnees.get("themes_prioritaires") or []:
        if theme.get("code") and theme.get("libelle"):
            chapitre(theme["code"], theme["libelle"])

    def domaine(point):
        maison = (placements.get(point) or {}).get("maison")
        angles = {"Ascendant": 1, "Descendant": 7, "MC": 10, "FC": 4}
        angle = next((a.get("angle") for a in donnees.get("points_angulaires_rs") or []
                      if a.get("point") == point and a.get("angle") in angles), None)
        if angle or point in angles:
            maison = angles.get(angle or point)
        try:
            maison = int(maison)
        except (TypeError, ValueError):
            maison = None
        return DOMAINES.get(maison, ("orientation", ouverture["titre"]))

    # Le foyer de la figure donne son chapitre principal. Les autres membres
    # gardent leurs domaines : leur placement y apporte une nuance, pas un
    # second développement de la figure complète.
    for i, figure in enumerate(donnees.get("configurations_majeures_rs") or []):
        if figure.get("type") not in FIGURES_DEVELOPPEES or figure.get("etat") == "invalide":
            continue
        membres = figure.get("planetes") or []
        if len(membres) < 3:
            continue
        point = figure.get("planete_focale")
        if not point:
            point = next((p for p in membres if p in placements), None)
        code, titre = domaine(point)
        chapitre(code, titre)["facteurs_a_developper"].append(f"configurations_majeures_rs[{i}]")

    for point in placements:
        code, titre = domaine(point)
        chapitre(code, titre)["facteurs_a_developper"].append(f"placements_rs.{point}")
    for i, contact in enumerate(donnees.get("aspects_rs_natal") or []):
        if contact.get("point_rs") == "Soleil":
            continue  # Le retour solaire n'est pas une nouvelle activation natale.
        code, titre = domaine(contact.get("point_rs"))
        chapitre(code, titre)["facteurs_a_developper"].append(f"aspects_rs_natal[{i}]")
    for i, aspect in enumerate(donnees.get("aspects_internes_rs") or []):
        code, titre = domaine(aspect.get("planete1"))
        # Un aspect déjà membre d'une figure ne doit pas être redéveloppé seul.
        figure_owner = next((c for c in chapitres.values() for ref in c["facteurs_a_developper"]
            if ref.startswith("configurations_majeures_rs[")
            and {aspect.get("planete1"), aspect.get("planete2")} <= set(
                donnees["configurations_majeures_rs"][int(ref.split("[")[1][:-1])].get("planetes") or [])), None)
        (figure_owner if figure_owner is not None else chapitre(code, titre))["facteurs_a_developper"].append(f"aspects_internes_rs[{i}]")
    for i, angle in enumerate(donnees.get("points_angulaires_rs") or []):
        code, titre = domaine(angle.get("point"))
        chapitre(code, titre)["facteurs_a_developper"].append(f"points_angulaires_rs[{i}]")
    if donnees.get("profection_annuelle"):
        ouverture["facteurs_a_developper"].append("profection_annuelle")
    for i, theme in enumerate(donnees.get("themes_prioritaires") or []):
        if theme.get("code") in chapitres:
            chapitres[theme["code"]]["facteurs_a_developper"].append(f"themes_prioritaires[{i}] : utiliser ses preuves pour ce domaine, sans redévelopper un facteur attribué ailleurs")
    # Les libellés permettent de retrouver les faits dans le relevé textuel,
    # qui ne comporte pas les indices Python des tableaux.
    def libelle(ref):
        if ref.startswith("placements_rs."):
            return ref.split(".", 1)[1] + " RS : placement, maîtrises et superposition vérifiés"
        if "[" not in ref:
            return ref
        collection, index = ref.split("[", 1)
        fait = donnees[collection][int(index.split("]", 1)[0])]
        if collection == "configurations_majeures_rs":
            return str(fait.get("type")) + " : " + ", ".join(fait.get("planetes") or [])
        if collection == "aspects_rs_natal":
            return f"{fait.get('point_rs')} RS {fait.get('aspect')} {fait.get('point_natal')} natal"
        if collection == "aspects_internes_rs":
            return f"{fait.get('planete1')} RS {fait.get('aspect')} {fait.get('planete2')} RS"
        if collection == "points_angulaires_rs":
            return f"{fait.get('point')} conjoint {fait.get('angle')} RS"
        return str(fait.get("libelle")) + " : preuves du domaine, sans réinterpréter les facteurs attribués ailleurs"
    for c in chapitres.values():
        c["facteurs_a_developper"] = [libelle(ref) for ref in c["facteurs_a_developper"]]
    return [c for c in chapitres.values() if c["facteurs_a_developper"]]
