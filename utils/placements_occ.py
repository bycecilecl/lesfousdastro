# utils/placements_occ.py

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : build_resume_occidental(data, orbe_max=6.0, max_aspects=999)
# Rôle : Génère un résumé textuel de l’astrologie occidentale à partir des
#        données brutes calculées par calcul_theme().
#        Ce bloc est ensuite fusionné avec la partie védique.
# Entrées :
#   - data (dict)      : données astrologiques (planètes, maisons, aspects…)
#   - orbe_max (float) : filtre, garde uniquement les aspects ≤ orbe_max
#   - max_aspects (int): limite du nombre d’aspects à afficher (999 = pas de limite)
# Dépendances :
#   - ORDRE_PLANETES_OCC (ordre d’affichage des planètes)
#   - _normalize_aspects() (nettoie et normalise les aspects)
# Sortie :
#   - str : bloc texte structuré avec :
#       1) Positions planétaires (occidentales)
#       2) Maisons astrologiques tropicales
#       3) Aspects filtrés par orbe et triés par ordre croissant
#       4) Liste brute des points forts (si présente dans `data`)
# Où c’est utilisé :
#   - build_resume_fusion() → pour produire le résumé occidental + védique
# Remarques :
#   - Les aspects sont triés par orbe croissant après filtrage.
#   - Les points forts peuvent être une liste ou un dict → conversion en liste.
# ─────────────────────────────────────────────────────────────────────────────
from typing import Dict, Any, List

ORDRE_PLANETES_OCC = [
    "Ascendant","Soleil","Lune","Mercure","Vénus","Mars","Jupiter","Saturne",
    "Uranus","Neptune","Pluton","Rahu","Ketu","Lune Noire","Chiron"
]


# def _normalize_aspects(aspects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """
#     Normalise les aspects au format : source / cible / type / orbe (float)
#     Accepte aussi : planete1 / planete2 / aspect / orbe (string/float)
#     """
#     out = []
#     for a in aspects or []:
#         src = a.get("source") or a.get("planete1")
#         dst = a.get("cible") or a.get("planete2")
#         typ = a.get("type") or a.get("aspect")
#         orbe_raw = a.get("orbe")
#         try:
#             orbe = float(orbe_raw) if orbe_raw is not None else 999.0
#         except Exception:
#             orbe = 999.0
#         if src and dst and typ:
#             out.append({"source": src, "cible": dst, "type": typ, "orbe": orbe})
#     return out




def _normalize_aspects(aspects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalise les aspects au format : source / cible / type / orbe (float)
    Accepte aussi : planete1 / planete2 / aspect / orbe (string/float)
    """
    out = []
    for a in aspects or []:
        src = a.get("source") or a.get("planete1")
        dst = a.get("cible") or a.get("planete2")
        typ = a.get("type") or a.get("aspect")
        orbe_raw = a.get("orbe")
        try:
            orbe = float(orbe_raw) if orbe_raw is not None else 999.0
        except Exception:
            orbe = 999.0
        if src and dst and typ:
            out.append({"source": src, "cible": dst, "type": typ, "orbe": orbe})
    return out


def _filtrer_aspects_intelligemment(aspects: List[Dict[str, Any]], max_aspects: int = 12) -> List[Dict[str, Any]]:
    """
    🎯 NOUVEAU : Filtre les aspects de manière intelligente pour le LLM
    
    Priorités :
    1. Aspects majeurs (conjonction, opposition, carré, trigone, sextile)
    2. Orbe serré (< 3°)
    3. Implique Soleil, Lune, Ascendant
    4. Limite au nombre max_aspects
    """
    
    # Planètes prioritaires
    planetes_importantes = ['Soleil', 'Lune', 'Ascendant', 'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne']
    planetes_critiques = ['Soleil', 'Lune', 'Ascendant']
    
    # Aspects majeurs
    aspects_majeurs = ['conjonction', 'opposition', 'carré', 'trigone', 'sextile']
    
    aspects_avec_score = []
    
    for aspect in aspects:
        source = aspect.get('source', '')
        cible = aspect.get('cible', '')
        type_aspect = aspect.get('type', '').lower()
        orbe = aspect.get('orbe', 10)
        
        # Calcul du score de priorité
        score = 0
        
        # ✅ Bonus pour aspects majeurs
        if any(maj in type_aspect for maj in aspects_majeurs):
            score += 10
        
        # ✅ Bonus pour orbe serré
        if orbe <= 1:
            score += 8
        elif orbe <= 2:
            score += 5
        elif orbe <= 3:
            score += 3
        elif orbe <= 4:
            score += 1
        
        # ✅ Bonus pour planètes importantes
        if source in planetes_importantes:
            score += 3
        if cible in planetes_importantes:
            score += 3
            
        # ✅ Super bonus pour Soleil, Lune, Ascendant
        if source in planetes_critiques:
            score += 7
        if cible in planetes_critiques:
            score += 7
        
        # ✅ Bonus pour aspects de tension (plus révélateurs)
        if 'carré' in type_aspect or 'opposition' in type_aspect:
            score += 2
        
        # ❌ Malus pour aspects mineurs
        if any(mineur in type_aspect for mineur in ['quinconce', 'semi-sextile', 'semi-carré']):
            score -= 5
        
        # ❌ Malus pour planètes lentes ensemble (moins personnel)
        planetes_lentes = ['Uranus', 'Neptune', 'Pluton']
        if source in planetes_lentes and cible in planetes_lentes:
            score -= 4
        
        aspect['score_priorite'] = score
        aspects_avec_score.append(aspect)
    
    # Trier par score décroissant puis par orbe croissant
    aspects_avec_score.sort(key=lambda x: (-x['score_priorite'], x['orbe']))
    
    # Garder seulement les meilleurs
    aspects_finaux = aspects_avec_score[:max_aspects]
    
    print(f"🎯 Aspects filtrés intelligemment : {len(aspects)} → {len(aspects_finaux)} (gardés les {max_aspects} plus importants)")
    
    return aspects_finaux


def build_resume_occidental(
    data: Dict[str, Any],
    orbe_max: float = 6.0,
    max_aspects: int = 12  # 🆕 Réduit de 999 à 12 par défaut
) -> str:
    """
    Construit le bloc 'Occidental' à partir de data (retour de calcul_theme).
    VERSION OPTIMISÉE avec filtrage intelligent des aspects.

    Sections retournées (texte prêt à injecter) :
    - Positions planétaires (occidentales)
    - Maisons astrologiques tropicales
    - Aspects astrologiques (FILTRÉS INTELLIGEMMENT 🎯)
    - Résumé des points forts
    """
    planetes = data.get("planetes", {}) or {}
    maisons = data.get("maisons", {}) or {}
    aspects = _normalize_aspects(data.get("aspects", []))
    points_forts = data.get("points_forts") or []

    # 1) Positions planétaires (occidentales) - INCHANGÉ
    lignes_pos = []
    for nom in ORDRE_PLANETES_OCC:
        p = planetes.get(nom)
        if not p:
            continue
        deg = p.get("degre", "?")
        signe = p.get("signe", "?")
        maison = p.get("maison", "—")
        if nom == "Ascendant":
            lignes_pos.append(f"Ascendant : {deg}° en {signe} – Maison")
        else:
            lignes_pos.append(f"{nom} : {deg}° en {signe} – Maison {maison}")
    bloc_pos = "Positions planétaires (occidentales)\n" + "\n".join(lignes_pos)

    # 2) Maisons astrologiques tropicales - INCHANGÉ
    lignes_maisons = []
    for i in range(1, 13):
        m = maisons.get(f"Maison {i}", {}) or {}
        deg = m.get("degre", "0.0")
        signe = m.get("signe", "?")
        lignes_maisons.append(f"Maison {i} : {deg}° en {signe}")
    bloc_maisons = "Maisons astrologiques tropicales\n" + "\n".join(lignes_maisons)

    # 🎯 3) Aspects astrologiques - NOUVELLE LOGIQUE INTELLIGENTE
    print(f"🔍 Filtrage aspects : {len(aspects)} aspects bruts")
    
    # D'abord filtrer par orbe max (garde les aspects pas trop larges)
    aspects_orbe_ok = [a for a in aspects if a["orbe"] <= orbe_max]
    print(f"🔍 Après filtre orbe ≤ {orbe_max}° : {len(aspects_orbe_ok)} aspects")
    
    # Puis filtrage intelligent par priorité
    aspects_filtrés = _filtrer_aspects_intelligemment(aspects_orbe_ok, max_aspects)
    print(f"🔍 Après filtre intelligent : {len(aspects_filtrés)} aspects gardés")

    # Formatage final (groupé par type pour plus de clarté)
    if aspects_filtrés:
        lignes_aspects = []
        
        # Grouper par type d'aspect
        aspects_par_type = {}
        for a in aspects_filtrés:
            type_asp = a['type']
            if type_asp not in aspects_par_type:
                aspects_par_type[type_asp] = []
            aspects_par_type[type_asp].append(a)
        
        # Afficher par ordre d'importance
        ordre_types = ['conjonction', 'opposition', 'carré', 'trigone', 'sextile']
        
        for type_aspect in ordre_types:
            if type_aspect in aspects_par_type:
                lignes_aspects.append(f"\n--- {type_aspect.upper()} ---")
                for a in aspects_par_type[type_aspect]:
                    lignes_aspects.append(f"{a['source']}\t{a['type']}\t{a['cible']}\t{a['orbe']:.2f}°")
        
        # Autres aspects s'il y en a
        autres_types = [t for t in aspects_par_type.keys() if t not in ordre_types]
        if autres_types:
            lignes_aspects.append(f"\n--- AUTRES ASPECTS ---")
            for type_aspect in autres_types:
                for a in aspects_par_type[type_aspect]:
                    lignes_aspects.append(f"{a['source']}\t{a['type']}\t{a['cible']}\t{a['orbe']:.2f}°")
        
        entete = "Aspects astrologiques (sélection des plus significatifs)"
        bloc_aspects = entete + "\n" + "\n".join(lignes_aspects)
    else:
        bloc_aspects = "Aspects astrologiques\nAucun aspect significatif détecté."

    # 4) Résumé des points forts - INCHANGÉ
    if isinstance(points_forts, dict):
        pf_list = []
        for v in points_forts.values():
            if isinstance(v, list):
                pf_list += v
        points_forts = pf_list
    bloc_pf = "Résumé des points forts\n" + ("\n".join(points_forts) if points_forts else "—")

    # Assemblage final
    return f"{bloc_pos}\n\n{bloc_maisons}\n\n{bloc_aspects}\n\n{bloc_pf}"