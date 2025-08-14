from utils.formatage import (
    ASPECTS_MAJEURS, ASPECTS_MINEURS,
    formater_positions_planetes,
    formater_aspects,
    formater_aspects_significatifs,
    formater_resume_complet,
)

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_positions_planetes(planetes)
# Rôle :
#   - Transforme le dict des planètes (nom → {signe, degre, maison})
#     en un bloc texte lisible, une ligne par planète.
# Entrée :
#   - planetes (dict) : ex. {"Soleil": {"signe":"Lion","degre":12.3,"maison":5}, ...}
# Sortie :
#   - str : lignes type "Soleil : Lion 12.3° (Maison 5)" séparées par "\n".
# Remarques :
#   - Valeurs par défaut si clé absente : signe="inconnu", degre="n/a", maison="n/a".
#   - Doublon fonctionnel possible avec utils.utils_formatage.formater_positions_planetes :
#     garde celle-ci pour l’analyse gratuite si c’est celle qui est importée ici.
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
# Rôle :
#   - Convertit la liste d’aspects (planete1/planete2/aspect/orbe)
#     en un bloc texte lisible, une ligne par aspect.
# Entrée :
#   - aspects (list[dict]) : ex. [{"planete1":"Soleil","planete2":"Lune",
#                                  "aspect":"Conjonction","orbe":2.1}, ...]
# Sortie :
#   - str : lignes type "Soleil Conjonction Lune (orbe 2.1°)" séparées par "\n".
# Remarques :
#   - Valeurs par défaut si clé absente : "?" pour planètes/aspect, "?" pour orbe.
#   - Chevauchement possible avec utils.utils_formatage.formater_aspects :
#     utilises-en une seule dans le flux pour éviter la confusion.
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
# LOGIQUE : analyse_gratuite(planetes, aspects, lune_vedique)
# Rôle :
#   - Produit une courte liste de “points marquants” pour l’analyse gratuite :
#       • Conjonctions serrées (< = 5°) impliquant Ascendant / Soleil / Lune
#       • Présence de ces trois luminaires en maisons angulaires (1, 4, 7, 10)
#       • Rappel du nakshatra de la Lune (si fourni côté védique)
# Entrées :
#   - planetes (dict) : placements occidentaux (inclut "Ascendant", "Soleil", "Lune")
#   - aspects  (list[dict]) : aspects calculés (planete1, planete2, aspect, orbe)
#   - lune_vedique (dict|None) : ex. {"nakshatra":"Rohini", ...}
# Sortie :
#   - list[str] : phrases prêtes à afficher/envoyer par mail dans l’offre gratuite
# Paramètres importants :
#   - seuil_orbe = 5.0 : seuil pour considérer une conjonction “serrée”
# Remarques :
#   - Si rien n’est détecté, renvoie un message par défaut indiquant l’absence
#     d’aspect marquant pour la trinité Asc/Soleil/Lune.
#   - Fonction utilisée dans la route d’analyse gratuite pour générer le résumé.
# ─────────────────────────────────────────────────────────────────────────────

def analyse_gratuite(planetes, aspects, lune_vedique):
    resultats = []
    ascendant = planetes.get('Ascendant')
    soleil = planetes.get('Soleil')
    lune = planetes.get('Lune')

    luminaires = {'Ascendant': ascendant, 'Soleil': soleil, 'Lune': lune}
    seuil_orbe = 5.0

    for lum_name, lum_info in luminaires.items():
        if not lum_info:
            continue
        deg_lum = lum_info.get('degre')
        for asp in aspects:
            if asp['aspect'].lower() == 'conjonction' and lum_name in [asp['planete1'], asp['planete2']]:
                autre_planete = asp['planete2'] if asp['planete1'] == lum_name else asp['planete1']
                orbe = asp.get('orbe', 0)
                if orbe <= seuil_orbe:
                    resultats.append(f"{lum_name} est en conjonction serrée avec {autre_planete} (orbe {orbe}°)")

    maisons_angulaires = [1, 4, 7, 10]
    for nomp, infos in planetes.items():
        maison = infos.get('maison')
        if maison in maisons_angulaires and nomp in ['Ascendant', 'Soleil', 'Lune']:
            resultats.append(f"{nomp} en maison angulaire ({maison})")

    nakshatra = lune_vedique.get('nakshatra') if lune_vedique else None
    if nakshatra:
        resultats.append(f"La Lune védique est en Nakshatra {nakshatra}, apportant une coloration karmique ou spirituelle.")

    if not resultats:
        resultats.append("Analyse gratuite : aucun aspect marquant détecté sur la trinité Ascendant/Soleil/Lune.")

    return resultats