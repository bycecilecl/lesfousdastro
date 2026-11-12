"""Sélectionne le vécu déclaré dans le journal pour contextualiser un cycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, case

from models.espace_personnel import EntreeJournal, ProfilAstral
from utils.confidentialite_journal_mails import lire_choix_journal_mails, journal_non_autorise


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
    limite_entrees: int | None = 5,
    historique_strict: bool = False,
    connu_avant_utc: datetime | None = None,
) -> dict:
    """Retourne les observations récentes, sans les interpréter ni les inférer.

    Les textes sont strictement attribués à la personne. Ils servent seulement
    à sélectionner les scénarios concrets dans l'email du cycle, jamais à
    « prouver » une lecture astrologique.
    La fenêtre porte sur les dates d'observation. Une relecture explicite peut
    inclure les saisies connues plus tard, via connu_avant_utc, sans avancer
    cette fenêtre ni modifier le journal.
    """
    if jours_regardes < 1 or (limite_entrees is not None and limite_entrees < 1):
        raise ValueError("Les limites du contexte journal doivent être positives.")
    if not lire_choix_journal_mails(utilisateur_id)["autorise"]:
        return journal_non_autorise()
    debut = _instant_utc(debut_cycle_utc)
    connu_avant = _instant_utc(connu_avant_utc) if connu_avant_utc is not None else debut
    borne = debut - timedelta(days=jours_regardes)
    requete = (
        EntreeJournal.query
        .filter(
            EntreeJournal.utilisateur_id == utilisateur_id,
            EntreeJournal.date_creation <= connu_avant,
            EntreeJournal.date_observation < debut,
            or_(
                and_(EntreeJournal.est_periode.is_(False), EntreeJournal.date_observation >= borne),
                and_(EntreeJournal.est_periode.is_(True), or_(
                    EntreeJournal.date_fin_periode.is_(None),
                    EntreeJournal.date_fin_periode >= borne.date(),
                )),
            ),
        )
        .order_by(
            case((and_(EntreeJournal.est_periode.is_(True), or_(
                EntreeJournal.date_fin_periode.is_(None), EntreeJournal.date_fin_periode >= debut.date(),
            )), 0), else_=1),
            EntreeJournal.date_observation.desc(),
        )
    )
    if historique_strict:
        # Par défaut, conserve ce qui était connu à la date du mail. Une
        # relecture explicite peut choisir une date de connaissance ultérieure.
        requete = requete.filter(or_(
            EntreeJournal.date_modification.is_(None),
            EntreeJournal.date_modification <= connu_avant,
        ))
    if limite_entrees is not None:
        requete = requete.limit(limite_entrees)
    entrees = requete.all()
    observations = []
    for entree in entrees:
        contenu = {
            champ: (getattr(entree, champ) or "").strip()[:LIMITE_CARACTERES_PAR_CHAMP]
            for champ in CHAMPS_JOURNAL
            if (getattr(entree, champ) or "").strip()
        }
        if not contenu and entree.niveau_energie is None:
            continue
        observation = {
            "date": entree.date_observation.date().isoformat(),
            "periode": ({
                "debut": entree.date_observation.date().isoformat(),
                "fin": entree.date_fin_periode.isoformat() if entree.date_fin_periode else None,
                "toujours_en_cours": entree.date_fin_periode is None,
            } if entree.est_periode else None),
            "niveau_energie": entree.niveau_energie,
            "declaration": contenu,
        }
        derniere_saisie = entree.date_modification or entree.date_creation
        if derniere_saisie and _instant_utc(derniere_saisie) > debut:
            observation["saisie_apres_date_reference"] = True
        observations.append(observation)
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
    *,
    jours_regardes: int = 45,
    limite_entrees: int | None = 5,
    historique_strict: bool = False,
    connu_avant_utc: datetime | None = None,
) -> dict:
    """Unit la situation stable du profil et les observations récentes."""
    connu_avant = _instant_utc(connu_avant_utc or debut_cycle_utc)
    situation = {
        champ: (getattr(profil, champ) or "").strip()[:LIMITE_CARACTERES_PAR_CHAMP]
        for champ in CHAMPS_SITUATION
        if (getattr(profil, champ) or "").strip()
    }
    profil_modifie = profil.date_modification or profil.date_creation
    profil_disponible = not (
        historique_strict and profil_modifie
        and _instant_utc(profil_modifie) > connu_avant
    )
    return {
        "situation_actuelle": situation if profil_disponible else {},
        "statut_profil": "disponible" if profil_disponible else "version_anterieure_non_archivee",
        "connu_avant_utc": connu_avant.isoformat(),
        "journal_autorise": lire_choix_journal_mails(profil.utilisateur_id)["autorise"],
        "journal_recent": construire_contexte_journal_cycle(
            profil.utilisateur_id,
            debut_cycle_utc,
            jours_regardes=jours_regardes,
            limite_entrees=limite_entrees,
            historique_strict=historique_strict,
            connu_avant_utc=connu_avant,
        ),
    }
