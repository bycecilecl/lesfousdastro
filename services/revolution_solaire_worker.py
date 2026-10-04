"""Reprend les commandes de RS payées après une panne ou un redémarrage."""

from datetime import datetime, timedelta, timezone
from threading import Thread
from time import sleep, time

from extensions import db
from models.analysis_orders import AnalysisJob, AnalysisOrder
from services.analysis_orders import environment_matches


def _date_utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def reprendre_commandes_rs(app):
    """Une tentative au plus par commande ; run_job arbitre entre workers."""
    limite = datetime.now(timezone.utc) - timedelta(minutes=45)
    jobs = AnalysisJob.query.filter_by(product="revolution_solaire").filter(
        AnalysisJob.status.in_(("pending", "running", "complete"))
    ).all()
    for job in jobs:
        commande = db.session.get(AnalysisOrder, job.order_id)
        if not commande or commande.status != "paid" or not environment_matches(commande):
            continue
        if job.status == "running" and _date_utc(job.started_at) and _date_utc(job.started_at) < limite:
            AnalysisJob.query.filter_by(id=job.id, status="running").update({"status": "pending"})
            db.session.commit()
            job.status = "pending"

        livraison = AnalysisJob.query.filter_by(
            order_id=commande.id, product="__delivery"
        ).one_or_none()
        if livraison and livraison.status == "running" and _date_utc(livraison.started_at) and _date_utc(livraison.started_at) < limite:
            AnalysisJob.query.filter_by(id=livraison.id, status="running").update({"status": "pending"})
            db.session.commit()
            livraison.status = "pending"

        if job.status == "pending":
            reprise = job.result if isinstance(job.result, dict) else {}
            if reprise.get("retry_after", 0) > time():
                continue
        elif job.status != "complete" or not livraison or livraison.status != "pending":
            continue

        # Import tardif : checkout importe lui-même le service de commandes.
        from routes.checkout import generer_pack_et_envoyer_email

        app.logger.info("Reprise automatique RS : commande %s", commande.id)
        generer_pack_et_envoyer_email(
            ["revolution_solaire"], dict(commande.beneficiary),
            {"secure_order_id": commande.id, "fallback_urls": {}},
        )


def demarrer_relances_rs(app):
    def boucle():
        while True:
            try:
                with app.app_context():
                    reprendre_commandes_rs(app)
                    db.session.remove()
            except Exception:
                app.logger.exception("Reprise automatique RS interrompue ; nouvel essai dans une minute")
            sleep(60)

    Thread(target=boucle, name="relances-rs-payees", daemon=True).start()
