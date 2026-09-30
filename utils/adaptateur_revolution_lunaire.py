"""Pont entre une révolution lunaire et les moteurs astrologiques existants."""

from __future__ import annotations

from typing import Any

from utils.configurations_astrologiques import analyser_configurations_majeures
from utils.utils_points_forts import detecter_amas, profil_elements_modalites


def _adapter_aspects_internes(aspects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapte les clés de la RL au contrat du moteur de configurations."""
    aspects_adaptes = []
    for aspect in aspects or []:
        planete1 = aspect.get("point_1") or aspect.get("planete1")
        planete2 = aspect.get("point_2") or aspect.get("planete2")
        if not planete1 or not planete2:
            continue
        aspects_adaptes.append({
            "planete1": planete1,
            "planete2": planete2,
            "aspect": aspect.get("aspect"),
            "orbe": aspect.get("orbe"),
        })
    return aspects_adaptes


def enrichir_priorites_avec_moteurs_existants(theme: dict[str, Any]) -> dict[str, Any]:
    """Produit les facteurs collectifs sans réimplémenter les moteurs du thème.

    La fonction ne modifie pas le thème reçu. Elle retourne uniquement les
    résultats structurés destinés à compléter ``priorites_interpretation``.
    """
    planetes = theme.get("planetes") or {}
    donnees_communes = {"planetes": planetes}
    aspects = _adapter_aspects_internes(theme.get("aspects_revolution") or [])

    return {
        "amas_signes": detecter_amas(
            donnees_communes,
            seuil=3,
            par="signe",
            strict=True,
        ),
        "amas_maisons": detecter_amas(
            donnees_communes,
            seuil=3,
            par="maison",
            strict=True,
        ),
        "dominantes_elements_modalites": profil_elements_modalites(
            donnees_communes
        ),
        "configurations_majeures": analyser_configurations_majeures(
            aspects=aspects,
            positions=planetes,
        ),
    }

