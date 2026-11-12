"""Contrat factuel commun aux cycles natal, solaire, lunaire et aux transits.

Ce module ne calcule ni n'interprète : il compose les données déjà calculées
pour alimenter un futur email ou une synthèse sans confondre leurs provenances.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from models.espace_personnel import CycleLunaire, CycleSolaire, ProfilAstral
from utils.cycles_abonnement import trouver_cycle_solaire_actif


def _charger_json(valeur: str | None, nom: str) -> dict[str, Any]:
    if not valeur:
        raise ValueError(f"{nom} est absent.")
    try:
        donnees = json.loads(valeur)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{nom} est invalide.") from exc
    if not isinstance(donnees, dict):
        raise ValueError(f"{nom} doit être un objet JSON.")
    return donnees


def _normaliser_instant(instant_utc: datetime | None) -> datetime:
    instant = instant_utc or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def _cycle_lunaire_actif(
    profil_id: int,
    instant_utc: datetime,
) -> CycleLunaire | None:
    return (
        CycleLunaire.query
        .filter(
            CycleLunaire.profil_id == profil_id,
            CycleLunaire.debut_cycle_utc <= instant_utc,
            CycleLunaire.fin_cycle_utc > instant_utc,
        )
        .order_by(CycleLunaire.debut_cycle_utc.desc())
        .first()
    )


def construire_dossier_cycle(
    profil: ProfilAstral,
    *,
    instant_utc: datetime | None = None,
    photo_transits: dict[str, Any] | None = None,
    cycle_lunaire: CycleLunaire | None = None,
) -> dict[str, Any]:
    """Réunit les faits dont dépend une lecture de cycle à une date donnée.

    Les thèmes restent contenus sous leurs clés d'origine, afin que leur rôle
    soit traçable : ``natal``, ``revolution_solaire``, ``revolution_lunaire``
    et ``transits``. L'absence d'une RL ou des transits est autorisée : le
    futur émetteur pourra alors savoir précisément quel fragment manque.
    """
    if profil.id is None:
        raise ValueError("Le profil doit être enregistré avant de composer un dossier.")
    instant = _normaliser_instant(instant_utc)
    theme_natal = _charger_json(profil.theme_natal, "Le thème natal")
    cycle_solaire = trouver_cycle_solaire_actif(profil.id, instant)
    cycle_lunaire = cycle_lunaire or _cycle_lunaire_actif(profil.id, instant)

    dossier: dict[str, Any] = {
        "version_contrat": "cycle-abonnement-v1",
        "instant_reference_utc": instant.isoformat(),
        "profil": {
            "id": profil.id,
            "prenom": profil.prenom,
            "lieu_cycles": profil.ville_cycles,
            "fuseau_cycles": profil.fuseau_cycles,
        },
        "natal": {
            "source": "ProfilAstral.theme_natal",
            "theme": theme_natal,
        },
        "revolution_solaire": None,
        "revolution_lunaire": None,
        "transits": photo_transits,
    }
    if cycle_solaire is not None:
        dossier["revolution_solaire"] = {
            "source": "CycleSolaire",
            "cycle_id": cycle_solaire.id,
            "annee": cycle_solaire.annee,
            "debut_cycle_utc": cycle_solaire.debut_cycle_utc.isoformat(),
            "fin_cycle_utc": cycle_solaire.fin_cycle_utc.isoformat(),
            "lieu": cycle_solaire.ville,
            "fuseau": cycle_solaire.fuseau_horaire,
            "donnees_techniques": _charger_json(
                cycle_solaire.theme_technique,
                "Le thème technique de la révolution solaire",
            ),
        }
    if cycle_lunaire is not None:
        dossier["revolution_lunaire"] = {
            "source": "CycleLunaire",
            "cycle_id": cycle_lunaire.id,
            "debut_cycle_utc": cycle_lunaire.debut_cycle_utc.isoformat(),
            "fin_cycle_utc": cycle_lunaire.fin_cycle_utc.isoformat(),
            "lieu": cycle_lunaire.ville,
            "fuseau": cycle_lunaire.fuseau_horaire,
            "donnees_techniques": _charger_json(
                cycle_lunaire.theme_technique,
                "Le thème technique de la révolution lunaire",
            ),
        }
    return dossier
