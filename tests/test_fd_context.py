"""Vérifications hors ligne du laboratoire ; aucun appel IA ni paiement."""
import ast
import contextlib
import csv
import io
import logging
from pathlib import Path
import unittest
import unicodedata
from unittest.mock import Mock

from utils.fd_context import build_context, configurations, quinconces, valid_dignity
from utils.fd_figures import major_figures, figures_html

ROOT = Path(__file__).resolve().parents[1]


def theme_at(points):
    signs = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
             'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
    return {'planetes': {name: {'longitude': lon, 'signe': signs[int(lon % 360) // 30],
                               'maison': index + 1}
                        for index, (name, lon) in enumerate(points.items())}}


class FiguresTests(unittest.TestCase):
    def test_t_square_category_and_focal_planet(self):
        theme = theme_at({'Soleil': 0, 'Lune': 180, 'Mars': 90})
        figures = major_figures(theme)
        t = [f for f in figures if f['type'] == 't_carre']
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]['categorie'], 'Tes Défis')
        self.assertEqual(t[0]['planete_focale'], 'Mars')
        self.assertIn('maison 3', configurations(theme, figures))
        self.assertIn('Sommet focal : Mars', figures_html(theme, figures))

    def test_grand_trine_category_and_existing_orbs(self):
        for lon, expected in [(120, True), (128, True), (131, False)]:
            figures = major_figures(theme_at({'Soleil': 0, 'Lune': lon, 'Mars': 240}))
            matches = [f for f in figures if f['type'] == 'grand_trigone']
            self.assertEqual(bool(matches), expected)
            if expected:
                self.assertEqual(matches[0]['categorie'], 'Tes Potentiels')

    def test_stellium_and_no_duplicate_concentration(self):
        figures = major_figures(theme_at({'Soleil': 0, 'Mercure': 2, 'Mars': 5}))
        self.assertEqual(len(figures), 1)
        self.assertEqual(figures[0]['type'], 'stellium')
        self.assertEqual(figures[0]['categorie'], 'Dynamiques mixtes')

    def test_unrelated_aspects_do_not_make_t_square(self):
        theme = {'aspects': [dict(p1=a, p2=b, type=t, orb=0) for a, b, t in
                            [('Soleil', 'Lune', 'opposition'),
                             ('Mars', 'Saturne', 'carré'), ('Mercure', 'Vénus', 'carré')]]}
        self.assertFalse(any(f['type'] == 't_carre' for f in major_figures(theme)))

    def test_grand_square_absorbs_internal_t_squares(self):
        figures = major_figures(theme_at({'Soleil': 0, 'Lune': 180, 'Mars': 90, 'Saturne': 270}))
        self.assertEqual(sum(f['type'] == 'grand_carre' for f in figures), 1)
        self.assertFalse(any(f['type'] == 't_carre' for f in figures))

    def test_angular_group_crosses_zero_and_preserves_houses(self):
        theme = theme_at({'Soleil': 358, 'Pluton': 2, 'Lune Noire': 1})
        theme['ascendant'] = {'degre': 0, 'signe': 'Bélier'}
        text = configurations(theme)
        self.assertEqual(text.count('Configuration angulaire'), 1)
        self.assertIn('Ascendant', text)
        self.assertIn('Lune Noire', text)
        self.assertIn('Dynamiques mixtes', text)

    def test_interceptions_and_dignities(self):
        theme = {'planetes': {'Mars': {'signe': 'Scorpion', 'maison': 6},
                             'Vénus': {'signe': 'Verseau', 'maison': 10}},
                 'interceptions': {'signes_interceptes': ['Scorpion']}}
        text = build_context(theme)
        self.assertIn('Mars en Scorpion, maison 6, signe intercepté', text)
        self.assertIn('Vénus en Verseau, maison 10', text)
        self.assertFalse(valid_dignity('Soleil', 'Capricorne', 'exaltation'))
        self.assertTrue(valid_dignity('Soleil', 'Bélier', 'exaltation'))
        self.assertTrue(valid_dignity('Jupiter', 'Vierge', 'exil'))

    def test_quinconce_barreme_and_boundary(self):
        # Exécuter seulement les fonctions pures pour éviter les imports de clients IA.
        tree = ast.parse((ROOT / 'utils/fd_inject.py').read_text())
        names = {'_norm', '_norm_aspect', '_pair_key', '_collect_theme_aspects',
                 '_parse_aspects_field', 'detect_aspects_from_csv', 'detect_etat_planetes'}
        tree.body = [n for n in tree.body if
                     isinstance(n, ast.FunctionDef) and n.name in names or
                     isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_ASPECT_MAP' for t in n.targets)]
        def rows(name):
            with (ROOT / 'data' / 'forces_defis_report' / name).open() as handle:
                return list(csv.DictReader(handle, delimiter=';'))
        ns = {'unicodedata': unicodedata, '_read_csv': rows}
        exec(compile(tree, 'fd_inject.py', 'exec'), ns)
        # Comparaison au score du CSV local, sans imposer celui d'un autre dossier.
        control = theme_at({'Lune': 0, 'Neptune': 90})
        control['aspects'] = [dict(planete1='Lune', planete2='Neptune', aspect='Carré', orbe=0)]
        tension = ns['detect_aspects_from_csv'](control, 'defis')
        self.assertTrue(tension)
        for orb, count in [(0, 1), (3, 1), (3.01, 0)]:
            theme = theme_at({'Lune': 0, 'Neptune': 150 + orb})
            result = ns['detect_aspects_from_csv'](theme, 'defis')
            self.assertEqual(len(result), count)
            if count:
                self.assertEqual(result[0]['score'], tension[0]['score'])
                self.assertEqual(result[0]['aspect'], 'quinconce')
                self.assertIn('ajustements', result[0]['comment'])
        states = ns['detect_etat_planetes'](
            {'planetes': {'Mars': {'signe': 'Scorpion', 'maison': 6}}}, 'etat_planetes.csv')
        self.assertTrue(any(s['type'] == 'force' and 'domicile' in s['etat'] for s in states))

    def test_figures_stay_in_prompt_without_prefixed_report_block(self):
        tree = ast.parse((ROOT / 'utils/forces_defis_analyse.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'analyse_forces_defis']
        prompts = []
        def fake_llm(prompt, system_prompt=None):
            prompts.append(prompt)
            return 'mot ' * 1700
        ns = dict(
            _build_contexte_global=lambda t: {'placements_str': 'contexte ' * 10},
            construire_selection_point_astral=lambda t: {},
            build_unified_priorities=lambda *a, **k: 'Mars domicile Scorpion',
            _GENERER_FORCES_DEFIS=lambda t: {},
            extraire_forces_defis_par_maisons=lambda t: {},
            _genre_directives=lambda m: '', interroger_llm=fake_llm,
            logger=logging.getLogger('test.fd'),
            md_light_to_html=lambda text: text,
            _birth_header_html=lambda *a: '', DISCLAIMER_FORCES_DEFIS_HTML='')
        exec(compile(tree, 'forces_defis_analyse.py', 'exec'), ns)
        with contextlib.redirect_stdout(io.StringIO()):
            result = ns['analyse_forces_defis'](theme_at({'Soleil': 0, 'Lune': 180, 'Mars': 90}))
            self.assertIn('FIGURES CLASSÉES', prompts[0])
            self.assertIn('quatre dynamiques', prompts[0])
            self.assertIn('BARÈME', prompts[0])
            self.assertIn('puis Synthèse', prompts[0])
            self.assertIn('T-carré', prompts[0])
            self.assertIn('Tes Défis', prompts[0])
            self.assertIn('Sommet focal : Mars', prompts[0])
            self.assertNotIn('Configurations majeures', result)
            self.assertNotIn('fd-figures', result)
            self.assertEqual(result.strip(), ('mot ' * 1700).strip())
            short = 'mot ' * 762
            client = Mock(side_effect=lambda prompt, **kwargs: short)
            ns['interroger_llm'] = client
            with self.assertLogs('test.fd', level='WARNING'):
                result = ns['analyse_forces_defis']({'planetes': {}})
            self.assertEqual(result.strip(), short.strip())
            client.assert_called_once()
            ns['interroger_llm'] = lambda prompt: ''
            with self.assertRaises(ValueError):
                ns['analyse_forces_defis']({'planetes': {}})


if __name__ == '__main__':
    unittest.main()
