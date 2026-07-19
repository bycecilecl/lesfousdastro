# ─────────────────────────────────────────────────────────────────────────────
# MODULE : utils/utils_formatage.py
# Rôle : Fonctions de formatage “texte” pour afficher les placements et aspects.
# Contexte : utilisé par l’analyse gratuite, le Point Astral et les résumés.
# Doublons connus :
#   - utils_analyse.py (formater_positions_planetes / formater_aspects)
#   - utils/format_utils.py (variantes proches)
# Recommandation :
#   → Centraliser ici et supprimer/archiver les doublons ailleurs.
# ─────────────────────────────────────────────────────────────────────────────

# utils/utils_formatage.py — passerelle vers utils/formatage.py
from utils.formatage import (
    ASPECTS_MAJEURS, ASPECTS_MINEURS,
    formater_positions_planetes,
    formater_aspects,
    formater_aspects_significatifs,
    formater_resume_complet,
)

__all__ = [
    "ASPECTS_MAJEURS", "ASPECTS_MINEURS",
    "formater_positions_planetes",
    "formater_aspects",
    "formater_aspects_significatifs",
    "formater_resume_complet",
]

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_positions_planetes(planetes)
# Rôle : transforme le dict de planètes en lignes lisibles "Nom : Signe X° (Maison N)".
# Entrée :
#   - planetes (dict) : {"Soleil": {"signe": "...", "degre": 12.3, "maison": 5}, ...}
# Sortie :
#   - str multi‑ligne prêt à afficher (une ligne par planète)
# Tolérance :
#   - valeurs manquantes → "inconnu" / "n/a"
# ─────────────────────────────────────────────────────────────────────────────

def formater_positions_planetes(planetes):
    lignes = []
    for nom, infos in planetes.items():
        signe = infos.get('signe', 'inconnu')
        degre = infos.get('degre', 'n/a')
        maison = infos.get('maison', 'n/a')
        lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
    return "\n".join(lignes)

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_aspects(aspects)
# Rôle : formate tous les aspects au format "P1 Aspect P2 (orbe X°)".
# Entrée :
#   - aspects (list[dict]) : [{'planete1','planete2','aspect','orbe'}, ...]
# Sortie :
#   - str multi‑ligne listant tous les aspects (sans filtrage d’orbe)
# ─────────────────────────────────────────────────────────────────────────────

def formater_aspects(aspects):
    lignes = []
    for asp in aspects:
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        type_asp = asp.get('aspect', '?')
        orbe = asp.get('orbe', '?')
        lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes)

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_aspects_significatifs(aspects, seuil_orbe=5.0)
# Rôle : idem formater_aspects mais NE GARDE que les aspects avec orbe ≤ seuil.
# Entrées :
#   - aspects (list[dict]) : mêmes clés que ci‑dessus
#   - seuil_orbe (float)   : filtre (par défaut 5°)
# Sortie :
#   - str multi‑ligne filtré, ou message “Aucun aspect significatif …”
# ─────────────────────────────────────────────────────────────────────────────

def formater_aspects_significatifs(aspects, seuil_orbe=5.0):
    lignes = []
    for asp in aspects:
        orbe = asp.get('orbe')
        if orbe is not None and orbe <= seuil_orbe:
            p1 = asp.get('planete1', '?')
            p2 = asp.get('planete2', '?')
            type_asp = asp.get('aspect', '?')
            lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes) if lignes else "Aucun aspect significatif (orbe ≤ 5°)."

# ✅ Exemples de test → protéger avec if __name__ == "__main__"
if __name__ == "__main__":
    aspects_exemple = [
        {'planete1': 'Lune', 'planete2': 'Uranus', 'aspect': 'opposition', 'orbe': 6.2},
        {'planete1': 'Soleil', 'planete2': 'Pluton', 'aspect': 'conjonction', 'orbe': 2.5},
        {'planete1': 'Mars', 'planete2': 'Neptune', 'aspect': 'carré', 'orbe': 5.0},
        {'planete1': 'Vénus', 'planete2': 'Saturne', 'aspect': 'sextile', 'orbe': 1.8}
    ]
    print(formater_aspects_significatifs(aspects_exemple))