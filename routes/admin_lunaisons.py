from utils.auth_espace import administratrice_connectee
"""Édition locale des lectures collectives, sans génération ni envoi."""
from datetime import datetime
import os
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.espace_personnel import AnalyseLunaison, utcnow
from utils.analyses_lunaisons import (
    FUSEAU_EDITION, lunaisons_du_mois, retrouver_lunaison, verifier_table_analyses,
)
from utils.auth_espace import jeton_csrf_espace, verifier_csrf_espace


admin_lunaisons_bp = Blueprint("admin_lunaisons", __name__, url_prefix="/admin/lunaisons")


def acces_administration_locale():
    return administratrice_connectee()


@admin_lunaisons_bp.app_context_processor
def contexte_admin_lunaisons():
    return {"administration_lunaisons_locale": acces_administration_locale()}


@admin_lunaisons_bp.before_request
def proteger_administration():
    if not acces_administration_locale():
        abort(404)
    if request.method == "POST":
        verifier_csrf_espace()


@admin_lunaisons_bp.after_request
def proteger_reponse(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Content-Security-Policy"] = "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    return reponse


@admin_lunaisons_bp.route("")
@admin_lunaisons_bp.route("/")
def index():
    mois = request.args.get("mois", datetime.now(FUSEAU_EDITION).strftime("%Y-%m"))
    try:
        calendrier = lunaisons_du_mois(mois)
    except ValueError as erreur:
        abort(400, str(erreur))
    erreur_schema = None
    analyses = {}
    try:
        verifier_table_analyses()
        dates = [l["date_utc"] for l in calendrier]
        analyses = {(a.type_lunaison, a.date_utc): a for a in AnalyseLunaison.query.filter(AnalyseLunaison.date_utc.in_(dates)).all()}
    except ValueError as erreur:
        erreur_schema = str(erreur)
    for fiche in calendrier:
        fiche["analyse"] = analyses.get((fiche["type"], fiche["date_utc"]))
    return render_template("admin/lunaisons.html", calendrier=calendrier, mois=mois,
                           erreur_schema=erreur_schema), (503 if erreur_schema else 200)


@admin_lunaisons_bp.route("/<nature>/<date_utc>", methods=["GET", "POST"])
def editer(nature, date_utc):
    try:
        fiche = retrouver_lunaison(nature, date_utc)
    except ValueError as erreur:
        abort(404, str(erreur))
    try:
        verifier_table_analyses()
    except ValueError as erreur:
        return render_template("admin/lunaisons.html", calendrier=[],
                               mois=fiche["date_locale"].strftime("%Y-%m"), erreur_schema=str(erreur)), 503
    analyse = AnalyseLunaison.query.filter_by(type_lunaison=nature, date_utc=date_utc).first()
    formulaire = {"titre": analyse.titre if analyse else "", "texte": analyse.texte if analyse else ""}
    erreur = None
    code = 200
    if request.method == "POST":
        formulaire = {cle: request.form.get(cle, "").strip() for cle in ("titre", "texte")}
        action = request.form.get("action")
        try:
            try:
                revision = int(request.form.get("revision", ""))
            except ValueError as exc:
                raise ValueError("La version du formulaire est absente. Copie ton texte, puis recharge la fiche.") from exc
            if revision != (analyse.revision if analyse else 0):
                raise RuntimeError("La fiche a changé dans un autre onglet. Ton texte est conservé ci-dessous : copie-le avant de recharger la dernière version.")
            if action not in {"enregistrer", "valider", "retirer"}:
                raise ValueError("Choisis une action disponible.")
            if action == "retirer" and (analyse is None or analyse.validee_le is None):
                raise ValueError("Cette fiche n'a pas de version validée à retirer.")
            if len(formulaire["titre"]) > 200:
                raise ValueError("Le titre doit tenir en 200 caractères.")
            if action == "valider" and not formulaire["texte"]:
                raise ValueError("Ajoute ton analyse avant de la valider pour les mails.")
            maintenant = utcnow()
            valeurs = {**formulaire, "revision": revision + 1, "date_modification": maintenant}
            if action == "valider":
                valeurs.update(titre_valide=formulaire["titre"], texte_valide=formulaire["texte"],
                               validee_le=maintenant, revision_validee=(analyse.revision_validee if analyse else 0) + 1)
            elif action == "retirer":
                valeurs.update(titre_valide=None, texte_valide=None, validee_le=None)
            if analyse is None:
                db.session.add(AnalyseLunaison(type_lunaison=nature, date_utc=date_utc,
                                               instant_utc=fiche["instant"], **valeurs))
            else:
                nombre = AnalyseLunaison.query.filter_by(id=analyse.id, revision=revision).update(valeurs, synchronize_session=False)
                if nombre != 1:
                    raise RuntimeError("La fiche a changé pendant l'enregistrement. Ton texte est conservé ci-dessous : copie-le avant de recharger.")
            db.session.commit()
        except (ValueError, RuntimeError, IntegrityError) as exc:
            db.session.rollback()
            erreur = str(exc) if not isinstance(exc, IntegrityError) else "Une autre fiche vient d'être enregistrée pour cette lunaison. Copie ton texte avant de recharger."
            code = 409 if isinstance(exc, (RuntimeError, IntegrityError)) else 400
        else:
            messages = {
                "enregistrer": "Brouillon enregistré. La version validée reste celle utilisée dans les mails, s'il y en a une.",
                "valider": "Analyse validée pour les prochains mails concernés. Aucun mail généré ou envoyé.",
                "retirer": "Validation retirée. Ton texte reste enregistré en brouillon. Aucun mail existant modifié.",
            }
            flash(messages[action], "success")
            return redirect(url_for("admin_lunaisons.editer", nature=nature, date_utc=date_utc))
    return render_template("admin/analyse_lunaison.html", fiche=fiche, analyse=analyse,
                           formulaire=formulaire, erreur=erreur, conflit=(code == 409),
                           csrf_lunaisons=jeton_csrf_espace()), code
