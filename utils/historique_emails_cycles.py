"""Contexte compact des emails déjà envoyés à un profil abonné."""

from __future__ import annotations

import json

from models.espace_personnel import EmailCycleAbonnement, ProfilAstral
from extensions import db
from utils.confidentialite_journal_mails import lire_choix_journal_mails


def contexte_historique_emails(profil_id: int, *, limite: int = 6) -> dict:
    profil = db.session.get(ProfilAstral, profil_id)
    if profil is None or not lire_choix_journal_mails(profil.utilisateur_id)["autorise"]:
        return {"nombre_emails_recents": 0, "emails_recents": []}
    emails = (
        EmailCycleAbonnement.query
        .filter(
            EmailCycleAbonnement.profil_id == profil_id,
            EmailCycleAbonnement.statut.in_(("genere", "envoye")),
        )
        .order_by(EmailCycleAbonnement.date_envoi.desc(), EmailCycleAbonnement.date_generation.desc())
        .limit(limite)
        .all()
    )
    resultats = []
    for email in emails:
        try:
            points = json.loads(email.points_abordes or "[]")
        except json.JSONDecodeError:
            points = []
        resultats.append({
            "type": email.type_email,
            "objet": email.objet,
            "points_abordes": points,
            "question_journal": email.question_journal,
        })
    return {"nombre_emails_recents": len(resultats), "emails_recents": resultats}
