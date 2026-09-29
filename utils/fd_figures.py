"""Adaptateur Forces & Défis du moteur de figures existant dans le laboratoire."""
from itertools import combinations
from math import isfinite
from html import escape

from point_astral_famille import configurations_astrologiques as engine
from utils.fd_context import (norm, placements, planet_context, concentration_records,
                              ascendant_ruler)


def _diamants_du_rapport(figures, aspects):
    """Détecte les cerfs-volants pour ce rapport sans changer le moteur partagé."""
    index = {(frozenset((a['planete1'], a['planete2'])), a['aspect']): a
             for a in aspects}

    def linked(a, b, kind):
        return index.get((frozenset((a, b)), kind))

    results = []
    seen = set()
    bodies = {body for a in aspects for body in (a['planete1'], a['planete2'])
              if body in engine.CORPS_CONFIGURATIONS_MAJEURES}
    for trigone in (f for f in figures if f['type'] == 'grand_trigone'):
        summits = trigone.get('sommets') or [[p] for p in trigone['planetes']]
        if len(summits) != 3 or any(len(s) != 1 for s in summits):
            continue
        vertices = [s[0] for s in summits]
        for opposite in vertices:
            others = [p for p in vertices if p != opposite]
            candidates = {tip for tip in bodies - set(vertices)
                          if linked(tip, opposite, 'opposition')
                          and all(linked(tip, p, 'sextile') for p in others)}
            while candidates:
                group = {min(candidates)}
                candidates -= group
                frontier = list(group)
                while frontier:
                    current = frontier.pop()
                    joined = {p for p in candidates if linked(current, p, 'conjonction')}
                    candidates -= joined
                    group |= joined
                    frontier.extend(joined)
                members = tuple(sorted(set(vertices) | group))
                if members in seen:
                    continue
                seen.add(members)
                results.append({'type': 'diamant', 'label': 'Diamant (cerf-volant)',
                                'categorie': 'Tes Potentiels', 'planetes': list(members),
                                'sommets_grand_trigone': vertices,
                                'pointe': sorted(group), 'sommet_oppose': opposite})
    return results


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
    records.extend(_diamants_du_rapport(records, list(aspects.values())))
    stelliums = [set(r['planetes']) for r in records if r['type'] == 'stellium']
    records.extend(r for r in concentration_records(theme)
                   if not any({canonical(p) for p in r['planetes']} <= members for members in stelliums))
    return records


def figure_description(theme, figure):
    text = figure['label'] + ' : ' + ' ; '.join(planet_context(theme, n) for n in figure['planetes'])
    if figure.get('type') == 'concentration' and figure['label'].startswith('Concentration par'):
        positions = {}
        for name in figure['planetes']:
            data = next((value for key, value in placements(theme).items()
                         if norm(key) == norm(name)), {})
            value = next((data.get(key) for key in
                          ('longitude', 'lon', 'ecliptic_longitude', 'degre')
                          if data.get(key) is not None), None)
            try:
                positions[name] = float(value) % 360
            except (TypeError, ValueError):
                pass
        if len(positions) >= 2:
            pairs = ((abs((a_lon - b_lon + 180) % 360 - 180), a, b)
                     for (a, a_lon), (b, b_lon) in combinations(positions.items(), 2))
            gap, a, b = max(pairs)
            if gap > engine.ORBE_CONJONCTION_BLOC:
                text += (f'. {a}–{b} : écart {gap:.2f}°, hors orbe de conjonction '
                         f'de {engine.ORBE_CONJONCTION_BLOC:g}°')
    if any(norm(n) in {'lune noire', 'lilith'} for n in figure['planetes']):
        text += '. Composante Lune Noire : Défi'
    focal = figure.get('planetes_focales') or ([figure['planete_focale']] if figure.get('planete_focale') else [])
    if focal:
        text += '. Sommet focal : ' + ', '.join(focal)
    ruler = ascendant_ruler(theme)
    members = {norm(n) for n in figure['planetes']}
    if ruler and norm(ruler) in members:
        text += f". Maître d'Ascendant impliqué : {ruler} — priorité renforcée"
        if any(norm(n) == norm(ruler) for n in focal):
            text += ', enjeu identitaire central au sommet de la figure'
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
