"""Liens vers les mails envoyés des événements du calendrier, en lecture seule."""
from datetime import datetime, timedelta, timezone

from flask import url_for
from sqlalchemy import inspect, select

from extensions import db
from models.espace_personnel import MailEvenementAbonne

NATURES = {"rl", "nouvelle_lune", "pleine_lune"}
TOLERANCE = timedelta(seconds=120)


def _utc(instant):
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def relier_mails_envoyes(evenements, utilisateur_id):
    """Associe la nature et l’instant de l’événement, jamais sa date d’envoi.

    La tolérance de deux minutes absorbe les écarts de recherche numérique des
    éphémérides. Aucun rapprochement au seul jour, ni aucune génération/envoi.
    La route d’archive vérifie à nouveau le propriétaire et le statut envoyé.
    """
    cibles = []
    for evenement in evenements:
        if evenement.get("nature") not in NATURES:
            continue
        evenement.pop("mail_url", None)
        try:
            instant = datetime.fromisoformat(evenement["date"])
            if instant.tzinfo is None:
                continue
            cibles.append((evenement, _utc(instant)))
        except (KeyError, TypeError, ValueError):
            continue
    if not cibles or not inspect(db.session.get_bind(mapper=MailEvenementAbonne)).has_table("mails_evenements_abonnes"):
        return
    # Seulement les identifiants et les instants : pas de prompt ni de corps de mail.
    mails = db.session.execute(select(MailEvenementAbonne.id, MailEvenementAbonne.nature,
        MailEvenementAbonne.instant_evenement).where(
        MailEvenementAbonne.utilisateur_id == utilisateur_id,
        MailEvenementAbonne.statut == "envoye",
        MailEvenementAbonne.nature.in_(NATURES),
        MailEvenementAbonne.instant_evenement >= min(instant for _, instant in cibles) - TOLERANCE,
        MailEvenementAbonne.instant_evenement <= max(instant for _, instant in cibles) + TOLERANCE,
    ).order_by(MailEvenementAbonne.date_envoi.desc(), MailEvenementAbonne.id.desc())).all()
    for evenement, instant in cibles:
        for mail_id, nature, instant_mail in mails:
            if nature == evenement["nature"] and abs(_utc(instant_mail) - instant) <= TOLERANCE:
                evenement["mail_url"] = url_for("abonnement_client.lire_mail", mail_id=mail_id)
                break
