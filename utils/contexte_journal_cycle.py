"""Sélectionne le vécu déclaré dans le journal pour contextualiser un cycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models.espace_personnel import EntreeJournal, ProfilAstral


CHAMPS_JOURNAL = (
    "emotions",
    "situation",
    "reaction_automatique",
    "choix_conscient",
    "notes_libres",
)
CHAMPS_SITUATION = (
    "situation_foyer",
    "situation_amour",
    "situation_travail",
    "situation_enfants",
    "situation_sante",
    "preoccupation_actuelle",
)
LIMITE_CARACTERES_PAR_CHAMP = 700


def _instant_utc(instant: datetime) -> datetime:
    return (
        instant.replace(tzinfo=timezone.utc)
        if instant.tzinfo is None
        else instant.astimezone(timezone.utc)
    )


def construire_contexte_journal_cycle(
    utilisateur_id: int,
    debut_cycle_utc: datetime,
    *,
    jours_regardes: int = 45,
    limite_entrees: int = 5,
) -> dict:
    """Retourne les observations récentes, sans les interpréter ni les inférer.

    Les textes sont strictement attribués à la personne. Ils servent seulement
    à sélectionner les scénarios concrets dans l'email du cycle, jamais à
    « prouver » une lecture astrologique.
    """
    if jours_regardes < 1 or limite_entrees < 1:
        raise ValueError("Les limites du contexte journal doivent être positives.")
    debut = _instant_utc(debut_cycle_utc)
    borne = debut - timedelta(days=jours_regardes)
    entrees = (
        EntreeJournal.query
        .filter(
            EntreeJournal.utilisateur_id == utilisateur_id,
            EntreeJournal.date_observation >= borne,
            EntreeJournal.date_observation < debut,
        )
        .order_by(EntreeJournal.date_observation.desc())
        .limit(limite_entrees)
        .all()
    )
    observations = []
    for entree in entrees:
        contenu = {
            champ: (getattr(entree, champ) or "").strip()[:LIMITE_CARACTERES_PAR_CHAMP]
            for champ in CHAMPS_JOURNAL
            if (getattr(entree, champ) or "").strip()
        }
        if not contenu and entree.niveau_energie is None:
            continue
        observations.append({
            "date": entree.date_observation.date().isoformat(),
            "niveau_energie": entree.niveau_energie,
            "declaration": contenu,
        })
    return {
        "source": "journal personnel déclaré par la personne",
        "periode_observee": {
            "debut_utc": borne.isoformat(),
            "fin_utc": debut.isoformat(),
        },
        "nombre_entrees_retenues": len(observations),
        "observations": observations,
    }


def construire_contexte_client_cycle(
    profil: ProfilAstral,
    debut_cycle_utc: datetime,
) -> dict:
    """Unit la situation stable du profil et les observations récentes."""
    situation = {
        champ: (getattr(profil, champ) or "").strip()[:LIMITE_CARACTERES_PAR_CHAMP]
        for champ in CHAMPS_SITUATION
        if (getattr(profil, champ) or "").strip()
    }
    return {
        "situation_actuelle": situation,
        "journal_recent": construire_contexte_journal_cycle(
            profil.utilisateur_id,
            debut_cycle_utc,
        ),
    }
