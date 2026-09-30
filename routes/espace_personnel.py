"""Première tranche de l'espace personnel : compte et connexion par e-mail."""

import os
import requests

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from extensions import db
from models.espace_personnel import UtilisateurEspace
from utils.acces_espace import (
    consommer_lien_connexion,
    creer_lien_connexion,
    email_invite,
    lien_recent,
    trouver_ou_creer_utilisateur,
)
from utils.email_sender import envoyer_email_avec_analyse


espace_personnel_bp = Blueprint("espace_personnel", __name__, url_prefix="/mon-espace")


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


@espace_personnel_bp.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.pop("utilisateur_espace_id", None)
    return redirect(url_for("espace_personnel.connexion"))
