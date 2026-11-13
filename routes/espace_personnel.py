LECTURES_PLANETAIRES = {
    "Soleil": {
        "dynamique": "met en lumière ce qui demande à être affirmé consciemment",
        "question": "Qu’est-ce que j’ai besoin d’assumer ou de rendre visible aujourd’hui ?",
    },
    "Lune": {
        "dynamique": "fait remonter les besoins, les réactions et la météo émotionnelle",
        "question": "Quel besoin émotionnel cherche réellement à être entendu ?",
    },
    "Mercure": {
        "dynamique": "active la pensée, les échanges et la manière de nommer les choses",
        "question": "Qu’est-ce qui mérite d’être compris, dit ou reformulé plus clairement ?",
    },
    "Vénus": {
        "dynamique": "interroge les liens, les valeurs, le plaisir et ce qui compte vraiment",
        "question": "Est-ce que mon choix respecte ce que j’aime et ce que je considère précieux ?",
    },
    "Mars": {
        "dynamique": "mobilise l’action, le désir, la colère et la capacité à trancher",
        "question": "Où mon énergie veut-elle agir, et comment l’utiliser sans la subir ?",
    },
    "Jupiter": {
        "dynamique": "amplifie, ouvre et pousse à élargir le champ des possibles",
        "question": "Où puis-je grandir sans confondre expansion et excès ?",
    },
    "Saturne": {
        "dynamique": "structure, limite et oblige à regarder la réalité en face",
        "question": "Où ai-je besoin de poser une limite ou de prendre ma responsabilité ?",
    },
    "Uranus": {
        "dynamique": "réveille et libère ce qui était devenu trop figé",
        "question": "Quelle ancienne manière de fonctionner ne me laisse plus respirer ?",
    },
    "Neptune": {
        "dynamique": "sensibilise, inspire et dissout les repères devenus trop rigides",
        "question": "Où dois-je distinguer l’intuition véritable de la projection ou du flou ?",
    },
    "Pluton": {
        "dynamique": "intensifie et révèle ce qui opère en profondeur",
        "question": "Qu’est-ce que cette situation révèle de mon rapport au contrôle et à la transformation ?",
    },
}
PLANETES_TRANSIT_JOURNAL = (
    "Soleil",
    "Lune",
    "Mercure",
    "Vénus",
    "Mars",
    "Jupiter",
    "Saturne",
    "Uranus",
    "Neptune",
    "Pluton",
)
IMPORTANCE_TRANSIT_DU_MOMENT = 20
FICHIERS_LOG_RS = ("requete.json", "reponse_brute.txt", "usage.json", "mecanismes.json", "enjeux.json", "controles.json", "reprise_locale.json")
TAILLE_MAX_RAPPORT = 15 * 1024 * 1024
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dataclasses import asdict
import json
import os
import re
import swisseph as swe
import unicodedata
import uuid
from urllib.parse import urlsplit
from threading import Thread
import pdfplumber
from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from extensions import db
from models.espace_personnel import DecodageObservationMecanisme
from models.espace_personnel import AbonnementEspace, AnalysePersonnelle, CycleLunaire, CycleSolaire, DroitAnalyseAchetee, EmailCycleAbonnement, EnjeuAnnuel, EnjeuPeriode, EntreeJournal, MecanismeExploration, ObservationMecanisme, ProfilAstral, SectionAnalyse, SuggestionMecanisme, UtilisateurEspace
from utils.auth_espace import labo_local as mode_labo
from utils.auth_espace import administratrice_connectee, jeton_csrf_espace, ouvrir_session_espace, utilisateur_connecte, verifier_csrf_espace
from routes.auth_espace import enregistrer_routes_auth, ROUTES_PUBLIQUES_AUTH, ROUTES_AUTH
from utils.calcul_theme import calcul_theme
from utils.configurations_astrologiques import analyser_configurations_majeures
from utils.extraction_mecanismes_ia import generer_suggestions_avec_claude
from utils.preparation_mecanismes import (
    ExtractionMecanismesEnCours, preparer_sections_mecanismes, verrou_mecanismes,
)
from utils.exploration_rs import extraire_pages_rs, generer_enjeux_rs, lire_reponse_enjeux_rs, propositions_rs_a_verifier, verrou_extraction_rs
from utils.enjeux_annuels import actualiser_enjeux_email
from utils.extraction_enjeux_transits_ia import generer_enjeux_transits_avec_claude
from utils.extraction_enjeux_forces_defis_ia import generer_enjeux_forces_defis_avec_claude
from utils.interpretation_cycle_lunaire import generer_interpretation_avec_claude
from utils.analyse_sections import extraire_sections_analyse_karmique, extraire_sections_forces_defis, extraire_sections_point_astral, extraire_sections_profil_amoureux, extraire_sections_transits
from utils.revolution_lunaire import calculer_theme_revolution_lunaire, priorites_interpretation, prochaine_revolution_lunaire
from utils.cycles_abonnement import rattacher_cycle_lunaire_a_sa_rs
from utils.brouillon_email_cycle import TYPE_EMAIL_BOUSSOLE, preparer_brouillon_boussole, droits_email, generation_autorisee
from utils.mails_quinzaine import VERSION_CONTRAT, preparer_mails_mois, actualiser_mail_quinzaine
from utils.generation_mail_abonne import generer_mail_enregistre, journaux_mail, dossier_journaux_mail, FICHIERS_MAIL
from utils.email_cycle_abonnement import convertir_email_texte_en_html
from utils.acces_abonnement import acces_abonnement
from utils.avatars_espace import AVATARS_ESPACE
from utils.llm_client import ask_llm
from utils.email_sender import envoyer_email_avec_analyse
from utils.transits.calcul_transits import PLANETES_SWISSEPH, longitude_to_signe
from utils.transits.detecteurs import detecter_aspects
from utils.transits.maisons import extraire_cuspides
from utils.transits.synthese_brady import THEMES_MAISONS
from flask import g
from pathlib import Path
import tempfile
from utils.claude_espace import BlocTronqueError
from utils.email_espace import envoyer_email_avec_analyse
"""Première tranche de l'espace personnel : compte et connexion par e-mail."""

import os
import requests
import json
import math
import hmac
import secrets
import re
import hashlib
import io
import uuid
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import update

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, session, url_for

from extensions import db
from models.espace_personnel import (
    AbonnementEspace, AnalysePersonnelle, CycleLunaire, CycleSolaire, DroitAnalyseAchetee,
    EmailCycleAbonnement, EnjeuPeriode, EntreeJournal, FichierAnalyse,
    MecanismeExploration, ObservationMecanisme, ProfilAstral, SectionAnalyse, SuggestionMecanisme,
    UtilisateurEspace,
)
from utils.acces_abonnement import acces_abonnement
from utils.calcul_theme import calcul_theme
from utils.acces_espace import (
    activer_accompagnement_beta,
    consommer_lien_connexion,
    creer_lien_connexion,
    email_invite,
    lien_recent,
    trouver_ou_creer_utilisateur,
)
from utils.email_sender import envoyer_email_avec_analyse
from utils.stockage_espace import racine_privee_espace


espace_personnel_bp = Blueprint("espace_personnel", __name__, url_prefix="/mon-espace")
DUREE_SESSION_ESPACE = timedelta(days=14)


@espace_personnel_bp.record_once
def configurer_session_espace(etat):
    etat.app.permanent_session_lifetime = DUREE_SESSION_ESPACE
    etat.app.config["ESPACE_VERIFIER_FORMULAIRE_PUBLIC"] = verifier_turnstile
    etat.app.config["ESPACE_AUTORISER_INSCRIPTION"] = email_invite
    etat.app.config["ESPACE_APRES_CONNEXION"] = activer_accompagnement_beta

RESSENTIS_MECANISME = {
    "me_parle": "Ça me parle clairement",
    "parfois": "Ça me parle parfois",
    "a_observer": "Je ne sais pas encore",
    "ne_me_correspond_pas": "Je ne me reconnais pas",
    "incorrect": "Je pense que c’est incorrect",
}
STATUTS_MECANISME = {
    "a_explorer": "À explorer",
    "en_observation": "En observation",
    "recurrent": "Récurrent",
    "en_transformation": "En transformation",
    "apaise": "Apaisé",
    "probablement_depasse": "Probablement dépassé",
    "non_pertinent": "Non pertinent",
}

CATALOGUE_ANALYSES = (
    {"type": "point_astral_essentiel", "titre": "Point Astral Essentiel", "description": "Les grandes lignes de ton fonctionnement et de tes ressources."},
    {"type": "racines_familiales", "titre": "Racines familiales", "description": "Les héritages et les dynamiques de ton histoire familiale."},
    {"type": "profil_amoureux", "titre": "Profil amoureux", "description": "Ta manière d’aimer et d’entrer en relation."},
    {"type": "forces_defis", "titre": "Mes Potentiels & Défis", "description": "Tes ressources naturelles et tes tensions de fond."},
    {"type": "analyse_karmique", "titre": "Analyse karmique", "description": "Les axes profonds d’évolution de ton thème."},
    {"type": "transits", "titre": "Transits", "description": "Les énergies qui activent ton thème actuellement."},
)
TYPES_EXTRACTION_MECANISMES = {
    "racines_familiales", "profil_amoureux", "forces_defis", "analyse_karmique", "transits",
}
TITRES_PDF_PAR_ANALYSE = {
    "point_astral_essentiel": ("point astral", "flash astral"),
    "racines_familiales": ("racines familiales", "point astral racines", "point astral", "flash astral"),
    "profil_amoureux": ("profil amoureux",),
    "forces_defis": ("potentiels defis", "potentiel defis", "forces defis"),
    "analyse_karmique": ("analyse karmique",),
    "transits": ("point transits", "flash transits", "transits"),
    "revolution_solaire": ("revolution solaire",),
}


def _texte_pdf_normalise(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte.casefold()).split())


def _verifier_rapport_fda(contenu, type_analyse):
    import pdfplumber

    if not contenu.startswith(b"%PDF-") or len(contenu) > 15 * 1024 * 1024:
        raise ValueError("Le rapport PDF est invalide ou dépasse 15 Mo.")
    try:
        with pdfplumber.open(io.BytesIO(contenu)) as rapport:
            texte = _texte_pdf_normalise(" ".join((page.extract_text() or "") for page in rapport.pages[:3]))
    except Exception as erreur:
        raise ValueError("Le PDF ne peut pas être lu.") from erreur
    titres = TITRES_PDF_PAR_ANALYSE[type_analyse]
    if "les fous d astro" not in texte or not any(titre in texte for titre in titres):
        raise ValueError("Ce PDF ne correspond pas à l’analyse Les Fous d’Astro choisie.")


def _compte_connecte():
    return utilisateur_connecte()


def _jeton_formulaire_portail():
    jeton = session.get("espace_formulaire_csrf")
    if not jeton:
        jeton = secrets.token_urlsafe(32)
        session["espace_formulaire_csrf"] = jeton
    return jeton


def _verifier_formulaire_portail():
    if request.form.get('csrf_token'):
        verifier_csrf_espace()
        return True
    return hmac.compare_digest(
        request.form.get("espace_csrf", ""), _jeton_formulaire_portail()
    )





def _photo_transits_journal(theme, jour):
    """Fige les positions et contacts calculés au moment de la note, sans IA."""
    from dataclasses import asdict
    import swisseph as swe
    from utils.transits.calcul_transits import PLANETES_SWISSEPH, longitude_to_signe
    from utils.transits.detecteurs import detecter_aspects
    from utils.transits.maisons import extraire_cuspides

    instant = datetime.combine(jour, time(12, 0))
    julien = swe.julday(instant.year, instant.month, instant.day, 12)
    positions = {}
    for nom in ("Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"):
        coordonnees = swe.calc_ut(julien, PLANETES_SWISSEPH[nom])[0]
        positions[nom] = {
            **longitude_to_signe(coordonnees[0] % 360),
            "retrograde": coordonnees[3] < 0,
            "vitesse": round(coordonnees[3], 6),
        }
    maitre = theme.get("maitre_ascendant")
    if isinstance(maitre, dict):
        maitre = maitre.get("nom")
    aspects = detecter_aspects(
        positions, theme.get("planetes", {}), extraire_cuspides(theme),
        theme.get("house_rulers_map", {}), maitre_ascendant=maitre,
        angles_deg=theme.get("angles_deg", {}),
    )
    aspects.sort(key=lambda transit: (-transit.importance, transit.orbe))
    return {"date_calcul": instant.isoformat(), "positions": positions,
            "transits": [asdict(transit) for transit in aspects]}


def _transits_visibles_journal(photo):
    from utils.transits.synthese_brady import THEMES_MAISONS

    groupes = {}
    for transit in (photo or {}).get("transits", []):
        if not isinstance(transit, dict):
            continue
        planete = transit.get("planete_transit") or "Transit"
        groupes.setdefault(planete, []).append(transit)
    resultat = {"climat_fond": [], "declencheurs": []}
    lentes = {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}
    for planete, transits in groupes.items():
        enrichis = []
        for transit in sorted(transits, key=lambda item: (-item.get("importance", 0), item.get("orbe", 999))):
            contexte = transit.get("contexte") or {}
            maisons_cible = contexte.get("maisons_gouvernees_natale") or []
            enrichis.append({
                **transit,
                "maison_cible": contexte.get("maison_natale_planete"),
                "theme_maison_cible": THEMES_MAISONS.get(contexte.get("maison_natale_planete")),
                "maisons_dirigees_cible": [
                    {"maison": maison, "theme": THEMES_MAISONS.get(maison, "domaine à explorer")}
                    for maison in maisons_cible if isinstance(maison, int)
                ],
            })
        contexte = enrichis[0].get("contexte") or {}
        maisons_planete = contexte.get("maisons_gouvernees_transit") or []
        groupe = {
            "planete": planete, "aspects": enrichis,
            "intensite_max": max(t.get("importance", 0) for t in enrichis),
            "orbe_min": min(t.get("orbe", 999) for t in enrichis),
            "maison_transitee": contexte.get("maison_transit"),
            "theme_maison_transitee": THEMES_MAISONS.get(contexte.get("maison_transit")),
            "maison_natale_planete": contexte.get("maison_natale_transit"),
            "theme_maison_natale_planete": THEMES_MAISONS.get(contexte.get("maison_natale_transit")),
            "maisons_dirigees_planete": [
                {"maison": maison, "theme": THEMES_MAISONS.get(maison, "domaine à explorer")}
                for maison in maisons_planete if isinstance(maison, int)
            ],
        }
        resultat["climat_fond" if planete in lentes else "declencheurs"].append(groupe)
    for liste in resultat.values():
        liste.sort(key=lambda groupe: (-groupe["intensite_max"], groupe["orbe_min"]))
    return resultat


def import_profil_autorise(utilisateur):
    """L'import du labo reste limité aux deux comptes de validation."""
    autorises = os.getenv(
        "ESPACE_IMPORT_EMAILS", "cecilecl@gmail.com,cecilecl.cyp@gmail.com"
    )
    return utilisateur.email.lower() in {
        email.strip().lower() for email in autorises.split(",") if email.strip()
    }


def import_profil_disponible(utilisateur):
    """L'import de test reste visible après une saisie manuelle du thème natal."""
    if not import_profil_autorise(utilisateur):
        return False
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    return abonnement is None


def verifier_turnstile():
    jeton = (request.form.get("cf-turnstile-response") or "").strip()
    secret = (os.getenv("TURNSTILE_SECRET_KEY") or "").strip()
    if not jeton or not secret:
        return False
    try:
        reponse = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": jeton, "remoteip": request.remote_addr},
            timeout=8,
        )
        resultat = reponse.json()
    except (requests.RequestException, ValueError):
        return False
    return resultat.get("success") is True and resultat.get("hostname") in {
        "lesfousdastro.fr", "www.lesfousdastro.fr"
    }








@espace_personnel_bp.route("/")
def accueil():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        session.pop("utilisateur_espace_id", None)
        return redirect(url_for("espace_personnel.connexion"))
    try:
        activer_accompagnement_beta(utilisateur)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Activation de l'accompagnement bêta impossible")
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits_abonnement = acces_abonnement(abonnement)
    entrees = (
        EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id)
        .order_by(EntreeJournal.date_observation.desc()).all()
    )
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).filter(AnalysePersonnelle.statut != "remplacee").all()
    analyse_ids = [analyse.id for analyse in analyses]
    nb_mecanismes_en_cours = 0
    if analyse_ids:
        nb_mecanismes_en_cours = (
            MecanismeExploration.query
            .filter(MecanismeExploration.analyse_id.in_(analyse_ids))
            .filter(~MecanismeExploration.statut.in_(("probablement_depasse", "non_pertinent")))
            .count()
        )
    cycle_solaire = cycle_lunaire = None
    date_rs_locale = date_cycle_locale = None
    if profil_astral:
        cycle_solaire = (
            CycleSolaire.query.filter_by(profil_id=profil_astral.id)
            .order_by(CycleSolaire.debut_cycle_utc.desc()).first()
        )
        cycle_lunaire = (
            CycleLunaire.query.filter_by(profil_id=profil_astral.id)
            .order_by(CycleLunaire.debut_cycle_utc.desc()).first()
        )
        try:
            fuseau = ZoneInfo(profil_astral.fuseau_cycles or profil_astral.fuseau_horaire)
            if cycle_solaire:
                date_rs_locale = cycle_solaire.debut_cycle_utc.replace(
                    tzinfo=timezone.utc
                ).astimezone(fuseau)
            if cycle_lunaire:
                date_cycle_locale = cycle_lunaire.debut_cycle_utc.replace(
                    tzinfo=timezone.utc
                ).astimezone(fuseau)
        except (TypeError, ValueError, KeyError):
            current_app.logger.warning("Dates des cycles indisponibles dans le tableau de bord")

    resume_contacts = []
    resume_indisponible = False
    nombre_transits_collectifs = None
    try:
        from utils.ciel_collectif import ciel_collectif_mois
        aujourd_hui = datetime.now(ZoneInfo("Europe/Paris")).date()
        ciel = ciel_collectif_mois(aujourd_hui.year, aujourd_hui.month, jour_reference=aujourd_hui)
        nombre_transits_collectifs = len(ciel["evenements"])
    except Exception:
        current_app.logger.exception("Repères du ciel collectif indisponibles")
    if profil_astral and profil_astral.theme_natal and droits_abonnement["transits_personnalises"]:
        try:
            from utils.resume_calendrier import resume_du_jour
            fuseau = profil_astral.fuseau_cycles or profil_astral.fuseau_horaire
            resume_contacts = resume_du_jour(
                profil_astral.theme_natal,
                datetime.now(ZoneInfo(fuseau)).date().isoformat(),
                fuseau,
            )
        except Exception:
            current_app.logger.exception("Résumé du calendrier indisponible")
            resume_indisponible = True
    return render_template(
        "espace_personnel/accueil.html",
        utilisateur=utilisateur,
        utilisateur_espace=utilisateur,
        profil=profil_astral,
        droits_abonnement=droits_abonnement,
        entrees=entrees,
        analyses=analyses,
        nb_mecanismes_en_cours=nb_mecanismes_en_cours,
        resume_contacts=resume_contacts,
        resume_indisponible=resume_indisponible,
        nombre_transits_collectifs=nombre_transits_collectifs,
        cycle_solaire=cycle_solaire,
        cycle_lunaire=cycle_lunaire,
        date_rs_locale=date_rs_locale,
        date_cycle_locale=date_cycle_locale,
    )


@espace_personnel_bp.route("/ciel-du-moment")
def ciel_collectif():
    """Affiche les aspects du ciel actuel, sans données de naissance."""
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    from utils.ciel_collectif import ciel_collectif_mois
    from utils.figures_ciel_collectif import figures_ciel_collectif

    aujourd_hui = datetime.now(ZoneInfo("Europe/Paris")).date()
    mois_brut = request.args.get("mois", aujourd_hui.strftime("%Y-%m"))
    try:
        annee, mois = map(int, mois_brut.split("-"))
        premier = date(annee, mois, 1)
        jour_brut = request.args.get("jour")
        jour_choisi = date.fromisoformat(jour_brut) if jour_brut else (
            aujourd_hui if (aujourd_hui.year, aujourd_hui.month) == (annee, mois) else premier
        )
        if (jour_choisi.year, jour_choisi.month) != (annee, mois):
            abort(400)
        ciel = ciel_collectif_mois(annee, mois, jour_reference=jour_choisi,
                                  inclure_stations=True)
    except (TypeError, ValueError):
        abort(400)
    figures_jour = figures_ciel_collectif(jour_choisi)
    precedent = premier - timedelta(days=1)
    suivant = (premier.replace(day=28) + timedelta(days=4)).replace(day=1)
    return render_template(
        "espace_personnel/ciel_collectif.html",
        utilisateur_espace=utilisateur,
        ciel=ciel,
        jour_choisi=jour_choisi,
        figures_jour=figures_jour,
        mois=premier,
        titre_mois=("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                    "août", "septembre", "octobre", "novembre", "décembre")[mois - 1],
        precedent=precedent.strftime("%Y-%m"),
        suivant=suivant.strftime("%Y-%m"),
        dernier_jour=(suivant - timedelta(days=1)).isoformat(),
    )


@espace_personnel_bp.route("/accompagnement")
def accompagnement():
    """Réunit les repères déjà calculés sans déclencher de génération IA."""
    utilisateur = _utilisateur_espace_courant()
    abonnement = AbonnementEspace.query.filter_by(
        utilisateur_id=utilisateur.id
    ).first()
    droits_abonnement = acces_abonnement(abonnement)
    profil_astral = _profil_astral_courant()
    maintenant = datetime.now(timezone.utc)

    cycle_solaire = None
    cycle_lunaire = None
    prochain_cycle_lunaire = None
    interpretation_cycle = {}
    dernier_email = None

    if profil_astral:
        cycle_solaire = (
            CycleSolaire.query
            .filter(
                CycleSolaire.profil_id == profil_astral.id,
                CycleSolaire.debut_cycle_utc <= maintenant,
                CycleSolaire.fin_cycle_utc > maintenant,
            )
            .order_by(CycleSolaire.debut_cycle_utc.desc())
            .first()
        )
        cycle_lunaire = (
            CycleLunaire.query
            .filter(
                CycleLunaire.profil_id == profil_astral.id,
                CycleLunaire.debut_cycle_utc <= maintenant,
                CycleLunaire.fin_cycle_utc > maintenant,
            )
            .order_by(CycleLunaire.debut_cycle_utc.desc())
            .first()
        )
        prochain_cycle_lunaire = (
            CycleLunaire.query
            .filter(
                CycleLunaire.profil_id == profil_astral.id,
                CycleLunaire.debut_cycle_utc > maintenant,
            )
            .order_by(CycleLunaire.debut_cycle_utc.asc())
            .first()
        )
        if cycle_lunaire and cycle_lunaire.interpretation:
            try:
                interpretation_cycle = json.loads(cycle_lunaire.interpretation)
            except (TypeError, ValueError):
                interpretation_cycle = {}
        dernier_email = (
            EmailCycleAbonnement.query
            .filter_by(profil_id=profil_astral.id)
            .order_by(EmailCycleAbonnement.date_creation.desc())
            .first()
        )

    # Ne transmettre au tableau de bord que le suivi inclus dans la formule.
    # Les archives restent accessibles par leurs routes propriétaires.
    if not droits_abonnement["revolution_solaire"]:
        cycle_solaire = None
    if not droits_abonnement["cycle_lunaire"]:
        cycle_lunaire = None
        prochain_cycle_lunaire = None
        interpretation_cycle = {}
    if not isinstance(interpretation_cycle, dict):
        interpretation_cycle = {}

    enjeux_fond = []
    enjeux_moment = []
    enjeux_rows = (
        db.session.query(EnjeuPeriode, AnalysePersonnelle)
        .join(AnalysePersonnelle, AnalysePersonnelle.id == EnjeuPeriode.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur.id)
        .order_by(AnalysePersonnelle.date_creation.desc(), EnjeuPeriode.ordre.asc())
        .all()
    )
    for enjeu, analyse in enjeux_rows:
        donnees = {"objet": enjeu, "analyse": analyse}
        if analyse.type_analyse == "forces_defis":
            enjeux_fond.append(donnees)
        else:
            enjeux_moment.append(donnees)

    dernieres_entrees = (
        EntreeJournal.query
        .filter_by(utilisateur_id=utilisateur.id)
        .order_by(EntreeJournal.date_observation.desc())
        .limit(3)
        .all()
    )

    return render_template(
        "espace_personnel/accompagnement.html",
        utilisateur_espace=utilisateur,
        profil=profil_astral,
        cycle_solaire=cycle_solaire,
        cycle_lunaire=cycle_lunaire,
        prochain_cycle_lunaire=prochain_cycle_lunaire,
        interpretation_cycle=interpretation_cycle,
        enjeux_fond=enjeux_fond,
        enjeux_moment=enjeux_moment,
        dernieres_entrees=dernieres_entrees,
        dernier_email=dernier_email,
        droits_abonnement=droits_abonnement,
    )


@espace_personnel_bp.route("/laboratoire")
def laboratoire():
    utilisateur = _utilisateur_espace_courant()
    mecanismes_tous = (
        MecanismeExploration.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur.id)
        .order_by(MecanismeExploration.date_modification.desc())
        .all()
    )
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).all()
    analyses_par_id = {analyse.id: analyse for analyse in analyses}
    suivis_par_mecanisme = {}
    observations = (
        ObservationMecanisme.query
        .join(MecanismeExploration, MecanismeExploration.id == ObservationMecanisme.mecanisme_id)
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur.id)
        .order_by(ObservationMecanisme.date_observation.desc())
        .all()
    )
    for observation in observations:
        suivi = suivis_par_mecanisme.setdefault(
            observation.mecanisme_id,
            {"nombre": 0, "derniere_date": observation.date_observation},
        )
        suivi["nombre"] += 1
    statuts_termines = {"apaise", "probablement_depasse", "non_pertinent"}
    analyse_selectionnee = request.args.get("analyse", type=int)
    statut_selectionne = request.args.get("statut", "").strip()
    actifs_seulement = request.args.get("actifs") == "1"
    jamais_observes = request.args.get("jamais_observes") == "1"
    if statut_selectionne not in STATUTS_MECANISME:
        statut_selectionne = ""

    mecanismes = [
        mecanisme
        for mecanisme in mecanismes_tous
        if (not analyse_selectionnee or mecanisme.analyse_id == analyse_selectionnee)
        and (not statut_selectionne or mecanisme.statut == statut_selectionne)
        and (not actifs_seulement or mecanisme.statut not in statuts_termines)
        and (not jamais_observes or mecanisme.id not in suivis_par_mecanisme)
    ]
    statistiques = {
        "en_cours": sum(
            mecanisme.statut not in statuts_termines
            for mecanisme in mecanismes_tous
        ),
        "en_transformation": sum(
            mecanisme.statut == "en_transformation"
            for mecanisme in mecanismes_tous
        ),
        "depasses": sum(
            mecanisme.statut == "probablement_depasse"
            for mecanisme in mecanismes_tous
        ),
    }
    return render_template(
        "espace_personnel/laboratoire.html",
        mecanismes=mecanismes,
        analyses_par_id=analyses_par_id,
        suivis_par_mecanisme=suivis_par_mecanisme,
        ressentis=RESSENTIS_MECANISME,
        statuts=STATUTS_MECANISME,
        statistiques=statistiques,
        analyses=analyses,
        analyse_selectionnee=analyse_selectionnee,
        statut_selectionne=statut_selectionne,
        actifs_seulement=actifs_seulement,
        jamais_observes=jamais_observes,
        filtres_actifs=bool(
            analyse_selectionnee
            or statut_selectionne
            or actifs_seulement
            or jamais_observes
        ),
    )


@espace_personnel_bp.route("/suggestions/<int:suggestion_id>/accepter", methods=["POST"])
def accepter_suggestion(suggestion_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    if not _verifier_formulaire_portail():
        abort(400)
    suggestion = (
        SuggestionMecanisme.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == SuggestionMecanisme.analyse_id)
        .filter(
            SuggestionMecanisme.id == suggestion_id,
            AnalysePersonnelle.utilisateur_id == utilisateur.id,
            AnalysePersonnelle.statut != "remplacee",
        )
        .first_or_404()
    )
    if suggestion.statut != "proposee":
        flash("Cette piste a déjà été traitée.", "error")
    else:
        try:
            manifestations = json.loads(suggestion.manifestations_possibles or "[]")
            if not isinstance(manifestations, list):
                manifestations = []
        except (TypeError, ValueError):
            manifestations = []
        reclamation = db.session.execute(
            update(SuggestionMecanisme)
            .where(SuggestionMecanisme.id == suggestion.id, SuggestionMecanisme.statut == "proposee")
            .values(statut="acceptee")
        )
        if reclamation.rowcount == 1:
            db.session.add(MecanismeExploration(
                analyse_id=suggestion.analyse_id,
                titre=majuscule_initiale(suggestion.titre),
                extrait_source=suggestion.extrait_source,
                hypothese=suggestion.hypothese,
                effets_possibles="\n".join(f"• {item}" for item in manifestations) or None,
                ressenti="a_observer",
                statut="a_explorer",
            ))
            db.session.commit()
            flash("Cette piste a été ajoutée à ton Labo.", "success")
        else:
            db.session.rollback()
            flash("Cette piste a déjà été traitée.", "error")
    return redirect(
        url_for("espace_personnel.explorer_analyse", analyse_id=suggestion.analyse_id)
        + f"#suggestion-{suggestion.id}"
    )


@espace_personnel_bp.route("/suggestions/<int:suggestion_id>/rejeter", methods=["POST"])
def rejeter_suggestion(suggestion_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    if not _verifier_formulaire_portail():
        abort(400)
    suggestion = (
        SuggestionMecanisme.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == SuggestionMecanisme.analyse_id)
        .filter(
            SuggestionMecanisme.id == suggestion_id,
            AnalysePersonnelle.utilisateur_id == utilisateur.id,
            AnalysePersonnelle.statut != "remplacee",
        )
        .first_or_404()
    )
    if suggestion.statut == "proposee":
        suggestion.statut = "rejetee"
        db.session.commit()
        flash("Cette piste a été écartée.", "success")
    else:
        flash("Cette piste a déjà été traitée.", "error")
    return redirect(url_for("espace_personnel.laboratoire") + "#suggestions-ia")


def _mecanisme_du_compte(mecanisme_id, utilisateur_id):
    return (
        MecanismeExploration.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(
            MecanismeExploration.id == mecanisme_id,
            AnalysePersonnelle.utilisateur_id == utilisateur_id,
        ).first_or_404()
    )


@espace_personnel_bp.route("/mecanismes/<int:mecanisme_id>", methods=["GET", "POST"])
def fiche_mecanisme(mecanisme_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    mecanisme = _mecanisme_du_compte(mecanisme_id, utilisateur.id)
    analyse = db.session.get(AnalysePersonnelle, mecanisme.analyse_id)
    if request.method == "POST":
        if not _verifier_formulaire_portail():
            abort(400)
        titre = majuscule_initiale(request.form.get("titre", ""))
        hypothese = request.form.get("hypothese", "").strip()
        ressenti = request.form.get("ressenti", "").strip()
        statut = request.form.get("statut", "").strip()
        if (
            not titre or len(titre) > 200 or not hypothese
            or ressenti not in RESSENTIS_MECANISME
            or statut not in STATUTS_MECANISME
        ):
            flash("Vérifie le titre, l’hypothèse, le ressenti et le statut.", "error")
        else:
            mecanisme.titre = titre
            mecanisme.hypothese = hypothese
            mecanisme.ressenti = ressenti
            mecanisme.statut = statut
            for champ in (
                "extrait_source", "effets_possibles", "indices_pour", "elements_contraires",
                "situations_observees", "piste_experimentation",
            ):
                setattr(mecanisme, champ, request.form.get(champ, "").strip() or None)
            db.session.commit()
            flash("Ton exploration a été mise à jour.", "success")
            return redirect(url_for("espace_personnel.fiche_mecanisme", mecanisme_id=mecanisme.id))
    observations = (
        ObservationMecanisme.query.filter_by(mecanisme_id=mecanisme.id)
        .order_by(ObservationMecanisme.date_observation.desc()).all()
    )
    observation_id = request.args.get("modifier_observation", type=int)
    observation_a_modifier = next(
        (observation for observation in observations if observation.id == observation_id), None
    )
    return render_template(
        "espace_personnel/fiche_mecanisme.html",
        analyse=analyse, mecanisme=mecanisme,
        ressentis=RESSENTIS_MECANISME, statuts=STATUTS_MECANISME,
        mode_modification=request.args.get("mode") == "modifier",
        observations_mecanisme=observations,
        synthese_evolution={
            "nombre_observations": len(observations),
            "derniere_observation": observations[0].date_observation if observations else None,
            "reactions_testees": [o.reaction_testee for o in observations if o.reaction_testee],
        },
        afficher_ajout_observation=request.args.get("ajouter_observation") == "1",
        observation_a_modifier=observation_a_modifier,
        date_du_jour=datetime.now().date().isoformat(),
        espace_csrf=_jeton_formulaire_portail(),
    )


def _champs_observation():
    try:
        date_observation = datetime.strptime(request.form.get("date_observation", ""), "%Y-%m-%d")
    except ValueError:
        abort(400)
    situation = request.form.get("situation", "").strip()
    if not situation:
        abort(400)
    champs = {"date_observation": date_observation, "situation": situation}
    for nom in (
        "reaction_automatique", "indice_pour", "element_contraire",
        "reaction_testee", "resultat_obtenu", "notes_libres",
    ):
        champs[nom] = request.form.get(nom, "").strip() or None
    return champs


@espace_personnel_bp.route("/mecanismes/<int:mecanisme_id>/observations/ajouter", methods=["POST"])
def ajouter_observation_mecanisme(mecanisme_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    mecanisme = _mecanisme_du_compte(mecanisme_id, utilisateur.id)
    if not _verifier_formulaire_portail():
        abort(400)
    observation = ObservationMecanisme(mecanisme_id=mecanisme.id, **_champs_observation())
    db.session.add(observation)
    db.session.commit()
    return redirect(url_for("espace_personnel.fiche_mecanisme", mecanisme_id=mecanisme.id) + "#journal-mecanisme")


@espace_personnel_bp.route("/observations-mecanisme/<int:observation_id>/modifier", methods=["POST"])
def modifier_observation_mecanisme(observation_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    observation = db.session.get(ObservationMecanisme, observation_id)
    if observation is None:
        abort(404)
    mecanisme = _mecanisme_du_compte(observation.mecanisme_id, utilisateur.id)
    if not _verifier_formulaire_portail():
        abort(400)
    for nom, valeur in _champs_observation().items():
        if nom in {"element_contraire", "reaction_testee"} and nom not in request.form:
            continue
        setattr(observation, nom, valeur)
    db.session.commit()
    return redirect(url_for("espace_personnel.fiche_mecanisme", mecanisme_id=mecanisme.id) + f"#observation-{observation.id}")


@espace_personnel_bp.route("/profil", methods=["GET", "POST"])
def profil():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        session.pop("utilisateur_espace_id", None)
        return redirect(url_for("espace_personnel.connexion"))

    csrf = session.get("espace_profil_csrf")
    if not csrf:
        csrf = secrets.token_urlsafe(32)
        session["espace_profil_csrf"] = csrf
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("profil_csrf", ""), csrf):
            return render_template(
                "espace_personnel/profil.html", profil=profil_astral,
                utilisateur=utilisateur, saisie=request.form,
                peut_importer=import_profil_disponible(utilisateur),
                erreur="Le formulaire a expiré. Recharge la page et réessaie.",
            ), 400
        prenom = (request.form.get("prenom") or "").strip()
        ville = (request.form.get("ville_naissance") or "").strip()
        fuseau = (request.form.get("fuseau_horaire") or "").strip()
        try:
            naissance = datetime.strptime(request.form.get("date_naissance", ""), "%Y-%m-%d").date()
            heure = datetime.strptime(request.form.get("heure_naissance", ""), "%H:%M").time()
            latitude = float(request.form.get("latitude", ""))
            longitude = float(request.form.get("longitude", ""))
            ZoneInfo(fuseau)
            if (
                not prenom or len(prenom) > 100 or not ville or len(ville) > 200
                or naissance > date.today() or not math.isfinite(latitude)
                or not math.isfinite(longitude) or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ValueError
        except (TypeError, ValueError, KeyError):
            return render_template(
                "espace_personnel/profil.html", profil=profil_astral,
                utilisateur=utilisateur, saisie=request.form,
                peut_importer=import_profil_disponible(utilisateur),
                erreur="Vérifie la date, l’heure et choisis une ville dans les suggestions.",
            ), 400

        try:
            theme = calcul_theme(
                nom=prenom,
                date_naissance=naissance.isoformat(),
                heure_naissance=heure.strftime("%H:%M"),
                lieu_naissance=ville,
                lat=latitude,
                lon=longitude,
                tzid=fuseau,
            )
            theme_json = json.dumps(theme, ensure_ascii=False, default=str)
        except Exception:
            current_app.logger.exception("Calcul du thème du profil impossible")
            return render_template(
                "espace_personnel/profil.html", profil=profil_astral,
                utilisateur=utilisateur, saisie=request.form,
                peut_importer=import_profil_disponible(utilisateur),
                erreur="Le thème n’a pas pu être calculé avec ces coordonnées. Réessaie plus tard.",
            ), 503

        if profil_astral is None:
            profil_astral = ProfilAstral(utilisateur_id=utilisateur.id)
            db.session.add(profil_astral)
        profil_astral.prenom = prenom
        profil_astral.date_naissance = naissance
        profil_astral.heure_naissance = heure
        profil_astral.ville_naissance = ville
        profil_astral.fuseau_horaire = fuseau
        profil_astral.latitude = latitude
        profil_astral.longitude = longitude
        profil_astral.theme_natal = theme_json
        profil_astral.date_calcul_theme = datetime.now(timezone.utc)
        utilisateur.prenom = prenom
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Enregistrement du profil impossible")
            return render_template(
                "espace_personnel/profil.html", profil=profil_astral,
                utilisateur=utilisateur, saisie=request.form,
                peut_importer=import_profil_disponible(utilisateur),
                erreur="Le profil n’a pas pu être enregistré. Réessaie plus tard.",
            ), 503
        flash("Ton profil astral est enregistré.", "success")
        return redirect(url_for("espace_personnel.profil"))

    return render_template(
        "espace_personnel/profil.html", profil=profil_astral,
        utilisateur=utilisateur, saisie=None,
        peut_importer=import_profil_disponible(utilisateur),
    )


@espace_personnel_bp.route("/profil/ville-cycles", methods=["POST"])
def modifier_ville_cycles():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        return redirect(url_for("espace_personnel.profil"))
    try:
        ville = request.form.get("ville_cycles", "").strip()
        fuseau = request.form.get("fuseau_cycles", "").strip()
        latitude = float(request.form.get("latitude_cycles", ""))
        longitude = float(request.form.get("longitude_cycles", ""))
        ZoneInfo(fuseau)
        if (
            not ville or len(ville) > 200 or not math.isfinite(latitude)
            or not math.isfinite(longitude) or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError
    except (TypeError, ValueError, KeyError):
        flash("Choisis une ville valide dans les suggestions.", "error")
        return redirect(url_for("espace_personnel.profil") + "#ville-cycles")
    profil_astral.ville_cycles = ville
    profil_astral.fuseau_cycles = fuseau
    profil_astral.latitude_cycles = latitude
    profil_astral.longitude_cycles = longitude
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Ville des cycles impossible à enregistrer")
        flash("La ville des cycles n’a pas pu être enregistrée.", "error")
    else:
        flash("La ville de tes cycles est enregistrée.", "success")
    return redirect(url_for("espace_personnel.profil") + "#ville-cycles")


@espace_personnel_bp.route("/profil/situation", methods=["POST"])
def modifier_situation_actuelle():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        return redirect(url_for("espace_personnel.profil"))
    champs = (
        "situation_foyer", "situation_amour", "situation_travail",
        "situation_enfants", "situation_sante", "preoccupation_actuelle",
    )
    donnees = {champ: request.form.get(champ, "").strip() for champ in champs}
    if any(len(valeur) > 5000 for valeur in donnees.values()):
        flash("Un des textes est trop long (5 000 caractères maximum).", "error")
        return redirect(url_for("espace_personnel.profil") + "#situation-actuelle")
    for champ, valeur in donnees.items():
        setattr(profil_astral, champ, valeur or None)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Situation actuelle impossible à enregistrer")
        flash("Ta situation actuelle n’a pas pu être enregistrée.", "error")
    else:
        flash("Ta situation actuelle est enregistrée.", "success")
    return redirect(url_for("espace_personnel.profil") + "#situation-actuelle")


@espace_personnel_bp.route("/ciel-natal")
def ciel_natal():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    theme = None
    if profil_astral and profil_astral.theme_natal:
        try:
            theme = json.loads(profil_astral.theme_natal)
            if not isinstance(theme, dict):
                theme = None
        except (TypeError, ValueError):
            pass
    return render_template("espace_personnel/ciel_natal.html", profil=profil_astral, theme=theme)


def _rendre_journal(utilisateur, **contexte):
    """Journal à deux colonnes : une seule entrée ouverte et l’index privé du membre."""
    donnees = {
        "entree_ouverte": None, "mode_modification": False,
        "date_du_jour": datetime.now().date().isoformat(),
        "contact_source": None, "cycle_source": None, "enjeu_source": None,
        "interpretation_cycle": None, "domaines_contact": [],
        "entrees": EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id)
            .order_by(EntreeJournal.date_observation.desc(), EntreeJournal.id.desc()).all(),
        **_contexte_mecanismes_journal(utilisateur.id),
    }
    donnees.update(contexte)
    return render_template("espace_personnel/journal.html", **donnees)



@espace_personnel_bp.route("/journal", methods=["GET", "POST"])
def journal():
    utilisateur = _utilisateur_espace_courant()
    profil_astral = _profil_astral_courant()
    entree_ouverte = None
    mode_modification = False
    if request.method == "GET" and "entree" in request.args:
        entree_id = request.args.get("entree", type=int)
        if not entree_id or entree_id < 1:
            abort(400)
        entree_ouverte = _entree_courante_ou_404(entree_id)
        mode_modification = request.args.get("mode") == "modifier"
    date_prefill = datetime.now().date().isoformat()
    date_demandee = request.form.get("date_observation") if request.method == "POST" else request.args.get("date")
    if date_demandee:
        try:
            date_prefill = datetime.strptime(date_demandee, "%Y-%m-%d").date().isoformat()
        except (ValueError, TypeError):
            if request.method == "GET": abort(400)
    from utils.journal_contact import contact_du_jour, DOMAINES
    source = request.form if request.method == "POST" else request.args
    contact_source = None
    if source.get("contact_planete"):
        try:
            if not profil_astral or not profil_astral.theme_natal: raise ValueError()
            contact_source = contact_du_jour(json.loads(profil_astral.theme_natal), date_prefill,
                profil_astral.fuseau_cycles or profil_astral.fuseau_horaire or "Europe/Paris",
                source.get("contact_planete"), source.get("contact_point"), source.get("contact_aspect"))
        except (ValueError, TypeError, KeyError):
            abort(400, description="Ce contact n’est pas actif pour ton thème à cette date.")
    cycle_source = None
    enjeu_source = None
    enjeu_id_brut = (
        request.form.get("enjeu_periode_id", "").strip()
        if request.method == "POST"
        else request.args.get("enjeu_id", "").strip()
    )
    if enjeu_id_brut:
        try:
            enjeu_id = int(enjeu_id_brut)
        except (TypeError, ValueError):
            enjeu_id = None
        if enjeu_id is not None:
            enjeu_source = (
                EnjeuPeriode.query
                .join(AnalysePersonnelle, AnalysePersonnelle.id == EnjeuPeriode.analyse_id)
                .filter(
                    EnjeuPeriode.id == enjeu_id,
                    AnalysePersonnelle.utilisateur_id == utilisateur.id,
                )
                .first()
            )
    cycle_id_brut = (
        request.form.get("cycle_lunaire_id", "").strip()
        if request.method == "POST"
        else request.args.get("cycle_id", "").strip()
    )
    if cycle_id_brut:
        try:
            cycle_id = int(cycle_id_brut)
        except (TypeError, ValueError):
            cycle_id = None
        if cycle_id is not None and profil_astral:
            cycle_source = CycleLunaire.query.filter_by(
                id=cycle_id,
                profil_id=profil_astral.id,
            ).first()

    if request.method == "POST":
        date_observation_str = request.form.get("date_observation", "").strip()
        niveau_energie_str = request.form.get("niveau_energie", "").strip()

        try:
            date_observation = datetime.strptime(
                date_observation_str,
                "%Y-%m-%d",
            )
            niveau_energie = (
                int(niveau_energie_str)
                if niveau_energie_str
                else None
            )
            if niveau_energie is not None and not 1 <= niveau_energie <= 10:
                raise ValueError
        except (TypeError, ValueError):
            flash("Vérifie la date et, si tu l’as indiqué, le niveau d’énergie.", "error")
        else:
            try:
                est_periode, date_fin_periode = _dates_periode_journal(request.form, date_observation)
                mecanismes_choisis = _mecanismes_choisis_journal(request.form, utilisateur.id)
                if request.form.get("action") == "decoder" and not mecanismes_choisis:
                    raise ValueError("Coche au moins un mécanisme à décoder dans « Aller plus loin ».")
            except ValueError as erreur:
                flash(str(erreur), "error")
                return _rendre_journal(
                    utilisateur,
                    date_du_jour=date_prefill, contact_source=contact_source,
                    domaines_contact=DOMAINES, cycle_source=cycle_source,
                    enjeu_source=enjeu_source,
                    interpretation_cycle=json.loads(cycle_source.interpretation)
                    if cycle_source and cycle_source.interpretation else None,
                )
            photo_transits = None
            if profil_astral and profil_astral.theme_natal:
                try:
                    theme_natal = json.loads(profil_astral.theme_natal)
                    photo_transits = json.dumps(
                        _calculer_photo_transits(theme_natal, date_observation),
                        ensure_ascii=False,
                        default=str,
                    )
                except Exception:
                    photo_transits = None

            if contact_source:
                photo = json.loads(photo_transits) if photo_transits else {}
                photo["contact_journal"] = {**contact_source,
                    "domaine": request.form.get("domaine") if request.form.get("domaine") in DOMAINES else None,
                    "rien_particulier": request.form.get("rien_particulier") == "oui"}
                photo_transits = json.dumps(photo, ensure_ascii=False)

            entree = EntreeJournal(
                utilisateur_id=utilisateur.id,
                cycle_lunaire_id=cycle_source.id if cycle_source else None,
                enjeu_periode_id=enjeu_source.id if enjeu_source else None,
                date_observation=date_observation,
                est_periode=est_periode,
                date_fin_periode=date_fin_periode,
                niveau_energie=niveau_energie,
                emotions=request.form.get("emotions", "").strip() or None,
                situation=request.form.get("situation", "").strip() or None,
                reaction_automatique=request.form.get(
                    "reaction_automatique",
                    "",
                ).strip() or None,
                choix_conscient=request.form.get(
                    "choix_conscient",
                    "",
                ).strip() or None,
                notes_libres=request.form.get("notes_libres", "").strip() or None,
                transits_actifs=photo_transits,
            )

            try:
                db.session.add(entree)
                db.session.flush()
                liaisons = _relier_situation_aux_mecanismes(entree, mecanismes_choisis)
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("L’observation n’a pas pu être enregistrée.", "error")
            else:
                flash("Ta page est enregistrée." + (" Les liens avec ton Labo sont enregistrés aussi." if liaisons else ""), "success")
                if liaisons and request.form.get("action") == "decoder":
                    return redirect(url_for("espace_personnel.decoder_situation", entree_id=entree.id))
                return redirect(url_for("espace_personnel.journal", entree=entree.id) + "#page-journal")

    return _rendre_journal(
        utilisateur,
        entree_ouverte=entree_ouverte, mode_modification=mode_modification,
        date_du_jour=date_prefill,
        contact_source=contact_source,
        domaines_contact=DOMAINES,
        cycle_source=cycle_source,
        enjeu_source=enjeu_source,
        interpretation_cycle=(
            json.loads(cycle_source.interpretation)
            if cycle_source and cycle_source.interpretation
            else None
        ),
    )


@espace_personnel_bp.route("/calendrier")
def calendrier():
    from utils.calendrier_personnel import MOIS, cadre_mois, donnees_astrales

    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    tzid = (profil_astral.fuseau_cycles or profil_astral.fuseau_horaire) if profil_astral else "Europe/Paris"
    try:
        fuseau = ZoneInfo(tzid)
    except (TypeError, KeyError):
        tzid, fuseau = "Europe/Paris", ZoneInfo("Europe/Paris")
    mois_brut = request.args.get("mois", datetime.now(fuseau).strftime("%Y-%m"))
    if not re.fullmatch(r"\d{4}-\d{2}", mois_brut):
        abort(400)
    try:
        annee, mois = map(int, mois_brut.split("-"))
        if not 1900 <= annee <= 2100:
            raise ValueError
        debut, fin, jours = cadre_mois(annee, mois, tzid)
    except ValueError:
        abort(400)
    theme = {}
    if profil_astral and profil_astral.theme_natal:
        try:
            theme = json.loads(profil_astral.theme_natal)
            if not isinstance(theme, dict):
                theme = {}
        except (TypeError, ValueError):
            theme = {}
    cycles_rs = []
    if profil_astral and droits["revolution_solaire"]:
        rs_enregistrees = CycleSolaire.query.filter_by(profil_id=profil_astral.id).all()
        for rs in rs_enregistrees:
            debut_rs = rs.debut_cycle_utc.replace(tzinfo=timezone.utc) if rs.debut_cycle_utc.tzinfo is None else rs.debut_cycle_utc
            fin_rs = rs.fin_cycle_utc.replace(tzinfo=timezone.utc) if rs.fin_cycle_utc.tzinfo is None else rs.fin_cycle_utc
            if debut_rs >= fin or fin_rs <= debut:
                continue
            try:
                technique = json.loads(rs.theme_technique or "{}")
                theme_rs = technique.get("theme_revolution_solaire")
                if isinstance(theme_rs, dict):
                    cycles_rs.append({"id": rs.id, "debut": debut_rs, "fin": fin_rs, "theme": theme_rs})
            except (TypeError, ValueError):
                current_app.logger.warning("RS %s illisible pour le calendrier", rs.id)
    message = None
    try:
        donnees = donnees_astrales(
            theme, debut, fin,
            mars_actif=bool(theme) and droits["transits_personnalises"],
            lune_active=droits["cycle_lunaire"], cycles_rs=cycles_rs,
        )
    except Exception:
        current_app.logger.exception("Calcul du calendrier indisponible")
        donnees = {"periods": [], "events": []}
        message = "Les calculs astrologiques sont indisponibles pour ce mois. Ton journal reste accessible."
    entrees = EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id).all()
    notes = [
        {"date": max(entree.date_observation.date(), debut.date()).isoformat(),
         "debut_periode": entree.date_observation.date().isoformat(),
         "fin_periode": entree.date_fin_periode.isoformat() if entree.date_fin_periode else None,
         "est_periode": bool(entree.est_periode),
         "texte": entree.situation or entree.notes_libres or entree.emotions or "Observation enregistrée",
         "url": url_for("espace_personnel.fiche", entree_id=entree.id)}
        for entree in entrees if (
            entree.date_observation.date() < fin.date()
            and (entree.date_observation.date() >= debut.date() or (
                entree.est_periode and (entree.date_fin_periode is None or entree.date_fin_periode >= debut.date())
            ))
        )
    ]
    donnees.update({
        "jours": jours, "decalage": debut.weekday(), "fuseau": tzid,
        "notes": notes, "journal_url": url_for("espace_personnel.journal"),
        "mars": bool(theme) and droits["transits_personnalises"],
        "lune": droits["cycle_lunaire"],
    })
    try:
        from utils.ciel_collectif import ciel_collectif_mois
        ciel = ciel_collectif_mois(annee, mois, inclure_periodes=True)
        donnees["ciel_collectif"] = {
            "evenements": [{**evenement, "date": evenement["date"].isoformat()}
                           for evenement in ciel["evenements"]],
            "periodes_aspects": ciel["periodes_aspects"],
            "retrogradations": [{**periode, "debut": periode["debut"].isoformat(),
                                  "fin": periode["fin"].isoformat()}
                                 for periode in ciel["retrogradations"]],
            "periodes_stationnaires": [
                {**periode, "debut": periode["debut"].isoformat(),
                 "fin": periode["fin"].isoformat(),
                 "changement": periode["changement"].isoformat()}
                for periode in ciel["periodes_stationnaires"]
            ],
        }
    except Exception:
        current_app.logger.exception("Calcul du ciel collectif indisponible pour le calendrier")
        donnees["ciel_collectif"] = None
    precedent = (debut - timedelta(days=1)).strftime("%Y-%m")
    suivant = fin.strftime("%Y-%m")
    reponse = current_app.make_response(render_template(
        "espace_personnel/calendrier.html", donnees=donnees,
        titre_mois=f"{MOIS[mois-1].capitalize()} {annee}", mois=mois_brut,
        precedent=precedent if precedent >= "1900-01" else None,
        suivant=suivant if suivant <= "2100-12" else None,
        profil=profil_astral, droits=droits, message=message,
    ))
    reponse.headers["Cache-Control"] = "private, no-store"
    return reponse


@espace_personnel_bp.route("/revolutions-solaires")
def revolutions_solaires():
    """Bibliothèque annuelle autonome des révolutions solaires du profil."""
    from utils.revolution_solaire.themes_prioritaires import detecter_themes_prioritaires_rs
    utilisateur = _utilisateur_espace_courant()
    profil_astral = _profil_astral_courant()
    rapports_par_cycle = {}
    for rapport in AnalysePersonnelle.query.filter_by(
        utilisateur_id=utilisateur.id, type_analyse="revolution_solaire",
    ).order_by(AnalysePersonnelle.date_creation.desc(), AnalysePersonnelle.id.desc()).all():
        rapports_par_cycle.setdefault(rapport.cycle_solaire_id, []).append(rapport)
    debut_filtre = request.args.get("debut", type=int)
    fin_filtre = request.args.get("fin", type=int)
    if (debut_filtre is None) != (fin_filtre is None) or (
        debut_filtre is not None and not (1900 <= debut_filtre <= fin_filtre <= 2100)
    ):
        abort(400)
    cycles = []
    if profil_astral:
        cycles_enregistres = (
            CycleSolaire.query
            .filter_by(profil_id=profil_astral.id)
            .order_by(CycleSolaire.debut_cycle_utc.desc())
            .all()
        )
        for cycle in cycles_enregistres:
            if debut_filtre is not None and not debut_filtre <= cycle.annee <= fin_filtre:
                continue
            try:
                theme = json.loads(cycle.theme_technique)
                retour_local = datetime.fromisoformat(theme["retour_local"])
                donnees = theme.get("donnees", {})
                themes = donnees.get("themes_prioritaires") or detecter_themes_prioritaires_rs(donnees)
                activations = []
                for groupe in theme.get("activations_datees") or []:
                    contacts = groupe.get("contacts") or []
                    climat = contacts[0] if contacts else {}
                    cible = {"Rahu": "Nœud Nord", "Ketu": "Nœud Sud"}.get(
                        climat.get("cible"), climat.get("cible", "")
                    )
                    activations.append({
                        "debut": datetime.fromisoformat(groupe["du"]).strftime("%d.%m.%Y"),
                        "fin": datetime.fromisoformat(groupe["au"]).strftime("%d.%m.%Y"),
                        "mois": groupe["du"][:7],
                        "climat": f"{climat.get('transit', '')} {climat.get('aspect', '')} {cible}".strip(),
                    })
            except (KeyError, TypeError, ValueError):
                retour_local = None
                donnees = {}
                themes = []
                activations = []
            cycles.append({
                "themes": themes[:4],
                "activations": activations,
                "cycle": cycle,
                "rapports": rapports_par_cycle.get(cycle.id, []),
                "retour_local": retour_local,
                "ascendant": donnees.get("ascendant_rs"),
                "nombre_rl": CycleLunaire.query.filter_by(cycle_solaire_id=cycle.id).count(),
            })
    return render_template(
        "espace_personnel/revolutions_solaires.html",
        profil=profil_astral,
        cycles=cycles,
        debut_filtre=debut_filtre,
        fin_filtre=fin_filtre,
    )


@espace_personnel_bp.route("/revolutions-solaires/<int:cycle_id>/rapport")
def lire_rapport_revolution_solaire(cycle_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        abort(404)
    cycle = CycleSolaire.query.filter_by(id=cycle_id, profil_id=profil_astral.id).first_or_404()
    if not cycle.rapport_html:
        abort(404)
    reponse = Response(cycle.rapport_html, mimetype="text/html")
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data: https:"
    return reponse


@espace_personnel_bp.route("/cycles-lunaires")
def cycles_lunaires():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    cycles = []
    if profil_astral:
        enregistres = CycleLunaire.query.filter_by(profil_id=profil_astral.id).order_by(CycleLunaire.debut_cycle_utc.desc()).all()
        for cycle in enregistres:
            try:
                theme = json.loads(cycle.theme_technique)
                interpretation = json.loads(cycle.interpretation) if cycle.interpretation else None
                date_locale = datetime.fromisoformat(theme["instant_local"])
            except (KeyError, TypeError, ValueError):
                theme, interpretation, date_locale = None, None, None
            cycles.append({"cycle": cycle, "theme": theme, "interpretation": interpretation, "date_locale": date_locale})
    return render_template(
        "espace_personnel/cycles_lunaires.html", profil=profil_astral,
        cycles=cycles, droits=droits,
    )


def _rs_archivee_pour_instant(profil_id, instant_utc):
    """Utilise une RS du compte déjà enregistrée, sans générer de rapport payant."""
    instant = instant_utc.astimezone(timezone.utc).replace(tzinfo=None)
    cycles = CycleSolaire.query.filter_by(profil_id=profil_id).order_by(CycleSolaire.debut_cycle_utc.desc()).all()
    for cycle in cycles:
        debut = cycle.debut_cycle_utc.replace(tzinfo=None)
        fin = cycle.fin_cycle_utc.replace(tzinfo=None)
        if debut <= instant < fin:
            try:
                return cycle, json.loads(cycle.theme_technique).get("theme_revolution_solaire")
            except (TypeError, ValueError):
                return cycle, None
    return None, None


def _preparer_theme_cycle_lunaire(theme):
    """Reconstruit les champs de présentation absents du JSON technique enregistré."""
    from utils.revolution_lunaire import priorites_interpretation
    from utils.transits.calcul_transits import longitude_to_signe

    theme["date_locale"] = datetime.fromisoformat(theme["instant_local"])
    theme["angles"] = {
        nom: longitude_to_signe(longitude)
        for nom, longitude in theme["angles_deg"].items()
    }
    theme["aspects_nataux_principaux"] = [
        aspect for aspect in theme.get("aspects_avec_natal", [])
        if aspect["orbe"] <= 2
    ]
    theme["priorites"] = priorites_interpretation(theme)
    return theme


@espace_personnel_bp.route("/cycles-lunaires/apercu", methods=["GET", "POST"])
def apercu_cycle_lunaire():
    """Aperçu gratuit à calculer ; Claude intervient seulement sur POST autorisé."""
    from utils.revolution_lunaire import (
        calculer_theme_revolution_lunaire, prochaine_revolution_lunaire,
    )

    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not droits["cycle_lunaire"]:
        abort(403)
    if request.method == "POST" and not _verifier_formulaire_portail():
        abort(400)

    theme = None
    interpretation = None
    usage_ia = None
    erreur = None
    erreur_generation = None
    cycle = None
    entrees_cycle = []
    cycles_navigation = []
    lieu_revolution = profil.ville_cycles if profil else None
    peut_generer = False

    if profil and profil.theme_natal:
        try:
            if not all((
                profil.ville_cycles, profil.fuseau_cycles,
                profil.latitude_cycles is not None,
                profil.longitude_cycles is not None,
            )):
                raise ValueError("Renseigne d’abord la ville utilisée pour tes cycles lunaires.")
            natal = json.loads(profil.theme_natal)
            lune = (natal.get("planetes") or {}).get("Lune") or {}
            longitude_lune = lune.get("longitude", lune.get("degre"))
            if longitude_lune is None:
                raise ValueError("La longitude de la Lune natale est absente.")
            theme = calculer_theme_revolution_lunaire(
                longitude_lune,
                latitude=profil.latitude_cycles,
                longitude=profil.longitude_cycles,
                apres=datetime.now(timezone.utc),
                theme_natal=natal,
                tzid=profil.fuseau_cycles,
            )
            instant = datetime.fromisoformat(theme["instant_utc"])
            rs, theme_rs = _rs_archivee_pour_instant(profil.id, instant)
            if theme_rs:
                theme = calculer_theme_revolution_lunaire(
                    longitude_lune,
                    latitude=profil.latitude_cycles,
                    longitude=profil.longitude_cycles,
                    apres=instant - timedelta(minutes=1),
                    theme_natal=natal,
                    theme_revolution_solaire=theme_rs,
                    tzid=profil.fuseau_cycles,
                )
                instant = datetime.fromisoformat(theme["instant_utc"])
            cle_cycle = instant.strftime("%Y-%m-%d")
            cycle = CycleLunaire.query.filter_by(profil_id=profil.id, cle_cycle=cle_cycle).first()
            if cycle:
                theme = json.loads(cycle.theme_technique)
                lieu_revolution = cycle.ville
                if cycle.interpretation:
                    interpretation = json.loads(cycle.interpretation)
                    usage_ia = {
                        "tokens_entree": cycle.tokens_entree or 0,
                        "tokens_sortie": cycle.tokens_sortie or 0,
                        "tokens_total": (cycle.tokens_entree or 0) + (cycle.tokens_sortie or 0),
                    }
                entrees_cycle = EntreeJournal.query.filter_by(
                    cycle_lunaire_id=cycle.id, utilisateur_id=utilisateur.id,
                ).order_by(EntreeJournal.date_observation.desc()).all()
            _preparer_theme_cycle_lunaire(theme)
            cycles_navigation = CycleLunaire.query.filter_by(profil_id=profil.id).order_by(
                CycleLunaire.debut_cycle_utc.asc()
            ).all()
            peut_generer = interpretation is None and (
                cycle is None or cycle.statut in {"a_generer", "technique"}
            )

            if request.method == "POST":
                if interpretation is not None:
                    return redirect(url_for("espace_personnel.fiche_cycle_lunaire", cycle_id=cycle.id))
                if not peut_generer:
                    erreur_generation = "Une génération a déjà été tentée pour ce cycle. Aucun nouvel appel à Claude n’a été lancé."
                else:
                    if cycle is None:
                        prochain = prochaine_revolution_lunaire(
                            longitude_lune, apres=instant + timedelta(days=1),
                        )
                        cycle = CycleLunaire(
                            profil_id=profil.id, cle_cycle=cle_cycle,
                            debut_cycle_utc=instant, fin_cycle_utc=prochain,
                            ville=profil.ville_cycles, fuseau_horaire=profil.fuseau_cycles,
                            latitude=profil.latitude_cycles, longitude=profil.longitude_cycles,
                            theme_technique=json.dumps(theme, ensure_ascii=False, default=str),
                        )
                        db.session.add(cycle)
                    if rs and cycle.cycle_solaire_id is None:
                        cycle.cycle_solaire_id = rs.id
                    db.session.flush()
                    reclamation = db.session.execute(
                        update(CycleLunaire)
                        .where(
                            CycleLunaire.id == cycle.id,
                            CycleLunaire.statut.in_(("a_generer", "technique")),
                        )
                        .values(statut="en_cours")
                    )
                    if reclamation.rowcount != 1:
                        db.session.rollback()
                        return redirect(url_for("espace_personnel.apercu_cycle_lunaire"))
                    db.session.commit()
                    try:
                        from utils.interpretation_cycle_lunaire import generer_interpretation_avec_claude
                        interpretation, usage_ia = generer_interpretation_avec_claude(
                            profil.prenom, lieu_revolution, theme,
                        )
                        cycle.interpretation = json.dumps(interpretation, ensure_ascii=False)
                        cycle.tokens_entree = usage_ia["tokens_entree"]
                        cycle.tokens_sortie = usage_ia["tokens_sortie"]
                        cycle.statut = "genere"
                        cycle.date_generation = datetime.now(timezone.utc)
                        db.session.commit()
                        return redirect(url_for("espace_personnel.fiche_cycle_lunaire", cycle_id=cycle.id))
                    except Exception:
                        db.session.rollback()
                        cycle = CycleLunaire.query.filter_by(profil_id=profil.id, cle_cycle=cle_cycle).first()
                        cycle.statut = "echec"
                        db.session.commit()
                        current_app.logger.exception("Échec de génération du cycle lunaire")
                        erreur_generation = "L’interprétation n’a pas abouti. Aucun nouvel appel ne sera tenté automatiquement."
                        peut_generer = False
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            erreur = str(exc)

    return render_template(
        "espace_personnel/apercu_cycle_lunaire.html", profil=profil, theme=theme,
        erreur=erreur, erreur_generation=erreur_generation,
        interpretation=interpretation, usage_ia=usage_ia,
        cycle_enregistre=cycle, entrees_cycle=entrees_cycle,
        cycles_navigation=cycles_navigation, lieu_revolution=lieu_revolution,
        peut_generer=peut_generer, espace_csrf=_jeton_formulaire_portail(),
    )


@espace_personnel_bp.route("/cycles-lunaires/<int:cycle_id>")
def fiche_cycle_lunaire(cycle_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        abort(404)
    cycle = CycleLunaire.query.filter_by(id=cycle_id, profil_id=profil_astral.id).first_or_404()
    try:
        theme = json.loads(cycle.theme_technique)
        _preparer_theme_cycle_lunaire(theme)
        interpretation = json.loads(cycle.interpretation) if cycle.interpretation else None
    except (KeyError, TypeError, ValueError):
        abort(404)
    usage_ia = {
        "tokens_entree": cycle.tokens_entree or 0,
        "tokens_sortie": cycle.tokens_sortie or 0,
        "tokens_total": (cycle.tokens_entree or 0) + (cycle.tokens_sortie or 0),
    }
    entrees_cycle = EntreeJournal.query.filter_by(cycle_lunaire_id=cycle.id, utilisateur_id=utilisateur.id).order_by(EntreeJournal.date_observation.desc()).all()
    cycles_navigation = CycleLunaire.query.filter_by(profil_id=profil_astral.id).order_by(CycleLunaire.debut_cycle_utc.asc()).all()
    return render_template(
        "espace_personnel/apercu_cycle_lunaire.html", profil=profil_astral,
        theme=theme, erreur=None, erreur_generation=None, interpretation=interpretation,
        usage_ia=usage_ia, cycle_enregistre=cycle, entrees_cycle=entrees_cycle,
        cycles_navigation=cycles_navigation, lieu_revolution=cycle.ville,
        peut_generer=False, espace_csrf=_jeton_formulaire_portail(),
    )


@espace_personnel_bp.route("/mes-analyses")
def mes_analyses():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    toutes_analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).order_by(AnalysePersonnelle.date_creation.desc()).all()
    analyses = [analyse for analyse in toutes_analyses if analyse.statut != "remplacee"]
    anciennes_analyses = [analyse for analyse in toutes_analyses if analyse.statut == "remplacee"]
    droits_achetes = DroitAnalyseAchetee.query.filter_by(utilisateur_id=utilisateur.id).all()
    types_termines = {analyse.type_analyse for analyse in analyses if analyse.statut == "terminee"}
    analyses_a_explorer = [item for item in CATALOGUE_ANALYSES if item["type"] not in types_termines]
    droits_par_type = {droit.type_analyse: droit for droit in droits_achetes if droit.statut != "terminee"}
    ids_analyses = [analyse.id for analyse in analyses]
    nombres_mecanismes = {}
    nombres_suggestions = {}
    analyses_deja_extraites = set()
    if ids_analyses:
        for mecanisme in MecanismeExploration.query.filter(MecanismeExploration.analyse_id.in_(ids_analyses)).all():
            nombres_mecanismes[mecanisme.analyse_id] = nombres_mecanismes.get(mecanisme.analyse_id, 0) + 1
        for suggestion in SuggestionMecanisme.query.filter(SuggestionMecanisme.analyse_id.in_(ids_analyses)).all():
            analyses_deja_extraites.add(suggestion.analyse_id)
            if suggestion.statut == "proposee":
                nombres_suggestions[suggestion.analyse_id] = nombres_suggestions.get(suggestion.analyse_id, 0) + 1
    if not session.get("espace_profil_csrf"):
        session["espace_profil_csrf"] = secrets.token_urlsafe(32)
    return render_template(
        "espace_personnel/mes_analyses.html", utilisateur=utilisateur,
        analyses=analyses, anciennes_analyses=anciennes_analyses,
        peut_importer=import_profil_autorise(utilisateur) and not toutes_analyses,
        analyses_a_explorer=analyses_a_explorer,
        droits_par_type=droits_par_type,
        nombres_mecanismes=nombres_mecanismes,
        nombres_suggestions=nombres_suggestions,
        analyses_deja_extraites=analyses_deja_extraites,
        types_extraction_mecanismes=TYPES_EXTRACTION_MECANISMES,
        types_importables={item["type"] for item in CATALOGUE_ANALYSES},
        droits_abonnement=acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()),
        espace_csrf=_jeton_formulaire_portail(),
    )


@espace_personnel_bp.route(
    "/mes-analyses/<int:analyse_id>/suggestions/generer",
    methods=["POST"],
)
def generer_suggestions_mecanismes(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)
    destination = url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id)
    if analyse.type_analyse == "revolution_solaire":
        return redirect(destination)
    phase = "preparation"
    try:
        with verrou_mecanismes(analyse.id):
            if SuggestionMecanisme.query.filter_by(analyse_id=analyse.id).first():
                flash("Les pistes de ce rapport sont déjà disponibles.", "success")
                return redirect(destination + "#suggestions-ia")
            sections = preparer_sections_mecanismes(
                analyse, lambda: _pdf_pour_extraction(analyse),
            )
            sections_dict = [
                {
                    "cle_section": section.cle_section,
                    "titre": section.titre,
                    "contenu": section.contenu,
                }
                for section in sections
            ]
            sections_par_cle = {section.cle_section: section for section in sections}
            phase = "ia"
            print(f"[Mécanismes] Rapport {analyse.id} : demande explicite, un seul appel IA.", flush=True)
            suggestions, usage = generer_suggestions_avec_claude(
                sections_dict,
                type_analyse=analyse.type_analyse,
            )
            for suggestion in suggestions:
                section_source = sections_par_cle.get(suggestion.cle_section)
                db.session.add(SuggestionMecanisme(
                    analyse_id=analyse.id,
                    section_id=section_source.id if section_source else None,
                    titre=suggestion.titre,
                    hypothese=suggestion.hypothese,
                    manifestations_possibles=json.dumps(
                        suggestion.manifestations_possibles,
                        ensure_ascii=False,
                    ),
                    extrait_source=suggestion.extrait_source,
                    references_astrologiques=json.dumps(
                        suggestion.references_astrologiques,
                        ensure_ascii=False,
                    ),
                    priorite=suggestion.priorite,
                    statut="proposee",
                ))
            db.session.commit()
    except ExtractionMecanismesEnCours as erreur:
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec d’extraction des mécanismes du rapport %s (étape %s)", analyse.id, phase)
        if phase == "preparation":
            flash("Le PDF n’a pas pu être lu. Utilise un PDF avec du texte sélectionnable. Aucun appel IA n’a été lancé.", "error")
        else:
            flash("Les mécanismes n’ont pas pu être extraits ou enregistrés. Aucune relance automatique.", "error")
    else:
        flash(f"{len(suggestions)} pistes proposées · {usage['tokens_total']} tokens utilisés.", "success")
    return redirect(destination + "#suggestions-ia")


@espace_personnel_bp.route("/mes-analyses/importer", methods=["POST"])
def importer_analyse():
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    type_analyse = request.form.get("type_analyse", "").strip()
    catalogue = {analyse["type"]: analyse for analyse in CATALOGUE_ANALYSES}
    fichier = request.files.get("rapport")
    if type_analyse not in catalogue or fichier is None or not fichier.filename:
        flash("Choisis une analyse et son rapport PDF.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    contenu = fichier.read(15 * 1024 * 1024 + 1)
    try:
        _verifier_rapport_fda(contenu, type_analyse)
    except ValueError as erreur:
        flash(str(erreur), "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    date_generation = datetime.now(timezone.utc)
    date_brute = request.form.get("date_generation", "").strip()
    if date_brute:
        try:
            date_generation = datetime.combine(date.fromisoformat(date_brute), time.min)
        except ValueError:
            flash("La date de génération n’est pas valide.", "error")
            return redirect(url_for("espace_personnel.mes_analyses"))
    nom = f"{uuid.uuid4().hex}.pdf"
    analyse = AnalysePersonnelle(
        utilisateur_id=utilisateur.id,
        type_analyse=type_analyse,
        titre=catalogue[type_analyse]["titre"], statut="terminee",
        chemin_resultat=nom, date_generation=date_generation,
    )
    try:
        db.session.add(analyse)
        db.session.flush()
        db.session.add(FichierAnalyse(
            analyse_id=analyse.id, nom_fichier=nom,
            contenu=contenu, empreinte_sha256=hashlib.sha256(contenu).hexdigest(),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Import du rapport impossible")
        flash("Ce rapport n’a pas pu être ajouté.", "error")
    else:
        flash("Ton rapport a été ajouté à Mes analyses.", "success")
    return redirect(url_for("espace_personnel.mes_analyses"))


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/remplacer", methods=["POST"])
def remplacer_analyse(analyse_id):
    """Conserve l'ancien PDF et ses pistes, puis crée une version vierge avec le nouveau PDF."""
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    analyse = AnalysePersonnelle.query.filter_by(id=analyse_id, utilisateur_id=utilisateur.id).first_or_404()
    if analyse.statut != "terminee" or analyse.type_analyse not in {item["type"] for item in CATALOGUE_ANALYSES}:
        abort(409)
    ancien_fichier = FichierAnalyse.query.filter_by(analyse_id=analyse.id).first_or_404()
    fichier = request.files.get("rapport")
    if fichier is None or not fichier.filename:
        flash("Choisis le nouveau rapport PDF.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    contenu = fichier.read(15 * 1024 * 1024 + 1)
    try:
        _verifier_rapport_fda(contenu, analyse.type_analyse)
    except ValueError as erreur:
        flash(str(erreur), "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    empreinte = hashlib.sha256(contenu).hexdigest()
    if empreinte == ancien_fichier.empreinte_sha256:
        flash("Ce PDF est déjà celui de cette analyse.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    date_generation = datetime.now(timezone.utc)
    date_brute = request.form.get("date_generation", "").strip()
    if date_brute:
        try:
            date_generation = datetime.combine(date.fromisoformat(date_brute), time.min)
        except ValueError:
            flash("La date du rapport n’est pas valide.", "error")
            return redirect(url_for("espace_personnel.mes_analyses"))
    nom = f"{uuid.uuid4().hex}.pdf"
    try:
        reclamation = db.session.execute(
            update(AnalysePersonnelle)
            .where(AnalysePersonnelle.id == analyse.id,
                   AnalysePersonnelle.utilisateur_id == utilisateur.id,
                   AnalysePersonnelle.statut == "terminee")
            .values(statut="remplacee")
        )
        if reclamation.rowcount != 1:
            db.session.rollback()
            flash("Ce rapport a déjà été remplacé. Recharge la page.", "error")
            return redirect(url_for("espace_personnel.mes_analyses"))
        nouvelle_analyse = AnalysePersonnelle(
            utilisateur_id=utilisateur.id, type_analyse=analyse.type_analyse,
            titre=analyse.titre, statut="terminee", chemin_resultat=nom,
            date_generation=date_generation,
        )
        db.session.add(nouvelle_analyse)
        db.session.flush()
        db.session.add(FichierAnalyse(
            analyse_id=nouvelle_analyse.id, nom_fichier=nom,
            contenu=contenu, empreinte_sha256=empreinte,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Remplacement du rapport impossible pour l’analyse %s", analyse_id)
        flash("Le remplacement a échoué ; l’ancien rapport reste disponible.", "error")
    else:
        flash("Le nouveau PDF est en place. L’ancienne version et ses pistes restent dans les archives.", "success")
    return redirect(url_for("espace_personnel.mes_analyses"))


@espace_personnel_bp.route("/mes-analyses/importer-archives", methods=["POST"])
def importer_archives_labo():
    from utils.import_espace_labo import importer_archives

    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    if not import_profil_autorise(utilisateur):
        abort(404)
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        flash("Enregistre d’abord ton profil.", "error")
        return redirect(url_for("espace_personnel.profil"))
    fichier = request.files.get("archives_import")
    if fichier is None:
        flash("Choisis le fichier de tes archives.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    brut = fichier.read(12 * 1024 * 1024 + 1)
    if len(brut) > 12 * 1024 * 1024:
        flash("Le fichier d’archives est trop volumineux.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    try:
        paquet = json.loads(brut.decode("utf-8"))
        bilan = importer_archives(
            paquet, email=utilisateur.email,
            utilisateur_id=utilisateur.id, profil_id=profil_astral.id,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Import privé des archives impossible")
        flash("L’import des archives a échoué ; aucune donnée partielle n’a été conservée.", "error")
        return redirect(url_for("espace_personnel.mes_analyses"))
    flash(
        f"Archives importées : {bilan['analyses']} analyses, {bilan['journal']} notes, "
        f"{bilan['rs']} RS et {bilan['rl']} RL.", "success",
    )
    return redirect(url_for("espace_personnel.mes_analyses"))


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/lire")
def lire_analyse(analyse_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    analyse = AnalysePersonnelle.query.filter_by(id=analyse_id, utilisateur_id=utilisateur.id).first_or_404()
    fichier = FichierAnalyse.query.filter_by(analyse_id=analyse.id).first_or_404()
    reponse = Response(fichier.contenu, mimetype="application/pdf")
    reponse.headers["Content-Disposition"] = f'inline; filename="{fichier.nom_fichier}"'
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["Content-Security-Policy"] = "sandbox"
    return reponse


@espace_personnel_bp.route("/journal/<int:entree_id>")
def fiche(entree_id):
    utilisateur = _utilisateur_espace_courant()
    entree = _entree_courante_ou_404(entree_id)
    photo_transits = None
    if entree.transits_actifs:
        try:
            photo_transits = json.loads(entree.transits_actifs)
        except (TypeError, ValueError):
            photo_transits = None
    liaisons = (
        ObservationMecanisme.query
        .filter_by(entree_journal_id=entree.id)
        .order_by(ObservationMecanisme.date_creation.asc())
        .all()
    )
    mecanismes_par_id = {
        mecanisme.id: mecanisme
        for mecanisme in (
            MecanismeExploration.query
            .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
            .filter(AnalysePersonnelle.utilisateur_id == utilisateur.id)
            .all()
        )
    }
    ids_deja_relies = {liaison.mecanisme_id for liaison in liaisons}
    liaisons_labo = [
        {
            "observation": liaison,
            "mecanisme": mecanismes_par_id.get(liaison.mecanisme_id),
        }
        for liaison in liaisons
    ]
    mecanismes_disponibles = [
        mecanisme
        for mecanisme in mecanismes_par_id.values()
        if mecanisme.id not in ids_deja_relies
    ]
    cycle_source = (
        CycleLunaire.query.join(ProfilAstral, ProfilAstral.id == CycleLunaire.profil_id)
        .filter(CycleLunaire.id == entree.cycle_lunaire_id, ProfilAstral.utilisateur_id == utilisateur.id)
        .first()
        if entree.cycle_lunaire_id
        else None
    )
    return render_template(
        "espace_personnel/fiche.html",
        entree=entree,
        photo_transits=photo_transits,
        transits_visibles=_selectionner_transits_visibles(photo_transits),
        liaisons_labo=liaisons_labo,
        mecanismes_disponibles=mecanismes_disponibles,
        cycle_source=cycle_source,
    )


@espace_personnel_bp.route("/journal/<int:entree_id>/relier-mecanisme", methods=["POST"])
def relier_entree_mecanisme(entree_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    entree = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur.id).first_or_404()
    if not _verifier_formulaire_portail():
        abort(400)
    destination = (url_for("espace_personnel.journal", entree=entree.id) + "#aller-plus-loin"
                   if request.form.get("retour") == "journal"
                   else url_for("espace_personnel.fiche", entree_id=entree.id) + "#liaisons-labo")
    try:
        mecanismes = _mecanismes_choisis_journal(request.form, entree.utilisateur_id)
        if not mecanismes:
            raise ValueError("Coche au moins un mécanisme à relier à cette situation.")
        _relier_situation_aux_mecanismes(entree, mecanismes)
        db.session.commit()
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Impossible de relier les mécanismes à l’entrée %s", entree.id)
        flash("Les liens n’ont pas pu être enregistrés.", "error")
    else:
        flash("Cette situation est reliée aux mécanismes choisis.", "success")
        if request.form.get("action") == "decoder":
            return redirect(url_for("espace_personnel.decoder_situation", entree_id=entree.id))
    return redirect(destination)


@espace_personnel_bp.route("/journal/<int:entree_id>/modifier", methods=["GET", "POST"])
def modifier(entree_id):
    entree = _entree_courante_ou_404(entree_id)
    retour_journal = request.form.get("retour") == "journal"

    if request.method == "GET":
        return render_template(
            "espace_personnel/modifier.html",
            entree=entree,
        )

    date_observation_str = request.form.get("date_observation", "").strip()
    niveau_energie_str = request.form.get("niveau_energie", "").strip()

    try:
        date_observation = datetime.strptime(
            date_observation_str,
            "%Y-%m-%d",
        )
        niveau_energie = (
            int(niveau_energie_str)
            if niveau_energie_str
            else None
        )
        if niveau_energie is not None and not 1 <= niveau_energie <= 10:
            raise ValueError
    except (TypeError, ValueError):
        flash("Vérifie la date et, si tu l’as indiqué, le niveau d’énergie.", "error")
        if retour_journal:
            return _rendre_journal(_utilisateur_espace_courant(), entree_ouverte=entree, mode_modification=True)
        return redirect(url_for("espace_personnel.fiche", entree_id=entree.id))

    try:
        est_periode, date_fin_periode = _dates_periode_journal(request.form, date_observation)
    except ValueError as erreur:
        flash(str(erreur), "error")
        if retour_journal:
            return _rendre_journal(_utilisateur_espace_courant(), entree_ouverte=entree, mode_modification=True)
        return render_template("espace_personnel/modifier.html", entree=entree)

    entree.date_observation = date_observation
    entree.est_periode = est_periode
    entree.date_fin_periode = date_fin_periode
    # Les champs retirés du journal ne doivent pas effacer les anciennes informations.
    if "niveau_energie" in request.form:
        entree.niveau_energie = niveau_energie
    if "emotions" in request.form:
        entree.emotions = request.form.get("emotions", "").strip() or None
    entree.situation = request.form.get("situation", "").strip() or None
    if "reaction_automatique" in request.form:
        entree.reaction_automatique = request.form.get(
            "reaction_automatique",
            "",
        ).strip() or None
    if "choix_conscient" in request.form:
        entree.choix_conscient = request.form.get(
            "choix_conscient",
            "",
        ).strip() or None
    if "notes_libres" in request.form:
        entree.notes_libres = request.form.get("notes_libres", "").strip() or None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Les modifications n’ont pas pu être enregistrées.", "error")
        if retour_journal:
            return _rendre_journal(_utilisateur_espace_courant(), entree_ouverte=entree, mode_modification=True)
    else:
        flash("Ton observation a été mise à jour.", "success")

    if retour_journal:
        return redirect(url_for("espace_personnel.journal", entree=entree.id) + "#page-journal")
    return redirect(url_for("espace_personnel.fiche", entree_id=entree.id))


@espace_personnel_bp.route("/journal/<int:entree_id>/supprimer", methods=["POST"])
def supprimer(entree_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    jeton = session.get("espace_profil_csrf", "")
    if not jeton or not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
        abort(400)
    entree = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur.id).first_or_404()
    try:
        db.session.delete(entree)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Observation du journal impossible à supprimer")
        flash("L’observation n’a pas pu être supprimée.", "error")
        return redirect(url_for("espace_personnel.fiche", entree_id=entree_id))
    flash("L’observation a été supprimée.", "success")
    return redirect(url_for("espace_personnel.journal"))


@espace_personnel_bp.route("/profil/importer", methods=["POST"])
def importer_profil_labo():
    """Complète ou crée le profil du compte connecté sans écraser sa saisie."""
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    if not import_profil_autorise(utilisateur):
        abort(404)
    existant = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if not import_profil_disponible(utilisateur):
        flash("Les données du labo ont déjà été importées dans ce compte.", "error")
        return redirect(url_for("espace_personnel.profil"))

    csrf = session.get("espace_profil_csrf", "")
    if not csrf or not hmac.compare_digest(request.form.get("profil_csrf", ""), csrf):
        abort(400)
    fichier = request.files.get("profil_import")
    try:
        if fichier is None:
            raise ValueError("Choisis le fichier de ton profil.")
        brut = fichier.read(262145)
        if len(brut) > 262144:
            raise ValueError("Le fichier de profil est trop volumineux.")
        paquet = json.loads(brut.decode("utf-8"))
        if paquet.get("version") not in {1, 2} or paquet.get("email", "").strip().lower() != utilisateur.email.lower():
            raise ValueError("Ce fichier ne correspond pas à ce compte.")
        donnees = paquet["profil"]
        prenom = donnees["prenom"].strip()
        ville = donnees["ville_naissance"].strip()
        fuseau = donnees["fuseau_horaire"].strip()
        naissance = date.fromisoformat(donnees["date_naissance"])
        heure = time.fromisoformat(donnees["heure_naissance"])
        latitude = float(donnees["latitude"])
        longitude = float(donnees["longitude"])
        ZoneInfo(fuseau)
        if (
            not prenom or len(prenom) > 100 or not ville or len(ville) > 200
            or naissance > date.today() or not math.isfinite(latitude)
            or not math.isfinite(longitude) or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError("Les coordonnées de naissance du fichier sont invalides.")
        if existant is not None and (
            existant.date_naissance != naissance or existant.heure_naissance != heure
        ):
            raise ValueError(
                "La date ou l’heure de naissance ne correspond pas au profil déjà enregistré."
            )
        theme_texte = donnees["theme_natal"]
        theme = json.loads(theme_texte)
        if not isinstance(theme, dict) or not isinstance(theme.get("planetes"), dict) or not isinstance(theme.get("maisons"), dict):
            raise ValueError("Le thème natal du fichier est incomplet.")

        cycles = {}
        if donnees.get("ville_cycles"):
            cycles = {
                "ville_cycles": donnees["ville_cycles"].strip(),
                "fuseau_cycles": donnees["fuseau_cycles"].strip(),
                "latitude_cycles": float(donnees["latitude_cycles"]),
                "longitude_cycles": float(donnees["longitude_cycles"]),
            }
            ZoneInfo(cycles["fuseau_cycles"])
            if (
                len(cycles["ville_cycles"]) > 200
                or not math.isfinite(cycles["latitude_cycles"])
                or not math.isfinite(cycles["longitude_cycles"])
                or not -90 <= cycles["latitude_cycles"] <= 90
                or not -180 <= cycles["longitude_cycles"] <= 180
            ):
                raise ValueError("La ville des cycles est invalide.")

        contextes = {}
        for champ in (
            "situation_foyer", "situation_amour", "situation_travail",
            "situation_enfants", "situation_sante", "preoccupation_actuelle",
        ):
            valeur = donnees.get(champ)
            if valeur is not None and (not isinstance(valeur, str) or len(valeur) > 5000):
                raise ValueError("Le contexte du fichier est invalide.")
            contextes[champ] = valeur

        abonnement_source = paquet.get("abonnement")
        abonnement_import = None
        if abonnement_source is not None:
            if (
                not isinstance(abonnement_source, dict)
                or abonnement_source.get("statut") != "test"
                or abonnement_source.get("formule") not in {"accompagnement_astral", "beta_accompagnement"}
            ):
                raise ValueError("La formule de test du fichier est invalide.")

            def lire_instant(valeur):
                if not valeur:
                    return None
                instant = datetime.fromisoformat(valeur)
                return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant

            debut = lire_instant(abonnement_source.get("date_debut"))
            fin = lire_instant(abonnement_source.get("date_fin"))
            if debut and fin and fin <= debut:
                raise ValueError("La période de la formule de test est invalide.")
            abonnement_import = AbonnementEspace(
                utilisateur_id=utilisateur.id,
                formule=abonnement_source["formule"],
                statut="test",
                date_debut=debut,
                date_fin=fin,
                source="labo_import",
            )
    except (TypeError, ValueError, KeyError, AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return render_template(
            "espace_personnel/profil.html", profil=existant,
            utilisateur=utilisateur, saisie=None, peut_importer=True,
            erreur=str(exc) if isinstance(exc, ValueError) else "Le fichier de profil est invalide.",
        ), 400

    if existant is None:
        profil_astral = ProfilAstral(
            utilisateur_id=utilisateur.id,
            prenom=prenom,
            date_naissance=naissance,
            heure_naissance=heure,
            ville_naissance=ville,
            fuseau_horaire=fuseau,
            latitude=latitude,
            longitude=longitude,
            theme_natal=theme_texte,
            date_calcul_theme=datetime.now(timezone.utc),
            **cycles,
            **contextes,
        )
        utilisateur.prenom = prenom
        db.session.add(profil_astral)
    else:
        profil_astral = existant
        for champ, valeur in {**cycles, **contextes}.items():
            if getattr(profil_astral, champ) is None and valeur is not None:
                setattr(profil_astral, champ, valeur)
    if abonnement_import is not None:
        if AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first() is not None:
            db.session.rollback()
            return render_template(
                "espace_personnel/profil.html", profil=existant,
                utilisateur=utilisateur, saisie=None, peut_importer=True,
                erreur="Une formule existe déjà pour ce compte ; l’import a été arrêté.",
            ), 409
        db.session.add(abonnement_import)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Import du profil impossible")
        return render_template(
            "espace_personnel/profil.html", profil=existant,
            utilisateur=utilisateur, saisie=None, peut_importer=True,
            erreur="L’import n’a pas pu être enregistré. Réessaie plus tard.",
        ), 503
    flash("Ton profil du labo a bien été repris dans cet espace.", "success")
    return redirect(url_for("espace_personnel.profil"))


@espace_personnel_bp.route("/emails-cycle")
def emails_cycle():
    profil = _profil_astral_courant()
    emails = []
    if profil:
        emails = (
            EmailCycleAbonnement.query
            .filter_by(profil_id=profil.id)
            .order_by(EmailCycleAbonnement.date_modification.desc())
            .all()
        )
    return render_template(
        "espace_personnel/emails_cycle.html", profil=profil, emails=emails,
        droits=droits_email(profil) if profil else {"cycle_lunaire": False},
        mois_courant=datetime.now(ZoneInfo(profil.fuseau_cycles or "Europe/Paris") if profil else ZoneInfo("Europe/Paris")).strftime("%Y-%m"),
    )


@espace_personnel_bp.route("/emails-cycle/preparer", methods=["POST"])
def preparer_email_cycle():
    profil = _profil_astral_courant()
    if profil is None:
        abort(404)
    try:
        if droits_email(profil).get("emails_par_mois") == 2:
            mois = request.form.get("mois") or datetime.now(ZoneInfo(profil.fuseau_cycles or "Europe/Paris")).strftime("%Y-%m")
            preparer_mails_mois(profil, mois)
            db.session.commit()
            flash(f"Les deux créneaux du {mois} sont prêts : le 1er et le 15 à 9 h, heure de ta ville de cycles. Aucun appel IA ni envoi.", "success")
            return redirect(url_for("espace_personnel.emails_cycle"))
        email, _ = preparer_brouillon_boussole(profil)
        db.session.commit()
        flash("Le contrat factuel du prochain email est prêt. Aucun appel Claude n’a été fait.", "success")
        return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))
    except (TypeError, ValueError, RuntimeError) as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("espace_personnel.emails_cycle"))


@espace_personnel_bp.route("/emails-cycle/importer", methods=["POST"])
def importer_brouillon_cycle():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    if not import_profil_autorise(utilisateur):
        abort(404)
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        flash("Importe d’abord ton profil astral.", "error")
        return redirect(url_for("espace_personnel.profil"))
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not droits["cycle_lunaire"]:
        abort(403)
    csrf = session.get("espace_profil_csrf", "")
    if not csrf or not hmac.compare_digest(request.form.get("profil_csrf", ""), csrf):
        abort(400)
    fichier = request.files.get("brouillon_import")
    try:
        if fichier is None:
            raise ValueError("Choisis le fichier du brouillon.")
        brut = fichier.read(262145)
        if len(brut) > 262144:
            raise ValueError("Le fichier du brouillon est trop volumineux.")
        paquet = json.loads(brut.decode("utf-8"))
        if paquet.get("version") != 1 or paquet.get("email", "").strip().lower() != utilisateur.email.lower():
            raise ValueError("Ce brouillon ne correspond pas à ce compte.")
        cycle_donnees = paquet["cycle"]
        brouillon = paquet["brouillon"]
        cle_cycle = cycle_donnees["cle_cycle"]
        date.fromisoformat(cle_cycle)
        debut = datetime.fromisoformat(cycle_donnees["debut_cycle_utc"])
        fin = datetime.fromisoformat(cycle_donnees["fin_cycle_utc"])
        if debut.tzinfo is None:
            debut = debut.replace(tzinfo=timezone.utc)
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=timezone.utc)
        if fin <= debut:
            raise ValueError("Les dates du cycle sont invalides.")
        ville = cycle_donnees["ville"].strip()
        fuseau = cycle_donnees["fuseau_horaire"].strip()
        latitude = float(cycle_donnees["latitude"])
        longitude = float(cycle_donnees["longitude"])
        ZoneInfo(fuseau)
        if (
            not ville or len(ville) > 200 or not math.isfinite(latitude)
            or not math.isfinite(longitude) or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError("Le lieu du cycle est invalide.")
        technique = cycle_donnees["theme_technique"]
        if not isinstance(json.loads(technique), dict):
            raise ValueError("Le thème lunaire du fichier est invalide.")
        type_email = brouillon["type_email"]
        objet = brouillon["objet"]
        texte = brouillon["contenu_texte"]
        html = brouillon.get("contenu_html")
        if (
            type_email not in {"boussole_cycle", "boussole_lunaire"}
            or not isinstance(objet, str) or not 1 <= len(objet) <= 250
            or not isinstance(texte, str) or not 1 <= len(texte) <= 50000
            or (html is not None and (not isinstance(html, str) or len(html) > 50000))
        ):
            raise ValueError("Le contenu du brouillon est invalide.")
    except (TypeError, ValueError, KeyError, AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Le fichier du brouillon est invalide.", "error")
        return redirect(url_for("espace_personnel.emails_cycle"))

    cycle = CycleLunaire.query.filter_by(profil_id=profil_astral.id, cle_cycle=cle_cycle).first()
    if cycle is None:
        cycle = CycleLunaire(
            profil_id=profil_astral.id, cle_cycle=cle_cycle,
            debut_cycle_utc=debut, fin_cycle_utc=fin, ville=ville,
            fuseau_horaire=fuseau, latitude=latitude, longitude=longitude,
            theme_technique=technique, interpretation=cycle_donnees.get("interpretation"),
            statut=cycle_donnees.get("statut") or "technique",
        )
        db.session.add(cycle)
        db.session.flush()
    existant = EmailCycleAbonnement.query.filter_by(
        profil_id=profil_astral.id, cycle_lunaire_id=cycle.id, type_email=type_email,
    ).first()
    if existant is not None:
        db.session.rollback()
        flash("Ce brouillon est déjà dans ton espace ; aucun doublon créé.", "error")
        return redirect(url_for("espace_personnel.emails_cycle"))
    date_generation = brouillon.get("date_generation")
    try:
        date_generation = datetime.fromisoformat(date_generation) if date_generation else None
    except (TypeError, ValueError):
        date_generation = None
    email = EmailCycleAbonnement(
        profil_id=profil_astral.id, cycle_lunaire_id=cycle.id,
        type_email=type_email, statut="brouillon", objet=objet,
        contenu_texte=texte, contenu_html=html,
        declencheur_factuel=brouillon.get("declencheur_factuel"),
        points_abordes=brouillon.get("points_abordes"),
        question_journal=brouillon.get("question_journal"),
        date_generation=date_generation,
    )
    db.session.add(email)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Import du brouillon de cycle impossible")
        flash("Le brouillon n’a pas pu être enregistré.", "error")
        return redirect(url_for("espace_personnel.emails_cycle"))
    flash("Brouillon importé : il n’a pas été envoyé.", "success")
    return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))


@espace_personnel_bp.route("/emails-cycle/<int:email_id>")
def fiche_email_cycle(email_id):
    email = _email_cycle_courant_ou_404(email_id)
    preparation = _charger_preparation_email(email)
    cycle = db.session.get(CycleLunaire, email.cycle_lunaire_id) if email.cycle_lunaire_id else None
    if cycle and not (email.contenu_texte or email.contenu_html):
        if preparation.get("version_contrat") == VERSION_CONTRAT:
            preparation = actualiser_mail_quinzaine(_profil_astral_courant(), preparation)
        elif not str(preparation.get("version_contrat", "")).startswith("quinzaine_"):
            preparation = actualiser_enjeux_email(_profil_astral_courant(), preparation, cycle.debut_cycle_utc.replace(tzinfo=timezone.utc))
    return render_template(
        "espace_personnel/fiche_email_cycle.html",
        email=email,
        cycle=cycle,
        preparation=preparation,
        peut_generer=(generation_autorisee(droits_email(_profil_astral_courant()), preparation)
                      and (droits_email(_profil_astral_courant()).get("emails_par_mois") != 2
                           or preparation.get("version_contrat") == VERSION_CONTRAT)),
        journaux_mail=journaux_mail(email.id),
    )


@espace_personnel_bp.route("/emails-cycle/<int:email_id>/generer", methods=["POST"])
def generer_brouillon_email_cycle(email_id):
    """Produit un brouillon Claude, sans envoi et sans validation automatique."""
    email = _email_cycle_courant_ou_404(email_id)
    try:
        generer_mail_enregistre(email, _profil_astral_courant())
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec de conservation du brouillon email de cycle")
        flash("Le brouillon n’a pas pu être conservé. Consulte les journaux avant toute autre tentative.", "error")
    else:
        flash("Brouillon conservé : à relire, aucun envoi déclenché.", "success")
    return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))


@espace_personnel_bp.route("/emails-cycle/<int:email_id>/envoyer", methods=["POST"])
def envoyer_brouillon_cycle(email_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    csrf = session.get("espace_profil_csrf", "")
    if not csrf or not hmac.compare_digest(request.form.get("profil_csrf", ""), csrf):
        abort(400)
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        abort(404)
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not droits["cycle_lunaire"]:
        abort(403)
    email = EmailCycleAbonnement.query.filter_by(id=email_id, profil_id=profil_astral.id).first_or_404()
    if email.statut != "brouillon" or not email.objet or not email.contenu_texte:
        flash("Ce mail n’est plus un brouillon prêt à être envoyé.", "error")
        return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email_id))

    reclamation = db.session.execute(
        update(EmailCycleAbonnement)
        .where(EmailCycleAbonnement.id == email.id, EmailCycleAbonnement.statut == "brouillon")
        .values(statut="envoi_en_cours")
    )
    if reclamation.rowcount != 1:
        db.session.rollback()
        flash("Ce mail est déjà en cours d’envoi ou a été envoyé.", "error")
        return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email_id))
    db.session.commit()

    try:
        succes = envoyer_email_avec_analyse(
            destinataire=utilisateur.email,
            sujet=email.objet,
            contenu_txt=email.contenu_texte,
            contenu_html=email.contenu_html,
        )
    except Exception:
        current_app.logger.exception("Envoi du mail de cycle incertain")
        succes = False
    email.statut = "envoye" if succes else "envoi_incertain"
    if succes:
        email.date_envoi = datetime.now(timezone.utc)
    db.session.commit()
    flash(
        "Mail envoyé et archivé." if succes else
        "Envoi incertain : vérifie la boîte et les logs avant toute nouvelle tentative.",
        "success" if succes else "error",
    )
    return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email_id))





def _acces_dev_sur_machine_locale():
    """Le sélecteur de comptes DEV ne doit jamais être accessible sur Railway."""
    return (
        request.remote_addr in {"127.0.0.1", "::1"}
        and urlsplit(request.host_url).hostname in {"localhost", "127.0.0.1", "::1"}
        and not any(os.getenv(cle) for cle in (
            "RAILWAY_ENVIRONMENT_ID", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_NAME",
        ))
    )


def _route_outils_mails():
    chemin = request.path
    return chemin == "/mon-espace/emails-cycle" or chemin.startswith("/mon-espace/emails-cycle/")


@espace_personnel_bp.before_request
def exiger_connexion_espace():
    """Protège toutes les pages privées sans recourir au sélecteur DEV."""
    if _route_outils_mails():
        if not administratrice_connectee():
            abort(404)
        if request.method == "POST":
            verifier_csrf_espace()
    if '/extractions-rs/' in request.path and not administratrice_connectee():
        abort(404)
    if request.endpoint in ROUTES_PUBLIQUES_AUTH:
        return None
    utilisateur = utilisateur_connecte()
    if utilisateur is None:
        session.pop("utilisateur_espace_id", None)
        return redirect(url_for("espace_personnel.connexion", suivant=request.full_path))
    _jeton_formulaire_portail()
    if not session.get('espace_profil_csrf'):
        session['espace_profil_csrf'] = secrets.token_urlsafe(32)
    if request.method == 'POST' and request.endpoint not in ROUTES_AUTH and not _route_outils_mails():
        if request.form.get('csrf_token'):
            verifier_csrf_espace()
        elif request.form.get('espace_csrf'):
            if not _verifier_formulaire_portail():
                abort(400)
        elif request.form.get('profil_csrf'):
            if not hmac.compare_digest(request.form.get('profil_csrf', ''), session.get('espace_profil_csrf', '')):
                abort(400)
        else:
            abort(400, 'Recharge la page avant de réessayer.')
    return None


@espace_personnel_bp.app_context_processor
def contexte_auth_espace():
    return {"csrf_espace": jeton_csrf_espace, "avatars_espace": AVATARS_ESPACE,
            "auth_turnstile_actif": True, "outils_mails_admin": administratrice_connectee(), "utilisateur_espace": utilisateur_connecte()}


@espace_personnel_bp.after_request
def proteger_pages_auth_espace(reponse):
    reponse.headers["Cache-Control"] = "no-store, private"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    if _route_outils_mails():
        reponse.headers["Cache-Control"] = "no-store, private"
        reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.endpoint in ROUTES_AUTH:
        reponse.headers["Cache-Control"] = "no-store, private"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Content-Security-Policy"] = "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    return reponse


def _utilisateur_espace_courant():
    utilisateur = utilisateur_connecte()
    if utilisateur is None:
        abort(403)
    return utilisateur


def _profil_astral_courant():
    return ProfilAstral.query.filter_by(
        utilisateur_id=_utilisateur_espace_courant().id
    ).first()


def _analyse_courante_ou_404(analyse_id):
    return AnalysePersonnelle.query.filter_by(
        id=analyse_id,
        utilisateur_id=_utilisateur_espace_courant().id,
    ).first_or_404()


def _mecanisme_courant_ou_404(mecanisme_id):
    return (
        MecanismeExploration.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(
            MecanismeExploration.id == mecanisme_id,
            AnalysePersonnelle.utilisateur_id == _utilisateur_espace_courant().id,
        )
        .first_or_404()
    )


def _suggestion_courante_ou_404(suggestion_id):
    return (
        SuggestionMecanisme.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == SuggestionMecanisme.analyse_id)
        .filter(
            SuggestionMecanisme.id == suggestion_id,
            AnalysePersonnelle.utilisateur_id == _utilisateur_espace_courant().id,
        )
        .first_or_404()
    )


def _entree_courante_ou_404(entree_id):
    return EntreeJournal.query.filter_by(
        id=entree_id,
        utilisateur_id=_utilisateur_espace_courant().id,
    ).first_or_404()


def _observation_courante_ou_404(observation_id):
    return (
        ObservationMecanisme.query
        .join(MecanismeExploration, MecanismeExploration.id == ObservationMecanisme.mecanisme_id)
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(
            ObservationMecanisme.id == observation_id,
            AnalysePersonnelle.utilisateur_id == _utilisateur_espace_courant().id,
        )
        .first_or_404()
    )


def _dossier_rapports_importes():
    dossier = os.path.join(racine_privee_espace(), "analyses_uploads")
    os.makedirs(dossier, exist_ok=True)
    return dossier


def _normaliser_texte_pdf(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(caractere for caractere in texte if not unicodedata.combining(caractere))
    texte = texte.casefold().replace("’", " ").replace("'", " ")
    texte = re.sub(r"[^a-z0-9]+", " ", texte)
    return " ".join(texte.split())


def _verifier_pdf_fous_astro(chemin, type_analyse):
    """Vérifie la signature et le titre du rapport avant son archivage privé."""
    with pdfplumber.open(chemin) as document:
        texte = " ".join((page.extract_text() or "") for page in document.pages[:3])
    texte = _normaliser_texte_pdf(texte)
    titres_attendus = TITRES_PDF_PAR_ANALYSE.get(type_analyse, ())
    if "les fous d astro" not in texte or not any(titre in texte for titre in titres_attendus):
        raise ValueError("Ce PDF ne correspond pas à l’analyse Les Fous d’Astro choisie.")


def _calculer_positions_journal(date_calcul):
    jour_julien = swe.julday(
        date_calcul.year,
        date_calcul.month,
        date_calcul.day,
        date_calcul.hour
        + date_calcul.minute / 60
        + date_calcul.second / 3600,
    )
    positions = {}
    for nom_planete in PLANETES_TRANSIT_JOURNAL:
        coordonnees = swe.calc_ut(
            jour_julien,
            PLANETES_SWISSEPH[nom_planete],
        )[0]
        longitude = coordonnees[0] % 360
        positions[nom_planete] = {
            **longitude_to_signe(longitude),
            "retrograde": coordonnees[3] < 0,
            "vitesse": round(coordonnees[3], 6),
        }
    return {
        "date_transit": date_calcul.isoformat(),
        "positions": positions,
    }


def _calculer_photo_transits(theme, date_observation):
    """Photographie astrologique brute, sans LLM ni génération de rapport."""
    maintenant = datetime.now()
    date_calcul = (
        maintenant
        if date_observation.date() == maintenant.date()
        else date_observation.replace(hour=12, minute=0, second=0)
    )
    donnees_positions = _calculer_positions_journal(date_calcul)
    maitre_data = theme.get("maitre_ascendant")
    maitre_ascendant = (
        maitre_data.get("nom")
        if isinstance(maitre_data, dict)
        else maitre_data
    )
    aspects = detecter_aspects(
        donnees_positions["positions"],
        theme.get("planetes", {}),
        extraire_cuspides(theme),
        theme.get("house_rulers_map", {}),
        maitre_ascendant=maitre_ascendant,
        angles_deg=theme.get("angles_deg", {}),
    )
    transits_retenus = sorted(
        aspects,
        key=lambda transit: (-transit.importance, transit.orbe),
    )
    return {
        "date_calcul": donnees_positions["date_transit"],
        "positions": donnees_positions["positions"],
        "transits": [asdict(transit) for transit in transits_retenus],
    }


def _selectionner_transits_visibles(photo_transits):
    transits = photo_transits.get("transits", []) if photo_transits else []
    planetes_lentes = {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}

    groupes = {}
    for transit in transits:
        planete = transit.get("planete_transit", "Transit")
        groupes.setdefault(planete, []).append(transit)

    groupes_tries = []
    for planete, aspects in groupes.items():
        aspects_tries_bruts = sorted(
            aspects,
            key=lambda transit: (-transit.get("importance", 0), transit.get("orbe", 999)),
        )
        aspects_tries = []
        for transit in aspects_tries_bruts:
            contexte = transit.get("contexte") or {}
            aspect_enrichi = dict(transit)
            maison_cible = contexte.get("maison_natale_planete")
            maisons_dirigees_cible = contexte.get("maisons_gouvernees_natale") or []
            aspect_enrichi["maison_cible"] = maison_cible
            aspect_enrichi["theme_maison_cible"] = THEMES_MAISONS.get(maison_cible)
            aspect_enrichi["maisons_dirigees_cible"] = [
                {
                    "maison": maison,
                    "theme": THEMES_MAISONS.get(maison, "domaine à explorer"),
                }
                for maison in maisons_dirigees_cible
                if isinstance(maison, int)
            ]
            aspects_tries.append(aspect_enrichi)

        contexte_planete = (aspects_tries[0].get("contexte") or {}) if aspects_tries else {}
        maison_transitee = contexte_planete.get("maison_transit")
        maison_natale_planete = contexte_planete.get("maison_natale_transit")
        maisons_dirigees_planete = contexte_planete.get("maisons_gouvernees_transit") or []

        lecture = LECTURES_PLANETAIRES.get(planete, {})
        groupes_tries.append({
            "planete": planete,
            "aspects": aspects_tries,
            "intensite_max": max(
                (transit.get("importance", 0) for transit in aspects_tries),
                default=0,
            ),
            "orbe_min": min(
                (transit.get("orbe", 999) for transit in aspects_tries),
                default=999,
            ),
            "dynamique": lecture.get("dynamique"),
            "question": lecture.get("question"),
            "maison_transitee": maison_transitee,
            "theme_maison_transitee": THEMES_MAISONS.get(maison_transitee),
            "maison_natale_planete": maison_natale_planete,
            "theme_maison_natale_planete": THEMES_MAISONS.get(maison_natale_planete),
            "maisons_dirigees_planete": [
                {
                    "maison": maison,
                    "theme": THEMES_MAISONS.get(maison, "domaine à explorer"),
                }
                for maison in maisons_dirigees_planete
                if isinstance(maison, int)
            ],
        })

    groupes_tries.sort(
        key=lambda groupe: (-groupe["intensite_max"], groupe["orbe_min"]),
    )

    return {
        "climat_fond": [
            groupe
            for groupe in groupes_tries
            if groupe["planete"] in planetes_lentes
        ],
        "declencheurs": [
            groupe
            for groupe in groupes_tries
            if groupe["planete"] not in planetes_lentes
        ],
        "total_brut": len(transits),
    }


def _energies_du_moment(profil_astral):
    if not profil_astral or not profil_astral.theme_natal:
        return None, {"climat_fond": [], "declencheurs": [], "total_brut": 0}

    try:
        theme_natal = json.loads(profil_astral.theme_natal)
        photo_complete = _calculer_photo_transits(theme_natal, datetime.now())
    except Exception:
        return None, {"climat_fond": [], "declencheurs": [], "total_brut": 0}

    photo_importante = dict(photo_complete)
    photo_importante["transits"] = [
        transit
        for transit in photo_complete.get("transits", [])
        if transit.get("importance", 0) >= IMPORTANCE_TRANSIT_DU_MOMENT
    ]
    return photo_importante, _selectionner_transits_visibles(photo_importante)


@espace_personnel_bp.route("/profil/avatar", methods=["POST"])
def modifier_avatar():
    """Change uniquement le personnage du membre connecté."""
    verifier_csrf_espace()
    utilisateur = _utilisateur_espace_courant()
    personnage = request.form.get("avatar_personnage")
    if personnage is None or (personnage and personnage not in AVATARS_ESPACE):
        abort(400, "Choisis un personnage proposé ou Sans avatar.")
    utilisateur.avatar_personnage = personnage or None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Ton avatar n’a pas pu être enregistré. Réessaie après avoir rechargé la page.", "error")
    else:
        flash("Ton avatar est enregistré.", "success")
    return redirect(url_for("espace_personnel.profil") + "#mon-avatar")


@espace_personnel_bp.route("/profil/journal-mails", methods=["POST"])
def modifier_autorisation_journal_mails():
    """Enregistre seulement le choix du membre connecté, sans recalcul ni IA."""
    verifier_csrf_espace()
    utilisateur = _utilisateur_espace_courant()
    valeur = request.form.get("autoriser_journal_mails")
    if valeur not in {"oui", "non"}:
        abort(400, "Choisis si tu autorises ou non l'utilisation de ton journal dans les mails.")
    utilisateur.autoriser_journal_mails = valeur == "oui"
    utilisateur.journal_mails_choix_le = datetime.now(timezone.utc)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Ton choix n'a pas pu être enregistré. Réessaie après avoir rechargé la page.", "error")
    else:
        flash("Ton choix est enregistré pour les prochaines générations de mails.", "success")
    return redirect(url_for("espace_personnel.profil") + "#journal-mails")


@espace_personnel_bp.route("/energies-du-moment")
def energies_du_moment():
    profil_astral = _profil_astral_courant()
    photo_transits, transits_visibles = _energies_du_moment(profil_astral)
    return render_template(
        "espace_personnel/energies_du_moment.html",
        profil=profil_astral,
        photo_transits=photo_transits,
        transits_visibles=transits_visibles,
        nombre_transits=transits_visibles.get("total_brut", 0),
    )


def _email_cycle_courant_ou_404(email_id):
    profil = _profil_astral_courant()
    if profil is None:
        abort(404)
    return EmailCycleAbonnement.query.filter_by(
        id=email_id,
        profil_id=profil.id,
    ).first_or_404()


def _charger_preparation_email(email):
    try:
        donnees = json.loads(email.declencheur_factuel or "{}")
    except (TypeError, json.JSONDecodeError):
        donnees = {}
    return donnees if isinstance(donnees, dict) else {}


@espace_personnel_bp.route("/emails-cycle/<int:email_id>/prompt")
def lire_prompt_mail_cycle(email_id):
    email = _email_cycle_courant_ou_404(email_id)
    preparation = _charger_preparation_email(email)
    if not (email.contenu_texte or email.contenu_html) and preparation.get("version_contrat") == VERSION_CONTRAT:
        preparation = actualiser_mail_quinzaine(_profil_astral_courant(), preparation)
    return Response(preparation.get("prompt", "Prompt absent"), mimetype="text/plain", headers={"Cache-Control": "private, no-store"})


@espace_personnel_bp.route("/emails-cycle/<int:email_id>/journaux/<execution>/<nom>")
def lire_journal_mail_cycle(email_id, execution, nom):
    email = _email_cycle_courant_ou_404(email_id)
    if nom not in FICHIERS_MAIL or not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{12}", execution):
        abort(404)
    return send_from_directory(str(dossier_journaux_mail() / str(email.id) / execution), nom,
                               mimetype="text/plain", as_attachment=False)


def _dates_periode_journal(formulaire, date_debut):
    """Une période sans fin correspond explicitement à « toujours en cours »."""
    type_entree = formulaire.get("type_entree", "journee")
    if type_entree not in {"journee", "periode"}:
        raise ValueError("Choisis une journée ou une période.")
    if type_entree == "journee":
        return False, None
    if formulaire.get("toujours_en_cours") == "oui":
        return True, None
    try:
        date_fin = datetime.strptime(formulaire.get("date_fin_periode", ""), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError("Renseigne la date de fin ou coche « Toujours en cours ».")
    if date_fin < date_debut.date():
        raise ValueError("La date de fin doit être égale ou postérieure à la date de début.")
    return True, date_fin


@espace_personnel_bp.route(
    "/mes-analyses/<int:analyse_id>/preparer",
    methods=["POST"],
)
def preparer_analyse(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)
    destination = url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id)
    try:
        with verrou_mecanismes(analyse.id):
            preparer_sections_mecanismes(analyse, lambda: _pdf_pour_extraction(analyse))
    except ExtractionMecanismesEnCours as erreur:
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec de lecture du rapport %s", analyse.id)
        flash("Le PDF n’a pas pu être lu. Utilise un PDF avec du texte sélectionnable. Aucun appel IA n’a été lancé.", "error")
    else:
        flash("Ton rapport est prêt. Tu peux demander les mécanismes avec l’IA.", "success")
    return redirect(destination)


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/explorer", methods=["GET", "POST"])
def explorer_analyse(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)

    if request.method == "POST":
        titre = majuscule_initiale(request.form.get("titre", ""))
        hypothese = request.form.get("hypothese", "").strip()
        ressenti = request.form.get("ressenti", "a_observer").strip()
        statut = request.form.get("statut", "a_explorer").strip()

        if not titre or not hypothese:
            flash("Le titre et l’hypothèse sont obligatoires.", "error")
        elif ressenti not in RESSENTIS_MECANISME or statut not in STATUTS_MECANISME:
            flash("Le ressenti ou le statut sélectionné n’est pas valide.", "error")
        else:
            mecanisme = MecanismeExploration(
                analyse_id=analyse.id,
                titre=titre,
                extrait_source=request.form.get("extrait_source", "").strip() or None,
                hypothese=hypothese,
                effets_possibles=request.form.get("effets_possibles", "").strip() or None,
                ressenti=ressenti,
                statut=statut,
                piste_experimentation=request.form.get(
                    "piste_experimentation",
                    "",
                ).strip() or None,
            )
            try:
                db.session.add(mecanisme)
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Le mécanisme n’a pas pu être enregistré.", "error")
            else:
                flash("Le mécanisme a été ajouté à ton exploration.", "success")
                return redirect(
                    url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id)
                    + "#mes-mecanismes"
                )

    mecanismes = (
        MecanismeExploration.query
        .filter_by(analyse_id=analyse.id)
        .order_by(MecanismeExploration.date_creation.desc())
        .all()
    )
    sections_analyse = (
        SectionAnalyse.query
        .filter_by(analyse_id=analyse.id)
        .order_by(SectionAnalyse.ordre.asc())
        .all()
    )
    suggestions_enregistrees = (
        SuggestionMecanisme.query
        .filter_by(analyse_id=analyse.id)
        .order_by(SuggestionMecanisme.priorite.asc())
        .all()
    )
    suggestions = []
    for suggestion in suggestions_enregistrees:
        try:
            manifestations = json.loads(suggestion.manifestations_possibles or "[]")
        except (TypeError, ValueError):
            manifestations = []
        try:
            references = json.loads(suggestion.references_astrologiques or "[]")
        except (TypeError, ValueError):
            references = []
        suggestions.append({
            "objet": suggestion,
            "manifestations": manifestations,
            "references": references,
        })
    enjeux_periode = []
    for enjeu in (
        EnjeuPeriode.query
        .filter_by(analyse_id=analyse.id)
        .order_by(EnjeuPeriode.ordre.asc())
        .all()
    ):
        try:
            references = json.loads(enjeu.references_astrologiques or "[]")
        except (TypeError, ValueError):
            references = []
        enjeux_periode.append({"objet": enjeu, "references": references})
    enjeux_rs = (
        EnjeuAnnuel.query.filter_by(analyse_id=analyse.id).order_by(EnjeuAnnuel.ordre).all()
        if analyse.type_analyse == "revolution_solaire" else []
    )
    return render_template(
        "espace_personnel/explorer_analyse.html",
        analyse=analyse,
        mecanismes=mecanismes,
        sections_analyse=sections_analyse,
        sections_par_id={section.id: section for section in sections_analyse},
        suggestions=suggestions,
        enjeux_periode=enjeux_periode,
        titre_enjeux=(
            "Enjeux de fond de ton thème"
            if analyse.type_analyse == "forces_defis"
            else "Grands enjeux de la période"
        ),
        suggestion_reportee=request.args.get("reportee", type=int),
        ressentis=RESSENTIS_MECANISME,
        statuts=STATUTS_MECANISME,
        enjeux_annuels=[{
            "objet": enjeu,
            "manifestations": json.loads(enjeu.manifestations_possibles or "[]"),
            "references": json.loads(enjeu.references_astrologiques or "[]"),
        } for enjeu in enjeux_rs],
        propositions_rs_a_verifier=(
            propositions_rs_a_verifier(_dossier_extractions_rs(), analyse.id, enjeux_rs)
            if analyse.type_analyse == "revolution_solaire" and administratrice_connectee() else []
        ),
        journaux_rs=(
            _journaux_extraction_rs(analyse.id)
            if analyse.type_analyse == "revolution_solaire" and administratrice_connectee() else []
        ),
    )


@espace_personnel_bp.route(
    "/mes-analyses/<int:analyse_id>/enjeux/generer",
    methods=["POST"],
)
def generer_enjeux_periode(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)
    if analyse.type_analyse not in {"transits", "forces_defis"}:
        abort(404)
    if EnjeuPeriode.query.filter_by(analyse_id=analyse.id).first():
        flash("Les grands enjeux de cette période ont déjà été générés.", "error")
        return redirect(url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id))

    sections = (
        SectionAnalyse.query
        .filter_by(analyse_id=analyse.id)
        .order_by(SectionAnalyse.ordre.asc())
        .all()
    )
    if not sections:
        if not analyse.chemin_resultat:
            flash("Le PDF de cette période est introuvable.", "error")
            return redirect(url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id))
        chemin_pdf = _pdf_pour_extraction(analyse)
        extracteur = (
            extraire_sections_forces_defis
            if analyse.type_analyse == "forces_defis"
            else extraire_sections_transits
        )
        sections_extraites = extracteur(chemin_pdf)
        sections_dict = [
            {
                "cle_section": section["cle_section"],
                "titre": section["titre"],
                "contenu": section["contenu"],
            }
            for section in sections_extraites
        ]
    else:
        sections_extraites = None
        sections_dict = [
            {
                "cle_section": section.cle_section,
                "titre": section.titre,
                "contenu": section.contenu,
            }
            for section in sections
        ]

    try:
        generer_enjeux = (
            generer_enjeux_forces_defis_avec_claude
            if analyse.type_analyse == "forces_defis"
            else generer_enjeux_transits_avec_claude
        )
        enjeux, usage = generer_enjeux(sections_dict)
        maintenant = datetime.now(timezone.utc)
        if sections_extraites is not None:
            for section in sections_extraites:
                db.session.add(SectionAnalyse(
                    analyse_id=analyse.id,
                    cle_section=section["cle_section"],
                    titre=section["titre"],
                    contenu=section["contenu"],
                    ordre=section["ordre"],
                    source_format="pdf_importe",
                    date_creation=maintenant,
                    date_modification=maintenant,
                ))
        for ordre, enjeu in enumerate(enjeux, 1):
            db.session.add(EnjeuPeriode(
                analyse_id=analyse.id,
                contenu=enjeu.contenu,
                references_astrologiques=json.dumps(
                    enjeu.references_astrologiques,
                    ensure_ascii=False,
                ),
                ordre=ordre,
                date_creation=maintenant,
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec de génération des enjeux pour %s", analyse.type_analyse)
        flash("Les enjeux n'ont pas pu être générés ou validés.", "error")
    else:
        flash(
            f"{len(enjeux)} enjeux générés · {usage['tokens_total']} tokens utilisés.",
            "success",
        )
    return redirect(
        url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id)
        + "#enjeux-periode"
    )


def _dossier_extractions_rs():
    return os.path.join(racine_privee_espace(), "extractions_rs")


def _journaux_extraction_rs(analyse_id):
    from pathlib import Path
    dossier = Path(_dossier_extractions_rs()) / str(analyse_id)
    if not dossier.is_dir():
        return []
    return [
        {"id": execution.name, "fichiers": [nom for nom in FICHIERS_LOG_RS if (execution / nom).is_file()]}
        for execution in sorted(dossier.iterdir(), reverse=True)
        if execution.is_dir() and re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{12}", execution.name)
    ]


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/extractions-rs/<execution>/<nom>")
def lire_journal_extraction_rs(analyse_id, execution, nom):
    analyse = _analyse_courante_ou_404(analyse_id)
    if (analyse.type_analyse != "revolution_solaire" or nom not in FICHIERS_LOG_RS
            or not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{12}", execution)):
        abort(404)
    return send_from_directory(
        os.path.join(_dossier_extractions_rs(), str(analyse.id), execution), nom,
        mimetype="text/plain", as_attachment=False,
    )


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/enjeux-annuels/generer", methods=["POST"])
def generer_enjeux_annuels(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)
    if analyse.type_analyse != "revolution_solaire":
        abort(404)
    return _generer_enjeux_revolution_solaire(analyse)


def _enregistrer_enjeux_rs(analyse_id, sections, propositions):
    sources = {section.cle_section: section.id for section in sections}
    for ordre, proposition in enumerate(propositions, 1):
        db.session.add(EnjeuAnnuel(
            analyse_id=analyse_id, section_id=sources[proposition.cle_section],
            titre=proposition.titre, contenu=proposition.hypothese,
            manifestations_possibles=json.dumps(proposition.manifestations_possibles, ensure_ascii=False),
            extrait_source=proposition.extrait_source,
            references_astrologiques=json.dumps(proposition.references_astrologiques, ensure_ascii=False),
            ordre=ordre, retenu_email=False,
        ))


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/extractions-rs/<execution>/reprendre", methods=["POST"])
def reprendre_extraction_rs(analyse_id, execution):
    """Contrôle la réponse déjà payée, uniquement au clic, sans appel fournisseur."""
    from pathlib import Path
    analyse = _analyse_courante_ou_404(analyse_id)
    if analyse.type_analyse != "revolution_solaire" or not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{12}", execution):
        abort(404)
    dossier = Path(_dossier_extractions_rs()) / str(analyse.id) / execution
    if not (dossier / "reponse_brute.txt").is_file() or not (dossier / "usage.json").is_file():
        abort(404)
    destination = url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id) + "#enjeux-annuels"
    try:
        with verrou_extraction_rs(_dossier_extractions_rs(), analyse.id):
            if EnjeuAnnuel.query.filter_by(analyse_id=analyse.id).first():
                flash("Des enjeux sont déjà enregistrés pour ce PDF. Aucun appel IA.", "success")
                return redirect(destination)
            usage = json.loads((dossier / "usage.json").read_text(encoding="utf-8"))
            if usage.get("stop_reason") != "end_turn":
                raise ValueError("Cette réponse est incomplète et ne peut pas être reprise.")
            sections = SectionAnalyse.query.filter_by(analyse_id=analyse.id).order_by(SectionAnalyse.ordre).all()
            propositions, _, rejets = lire_reponse_enjeux_rs(
                (dossier / "reponse_brute.txt").read_text(encoding="utf-8"),
                [{"cle_section": s.cle_section, "titre": s.titre, "contenu": s.contenu} for s in sections],
                reprise_partielle=True,
            )
            _enregistrer_enjeux_rs(analyse.id, sections, propositions)
            db.session.commit()
            diagnostic = {
                "statut": "repris_partiellement" if rejets else "repris",
                "nombre": len(propositions), "enjeux_ecartes": rejets, "appel_ia": False,
            }
    except ValueError as erreur:
        db.session.rollback()
        diagnostic = {"statut": "echec_reprise", "detail": str(erreur), "appel_ia": False}
        flash(f"Reprise locale refusée : {erreur} Aucun appel IA n’a été fait.", "error")
    except Exception:
        db.session.rollback()
        diagnostic = {"statut": "echec_enregistrement", "appel_ia": False}
        current_app.logger.exception("Échec de reprise locale de l’extraction %s", execution)
        flash("La reprise n’a pas pu être enregistrée. Aucun appel IA n’a été fait.", "error")
    else:
        flash(f"{len(propositions)} enjeux récupérés depuis la réponse conservée, sans nouvel appel IA. Ils restent à relire et à sélectionner pour tes mails.", "success")
        for rejet in rejets:
            flash(f"Proposition conservée dans « Source à vérifier » : {rejet['titre']} — {rejet['motif']}", "error")
    texte = json.dumps(diagnostic, ensure_ascii=False, indent=2)
    (dossier / "reprise_locale.json").write_text(texte, encoding="utf-8")
    print(f"[EXPLORATION RS {analyse.id}] Reprise locale : {texte}", flush=True)
    return redirect(destination)


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/enjeux-annuels/retenir", methods=["POST"])
def retenir_enjeux_annuels(analyse_id):
    analyse = _analyse_courante_ou_404(analyse_id)
    if analyse.type_analyse != "revolution_solaire":
        abort(404)
    selection = set(request.form.getlist("enjeux_retenus"))
    enjeux = EnjeuAnnuel.query.filter_by(analyse_id=analyse.id).all()
    if not selection <= {str(enjeu.id) for enjeu in enjeux}:
        abort(400)
    for enjeu in enjeux:
        enjeu.retenu_email = str(enjeu.id) in selection
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Ta sélection n’a pas pu être enregistrée.", "error")
    else:
        flash("Ta sélection d’enjeux pour les prochains mails est enregistrée. Aucun mail n’a été généré ni envoyé.", "success")
    return redirect(url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id) + "#enjeux-annuels")


@espace_personnel_bp.route("/mes-analyses/<int:analyse_id>/enjeux-annuels/valider-source", methods=["POST"])
def valider_source_enjeu_annuel(analyse_id):
    """Validation humaine explicite d'une proposition jusque-là exclue des mails."""
    analyse = _analyse_courante_ou_404(analyse_id)
    if analyse.type_analyse != "revolution_solaire":
        abort(404)
    execution = request.form.get("execution", "")
    numero = request.form.get("numero", type=int)
    if not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{12}", execution) or numero not in range(1, 6):
        abort(400)
    destination = url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id) + "#enjeux-annuels"
    if request.form.get("confirmation_source") != "oui":
        flash("Confirme d’abord avoir relu le PDF et vérifié que cet enjeu y est soutenu.", "error")
        return redirect(destination)
    try:
        with verrou_extraction_rs(_dossier_extractions_rs(), analyse.id):
            enjeux = EnjeuAnnuel.query.filter_by(analyse_id=analyse.id).all()
            if any(e.execution_source == execution and e.numero_source == numero for e in enjeux):
                flash("Cet enjeu a déjà été validé manuellement. Aucun doublon ajouté.", "success")
                return redirect(destination)
            candidats = propositions_rs_a_verifier(_dossier_extractions_rs(), analyse.id, enjeux)
            candidat = next((c for c in candidats if c["execution"] == execution and c["numero"] == numero), None)
            if candidat is None:
                flash("Cette proposition n’est plus en attente de vérification.", "error")
                return redirect(destination)
            section = SectionAnalyse.query.filter_by(analyse_id=analyse.id, cle_section=candidat["cle_section"].strip("[]")).first()
            if section is None:
                raise ValueError("La page indiquée n’existe pas dans ce PDF.")
            db.session.add(EnjeuAnnuel(
                analyse_id=analyse.id, section_id=section.id,
                ordre=max((e.ordre for e in enjeux), default=0) + 1,
                titre=candidat["titre"], contenu=candidat["contenu"],
                manifestations_possibles=json.dumps(candidat["manifestations_possibles"], ensure_ascii=False),
                references_astrologiques=json.dumps(candidat["references_astrologiques"], ensure_ascii=False),
                extrait_source=candidat["extrait_source"], retenu_email=True,
                source_validation="validation_manuelle", execution_source=execution, numero_source=numero,
            ))
            db.session.commit()
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec de validation manuelle d’un enjeu annuel %s", analyse.id)
        flash("Ta validation n’a pas pu être enregistrée.", "error")
    else:
        flash("Enjeu validé par toi et retenu pour tes prochains mails. Aucun appel IA ni envoi.", "success")
    return redirect(destination)


def _generer_enjeux_revolution_solaire(analyse):
    destination = url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id) + "#enjeux-annuels"
    profil = _profil_astral_courant()
    if profil is None:
        abort(404)
    cycle = CycleSolaire.query.filter_by(id=analyse.cycle_solaire_id, profil_id=profil.id).first_or_404()
    try:
        with verrou_extraction_rs(_dossier_extractions_rs(), analyse.id):
            if EnjeuAnnuel.query.filter_by(analyse_id=analyse.id).first():
                flash("Les enjeux ont déjà été extraits de cette version du PDF.", "error")
                return redirect(destination)
            sections = SectionAnalyse.query.filter_by(analyse_id=analyse.id).order_by(SectionAnalyse.ordre).all()
            if not sections:
                raise ValueError("Le texte de ce PDF n’est pas disponible pour l’extraction.")
            suggestions, usage, execution, a_verifier = generer_enjeux_rs(
                [{"cle_section": s.cle_section, "titre": s.titre, "contenu": s.contenu} for s in sections],
                _dossier_extractions_rs(), analyse.id, cycle.annee,
            )
            _enregistrer_enjeux_rs(analyse.id, sections, suggestions)
            db.session.commit()
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec d’enregistrement des enjeux annuels de l’analyse %s", analyse.id)
        flash("Les enjeux n’ont pas pu être enregistrés. Consulte les journaux conservés ; aucune relance automatique.", "error")
    else:
        flash(f"{len(suggestions)} enjeux avec extrait vérifié et {len(a_verifier)} propositions avec source à vérifier pour {cycle.annee} · {usage['tokens_total']} tokens utilisés. Aucun enjeu n’est ajouté aux mails sans ton choix.", "success")
    return redirect(destination)


@espace_personnel_bp.route("/suggestions/<int:suggestion_id>/reporter", methods=["POST"])
def reporter_suggestion(suggestion_id):
    suggestion = _suggestion_courante_ou_404(suggestion_id)
    if suggestion.statut != "proposee":
        flash("Cette piste a déjà été traitée.", "error")
        destination = url_for(
            "espace_personnel.explorer_analyse",
            analyse_id=suggestion.analyse_id,
        )
    else:
        destination = url_for(
            "espace_personnel.explorer_analyse",
            analyse_id=suggestion.analyse_id,
            reportee=suggestion.id,
        )
    return redirect(destination + f"#suggestion-{suggestion.id}")


@espace_personnel_bp.route("/revolutions-solaires/<int:cycle_id>/importer", methods=["POST"])
def importer_revolution_solaire(cycle_id):
    """Archive une nouvelle version PDF sans modifier le calcul ni le rapport annuel existant."""
    utilisateur = _utilisateur_espace_courant()
    profil = _profil_astral_courant()
    if profil is None:
        abort(404)
    cycle = CycleSolaire.query.filter_by(id=cycle_id, profil_id=profil.id).first_or_404()
    fichier = request.files.get("rapport")
    destination = url_for("espace_personnel.revolutions_solaires") + f"#annee-{cycle.annee}"
    if not fichier or not fichier.filename:
        flash("Sélectionne le PDF de ton analyse annuelle.", "error")
        return redirect(destination)
    # Contrôle sur le fichier lui-même, indépendamment de Content-Length.
    contenu = fichier.stream.read(TAILLE_MAX_RAPPORT + 1)
    if len(contenu) > TAILLE_MAX_RAPPORT or not contenu.startswith(b"%PDF-"):
        flash("Choisis un PDF valide de 15 Mo maximum.", "error")
        return redirect(destination)
    nom = f"{uuid.uuid4().hex}.pdf"
    chemin = os.path.join(_dossier_rapports_importes(), nom)
    try:
        with open(chemin, "wb") as sortie:
            sortie.write(contenu)
        _verifier_pdf_fous_astro(chemin, "revolution_solaire")
        # Préparation locale : aucun appel IA pendant l'import.
        sections = extraire_pages_rs(chemin)
        analyse = AnalysePersonnelle(
            utilisateur_id=utilisateur.id, cycle_solaire_id=cycle.id,
            type_analyse="revolution_solaire", titre=f"Révolution solaire {cycle.annee}",
            statut="terminee", chemin_resultat=nom,
            date_generation=None,
        )
        db.session.add(analyse)
        db.session.flush()
        db.session.add(FichierAnalyse(analyse_id=analyse.id, nom_fichier=nom, contenu=contenu))
        db.session.flush()
        for section in sections:
            db.session.add(SectionAnalyse(analyse_id=analyse.id, source_format="pdf_importe", **section))
        db.session.commit()
        try:
            os.remove(chemin)
        except OSError:
            current_app.logger.warning("Nettoyage du PDF temporaire à effectuer après import %s", analyse.id)
    except ValueError as erreur:
        db.session.rollback()
        if os.path.isfile(chemin):
            os.remove(chemin)
        flash(str(erreur), "error")
    except Exception:
        db.session.rollback()
        if os.path.isfile(chemin):
            os.remove(chemin)
        current_app.logger.exception("Échec d’import du PDF annuel du cycle %s", cycle.id)
        flash("Le PDF n’a pas pu être importé. Les versions précédentes sont conservées.", "error")
    else:
        flash("Ton PDF annuel est ajouté. Tu peux maintenant en faire ressortir les grands enjeux de l’année.", "success")
        return redirect(url_for("espace_personnel.explorer_analyse", analyse_id=analyse.id))
    return redirect(destination)


enregistrer_routes_auth(espace_personnel_bp)


def _pdf_pour_extraction(analyse):
    """Copie éphémère d'un PDF privé en base ; aucun chemin client utilisé."""
    fichier = FichierAnalyse.query.filter_by(analyse_id=analyse.id).first_or_404()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as sortie:
        sortie.write(fichier.contenu)
        chemin = sortie.name
    g.setdefault('pdfs_extraction_temporaires', []).append(chemin)
    return chemin


@espace_personnel_bp.teardown_request
def nettoyer_pdf_extraction(erreur):
    for chemin in g.pop('pdfs_extraction_temporaires', []):
        try:
            os.remove(chemin)
        except FileNotFoundError:
            pass


espace_personnel_bp.add_url_rule('/<int:entree_id>', view_func=fiche, methods=['GET'])
espace_personnel_bp.add_url_rule('/<int:entree_id>/modifier', view_func=modifier, methods=['GET', 'POST'])
espace_personnel_bp.add_url_rule('/<int:entree_id>/supprimer', view_func=supprimer, methods=['POST'])


@espace_personnel_bp.app_template_filter("majuscule_initiale")
def majuscule_initiale(valeur):
    """Met la première lettre en majuscule sans changer le reste du titre."""
    texte = (valeur or "").strip()
    return texte[:1].upper() + texte[1:]


@espace_personnel_bp.route("/observations-mecanisme/<int:observation_id>/decoder", methods=["GET", "POST"])
def decoder_mecanisme(observation_id):
    """Décodage manuel d'un épisode du membre connecté, sans moteur IA."""
    from sqlalchemy.exc import IntegrityError
    from utils.decodage_mecanisme import (
        AIDES_DECODAGE, ConflitDecodage, ETAPES_DECODAGE, lire_reponses_decodage, reponses_depuis_formulaire,
    )

    observation = _observation_courante_ou_404(observation_id)
    mecanisme = _mecanisme_courant_ou_404(observation.mecanisme_id)
    decodage = DecodageObservationMecanisme.query.filter_by(observation_id=observation.id).first()
    entree = EntreeJournal.query.filter_by(
        id=observation.entree_journal_id,
        utilisateur_id=_utilisateur_espace_courant().id,
    ).first() if observation.entree_journal_id else None
    reponses = lire_reponses_decodage(decodage.reponses) if decodage else {
        "reactions": observation.reaction_automatique or "",
        "consequences": observation.resultat_obtenu or "",
        "emotion_visible": entree.emotions or "" if entree else "",
    }
    revision = decodage.revision if decodage else 0
    etape = max(1, min(6, request.values.get("etape", 1, type=int) or 1))
    action_decodage = request.form.get("action", "") if request.method == "POST" else ""
    action_etape = re.fullmatch(r"(etape|continuer)_([1-6])", action_decodage)
    if action_etape:
        etape = int(action_etape.group(2))
    erreur, statut = None, 200
    if request.method == "POST":
        verifier_csrf_espace()
        # Préserver la saisie à l'écran même si l'enregistrement est refusé.
        reponses = {cle: request.form.get(cle, "")
                    for bloc in ETAPES_DECODAGE for cle, _ in bloc["questions"]}
        try:
            reponses = reponses_depuis_formulaire(request.form)
            revision = request.form.get("revision", type=int)
            if revision is None or revision != (decodage.revision if decodage else 0):
                raise ConflitDecodage
            contenu = json.dumps(reponses, ensure_ascii=False)
            if decodage:
                mise_a_jour = db.session.execute(
                    update(DecodageObservationMecanisme)
                    .where(DecodageObservationMecanisme.id == decodage.id,
                           DecodageObservationMecanisme.revision == revision)
                    .values(reponses=contenu, revision=revision + 1,
                            date_modification=datetime.now(timezone.utc))
                )
                if mise_a_jour.rowcount != 1:
                    raise ConflitDecodage
            else:
                db.session.add(DecodageObservationMecanisme(
                    observation_id=observation.id, reponses=contenu,
                ))
            db.session.commit()
        except ValueError as probleme:
            db.session.rollback()
            erreur, statut = str(probleme), 400
        except (IntegrityError, ConflitDecodage):
            db.session.rollback()
            erreur = "Une autre version a été enregistrée. Ta saisie reste affichée ; conserve-la avant de recharger la page."
            statut = 409
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Enregistrement du décodage impossible pour l’observation %s", observation.id)
            erreur, statut = "Tes réponses n’ont pas pu être enregistrées. Elles restent affichées pour que tu puisses réessayer.", 500
        else:
            flash("Tes réponses sont enregistrées. Tu peux reprendre ce décodage quand tu le souhaites.", "success")
            if request.form.get("action") == "plus_tard":
                if entree:
                    return redirect(url_for("espace_personnel.journal") + f"#entree-{entree.id}")
                return redirect(url_for("espace_personnel.fiche_mecanisme", mecanisme_id=mecanisme.id)
                                + f"#observation-{observation.id}")
            if action_etape and action_etape.group(1) == "continuer":
                etape = min(6, etape + 1)
            return redirect(url_for("espace_personnel.decoder_mecanisme", observation_id=observation.id,
                                    etape=etape, enregistre=1) + f"#etape-{etape}")
    historique = (ObservationMecanisme.query.filter_by(mecanisme_id=mecanisme.id)
                  .order_by(ObservationMecanisme.date_observation.desc()).all())
    return render_template(
        "espace_personnel/decoder_mecanisme.html", observation=observation,
        mecanisme=mecanisme, entree=entree, etapes=ETAPES_DECODAGE, aides=AIDES_DECODAGE,
        reponses=reponses, revision=revision, etape_ouverte=etape,
        erreur=erreur, decodage=decodage, historique=historique,
        mecanismes_meme_situation=_liaisons_de_situation(entree.id, entree.utilisateur_id) if entree else [],
    ), statut


def _contexte_mecanismes_journal(utilisateur_id):
    """Accès direct au décodage dans le journal, limité aux données du membre."""
    mecanismes = (MecanismeExploration.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur_id)
        .order_by(MecanismeExploration.titre.asc()).all())
    par_id = {m.id: m for m in mecanismes}
    liaisons = {}
    if par_id:
        observations = (ObservationMecanisme.query
            .join(EntreeJournal, EntreeJournal.id == ObservationMecanisme.entree_journal_id)
            .filter(EntreeJournal.utilisateur_id == utilisateur_id,
                    ObservationMecanisme.mecanisme_id.in_(par_id))
            .order_by(ObservationMecanisme.date_creation.asc()).all())
        for observation in observations:
            liaisons.setdefault(observation.entree_journal_id, []).append(observation)
    return {"mecanismes_journal": mecanismes, "mecanismes_journal_par_id": par_id,
            "liaisons_journal": liaisons}


def _mecanismes_choisis_journal(formulaire, utilisateur_id):
    """Accepte les cases à cocher et les anciens formulaires à choix unique."""
    valeurs = formulaire.getlist("mecanisme_ids") + formulaire.getlist("mecanisme_id")
    try:
        ids = list(dict.fromkeys(int(v) for v in valeurs if v.strip()))
        if any(i <= 0 for i in ids):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Choisis des mécanismes présents dans ton Labo.")
    if not ids:
        return []
    mecanismes = (MecanismeExploration.query
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur_id,
                MecanismeExploration.id.in_(ids)).all())
    par_id = {m.id: m for m in mecanismes}
    if set(ids) != set(par_id):
        raise ValueError("Choisis uniquement des mécanismes présents dans ton Labo.")
    return [par_id[i] for i in ids]


def _relier_situation_aux_mecanismes(entree, mecanismes):
    """Crée seulement les liens manquants ; le demandeur valide la transaction."""
    if not mecanismes:
        return []
    EntreeJournal.query.filter_by(id=entree.id, utilisateur_id=entree.utilisateur_id).with_for_update().one()
    existants = {o.mecanisme_id: o for o in ObservationMecanisme.query.filter_by(entree_journal_id=entree.id).all()}
    liaisons = []
    for mecanisme in mecanismes:
        liaison = existants.get(mecanisme.id)
        if liaison is None:
            liaison = ObservationMecanisme(
                mecanisme_id=mecanisme.id, entree_journal_id=entree.id,
                date_observation=entree.date_observation,
                situation=entree.situation or entree.emotions or entree.notes_libres or "Situation notée dans le journal.",
                reaction_automatique=entree.reaction_automatique,
                indice_pour=request.form.get("indice_pour", "").strip() or None,
                notes_libres=entree.notes_libres,
            )
            db.session.add(liaison)
        liaisons.append(liaison)
    db.session.flush()
    return liaisons


def _liaisons_de_situation(entree_id, utilisateur_id):
    return (db.session.query(ObservationMecanisme, MecanismeExploration)
        .join(MecanismeExploration, MecanismeExploration.id == ObservationMecanisme.mecanisme_id)
        .join(AnalysePersonnelle, AnalysePersonnelle.id == MecanismeExploration.analyse_id)
        .filter(ObservationMecanisme.entree_journal_id == entree_id,
                AnalysePersonnelle.utilisateur_id == utilisateur_id)
        .order_by(MecanismeExploration.titre.asc()).all())


@espace_personnel_bp.route("/journal/<int:entree_id>/decoder")
def decoder_situation(entree_id):
    entree = _entree_courante_ou_404(entree_id)
    liaisons = _liaisons_de_situation(entree.id, entree.utilisateur_id)
    if len(liaisons) == 1:
        return redirect(url_for("espace_personnel.decoder_mecanisme", observation_id=liaisons[0][0].id))
    return render_template("espace_personnel/choisir_decodage.html", entree=entree,
                           mecanisme=None, liaisons=liaisons, observations=[], entrees_disponibles=[])


@espace_personnel_bp.route("/mecanismes/<int:mecanisme_id>/decoder", methods=["GET", "POST"])
def decoder_depuis_labo(mecanisme_id):
    mecanisme = _mecanisme_courant_ou_404(mecanisme_id)
    if request.method == "POST":
        verifier_csrf_espace()
        if request.form.getlist("mecanisme_ids") != [str(mecanisme.id)]:
            abort(400)
        entree_id = request.form.get("entree_id", type=int)
        if not entree_id:
            flash("Choisis une situation dans ton journal.", "error")
        else:
            return relier_entree_mecanisme(entree_id)
    observations = (ObservationMecanisme.query.filter_by(mecanisme_id=mecanisme.id)
                    .order_by(ObservationMecanisme.date_observation.desc()).all())
    if len(observations) == 1 and request.method == "GET":
        return redirect(url_for("espace_personnel.decoder_mecanisme", observation_id=observations[0].id))
    ids_relies = {o.entree_journal_id for o in observations if o.entree_journal_id}
    entrees = (EntreeJournal.query.filter_by(utilisateur_id=_utilisateur_espace_courant().id)
               .order_by(EntreeJournal.date_observation.desc()).all())
    return render_template("espace_personnel/choisir_decodage.html", mecanisme=mecanisme,
                           entree=None, liaisons=[], observations=observations,
                           entrees_disponibles=[e for e in entrees if e.id not in ids_relies])
