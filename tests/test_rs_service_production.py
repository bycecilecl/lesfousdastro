"""Le moteur RS payé conserve les deux étapes validées en local."""

import contextlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")

from utils.revolution_solaire import service


class RapportPayeDeuxEtapesTest(unittest.TestCase):
    def setUp(self):
        temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(temporaire.cleanup)
        self.racine = Path(temporaire.name)
        self.arguments = {
            "personne": {"nom": "Camille", "genre": "female"},
            "lieu_rs": {"lieu": "Paris"},
            "annee": 2026,
            "contexte_client": {"amour": "Je viens de changer de vie."},
            "stockage_dir": self.racine,
        }
        pile = contextlib.ExitStack()
        self.addCleanup(pile.close)
        instant = datetime(2026, 10, 11, tzinfo=timezone.utc)
        calcul = {
            "theme_natal": {}, "theme_revolution_solaire": {},
            "age_au_retour": 46, "naissance_locale": instant,
            "retour": {"retour_utc": instant}, "retour_local": instant,
        }
        resultats = {
            "calculer_theme_revolution_solaire": calcul,
            "extraire_donnees_revolution_solaire": {"facteurs_directeurs_rs": {}},
            "trouver_retour_solaire": {"retour_utc": instant},
            "calculer_transits_annuels_rs": [],
            "detecter_themes_prioritaires_rs": [],
            "generer_rapport_technique": "Ascendant RS calculé.",
            "verifier_rapport_revolution_solaire": "OK",
        }
        for nom, resultat in resultats.items():
            pile.enter_context(patch.object(service, nom, return_value=resultat))
        self.claude = pile.enter_context(patch.object(
            service, "ask_claude",
            side_effect=["# Ta révolution solaire 2026\n\nCorps neutre.<FIN_RAPPORT>",
                         "Une synthèse personnelle.<FIN_SYNTHESE>"],
        ))

    def test_deux_appels_et_contexte_reserve_a_la_synthese(self):
        rapport = service.generer_rapport_revolution_solaire(**self.arguments)
        self.assertEqual(self.claude.call_count, 2)
        self.assertNotIn("Je viens de changer de vie.", self.claude.call_args_list[0].args[0])
        self.assertIn("Je viens de changer de vie.", self.claude.call_args_list[1].args[0])
        self.assertIn("Corps neutre", rapport.texte_markdown)
        self.assertIn("Une synthèse personnelle", rapport.texte_markdown)
        self.assertNotIn("<FIN_", rapport.texte_markdown)
        dossier = self.racine / rapport.identifiant_generation
        self.assertEqual(json.loads((dossier / "preparation.json").read_text())["fournisseur"], "claude")
        self.assertTrue((dossier / "corps_neutre" / "reponse.json").exists())
        self.assertTrue((dossier / "synthese_contextuelle" / "reponse.json").exists())
        self.assertTrue((dossier / "rapport.json").exists())

        second = service.generer_rapport_revolution_solaire(**self.arguments)
        self.assertEqual(second.texte_markdown, rapport.texte_markdown)
        self.assertEqual(self.claude.call_count, 2)

    def test_reprise_apres_echec_de_mise_en_page_sans_nouvel_appel(self):
        with patch.object(service, "generer_rapport_html", side_effect=RuntimeError("HTML indisponible")):
            with self.assertRaises(RuntimeError):
                service.generer_rapport_revolution_solaire(**self.arguments)
        service.generer_rapport_revolution_solaire(**self.arguments)
        self.assertEqual(self.claude.call_count, 2)


if __name__ == "__main__":
    unittest.main()
