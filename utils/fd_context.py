"""Contexte factuel de Forces & Défis, sans appel réseau ni interprétation."""
import unicodedata


def norm(value):
    return unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower().strip()


def valid_dignity(planet, sign, state):
    # Domiciles, exaltation : exils/chutes calculés par opposition.
    signs = ['belier', 'taureau', 'gemeaux', 'cancer', 'lion', 'vierge', 'balance', 'scorpion', 'sagittaire', 'capricorne', 'verseau', 'poissons']
    rules = {'soleil': ([4], 0), 'lune': ([3], 1), 'mercure': ([2, 5], 5),
             'venus': ([1, 6], 11), 'mars': ([0, 7], 9), 'jupiter': ([8, 11], 3),
             'saturne': ([9, 10], 6)}
    if norm(planet) not in rules:
        return True  # Ne pas imposer une école pour les planètes transsaturniennes.
    homes, exalt = rules[norm(planet)]
    indices = {'domicile': homes, 'exaltation': [exalt],
               'exil': [(i + 6) % 12 for i in homes], 'chute': [(exalt + 6) % 12]}
    return norm(sign) in [signs[i] for i in indices.get(norm(state), [])]


def placements(theme):
    planets = dict(theme.get('planetes') or {})
    if 'Ascendant' not in planets and isinstance(theme.get('ascendant'), dict):
        planets['Ascendant'] = theme['ascendant']
    return planets


def intercepted_signs(theme):
    data = theme.get('interceptions') or {}
    if isinstance(data, list):
        return {norm(s) for s in data if isinstance(s, str)}
    signs = list(data.get('signes_interceptes') or [])
    for key in ('maisons_interceptées', 'maisons_interceptees'):
        signs.extend((data.get(key) or {}).keys())
    for item in data.values():
        if isinstance(item, dict):
            signs.extend(item.get('signes') or item.get('signs') or [])
    return {norm(s) for s in signs}


def planet_context(theme, name):
    aliases = {'milieu du ciel': 'mc', 'asc': 'ascendant', 'lilith': 'lune noire'}
    key = lambda n: aliases.get(norm(n), norm(n))
    match = next(((n, d) for n, d in placements(theme).items() if key(n) == key(name)), None)
    if match is None:
        return str(name) + ' (placement non fourni)'
    name, data = match
    sign = data.get('signe') or data.get('sign') or 'signe non fourni'
    house = data.get('maison') or data.get('house')
    text = f'{name} en {sign}'
    text += f', maison {house}' if house else ', maison non fournie'
    if norm(sign) in intercepted_signs(theme):
        text += ', signe intercepté'
    if data.get('retrograde') or data.get('retro'):
        text += ', rétrograde'
    return text


def build_context(theme):
    lines = [planet_context(theme, name) +
             (' [Défi]' if norm(name) in {'lune noire', 'lilith'} else '')
             for name in placements(theme)]
    return '\n'.join('- ' + line for line in lines)


def quinconces(theme):
    """Complète les aspects pour ce rapport uniquement : 150°, orbe <= 3°."""
    from itertools import combinations
    positions = []
    for name, data in placements(theme).items():
        value = next((data[k] for k in ('longitude', 'lon', 'ecliptic_longitude', 'degre')
                      if data.get(k) is not None), None)
        try:
            longitude = float(value) % 360
        except (ValueError, TypeError):
            continue
        positions.append((name, longitude))
    result = []
    for (a, x), (b, y) in combinations(positions, 2):
        separation = abs((x - y + 180) % 360 - 180)
        orb = abs(separation - 150)
        if orb <= 3.0:
            result.append({'p1': a, 'p2': b, 'type': 'quinconce', 'orb': orb})
    return result


def concentration_records(theme):
    """Fenêtres circulaires de 10°, groupes maximaux ; signe/maison distincts."""
    planets = placements(theme)
    real = {'Soleil', 'Lune', 'Mercure', 'Vénus', 'Venus', 'Mars', 'Jupiter', 'Saturne', 'Uranus', 'Neptune', 'Pluton'}
    personal = {'Soleil', 'Lune', 'Mercure', 'Vénus', 'Venus', 'Mars'}
    angles = {'Ascendant', 'Milieu du Ciel', 'MC', 'Descendant', 'Fond du Ciel'}
    allowed = real | angles | {'Lune Noire', 'Lilith'}
    positions = {}
    for name, data in planets.items():
        if name not in allowed:
            continue
        value = next((data[k] for k in ('longitude', 'lon', 'ecliptic_longitude', 'degre') if data.get(k) is not None), None)
        try:
            positions[name] = float(value) % 360
        except (ValueError, TypeError):
            pass
    groups = set()
    for start in positions.values():
        members = frozenset(n for n, lon in positions.items() if (lon - start) % 360 <= 10)
        if len(members & real) >= 2 and len(members) >= 3 and members & personal:
            groups.add(members)
    groups = [g for g in groups if not any(g < other for other in groups)]
    groups.sort(key=lambda g: (-bool(g & angles), -len(g), sorted(g)))
    records = []
    covered = []
    for members in groups:
        label = 'Configuration angulaire' if members & angles else 'Amas par proximité'
        records.append({'type': 'concentration', 'label': label,
                        'categorie': 'Dynamiques mixtes', 'planetes': sorted(members)})
        covered.append(members & real)
    for field, label in [('signe', 'Concentration par signe'), ('maison', 'Concentration par maison')]:
        buckets = {}
        for name, data in planets.items():
            if name in real and data.get(field) is not None:
                buckets.setdefault(str(data[field]), set()).add(name)
        for value, members in buckets.items():
            if len(members) < 3 or not members & personal or any(members == g for g in covered):
                continue
            records.append({'type': 'concentration',
                            'label': f'{label} {value} (ne suppose pas une conjonction de tous les membres)',
                            'categorie': 'Dynamiques mixtes', 'planetes': sorted(members)})
            covered.append(members)
    return records


def configurations(theme, figures=None):
    from utils.fd_figures import major_figures, figure_description
    figures = major_figures(theme) if figures is None else figures
    return '\n'.join(f"- [{f['categorie']} — mention obligatoire] {figure_description(theme, f)}"
                     for f in figures) or 'Aucune configuration majeure détectée.'
