"""Identifie les phases utiles d'un transit pour éviter les emails répétitifs."""

from __future__ import annotations


def empreinte_transit(transit: dict) -> str:
    return ":".join(str(transit.get(cle, "")) for cle in (
        "planete_transit", "aspect", "planete_natale",
    ))


def phase_transit(transit: dict, positions: dict) -> str:
    """Classe le passage actuel sans prétendre dater une station précise."""
    orbe = float(transit.get("orbe", 99))
    if orbe <= 0.2:
        return "passage_exact"
    planete = transit.get("planete_transit")
    if (positions.get(planete) or {}).get("retrograde"):
        return "retour_retrograde"
    if transit.get("application"):
        return "approche_directe"
    return "eloignement_direct"


def est_nouvelle_phase(transit: dict, positions: dict, historique: dict | None) -> tuple[bool, str]:
    """Compare un transit à l'historique compact des emails précédents."""
    phase = phase_transit(transit, positions)
    empreinte = empreinte_transit(transit)
    phases_precedentes = set()
    for email in (historique or {}).get("emails_recents", []):
        for point in email.get("points_abordes") or []:
            if point.get("empreinte") == empreinte and point.get("phase"):
                phases_precedentes.add(point["phase"])
    if not phases_precedentes:
        return True, phase
    if phase not in phases_precedentes:
        return True, phase
    return False, phase


def point_aborde_transit(transit: dict, positions: dict) -> dict:
    """Format à enregistrer avec l'email une fois réellement généré."""
    return {"empreinte": empreinte_transit(transit), "phase": phase_transit(transit, positions)}
