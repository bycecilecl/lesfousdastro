"""Ouverture contrôlée des commandes de Révolution solaire."""
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo


DATE_OUVERTURE = date(2026, 10, 9)


def ventes_ouvertes() -> bool:
    active = (os.getenv("REVOLUTION_SOLAIRE_SALES_ENABLED") or "").strip().lower()
    if active not in {"1", "true", "on", "yes"}:
        return False
    # Permettre une commande de test avant l'ouverture seulement quand le site
    # est en maintenance ET que les deux prestataires sont en mode bac à sable.
    maintenance = (os.getenv("APP_MAINTENANCE") or "").strip().lower() in {"1", "true", "on", "yes"}
    sandbox = (os.getenv("PAYMENTS_SANDBOX") or "").strip().lower() in {"1", "true", "on", "yes"}
    return (maintenance and sandbox) or datetime.now(ZoneInfo("Europe/Paris")).date() >= DATE_OUVERTURE
