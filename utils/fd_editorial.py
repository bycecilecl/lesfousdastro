"""Règles éditoriales locales au rapport Forces & Défis, avant rédaction."""
from copy import deepcopy
from html import escape
import re
from utils.fd_context import norm


def render_report_markdown(text):
    """Convertit le Markdown du rapport sans exécuter le HTML du modèle."""
    import markdown
    text = re.sub(
        r'^\s*#{1,2}\s*(?:Rapport\s+)?(?:Mes\s+)?Potentiels\s*(?:&|et)\s*Défis\s*\n+',
        '', str(text or ''), count=1, flags=re.IGNORECASE,
    )
    safe_text = escape(text).replace('[', r'\[').replace(']', r'\]')
    return markdown.markdown(safe_text, extensions=['extra', 'sane_lists'])


def excluded_body(name):
    value = norm(str(name).replace('œ', 'oe').replace('Œ', 'OE'))
    return (any(word in value for word in ('noeud', 'node', 'fortune', 'illumination', 'junon', 'juno'))
            or bool({'rahu', 'ketu'} & set(value.split())))


def prepare_theme(theme):
    result = deepcopy(theme)
    result['planetes'] = {n: d for n, d in result.get('planetes', {}).items()
                          if not excluded_body(n)}
    for key in ('aspects', 'aspects_significatifs'):
        if key in result:
            result[key] = [a for a in result[key] if not any(
                excluded_body(a.get(k, '')) for k in
                ('p1', 'p2', 'planete1', 'planete2', 'planet1', 'planet2', 'A', 'B', 'from', 'to')
            )] if all(isinstance(a, dict) for a in result[key]) else [
                a for a in result[key] if not excluded_body(str(a))]
    return result


def body_name(description):
    # Ne jamais assimiler Lune Noire à Lune lors des fusions.
    if norm(description).startswith('lune noire'):
        return 'Lune Noire'
    return description.split()[0].strip().title() if description else ''


def priority_tension(description):
    words = norm(description).split()
    return ('lune noire' not in norm(description)
            and bool({'soleil', 'lune'} & set(words))
            and bool({'mars', 'saturne', 'uranus', 'neptune'} & set(words))
            and bool({'conjonction', 'carre', 'opposition'} & set(words)))


def classify(items):
    result = []
    for original in items:
        item = dict(original)
        text = norm(item.get('description', ''))
        if excluded_body(text):
            continue
        if 'quinconce' in text and any(angle in text.split() for angle in
                                       ('asc', 'ascendant', 'mc', 'fc', 'dsc', 'descendant')):
            continue
        if 'conjonction' in text and 'soleil' in text and 'mercure' in text:
            continue
        if 'lune noire' in text or 'lilith' in text or priority_tension(text):
            suffix = item.get('categorie', '').partition('(')[2]
            item['categorie'] = 'DÉFI' + (' (' + suffix if suffix else '')
        result.append(item)
    return result


def report_prompt(meta, placements, priorities, figures):
    return f"""Rédige un rapport Potentiels & Défis personnalisé pour {meta.get('prenom', 'la personne')}
à partir des données fournies. Respecte leur classement, leur ordre et leur contenu :
ne fais pas de nouvelle sélection.

Structure : Tes Défis, Tes Potentiels, Dynamiques mixtes, puis Synthèse.

Construis une lecture, pas un catalogue. Regroupe les éléments qui décrivent une
même dynamique sans effacer leurs particularités. Ancre chaque interprétation
dans les signes, maisons et états fournis. Explique le mécanisme psychologique,
ses contradictions, ses manifestations concrètes possibles et les ressources mobilisables.

Tutoiement. Ton direct, incarné, psychologique et mordant, avec une pointe d’humour
noir pertinente. Pas de flatterie, de métaphores décoratives ni de conseils
interchangeables. Formule les vécus supposés au conditionnel ; n’invente aucun
fait astrologique ou biographique. Genre grammatical : {meta.get('genre', 'neutre')}.
Une maison n'est pas une dignité ni une conjonction à un angle : n'affirme une
conjonction que si son orbe figure dans les données. N'interprète pas le signe
d'une transsaturnienne hors maître d'Ascendant.

Vise 1 700 à 2 100 mots : assez de profondeur, sans répétitions ni inventaire exhaustif.
Chaque paragraphe traite quatre dynamiques maximum, sans chercher à atteindre ce plafond.

La synthèse ne refait pas la liste. Elle isole le point de bascule du thème :
comment une ressource sélectionnée répond au défi dominant, dans un vécu possible
et concret. Garde un fil conducteur, sans conseil interchangeable.

DONNÉES DU THÈME :
{placements}

DYNAMIQUES CLASSÉES PAR LE BARÈME :
{priorities}

FIGURES CLASSÉES — toutes à intégrer :
{figures}
"""


def ensure_report_sections(text):
    """Rétablit les quatre titres si le modèle les remplace par trois séparateurs."""
    text = str(text or '').strip()
    headings = ('Tes Défis', 'Tes Potentiels', 'Dynamiques mixtes', 'Synthèse')
    if any(re.search(rf'(?im)^#+\s*{re.escape(title)}\s*$', text) for title in headings):
        return text
    parts = [part.strip() for part in re.split(r'(?m)^\s*---\s*$', text)]
    if len(parts) != 4 or not all(parts):
        return text
    return '\n\n'.join(f'## {title}\n\n{part}' for title, part in zip(headings, parts))
