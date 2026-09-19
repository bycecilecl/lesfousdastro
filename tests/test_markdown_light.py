"""Régressions du Markdown léger utilisé par Potentiels & Défis."""
import unittest

from utils.convert_markdown_light import md_light_to_html


class MarkdownLightTests(unittest.TestCase):
    def test_italic_emphasis_from_report(self):
        source = ("séparer ce que tu *ressens* de ce que tu *penses*. "
                  "Tu ne discutes pas, tu *sondes*. C'est simplement *là*.")
        html = md_light_to_html(source)
        for word in ('ressens', 'penses', 'sondes', 'là'):
            self.assertIn(f'<em>{word}</em>', html)
        self.assertNotIn('*ressens*', html)

    def test_bold_and_italic_are_not_confused(self):
        html = md_light_to_html('**Important** et *nuancé*.')
        self.assertIn('<strong>Important</strong>', html)
        self.assertIn('<em>nuancé</em>', html)
        self.assertNotIn('<em><strong>', html)

    def test_emphasis_in_list_items_and_titles(self):
        html = md_light_to_html('# *Titre*\n\n- **Force** et *nuance*')
        self.assertIn('<h1 class="section-title"><em>Titre</em></h1>', html)
        self.assertIn('<li><strong>Force</strong> et <em>nuance</em></li>', html)


if __name__ == '__main__':
    unittest.main()
