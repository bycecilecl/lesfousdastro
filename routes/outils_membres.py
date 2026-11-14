"""Cartes natales privées et retours bêta. Aucun appel IA, aucun envoi de mail."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import re
import warnings
from uuid import uuid4

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from PIL import Image, UnidentifiedImageError
from PyPDF2 import PdfReader
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from extensions import db
from models.espace_personnel import (
    AbonnementEspace, CarteNataleMembre, InscriptionMailsBeta, RetourBetaMembre,
    UtilisateurEspace, utcnow,
)
from utils.auth_espace import administratrice_connectee, utilisateur_connecte, verifier_csrf_espace

outils_membres_bp = Blueprint("outils_membres", __name__)
TAILLE_MAX_CARTE = 15 * 1024 * 1024


def _table_prete(modele):
    return inspect(db.session.get_bind(mapper=modele)).has_table(modele.__tablename__)


@outils_membres_bp.app_template_global()
def carte_natale_du_membre():
    utilisateur = utilisateur_connecte()
    if utilisateur is None or not _table_prete(CarteNataleMembre):
        return None
    # Le contenu binaire est différé : il n’est chargé que pour ouvrir le fichier.
    return db.session.get(CarteNataleMembre, utilisateur.id)


@outils_membres_bp.app_template_global()
def retours_beta_accessibles():
    utilisateur = utilisateur_connecte()
    if utilisateur is None:
        return False
    if administratrice_connectee():
        return True
    if not _table_prete(InscriptionMailsBeta):
        return False
    inscription = db.session.get(InscriptionMailsBeta, utilisateur.id)
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    def utc(instant):
        return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)
    maintenant = datetime.now(timezone.utc)
    return bool(inscription and inscription.actif and maintenant < utc(inscription.fin)
        and abonnement and abonnement.formule == "beta_accompagnement"
        and abonnement.statut in {"actif", "test"}
        and (abonnement.date_fin is None or maintenant < utc(abonnement.date_fin)))


@outils_membres_bp.before_request
def proteger():
    if request.path.startswith("/admin/"):
        if not administratrice_connectee():
            abort(404)
    elif utilisateur_connecte() is None:
        return redirect(url_for("espace_personnel.connexion", suivant=request.full_path))
    if request.method == "POST":
        verifier_csrf_espace()


@outils_membres_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["Referrer-Policy"] = "same-origin"
    return reponse


def _document_valide(fichier):
    if fichier is None or not fichier.filename:
        raise ValueError("Choisis une image ou un PDF pour ce membre.")
    contenu = fichier.stream.read(TAILLE_MAX_CARTE + 1)
    if not contenu or len(contenu) > TAILLE_MAX_CARTE:
        raise ValueError("La carte doit faire au maximum 15 Mo.")
    if contenu.startswith(b"%PDF-"):
        try:
            lecteur = PdfReader(BytesIO(contenu), strict=False)
            if lecteur.is_encrypted or not 1 <= len(lecteur.pages) <= 100:
                raise ValueError()
        except Exception:
            raise ValueError("Ce PDF est illisible, protégé par mot de passe ou contient trop de pages.") from None
        mime, extension = "application/pdf", ".pdf"
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(contenu)) as image:
                    if image.width * image.height > 40_000_000:
                        raise ValueError()
                    formats = {"PNG": ("image/png", ".png"), "JPEG": ("image/jpeg", ".jpg"), "WEBP": ("image/webp", ".webp")}
                    mime, extension = formats[image.format]
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, KeyError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise ValueError("Choisis une image PNG, JPG ou WebP lisible, ou un PDF.") from None
    nom = secure_filename(Path(fichier.filename).stem)[:150] or "carte-natale"
    return contenu, mime, nom + extension


@outils_membres_bp.route("/admin/cartes-natales", methods=["GET", "POST"])
def cartes_natales():
    pret = _table_prete(CarteNataleMembre)
    selection = (request.form if request.method == "POST" else request.args).get("membre", type=int)
    if request.method == "POST":
        if not pret:
            abort(503, "Le stockage des cartes natales n’est pas encore préparé.")
        membre = db.session.get(UtilisateurEspace, selection) if selection else None
        if membre is None or membre.actif != 1:
            abort(404)
        try:
            contenu, mime, nom = _document_valide(request.files.get("carte"))
            carte = db.session.get(CarteNataleMembre, membre.id)
            if carte is None:
                carte = CarteNataleMembre(utilisateur_id=membre.id)
            carte.nom_fichier, carte.type_mime, carte.taille_octets = nom, mime, len(contenu)
            carte.contenu, carte.ajoutee_par, carte.date_modification = contenu, utilisateur_connecte().id, utcnow()
            db.session.add(carte)
            db.session.commit()
            flash(f"La carte natale de {membre.prenom} est enregistrée dans son profil.", "success")
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "error")
        except Exception:
            db.session.rollback()
            flash("La carte n’a pas pu être enregistrée. La carte précédente est conservée.", "error")
        return redirect(url_for("outils_membres.cartes_natales", membre=selection))
    membres = UtilisateurEspace.query.filter_by(actif=1).order_by(UtilisateurEspace.prenom, UtilisateurEspace.id).all()
    cartes = CarteNataleMembre.query.all() if pret else []
    return render_template("admin/cartes_natales.html", pret=pret, membres=membres,
        cartes={c.utilisateur_id: c for c in cartes}, selection=selection)


def _servir_carte(utilisateur_id):
    if not _table_prete(CarteNataleMembre):
        abort(404)
    carte = db.session.get(CarteNataleMembre, utilisateur_id)
    if carte is None:
        abort(404)
    reponse = send_file(BytesIO(carte.contenu), mimetype=carte.type_mime,
        download_name=carte.nom_fichier, as_attachment=request.args.get("telecharger") == "1",
        conditional=False, etag=False, max_age=0)
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    return reponse


@outils_membres_bp.route("/mon-espace/carte-natale/fichier")
def fichier_carte():
    return _servir_carte(utilisateur_connecte().id)


@outils_membres_bp.route("/admin/cartes-natales/<int:utilisateur_id>/fichier")
def fichier_carte_admin(utilisateur_id):
    return _servir_carte(utilisateur_id)


@outils_membres_bp.route("/mon-espace/retours-beta", methods=["GET", "POST"])
def retours_beta():
    if not retours_beta_accessibles():
        abort(404)
    pret = _table_prete(RetourBetaMembre)
    erreur = None
    if request.method == "POST":
        if not pret:
            abort(503, "Le stockage des retours bêta n’est pas encore préparé.")
        try:
            objet = request.form.get("objet", "").strip()
            texte = request.form.get("texte", "").strip()
            page = request.form.get("page_concernee", "").strip()
            nonce = request.form.get("nonce", "")
            if not 2 <= len(objet) <= 140:
                raise ValueError("Ajoute un objet entre 2 et 140 caractères.")
            if not 5 <= len(texte) <= 10000 or "\x00" in objet + texte + page:
                raise ValueError("Écris ta remarque entre 5 et 10 000 caractères.")
            if len(page) > 240:
                raise ValueError("Le nom de la page est trop long.")
            if not re.fullmatch(r"[a-f0-9]{32}", nonce):
                raise ValueError("Recharge la page avant d’enregistrer ton retour.")
            utilisateur_id = utilisateur_connecte().id
            deja = RetourBetaMembre.query.filter_by(nonce=nonce, utilisateur_id=utilisateur_id).first()
            if deja is None:
                db.session.add(RetourBetaMembre(utilisateur_id=utilisateur_id, objet=objet,
                    texte=texte, page_concernee=page or None, nonce=nonce))
                db.session.commit()
            flash("Merci, ton feedback est enregistré ! Je suis la seule à pouvoir le consulter.", "success")
            return redirect(url_for("outils_membres.retours_beta"))
        except IntegrityError:
            db.session.rollback()
            if RetourBetaMembre.query.filter_by(nonce=nonce, utilisateur_id=utilisateur_connecte().id).first():
                flash("Ton retour est déjà enregistré.", "success")
                return redirect(url_for("outils_membres.retours_beta"))
            erreur = "Le retour n’a pas pu être enregistré. Ton texte est conservé dans le formulaire."
        except ValueError as exc:
            db.session.rollback()
            erreur = str(exc)
        except Exception:
            db.session.rollback()
            erreur = "Le retour n’a pas pu être enregistré. Ton texte est conservé dans le formulaire."
    return render_template("espace_personnel/retours_beta.html", pret=pret, erreur=erreur,
        nonce=request.form.get("nonce") if re.fullmatch(r"[a-f0-9]{32}", request.form.get("nonce", "")) else uuid4().hex)


@outils_membres_bp.route("/admin/retours-beta")
def lire_retours_beta():
    pret = _table_prete(RetourBetaMembre)
    page = max(1, request.args.get("page", 1, type=int))
    lignes = (db.session.execute(select(RetourBetaMembre, UtilisateurEspace.prenom, UtilisateurEspace.email)
        .outerjoin(UtilisateurEspace, UtilisateurEspace.id == RetourBetaMembre.utilisateur_id)
        .order_by(RetourBetaMembre.date_creation.desc(), RetourBetaMembre.id.desc())
        .offset((page - 1) * 30).limit(31)).all() if pret else [])
    return render_template("admin/retours_beta.html", pret=pret, retours=lignes[:30], page=page, suite=len(lignes) > 30)
