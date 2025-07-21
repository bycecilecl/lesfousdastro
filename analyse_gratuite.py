

def formater_positions_planetes(planetes):
    lignes = []
    for nom, infos in planetes.items():
        signe = infos.get('signe', 'inconnu')
        degre = infos.get('degre', 'n/a')
        maison = infos.get('maison', 'n/a')
        lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
    return "\n".join(lignes)

def formater_aspects(aspects):
    lignes = []
    for asp in aspects:
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        type_asp = asp.get('aspect', '?')
        orbe = asp.get('orbe', '?')
        lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes)

def analyse_gratuite(planetes, aspects, lune_vedique):
    """
    Analyse synthétique et ciblée sur Ascendant, Soleil, Lune (luminaires)
    + Lune védique (Nakshatra) pour moduler l'analyse.

    Arguments :
    - planetes : dict, données planétaires tropicales avec clés planètes et infos (dont 'degre')
    - aspects : liste de dicts, chaque dict décrit un aspect entre deux planètes
    - lune_vedique : dict, infos sur la Lune sidérale, notamment le nakshatra

    Retour :
    - list[str], liste d'observations simples à afficher ou envoyer par mail
    """

    resultats = []

    # Récupérer les luminaires et Ascendant
    ascendant = planetes.get('Ascendant')
    soleil = planetes.get('Soleil')
    lune = planetes.get('Lune')

    luminaires = {'Ascendant': ascendant, 'Soleil': soleil, 'Lune': lune}

    # Analyse des conjonctions luminaires / Ascendant
    seuil_orbe = 5.0
    for lum_name, lum_info in luminaires.items():
        if not lum_info:
            continue
        deg_lum = lum_info.get('degre')
        for asp in aspects:
            # Vérifier si aspect est conjonction et implique le luminaire
            if asp['aspect'].lower() == 'conjonction' and lum_name in [asp['planete1'], asp['planete2']]:
                autre_planete = asp['planete2'] if asp['planete1'] == lum_name else asp['planete1']
                orbe = asp.get('orbe', 0)
                if orbe <= seuil_orbe:
                    resultats.append(f"{lum_name} est en conjonction serrée avec {autre_planete} (orbe {orbe}°)")

    # Analyse simple des positions en maison angulaire (1,4,7,10)
    maisons_angulaires = [1, 4, 7, 10]
    for nomp, infos in planetes.items():
        maison = infos.get('maison')
        if maison in maisons_angulaires and nomp in ['Ascendant', 'Soleil', 'Lune']:
            resultats.append(f"{nomp} en maison angulaire ({maison})")

    # Analyse du Nakshatra de la Lune védique
    nakshatra = lune_vedique.get('nakshatra') if lune_vedique else None
    if nakshatra:
        resultats.append(f"La Lune védique est en Nakshatra {nakshatra}, apportant une coloration karmique ou spirituelle.")

    # Si aucun point trouvé
    if not resultats:
        resultats.append("Analyse gratuite : aucun aspect marquant détecté sur la trinité Ascendant/Soleil/Lune.")

    return resultats


#Construction URL avec paramètres pour /placements
#params = {
#    'nom': data['nom'],
#    'date_naissance': request.form['date_naissance'],
#    'heure_naissance': request.form['heure_naissance'],
#    'lieu_naissance': request.form['lieu_naissance']
#}
#url_placements = '/placements?' + urlencode(params)
