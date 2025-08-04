

def est_angulaire(maison):
    return maison in [1, 4, 7, 10]

def detecter_angles_importants(planetes):
    points = []
    for nom, infos in planetes.items():
        maison = infos.get('maison')
        if maison and est_angulaire(maison):
            points.append(f"{nom} en maison angulaire ({maison})")
    return points

def detecter_amas(planetes, seuil=3):
    points = []
    signes_count = {}
    for nom, infos in planetes.items():
        signe = infos.get('signe')
        if signe:
            signes_count[signe] = signes_count.get(signe, []) + [nom]
    for signe, liste_planetes in signes_count.items():
        if len(liste_planetes) >= seuil:
            points.append(f"Amas planétaire en {signe} ({', '.join(liste_planetes)})")
    return points

def detecter_aspects_luminaire_detaille(aspects):
    luminaires = ['Soleil', 'Lune']
    priorite_map = {
        'conjonction': 0,
        'carré': 1,
        'opposition': 2,
        'trigone': 3,
        'sextile': 4
    }

    def priorite(asp):
        aspect_type = asp.get('aspect', '').lower()
        orbe = asp.get('orbe', 99)
        if aspect_type == "conjonction" and orbe <= 6:
            return 0
        return priorite_map.get(aspect_type, 5)

    filtres = [asp for asp in aspects if asp['planete1'] in luminaires or asp['planete2'] in luminaires]
    filtres_trie = sorted(filtres, key=priorite)

    resultats = []
    for asp in filtres_trie:
        p1 = asp['planete1']
        p2 = asp['planete2']
        asp_type = asp['aspect']
        orbe = asp.get('orbe', '?')
        resultats.append(f"{p1} {asp_type} {p2} (orbe {orbe}°)")

    return resultats

def detecter_conjonction_angles(positions, angles_degres, seuil_orbe=5):
    points = []
    for planete, deg_planete in positions.items():
        for angle_name, deg_angle in angles_degres.items():
            if planete.lower() == angle_name.lower():
                continue
            diff = abs((deg_planete - deg_angle + 180) % 360 - 180)
            if diff <= seuil_orbe:
                points.append(f"{planete} en conjonction avec l’angle {angle_name} (écart {round(diff,2)}°)")
    return points

def extraire_points_forts(data):
    points = []
    angles_degres = {
        'Ascendant': data.get('planetes', {}).get('Ascendant', {}).get('degre'),
        'Milieu du Ciel': data.get('maisons', {}).get('Maison 10', {}).get('degre'),
        'Descendant': data.get('maisons', {}).get('Maison 7', {}).get('degre'),
        'Fond du Ciel': data.get('maisons', {}).get('Maison 4', {}).get('degre')
    }
    angles_degres = {k: v for k, v in angles_degres.items() if v is not None}

    planetes = data.get('planetes', {})
    aspects = data.get('aspects', [])

    points += detecter_angles_importants(planetes)
    points += detecter_amas(planetes)
    points += detecter_aspects_luminaire_detaille(aspects)
    points += detecter_conjonction_angles(
        {k: v['degre'] for k, v in planetes.items() if 'degre' in v},
        angles_degres
    )

    return points