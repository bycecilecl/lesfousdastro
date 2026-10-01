import unittest

from utils.rendu_brouillon_cycle import rendu_brouillon_cycle


class RenduBrouillonCycleTests(unittest.TestCase):
    def test_aperçu_retire_objet_et_formate_titres(self):
        html = str(rendu_brouillon_cycle(
            "OBJET : Mon cycle\n\n**Le mouvement du mois**\n\n"
            "Un **choix** se précise.\nLa suite arrive."
        ))
        self.assertNotIn("OBJET", html)
        self.assertIn("<h2>Le mouvement du mois</h2>", html)
        self.assertIn("<strong>choix</strong>", html)
        self.assertIn("La suite arrive.", html)

    def test_aperçu_echappe_contenu_importe(self):
        html = str(rendu_brouillon_cycle("<script>alert(1)</script> **douceur**"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>douceur</strong>", html)


if __name__ == "__main__":
    unittest.main()
