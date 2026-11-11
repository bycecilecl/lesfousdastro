"""Mots de passe de l'espace membre. Aucun appel IA ni génération de rapport."""
from __future__ import annotations

from datetime import timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import os
import secrets
from urllib.parse import urlsplit

from flask import abort, current_app, request, session, url_for
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as insert_postgresql
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.espace_personnel import (
    LienConnexionEspace, LienMotDePasseEspace, LimiteAccesEspace,
    UtilisateurEspace, utcnow,
)
from utils.acces_espace import normaliser_email


MIN_MOT_DE_PASSE = 8
MAX_MOT_DE_PASSE = 128
DUREE_RECUPERATION_MINUTES = 30


def _utc(instant):
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def labo_local():
    """Un lien de prévisualisation ne doit jamais être affiché sur un hôte public."""
    return (
        (current_app.debug or current_app.testing)
        and request.remote_addr in {"127.0.0.1", "::1"}
        and urlsplit(request.host_url).hostname in {"localhost", "127.0.0.1", "::1"}
    )


def jeton_csrf_espace():
    if "csrf_espace" not in session:
        session["csrf_espace"] = secrets.token_urlsafe(32)
    return session["csrf_espace"]


def verifier_csrf_espace():
    attendu = session.get("csrf_espace", "")
    recu = request.form.get("csrf_token", "")
    if not attendu or not hmac.compare_digest(attendu.encode("utf-8"), recu.encode("utf-8")):
        abort(400, "Ta session a expiré. Recharge la page avant de réessayer.")


def _cle_limite(action, valeur):
    secret = current_app.secret_key
    if not secret:
        raise RuntimeError("SECRET_KEY doit être configurée pour l'espace membre.")
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hmac.new(secret, f"{action}:{valeur}".encode("utf-8"), hashlib.sha256).hexdigest()


def autoriser_tentative(action, valeur, *, maximum, secondes=900):
    """Incrément atomique SQLite/PostgreSQL, partagé entre les workers."""
    maintenant = utcnow()
    borne = maintenant - timedelta(seconds=secondes)
    cle = _cle_limite(action, valeur)
    table = LimiteAccesEspace.__table__
    nouvelle_fenetre = table.c.debut_fenetre <= borne
    dialecte = db.session.get_bind(mapper=LimiteAccesEspace).dialect.name
    inserer = insert_postgresql if dialecte == "postgresql" else insert_sqlite
    requete = inserer(table).values(cle=cle, debut_fenetre=maintenant, nombre=1)
    requete = requete.on_conflict_do_update(
        index_elements=[table.c.cle],
        set_={
            "debut_fenetre": case((nouvelle_fenetre, maintenant), else_=table.c.debut_fenetre),
            "nombre": case((nouvelle_fenetre, 1), else_=table.c.nombre + 1),
        },
    )
    # Exécution par le modèle afin de cibler le bind « journal ».
    db.session.execute(requete, bind_arguments={"mapper": LimiteAccesEspace})
    compteur = db.session.get(LimiteAccesEspace, cle, populate_existing=True)
    permis = compteur.nombre <= maximum
    LimiteAccesEspace.query.filter(
        LimiteAccesEspace.debut_fenetre < maintenant - timedelta(days=2),
    ).delete(synchronize_session=False)
    db.session.commit()
    return permis


def limiter_formulaire(action, email=""):
    # remote_addr vient du serveur. Aucun X-Forwarded-For arbitraire n'est accepté.
    adresse = request.remote_addr or "inconnue"
    maximum_ip = 60 if action == "connexion" else 8
    duree = 900 if action == "connexion" else 3600
    if not autoriser_tentative(action + ":ip", adresse, maximum=maximum_ip, secondes=duree):
        return False
    if email:
        return autoriser_tentative(
            action + ":email", normaliser_email(email),
            maximum=10 if action == "connexion" else 4, secondes=duree,
        )
    return True


@lru_cache(maxsize=1)
def _hash_factice():
    return generate_password_hash("Verification-factice-sans-compte-associe", method="scrypt")


def verifier_mot_de_passe(utilisateur, mot_de_passe):
    if not isinstance(mot_de_passe, str) or len(mot_de_passe) > MAX_MOT_DE_PASSE:
        return False
    empreinte = utilisateur.mot_de_passe_hash if utilisateur and utilisateur.mot_de_passe_hash else _hash_factice()
    correct = check_password_hash(empreinte, mot_de_passe)
    return bool(utilisateur and utilisateur.actif == 1 and utilisateur.mot_de_passe_hash and correct)


def valider_nouveau_mot_de_passe(mot_de_passe, confirmation):
    if len(mot_de_passe) < MIN_MOT_DE_PASSE or len(mot_de_passe) > MAX_MOT_DE_PASSE:
        raise ValueError(f"Choisis un mot de passe de {MIN_MOT_DE_PASSE} à {MAX_MOT_DE_PASSE} caractères. Une phrase fonctionne très bien.")
    if mot_de_passe != confirmation:
        raise ValueError("Les deux mots de passe ne correspondent pas.")


def utilisateur_connecte():
    identifiant = session.get("utilisateur_espace_id")
    if identifiant is None:
        return None
    utilisateur = db.session.get(UtilisateurEspace, identifiant)
    if not utilisateur or utilisateur.actif != 1 or session.get("version_auth_espace") != utilisateur.version_auth:
        session.pop("utilisateur_espace_id", None)
        session.pop("version_auth_espace", None)
        return None
    return utilisateur


def ouvrir_session_espace(utilisateur, *, permanent=True):
    session.clear()
    session["utilisateur_espace_id"] = utilisateur.id
    session["version_auth_espace"] = utilisateur.version_auth
    session["espace_connecte_le"] = utcnow().isoformat()
    session.permanent = permanent


def _url_publique(endpoint, **valeurs):
    chemin = url_for(endpoint, **valeurs)
    if labo_local():
        return url_for(endpoint, _external=True, **valeurs)
    origine = (os.getenv("ESPACE_URL_PUBLIQUE") or os.getenv("ESPACE_PUBLIC_ORIGIN") or "https://lesfousdastro.fr").strip().rstrip("/")
    url = urlsplit(origine)
    if url.scheme != "https" or not url.netloc or url.username or url.password or url.path or url.query or url.fragment:
        raise RuntimeError("ESPACE_URL_PUBLIQUE doit être une origine HTTPS, sans chemin.")
    return origine + chemin


def creer_lien_mot_de_passe(utilisateur):
    jeton = secrets.token_urlsafe(32)
    maintenant = utcnow()
    LienMotDePasseEspace.query.filter_by(utilisateur_id=utilisateur.id, utilise_le=None).update(
        {"utilise_le": maintenant}, synchronize_session=False,
    )
    db.session.add(LienMotDePasseEspace(
        utilisateur_id=utilisateur.id,
        empreinte_jeton=hashlib.sha256(jeton.encode("utf-8")).hexdigest(),
        version_auth=utilisateur.version_auth,
        expire_le=maintenant + timedelta(minutes=DUREE_RECUPERATION_MINUTES),
    ))
    lien = _url_publique("espace_personnel.definir_mot_de_passe", jeton=jeton)
    db.session.commit()
    return lien


def lire_lien_mot_de_passe(jeton, *, ancien_lien=False):
    if not jeton or len(jeton) > 128:
        return None, None
    modele = LienConnexionEspace if ancien_lien else LienMotDePasseEspace
    lien = modele.query.filter_by(empreinte_jeton=hashlib.sha256(jeton.encode("utf-8")).hexdigest()).first()
    if not lien or lien.utilise_le is not None or _utc(lien.expire_le) <= utcnow():
        return None, None
    utilisateur = db.session.get(UtilisateurEspace, lien.utilisateur_id)
    if not utilisateur or utilisateur.actif != 1:
        return None, None
    if not ancien_lien and lien.version_auth != utilisateur.version_auth:
        return None, None
    return utilisateur, lien


def enregistrer_mot_de_passe(utilisateur, mot_de_passe, *, lien=None):
    """Consomme le jeton et change le mot de passe dans une seule transaction."""
    maintenant = utcnow()
    empreinte = generate_password_hash(mot_de_passe, method="scrypt")
    if lien is not None:
        modele = type(lien)
        filtre = modele.query.filter(
            modele.id == lien.id, modele.utilise_le.is_(None), modele.expire_le > maintenant,
        )
        if modele is LienMotDePasseEspace:
            filtre = filtre.filter(modele.version_auth == utilisateur.version_auth)
        if filtre.update({"utilise_le": maintenant}, synchronize_session=False) != 1:
            db.session.rollback()
            raise ValueError("Ce lien a expiré ou a déjà été utilisé. Demande-en un nouveau.")
    # La version empêche deux liens concurrents d'écraser le même mot de passe.
    modifie = UtilisateurEspace.query.filter_by(
        id=utilisateur.id, actif=1, version_auth=utilisateur.version_auth,
    ).update({
        "mot_de_passe_hash": empreinte,
        "mot_de_passe_modifie_le": maintenant,
        "version_auth": utilisateur.version_auth + 1,
    }, synchronize_session=False)
    if modifie != 1:
        db.session.rollback()
        raise ValueError("Le compte a été modifié entre-temps. Recommence depuis la connexion.")
    for modele in (LienMotDePasseEspace, LienConnexionEspace):
        modele.query.filter_by(utilisateur_id=utilisateur.id, utilise_le=None).update(
            {"utilise_le": maintenant}, synchronize_session=False,
        )
    db.session.commit()
    db.session.refresh(utilisateur)
