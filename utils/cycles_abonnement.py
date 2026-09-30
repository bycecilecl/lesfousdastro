"""Liaisons durables entre les cycles solaires et lunaires de l'espace abonné."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from extensions import db
from models.espace_personnel import CycleLunaire, CycleSolaire, ProfilAstral
from utils.revolution_solaire.calcul_retour_solaire import trouver_retour_solaire
from utils.revolution_solaire.donnees_techniques import extraire_donnees_revolution_solaire
from utils.revolution_solaire.rapport_technique import generer_rapport_technique
from utils.revolution_solaire.theme_revolution_solaire import calculer_theme_revolution_solaire


def trouver_cycle_solaire_actif(
    profil_id: int,
    instant_utc: datetime,
) -> CycleSolaire | None:
    """Retourne la RS du profil qui couvre l'instant UTC demandé."""
    if instant_utc.tzinfo is None:
        instant_utc = instant_utc.replace(tzinfo=timezone.utc)
    return (
        CycleSolaire.query
        .filter(
            CycleSolaire.profil_id == profil_id,
            CycleSolaire.debut_cycle_utc <= instant_utc,
            CycleSolaire.fin_cycle_utc > instant_utc,
        )
        .order_by(CycleSolaire.debut_cycle_utc.desc())
        .first()
    )


def rattacher_cycle_lunaire_a_sa_rs(cycle: CycleLunaire) -> CycleSolaire | None:
    """Associe un cycle lunaire à la RS active, en la préparant si nécessaire.

    La RS ajoutée ici est uniquement le relevé calculé localement. L'appelant
    reste responsable de la transaction SQLAlchemy. Une liaison déjà
    enregistrée n'est jamais écrasée.
    """
    if cycle.cycle_solaire_id is not None:
        return None
    cycle_solaire = trouver_cycle_solaire_actif(
        cycle.profil_id,
        cycle.debut_cycle_utc,
    )
    if cycle_solaire is None:
        profil = db.session.get(ProfilAstral, cycle.profil_id)
        if profil is None:
            raise ValueError("Profil astral introuvable pour ce cycle lunaire.")
        cycle_solaire = creer_cycle_solaire_pour_instant(
            profil,
            cycle.debut_cycle_utc,
        )
    if cycle_solaire is not None:
        cycle.cycle_solaire_id = cycle_solaire.id
    return cycle_solaire


def _donnees_profil_pour_cycle(profil: ProfilAstral) -> tuple[dict, dict]:
    """Transforme le profil BDD en données attendues par le calcul RS."""
    if not all((profil.latitude is not None, profil.longitude is not None)):
        raise ValueError("Les coordonnées de naissance sont nécessaires pour calculer la RS.")
    if not all((
        profil.ville_cycles,
        profil.fuseau_cycles,
        profil.latitude_cycles is not None,
        profil.longitude_cycles is not None,
    )):
        raise ValueError("Renseigne la ville des cycles avant de calculer la RS.")
    personne = {
        "nom": profil.prenom,
        "date": profil.date_naissance.isoformat(),
        "heure": profil.heure_naissance.strftime("%H:%M"),
        "lieu": profil.ville_naissance,
        "lat": profil.latitude,
        "lon": profil.longitude,
        "tzid": profil.fuseau_horaire,
    }
    lieu_rs = {
        "lieu": profil.ville_cycles,
        "lat": profil.latitude_cycles,
        "lon": profil.longitude_cycles,
        "tzid": profil.fuseau_cycles,
    }
    return personne, lieu_rs


def creer_ou_recuperer_cycle_solaire(
    profil: ProfilAstral,
    annee: int,
) -> CycleSolaire:
    """Calcule et persiste une RS technique sans appeler le LLM.

    Le rapport client reste vide à ce stade : il sera généré seulement par le
    flux de vente ou l'espace abonné prévu pour cela.
    """
    cycle = CycleSolaire.query.filter_by(
        profil_id=profil.id,
        cle_cycle=str(annee),
    ).first()
    if cycle is not None:
        return cycle

    personne, lieu_rs = _donnees_profil_pour_cycle(profil)
    calcul = calculer_theme_revolution_solaire(
        profil.prenom,
        personne,
        lieu_rs,
        annee,
    )
    donnees = extraire_donnees_revolution_solaire(
        calcul["theme_natal"],
        calcul["theme_revolution_solaire"],
        age_profection=calcul["age_au_retour"],
    )
    retour_utc = calcul["retour"]["retour_utc"]
    prochain_retour = trouver_retour_solaire(calcul["naissance_locale"], annee + 1)["retour_utc"]
    retour_local = calcul["retour_local"]
    releve = generer_rapport_technique(donnees, retour_local)
    theme_technique = {
        "retour_utc": retour_utc.isoformat(),
        "retour_local": retour_local.isoformat(),
        "lieu_rs": lieu_rs,
        # Le thème RS brut est conservé pour calculer ensuite les contacts
        # RL→RS. Le relevé ``donnees`` reste la version hiérarchisée destinée
        # à l'interprétation.
        "theme_revolution_solaire": calcul["theme_revolution_solaire"],
        "donnees": donnees,
    }
    cycle = CycleSolaire(
        profil_id=profil.id,
        cle_cycle=str(annee),
        annee=annee,
        debut_cycle_utc=retour_utc,
        fin_cycle_utc=prochain_retour,
        ville=lieu_rs["lieu"],
        fuseau_horaire=lieu_rs["tzid"],
        latitude=lieu_rs["lat"],
        longitude=lieu_rs["lon"],
        theme_technique=json.dumps(theme_technique, ensure_ascii=False, default=str),
        releve_technique=releve,
        statut="technique",
    )
    db.session.add(cycle)
    db.session.flush()
    return cycle


def creer_cycle_solaire_pour_instant(
    profil: ProfilAstral,
    instant_utc: datetime,
) -> CycleSolaire:
    """Retourne la RS couvrant l'instant, en créant seulement celle qui manque.

    Le retour d'une année civile peut arriver après l'instant demandé (anniversaire
    de décembre, par exemple). Dans ce cas, la RS de l'année précédente est le
    cadre actif.
    """
    if instant_utc.tzinfo is None:
        instant_utc = instant_utc.replace(tzinfo=timezone.utc)
    cycle = trouver_cycle_solaire_actif(profil.id, instant_utc)
    if cycle is not None:
        return cycle

    cycle_candidat = creer_ou_recuperer_cycle_solaire(profil, instant_utc.year)
    if (
        cycle_candidat.debut_cycle_utc <= instant_utc
        and cycle_candidat.fin_cycle_utc > instant_utc
    ):
        return cycle_candidat

    cycle_precedent = creer_ou_recuperer_cycle_solaire(
        profil,
        instant_utc.year - 1,
    )
    if (
        cycle_precedent.debut_cycle_utc <= instant_utc
        and cycle_precedent.fin_cycle_utc > instant_utc
    ):
        return cycle_precedent

    raise RuntimeError("Impossible d'identifier la RS couvrant ce cycle lunaire.")
