"""Lectures collectives et cartes importées par Cécile, sans génération."""
from io import BytesIO
import re

from flask import Blueprint, abort, redirect, render_template, request, send_file, url_for

from extensions import db
from models.espace_personnel import AbonnementEspace, AnalyseLunaison, CarteLunaison
from utils.analyses_lunaisons import FUSEAU_EDITION, TYPES_LUNAISONS, utc, verifier_table_analyses
from utils.auth_espace import administratrice_connectee, utilisateur_connecte
from utils.cartes_lunaisons import cartes_de_la_fiche, stockage_pret

lunaisons_bp = Blueprint("lunaisons", __name__)


@lunaisons_bp.before_request
def proteger():
    if request.endpoint == "lunaisons.fichier":
        return None  # Image collective publiée : URL opaque pour les lecteurs d’e-mails.
    utilisateur = utilisateur_connecte()
    if utilisateur is None:
        return redirect(url_for("espace_personnel.connexion", suivant=request.path))
    if not administratrice_connectee():
        from utils.acces_abonnement import acces_abonnement
        abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
        if not acces_abonnement(abonnement)["actif"]:
            return render_template("espace_personnel/lunaisons_acces.html"), 403


@lunaisons_bp.after_request
def prive(reponse):
    if request.endpoint != "lunaisons.fichier":
        reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse


@lunaisons_bp.route("/cartes-lunaisons/<identifiant>.png")
def fichier(identifiant):
    if not re.fullmatch(r"[0-9a-f]{64}", identifiant) or not stockage_pret():
        abort(404)
    carte = db.session.get(CarteLunaison, identifiant)
    if carte is None:
        abort(404)
    if carte.publiee_le is None:
        from routes.admin_lunaisons import acces_administration_locale
        if not administratrice_connectee() and not acces_administration_locale():
            abort(404)
    reponse = send_file(BytesIO(carte.contenu), mimetype="image/png",
        download_name="carte-lunaison.png", conditional=True, etag=carte.id)
    reponse.headers["Cache-Control"] = (
        "public, max-age=31536000, immutable" if carte.publiee_le else "private, no-store")
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; frame-ancestors 'none'"
    reponse.headers["Referrer-Policy"] = "no-referrer"
    return reponse


def _donnees(analyse):
    _, carte = cartes_de_la_fiche(analyse.type_lunaison, analyse.date_utc)
    return {"analyse": analyse, "carte": carte,
            "libelle": TYPES_LUNAISONS[analyse.type_lunaison],
            "date_locale": utc(analyse.instant_utc).astimezone(FUSEAU_EDITION)}


@lunaisons_bp.route("/mon-espace/lunaisons")
def index():
    try:
        verifier_table_analyses()
    except ValueError:
        return render_template("espace_personnel/lunaisons.html", lunaisons=[], stockage=False), 503
    page = max(1, request.args.get("page", 1, type=int))
    analyses = AnalyseLunaison.query.filter(AnalyseLunaison.validee_le.isnot(None),
        AnalyseLunaison.texte_valide.isnot(None), AnalyseLunaison.texte_valide != "").order_by(
        AnalyseLunaison.instant_utc.desc()).offset((page - 1) * 12).limit(13).all()
    return render_template("espace_personnel/lunaisons.html",
                           lunaisons=[_donnees(a) for a in analyses[:12]], stockage=True,
                           page=page, suite=len(analyses) > 12)


@lunaisons_bp.route("/mon-espace/lunaisons/<nature>/<date_utc>")
def fiche(nature, date_utc):
    if nature not in TYPES_LUNAISONS or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_utc):
        abort(404)
    try:
        verifier_table_analyses()
    except ValueError:
        abort(503)
    analyse = AnalyseLunaison.query.filter_by(type_lunaison=nature, date_utc=date_utc).filter(
        AnalyseLunaison.validee_le.isnot(None), AnalyseLunaison.texte_valide.isnot(None),
        AnalyseLunaison.texte_valide != "").first_or_404()
    return render_template("espace_personnel/lunaison.html", **_donnees(analyse))
