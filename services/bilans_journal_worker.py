"""Planification des bilans 30 jours, activée explicitement sur Railway seulement."""
from threading import Event, Thread

CLE_VERROU = 202611201130


def passage_avec_verrou(app):
    from sqlalchemy import text
    from extensions import db
    from models.espace_personnel import BilanJournal30Jours
    from utils.automatisation_bilans_journal import automatique_actif, passer_bilans
    if not automatique_actif():
        return {"statut": "desactive"}
    with app.app_context():
        try:
            moteur = db.session.get_bind(mapper=BilanJournal30Jours)
            if moteur.dialect.name != "postgresql":
                return {"statut": "hors_production"}
            with moteur.connect() as verrou:
                acquis = verrou.execute(text("SELECT pg_try_advisory_lock(:cle)"), {"cle": CLE_VERROU}).scalar_one()
                verrou.commit()
                if not acquis:
                    return {"statut": "autre_worker_actif"}
                try:
                    return passer_bilans()
                finally:
                    db.session.remove()
                    try:
                        verrou.execute(text("SELECT pg_advisory_unlock(:cle)"), {"cle": CLE_VERROU})
                        verrou.commit()
                    except Exception:
                        verrou.invalidate()
        finally:
            db.session.remove()


def demarrer_bilans_journal(app):
    from utils.automatisation_bilans_journal import automatique_actif
    if app.extensions.get("bilans_journal_worker") or not automatique_actif():
        return False
    arret = Event()

    def boucle():
        while not arret.is_set() and automatique_actif():
            try:
                resultat = passage_avec_verrou(app)
                if resultat.get("generes") or resultat.get("sans_appel"):
                    app.logger.info("[BILANS JOURNAL] %s", resultat)
            except Exception:
                app.logger.exception("[BILANS JOURNAL] Passage interrompu ; aucune tentative engagée rejouée")
            arret.wait(600)

    thread = Thread(target=boucle, name="bilans-journal-30-jours", daemon=True)
    app.extensions["bilans_journal_worker"] = {"thread": thread, "arret": arret}
    thread.start()
    return True
