"""Connexion à usage unique et liste des premières adresses invitées."""

from datetime import timedelta, timezone
import hashlib
import os
import secrets

from flask import url_for
from sqlalchemy import func, update

from extensions import db
from models.espace_personnel import AbonnementEspace, LienConnexionEspace, UtilisateurEspace, utcnow


DUREE_LIEN_MINUTES = 20
DELAI_NOUVEAU_LIEN_SECONDES = 60


def normaliser_email(email):
    return (email or "").strip().lower()


def email_invite(email):
    if os.getenv("ESPACE_INSCRIPTION_OUVERTE", "false").lower() in {"1", "true", "yes"}:
        return True
    adresses = os.getenv(
        "ESPACE_INVITE_EMAILS", "cecilecl@gmail.com,cecilecl.cyp@gmail.com"
    )
    invites = {normaliser_email(adresse) for adresse in adresses.split(",")}
    return normaliser_email(email) in invites


def activer_accompagnement_beta(utilisateur):
    """Accorde trois mois de bêta aux seules adresses explicitement désignées."""
    adresses = os.getenv("ESPACE_BETA_EMAILS", "")
    invites = {normaliser_email(adresse) for adresse in adresses.split(",") if adresse.strip()}
    if normaliser_email(utilisateur.email) not in invites:
        return False
    if AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first() is not None:
        return False
    debut = utcnow()
    db.session.add(AbonnementEspace(
        utilisateur_id=utilisateur.id,
        formule="beta_accompagnement",
        statut="test",
        date_debut=debut,
        date_fin=debut + timedelta(days=90),
        source="invitation_beta",
    ))
    db.session.commit()
    return True


def trouver_ou_creer_utilisateur(email, prenom=""):
    email = normaliser_email(email)
    if not email or "@" not in email or len(email) > 255:
        raise ValueError("Adresse e-mail invalide.")
    utilisateur = UtilisateurEspace.query.filter(func.lower(UtilisateurEspace.email) == email).first()
    if utilisateur is None:
        utilisateur = UtilisateurEspace(
            email=email,
            prenom=(prenom or email.split("@", 1)[0]).strip()[:100] or "Mon espace",
            actif=1,
        )
        db.session.add(utilisateur)
        db.session.flush()
    return utilisateur


def lien_recent(utilisateur_id):
    dernier = (
        LienConnexionEspace.query
        .filter_by(utilisateur_id=utilisateur_id)
        .order_by(LienConnexionEspace.date_creation.desc())
        .first()
    )
    if dernier is None:
        return False
    date_creation = dernier.date_creation
    if date_creation.tzinfo is None:
        date_creation = date_creation.replace(tzinfo=timezone.utc)
    return (utcnow() - date_creation).total_seconds() < DELAI_NOUVEAU_LIEN_SECONDES


def creer_lien_connexion(utilisateur):
    """Conserve seulement l'empreinte du jeton et invalide les anciens liens."""
    maintenant = utcnow()
    for ancien in LienConnexionEspace.query.filter_by(utilisateur_id=utilisateur.id, utilise_le=None):
        ancien.utilise_le = maintenant
    jeton = secrets.token_urlsafe(32)
    db.session.add(LienConnexionEspace(
        utilisateur_id=utilisateur.id,
        empreinte_jeton=hashlib.sha256(jeton.encode()).hexdigest(),
        expire_le=maintenant + timedelta(minutes=DUREE_LIEN_MINUTES),
    ))
    db.session.commit()
    origine = os.getenv("ESPACE_PUBLIC_ORIGIN", "https://lesfousdastro.fr").rstrip("/")
    chemin = url_for("espace_personnel.valider_connexion", jeton=jeton)
    return f"{origine}{chemin}"


def consommer_lien_connexion(jeton):
    """La mise à jour conditionnelle empêche de consommer deux fois le même lien."""
    empreinte = hashlib.sha256((jeton or "").encode()).hexdigest()
    maintenant = utcnow()
    resultat = db.session.execute(
        update(LienConnexionEspace)
        .where(
            LienConnexionEspace.empreinte_jeton == empreinte,
            LienConnexionEspace.utilise_le.is_(None),
            LienConnexionEspace.expire_le > maintenant,
        )
        .values(utilise_le=maintenant)
    )
    if resultat.rowcount != 1:
        db.session.rollback()
        return None
    lien = LienConnexionEspace.query.filter_by(empreinte_jeton=empreinte).first()
    utilisateur = db.session.get(UtilisateurEspace, lien.utilisateur_id)
    db.session.commit()
    return utilisateur if utilisateur and utilisateur.actif == 1 else None
