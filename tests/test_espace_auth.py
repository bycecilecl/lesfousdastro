"""Connexion réelle à l'espace : compte persistant et lien à usage unique."""

import importlib.util
from datetime import timedelta
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

from flask import Flask

from extensions import db
from models.espace_personnel import LienConnexionEspace, UtilisateurEspace, utcnow


spec = importlib.util.spec_from_file_location(
    "espace_auth_under_test",
    Path(__file__).resolve().parents[1] / "routes" / "espace_personnel.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestEspaceAuth(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "cle-de-test"
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        db.init_app(app)
        app.register_blueprint(module.espace_personnel_bp)
        with app.app_context():
            db.create_all()
        self.app = app
        self.client = app.test_client()
        self.env = patch.dict(
            "os.environ",
            {"ESPACE_INVITE_EMAILS": "cecile@example.com,guillaume@example.com"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.render = patch.object(
            module,
            "render_template",
            side_effect=lambda template, **context: f"{template}|{context}",
        )
        self.render.start()
        self.addCleanup(self.render.stop)
        self.turnstile = patch.object(module, "verifier_turnstile", return_value=True)
        self.turnstile.start()
        self.addCleanup(self.turnstile.stop)

    def _demander_lien(self):
        with patch.object(module, "envoyer_email_avec_analyse", return_value=True) as envoyer:
            reponse = self.client.post(
                "/mon-espace/connexion",
                data={"email": "CECILE@example.com", "prenom": "Cécile"},
            )
        texte = envoyer.call_args.kwargs["contenu_txt"]
        lien = re.search(r"https?://[^\s]+", texte).group()
        self.assertEqual(urlparse(lien).netloc, "lesfousdastro.fr")
        return reponse, urlparse(lien).path

    def test_compte_et_lien_persistants_puis_connexion(self):
        reponse, chemin = self._demander_lien()
        self.assertEqual(reponse.status_code, 200)
        with self.app.app_context():
            self.assertEqual(UtilisateurEspace.query.count(), 1)
            self.assertEqual(LienConnexionEspace.query.count(), 1)
            self.assertEqual(UtilisateurEspace.query.first().prenom, "Cécile")
        self.assertEqual(self.client.get(chemin).status_code, 302)
        accueil = self.client.get("/mon-espace/")
        self.assertEqual(accueil.status_code, 200)
        self.assertIn(b"espace_personnel/accueil.html", accueil.data)
        self.client.post("/mon-espace/deconnexion")
        self.assertEqual(self.client.get("/mon-espace/").status_code, 302)

    def test_lien_a_usage_unique(self):
        _, chemin = self._demander_lien()
        premier = self.client.get(chemin)
        second = self.client.get(chemin)
        self.assertEqual(premier.headers["Location"], "/mon-espace/")
        self.assertEqual(second.headers["Location"], "/mon-espace/connexion")
        with self.app.app_context():
            self.assertIsNotNone(LienConnexionEspace.query.first().utilise_le)

    def test_lien_expire_refuse(self):
        _, chemin = self._demander_lien()
        with self.app.app_context():
            lien = LienConnexionEspace.query.first()
            lien.expire_le = utcnow() - timedelta(seconds=1)
            db.session.commit()
        reponse = self.client.get(chemin)
        self.assertEqual(reponse.headers["Location"], "/mon-espace/connexion")
        self.assertEqual(self.client.get("/mon-espace/").status_code, 302)

    def test_adresse_non_invitee_ne_cree_pas_de_compte(self):
        with patch.object(module, "envoyer_email_avec_analyse") as envoyer:
            reponse = self.client.post(
                "/mon-espace/connexion", data={"email": "autre@example.com"}
            )
        self.assertEqual(reponse.status_code, 200)
        envoyer.assert_not_called()
        with self.app.app_context():
            self.assertEqual(UtilisateurEspace.query.count(), 0)

    def test_une_minute_entre_deux_envois(self):
        self._demander_lien()
        with patch.object(module, "envoyer_email_avec_analyse") as envoyer:
            reponse = self.client.post(
                "/mon-espace/connexion", data={"email": "cecile@example.com"}
            )
        self.assertEqual(reponse.status_code, 429)
        envoyer.assert_not_called()

    def test_captcha_requis(self):
        with patch.object(module, "verifier_turnstile", return_value=False):
            reponse = self.client.post(
                "/mon-espace/connexion", data={"email": "cecile@example.com"}
            )
        self.assertEqual(reponse.status_code, 400)

    def test_echec_envoi_signale(self):
        with patch.object(module, "envoyer_email_avec_analyse", return_value=False):
            reponse = self.client.post(
                "/mon-espace/connexion", data={"email": "cecile@example.com"}
            )
        self.assertEqual(reponse.status_code, 503)


if __name__ == "__main__":
    unittest.main()
