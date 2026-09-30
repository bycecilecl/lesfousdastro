"""Droits explicites des formules de l'espace ; le compte gratuit reste accessible."""

from datetime import datetime, timezone


FORMULES = {
    "espace_gratuit": {"emails_par_mois": 0, "cycle_lunaire": False, "revolution_solaire": False},
    "boussole_lunaire": {"emails_par_mois": 1, "cycle_lunaire": True, "revolution_solaire": False},
    "accompagnement_astral": {"emails_par_mois": 2, "cycle_lunaire": True, "revolution_solaire": True},
    "beta_accompagnement": {"emails_par_mois": 2, "cycle_lunaire": True, "revolution_solaire": True},
}


def _instant(valeur):
    if valeur is None:
        return None
    if valeur.tzinfo is None:
        return valeur.replace(tzinfo=timezone.utc)
    return valeur.astimezone(timezone.utc)


def acces_abonnement(abonnement, maintenant=None):
    """Calcule les droits actifs sans confondre espace gratuit et abonnement."""
    instant = _instant(maintenant or datetime.now(timezone.utc))
    actif = bool(abonnement and abonnement.statut in {"actif", "test"})
    if actif:
        debut = _instant(abonnement.date_debut)
        fin = _instant(abonnement.date_fin)
        actif = (debut is None or debut <= instant) and (fin is None or instant < fin)
    code = abonnement.formule if actif and abonnement.formule in FORMULES else "espace_gratuit"
    return {"code": code, "actif": code != "espace_gratuit", **FORMULES[code]}
