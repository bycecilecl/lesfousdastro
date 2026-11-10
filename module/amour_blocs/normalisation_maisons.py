"""Format local commun : clés Maison N, maisons planétaires entières de 1 à 12."""
import re


def numero_maison(valeur):
    if valeur is None:
        return None
    match = re.fullmatch(r"(?:maison[\s_]+)?(0?[1-9]|1[0-2])(?:\.0+)?", str(valeur).strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"Maison invalide : {valeur!r} ; numéro de 1 à 12 attendu.")
    return int(match.group(1))


def normaliser_maisons_theme(theme):
    """Copie les données utiles sans modifier le thème ni sa doctrine de maîtrises."""
    copie = dict(theme)
    maisons = {}
    for cle, infos in (theme.get('maisons') or theme.get('maisons_tropicales') or {}).items():
        numero = numero_maison(cle)
        if numero is None:
            raise ValueError('Numéro de maison absent dans les cuspides.')
        label = f'Maison {numero}'
        data = dict(infos or {})
        if not data.get('signe') and data.get('cuspide_signe'):
            data['signe'] = data['cuspide_signe']
        if label in maisons:
            communs = maisons[label].keys() & data.keys()
            if any(maisons[label][k] != data[k] for k in communs):
                raise ValueError(f'Données contradictoires pour {label}.')
            maisons[label].update(data)
        else:
            maisons[label] = data
    copie['maisons'] = maisons
    if 'maisons_tropicales' in theme:
        copie['maisons_tropicales'] = {k: dict(v) for k, v in maisons.items()}
    planetes = {}
    for nom, infos in (theme.get('planetes') or theme.get('planètes') or {}).items():
        data = dict(infos or {})
        if 'maison' in data:
            data['maison'] = numero_maison(data['maison'])
        planetes[nom] = data
    copie['planetes'] = planetes
    if 'planètes' in theme:
        copie['planètes'] = {k: dict(v) for k, v in planetes.items()}
    return copie
