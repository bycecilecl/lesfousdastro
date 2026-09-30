"""L'import des archives conserve les PDF et isole les comptes personnels."""

import base64
from datetime import date, time
import hashlib
import importlib.util
from pathlib import Path
import unittest

from flask import Flask

from extensions import db
from models.espace_personnel import (
    AnalysePersonnelle, FichierAnalyse, MecanismeExploration, ProfilAstral,
    UtilisateurEspace,
)
from utils.import_espace_labo import TABLES, importer_archives


spec = importlib.util.spec_from_file_location(
    "espace_archives_under_test",
    Path(__file__).resolve().parents[1] / "routes" / "espace_personnel.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestArchivesEspace(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
        )
        self.app.secret_key = "test-archives"
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.url_build_error_handlers.append(
            lambda error, endpoint, values: "/" if not endpoint.startswith("espace_personnel.") else None
        )
        db.init_app(self.app)
        self.app.register_blueprint(module.espace_personnel_bp)
        with self.app.app_context():
            db.create_all()
            self.comptes = []
            for prenom, email in (("Cécile", "cecile@example.com"), ("Guillaume", "guillaume@example.com")):
                utilisateur = UtilisateurEspace(prenom=prenom, email=email)
                db.session.add(utilisateur)
                db.session.flush()
                profil = ProfilAstral(
                    utilisateur_id=utilisateur.id, prenom=prenom,
                    date_naissance=date(1980, 10, 11), heure_naissance=time(6, 38),
                    ville_naissance="Paris", fuseau_horaire="Europe/Paris",
                )
                db.session.add(profil)
                db.session.flush()
                self.comptes.append((utilisateur.id, profil.id, email))
            db.session.commit()
        self.client = self.app.test_client()

    def _paquet(self):
        contenu = b"%PDF-1.4\n%%EOF\n"
        donnees = {nom: [] for nom in TABLES}
        donnees["analyses_personnelles"] = [{
            "id": 42, "utilisateur_id": 999, "type_analyse": "point_astral",
            "titre": "Mon point astral", "statut": "terminee",
            "chemin_resultat": "rapport.pdf",
        }]
        donnees["mecanismes_exploration"] = [{
            "id": 57, "analyse_id": 42, "titre": "Un mécanisme à explorer",
            "hypothese": "Une hypothèse personnelle", "ressenti": "a_observer",
            "statut": "a_explorer",
        }]
        return {
            "version": 1, "email": self.comptes[0][2], "donnees": donnees,
            "pdfs": {"42": {
                "nom": "rapport.pdf", "sha256": hashlib.sha256(contenu).hexdigest(),
                "base64": base64.b64encode(contenu).decode("ascii"),
            }},
        }

    def test_import_et_lecture_du_pdf_reserves_au_proprietaire(self):
        utilisateur_id, profil_id, email = self.comptes[0]
        with self.app.app_context():
            bilan = importer_archives(
                self._paquet(), email=email,
                utilisateur_id=utilisateur_id, profil_id=profil_id,
            )
            db.session.commit()
            self.assertEqual(bilan["analyses"], 1)
            analyse = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur_id).one()
            self.assertEqual(FichierAnalyse.query.filter_by(analyse_id=analyse.id).count(), 1)
            analyse_id = analyse.id
        with self.client.session_transaction() as session:
            session["utilisateur_espace_id"] = utilisateur_id
        reponse = self.client.get(f"/mon-espace/mes-analyses/{analyse_id}/lire")
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data.startswith(b"%PDF-"))
        with self.client.session_transaction() as session:
            session["utilisateur_espace_id"] = self.comptes[1][0]
        self.assertEqual(
            self.client.get(f"/mon-espace/mes-analyses/{analyse_id}/lire").status_code,
            404,
        )

    def test_export_d_un_autre_compte_est_refuse(self):
        utilisateur_id, profil_id, email = self.comptes[1]
        with self.app.app_context():
            with self.assertRaises(ValueError):
                importer_archives(
                    self._paquet(), email=email,
                    utilisateur_id=utilisateur_id, profil_id=profil_id,
                )
            self.assertEqual(AnalysePersonnelle.query.count(), 0)

    def test_mecanisme_prive_et_modification_protegee(self):
        utilisateur_id, profil_id, email = self.comptes[0]
        with self.app.app_context():
            importer_archives(
                self._paquet(), email=email,
                utilisateur_id=utilisateur_id, profil_id=profil_id,
            )
            db.session.commit()
            mecanisme_id = MecanismeExploration.query.one().id
        with self.client.session_transaction() as session:
            session["utilisateur_espace_id"] = utilisateur_id
        self.assertEqual(self.client.get(f"/mon-espace/mecanismes/{mecanisme_id}").status_code, 200)
        self.assertEqual(
            self.client.post(
                f"/mon-espace/mecanismes/{mecanisme_id}",
                data={"titre": "Titre modifié", "hypothese": "Texte"},
            ).status_code,
            400,
        )
        with self.client.session_transaction() as session:
            session["utilisateur_espace_id"] = self.comptes[1][0]
        self.assertEqual(self.client.get(f"/mon-espace/mecanismes/{mecanisme_id}").status_code, 404)

    def test_pdf_modifie_annule_tout_l_import(self):
        paquet = self._paquet()
        paquet["pdfs"]["42"]["sha256"] = "0" * 64
        utilisateur_id, profil_id, email = self.comptes[0]
        with self.app.app_context():
            with self.assertRaises(ValueError):
                importer_archives(
                    paquet, email=email,
                    utilisateur_id=utilisateur_id, profil_id=profil_id,
                )
            db.session.rollback()
            self.assertEqual(AnalysePersonnelle.query.count(), 0)
            self.assertEqual(FichierAnalyse.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
