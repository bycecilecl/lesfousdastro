# utils/transits/transits_bdd.py

import csv
import os
import logging

logger = logging.getLogger(__name__)


BASE_DIR = os.path.join("data", "transits")


def _clean(value) -> str:
    return str(value or "").strip()


def _clean_key(value) -> str:
    return _clean(value).lower()


def charger_bdd_aspects() -> dict:
    chemin = os.path.join(BASE_DIR, "transits_aspects.csv")

    if not os.path.exists(chemin):
        return {}

    bdd = {}

    with open(chemin, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        logger.info("HEADERS ASPECTS = %s", reader.fieldnames)

        for row in reader:
            key = (
                _clean_key(row.get("PLANETE_TRANSIT")),
                _clean_key(row.get("ASPECT")),
                _clean_key(row.get("PLANETE_NATALE")),
            )

            bdd[key] = {
                "interpretation": _clean(row.get("INTERPRETATION")),
            }

    return bdd


def charger_bdd_maisons() -> dict:
    chemin = os.path.join(BASE_DIR, "transits_maisons.csv")

    if not os.path.exists(chemin):
        return {}

    bdd = {}

    with open(chemin, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        logger.info("HEADERS MAISONS = %s", reader.fieldnames)

        for row in reader:
            key = (
                _clean_key(row.get("PLANETE")),
                _clean_key(row.get("DONNEE")),
                _clean(row.get("VALEUR")),
            )

            bdd[key] = {
                "interpretation": _clean(row.get("INTERPRETATION")),
            }

    return bdd


def chercher_interpretation_aspect(
    planete_transit: str,
    aspect: str,
    planete_natale: str,
) -> str | None:
    bdd = charger_bdd_aspects()

    key = (
        _clean_key(planete_transit),
        _clean_key(aspect),
        _clean_key(planete_natale),
    )

    donnee = bdd.get(key)
    if not donnee:
        return None

    return donnee.get("interpretation") or None


def chercher_interpretation_maison(
    planete: str,
    maison: int | str | None,
) -> str | None:
    if maison in (None, "", "—"):
        return None

    bdd = charger_bdd_maisons()

    key = (
        _clean_key(planete),
        "maison",
        _clean(maison),
    )

    donnee = bdd.get(key)
    if not donnee:
        return None

    return donnee.get("interpretation") or None
