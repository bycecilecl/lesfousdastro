"""Contrôles hors ligne du gabarit web Potentiels & Défis."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResultTemplateTests(unittest.TestCase):
    def test_template_matches_report_family_structure(self):
        template = (ROOT / 'templates/forces_defis_resultat.html').read_text()
        for marker in ('logo-header', 'personal-info', 'content-wrapper',
                       'logo_base64', 'infos.date_naissance', 'pdf_url'):
            self.assertIn(marker, template)
        self.assertIn('max-width:1200px', template)
        self.assertIn("url_for('main.index')", template)

    def test_disclaimer_has_stable_css_hook(self):
        analysis = (ROOT / 'utils/forces_defis_analyse.py').read_text()
        template = (ROOT / 'templates/forces_defis_resultat.html').read_text()
        self.assertIn('class="fd-disclaimer"', analysis)
        self.assertIn('.content-wrapper .fd-disclaimer', template)


if __name__ == '__main__':
    unittest.main()
