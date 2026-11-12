"""Choix actuel du membre pour ses notes dans les mails. Aucun appel IA."""
from copy import deepcopy
from datetime import timezone

from sqlalchemy import select

from extensions import db
from models.espace_personnel import UtilisateurEspace


def lire_choix_journal_mails(utilisateur_id):
    """Relit les colonnes en base, sans réutiliser un ancien objet de session."""
    ligne = db.session.execute(select(
        UtilisateurEspace.autoriser_journal_mails,
        UtilisateurEspace.journal_mails_choix_le,
    ).where(UtilisateurEspace.id == utilisateur_id)).first()
    date_choix = ligne[1] if ligne else None
    if date_choix is not None:
        date_choix = (date_choix.replace(tzinfo=timezone.utc) if date_choix.tzinfo is None
                      else date_choix.astimezone(timezone.utc))
    return {"autorise": bool(ligne and ligne[0]),
            "choix_le": date_choix.isoformat() if date_choix else None}


def journal_non_autorise():
    return {"statut": "utilisation_non_autorisee", "nombre_entrees_retenues": 0, "observations": []}


def filtrer_preparation_journal_mails(profil, preparation):
    """Applique le choix ACTUEL, y compris à une préparation ou un essai ancien.

    Les archives sont conservées. Les anciens mails peuvent contenir une
    reformulation des notes : ne pas les réinjecter dans le prompt en cas de refus.
    Le profil déclaré est distinct du journal et reste disponible.
    """
    copie = deepcopy(preparation)
    choix = lire_choix_journal_mails(profil.utilisateur_id)
    copie["choix_journal_mails"] = choix
    contexte = copie.get("contexte_client") or {}
    contexte["journal_autorise"] = choix["autorise"]
    if not choix["autorise"]:
        contexte["journal_recent"] = journal_non_autorise()
        contrat = copie.get("contrat") or {}
        contrat.pop("mails_precedents", None)
        contrat.pop("historique_emails", None)
    copie["contexte_client"] = contexte
    return copie
