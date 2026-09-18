"""Adaptateur Forces & Défis du moteur de figures existant dans le laboratoire."""
from itertools import combinations
from math import isfinite
from html import escape

from point_astral_famille import configurations_astrologiques as engine
from utils.fd_context import norm, placements, planet_context, concentration_records


def major_figures(theme):
    """Figures hors quotas CSV ; règles et orbes du moteur existant conservés."""
    aliases = {norm(n): n for n in engine.CORPS_CONFIGURATIONS_MAJEURES | engine.POINTS_CONJONCTIONS_IDENTITAIRES}
    aliases.update({'asc': 'Ascendant', 'milieu du ciel': 'MC', 'lilith': 'Lune Noire'})
    canonical = lambda name: aliases.get(norm(name), name)
    positions = {}
    for name, data in placements(theme).items():
        copied = dict(data)
        value = next((data[k] for k in ('longitude', 'lon', 'ecliptic_longitude', 'degre')
                      if data.get(k) is not None), None)
        # 'degre' est une longitude absolue dans le calculateur du site.
        try:
            longitude = float(value) % 360
            if isfinite(longitude):
                copied['longitude'] = longitude
        except (TypeError, ValueError):
            pass
        positions[canonical(name)] = copied

    aspects = {}
    translations = {'carre': 'carré', 'square': 'carré', 'trine': 'trigone',
                    'conjunction': 'conjonction', 'quincunx': 'quinconce'}
    for raw in (theme.get('aspects') or theme.get('aspects_significatifs') or []):
        if not isinstance(raw, dict):
            continue
        a = canonical(raw.get('planete1') or raw.get('p1') or raw.get('planet1') or '')
        b = canonical(raw.get('planete2') or raw.get('p2') or raw.get('planet2') or '')
        kind = norm(raw.get('aspect') or raw.get('type') or '')
        kind = translations.get(kind, kind)
        orb = next((raw[k] for k in ('orbe', 'orb') if raw.get(k) is not None), None)
        try:
            orb = float(orb)
        except (TypeError, ValueError):
            continue
        if a and b and a != b and isfinite(orb) and orb >= 0:
            aspects[(*sorted((a, b)), kind)] = dict(planete1=a, planete2=b, aspect=kind, orbe=orb)

    # Les aspects individuels sont parfois filtrés plus strictement que les figures.
    # Reconstituer les liens depuis les longitudes avec les limites de ce moteur.
    rules = [('conjonction', 0, engine.ORBE_CONJONCTION_BLOC),
             ('opposition', 180, max(engine.ORBE_OPPOSITION_T_CARRE, engine.ORBE_OPPOSITION_GRAND_CARRE)),
             ('carré', 90, max(engine.ORBE_CARRE_T_CARRE, engine.ORBE_CARRE_GRAND_CARRE)),
             ('trigone', 120, engine.ORBE_GRAND_TRIGONE)]
    for (a, pa), (b, pb) in combinations(sorted(positions.items()), 2):
        x, y = pa.get('longitude'), pb.get('longitude')
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        if not isfinite(x) or not isfinite(y):
            continue
        distance = abs((x - y + 180) % 360 - 180)
        for kind, angle, limit in rules:
            key = (*sorted((a, b)), kind)
            aspects.pop(key, None)
            orb = abs(distance - angle)
            if orb <= limit:
                aspects[key] = dict(planete1=a, planete2=b, aspect=kind, orbe=orb)

    categories = {'t_carre': ('Tes Défis', 'T-carré'),
                  'grand_carre': ('Tes Défis', 'Grand carré'),
                  'grand_trigone': ('Tes Potentiels', 'Grand trigone'),
                  'stellium': ('Dynamiques mixtes', 'Amas (stellium)')}
    records = []
    for figure in engine.analyser_configurations_majeures(list(aspects.values()), positions):
        if figure.get('type') in categories:
            category, label = categories[figure['type']]
            records.append({**figure, 'categorie': category, 'label': label})
    stelliums = [set(r['planetes']) for r in records if r['type'] == 'stellium']
    records.extend(r for r in concentration_records(theme)
                   if not any({canonical(p) for p in r['planetes']} <= members for members in stelliums))
    return records


def figure_description(theme, figure):
    text = figure['label'] + ' : ' + ' ; '.join(planet_context(theme, n) for n in figure['planetes'])
    if any(norm(n) in {'lune noire', 'lilith'} for n in figure['planetes']):
        text += '. Composante Lune Noire : Défi'
    focal = figure.get('planetes_focales') or ([figure['planete_focale']] if figure.get('planete_focale') else [])
    if focal:
        text += '. Sommet focal : ' + ', '.join(focal)
    return text


def figures_html(theme, figures):
    """Rappel factuel garanti même si la rédaction omet une figure."""
    if not figures:
        return ''
    blocks = ['<section class="fd-figures"><h2>Configurations majeures</h2>']
    for category in ('Tes Défis', 'Tes Potentiels', 'Dynamiques mixtes'):
        selected = [f for f in figures if f['categorie'] == category]
        if selected:
            blocks.append('<h3>' + escape(category) + '</h3>')
            for figure in selected:
                blocks.append('<p>' + escape(figure_description(theme, figure)) + '</p>')
    return ''.join(blocks) + '</section>'
