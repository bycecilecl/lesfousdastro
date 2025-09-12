# =============================================================================
# UTILITAIRE : get_planetes_en_maison
# -----------------------------------------------------------------------------
# Rôle :
#   - Récupère la liste des planètes présentes dans une maison donnée
#   - Utilise en priorité l’info "maison" stockée dans data['planetes'][*]
#   - En fallback, fusionne avec la liste data['maisons'][<num>]['planetes']
#
# Paramètres :
#   - data (dict) : thème astrologique complet
#   - maison_num (int/str) : numéro de la maison à examiner
#   - inclure_points (bool) : si False, exclut les points/angles
#       comme Ascendant, Nœuds, Lune Noire, etc.
#
# Retour :
#   - Liste des noms de planètes trouvées dans cette maison
#
# Utilisation typique :
#   - Lorsqu’une analyse a besoin de savoir quelles planètes sont
#     présentes dans une maison (ex : Maison 7 → relations)
#   - Pour enrichir les interprétations textuelles ou vérifier des
#     configurations (amas, aspects angulaires, etc.)
#
# Exemple :
#   planetes_maison_10 = get_planetes_en_maison(data, 10)
# =============================================================================

def get_planetes_en_maison(data, maison_num, inclure_points=False):
    """
    Retourne la liste des planètes présentes dans une maison donnée.
    Priorité aux infos de data['planetes'][*]['maison'].
    En fallback, fusionne avec data['maisons'][str(maison)]['planetes'] si présent.
    """
    maison_str = str(maison_num)
    planetes = data.get("planetes", {})
    maisons = data.get("maisons", {})
    
    # Points/angles à exclure si inclure_points=False
    points_a_exclure = {
        "Ascendant", "Descendant", "Milieu du Ciel", "Fond du Ciel",
        "Rahu", "Ketu", "Noeud Nord", "Noeud Sud",
        "Lune Noire", "Lilith"
    }

    trouves = []

    # 1) Source fiable : chaque planète qui a "maison" == maison_num
    for nom, infos in planetes.items():
        if not isinstance(infos, dict):
            continue
        m = infos.get("maison")
        # Comparaison souple (int/str)
        if m is not None and str(m) == maison_str:
            if not inclure_points and nom in points_a_exclure:
                continue
            trouves.append(nom)

    # 2) Fallback/merge : liste déclarée dans data["maisons"]["X"]["planetes"]
    listed = set(trouves)
    liste_maison = maisons.get(maison_str, {}).get("planetes", []) or []
    for nom in liste_maison:
        if not inclure_points and nom in points_a_exclure:
            continue
        if nom not in listed:
            trouves.append(nom)

    return trouves