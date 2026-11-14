"""Archives privées des mails envoyés ; aucun moteur, paiement ou transport."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Blueprint, Response, abort, redirect, render_template, url_for
from sqlalchemy import inspect
from extensions import db
from models.espace_personnel import MailEvenementAbonne, ProfilAstral
from utils.auth_espace import utilisateur_connecte
from utils.journal_mails import notes_du_mail

archives_mails_bp = Blueprint("abonnement_client", __name__, url_prefix="/mon-espace")
NATURES = {"rl": "Révolution Lunaire", "nouvelle_lune": "Nouvelle Lune", "pleine_lune": "Pleine Lune"}

def utc(instant):
    from datetime import timezone
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)

def _stockage_pret():
    return inspect(db.session.get_bind(mapper=MailEvenementAbonne)).has_table("mails_evenements_abonnes")

@archives_mails_bp.before_request
def proteger():
    if utilisateur_connecte() is None:
        return redirect(url_for("espace_personnel.connexion", suivant="/mon-espace/mes-mails"))

@archives_mails_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    return reponse

@archives_mails_bp.route("/mes-mails")
def mes_mails():
    utilisateur = utilisateur_connecte()
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    try:
        fuseau = ZoneInfo(profil.fuseau_cycles) if profil and profil.fuseau_cycles else ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        fuseau = ZoneInfo("Europe/Paris")
    mails = MailEvenementAbonne.query.filter_by(utilisateur_id=utilisateur.id, statut="envoye").order_by(
        MailEvenementAbonne.date_envoi.desc()).all() if _stockage_pret() else []
    return render_template("espace_personnel/mes_mails.html", mails=mails, natures=NATURES, utc=utc, fuseau=fuseau)

def _mail(mail_id):
    if not _stockage_pret():
        abort(404)
    return MailEvenementAbonne.query.filter_by(id=mail_id, utilisateur_id=utilisateur_connecte().id, statut="envoye").first_or_404()

@archives_mails_bp.route("/mes-mails/<mail_id>")
def lire_mail(mail_id):
    mail = _mail(mail_id)
    return render_template("espace_personnel/lire_mail.html", mail=mail, notes_liees=notes_du_mail(mail))

@archives_mails_bp.route("/mes-mails/<mail_id>/contenu")
def contenu_mail(mail_id):
    mail = _mail(mail_id)
    reponse = Response(mail.contenu_html or "", mimetype="text/html")
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data: https://lesfousdastro.fr; frame-ancestors 'self'; form-action 'none'"
    return reponse
