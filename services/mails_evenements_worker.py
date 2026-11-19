"""Échéances des mails abonnés, sur le serveur existant, désactivées par défaut.

Un verrou PostgreSQL couvre tout un passage, y compris les appels externes.
Les statuts persistés du moteur empêchent de rejouer une tentative payante.
"""
import logging
import os
from threading import Event, Thread


CLE_VERROU = 202612010915
logger = logging.getLogger(__name__)


def passage_avec_verrou(app):
    from sqlalchemy import text
    from extensions import db
    from models.espace_personnel import MailEvenementAbonne
    from utils.automatisation_mails_evenements import automatique_actif, passer_automatisation

    if not automatique_actif():
        return {"statut": "desactive"}
    with app.app_context():
        moteur = db.session.get_bind(mapper=MailEvenementAbonne)
        if moteur.dialect.name != "postgresql":
            raise ValueError("Le programme automatique exige PostgreSQL. Aucun traitement lancé.")
        try:
            with moteur.connect() as verrou:
                acquis = verrou.execute(text("SELECT pg_try_advisory_lock(:cle)"), {"cle": CLE_VERROU}).scalar_one()
                verrou.commit()
                if not acquis:
                    return {"statut": "autre_worker_actif"}
                try:
                    return passer_automatisation()
                finally:
                    db.session.remove()
                    try:
                        verrou.execute(text("SELECT pg_advisory_unlock(:cle)"), {"cle": CLE_VERROU})
                        verrou.commit()
                    except Exception:
                        # Ne jamais remettre dans le pool une connexion encore verrouillée.
                        verrou.invalidate()
                        logger.exception("[MAILS AUTO] Connexion de verrou abandonnée")
        finally:
            db.session.remove()


def demarrer_mails_evenements(app):
    """Ne démarre qu'après activation explicite sur Railway ; aucun test local implicite."""
    from utils.automatisation_mails_evenements import automatique_actif

    if app.extensions.get("mails_evenements_worker"):
        return False
    if not os.getenv("RAILWAY_ENVIRONMENT_ID") or not automatique_actif():
        app.logger.info("[MAILS AUTO] Désactivés ; aucune génération ni aucun envoi au démarrage")
        return False
    try:
        intervalle = max(30, min(300, int(os.getenv("MAILS_EVENEMENTS_INTERVALLE_SECONDES", "60"))))
    except ValueError:
        intervalle = 60
    arret = Event()

    def boucle():
        dernier_statut = None
        while not arret.is_set() and automatique_actif():
            try:
                resultat = passage_avec_verrou(app)
                statut = resultat.get("statut")
                if statut != dernier_statut or resultat.get("traitements") or resultat.get("planifies"):
                    app.logger.info("[MAILS AUTO] %s", resultat)
                dernier_statut = statut
                if statut == "beta_terminee":
                    break
            except Exception:
                app.logger.exception("[MAILS AUTO] Passage interrompu ; les tentatives engagées ne sont pas relancées")
            arret.wait(intervalle)

    thread = Thread(target=boucle, name="mails-evenements-abonnes", daemon=True)
    app.extensions["mails_evenements_worker"] = {"thread": thread, "arret": arret}
    app.logger.info("[MAILS AUTO] Programme démarré ; échéances vérifiées toutes les %s secondes", intervalle)
    thread.start()
    return True
