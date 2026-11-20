"""Liste privée des adresses invitées à l’offre bêta, sans mail ni appel externe."""
import re

OFFRE_BETA = "accompagnement_decembre_2026"


def _email(valeur):
    return (valeur or "").strip().lower()


def stockage_invitations_pret():
    from sqlalchemy import inspect
    from extensions import db
    from models.espace_personnel import InvitationOffreBeta
    return inspect(db.session.get_bind(mapper=InvitationOffreBeta)).has_table("invitations_offre_beta")


def adresse_invitee_beta(email):
    """Relit la liste actuelle ; absence de stockage ou de liste = offre fermée."""
    from sqlalchemy import select
    from extensions import db
    from models.espace_personnel import InvitationOffreBeta
    if not email or not stockage_invitations_pret():
        return False
    return db.session.execute(select(InvitationOffreBeta.actif).where(
        InvitationOffreBeta.email == _email(email), InvitationOffreBeta.offre == OFFRE_BETA
    )).scalar_one_or_none() is True


def verifier_invitation_beta(utilisateur):
    if not utilisateur or not utilisateur.actif or not adresse_invitee_beta(utilisateur.email):
        raise ValueError("Cette offre bêta est réservée aux adresses invitées par Cécile. Connecte-toi avec l’adresse de ton invitation.")


def autoriser_adresses_beta(texte):
    """Valide toute la saisie avant modification. Ne crée ni compte ni abonnement."""
    from extensions import db
    from models.espace_personnel import InvitationOffreBeta
    if len(texte) > 60000:
        raise ValueError("La liste est trop longue : indique au maximum 200 adresses.")
    adresses = sorted({_email(e) for e in re.split(r"[\s,;]+", texte.strip()) if e})
    if not adresses or len(adresses) > 200 or any(len(e) > 255 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", e) for e in adresses):
        raise ValueError("Indique des adresses e-mail valides, séparées par des lignes, virgules ou points-virgules (200 maximum).")
    for email in adresses:
        invitation = db.session.get(InvitationOffreBeta, (email, OFFRE_BETA))
        if invitation is None:
            db.session.add(InvitationOffreBeta(email=email, offre=OFFRE_BETA, actif=True))
        else:
            invitation.actif = True
    return len(adresses)
