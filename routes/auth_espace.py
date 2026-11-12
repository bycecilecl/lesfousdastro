"""Parcours de connexion membre par e-mail et mot de passe."""
import logging
from threading import Thread

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from extensions import db
from models.espace_personnel import UtilisateurEspace
from utils.acces_espace import email_invite, normaliser_email, trouver_ou_creer_utilisateur
from utils.auth_espace import (
    DUREE_RECUPERATION_MINUTES, MIN_MOT_DE_PASSE, MAX_MOT_DE_PASSE,
    creer_lien_mot_de_passe, enregistrer_mot_de_passe, labo_local,
    limiter_formulaire, lire_lien_mot_de_passe, ouvrir_session_espace,
    utilisateur_connecte, valider_nouveau_mot_de_passe, verifier_csrf_espace,
    verifier_mot_de_passe,
)
from utils.email_espace import envoyer_email_avec_analyse


ROUTES_PUBLIQUES_AUTH = {
    "espace_personnel.connexion", "espace_personnel.inscription",
    "espace_personnel.mot_de_passe_oublie", "espace_personnel.definir_mot_de_passe",
    "espace_personnel.valider_connexion",
}
ROUTES_AUTH = ROUTES_PUBLIQUES_AUTH | {
    "espace_personnel.modifier_mot_de_passe", "espace_personnel.deconnexion",
}


def _envoyer_recuperation(email, lien):
    """L'envoi ne change pas le temps de réponse selon l'existence du compte."""
    texte = (
        "Bonjour,\n\nTu as demandé à définir ou réinitialiser ton mot de passe "
        "pour ton espace Les Fous d’Astro.\n\n"
        f"{lien}\n\nCe lien est valable {DUREE_RECUPERATION_MINUTES} minutes "
        "et ne fonctionne qu’une fois.\n\n"
        "Après avoir choisi ton mot de passe, tu pourras te connecter directement "
        "avec ton e-mail et ce mot de passe.\n\n"
        "Si tu n’as pas fait cette demande, ignore cet e-mail : ton mot de passe reste inchangé."
    )
    if not envoyer_email_avec_analyse(
        destinataire=email, sujet="Définir ton mot de passe — Les Fous d’Astro",
        contenu_txt=texte, smtp_timeout=15,
    ):
        logging.getLogger(__name__).error("Envoi du message de récupération impossible ; vérifier le service e-mail.")


def url_suivante_espace(valeur):
    valeur = (valeur or "").strip()
    chemin = valeur.split("?", 1)[0]
    valide = (chemin == "/mon-espace" or chemin.startswith("/mon-espace/")) and "\\" not in valeur
    if any(ord(c) < 32 for c in valeur):
        valide = False
    if any(chemin.startswith("/mon-espace/" + p) for p in (
        "connexion", "inscription", "mot-de-passe-oublie", "definir-mot-de-passe", "deconnexion",
    )):
        valide = False
    return valeur if valide else url_for("espace_personnel.accueil")


def connexion():
    suivant = url_suivante_espace(request.values.get("suivant"))
    email, statut = "", 200
    if request.method == "GET" and utilisateur_connecte():
        return redirect(suivant)
    if request.method == "POST":
        verifier_csrf_espace()
        email = normaliser_email(request.form.get("email", ""))
        verifier_public = current_app.config.get("ESPACE_VERIFIER_FORMULAIRE_PUBLIC")
        if verifier_public and not verifier_public():
            flash("La vérification de sécurité a échoué. Réessaie.", "error")
            return render_template("espace_personnel/connexion.html", suivant=suivant, email=email), 400
        if not limiter_formulaire("connexion", email):
            flash("Trop de tentatives. Attends quelques minutes avant de réessayer.", "error")
            statut = 429
        else:
            utilisateur = UtilisateurEspace.query.filter(func.lower(UtilisateurEspace.email) == email).first()
            if verifier_mot_de_passe(utilisateur, request.form.get("mot_de_passe", "")):
                apres_connexion = current_app.config.get("ESPACE_APRES_CONNEXION")
                if apres_connexion:
                    try:
                        apres_connexion(utilisateur)
                    except Exception:
                        db.session.rollback()
                        current_app.logger.error("Actualisation des droits membre impossible.")
                ouvrir_session_espace(utilisateur, permanent=request.form.get("rester_connecte") == "1")
                flash(f"Te voilà connectée, {utilisateur.prenom}.", "success")
                return redirect(suivant)
            flash("Adresse e-mail ou mot de passe incorrect. Pour une première connexion, définis ton mot de passe ci-dessous.", "error")
            statut = 401
    return render_template("espace_personnel/connexion.html", suivant=suivant, email=email), statut


def _demander_mot_de_passe(*, inscription=False):
    """Seul le POST explicite peut déclencher l'envoi d'un e-mail."""
    lien_test, email, prenom, statut = None, "", "", 200
    if request.method == "POST":
        verifier_csrf_espace()
        email = normaliser_email(request.form.get("email", ""))
        prenom = request.form.get("prenom", "").strip()[:100]
        verifier_public = current_app.config.get("ESPACE_VERIFIER_FORMULAIRE_PUBLIC")
        if verifier_public and not verifier_public():
            flash("La vérification de sécurité a échoué. Réessaie.", "error")
            return render_template(
                "espace_personnel/demander_mot_de_passe.html", inscription=inscription,
                lien_test=None, email=email, prenom=prenom,
            ), 400
        if len(email) > 255 or not _email_valide(email):
            flash("Vérifie ton adresse e-mail.", "error")
            statut = 400
        elif not limiter_formulaire("recuperation", email):
            flash("Trop de demandes. Réessaie un peu plus tard.", "error")
            statut = 429
        else:
            utilisateur = UtilisateurEspace.query.filter(func.lower(UtilisateurEspace.email) == email).first()
            autoriser_inscription = current_app.config.get("ESPACE_AUTORISER_INSCRIPTION")
            creation_autorisee = autoriser_inscription(email) if autoriser_inscription else True
            if utilisateur is None and inscription and creation_autorisee:
                try:
                    utilisateur = trouver_ou_creer_utilisateur(email, prenom)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    utilisateur = UtilisateurEspace.query.filter(func.lower(UtilisateurEspace.email) == email).first()
                    if utilisateur is None:
                        current_app.logger.error("Création de compte membre impossible ; aucun mot de passe ni jeton journalisé.")
            if utilisateur is not None and utilisateur.actif == 1:
                try:
                    lien = creer_lien_mot_de_passe(utilisateur)
                    if labo_local():
                        lien_test = lien
                    else:
                        Thread(target=_envoyer_recuperation, args=(utilisateur.email, lien), daemon=True).start()
                except Exception:
                    db.session.rollback()
                    current_app.logger.error("Préparation de récupération impossible ; vérifier la configuration de l'espace membre.")
            if not lien_test:
                flash("Si cette adresse correspond à un compte actif, un e-mail te permettra de définir ton mot de passe. Consulte aussi tes indésirables.", "success")
                return redirect(url_for("espace_personnel.connexion"))
    return render_template(
        "espace_personnel/demander_mot_de_passe.html", inscription=inscription,
        lien_test=lien_test, email=email, prenom=prenom,
    ), statut


def _email_valide(email):
    import re
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


def inscription():
    if request.method == 'POST' and not email_invite(normaliser_email(request.form.get('email', ''))):
        abort(403, 'Les inscriptions ne sont pas ouvertes pour cette adresse.')
    return _demander_mot_de_passe(inscription=True)


def mot_de_passe_oublie():
    return _demander_mot_de_passe()


def _formulaire_definition(jeton, *, ancien_lien=False):
    utilisateur, lien = lire_lien_mot_de_passe(jeton, ancien_lien=ancien_lien)
    if utilisateur is None:
        flash("Ce lien a expiré ou a déjà été utilisé. Demande un nouveau lien pour définir ton mot de passe.", "error")
        return redirect(url_for("espace_personnel.mot_de_passe_oublie"))
    statut = 200
    if request.method == "POST":
        verifier_csrf_espace()
        if not limiter_formulaire("definition"):
            flash("Trop de tentatives. Réessaie un peu plus tard.", "error")
            statut = 429
        else:
            mot_de_passe = request.form.get("mot_de_passe", "")
            try:
                valider_nouveau_mot_de_passe(mot_de_passe, request.form.get("confirmation", ""))
                enregistrer_mot_de_passe(utilisateur, mot_de_passe, lien=lien)
            except ValueError as erreur:
                flash(str(erreur), "error")
                statut = 400
            else:
                session.clear()
                flash("Ton mot de passe est enregistré. Tu peux maintenant te connecter.", "success")
                return redirect(url_for("espace_personnel.connexion"))
    return render_template(
        "espace_personnel/definir_mot_de_passe.html", modification=False,
        minimum=MIN_MOT_DE_PASSE, maximum=MAX_MOT_DE_PASSE, email=utilisateur.email,
    ), statut


def definir_mot_de_passe(jeton):
    return _formulaire_definition(jeton)


def valider_connexion(jeton):
    # Les liens déjà reçus restent utilisables ; un GET ne les consomme jamais.
    return _formulaire_definition(jeton, ancien_lien=True)


def modifier_mot_de_passe():
    utilisateur = utilisateur_connecte()
    if utilisateur is None:
        abort(403)
    statut = 200
    if request.method == "POST":
        verifier_csrf_espace()
        if not limiter_formulaire("modification", utilisateur.email or str(utilisateur.id)):
            flash("Trop de tentatives. Réessaie un peu plus tard.", "error")
            statut = 429
        elif not verifier_mot_de_passe(utilisateur, request.form.get("mot_de_passe_actuel", "")):
            flash("Le mot de passe actuel est incorrect.", "error")
            statut = 400
        else:
            mot_de_passe = request.form.get("mot_de_passe", "")
            try:
                valider_nouveau_mot_de_passe(mot_de_passe, request.form.get("confirmation", ""))
                enregistrer_mot_de_passe(utilisateur, mot_de_passe)
            except ValueError as erreur:
                flash(str(erreur), "error")
                statut = 400
            else:
                ouvrir_session_espace(utilisateur)
                flash("Ton mot de passe a été modifié. Les autres sessions ont été déconnectées.", "success")
                return redirect(url_for("espace_personnel.accueil"))
    return render_template(
        "espace_personnel/definir_mot_de_passe.html", modification=True,
        minimum=MIN_MOT_DE_PASSE, maximum=MAX_MOT_DE_PASSE, email=utilisateur.email,
    ), statut


def deconnexion():
    verifier_csrf_espace()
    session.clear()
    flash("Tu es déconnectée de ton espace.", "success")
    return redirect(url_for("espace_personnel.connexion"))


def enregistrer_routes_auth(bp, *, inclure_deconnexion=True):
    for chemin, vue in (
        ("/connexion", connexion), ("/inscription", inscription),
        ("/mot-de-passe-oublie", mot_de_passe_oublie),
        ("/definir-mot-de-passe/<jeton>", definir_mot_de_passe),
        ("/connexion/<jeton>", valider_connexion),
        ("/mot-de-passe", modifier_mot_de_passe),
    ):
        bp.add_url_rule(chemin, endpoint=vue.__name__, view_func=vue, methods=["GET", "POST"])
    if inclure_deconnexion:
        bp.add_url_rule("/deconnexion", endpoint="deconnexion", view_func=deconnexion, methods=["POST"])
