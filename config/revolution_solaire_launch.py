"""Ouverture contrôlée des commandes de Révolution solaire."""
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo


DATE_OUVERTURE = date(2026, 10, 9)


def ventes_ouvertes() -> bool:
    active = (os.getenv("REVOLUTION_SOLAIRE_SALES_ENABLED") or "").strip().lower()
    return active in {"1", "true", "on", "yes"} and datetime.now(
        ZoneInfo("Europe/Paris")
    ).date() >= DATE_OUVERTURE
