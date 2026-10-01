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
    MecanismeExploration, ObservationMecanisme, ProfilAstral, SuggestionMecanisme,
    UtilisateurEspace,
)
from utils.acces_abonnement import acces_abonnement
from utils.calcul_theme import calcul_theme
from utils.acces_espace import (
    consommer_lien_connexion,
    creer_lien_connexion,
    email_invite,
    lien_recent,
    trouver_ou_creer_utilisateur,
)
from utils.email_sender import envoyer_email_avec_analyse


espace_personnel_bp = Blueprint("espace_personnel", __name__, url_prefix="/mon-espace")
DUREE_SESSION_ESPACE = timedelta(days=14)


@espace_personnel_bp.record_once
def configurer_session_espace(etat):
    etat.app.permanent_session_lifetime = DUREE_SESSION_ESPACE

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
TITRES_PDF_PAR_ANALYSE = {
    "point_astral_essentiel": ("point astral", "flash astral"),
    "racines_familiales": ("racines familiales", "point astral racines", "point astral", "flash astral"),
    "profil_amoureux": ("profil amoureux",),
    "forces_defis": ("potentiels defis", "potentiel defis", "forces defis"),
    "analyse_karmique": ("analyse karmique",),
    "transits": ("point transits", "flash transits", "transits"),
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
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    return utilisateur if utilisateur is not None and utilisateur.actif == 1 else None


def _jeton_formulaire_portail():
    jeton = session.get("espace_formulaire_csrf")
    if not jeton:
        jeton = secrets.token_urlsafe(32)
        session["espace_formulaire_csrf"] = jeton
    return jeton


def _verifier_formulaire_portail():
    return hmac.compare_digest(
        request.form.get("espace_csrf", ""), _jeton_formulaire_portail()
    )


@espace_personnel_bp.before_request
def verifier_session_espace():
    if not session.get("utilisateur_espace_id"):
        return None
    debut = session.get("espace_connecte_le")
    if debut:
        try:
            instant = datetime.fromisoformat(debut)
            expire = instant.tzinfo is None or datetime.now(timezone.utc) - instant >= DUREE_SESSION_ESPACE
        except (TypeError, ValueError):
            expire = True
        if expire:
            session.clear()
            if request.endpoint != "espace_personnel.connexion":
                return redirect(url_for("espace_personnel.connexion"))
            return None
    _jeton_formulaire_portail()
    return None


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


@espace_personnel_bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "GET":
        if _compte_connecte() is not None:
            return redirect(url_for("espace_personnel.accueil"))
        return render_template("espace_personnel/connexion.html")
    if not verifier_turnstile():
        return render_template(
            "espace_personnel/connexion.html",
            erreur="La vérification de sécurité a échoué. Réessaie.",
        ), 400

    email = (request.form.get("email") or "").strip().lower()
    prenom = (request.form.get("prenom") or "").strip()
    if not email or "@" not in email or len(email) > 255:
        return render_template(
            "espace_personnel/connexion.html",
            erreur="Renseigne une adresse e-mail valide.",
        ), 400

    if email_invite(email):
        try:
            utilisateur = trouver_ou_creer_utilisateur(email, prenom)
            if utilisateur.actif != 1:
                db.session.rollback()
                return render_template("espace_personnel/connexion.html", confirmation=True)
            if lien_recent(utilisateur.id):
                db.session.rollback()
                return render_template(
                    "espace_personnel/connexion.html",
                    erreur="Un lien vient d'être demandé. Attends une minute avant de réessayer.",
                ), 429
            lien = creer_lien_connexion(utilisateur)
            contenu = (
                f"Bonjour {utilisateur.prenom},\n\n"
                "Voici ton lien de connexion à ton espace astral :\n\n"
                f"{lien}\n\n"
                "Il est valable 20 minutes et ne peut être utilisé qu'une fois.\n\n"
                "L'espace ouvre progressivement : tes informations de compte sont déjà "
                "accessibles, et les autres rubriques arriveront ensuite.\n\n"
                "Les Fous d'Astro"
            )
            if not envoyer_email_avec_analyse(
                destinataire=utilisateur.email,
                sujet="Ton lien de connexion — Les Fous d'Astro",
                contenu_txt=contenu,
            ):
                current_app.logger.error("Échec de l'envoi du lien de connexion à l'espace")
                return render_template(
                    "espace_personnel/connexion.html",
                    erreur="Le lien n'a pas pu être envoyé. Réessaie plus tard.",
                ), 503
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Échec de la connexion à l'espace personnel")
            return render_template(
                "espace_personnel/connexion.html",
                erreur="La connexion est momentanément indisponible. Réessaie plus tard.",
            ), 503

    return render_template("espace_personnel/connexion.html", confirmation=True)


@espace_personnel_bp.route("/connexion/<jeton>")
def valider_connexion(jeton):
    utilisateur = consommer_lien_connexion(jeton)
    if utilisateur is None:
        flash("Ce lien est invalide ou a expiré. Demande-en un nouveau.", "error")
        return redirect(url_for("espace_personnel.connexion"))
    session.clear()
    session["utilisateur_espace_id"] = utilisateur.id
    session["espace_connecte_le"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True
    return redirect(url_for("espace_personnel.accueil"))


@espace_personnel_bp.route("/")
def accueil():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        session.pop("utilisateur_espace_id", None)
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits_abonnement = acces_abonnement(abonnement)
    entrees = (
        EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id)
        .order_by(EntreeJournal.date_observation.desc()).all()
    )
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).all()
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
    """Affiche les repères déjà enregistrés, sans appel IA."""
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits = acces_abonnement(abonnement)
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
    cycle_solaire = cycle_lunaire = prochain_cycle_lunaire = dernier_email = None
    interpretation_cycle = {}
    if profil:
        cycle_solaire = (
            CycleSolaire.query.filter_by(profil_id=profil.id)
            .filter(CycleSolaire.debut_cycle_utc <= maintenant, CycleSolaire.fin_cycle_utc > maintenant)
            .order_by(CycleSolaire.debut_cycle_utc.desc()).first()
        )
        cycle_lunaire = (
            CycleLunaire.query.filter_by(profil_id=profil.id)
            .filter(CycleLunaire.debut_cycle_utc <= maintenant, CycleLunaire.fin_cycle_utc > maintenant)
            .order_by(CycleLunaire.debut_cycle_utc.desc()).first()
        )
        prochain_cycle_lunaire = (
            CycleLunaire.query.filter_by(profil_id=profil.id)
            .filter(CycleLunaire.debut_cycle_utc > maintenant)
            .order_by(CycleLunaire.debut_cycle_utc.asc()).first()
        )
        dernier_email = (
            EmailCycleAbonnement.query.filter_by(profil_id=profil.id)
            .order_by(EmailCycleAbonnement.date_creation.desc()).first()
        )
        if cycle_lunaire and cycle_lunaire.interpretation:
            try:
                interpretation_cycle = json.loads(cycle_lunaire.interpretation)
            except (TypeError, ValueError):
                pass
    if not isinstance(interpretation_cycle, dict):
        interpretation_cycle = {}
    if not droits["revolution_solaire"]:
        cycle_solaire = None
    if not droits["cycle_lunaire"]:
        cycle_lunaire = prochain_cycle_lunaire = None
        interpretation_cycle = {}

    enjeux_fond, enjeux_moment = [], []
    enjeux_rows = (
        db.session.query(EnjeuPeriode, AnalysePersonnelle)
        .join(AnalysePersonnelle, AnalysePersonnelle.id == EnjeuPeriode.analyse_id)
        .filter(AnalysePersonnelle.utilisateur_id == utilisateur.id)
        .order_by(AnalysePersonnelle.date_creation.desc(), EnjeuPeriode.ordre.asc()).all()
    )
    for enjeu, analyse in enjeux_rows:
        (enjeux_fond if analyse.type_analyse == "forces_defis" else enjeux_moment).append(
            {"objet": enjeu, "analyse": analyse}
        )
    dernieres_entrees = (
        EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id)
        .order_by(EntreeJournal.date_observation.desc()).limit(3).all()
    )
    return render_template(
        "espace_personnel/accompagnement.html",
        utilisateur_espace=utilisateur, profil=profil,
        cycle_solaire=cycle_solaire, cycle_lunaire=cycle_lunaire,
        prochain_cycle_lunaire=prochain_cycle_lunaire,
        interpretation_cycle=interpretation_cycle,
        enjeux_fond=enjeux_fond, enjeux_moment=enjeux_moment,
        dernieres_entrees=dernieres_entrees, dernier_email=dernier_email,
        droits_abonnement=droits,
    )


@espace_personnel_bp.route("/laboratoire")
def laboratoire():
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).all()
    analyses_par_id = {analyse.id: analyse for analyse in analyses}
    mecanismes_tous = (
        MecanismeExploration.query.filter(MecanismeExploration.analyse_id.in_(analyses_par_id))
        .order_by(MecanismeExploration.date_modification.desc()).all()
        if analyses_par_id else []
    )
    ids = [mecanisme.id for mecanisme in mecanismes_tous]
    observations = (
        ObservationMecanisme.query.filter(ObservationMecanisme.mecanisme_id.in_(ids))
        .order_by(ObservationMecanisme.date_observation.desc()).all()
        if ids else []
    )
    suivis = {}
    for observation in observations:
        suivi = suivis.setdefault(
            observation.mecanisme_id,
            {"nombre": 0, "derniere_date": observation.date_observation},
        )
        suivi["nombre"] += 1
    analyse_selectionnee = request.args.get("analyse", type=int)
    statut_selectionne = request.args.get("statut", "").strip()
    if statut_selectionne not in STATUTS_MECANISME:
        statut_selectionne = ""
    actifs_seulement = request.args.get("actifs") == "1"
    jamais_observes = request.args.get("jamais_observes") == "1"
    termines = {"apaise", "probablement_depasse", "non_pertinent"}
    mecanismes = [
        mecanisme for mecanisme in mecanismes_tous
        if (not analyse_selectionnee or mecanisme.analyse_id == analyse_selectionnee)
        and (not statut_selectionne or mecanisme.statut == statut_selectionne)
        and (not actifs_seulement or mecanisme.statut not in termines)
        and (not jamais_observes or mecanisme.id not in suivis)
    ]
    suggestions_a_examiner = (
        SuggestionMecanisme.query
        .filter(
            SuggestionMecanisme.analyse_id.in_(analyses_par_id),
            SuggestionMecanisme.statut == "proposee",
        )
        .order_by(SuggestionMecanisme.priorite.asc())
        .all()
        if analyses_par_id else []
    )
    if analyse_selectionnee:
        suggestions_a_examiner = [
            suggestion for suggestion in suggestions_a_examiner
            if suggestion.analyse_id == analyse_selectionnee
        ]
    statistiques = {
        "en_cours": sum(m.statut not in termines for m in mecanismes_tous),
        "en_transformation": sum(m.statut == "en_transformation" for m in mecanismes_tous),
        "depasses": sum(m.statut == "probablement_depasse" for m in mecanismes_tous),
    }
    return render_template(
        "espace_personnel/laboratoire.html",
        mecanismes=mecanismes, analyses_par_id=analyses_par_id,
        suivis_par_mecanisme=suivis,
        ressentis=RESSENTIS_MECANISME, statuts=STATUTS_MECANISME,
        statistiques=statistiques, analyses=analyses,
        analyse_selectionnee=analyse_selectionnee,
        statut_selectionne=statut_selectionne,
        actifs_seulement=actifs_seulement,
        jamais_observes=jamais_observes,
        filtres_actifs=bool(analyse_selectionnee or statut_selectionne or actifs_seulement or jamais_observes),
        suggestions_a_examiner=suggestions_a_examiner,
        espace_csrf=_jeton_formulaire_portail(),
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
                titre=suggestion.titre,
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
    return redirect(url_for("espace_personnel.laboratoire") + "#mes-mecanismes")


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
        titre = request.form.get("titre", "").strip()
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


@espace_personnel_bp.route("/journal", methods=["GET", "POST"])
def journal():
    from utils.journal_contact import DOMAINES, contact_du_jour

    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    jeton = session.get("espace_profil_csrf")
    if not jeton:
        jeton = secrets.token_urlsafe(32)
        session["espace_profil_csrf"] = jeton
    date_prefill = request.form.get("date_observation") if request.method == "POST" else request.args.get("date")
    if not date_prefill:
        date_prefill = date.today().isoformat()
    try:
        date_observation = date.fromisoformat(date_prefill)
        if not 1900 <= date_observation.year <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        abort(400)

    source = request.form if request.method == "POST" else request.args
    contact_source = None
    if source.get("contact_planete"):
        try:
            if profil_astral is None or not profil_astral.theme_natal:
                raise ValueError
            contact_source = contact_du_jour(
                json.loads(profil_astral.theme_natal), date_prefill,
                profil_astral.fuseau_cycles or profil_astral.fuseau_horaire,
                source.get("contact_planete"), source.get("contact_point"),
                source.get("contact_aspect"),
            )
        except (TypeError, ValueError, KeyError):
            abort(400, description="Ce contact n’est pas actif pour ton thème à cette date.")
    cycle_source = None
    cycle_brut = source.get("cycle_lunaire_id") if request.method == "POST" else source.get("cycle_id")
    if cycle_brut:
        try:
            cycle_id = int(cycle_brut)
        except (TypeError, ValueError):
            abort(400)
        if profil_astral:
            cycle_source = CycleLunaire.query.filter_by(id=cycle_id, profil_id=profil_astral.id).first_or_404()
    enjeu_source = None
    enjeu_brut = source.get("enjeu_periode_id") if request.method == "POST" else source.get("enjeu_id")
    if enjeu_brut:
        try:
            enjeu_id = int(enjeu_brut)
        except (TypeError, ValueError):
            abort(400)
        enjeu_source = (
            EnjeuPeriode.query
            .join(AnalysePersonnelle, AnalysePersonnelle.id == EnjeuPeriode.analyse_id)
            .filter(EnjeuPeriode.id == enjeu_id, AnalysePersonnelle.utilisateur_id == utilisateur.id)
            .first_or_404()
        )
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
            abort(400)
        energie_texte = request.form.get("niveau_energie", "").strip()
        try:
            energie = int(energie_texte) if energie_texte else None
            if energie is not None and not 1 <= energie <= 10:
                raise ValueError
        except (TypeError, ValueError):
            flash("Vérifie le niveau d’énergie indiqué.", "error")
        else:
            champs = ("situation", "emotions", "reaction_automatique", "choix_conscient", "notes_libres")
            valeurs = {champ: request.form.get(champ, "").strip() or None for champ in champs}
            if any(valeur and len(valeur) > 10000 for valeur in valeurs.values()):
                flash("Un texte dépasse 10 000 caractères.", "error")
            else:
                photo = None
                if profil_astral and profil_astral.theme_natal:
                    try:
                        photo = _photo_transits_journal(
                            json.loads(profil_astral.theme_natal), date_observation,
                        )
                    except Exception:
                        current_app.logger.exception("Photographie des transits indisponible pour le journal")
                if contact_source:
                    photo = photo or {}
                    photo["contact_journal"] = {
                        **contact_source,
                        "domaine": request.form.get("domaine") if request.form.get("domaine") in DOMAINES else None,
                        "rien_particulier": request.form.get("rien_particulier") == "oui",
                    }
                entree = EntreeJournal(
                    utilisateur_id=utilisateur.id,
                    cycle_lunaire_id=cycle_source.id if cycle_source else None,
                    enjeu_periode_id=enjeu_source.id if enjeu_source else None,
                    date_observation=datetime.combine(date_observation, time.min),
                    niveau_energie=energie,
                    transits_actifs=json.dumps(photo, ensure_ascii=False, default=str) if photo else None,
                    **valeurs,
                )
                try:
                    db.session.add(entree)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Observation du journal impossible à enregistrer")
                    flash("Ton observation n’a pas pu être enregistrée.", "error")
                else:
                    return redirect(url_for("espace_personnel.fiche", entree_id=entree.id))
    entrees = (
        EntreeJournal.query.filter_by(utilisateur_id=utilisateur.id)
        .order_by(EntreeJournal.date_observation.desc(), EntreeJournal.id.desc()).all()
    )
    return render_template(
        "espace_personnel/journal.html", entrees=entrees,
        date_du_jour=date_prefill,
        contact_source=contact_source,
        domaines_contact=DOMAINES,
        cycle_source=cycle_source,
        enjeu_source=enjeu_source,
        interpretation_cycle=(
            json.loads(cycle_source.interpretation)
            if cycle_source and cycle_source.interpretation else None
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
        {"date": entree.date_observation.date().isoformat(),
         "texte": entree.situation or entree.notes_libres or entree.emotions or "Observation enregistrée",
         "url": url_for("espace_personnel.fiche", entree_id=entree.id)}
        for entree in entrees if debut.date() <= entree.date_observation.date() < fin.date()
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
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    debut_filtre = request.args.get("debut", type=int)
    fin_filtre = request.args.get("fin", type=int)
    if (debut_filtre is None) != (fin_filtre is None) or (
        debut_filtre is not None and not (1900 <= debut_filtre <= fin_filtre <= 2100)
    ):
        abort(400)
    cycles = []
    if profil_astral:
        enregistres = CycleSolaire.query.filter_by(profil_id=profil_astral.id).order_by(CycleSolaire.debut_cycle_utc.desc()).all()
        for cycle in enregistres:
            if debut_filtre is not None and not debut_filtre <= cycle.annee <= fin_filtre:
                continue
            try:
                theme = json.loads(cycle.theme_technique)
                retour_local = datetime.fromisoformat(theme["retour_local"])
                donnees = theme.get("donnees") or {}
                themes = donnees.get("themes_prioritaires") or []
                activations = []
                for groupe in theme.get("activations_datees") or []:
                    contacts = groupe.get("contacts") or []
                    climat = contacts[0] if contacts else {}
                    cible = {"Rahu": "Nœud Nord", "Ketu": "Nœud Sud"}.get(climat.get("cible"), climat.get("cible", ""))
                    activations.append({
                        "debut": datetime.fromisoformat(groupe["du"]).strftime("%d.%m.%Y"),
                        "fin": datetime.fromisoformat(groupe["au"]).strftime("%d.%m.%Y"),
                        "mois": groupe["du"][:7],
                        "climat": f"{climat.get('transit', '')} {climat.get('aspect', '')} {cible}".strip(),
                    })
            except (KeyError, TypeError, ValueError):
                retour_local, donnees, themes, activations = None, {}, [], []
            cycles.append({
                "themes": themes[:4], "activations": activations, "cycle": cycle,
                "retour_local": retour_local, "ascendant": donnees.get("ascendant_rs"),
                "nombre_rl": CycleLunaire.query.filter_by(cycle_solaire_id=cycle.id).count(),
            })
    return render_template(
        "espace_personnel/revolutions_solaires.html", profil=profil_astral,
        cycles=cycles, debut_filtre=debut_filtre, fin_filtre=fin_filtre,
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
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).order_by(AnalysePersonnelle.date_creation.desc()).all()
    droits_achetes = DroitAnalyseAchetee.query.filter_by(utilisateur_id=utilisateur.id).all()
    types_termines = {analyse.type_analyse for analyse in analyses if analyse.statut == "terminee"}
    analyses_a_explorer = [item for item in CATALOGUE_ANALYSES if item["type"] not in types_termines]
    droits_par_type = {droit.type_analyse: droit for droit in droits_achetes if droit.statut != "terminee"}
    ids_analyses = [analyse.id for analyse in analyses]
    nombres_mecanismes = {}
    nombres_suggestions = {}
    if ids_analyses:
        for mecanisme in MecanismeExploration.query.filter(MecanismeExploration.analyse_id.in_(ids_analyses)).all():
            nombres_mecanismes[mecanisme.analyse_id] = nombres_mecanismes.get(mecanisme.analyse_id, 0) + 1
        for suggestion in SuggestionMecanisme.query.filter(
            SuggestionMecanisme.analyse_id.in_(ids_analyses),
            SuggestionMecanisme.statut == "proposee",
        ).all():
            nombres_suggestions[suggestion.analyse_id] = nombres_suggestions.get(suggestion.analyse_id, 0) + 1
    if not session.get("espace_profil_csrf"):
        session["espace_profil_csrf"] = secrets.token_urlsafe(32)
    return render_template(
        "espace_personnel/mes_analyses.html", utilisateur=utilisateur,
        analyses=analyses, peut_importer=import_profil_autorise(utilisateur) and not analyses,
        analyses_a_explorer=analyses_a_explorer,
        droits_par_type=droits_par_type,
        nombres_mecanismes=nombres_mecanismes,
        nombres_suggestions=nombres_suggestions,
    )


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
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    entree = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur.id).first_or_404()
    photo = None
    if entree.transits_actifs:
        try:
            photo = json.loads(entree.transits_actifs)
        except (TypeError, ValueError):
            pass
    liaisons = ObservationMecanisme.query.filter_by(entree_journal_id=entree.id).all()
    analyses = AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur.id).all()
    analyse_ids = [analyse.id for analyse in analyses]
    mecanismes = (
        MecanismeExploration.query.filter(MecanismeExploration.analyse_id.in_(analyse_ids)).all()
        if analyse_ids else []
    )
    mecanismes_par_id = {mecanisme.id: mecanisme for mecanisme in mecanismes}
    deja_relies = {liaison.mecanisme_id for liaison in liaisons}
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    cycle_source = (
        CycleLunaire.query.filter_by(id=entree.cycle_lunaire_id, profil_id=profil_astral.id).first()
        if entree.cycle_lunaire_id and profil_astral else None
    )
    if not session.get("espace_profil_csrf"):
        session["espace_profil_csrf"] = secrets.token_urlsafe(32)
    return render_template(
        "espace_personnel/fiche.html", entree=entree,
        photo_transits=photo, transits_visibles=_transits_visibles_journal(photo),
        liaisons_labo=[{"observation": liaison, "mecanisme": mecanismes_par_id.get(liaison.mecanisme_id)} for liaison in liaisons],
        mecanismes_disponibles=[m for m in mecanismes if m.id not in deja_relies],
        cycle_source=cycle_source, espace_csrf=_jeton_formulaire_portail(),
    )


@espace_personnel_bp.route("/journal/<int:entree_id>/relier-mecanisme", methods=["POST"])
def relier_entree_mecanisme(entree_id):
    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    entree = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur.id).first_or_404()
    if not _verifier_formulaire_portail():
        abort(400)
    try:
        mecanisme_id = int(request.form.get("mecanisme_id", ""))
    except (TypeError, ValueError):
        abort(400)
    mecanisme = _mecanisme_du_compte(mecanisme_id, utilisateur.id)
    if ObservationMecanisme.query.filter_by(entree_journal_id=entree.id, mecanisme_id=mecanisme.id).first():
        flash("Cette observation est déjà reliée à ce mécanisme.", "error")
    else:
        liaison = ObservationMecanisme(
            mecanisme_id=mecanisme.id, entree_journal_id=entree.id,
            date_observation=entree.date_observation,
            situation=entree.situation or entree.emotions or entree.notes_libres or "Observation du journal",
            reaction_automatique=entree.reaction_automatique,
            indice_pour=request.form.get("indice_pour", "").strip() or None,
            element_contraire=request.form.get("element_contraire", "").strip() or None,
            reaction_testee=request.form.get("reaction_testee", "").strip() or None,
            resultat_obtenu=request.form.get("resultat_obtenu", "").strip() or None,
            notes_libres=entree.notes_libres,
        )
        db.session.add(liaison)
        db.session.commit()
        flash("Observation reliée au mécanisme.", "success")
    return redirect(url_for("espace_personnel.fiche", entree_id=entree.id) + "#liaisons-labo")


@espace_personnel_bp.route("/journal/<int:entree_id>/modifier", methods=["GET", "POST"])
def modifier(entree_id):
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    entree = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur.id).first_or_404()
    jeton = session.get("espace_profil_csrf")
    if not jeton:
        jeton = secrets.token_urlsafe(32)
        session["espace_profil_csrf"] = jeton
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("profil_csrf", ""), jeton):
            abort(400)
        try:
            jour = date.fromisoformat(request.form.get("date_observation", ""))
            energie_texte = request.form.get("niveau_energie", "").strip()
            energie = int(energie_texte) if energie_texte else None
            if not 1900 <= jour.year <= 2100 or (energie is not None and not 1 <= energie <= 10):
                raise ValueError
        except (TypeError, ValueError):
            flash("Vérifie la date et le niveau d’énergie.", "error")
        else:
            champs = ("situation", "emotions", "reaction_automatique", "choix_conscient", "notes_libres")
            valeurs = {champ: request.form.get(champ, "").strip() or None for champ in champs}
            if any(valeur and len(valeur) > 10000 for valeur in valeurs.values()):
                flash("Un texte dépasse 10 000 caractères.", "error")
            else:
                entree.date_observation = datetime.combine(jour, time.min)
                entree.niveau_energie = energie
                for champ, valeur in valeurs.items():
                    setattr(entree, champ, valeur)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Observation du journal impossible à modifier")
                    flash("La modification n’a pas pu être enregistrée.", "error")
                else:
                    return redirect(url_for("espace_personnel.fiche", entree_id=entree.id))
    return render_template("espace_personnel/modifier.html", entree=entree)


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
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    droits = acces_abonnement(
        AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    )
    emails = (
        EmailCycleAbonnement.query.filter_by(profil_id=profil_astral.id)
        .order_by(EmailCycleAbonnement.date_creation.desc()).all()
        if profil_astral else []
    )
    if not session.get("espace_profil_csrf"):
        session["espace_profil_csrf"] = secrets.token_urlsafe(32)
    _jeton_formulaire_portail()
    return render_template(
        "espace_personnel/emails_cycle.html", utilisateur=utilisateur,
        profil=profil_astral, droits=droits, emails=emails,
        peut_importer=bool(profil_astral and import_profil_autorise(utilisateur)),
    )


@espace_personnel_bp.route("/emails-cycle/preparer", methods=["POST"])
def preparer_email_cycle():
    """Prépare le contrat factuel du prochain mail sans appel à Claude."""
    from utils.brouillon_email_cycle import preparer_brouillon_boussole

    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    if not _verifier_formulaire_portail():
        abort(400)
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil is None:
        abort(404)
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not droits["cycle_lunaire"]:
        abort(403)
    try:
        email, _ = preparer_brouillon_boussole(profil)
        db.session.commit()
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("espace_personnel.emails_cycle"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Préparation du mail de cycle impossible")
        flash("Le prochain mail n’a pas pu être préparé.", "error")
        return redirect(url_for("espace_personnel.emails_cycle"))
    flash("Le contrat factuel du prochain mail est prêt. Aucun appel à Claude n’a été fait.", "success")
    return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))


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
    from utils.rendu_brouillon_cycle import rendu_brouillon_cycle

    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    profil_astral = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil_astral is None:
        abort(404)
    email = EmailCycleAbonnement.query.filter_by(id=email_id, profil_id=profil_astral.id).first_or_404()
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not session.get("espace_profil_csrf"):
        session["espace_profil_csrf"] = secrets.token_urlsafe(32)
    _jeton_formulaire_portail()
    try:
        preparation = json.loads(email.declencheur_factuel or "{}")
    except (TypeError, ValueError):
        preparation = {}
    from utils.brouillon_email_cycle import generation_autorisee
    peut_generer = (
        email.statut == "prepare" and not email.contenu_texte
        and bool(preparation.get("prompt"))
        and generation_autorisee(droits, preparation)
    )
    return render_template(
        "espace_personnel/fiche_email_cycle.html", utilisateur=utilisateur,
        email=email, droits=droits, peut_generer=peut_generer,
        contenu_apercu=rendu_brouillon_cycle(email.contenu_texte),
    )


@espace_personnel_bp.route("/emails-cycle/<int:email_id>/generer", methods=["POST"])
def generer_brouillon_email_cycle(email_id):
    """Un clic explicite, un seul appel Claude, brouillon enregistré sans envoi."""
    from utils.brouillon_email_cycle import generation_autorisee
    from utils.email_cycle_abonnement import convertir_email_texte_en_html, generer_texte_email_cycle

    utilisateur = _compte_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion"))
    if not _verifier_formulaire_portail():
        abort(400)
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil is None:
        abort(404)
    email = EmailCycleAbonnement.query.filter_by(id=email_id, profil_id=profil.id).first_or_404()
    droits = acces_abonnement(AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first())
    if not droits["cycle_lunaire"]:
        abort(403)
    try:
        preparation = json.loads(email.declencheur_factuel or "{}")
    except (TypeError, ValueError):
        preparation = {}
    prompt = preparation.get("prompt")
    if not generation_autorisee(droits, preparation) or not isinstance(prompt, str) or not prompt.strip():
        abort(403)
    if email.statut != "prepare" or email.contenu_texte:
        flash("Ce mail a déjà été généré ou tenté. Aucun nouvel appel à Claude n’a été lancé.", "error")
        return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))

    reclamation = db.session.execute(
        update(EmailCycleAbonnement)
        .where(EmailCycleAbonnement.id == email.id, EmailCycleAbonnement.statut == "prepare")
        .values(statut="generation_en_cours")
    )
    if reclamation.rowcount != 1:
        db.session.rollback()
        flash("Une génération est déjà en cours pour ce mail.", "error")
        return redirect(url_for("espace_personnel.fiche_email_cycle", email_id=email.id))
    db.session.commit()
    try:
        texte = generer_texte_email_cycle(prompt)
        objet = next((
            correspondance.group(1).strip()[:250]
            for ligne in texte.splitlines()
            if (correspondance := re.match(r"^OBJET\s*:\s*(.+)$", ligne.strip(), re.IGNORECASE))
        ), "")
        if not objet:
            raise ValueError("Le brouillon n’a pas d’objet valide.")
        email.objet = objet
        email.contenu_texte = texte
        email.contenu_html = convertir_email_texte_en_html(texte)
        email.statut = "brouillon"
        email.date_generation = datetime.now(timezone.utc)
        db.session.commit()
        flash("Le brouillon est prêt à être relu. Aucun mail n’a été envoyé.", "success")
    except Exception:
        db.session.rollback()
        email = EmailCycleAbonnement.query.filter_by(id=email_id, profil_id=profil.id).first()
        email.statut = "generation_echec"
        db.session.commit()
        current_app.logger.exception("Génération du mail de cycle impossible")
        flash("Le brouillon n’a pas abouti. Aucun nouvel appel à Claude ne sera lancé automatiquement.", "error")
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


@espace_personnel_bp.route("/deconnexion", methods=["POST"])
def deconnexion():
    if not _verifier_formulaire_portail():
        abort(400)
    session.clear()
    return redirect(url_for("espace_personnel.connexion"))
