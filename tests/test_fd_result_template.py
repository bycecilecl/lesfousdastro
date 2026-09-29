"""Contrôles hors ligne du gabarit web Potentiels & Défis."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResultTemplateTests(unittest.TestCase):
    def test_booking_link_points_to_services_page(self):
        analysis = (ROOT / 'utils/forces_defis_analyse.py').read_text()
        template = (ROOT / 'templates/forces_defis_resultat.html').read_text()
        self.assertIn('href="https://lesfousdastro.fr/prestations"', template)
        self.assertNotIn('href="https://bycecilecl.com"', template)
        self.assertNotIn('DISCLAIMER_FORCES_DEFIS_HTML', analysis)

    def test_template_matches_report_family_structure(self):
        template = (ROOT / 'templates/forces_defis_resultat.html').read_text()
        for marker in ('logo-header', 'personal-info', 'content-wrapper',
                       'logo_base64', 'infos.date_naissance', 'pdf_url'):
            self.assertIn(marker, template)
        self.assertIn('max-width:1200px', template)
        self.assertIn("url_for('main.index')", template)
        self.assertIn("url_for('static', filename='images/logo_les_fous_dastro.webp')", template)

    def test_disclaimer_has_stable_css_hook(self):
        analysis = (ROOT / 'utils/forces_defis_analyse.py').read_text()
        template = (ROOT / 'templates/forces_defis_resultat.html').read_text()
        self.assertIn('class="fd-disclaimer"', template)
        self.assertEqual(template.count('À propos de cette lecture'), 1)
        self.assertNotIn('fd-disclaimer', analysis)
        self.assertIn('.fd-disclaimer', template)

    def test_pdf_notice_is_present_in_solo_and_pack(self):
        route = (ROOT / 'routes/forces_defis_module.py').read_text()
        self.assertEqual(route.count('À propos de cette lecture :'), 2)
        self.assertEqual(route.count('.fd-birth-header{{display:none}}'), 2)


if __name__ == '__main__':
    unittest.main()
