"""Contrôles sans paiement ni appel IA du parcours de vente RS."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from flask import Flask
from werkzeug.exceptions import BadRequest

from config.products import PRODUCTS
from services.analysis_orders import catalog_items


os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
MODULE_PATH = Path(__file__).resolve().parents[1] / "routes" / "revolution_solaire_module.py"
spec = importlib.util.spec_from_file_location("rs_vente_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def donnees_valides():
    return {
        "nom": "Test", "date_naissance": "1980-10-11", "heure_naissance": "06:38",
        "gender": "male",
        "lieu_naissance": "Chalon-sur-Saône", "lat": "46.78", "lon": "4.85",
        "tzid": "Europe/Paris", "annee_rs": "2014", "lieu_rs": "Paris",
        "lat_rs": "48.85", "lon_rs": "2.35", "tzid_rs": "Europe/Paris",
        "contexte_rs_json": json.dumps({"amour": "Question relationnelle"}),
    }


class VenteRevolutionSolaireTest(TestCase):
    def test_date_d_ouverture_est_verifiee_a_chaque_commande(self):
        app = Flask(__name__)
        produit = {"label": "Ma Révolution Solaire", "price_cents": 4200}
        with app.app_context(), patch.dict(PRODUCTS, {"revolution_solaire": produit}):
            with patch("services.analysis_orders.ventes_ouvertes", return_value=False):
                with self.assertRaises(BadRequest):
                    catalog_items([{"key": "revolution_solaire"}])
            with patch("services.analysis_orders.ventes_ouvertes", return_value=True):
                items, produits = catalog_items([{"key": "revolution_solaire"}])
        self.assertEqual(items[0]["price_cents"], 4200)
        self.assertEqual(produits, ["revolution_solaire"])

    def test_valide_annee_lieu_et_contexte(self):
        demande = module._demande_depuis_commande(donnees_valides())
        self.assertEqual(demande["annee"], 2014)
        self.assertEqual(demande["lieu_rs"]["tzid"], "Europe/Paris")
        self.assertEqual(demande["contexte_client"]["amour"], "Question relationnelle")
        self.assertEqual(demande["personne"]["genre"], "male")
        for erreur in (
            {"annee_rs": "1899"}, {"tzid_rs": "Invalid/Zone"},
            {"contexte_rs_json": json.dumps({"amour": "x" * 301})},
        ):
            with self.subTest(erreur=erreur), self.assertRaises(ValueError):
                module._demande_depuis_commande({**donnees_valides(), **erreur})

    def test_genere_pdf_prive_puis_url_s3(self):
        app = Flask(__name__)
        with app.app_context(), \
                patch.object(module, "generer_rapport_revolution_solaire", return_value=SimpleNamespace(html="<body><h1>RS</h1><p>Lecture annuelle</p></body>")) as genere, \
                patch.object(module, "private_pdf_path", return_value="/tmp/rs-test.pdf"), \
                patch.object(module, "html_to_pdf", return_value=True) as pdf, \
                patch.object(module, "upload_client_pdf", return_value="https://example.test/rs.pdf") as upload:
            resultat = module.generer_revolution_solaire_pdf_s3(donnees_valides())
        self.assertEqual(resultat["pdf_url"], "https://example.test/rs.pdf")
        self.assertIn("Lecture annuelle", resultat["rapport_html"])
        self.assertEqual(genere.call_args.kwargs["annee"], 2014)
        html_pdf = pdf.call_args.args[0]
        self.assertIn('data:image/webp;base64,', html_pdf)
        self.assertIn('Révolution Solaire - Test', html_pdf)
        self.assertIn('Lecture annuelle', html_pdf)
        self.assertEqual(upload.call_args.kwargs["key_prefix"], "revolution_solaire")

    def test_pas_de_livraison_si_pdf_echoue(self):
        app = Flask(__name__)
        with app.app_context(), \
                patch.object(module, "generer_rapport_revolution_solaire", return_value=SimpleNamespace(html="<body><h1>RS</h1><p>Lecture annuelle</p></body>")), \
                patch.object(module, "private_pdf_path", return_value="/tmp/rs-test.pdf"), \
                patch.object(module, "html_to_pdf", return_value=False), \
                patch.object(module, "upload_client_pdf") as upload:
            with self.assertRaises(RuntimeError):
                module.generer_revolution_solaire_pdf_s3(donnees_valides())
        upload.assert_not_called()

    def test_relance_le_rapport_puis_pdf_et_stockage_sans_regenerer_le_rapport(self):
        app = Flask(__name__)
        rapport = SimpleNamespace(html="<body><h1>RS</h1><p>Lecture annuelle</p></body>")
        with app.app_context(), \
                patch.object(module, "generer_rapport_revolution_solaire",
                             side_effect=[RuntimeError("Claude temporairement indisponible"), rapport]) as genere, \
                patch.object(module, "private_pdf_path", return_value="/tmp/rs-test.pdf"), \
                patch.object(module, "html_to_pdf", side_effect=[False, True]) as pdf, \
                patch.object(module, "upload_client_pdf",
                             side_effect=[RuntimeError("S3 indisponible"), "https://example.test/rs.pdf"]) as upload, \
                patch("utils.revolution_solaire.relances.sleep", return_value=None):
            resultat = module.generer_revolution_solaire_pdf_s3(donnees_valides())
        self.assertEqual(resultat["pdf_url"], "https://example.test/rs.pdf")
        self.assertEqual(genere.call_count, 2)
        self.assertEqual(
            genere.call_args_list[0].kwargs["stockage_dir"],
            genere.call_args_list[1].kwargs["stockage_dir"],
        )
        self.assertEqual(pdf.call_count, 2)
        self.assertEqual(upload.call_count, 2)

    def test_relance_worker_retrouve_les_archives_de_la_commande(self):
        app = Flask(__name__)
        rapport = SimpleNamespace(html="<body><h1>RS</h1><p>Lecture annuelle</p></body>")
        with app.app_context(), \
                patch.object(module, "generer_rapport_revolution_solaire", return_value=rapport) as genere, \
                patch.object(module, "private_pdf_path", return_value="/tmp/rs-test.pdf"), \
                patch.object(module, "html_to_pdf", return_value=True), \
                patch.object(module, "upload_client_pdf", side_effect=[
                    RuntimeError("S3 indisponible"), RuntimeError("S3 indisponible"),
                    RuntimeError("S3 indisponible"), "https://example.test/rs.pdf",
                ]), \
                patch("utils.revolution_solaire.relances.sleep", return_value=None):
            with self.assertRaises(RuntimeError):
                module.generer_revolution_solaire_pdf_s3(
                    donnees_valides(), commande_id="commande-payee-123",
                )
            module.generer_revolution_solaire_pdf_s3(
                donnees_valides(), commande_id="commande-payee-123",
            )
        archives = [appel.kwargs["stockage_dir"] for appel in genere.call_args_list]
        self.assertEqual(archives, [archives[0], archives[0]])
