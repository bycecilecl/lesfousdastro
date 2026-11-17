"""Écran d’essai réservé à l’administratrice, en local et en production."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import inspect

from extensions import db
from models.espace_personnel import AnalyseLunaison, MailEvenementAbonne
from utils.auth_espace import administratrice_connectee, utilisateur_connecte, verifier_csrf_espace
from utils.essais_mails_evenements import PREFIXE, analyse_validee, budget
from utils.mails_evenements import utc

admin_essais_mails_bp = Blueprint("admin_essais_mails", __name__, url_prefix="/admin/essais-mails")


@admin_essais_mails_bp.app_template_filter("date_essai_mail")
def date_essai_mail(instant):
    if isinstance(instant, str):
        return datetime.fromisoformat(instant).strftime("%d.%m.%Y à %H:%M")
    return utc(instant).astimezone(ZoneInfo("Europe/Paris")).strftime("%d.%m.%Y à %H:%M")


@admin_essais_mails_bp.app_template_filter("json_essai_mail")
def json_essai_mail(valeur):
    return json.dumps(valeur, ensure_ascii=False, indent=2, default=str)


@admin_essais_mails_bp.before_request
def proteger():
    if not administratrice_connectee():
        abort(404)
    if request.method == "POST":
        verifier_csrf_espace()


@admin_essais_mails_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["Referrer-Policy"] = "same-origin"
    return reponse


def _stockage_pret():
    return all(inspect(db.session.get_bind(mapper=modele)).has_table(modele.__tablename__)
               for modele in (MailEvenementAbonne, AnalyseLunaison))


def _essai(id):
    if not _stockage_pret():
        abort(404)
    return MailEvenementAbonne.query.filter(MailEvenementAbonne.id == id,
        MailEvenementAbonne.utilisateur_id == utilisateur_connecte().id,
        MailEvenementAbonne.cle_evenement.startswith(PREFIXE)).first_or_404()


@admin_essais_mails_bp.route("")
@admin_essais_mails_bp.route("/")
def index():
    pret = _stockage_pret()
    essais = (MailEvenementAbonne.query.filter(MailEvenementAbonne.utilisateur_id == utilisateur_connecte().id,
        MailEvenementAbonne.cle_evenement.startswith(PREFIXE)).order_by(
        MailEvenementAbonne.date_creation.desc()).limit(20).all() if pret else [])
    mail = _essai(request.args["essai"]) if request.args.get("essai") else essais[0] if essais else None
    from utils.confidentialite_journal_mails import lire_choix_journal_mails
    return render_template("admin/essais_mails.html", pret=pret, essais=essais, mail=mail,
        analyse=analyse_validee() if pret else None, choix_journal=lire_choix_journal_mails(utilisateur_connecte().id),
        dossier=json.loads(mail.dossier_json or "{}") if mail else {},
        parametres=json.loads(mail.parametres_json or "{}") if mail else {},
        source=json.loads(mail.source_lunaison_json or "null") if mail else None,
        usage=json.loads(mail.usage_json or "{}") if mail else {}, controle=budget(mail.prompt) if mail else None)


def _action(nom, id=None):
    if not _stockage_pret():
        abort(503, "Le stockage des mails événements n’est pas disponible.")
    mail = _essai(id) if id else None
    try:
        from utils import essais_mails_evenements as moteur
        if nom == "preparer":
            mail = moteur.preparer(utilisateur_connecte(), nature=request.form.get("nature", "pleine_lune"))
            flash("Aperçu préparé avec les données actuelles. Aucun appel IA ni envoi.", "success")
        elif nom == "generer":
            moteur.generer(mail, utilisateur_connecte())
            flash("Le brouillon est généré et conservé. Aucun mail envoyé.", "success")
        else:
            if request.form.get("validation_relecture") != "oui":
                raise ValueError("Coche la validation de ta relecture avant l’envoi à ton adresse.")
            moteur.envoyer_a_soi(mail, utilisateur_connecte())
            flash("Le mail a été remis au transport pour ton adresse uniquement. Tu peux vérifier ta boîte et Mes mails.", "success")
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), "error")
    except Exception as erreur:
        db.session.rollback()
        current_app.logger.exception("[ESSAI MAIL] Action interrompue : %s", nom)
        flash("L’action a été interrompue. Les résultats enregistrés sont conservés ; aucun nouvel appel ni renvoi automatique.", "error")
    return redirect(url_for("admin_essais_mails.index", **({"essai": mail.id} if mail else {})))


@admin_essais_mails_bp.route("/preparer", methods=["POST"])
def preparer():
    return _action("preparer")


@admin_essais_mails_bp.route("/<id>/generer", methods=["POST"])
def generer(id):
    return _action("generer", id)


@admin_essais_mails_bp.route("/<id>/envoyer", methods=["POST"])
def envoyer(id):
    return _action("envoyer", id)


@admin_essais_mails_bp.route("/<id>/lecture")
def lecture(id):
    mail = _essai(id)
    reponse = Response(mail.contenu_html or "", mimetype="text/html")
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'"
    return reponse
