def est_angulaire(maison):
    """Retourne True si la maison est angulaire (1,4,7,10)."""
    return maison in [1, 4, 7, 10]

def detecter_angles_importants(planetes):
    """Détecte les planètes en maison angulaire."""
    points = []
    for nom, infos in planetes.items():
        maison = infos.get('maison')
        if maison and est_angulaire(maison):
            points.append(f"{nom} en maison angulaire ({maison})")
    return points

def detecter_amas(planetes, seuil=3):
    """Détecte les amas planétaires dans un même signe dépassant le seuil."""
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
    """
    Repère les aspects marquants entre luminaires (Soleil, Lune)
    et planètes lourdes (Saturne, Pluton, Jupiter, Mars) en conjonction, carré ou opposition.
    """
    points = []
    luminaires = ['Soleil', 'Lune']
    lourdes = ['Saturne', 'Pluton', 'Jupiter', 'Mars']
    aspects_interessants = ['conjonction', 'carré', 'opposition']
    
    for asp in aspects:
        p1, p2 = asp['planete1'], asp['planete2']
        aspect_type = asp['aspect'].lower()
        if aspect_type in aspects_interessants:
            if (p1 in luminaires and p2 in lourdes) or (p2 in luminaires and p1 in lourdes):
                points.append(f"Luminaire ({p1 if p1 in luminaires else p2}) en {aspect_type} avec planète lourde ({p2 if p2 in lourdes else p1})")
    return points

def detecter_conjonction_angles(positions, angles_degres, seuil_orbe=5):
    """
    Détecte les planètes en conjonction avec les angles importants (AS, MC, DC, FC)
    même si elles ne sont pas en maison angulaire.
    """
    points = []
    for planete, deg_planete in positions.items():
        for angle_name, deg_angle in angles_degres.items():
            # Ne pas comparer si la planète est le même angle
            if planete.lower() == angle_name.lower():
                continue
            diff = abs((deg_planete - deg_angle + 180) % 360 - 180)  # Différence angulaire la plus courte
            if diff <= seuil_orbe:
                points.append(f"{planete} en conjonction avec l’angle {angle_name} (écart {round(diff,2)}°)")
    return points

def extraire_points_forts(data):
    """
    Fonction principale d'extraction des points forts.
    Appelle les fonctions de détection des configurations importantes.
    """
    points = []

    # Calculer les angles importants (AS, MC, DC, FC) en degrés
    angles_degres = {
        'Ascendant': data.get('planetes', {}).get('Ascendant', {}).get('degre', None),
        'Milieu du Ciel': data.get('maisons', {}).get('Maison 10', {}).get('degre', None),
        'Descendant': data.get('maisons', {}).get('Maison 7', {}).get('degre', None),
        'Fond du Ciel': data.get('maisons', {}).get('Maison 4', {}).get('degre', None)
    }
    angles_degres = {k: v for k, v in angles_degres.items() if v is not None}

    # Appeler chaque détecteur et accumuler les résultats
    points += detecter_angles_importants(data['planetes'])
    points += detecter_amas(data['planetes'])
    points += detecter_aspects_luminaire(data['planetes'], data.get('aspects', []))
    points += detecter_conjonction_angles(
        {k: v['degre'] for k, v in data['planetes'].items() if 'degre' in v},
        angles_degres
    )

    return points