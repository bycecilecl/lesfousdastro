# utils/placements_fusion.py

from typing import Dict, Any
from utils.placements_occ import build_resume_occidental
from utils.placements_ved import build_resume_vedique

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : build_resume_fusion(data, orbe_max=6.0)
# Rôle : Construit un résumé mixte astrologie occidentale + astrologie védique.
#        Sert à générer un bloc texte complet à partir des calculs bruts.
# Entrées :
#   - data (dict) : données astrologiques calculées (occidentales et védiques)
#   - orbe_max (float) : orbe maximum pour filtrer les aspects occidentaux
# Dépendances :
#   - utils.placements_occ.build_resume_occidental()
#   - utils.placements_ved.build_resume_vedique()
# Sortie :
#   - str : texte combiné contenant :
#       1) résumé occidental (avec aspects filtrés par orbe_max)
#       2) résumé védique (sans aspects)
#       3) nakshatra lunaire (si présent)
#       4) points forts occidentaux (si présents dans `data`)
# Où c’est utilisé :
#   - Génération du “résumé fusionné” affiché dans les analyses
#   - Debug / affichage interne des placements
# Remarques :
#   - Ignore les sections vides (ne concatène que celles qui existent).
# ─────────────────────────────────────────────────────────────────────────────

def build_resume_fusion(data: Dict[str, Any], orbe_max: float = 6.0) -> str:
    """
    Fusionne les résumés occidental et védique dans un seul bloc.
    - orbe_max : filtrage des aspects (côté occidental)
    - côté védique : pas d'aspects
    - ajoute (optionnel) un rappel du Nakshatra lunaire + points forts si dispos
    """
    # Occidental — on passe uniquement les kwargs supportés par ta fonction
    bloc_occ = build_resume_occidental(
        data,
        orbe_max=4.0,
        max_aspects=10
    )

    # Védique — signature simple
    bloc_ved = build_resume_vedique(data)

    # Rappel Nakshatra de la Lune (si présent)
    nak = (data.get("planetes_vediques", {}) or {}).get("Lune", {}) or {}
    nak_lune = nak.get("nakshatra")
    bloc_nak = f"Nakshatra lunaire : {nak_lune}" if nak_lune else ""

    # Points forts occidental (si listés dans data)
    points = data.get("points_forts") or []
    bloc_points = ""
    if points:
        bloc_points = "Résumé des points forts (Occidental)\n" + "\n".join(points)

    parts = [bloc_occ, bloc_ved, bloc_nak, bloc_points]
    return "\n\n".join(p for p in parts if p).strip()