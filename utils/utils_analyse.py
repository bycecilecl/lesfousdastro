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