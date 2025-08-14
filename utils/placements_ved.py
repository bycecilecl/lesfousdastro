# utils/placements_ved.py

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : build_resume_vedique(data)
# Rôle : Génère un résumé textuel de l’astrologie védique à partir des données
#        brutes calculées par calcul_theme().
#        Ce bloc est ensuite fusionné avec la partie occidentale.
# Entrées :
#   - data (dict) : données astrologiques (Ascendant sidéral, maître, maisons,
#                   planètes védiques avec nakshatras…)
# Dépendances :
#   - ORDRE_PLANETES_VED (ordre d’affichage des planètes)
# Sortie :
#   - str : bloc texte structuré avec :
#       1) Ascendant sidéral (+ nakshatra si dispo)
#       2) Maître de l’Ascendant (sidéral)
#       3) Maisons astrologiques védiques (1..12)
#       4) Positions planétaires védiques (+ nakshatra)
#       5) Nakshatra lunaire clé (rappel explicite)
# Où c’est utilisé :
#   - build_resume_fusion() → pour produire le résumé occidental + védique
# Remarques :
#   - Les nakshatras sont inclus quand disponibles pour donner plus de contexte.
#   - Les données proviennent de la clé `planetes_vediques` et `maisons_vediques`
#     générées par calcul_theme().
# ─────────────────────────────────────────────────────────────────────────────

from typing import Dict, Any, List

ORDRE_PLANETES_VED = [
    "Ascendant","Soleil","Lune","Mercure","Vénus","Mars","Jupiter","Saturne",
    "Uranus","Neptune","Pluton","Rahu","Ketu"
]

def build_resume_vedique(data: Dict[str, Any]) -> str:
    """
    Construit le bloc 'Védique' à partir de data (retour de calcul_theme).

    Sections :
    - Ascendant sidéral (avec nakshatra si dispo)
    - Maître de l’Ascendant (sidéral)
    - Maisons védiques (1..12)
    - Positions planétaires védiques (avec nakshatra)
    - Nakshatra lunaire (rappel)
    """
    asc_sid = data.get("ascendant_sidereal", {}) or {}
    maitre_ved = data.get("maitre_ascendant_vedique", {}) or {}
    maisons_v = data.get("maisons_vediques", {}) or {}
    plan_v = data.get("planetes_vediques", {}) or {}

    # 1) Ascendant sidéral
    asc_deg = asc_sid.get("degre", "?")
    asc_signe = asc_sid.get("signe", "?")
    asc_nak = asc_sid.get("nakshatra")
    bloc_asc = "Ascendant sidéral\n"
    bloc_asc += f"{asc_deg}° en {asc_signe}"
    if asc_nak:
        bloc_asc += f", nakshatra : {asc_nak}"

    # 2) Maître de l’Ascendant (sidéral)
    if maitre_ved:
        bloc_maitre = (
            "Maître de l’Ascendant (sidéral)\n"
            f"{maitre_ved.get('nom','?')} à {maitre_ved.get('degre','?')}° "
            f"en {maitre_ved.get('signe','?')} (Maison {maitre_ved.get('maison','?')})"
        )
        if maitre_ved.get("nakshatra"):
            bloc_maitre += f" – Nakshatra : {maitre_ved.get('nakshatra')}"
    else:
        bloc_maitre = "Maître de l’Ascendant (sidéral)\n—"

    # 3) Maisons védiques (1..12)
    lignes_maisons_v = []
    for i in range(1, 13):
        m = maisons_v.get(f"Maison {i}", {}) or {}
        deg = m.get("degre", "0.0")
        signe = m.get("signe", "?")
        lignes_maisons_v.append(f"Maison {i} : {deg}° en {signe}")
    bloc_maisons_v = "Maisons astrologiques védiques\n" + "\n".join(lignes_maisons_v)

    # 4) Positions planétaires védiques (avec nakshatra)
    lignes_pos_v = []
    for nom in ORDRE_PLANETES_VED:
        p = plan_v.get(nom)
        if not p:
            continue
        deg = p.get("degre", "?")
        signe = p.get("signe", "?")
        maison = p.get("maison", "—")
        nak = p.get("nakshatra")
        if nom == "Ascendant":
            ligne = f"Ascendant : {deg}° en {signe} – Maison"
            if nak:
                ligne += f" – Nakshatra : {nak}"
        else:
            ligne = f"{nom} : {deg}° en {signe} – Maison {maison}"
            if nak:
                ligne += f" – Nakshatra : {nak}"
        lignes_pos_v.append(ligne)
    bloc_pos_v = "Positions planétaires védiques\n" + "\n".join(lignes_pos_v)

    # 5) Nakshatra de la Lune (rappel explicite)
    lune_v = plan_v.get("Lune", {}) or {}
    nak_lune = lune_v.get("nakshatra")
    bloc_nak_lune = "Nakshatra lunaire clé\n" + (nak_lune if nak_lune else "—")

    # Assemblage final
    sections = [bloc_asc, bloc_maitre, bloc_maisons_v, bloc_pos_v, bloc_nak_lune]
    return "\n\n".join(sections)