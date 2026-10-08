import unittest

from utils.revolution_solaire.prompt_rapport_complet import construire_prompt_rapport_complet
from utils.revolution_solaire.accords import accorder_formes_inclusives
from utils.revolution_solaire.prompt_synthese_contextuelle import (
    TITRE_SYNTHESE,
    assembler_rapport,
    construire_prompt_synthese_contextuelle,
)


class PromptsDeuxEtapesTest(unittest.TestCase):
    def test_le_corps_ne_recoit_aucune_confidence(self):
        confidence = "je vis dans un appartement que je n'aime pas"
        prompt_corps = construire_prompt_rapport_complet(
            {}, [], nom="Test", annee=2026, debut_transits="2026-10-11",
            fin_transits="2027-10-11", synthese_interne="",
            releve_technique="Ascendant RS en Bélier.",
        )
        prompt_synthese = construire_prompt_synthese_contextuelle(
            "Ascendant RS en Bélier.", {"foyer": confidence})
        self.assertNotIn(confidence, prompt_corps)
        self.assertNotIn("CONTEXTE FOURNI PAR LA PERSONNE", prompt_corps)
        self.assertIn(confidence, prompt_synthese)
        self.assertNotIn(TITRE_SYNTHESE, prompt_corps)

    def test_assemblage_ne_reecrit_pas_le_corps(self):
        corps = "# Ta révolution solaire 2026\n\nUne lecture neutre.<FIN_RAPPORT>"
        texte = assembler_rapport(corps, "Un choix plus personnel.<FIN_SYNTHESE>")
        self.assertTrue(texte.startswith("# Ta révolution solaire 2026\n\nUne lecture neutre."))
        self.assertEqual(texte.count(TITRE_SYNTHESE), 1)
        self.assertNotIn("<FIN_", texte)

    def test_accord_masculin_et_feminin(self):
        self.assertEqual(accorder_formes_inclusives('Tu es prêt·e.', 'male'), 'Tu es prêt.')
        self.assertEqual(accorder_formes_inclusives('Tu es prêt·e.', 'female'), 'Tu es prête.')
        self.assertEqual(accorder_formes_inclusives('Tu es prêt·e.', ''), 'Tu es prêt·e.')

    def test_genre_transmis_au_prompt(self):
        prompt = construire_prompt_rapport_complet(
            {}, [], nom='Test', genre='male', annee=2026,
            debut_transits='', fin_transits='', synthese_interne='',
            releve_technique='Chiron RS est en maison VII.',
        )
        self.assertIn('Accord grammatical demandé : masculin', prompt)
        self.assertIn('Chiron, les Nœuds, la Lune Noire', prompt)


if __name__ == "__main__":
    unittest.main()
