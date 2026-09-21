"""Le rapport FD ne reconfigure ni les clients IA ni les données partagées."""
import ast
import csv
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IsolationTests(unittest.TestCase):
    def test_csv_resolver_is_scoped_and_reads_validated_files(self):
        source = ROOT / 'utils/fd_inject.py'
        tree = ast.parse(source.read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in {'_resolve_data_dir', '_read_csv'}]
        ns = {'Path': Path, 'csv': csv, '__file__': str(source), '_FALLBACK_SINGLE_FILE': None}
        exec(compile(tree, str(source), 'exec'), ns)
        ns['DATA_DIR'] = ns['_resolve_data_dir']()
        self.assertEqual(ns['DATA_DIR'], ROOT / 'data/forces_defis_report')
        for name in ('forces_defis.csv', 'etat_planetes.csv', 'placements_maisons.csv'):
            self.assertTrue(ns['_read_csv'](name))
        neptune = next(r for r in ns['_read_csv']('placements_maisons.csv')
                       if r['PLANETE'] == 'Neptune' and r['MAISON'] == 'VIII')
        self.assertNotIn('Fatigue chronique', neptune['COMMENTAIRE'])

    def test_analysis_uses_dedicated_client(self):
        tree = ast.parse((ROOT / 'utils/forces_defis_analyse.py').read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertIn('utils.fd_claude', imports)
        self.assertNotIn('utils.openai_utils', imports)
        self.assertNotIn('utils.llm_client', imports)

    def test_no_global_provider_configuration(self):
        for name in ('fd_claude', 'fd_editorial', 'fd_figures', 'fd_context'):
            source = (ROOT / f'utils/{name}.py').read_text()
            self.assertNotIn('load_dotenv', source)
            self.assertNotIn('os.environ[', source)

    def test_pdf_uses_forces_defis_running_header(self):
        tree = ast.parse((ROOT / 'routes/forces_defis_module.py').read_text())
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == 'html_to_pdf']
        self.assertEqual(len(calls), 2)
        for call in calls:
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            self.assertIn('page_header', values)
            self.assertEqual(ast.literal_eval(values['page_header']),
                             "Mes Potentiels & Défis - Les Fous d'Astro")

    def test_solo_forces_defis_uses_background_generation(self):
        source = (ROOT / 'routes/checkout.py').read_text()
        self.assertIn(
            'if len(valid_products) == 1 and valid_products[0] != "forces_defis":',
            source,
        )

    def test_background_result_is_persisted_and_displayed_without_regeneration(self):
        checkout = (ROOT / 'routes/checkout.py').read_text()
        generator = (ROOT / 'routes/forces_defis_module.py').read_text()
        waiting = (ROOT / 'templates/analyses_en_cours.html').read_text()

        self.assertIn('"contenu_html": str(contenu_html)', generator)
        self.assertIn('"contenu_html": resultat.get("contenu_html")', checkout)
        self.assertIn('@checkout_bp.route("/analyse-status/<product_id>")', checkout)
        self.assertIn('@checkout_bp.route("/analyse-resultat/<product_id>")', checkout)
        self.assertIn('owned_order(paid=True)', checkout)
        self.assertIn('fetch(statusUrl', waiting)
        self.assertIn('window.location.replace(data.result_url)', waiting)


if __name__ == '__main__':
    unittest.main()
