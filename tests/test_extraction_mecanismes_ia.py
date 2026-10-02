import unittest

from utils.extraction_mecanismes_ia import construire_messages_extraction


class TestExtractionMecanismesIA(unittest.TestCase):
    def test_ajoute_les_garde_fous_karmiques_uniquement_au_karmique(self):
        sections = [{
            "cle_section": "synthese",
            "titre": "Synthèse",
            "contenu": "Un mécanisme possible est présenté avec assez de contenu.",
        }]

        prompt_karmique = construire_messages_extraction(
            sections,
            type_analyse="analyse_karmique",
        )[0]["content"]
        prompt_standard = construire_messages_extraction(sections)[0]["content"]

        self.assertIn("ne sont jamais des faits établis", prompt_karmique)
        self.assertIn("sans adjectif genré", prompt_karmique)
        self.assertIn("ignore toute affirmation médicale", prompt_karmique)
        self.assertNotIn("Règles spécifiques à l'analyse karmique", prompt_standard)


if __name__ == "__main__":
    unittest.main()
