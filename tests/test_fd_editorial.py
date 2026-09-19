"""Règles validées : tests hors ligne sans import des clients IA."""
import ast
import csv
import re
import unicodedata
import unittest
from pathlib import Path
from utils.fd_editorial import (prepare_theme, classify, priority_tension,
                                report_prompt, ensure_report_sections)

ROOT = Path(__file__).resolve().parents[1]


def selection_functions():
    tree = ast.parse((ROOT / 'utils/fd_inject.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) or
                 isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                 t.id == '_ASPECT_MAP' for t in n.targets)]
    namespace = {'unicodedata': unicodedata, 're': re, 'Path': Path}
    exec(compile(tree, 'fd_inject.py', 'exec'), namespace)
    def rows(name):
        with (ROOT / 'data' / 'forces_defis_report' / name).open() as handle:
            return list(csv.DictReader(handle, delimiter=';'))
    namespace['_read_csv'] = rows
    return namespace


class EditorialTests(unittest.TestCase):
    def test_exact_priority_pairs(self):
        for luminary in ('Soleil', 'Lune'):
            for other in ('Mars', 'Saturne', 'Uranus', 'Neptune'):
                for aspect in ('conjonction', 'carré', 'opposition'):
                    self.assertTrue(priority_tension(f'{luminary} {aspect} {other}'))
                    self.assertTrue(priority_tension(f'{other} {aspect} {luminary}'))
        for text in ('Soleil carré Pluton', 'Lune trigone Neptune',
                     'Lune quinconce Saturne', 'Lune Noire carré Mars'):
            self.assertFalse(priority_tension(text))

    def test_exclusions_without_mutating_theme(self):
        names = ['Soleil', 'Lune', 'Lune Noire', 'Rahu', 'Ketu', 'Nœud Nord',
                 'Noeud Sud', 'Part de Fortune', "Point d’illumination", 'Junon', 'Juno']
        theme = {'planetes': {n: {} for n in names},
                 'aspects': [dict(p1='Mars', p2='Rahu', type='trigone')]}
        clean = prepare_theme(theme)
        self.assertEqual(set(clean['planetes']), {'Soleil', 'Lune', 'Lune Noire'})
        self.assertEqual(clean['aspects'], [])
        self.assertEqual(len(theme['planetes']), len(names))

    def test_excluded_points_are_removed_from_aspects_and_priorities(self):
        excluded = ('Junon', 'Juno', 'Part de Fortune', "Point d’illumination")
        for body in excluded:
            theme = {'planetes': {'Soleil': {}, body: {}},
                     'aspects': [dict(p1='Soleil', p2=body, type='conjonction')]}
            clean = prepare_theme(theme)
            self.assertNotIn(body, clean['planetes'])
            self.assertEqual(clean['aspects'], [])
            self.assertEqual(classify([
                dict(description=f'Soleil conjonction {body}', categorie='MIXTE')
            ]), [])

    def test_black_moon_is_always_challenge_and_filters(self):
        items = [dict(description=t, categorie='FORCE (aspect)', score=5) for t in
                 ('Lune Noire conjoint FC', 'Lilith trigone Mars',
                  'Soleil conjonction Mercure', 'Ascendant quinconce Pluton',
                  'Mars trigone Rahu', 'Lune domicile Cancer')]
        result = classify(items)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(r['categorie'].startswith('DÉFI') for r in result[:2]))
        self.assertTrue(result[2]['categorie'].startswith('FORCE'))

    def test_full_selection_preserves_cancer_moon(self):
        ns = selection_functions()
        theme = {'planetes': {
            'Lune': {'signe': 'Cancer', 'maison': 2, 'degre_dans_signe': 15},
            'Lune Noire': {'signe': 'Vierge', 'maison': 4, 'degre_dans_signe': 8.53},
            'Soleil': {'signe': 'Capricorne', 'maison': 8},
            'Neptune': {'signe': 'Capricorne', 'maison': 8},
            'Venus': {'signe': 'Verseau', 'maison': 10},
            'Pluton': {'signe': 'Scorpion', 'maison': 6}},
            'maisons': {'4': {'signe': 'Vierge', 'degre_dans_signe': 1}},
            'aspects': [dict(p1=a, p2=b, type=t, orb=1) for a, b, t in
                        [('Venus', 'Pluton', 'carré'), ('Lune', 'Neptune', 'opposition'),
                         ('Soleil', 'Neptune', 'conjonction')]]}
        text = ns['build_unified_priorities'](theme)
        challenges, potentials = text.split('## 🟢 POTENTIELS')
        self.assertIn('Lune Noire conjoint FC', challenges)
        self.assertNotIn('Sensibilité et intuition profondes', challenges)
        self.assertIn('Lune domicile Cancer', potentials)
        self.assertIn('Sensibilité et intuition profondes', potentials)
        self.assertLess(challenges.index('Lune opposition Neptune'), challenges.index('Venus carre Pluton'))
        self.assertLess(challenges.index('Soleil conjonction Neptune'), challenges.index('Venus carre Pluton'))
        self.assertNotIn('Fatigue chronique', text)

    def test_angle_quinconces_removed_planet_quinconces_kept(self):
        ns = selection_functions()
        for angle in ('Ascendant', 'MC', 'FC', 'Descendant'):
            theme = {'planetes': {}, 'aspects': [dict(p1=angle, p2='Pluton', type='quinconce', orb=0)]}
            self.assertEqual(ns['detect_aspects_from_csv'](theme, 'mixte'), [])
        theme = {'planetes': {}, 'aspects': [dict(p1='Lune', p2='Neptune', type='quinconce', orb=3)]}
        self.assertTrue(ns['detect_aspects_from_csv'](theme, 'defis'))

    def test_short_prompt_no_selection_rules(self):
        prompt = report_prompt({}, 'PLACEMENTS', 'SELECTION', 'FIGURES')
        self.assertLess(len(prompt.split()), 270)
        self.assertIn('puis Synthèse', prompt)
        self.assertIn('quatre dynamiques maximum', prompt)
        self.assertNotIn('EXCLUSIONS', prompt)
        self.assertNotIn('ORDRE IMPÉRATIF', prompt)

    def test_missing_headings_are_restored_from_separators(self):
        text = 'défis\n---\npotentiels\n---\nmixtes\n---\nsynthèse'
        result = ensure_report_sections(text)
        self.assertEqual(result.count('## '), 4)
        for title in ('Tes Défis', 'Tes Potentiels', 'Dynamiques mixtes', 'Synthèse'):
            self.assertIn('## ' + title, result)
        self.assertNotIn('\n---\n', result)

    def test_existing_headings_are_not_rewritten(self):
        text = '## Tes Défis\n\nTexte déjà structuré.'
        self.assertEqual(ensure_report_sections(text), text)


if __name__ == '__main__':
    unittest.main()
