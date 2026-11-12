"""Sélection des enjeux du PDF annuel pour les futurs mails, sans appel IA."""
from copy import deepcopy
from datetime import timezone
import json

from models.espace_personnel import AnalysePersonnelle, CycleSolaire, EnjeuAnnuel


def contexte_enjeux_annuels(profil, instant_cycle):
    if instant_cycle.tzinfo is None:
        instant_cycle = instant_cycle.replace(tzinfo=timezone.utc)
    instant = instant_cycle.astimezone(timezone.utc).replace(tzinfo=None)
    cycle = CycleSolaire.query.filter(
        CycleSolaire.profil_id == profil.id,
        CycleSolaire.debut_cycle_utc <= instant,
        CycleSolaire.fin_cycle_utc > instant,
    ).order_by(CycleSolaire.debut_cycle_utc.desc()).first()
    if cycle is None:
        return {"statut": "sans_cycle", "enjeux": []}
    # Toujours la dernière version de cette année : jamais de repli silencieux
    # sur les enjeux d'un ancien PDF ou d'une autre année.
    analyse = AnalysePersonnelle.query.filter_by(
        utilisateur_id=profil.utilisateur_id, cycle_solaire_id=cycle.id,
        type_analyse="revolution_solaire",
    ).order_by(AnalysePersonnelle.date_creation.desc(), AnalysePersonnelle.id.desc()).first()
    if analyse is None:
        return {"statut": "sans_pdf", "annee": cycle.annee, "enjeux": []}
    enjeux = EnjeuAnnuel.query.filter(
        EnjeuAnnuel.analyse_id == analyse.id, EnjeuAnnuel.retenu_email.is_(True),
        EnjeuAnnuel.source_validation.in_(("extrait_verifie", "validation_manuelle")),
    ).order_by(EnjeuAnnuel.ordre).all()
    return {
        "statut": "retenus" if enjeux else "aucun_enjeu_retenu",
        "annee": cycle.annee, "cycle_solaire_id": cycle.id,
        "analyse_id": analyse.id, "pdf_ajoute_le": analyse.date_creation.isoformat(),
        "periode": {"debut": cycle.debut_cycle_utc.isoformat(), "fin": cycle.fin_cycle_utc.isoformat()},
        "enjeux": [{
            "id": enjeu.id, "titre": enjeu.titre, "contenu": enjeu.contenu,
            "references_astrologiques": json.loads(enjeu.references_astrologiques or "[]"),
        } for enjeu in enjeux],
    }


def actualiser_enjeux_email(profil, preparation, instant_cycle):
    """Actualise seulement les enjeux d'un mail non généré, sans recalcul du ciel."""
    from utils.email_cycle_abonnement import construire_prompt_email_cycle
    from utils.confidentialite_journal_mails import filtrer_preparation_journal_mails

    if preparation.get("portee", "complet") != "complet" or not preparation.get("contrat"):
        return preparation
    copie = filtrer_preparation_journal_mails(profil, preparation)
    copie["contrat"]["enjeux_annuels_du_rapport"] = contexte_enjeux_annuels(profil, instant_cycle)
    copie["prompt"] = construire_prompt_email_cycle(
        profil.prenom, copie["contrat"], contexte_client=copie.get("contexte_client"),
    )
    return copie
