"""Première tranche de l'espace personnel : compte et connexion par e-mail."""

import os
import requests
import json
import math
import hmac
import secrets
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import update

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from extensions import db
from models.espace_personnel import (
    AbonnementEspace, CycleLunaire, EmailCycleAbonnement,
    ProfilAstral, UtilisateurEspace,
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


def import_profil_autorise(utilisateur):
    """L'import du labo reste limité aux deux comptes de validation."""
    autorises = os.getenv(
        "ESPACE_IMPORT_EMAILS", "cecilecl@gmail.com,cecilecl.cyp@gmail.com"
    )
    return utilisateur.email.lower() in {
        email.strip().lower() for email in autorises.split(",") if email.strip()
    }


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
    session["utilisateur_espace_id"] = utilisateur.id
    session.permanent = False
    return redirect(url_for("espace_personnel.accueil"))


@espace_personnel_bp.route("/")
def accueil():
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        session.pop("utilisateur_espace_id", None)
        return redirect(url_for("espace_personnel.connexion"))
    return render_template("espace_personnel/accueil.html", utilisateur=utilisateur)


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
                erreur="Le profil n’a pas pu être enregistré. Réessaie plus tard.",
            ), 503
        flash("Ton profil astral est enregistré.", "success")
        return redirect(url_for("espace_personnel.profil"))

    return render_template(
        "espace_personnel/profil.html", profil=profil_astral,
        utilisateur=utilisateur, saisie=None,
        peut_importer=profil_astral is None and import_profil_autorise(utilisateur),
    )


@espace_personnel_bp.route("/profil/importer", methods=["POST"])
def importer_profil_labo():
    """Importe le seul profil appartenant au compte connecté, une seule fois."""
    utilisateur_id = session.get("utilisateur_espace_id")
    utilisateur = db.session.get(UtilisateurEspace, utilisateur_id) if utilisateur_id else None
    if utilisateur is None or utilisateur.actif != 1:
        return redirect(url_for("espace_personnel.connexion"))
    if not import_profil_autorise(utilisateur):
        abort(404)
    existant = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if existant is not None:
        flash("Ce compte possède déjà un profil. Utilise le formulaire pour le mettre à jour.", "error")
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
            "espace_personnel/profil.html", profil=None,
            utilisateur=utilisateur, saisie=None, peut_importer=True,
            erreur=str(exc) if isinstance(exc, ValueError) else "Le fichier de profil est invalide.",
        ), 400

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
    if abonnement_import is not None:
        if AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first() is not None:
            db.session.rollback()
            return render_template(
                "espace_personnel/profil.html", profil=None,
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
            "espace_personnel/profil.html", profil=None,
            utilisateur=utilisateur, saisie=None, peut_importer=True,
            erreur="L’import n’a pas pu être enregistré. Réessaie plus tard.",
        ), 503
    flash("Ton profil du labo a bien été importé.", "success")
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
    return render_template(
        "espace_personnel/emails_cycle.html", utilisateur=utilisateur,
        profil=profil_astral, droits=droits, emails=emails,
        peut_importer=bool(profil_astral and import_profil_autorise(utilisateur)),
    )


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
    return render_template(
        "espace_personnel/fiche_email_cycle.html", utilisateur=utilisateur,
        email=email, droits=droits,
    )


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
    session.pop("utilisateur_espace_id", None)
    return redirect(url_for("espace_personnel.connexion"))
