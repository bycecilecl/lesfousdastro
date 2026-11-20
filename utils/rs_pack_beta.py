"""Branche un rapport acheté dans le pack sur le moteur RS existant, sans le modifier."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo


def preparer(profil, formulaire):
    try:
        annee = int(formulaire.get("annee", ""))
        lieu = {"lieu": formulaire.get("lieu", "").strip(),
                "lat": float(formulaire.get("lat", "")), "lon": float(formulaire.get("lon", "")),
                "tzid": formulaire.get("tzid", "").strip()}
    except (TypeError, ValueError):
        raise ValueError("Vérifie l’année et choisis une ville dans les suggestions.") from None
    if not max(1900, profil.date_naissance.year) <= annee <= 2100 or not lieu["lieu"] or len(lieu["lieu"]) > 200:
        raise ValueError("Choisis l’année et la ville de ton retour solaire.")
    if not math.isfinite(lieu["lat"]) or not math.isfinite(lieu["lon"]) or not -90 <= lieu["lat"] <= 90 or not -180 <= lieu["lon"] <= 180:
        raise ValueError("Les coordonnées de la ville sont invalides.")
    try:
        ZoneInfo(lieu["tzid"])
    except (KeyError, ValueError):
        raise ValueError("Choisis une ville dans les suggestions.") from None
    if profil.latitude is None or profil.longitude is None:
        raise ValueError("Complète les coordonnées de ton profil astral.")
    personne = {"nom": profil.prenom, "genre": "", "date": profil.date_naissance.isoformat(),
        "heure": profil.heure_naissance.strftime("%H:%M"), "lieu": profil.ville_naissance,
        "lat": profil.latitude, "lon": profil.longitude, "tzid": profil.fuseau_horaire}
    contexte = formulaire.get("preoccupation", "").strip()
    if len(contexte) > 5000:
        raise ValueError("Ton repère personnel dépasse 5 000 caractères.")
    return {"personne": personne, "lieu_rs": lieu, "annee": annee,
            "contexte_client": {"preoccupation": contexte} if contexte else {}}


def _cycle(profil, preparation):
    """Prépare les données annuelles avec le lieu choisi, sans génération IA."""
    from models.espace_personnel import CycleSolaire
    from utils.revolution_solaire.theme_revolution_solaire import calculer_theme_revolution_solaire
    from utils.revolution_solaire.donnees_techniques import extraire_donnees_revolution_solaire
    from utils.revolution_solaire.calcul_retour_solaire import trouver_retour_solaire
    annee, lieu = preparation["annee"], preparation["lieu_rs"]
    existant = CycleSolaire.query.filter_by(profil_id=profil.id, cle_cycle=str(annee)).first()
    if existant:
        if abs(existant.latitude-lieu["lat"]) > .001 or abs(existant.longitude-lieu["lon"]) > .001 or existant.fuseau_horaire != lieu["tzid"]:
            raise ValueError("Une RS de cette année est déjà enregistrée avec un autre lieu. Contacte Cécile avant de la remplacer.")
        return existant
    calcul = calculer_theme_revolution_solaire(profil.prenom, preparation["personne"], lieu, annee)
    donnees = extraire_donnees_revolution_solaire(calcul["theme_natal"], calcul["theme_revolution_solaire"], age_profection=calcul["age_au_retour"])
    prochain = trouver_retour_solaire(calcul["naissance_locale"], annee+1)["retour_utc"]
    archive = {"retour_utc": calcul["retour"]["retour_utc"].isoformat(),
        "retour_local": calcul["retour_local"].isoformat(), "lieu_rs": lieu,
        "theme_revolution_solaire": calcul["theme_revolution_solaire"], "donnees": donnees}
    return CycleSolaire(profil_id=profil.id, cle_cycle=str(annee), annee=annee,
        debut_cycle_utc=calcul["retour"]["retour_utc"], fin_cycle_utc=prochain,
        ville=lieu["lieu"], fuseau_horaire=lieu["tzid"], latitude=lieu["lat"], longitude=lieu["lon"],
        theme_technique=json.dumps(archive, ensure_ascii=False, default=str), statut="technique")


def generer(commande, droit, profil, preparation):
    """Un POST explicite, un rapport. Aucune relance automatique après un échec."""
    from flask import current_app
    from sqlalchemy import select, update
    from extensions import db
    from models.espace_personnel import AnalysePersonnelle, CommandeAbonnementEspace, RevolutionSolairePackBeta
    from utils.souscription_espace import formule_commande
    from utils.stockage_espace import racine_privee_espace
    if commande.statut != "active" or not formule_commande(commande)["avec_rs"] or droit.utilisateur_id != profil.utilisateur_id:
        raise ValueError("Le pack avec Révolution Solaire n’est pas disponible pour ce compte.")
    cycle = _cycle(profil, preparation)
    # Les calculs peuvent précéder la réservation, jamais les appels IA.
    reservation = db.session.execute(update(RevolutionSolairePackBeta).where(
        RevolutionSolairePackBeta.commande_id == commande.id,
        RevolutionSolairePackBeta.statut == "a_preparer"
    ).values(statut="en_cours", preparation_json=json.dumps(preparation, ensure_ascii=False)))
    db.session.commit()
    if reservation.rowcount != 1:
        raise ValueError("Ce rapport est déjà en cours, terminé ou à vérifier. Aucun nouvel appel lancé.")
    try:
        etat = db.session.execute(select(CommandeAbonnementEspace.statut).where(CommandeAbonnementEspace.id == commande.id)).scalar_one()
        if etat != "active":
            raise ValueError("Cet achat n’est plus actif.")
        from utils.revolution_solaire.service import generer_rapport_revolution_solaire
        moteur = generer_rapport_revolution_solaire
        choix = current_app.config.get("RS_REPORT_ENGINE", "blocs_personnels")
        if choix == "blocs_personnels":
            from utils.revolution_solaire.v2.blocs.service_formulaire import generer_rapport_formulaire
            moteur = generer_rapport_formulaire
        elif choix in {"v2", "enjeux", "enjeux_detaillee", "archive_enjeux"}:
            from utils.revolution_solaire.service import generer_rapport_revolution_solaire_v2
            moteur = generer_rapport_revolution_solaire_v2
            if choix != "v2":
                from functools import partial
                moteur = partial(moteur, moteur_enjeux={"enjeux_detaillee": "detaillee", "archive_enjeux": "archive"}.get(choix, True))
        archives = racine_privee_espace()/"rs_pack_beta"/commande.id
        archives.mkdir(parents=True, exist_ok=True, mode=0o700)
        print("[PACK RS] Préparation confirmée, moteur existant :", choix, flush=True)
        print(json.dumps(preparation, ensure_ascii=False, indent=2), flush=True)
        rapport = moteur(**preparation, stockage_dir=archives, autoriser_generation=True, identifiant_execution=commande.id)
        droit.identifiant_generation = rapport.identifiant_generation
        db.session.commit()
        # Conserver le PDF privé avec la même mise en page que le rapport public.
        destination = racine_privee_espace()/"analyses_uploads"/("rs-pack-"+commande.id+".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        pdf_archive = archives/rapport.identifiant_generation/"rapport.pdf"
        if pdf_archive.is_file():
            shutil.copy2(pdf_archive, destination)
        else:
            from utils.pdf_utils import html_to_pdf
            from utils.revolution_solaire.rapport_pdf import habiller_rapport_pdf
            html = habiller_rapport_pdf(rapport.html, personne=preparation["personne"], lieu_rs=preparation["lieu_rs"], annee=preparation["annee"])
            if not html_to_pdf(html, str(destination)) or not destination.is_file():
                raise ValueError("Le texte est conservé, mais son PDF n’a pas pu être préparé.")
        os.chmod(destination, 0o600)
        # La réservation a été validée avant l’appel ; le cycle neuf est enregistré ici.
        db.session.add(cycle)
        db.session.flush()
        analyse = AnalysePersonnelle(utilisateur_id=profil.utilisateur_id, cycle_solaire_id=cycle.id,
            type_analyse="revolution_solaire", titre=f"Révolution solaire {preparation['annee']}",
            statut="terminee", chemin_resultat=destination.name, date_generation=datetime.now(timezone.utc))
        db.session.add(analyse)
        db.session.flush()
        # Les anciennes versions annuelles et leurs PDF restent conservés.
        if not cycle.rapport_texte:
            cycle.rapport_texte, cycle.rapport_html = rapport.texte_markdown, rapport.html
            cycle.date_generation = datetime.now(timezone.utc)
        droit.statut, droit.analyse_id, droit.date_generation = "terminee", analyse.id, datetime.now(timezone.utc)
        droit.erreur = None
        db.session.commit()
        print("[PACK RS] Rapport conservé dans Mes analyses. Aucun envoi de mail ni extraction IA supplémentaire.", flush=True)
        return analyse
    except Exception:
        db.session.rollback()
        droit = db.session.get(RevolutionSolairePackBeta, commande.id)
        droit.statut, droit.erreur = "a_revoir", "La préparation du rapport s’est interrompue. Les résultats disponibles sont conservés ; contacte Cécile. Aucun nouvel appel automatique."
        db.session.commit()
        raise ValueError(droit.erreur) from None
