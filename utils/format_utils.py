
# (ex: format_utils.py)
from utils.utils_formatage import (
    ASPECTS_MAJEURS, ASPECTS_MINEURS,
    formater_positions_planetes, formater_aspects,
    formater_aspects_significatifs, formater_resume_complet,
)

__all__ = [
    "ASPECTS_MAJEURS", "ASPECTS_MINEURS",
    "formater_positions_planetes", "formater_aspects",
    "formater_aspects_significatifs", "formater_resume_complet",
]

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_positions_planetes(planetes)
# Rôle :
#   Transforme le dictionnaire des planètes en un bloc texte lisible (une ligne
#   par planète) du type : "Soleil : Lion 12.34° — Maison 5".
# Entrée :
#   - planetes (dict) : { "Soleil": {"signe": str, "degre_dans_signe": float,
#                                    "maison": int|str, ...}, ... }
# Sortie :
#   - str : lignes jointes par "\n", prêtes à injecter dans un prompt/email/template.
# Où c’est utilisé :
#   - Analyse gratuite : pour construire le résumé des positions envoyé au LLM.
#   - Routes de rendu (ex. /test_placements) pour affichage rapide.
# Remarques :
#   - Sécurise les clés manquantes avec valeurs par défaut (signe="inconnu",
#     degre=0.0, maison="N/A"), et arrondit le degré à 2 décimales.
# ─────────────────────────────────────────────────────────────────────────────

def formater_positions_planetes(planetes):
    lignes = []
    for planete, infos in planetes.items():
        signe = infos.get("signe", "inconnu")
        degre = round(infos.get("degre_dans_signe", 0.0), 2)
        maison = infos.get("maison", "N/A")
        lignes.append(f"{planete} : {signe} {degre}° — Maison {maison}")
    return "\n".join(lignes)

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_aspects(aspects)
# Rôle :
#   Convertit la liste d’aspects en lignes lisibles du type :
#   "Soleil Trigone Lune (orbe : 1.25°)".
# Entrée :
#   - aspects (list[dict]) : items avec clés "planete1", "planete2",
#                            "aspect" (label), "orbe" (float).
# Sortie :
#   - str : lignes jointes par "\n", prêtes pour prompt/email/template.
# Où c’est utilisé :
#   - Analyse gratuite : bloc “Aspects astrologiques” passé au LLM.
#   - Pages de test/diagnostic (ex. /test_placements).
# Remarques :
#   - Arrondit l’orbe à 2 décimales ; suppose que les clés existent
#     (si les données peuvent être partielles, envisager .get() + défauts).
# ─────────────────────────────────────────────────────────────────────────────


def formater_aspects(aspects):
    lignes = []
    for aspect in aspects:
        p1 = aspect["planete1"]
        p2 = aspect["planete2"]
        nom_aspect = aspect["aspect"]
        orbe = round(aspect["orbe"], 2)
        lignes.append(f"{p1} {nom_aspect} {p2} (orbe : {orbe}°)")
    return "\n".join(lignes)