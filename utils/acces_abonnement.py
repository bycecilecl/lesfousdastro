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
    })
    return droits
