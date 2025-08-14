# ────────────────────────────────────────────────
# UTIL : corriger_donnees_maisons(data)
# Objectif : Harmonise/fiabilise la clé "maison" pour chaque planète.
# Détails :
#   - Convertit "maison" au type int si elle arrive en str ("10") ou float (10.0).
#   - Si l’Ascendant n’a pas de "maison", force 1 (convention).
#   - Ne touche qu’aux items de data['planetes'] qui sont des dicts.
# À quel moment l’appeler :
#   - Juste après calcul_theme(...) et avant toute logique d’analyse
#     (détection angulaires, amas, etc.) afin d’éviter les bugs de typage.
# Effets de bord :
#   - Modifie le dict data en place (retourne également data par commodité).
# ────────────────────────────────────────────────

def corriger_donnees_maisons(data: dict) -> dict:
    """Corrige les problèmes de typage dans les numéros de maisons"""
    planetes = data.get('planetes', {})

    for nom_planete, info_planete in planetes.items():
        if isinstance(info_planete, dict):
            maison = info_planete.get('maison')

            if isinstance(maison, str) and maison.isdigit():
                info_planete['maison'] = int(maison)
            elif isinstance(maison, float):
                info_planete['maison'] = int(maison)
            elif maison is None and nom_planete == 'Ascendant':
                info_planete['maison'] = 1

    return data

# ────────────────────────────────────────────────
# UTIL : valider_donnees_avant_analyse(data) -> (ok: bool, erreurs: list)
# Objectif : Contrôle de cohérence avant de lancer une analyse longue/LLM.
# Vérifie :
#   - Présence et structure des planètes clés : Ascendant, Soleil, Lune.
#   - Pour ces 3 : existence d’un "signe" et d’une "maison".
#   - Présence d’au moins un aspect dans data['aspects'].
#   - Nombre de maisons effectivement occupées (>= 8 recommandé).
# Usage recommandé :
#   - Appelée dans les routes d’analyse (ex : /analyse_point_astral)
#     pour bloquer proprement si les données sont incomplètes.
# Remarques :
#   - Retourne (True, []) si tout est OK, sinon (False, [liste d’erreurs]).
#   - Si tu veux autoriser des thèmes “pauvres” en aspects, adoucis la règle
#     “Aucun aspect calculé” selon ton besoin.
# ────────────────────────────────────────────────

def valider_donnees_avant_analyse(data: dict) -> tuple[bool, list]:
    """Valide les données avant l'analyse et retourne les erreurs"""
    erreurs = []

    planetes = data.get('planetes', {})
    planetes_requises = ['Ascendant', 'Soleil', 'Lune']

    for planete in planetes_requises:
        info = planetes.get(planete)
        if not isinstance(info, dict):
            erreurs.append(f"{planete}: données absentes ou malformées")
        else:
            if not info.get('signe'):
                erreurs.append(f"{planete}: signe manquant")
            if info.get('maison') is None:
                erreurs.append(f"{planete}: maison manquante")

    aspects = data.get('aspects', [])
    if not aspects:
        erreurs.append("Aucun aspect calculé")

    maisons_trouvees = {info['maison'] for info in planetes.values()
                        if isinstance(info, dict) and info.get('maison')}

    if len(maisons_trouvees) < 8:
        erreurs.append(f"Seulement {len(maisons_trouvees)} maisons occupées détectées")

    return len(erreurs) == 0, erreurs