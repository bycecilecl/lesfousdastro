"""Connexion réelle à l'espace : compte persistant et lien à usage unique."""

import importlib.util
import io
import json
from datetime import date, time, timedelta
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

from flask import Flask

from extensions import db
from models.espace_personnel import (
    AbonnementEspace, CycleLunaire, EmailCycleAbonnement,
    LienConnexionEspace, ProfilAstral, UtilisateurEspace, utcnow,
)


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

    def _connecter_compte(self, email="cecile@example.com"):
        with self.app.app_context():
            utilisateur = UtilisateurEspace(prenom="Cécile", email=email)
            db.session.add(utilisateur)
            db.session.commit()
            utilisateur_id = utilisateur.id
        with self.client.session_transaction() as donnees:
            donnees["utilisateur_espace_id"] = utilisateur_id
            donnees["espace_profil_csrf"] = "jeton-de-test"
        return utilisateur_id

    def _donnees_profil(self):
        return {
            "prenom": "Cécile",
            "date_naissance": "1980-10-11",
            "heure_naissance": "06:38",
            "ville_naissance": "Chalon-sur-Saône, France",
            "latitude": "46.7806",
            "longitude": "4.8528",
            "fuseau_horaire": "Europe/Paris",
            "profil_csrf": "jeton-de-test",
        }

    def _fichier_import(self, email="cecile@example.com"):
        profil = self._donnees_profil()
        profil.pop("profil_csrf")
        profil["theme_natal"] = json.dumps({"planetes": {"Lune": {}}, "maisons": {"1": {}}})
        profil["situation_travail"] = "Projet en cours"
        contenu = json.dumps({
            "version": 2, "email": email, "profil": profil,
            "abonnement": {"formule": "accompagnement_astral", "statut": "test"},
        }).encode()
        return io.BytesIO(contenu)

    def _compte_avec_mail(self):
        utilisateur_id = self._connecter_compte("cecilecl@gmail.com")
        with self.app.app_context():
            db.session.add(ProfilAstral(
                utilisateur_id=utilisateur_id, prenom="Cécile",
                date_naissance=date(1980, 10, 11), heure_naissance=time(6, 38),
                ville_naissance="Chalon-sur-Saône", fuseau_horaire="Europe/Paris",
                latitude=46.7806, longitude=4.8528,
                theme_natal=json.dumps({"planetes": {"Lune": {}}, "maisons": {"1": {}}}),
            ))
            db.session.add(AbonnementEspace(
                utilisateur_id=utilisateur_id, formule="accompagnement_astral", statut="test",
            ))
            db.session.commit()
        return utilisateur_id

    def _fichier_brouillon(self, email="cecilecl@gmail.com"):
        contenu = {
            "version": 1, "email": email,
            "cycle": {
                "cle_cycle": "2026-10-12", "debut_cycle_utc": "2026-10-12T03:47:00+00:00",
                "fin_cycle_utc": "2026-11-08T11:00:00+00:00", "ville": "Solliès-Pont",
                "fuseau_horaire": "Europe/Paris", "latitude": 43.182, "longitude": 6.037,
                "theme_technique": json.dumps({"planetes": {"Lune": {}}}), "statut": "technique",
            },
            "brouillon": {
                "type_email": "boussole_cycle", "objet": "Ton mois d'octobre",
                "contenu_texte": "Bonjour Cécile, voici ton mois.",
                "contenu_html": "<p>Bonjour Cécile, voici ton mois.</p>",
                "date_generation": "2026-09-18T06:18:53+00:00",
            },
        }
        return io.BytesIO(json.dumps(contenu).encode())

    def _importer_brouillon_test(self):
        return self.client.post(
            "/mon-espace/emails-cycle/importer",
            data={"profil_csrf": "jeton-de-test", "brouillon_import": (self._fichier_brouillon(), "mail.json")},
            content_type="multipart/form-data",
        )

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

    def test_profil_exige_une_connexion(self):
        reponse = self.client.get("/mon-espace/profil")
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse.headers["Location"], "/mon-espace/connexion")

    def test_profil_calcule_et_enregistre_un_theme_prive(self):
        utilisateur_id = self._connecter_compte()
        with patch.object(module, "calcul_theme", return_value={"planetes": {"Soleil": "Balance"}}) as calcul:
            reponse = self.client.post("/mon-espace/profil", data=self._donnees_profil())
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse.headers["Location"], "/mon-espace/profil")
        calcul.assert_called_once()
        with self.app.app_context():
            profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur_id).one()
            self.assertEqual(profil.ville_naissance, "Chalon-sur-Saône, France")
            self.assertIn('"Soleil": "Balance"', profil.theme_natal)

    def test_recalcul_ne_supprime_pas_la_situation_ni_ne_cree_de_doublon(self):
        utilisateur_id = self._connecter_compte()
        with patch.object(module, "calcul_theme", return_value={"planetes": {}}):
            self.client.post("/mon-espace/profil", data=self._donnees_profil())
            with self.app.app_context():
                profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur_id).one()
                profil.situation_travail = "Projet en cours"
                db.session.commit()
                ancien_id = profil.id
            donnees = self._donnees_profil()
            donnees["ville_naissance"] = "Paris, France"
            self.client.post("/mon-espace/profil", data=donnees)
        with self.app.app_context():
            profils = ProfilAstral.query.filter_by(utilisateur_id=utilisateur_id).all()
            self.assertEqual(len(profils), 1)
            self.assertEqual(profils[0].id, ancien_id)
            self.assertEqual(profils[0].situation_travail, "Projet en cours")
            self.assertEqual(profils[0].ville_naissance, "Paris, France")

    def test_coordonnees_invalides_ne_declenchent_pas_le_calcul(self):
        self._connecter_compte()
        donnees = self._donnees_profil()
        donnees["latitude"] = "nan"
        with patch.object(module, "calcul_theme") as calcul:
            reponse = self.client.post("/mon-espace/profil", data=donnees)
        self.assertEqual(reponse.status_code, 400)
        calcul.assert_not_called()
        with self.app.app_context():
            self.assertEqual(ProfilAstral.query.count(), 0)

    def test_modification_du_profil_refusee_sans_jeton_formulaire(self):
        self._connecter_compte()
        donnees = self._donnees_profil()
        donnees.pop("profil_csrf")
        with patch.object(module, "calcul_theme") as calcul:
            reponse = self.client.post("/mon-espace/profil", data=donnees)
        self.assertEqual(reponse.status_code, 400)
        calcul.assert_not_called()

    def test_un_compte_ne_voit_pas_le_profil_de_l_autre(self):
        premier_id = self._connecter_compte()
        with patch.object(module, "calcul_theme", return_value={"planetes": {}}):
            self.client.post("/mon-espace/profil", data=self._donnees_profil())
        second_id = self._connecter_compte("guillaume@example.com")
        reponse = self.client.get("/mon-espace/profil")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("'profil': None", reponse.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNotNone(ProfilAstral.query.filter_by(utilisateur_id=premier_id).first())
            self.assertIsNone(ProfilAstral.query.filter_by(utilisateur_id=second_id).first())

    def test_import_du_labo_associe_le_profil_au_compte_connecte(self):
        utilisateur_id = self._connecter_compte("cecilecl@gmail.com")
        reponse = self.client.post(
            "/mon-espace/profil/importer",
            data={"profil_csrf": "jeton-de-test", "profil_import": (self._fichier_import("cecilecl@gmail.com"), "profil.json")},
            content_type="multipart/form-data",
        )
        self.assertEqual(reponse.status_code, 302)
        with self.app.app_context():
            profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur_id).one()
            self.assertEqual(profil.situation_travail, "Projet en cours")
            self.assertIn("Lune", profil.theme_natal)
            abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur_id).one()
            self.assertEqual((abonnement.formule, abonnement.statut), ("accompagnement_astral", "test"))

    def test_import_refuse_le_fichier_d_un_autre_compte(self):
        self._connecter_compte("cecilecl@gmail.com")
        reponse = self.client.post(
            "/mon-espace/profil/importer",
            data={"profil_csrf": "jeton-de-test", "profil_import": (self._fichier_import("cecilecl.cyp@gmail.com"), "profil.json")},
            content_type="multipart/form-data",
        )
        self.assertEqual(reponse.status_code, 400)
        with self.app.app_context():
            self.assertEqual(ProfilAstral.query.count(), 0)

    def test_import_ne_remplace_pas_un_profil_existant(self):
        utilisateur_id = self._connecter_compte("cecilecl@gmail.com")
        with self.app.app_context():
            db.session.add(ProfilAstral(
                utilisateur_id=utilisateur_id, prenom="Cécile",
                date_naissance=date(1980, 10, 11), heure_naissance=time(6, 38),
                ville_naissance="Paris", fuseau_horaire="Europe/Paris",
            ))
            db.session.commit()
        reponse = self.client.post(
            "/mon-espace/profil/importer",
            data={"profil_csrf": "jeton-de-test", "profil_import": (self._fichier_import("cecilecl@gmail.com"), "profil.json")},
            content_type="multipart/form-data",
        )
        self.assertEqual(reponse.status_code, 302)
        with self.app.app_context():
            self.assertEqual(ProfilAstral.query.count(), 1)
            self.assertEqual(ProfilAstral.query.one().ville_naissance, "Paris")

    def test_import_du_brouillon_n_envoie_rien_et_refuse_le_doublon(self):
        self._compte_avec_mail()
        with patch.object(module, "envoyer_email_avec_analyse") as envoyer:
            premier = self._importer_brouillon_test()
            second = self._importer_brouillon_test()
        self.assertEqual(premier.status_code, 302)
        self.assertEqual(second.status_code, 302)
        envoyer.assert_not_called()
        with self.app.app_context():
            self.assertEqual(CycleLunaire.query.count(), 1)
            self.assertEqual(EmailCycleAbonnement.query.count(), 1)
            self.assertEqual(EmailCycleAbonnement.query.one().statut, "brouillon")

    def test_envoi_manuel_n_est_possible_qu_une_fois(self):
        self._compte_avec_mail()
        self._importer_brouillon_test()
        with self.app.app_context():
            email_id = EmailCycleAbonnement.query.one().id
        with patch.object(module, "envoyer_email_avec_analyse", return_value=True) as envoyer:
            premier = self.client.post(
                f"/mon-espace/emails-cycle/{email_id}/envoyer",
                data={"profil_csrf": "jeton-de-test"},
            )
            second = self.client.post(
                f"/mon-espace/emails-cycle/{email_id}/envoyer",
                data={"profil_csrf": "jeton-de-test"},
            )
        self.assertEqual((premier.status_code, second.status_code), (302, 302))
        envoyer.assert_called_once()
        self.assertEqual(envoyer.call_args.kwargs["destinataire"], "cecilecl@gmail.com")
        with self.app.app_context():
            email = EmailCycleAbonnement.query.one()
            self.assertEqual(email.statut, "envoye")
            self.assertIsNotNone(email.date_envoi)

    def test_echec_envoi_reste_incertain_sans_relance_automatique(self):
        self._compte_avec_mail()
        self._importer_brouillon_test()
        with self.app.app_context():
            email_id = EmailCycleAbonnement.query.one().id
        with patch.object(module, "envoyer_email_avec_analyse", return_value=False) as envoyer:
            self.client.post(
                f"/mon-espace/emails-cycle/{email_id}/envoyer",
                data={"profil_csrf": "jeton-de-test"},
            )
            self.client.post(
                f"/mon-espace/emails-cycle/{email_id}/envoyer",
                data={"profil_csrf": "jeton-de-test"},
            )
        envoyer.assert_called_once()
        with self.app.app_context():
            self.assertEqual(EmailCycleAbonnement.query.one().statut, "envoi_incertain")

    def test_un_autre_compte_ne_peut_pas_lire_le_brouillon(self):
        self._compte_avec_mail()
        self._importer_brouillon_test()
        with self.app.app_context():
            email_id = EmailCycleAbonnement.query.one().id
        self._connecter_compte("cecilecl.cyp@gmail.com")
        self.assertEqual(self.client.get(f"/mon-espace/emails-cycle/{email_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
