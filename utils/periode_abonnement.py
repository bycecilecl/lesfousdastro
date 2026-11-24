"""Durée calendaire de l'offre bêta, sans accès réseau ni base de données."""
from calendar import monthrange
from datetime import timezone
from zoneinfo import ZoneInfo


def fin_trois_mois(debut):
    """Même date et heure à Paris trois mois plus tard, bornée à la fin du mois."""
    instant = debut.replace(tzinfo=timezone.utc) if debut.tzinfo is None else debut
    local = instant.astimezone(ZoneInfo("Europe/Paris"))
    mois_total = local.year * 12 + local.month - 1 + 3
    annee, mois_index = divmod(mois_total, 12)
    mois = mois_index + 1
    jour = min(local.day, monthrange(annee, mois)[1])
    return local.replace(year=annee, month=mois, day=jour).astimezone(timezone.utc)
