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

def detecter_aspects_luminaire(planetes, aspects):
    points = []
    luminaires = ['Soleil', 'Lune']
    lourdes = ['Saturne', 'Pluton', 'Jupiter', 'Mars']
    aspects_interessants = ['conjonction', 'carré', 'opposition']

    for asp in aspects:
        p1, p2 = asp.get('planete1'), asp.get('planete2')
        type_asp = asp.get('aspect', '').lower()
        if type_asp in aspects_interessants:
            if (p1 in luminaires and p2 in lourdes) or (p2 in luminaires and p1 in lourdes):
                points.append(f"Luminaire ({p1 if p1 in luminaires else p2}) en {type_asp} avec planète lourde ({p2 if p2 in lourdes else p1})")
    return points

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
    points += detecter_aspects_luminaire(planetes, aspects)
    points += detecter_conjonction_angles(
        {k: v['degre'] for k, v in planetes.items() if 'degre' in v},
        angles_degres
    )

    return points