"""Filtres des aspects RS/natals et contacts validés ; calculs conservés."""

from copy import deepcopy

VERSION_FILTRE_ASPECTS = "aspects_sans_noeuds_chiron_fortune_4"
PLANETES_LENTES = frozenset({"Uranus", "Neptune", "Pluton"})
NOEUDS = frozenset({"Rahu", "Ketu"})
POINTS_ASPECTS_EXCLUS = NOEUDS | {"Chiron", "Part de Fortune"}
AXES_FIXES = {frozenset({"Ascendant", "Descendant"}), frozenset({"MC", "FC"})}


def aspect_interne_autorise(aspect):
    """Même filtre dans les deux thèmes, quel que soit l'ordre des participants."""
    paire = frozenset({aspect["planete1"], aspect["planete2"]})
    if paire & POINTS_ASPECTS_EXCLUS:
        return False
    if paire in AXES_FIXES:
        return False
    if paire & PLANETES_LENTES and "Lune Noire" in paire:
        return False
    return True


def fait_autorise(fait):
    """Nœuds sans aspects ; Chiron et Part de Fortune hors lecture. Calculs conservés."""
    categorie, source = fait.get("type"), fait.get("source")
    valeur = fait.get("valeur", {})
    # Positions, superpositions et anciennes cibles de transit restent archivées,
    # mais la Part de Fortune ne participe plus à aucun prompt de lecture.
    if fait.get("objet") == "Part de Fortune" or valeur.get("cible") == "Part de Fortune":
        return False
    if source in {"natal", "rs", "rs_vers_natal", "natal_vers_rs"} and fait.get("objet") == "Chiron":
        return False
    if categorie == "contact":
        return not {valeur.get("point_rs"), valeur.get("point_natal")} & POINTS_ASPECTS_EXCLUS
    if source not in {"natal", "rs"}:
        return True
    if categorie == "aspects":
        return aspect_interne_autorise(valeur)
    if categorie == "angularites":
        return not {valeur.get("point"), valeur.get("angle")} & POINTS_ASPECTS_EXCLUS
    if categorie == "configurations":
        return not set(valeur.get("planetes", [])) & POINTS_ASPECTS_EXCLUS
    return True


def filtrer_historique(analyses, faits):
    """Retire les références exclues d'une copie ; aucune lecture IA réécrite."""
    exclus = {cle for cle, fait in faits.items() if not fait_autorise(fait)}
    resultat = deepcopy(analyses)
    for analyse in resultat.values():
        for enjeu in analyse.get("enjeux", []):
            enjeu["preuves"] = [cle for cle in enjeu.get("preuves", []) if cle not in exclus]
            for exemple in enjeu.get("exemples", []):
                exemple["preuves"] = [cle for cle in exemple.get("preuves", []) if cle not in exclus]
        if isinstance(analyse.get("couverture"), list):
            lignes = []
            for ligne in analyse["couverture"]:
                ligne["faits"] = [cle for cle in ligne["faits"] if cle not in exclus]
                if ligne["faits"]:
                    lignes.append(ligne)
            analyse["couverture"] = lignes
    return resultat
