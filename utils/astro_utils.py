def corriger_donnees_maisons(data: dict) -> dict:
    """Corrige les problèmes de typage dans les numéros de maisons"""
    planetes = data.get('planetes', {})

    for nom_planete, info_planete in planetes.items():
        if isinstance(info_planete, dict):
            maison = info_planete.get('maison')

            if isinstance(maison, str) and maison.isdigit():
                info_planete['maison'] = int(maison)
            elif isinstance(maison, float):
                info_planete['maison'] = int(maison)
            elif maison is None and nom_planete == 'Ascendant':
                info_planete['maison'] = 1

    return data


def valider_donnees_avant_analyse(data: dict) -> tuple[bool, list]:
    """Valide les données avant l'analyse et retourne les erreurs"""
    erreurs = []

    planetes = data.get('planetes', {})
    planetes_requises = ['Ascendant', 'Soleil', 'Lune']

    for planete in planetes_requises:
        info = planetes.get(planete)
        if not isinstance(info, dict):
            erreurs.append(f"{planete}: données absentes ou malformées")
        else:
            if not info.get('signe'):
                erreurs.append(f"{planete}: signe manquant")
            if info.get('maison') is None:
                erreurs.append(f"{planete}: maison manquante")

    aspects = data.get('aspects', [])
    if not aspects:
        erreurs.append("Aucun aspect calculé")

    maisons_trouvees = {info['maison'] for info in planetes.values()
                        if isinstance(info, dict) and info.get('maison')}

    if len(maisons_trouvees) < 8:
        erreurs.append(f"Seulement {len(maisons_trouvees)} maisons occupées détectées")

    return len(erreurs) == 0, erreurs