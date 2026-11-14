"""Communauté privée de la bêta : publications, commentaires et salon sans IA."""
from datetime import datetime, timezone
import hashlib
import re
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.espace_personnel import (AbonnementEspace, CommentaireCommunaute, EntreeJournal,
    InscriptionMailsBeta, MessageSalonCommunaute, ProfilCommunaute, PublicationCommunaute,
    SignalementCommunaute, UtilisateurEspace)
from utils.auth_espace import administratrice_connectee, autoriser_tentative, utilisateur_connecte, verifier_csrf_espace
from utils.avatars_espace import AVATARS_ESPACE

communaute_bp = Blueprint("communaute", __name__, url_prefix="/mon-espace/communaute")
GROUPE = "beta_dec2026"
MOTIFS_SIGNALEMENT = {
    "respect": "Propos blessants, insultes ou harcèlement",
    "interpretation": "Conseil ou interprétation personnelle non demandée",
    "vie_privee": "Informations privées partagées sans accord",
    "inquietude": "Ce contenu m’inquiète",
    "autre": "Autre raison",
}


def _json():
    return request.accept_mimetypes.best == "application/json"


def _utc(date):
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)


def _membre(utilisateur):
    if administratrice_connectee():
        return True
    inscription = db.session.get(InscriptionMailsBeta, utilisateur.id)
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).first()
    return bool(inscription and inscription.actif and datetime.now(timezone.utc) < _utc(inscription.fin)
        and abonnement and abonnement.formule == "beta_accompagnement" and abonnement.statut in {"actif", "test"}
        and (abonnement.date_fin is None or datetime.now(timezone.utc) < _utc(abonnement.date_fin)))


@communaute_bp.before_request
def proteger():
    utilisateur = utilisateur_connecte()
    if not utilisateur:
        if _json():
            return jsonify(error="Reconnecte-toi pour retrouver le salon."), 401
        return redirect(url_for("espace_personnel.connexion", suivant="/mon-espace/communaute"))
    noms = set(inspect(db.session.get_bind(mapper=ProfilCommunaute)).get_table_names())
    stockage = {"profils_communaute", "publications_communaute", "commentaires_communaute", "messages_salon_communaute", "inscriptions_mails_beta"} <= noms
    if not stockage:
        if _json():
            return jsonify(error="La communauté est en cours de préparation."), 503
        return render_template("communaute/acces.html", stockage=False), 503
    if request.endpoint != "communaute.mon_profil" and not _membre(utilisateur):
        if _json():
            return jsonify(error="La communauté est réservée aux membres du groupe bêta."), 403
        return render_template("communaute/acces.html", stockage=True), 403
    if request.method == "POST":
        verifier_csrf_espace()


@communaute_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    return reponse


def _profil():
    return db.session.get(ProfilCommunaute, utilisateur_connecte().id)


@communaute_bp.app_template_global()
def profil_communaute_du_membre():
    utilisateur = utilisateur_connecte()
    if not utilisateur or not inspect(db.session.get_bind(mapper=ProfilCommunaute)).has_table("profils_communaute"):
        return None
    return db.session.get(ProfilCommunaute, utilisateur.id)


def _url_pseudo(suivant=None, entree=None):
    suite = {"communaute_suivant": suivant} if suivant in {"publier", "salon"} else {}
    if suivant == "publier" and entree:
        suite["communaute_entree"] = entree
    return url_for("espace_personnel.profil", _anchor="pseudo-communaute", **suite)


def _identites(ids):
    if not ids:
        return {}
    lignes = db.session.execute(select(ProfilCommunaute, UtilisateurEspace.est_administratrice, UtilisateurEspace.avatar_personnage).join(
        UtilisateurEspace, UtilisateurEspace.id == ProfilCommunaute.utilisateur_id
    ).where(ProfilCommunaute.utilisateur_id.in_(ids))).all()
    return {p.utilisateur_id: {"pseudo": p.pseudo, "avatar": avatar if avatar in AVATARS_ESPACE else None,
        "creatrice": bool(admin), "couleur": p.utilisateur_id % 6} for p, admin, avatar in lignes}


def _rendre(nom, **contexte):
    return render_template("communaute/"+nom, mon_profil=_profil(), moi=utilisateur_connecte().id,
        moderatrice=administratrice_connectee(), nonce=uuid4().hex,
        signalements_prets=_signalements_prets(), **contexte)


def _signalements_prets():
    return inspect(db.session.get_bind(mapper=SignalementCommunaute)).has_table("signalements_communaute")


def _publication(id):
    return PublicationCommunaute.query.filter_by(id=id, groupe=GROUPE, retiree=False).first_or_404()


def _texte(champ, minimum, maximum):
    texte = request.form.get(champ, "").strip()
    if not minimum <= len(texte) <= maximum or "\x00" in texte:
        raise ValueError(f"Ce texte doit contenir entre {minimum} et {maximum} caractères.")
    return texte


def _nonce():
    valeur = request.form.get("nonce", "")
    if not re.fullmatch(r"[a-f0-9]{32}", valeur):
        raise ValueError("Recharge la page avant de publier.")
    return valeur


def _limiter(action, maximum):
    if not autoriser_tentative("communaute_"+action, str(utilisateur_connecte().id), maximum=maximum, secondes=60):
        if action == "signalement":
            raise ValueError("Tu as enregistré plusieurs signalements à la suite. Attends une minute avant de continuer.")
        raise ValueError("Tu as publié plusieurs messages à la suite. Attends une minute avant de continuer.")


def _sauver(objet):
    db.session.add(objet)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        deja = type(objet).query.filter_by(nonce=objet.nonce, utilisateur_id=utilisateur_connecte().id).first()
        if deja is None:
            raise ValueError("Le message n’a pas pu être enregistré. Recharge la page.") from None
        return deja
    return objet


@communaute_bp.route("")
@communaute_bp.route("/")
def index():
    page = max(1, min(10000, request.args.get("page", 1, type=int)))
    publications = PublicationCommunaute.query.filter_by(groupe=GROUPE, retiree=False).order_by(
        PublicationCommunaute.date_creation.desc(), PublicationCommunaute.id.desc()).offset((page-1)*12).limit(13).all()
    suite = len(publications) > 12
    publications = publications[:12]
    ids = [p.id for p in publications]
    nombres = dict(db.session.execute(select(CommentaireCommunaute.publication_id, func.count()).where(
        CommentaireCommunaute.publication_id.in_(ids), CommentaireCommunaute.retire.is_(False)
    ).group_by(CommentaireCommunaute.publication_id)).all()) if ids else {}
    return _rendre("index.html", publications=publications, page=page, suite=suite, nombres=nombres,
        identites=_identites({p.utilisateur_id for p in publications}))


@communaute_bp.route("/mon-profil", methods=["GET", "POST"])
def mon_profil():
    suivant = request.values.get("suivant")
    entree = request.values.get("entree", type=int)
    if request.method == "POST":
        try:
            pseudo = _texte("pseudo", 2, 32)
            if "@" in pseudo or any(ord(c) < 32 for c in pseudo):
                raise ValueError("Choisis un prénom ou un pseudo, sans adresse e-mail.")
            profil = _profil() or ProfilCommunaute(utilisateur_id=utilisateur_connecte().id)
            profil.pseudo, profil.pseudo_cle = pseudo, pseudo.casefold()
            db.session.add(profil)
            db.session.commit()
            if suivant in {"publier", "salon"} and _membre(utilisateur_connecte()):
                flash("Ton pseudo est enregistré.", "success")
                destination = "communaute." + suivant
                return redirect(url_for(destination, **({"entree": entree} if suivant == "publier" and entree else {})))
            flash("Ton pseudo est enregistré.", "pseudo_success")
            return redirect(_url_pseudo())
        except IntegrityError:
            db.session.rollback()
            flash("Ce pseudo est déjà utilisé. Choisis-en un autre.", "pseudo_error")
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "pseudo_error")
    return redirect(_url_pseudo(suivant, entree))


@communaute_bp.route("/publier", methods=["GET", "POST"])
def publier():
    if not _profil():
        return redirect(url_for("communaute.mon_profil", suivant="publier", entree=request.values.get("entree", type=int)))
    note = None
    entree_id = request.values.get("entree", type=int)
    if entree_id:
        note = EntreeJournal.query.filter_by(id=entree_id, utilisateur_id=utilisateur_connecte().id).first_or_404()
    if request.method == "POST":
        try:
            titre, texte, nonce = _texte("titre", 2, 140), _texte("texte", 5, 10000), _nonce()
            deja = PublicationCommunaute.query.filter_by(nonce=nonce, utilisateur_id=utilisateur_connecte().id).first()
            if deja:
                return redirect(url_for("communaute.fiche", publication_id=deja.id))
            if request.form.get("confirmer_partage") != "oui":
                raise ValueError("Confirme que tu souhaites partager ce texte avec le groupe.")
            _limiter("publication", 5)
            publication = _sauver(PublicationCommunaute(groupe=GROUPE, utilisateur_id=utilisateur_connecte().id,
                titre=titre, texte=texte, nonce=nonce, entree_journal_id=note.id if note else None))
            return redirect(url_for("communaute.fiche", publication_id=publication.id))
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "error")
    return _rendre("publier.html", note=note, publication=None)


@communaute_bp.route("/prises-de-conscience/<int:publication_id>/modifier", methods=["GET", "POST"])
def modifier(publication_id):
    publication = _publication(publication_id)
    if publication.utilisateur_id != utilisateur_connecte().id:
        abort(404)
    if request.method == "POST":
        try:
            titre, texte = _texte("titre", 2, 140), _texte("texte", 5, 10000)
            if request.form.get("confirmer_partage") != "oui":
                raise ValueError("Confirme le texte que tu souhaites partager.")
            publication.titre, publication.texte = titre, texte
            db.session.commit()
            return redirect(url_for("communaute.fiche", publication_id=publication.id))
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "error")
    return _rendre("publier.html", publication=publication, note=None)


@communaute_bp.route("/prises-de-conscience/<int:publication_id>", methods=["GET", "POST"])
def fiche(publication_id):
    publication = _publication(publication_id)
    if request.method == "POST":
        if not _profil():
            return redirect(url_for("communaute.mon_profil"))
        try:
            texte, nonce = _texte("texte", 1, 2000), _nonce()
            _limiter("commentaire", 10)
            _sauver(CommentaireCommunaute(publication_id=publication.id, utilisateur_id=utilisateur_connecte().id, texte=texte, nonce=nonce))
            return redirect(url_for("communaute.fiche", publication_id=publication.id)+"#discussion")
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "error")
    commentaires = CommentaireCommunaute.query.filter_by(publication_id=publication.id, retire=False).order_by(CommentaireCommunaute.date_creation).all()
    return _rendre("fiche.html", publication=publication, commentaires=commentaires,
        identites=_identites({publication.utilisateur_id}|{c.utilisateur_id for c in commentaires}))


@communaute_bp.route("/retirer/<nature>/<int:id>", methods=["POST"])
def retirer(nature, id):
    modele = {"publication": PublicationCommunaute, "commentaire": CommentaireCommunaute, "message": MessageSalonCommunaute}.get(nature)
    if modele is None:
        abort(404)
    objet = db.session.get(modele, id)
    if objet is None or (nature != "commentaire" and objet.groupe != GROUPE):
        abort(404)
    if nature == "commentaire":
        _publication(objet.publication_id)
    if objet.utilisateur_id != utilisateur_connecte().id and not administratrice_connectee():
        abort(404)
    if nature == "publication":
        objet.retiree = True
    else:
        objet.retire = True
    db.session.commit()
    if _json():
        return jsonify(ok=True)
    destination = url_for("communaute.salon") if nature == "message" else url_for("communaute.fiche", publication_id=objet.publication_id) if nature == "commentaire" else url_for("communaute.index")
    return redirect(destination)


def _messages():
    return list(reversed(MessageSalonCommunaute.query.filter_by(groupe=GROUPE, retire=False).order_by(
        MessageSalonCommunaute.id.desc()).limit(80).all()))


def _message_json(message, identites, moi_id, moderatrice, signalements_prets=False):
    auteur = identites.get(message.utilisateur_id, {"pseudo": "Membre", "couleur": 0})
    avatar = AVATARS_ESPACE.get(auteur.get("avatar"))
    moi = moi_id == message.utilisateur_id
    return {"id": message.id, "texte": message.texte, "pseudo": auteur["pseudo"],
        "avatar": url_for("static", filename=avatar["fichier"]) if avatar else None,
        "couleur": auteur["couleur"], "creatrice": auteur.get("creatrice", False), "moi": moi,
        "date": _utc(message.date_creation).isoformat(),
        "retirer": url_for("communaute.retirer", nature="message", id=message.id) if moi or moderatrice else None,
        "signaler": url_for("communaute.signaler", nature="message", id=message.id) if signalements_prets else None}


@communaute_bp.route("/salon")
def salon():
    return _rendre("salon.html")


@communaute_bp.route("/salon/messages", methods=["GET", "POST"])
def messages():
    if request.method == "POST":
        if not _profil():
            return jsonify(error="Choisis ton pseudo avant de participer."), 409
        try:
            texte, nonce = _texte("texte", 1, 1000), _nonce()
            deja = MessageSalonCommunaute.query.filter_by(nonce=nonce, utilisateur_id=utilisateur_connecte().id).first()
            if deja is None:
                _limiter("salon", 30)
                _sauver(MessageSalonCommunaute(groupe=GROUPE, utilisateur_id=utilisateur_connecte().id, texte=texte, nonce=nonce))
        except ValueError as erreur:
            db.session.rollback()
            return jsonify(error=str(erreur)), 400
    derniers = _messages()
    identites = _identites({m.utilisateur_id for m in derniers})
    if request.method == "POST" and not _json():
        return redirect(url_for("communaute.salon"))
    moi_id, moderatrice = utilisateur_connecte().id, administratrice_connectee()
    signalements_prets = _signalements_prets()
    return jsonify(messages=[_message_json(m, identites, moi_id, moderatrice, signalements_prets) for m in derniers], nonce=uuid4().hex)


def _contenu_du_groupe(nature, id, *, inclure_retires=False):
    """Contrôle le groupe côté serveur, y compris celui du parent d’un commentaire."""
    modele = {"publication": PublicationCommunaute, "commentaire": CommentaireCommunaute,
              "message": MessageSalonCommunaute}.get(nature)
    if modele is None:
        abort(404)
    objet = db.session.get(modele, id)
    if objet is None:
        abort(404)
    if nature == "commentaire":
        parent = db.session.get(PublicationCommunaute, objet.publication_id)
        if parent is None or parent.groupe != GROUPE or (parent.retiree and not inclure_retires):
            abort(404)
    elif objet.groupe != GROUPE:
        abort(404)
    retire = objet.retiree if nature == "publication" else objet.retire
    if retire and not inclure_retires:
        abort(404)
    return objet


def _source_contenu(nature, objet):
    if nature == "message":
        return url_for("communaute.salon", _anchor=f"message-{objet.id}")
    return url_for("communaute.fiche", publication_id=objet.id if nature == "publication" else objet.publication_id,
                   _anchor=None if nature == "publication" else f"commentaire-{objet.id}")


@communaute_bp.route("/signaler/<nature>/<int:id>", methods=["GET", "POST"])
def signaler(nature, id):
    if not _signalements_prets():
        abort(503, "Les signalements sont en cours de préparation.")
    objet = _contenu_du_groupe(nature, id)
    titre = objet.titre if nature == "publication" else "Commentaire" if nature == "commentaire" else "Message du tchat"
    texte_copie, auteur_id = objet.texte, objet.utilisateur_id
    source = _source_contenu(nature, objet)
    if request.method == "POST":
        try:
            motif = request.form.get("motif", "")
            precision = request.form.get("precision", "").strip()
            if motif not in MOTIFS_SIGNALEMENT:
                raise ValueError("Choisis la raison de ton signalement.")
            if len(precision) > 2000 or "\x00" in precision:
                raise ValueError("La précision doit faire au maximum 2 000 caractères.")
            empreinte = hashlib.sha256((titre + "\n" + texte_copie).encode()).hexdigest()
            utilisateur_id = utilisateur_connecte().id
            deja = SignalementCommunaute.query.filter_by(signale_par=utilisateur_id,
                nature=nature, contenu_id=id, empreinte_contenu=empreinte).first()
            if deja is None:
                _limiter("signalement", 5)
                db.session.add(SignalementCommunaute(groupe=GROUPE, signale_par=utilisateur_id,
                    auteur_id=auteur_id, nature=nature, contenu_id=id,
                    empreinte_contenu=empreinte, titre_copie=titre, texte_copie=texte_copie,
                    motif=motif, precision=precision or None))
                db.session.commit()
            flash("Ton signalement est enregistré pour Cécile. Il reste privé.", "success")
            return redirect(source)
        except IntegrityError:
            db.session.rollback()
            if SignalementCommunaute.query.filter_by(signale_par=utilisateur_id, nature=nature,
                    contenu_id=id, empreinte_contenu=empreinte).first() is None:
                raise
            flash("Ton signalement est déjà enregistré pour Cécile.", "success")
            return redirect(source)
        except ValueError as erreur:
            db.session.rollback()
            flash(str(erreur), "error")
    return _rendre("signaler.html", nature=nature, contenu=objet, titre=titre, source=source,
        motifs=MOTIFS_SIGNALEMENT)


@communaute_bp.route("/signalements")
def signalements():
    if not administratrice_connectee():
        abort(404)
    archives = request.args.get("traites") == "1"
    page = max(1, min(10000, request.args.get("page", 1, type=int)))
    lignes = (SignalementCommunaute.query.filter_by(groupe=GROUPE, traite=archives)
        .order_by(SignalementCommunaute.date_creation.desc(), SignalementCommunaute.id.desc())
        .offset((page-1)*30).limit(31).all() if _signalements_prets() else [])
    return _rendre("signalements.html", signalements=lignes[:30], archives=archives,
        suite=len(lignes) > 30, page=page, motifs=MOTIFS_SIGNALEMENT,
        identites=_identites({s.signale_par for s in lignes[:30]} | {s.auteur_id for s in lignes[:30]}),
        utc=_utc, paris=ZoneInfo("Europe/Paris"))


@communaute_bp.route("/signalements/<int:id>/traiter", methods=["POST"])
def traiter_signalement(id):
    if not administratrice_connectee():
        abort(404)
    if not _signalements_prets():
        abort(503)
    signalement = SignalementCommunaute.query.filter_by(id=id, groupe=GROUPE).first_or_404()
    action = request.form.get("action")
    if action not in {"traiter", "retirer"}:
        abort(400)
    if action == "retirer":
        objet = _contenu_du_groupe(signalement.nature, signalement.contenu_id, inclure_retires=True)
        if signalement.nature == "publication":
            objet.retiree = True
        else:
            objet.retire = True
        # Plusieurs personnes peuvent avoir signalé le même contenu.
        SignalementCommunaute.query.filter_by(groupe=GROUPE, nature=signalement.nature,
            contenu_id=signalement.contenu_id, traite=False).update({
                "traite": True, "traite_le": datetime.now(timezone.utc), "traite_par": utilisateur_connecte().id},
                synchronize_session="fetch")
    else:
        signalement.traite, signalement.traite_le, signalement.traite_par = True, datetime.now(timezone.utc), utilisateur_connecte().id
    db.session.commit()
    flash("Contenu retiré du groupe et signalement traité." if action == "retirer" else "Signalement marqué comme traité.", "success")
    return redirect(url_for("communaute.signalements"))
