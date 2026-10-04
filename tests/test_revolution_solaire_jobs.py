"""Relance persistante d'une Révolution solaire payée, sans fournisseur externe."""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from extensions import db
from models.analysis_orders import AnalysisJob, AnalysisOrder
from services.analysis_orders import JobBusy, run_job
from services.revolution_solaire_worker import reprendre_commandes_rs


class RelanceCommandePayeeTest(unittest.TestCase):
    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(self.temporaire.name) / "jobs.db"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.contexte = self.app.app_context()
        self.contexte.push()
        db.create_all()
        self.commande = AnalysisOrder(
            id="commande-rs-test", owner_hash="x" * 64, provider="stripe",
            status="paid", amount_cents=4200, currency="EUR", sandbox=False,
            items=[{"key": "revolution_solaire", "quantity": 1, "price_cents": 4200}],
            products=["revolution_solaire"],
            beneficiary={"nom": "Alice", "email": "alice@example.test"},
        )
        db.session.add_all([
            self.commande,
            AnalysisJob(order_id=self.commande.id, product="revolution_solaire"),
            AnalysisJob(order_id=self.commande.id, product="__delivery"),
        ])
        db.session.commit()
        self.environnement = patch.dict(os.environ, {
            "PAYMENTS_SANDBOX": "0", "APP_MAINTENANCE": "0",
        })
        self.environnement.start()

    def tearDown(self):
        self.environnement.stop()
        db.session.remove()
        db.drop_all()
        self.contexte.pop()
        self.temporaire.cleanup()

    def test_echec_reprogramme_puis_worker_livre_une_seule_fois(self):
        def panne(_infos):
            raise RuntimeError("Claude indisponible")

        with self.assertRaises(RuntimeError):
            run_job(self.commande.id, "revolution_solaire", panne)
        job = AnalysisJob.query.filter_by(
            order_id=self.commande.id, product="revolution_solaire"
        ).one()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.result["retry_count"], 1)
        with self.assertRaises(JobBusy):
            run_job(self.commande.id, "revolution_solaire", panne)

        job.result = {"retry_count": 1, "retry_after": 0}
        db.session.commit()
        traitements = []

        def traiter(_produits, _client, _pending):
            traitements.append(self.commande.id)
            run_job(self.commande.id, "revolution_solaire",
                    lambda _infos: {"pdf_url": "https://example.test/rs.pdf"})
            livraison = AnalysisJob.query.filter_by(
                order_id=self.commande.id, product="__delivery"
            ).one()
            livraison.status = "complete"
            db.session.commit()

        faux_checkout = types.ModuleType("routes.checkout")
        faux_checkout.generer_pack_et_envoyer_email = traiter
        with patch.dict(sys.modules, {"routes.checkout": faux_checkout}):
            reprendre_commandes_rs(self.app)
            reprendre_commandes_rs(self.app)

        self.assertEqual(traitements, [self.commande.id])
        self.assertEqual(job.status, "complete")


if __name__ == "__main__":
    unittest.main()
