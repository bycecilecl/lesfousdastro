"""Suivi administratrice des échéances. Aucune génération ou livraison depuis cet écran."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, inspect

from extensions import db
from models.espace_personnel import InscriptionMailsBeta, MailEvenementAbonne, UtilisateurEspace
from utils.auth_espace import administratrice_connectee, verifier_csrf_espace
from utils.automatisation_mails_evenements import automatique_actif
from utils.mails_evenements import DEBUT_BETA, FIN_BETA, NATURES, PARIS, utc


admin_envois_automatiques_bp = Blueprint("admin_envois_automatiques", __name__, url_prefix="/admin/envois-automatiques")
LIBELLES_ETATS = {
    "planifie": "Prévu", "attente_analyse": "Ton analyse collective est attendue",
    "generation_en_cours": "Rédaction en cours", "generation_echouee": "Rédaction interrompue",
    "pret": "Mail rédigé, en attente d’envoi", "envoi_en_cours": "Envoi en cours",
    "envoi_incertain": "Envoi à vérifier", "envoye": "Envoyé",
    "expire": "Créneau dépassé", "bloque": "Bloqué, vérification nécessaire", "suspendu": "Suspendu",
}


@admin_envois_automatiques_bp.before_request
def proteger():
    if not administratrice_connectee():
        abort(404)
    if request.method == "POST":
        verifier_csrf_espace()


@admin_envois_automatiques_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    return reponse


def tables_pretes():
    return all(inspect(db.session.get_bind(mapper=modele)).has_table(modele.__tablename__)
               for modele in (InscriptionMailsBeta, MailEvenementAbonne))


@admin_envois_automatiques_bp.route("")
@admin_envois_automatiques_bp.route("/")
def index():
    pret = tables_pretes()
    inscriptions, mails, etats = [], [], {}
    utilisateurs = {}
    if pret:
        inscriptions = InscriptionMailsBeta.query.order_by(InscriptionMailsBeta.date_creation.desc()).all()
        # Les essais manuels n'entrent pas dans la file d'envoi automatique.
        filtre = ~MailEvenementAbonne.cle_evenement.startswith("essai-")
        mails = MailEvenementAbonne.query.filter(filtre).order_by(MailEvenementAbonne.date_prevue).limit(200).all()
        etats = dict(db.session.query(MailEvenementAbonne.statut, func.count(MailEvenementAbonne.id))
                     .filter(filtre).group_by(MailEvenementAbonne.statut).all())
        ids = {i.utilisateur_id for i in inscriptions} | {m.utilisateur_id for m in mails}
        if ids:
            utilisateurs = {u.id: u for u in UtilisateurEspace.query.filter(UtilisateurEspace.id.in_(ids)).all()}
    return render_template("admin/envois_automatiques.html", pret=pret,
        inscriptions=inscriptions, mails=mails, etats=etats, utilisateurs=utilisateurs,
        autorise=automatique_actif(), debut=DEBUT_BETA.astimezone(PARIS),
        fin=(FIN_BETA - timedelta(days=1)).astimezone(PARIS), maintenant=datetime.now(timezone.utc),
        natures=NATURES, utc=utc, paris=PARIS, libelles_etats=LIBELLES_ETATS)


@admin_envois_automatiques_bp.route("/comptes/<int:utilisateur_id>/suspendre", methods=["POST"])
def suspendre(utilisateur_id):
    if not tables_pretes():
        abort(503)
    inscription = db.session.get(InscriptionMailsBeta, utilisateur_id)
    if inscription is None:
        abort(404)
    inscription.actif = False
    db.session.commit()
    flash("Les prochains envois automatiques de ce compte sont suspendus. Son accès à l’espace est conservé.", "success")
    return redirect(url_for("admin_envois_automatiques.index"))
