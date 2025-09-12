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

def build_resume_occidental(
    data: Dict[str, Any],
    orbe_max: float = 6.0,
    max_aspects: int = 999
) -> str:
    """
    Construit le bloc 'Occidental' à partir de data (retour de calcul_theme).

    Sections retournées (texte prêt à injecter) :
    - Positions planétaires (occidentales)
    - Maisons astrologiques tropicales
    - Aspects astrologiques (tabulé)
    - Résumé des points forts
    """
    planetes = data.get("planetes", {}) or {}
    maisons = data.get("maisons", {}) or {}
    aspects = _normalize_aspects(data.get("aspects", []))
    points_forts = data.get("points_forts") or []

    # 1) Positions planétaires (occidentales)
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

    # 2) Maisons astrologiques tropicales (1..12)
    lignes_maisons = []
    for i in range(1, 13):
        m = maisons.get(f"Maison {i}", {}) or {}
        deg = m.get("degre", "0.0")
        signe = m.get("signe", "?")
        lignes_maisons.append(f"Maison {i} : {deg}° en {signe}")
    bloc_maisons = "Maisons astrologiques tropicales\n" + "\n".join(lignes_maisons)

    # 3) Aspects astrologiques — triés par orbe croissant + filtre orbe_max
    aspects_filtrés = [a for a in aspects if a["orbe"] <= orbe_max]
    aspects_filtrés.sort(key=lambda x: x["orbe"])
    if max_aspects is not None:
        aspects_filtrés = aspects_filtrés[:max_aspects]

    lignes_aspects = [
        f"{a['source']}\t{a['type']}\t{a['cible']}\t{a['orbe']:.2f}"
        for a in aspects_filtrés
    ]
    entete = "Planète 1\tAspect\tPlanète 2\tOrbe (°)"
    bloc_aspects = "Aspects astrologiques\n" + entete + "\n" + "\n".join(lignes_aspects)

    # 4) Résumé des points forts (liste brute telle que fournie)
    if isinstance(points_forts, dict):
        pf_list = []
        for v in points_forts.values():
            if isinstance(v, list):
                pf_list += v
        points_forts = pf_list
    bloc_pf = "Résumé des points forts\n" + ("\n".join(points_forts) if points_forts else "—")

    # Assemblage final
    return f"{bloc_pos}\n\n{bloc_maisons}\n\n{bloc_aspects}\n\n{bloc_pf}"