"""Règles d'accès de l'espace personnel et des formules d'accompagnement."""

from datetime import datetime, timezone


FORMULES_ABONNEMENT = {
    "espace_gratuit": {
        "libelle": "Espace gratuit",
        "cycle_lunaire": False,
        "revolution_solaire": False,
        "transits_personnalises": False,
        "journal_contextualise": False,
        "emails_par_mois": 0,
    },
    "boussole_lunaire": {
        "libelle": "Boussole lunaire",
        "cycle_lunaire": True,
        "revolution_solaire": False,
        "transits_personnalises": False,
        "journal_contextualise": False,
        "emails_par_mois": 1,
    },
    "accompagnement_astral": {
        "libelle": "Accompagnement astral",
        "cycle_lunaire": True,
        "revolution_solaire": True,
        "transits_personnalises": True,
        "journal_contextualise": True,
        "emails_par_mois": 2,
    },
    "beta_accompagnement": {
        "libelle": "Accompagnement astral — bêta",
        "cycle_lunaire": True,
        "revolution_solaire": True,
        "transits_personnalises": True,
        "journal_contextualise": True,
        "emails_par_mois": 2,
    },
}

STATUTS_ACTIFS = {"actif", "test"}

# Les alias couvrent les noms de routes des versions locale et de production.
DROITS_ACTIONS_ESPACE = {
    "generer_suggestions": "extraction_ia",
    "generer_suggestions_mecanismes": "extraction_ia",
    "generer_enjeux_periode": "extraction_ia",
    "generer_enjeux_annuels": "extraction_ia",
    "generer_brouillon_email_cycle": "emails_accompagnement",
    "envoyer_brouillon_cycle": "emails_accompagnement",
    "preparer_suivi_journal": "bilan_journal_30j",
    "generer_suivi_journal": "bilan_journal_30j",
    "generer_bilan_mecanisme": "appels_ia",
    "apercu_cycle_lunaire": "appels_ia",
    "relancer_cycle_lunaire": "appels_ia",
}


def _instant_comparable(valeur):
    """Normalise les dates SQLite, parfois relues sans fuseau horaire."""
    if valeur is None:
        return None
    if valeur.tzinfo is not None:
        return valeur.astimezone(timezone.utc).replace(tzinfo=None)
    return valeur


def acces_abonnement(abonnement, maintenant=None):
    """Retourne les droits effectifs ; l'espace gratuit reste toujours ouvert."""
    instant = _instant_comparable(maintenant or datetime.now(timezone.utc))
    actif = bool(abonnement and abonnement.statut in STATUTS_ACTIFS)

    if actif:
        debut = _instant_comparable(abonnement.date_debut)
        fin = _instant_comparable(abonnement.date_fin)
        actif = (debut is None or debut <= instant) and (fin is None or fin > instant)

    code_formule = (
        abonnement.formule
        if actif and abonnement.formule in FORMULES_ABONNEMENT
        else "espace_gratuit"
    )
    droits = dict(FORMULES_ABONNEMENT[code_formule])
    droits.update({
        "code": code_formule,
        "actif": code_formule != "espace_gratuit",
        "statut": abonnement.statut if abonnement else "gratuit",
        "date_debut": abonnement.date_debut if abonnement and actif else None,
        "date_fin": abonnement.date_fin if abonnement and actif else None,
        "appels_ia": code_formule != "espace_gratuit",
        "extraction_ia": code_formule != "espace_gratuit",
        "emails_accompagnement": code_formule != "espace_gratuit",
        "bilan_journal_30j": code_formule != "espace_gratuit",
    })
    return droits


def acces_beta_actif(abonnement, maintenant=None):
    """Communauté et feedback suivent l'abonnement, pas l'inscription aux mails."""
    return acces_abonnement(abonnement, maintenant)["code"] == "beta_accompagnement"


def droits_pour_compte(utilisateur_id, maintenant=None):
    """Droits actuels relus côté serveur, même pour une ancienne préparation."""
    if not utilisateur_id:
        return acces_abonnement(None, maintenant)
    from sqlalchemy import select
    from extensions import db
    from models.espace_personnel import AbonnementEspace, UtilisateurEspace
    compte = db.session.execute(select(UtilisateurEspace.actif).where(UtilisateurEspace.id == utilisateur_id)).scalar_one_or_none()
    if compte != 1:
        return acces_abonnement(None, maintenant)
    abonnement = db.session.execute(select(AbonnementEspace).where(
        AbonnementEspace.utilisateur_id == utilisateur_id,
    ).execution_options(populate_existing=True)).scalar_one_or_none()
    return acces_abonnement(abonnement, maintenant)


def exiger_droit_compte(utilisateur_id, droit):
    if not droits_pour_compte(utilisateur_id).get(droit, False):
        raise ValueError("Cette fonction est réservée à un abonnement payant actif. Aucun appel IA ni e-mail d’accompagnement n’est lancé.")
