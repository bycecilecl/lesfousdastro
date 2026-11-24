"""Installation, souscription et lectures privées du membre connecté."""
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import inspect

from extensions import db
from models.espace_personnel import AbonnementEspace, CommandeAbonnementEspace, InscriptionMailsBeta, MailEvenementAbonne, ProfilAstral, RevolutionSolairePackBeta
from utils.auth_espace import utilisateur_connecte, verifier_csrf_espace
from utils.mails_evenements import NATURES, utc
from utils.souscription_espace import OFFRE, FORMULES_BETA, configuration_paiement, formule_commande, offre_publique
from utils.invitations_beta import adresse_invitee_beta

abonnement_client_bp = Blueprint("abonnement_client", __name__, url_prefix="/mon-espace")


@abonnement_client_bp.before_request
def proteger():
    if request.endpoint == "abonnement_client.notification_paypal":
        return None  # Signature du fournisseur vérifiée par cette route.
    if utilisateur_connecte() is None:
        return redirect(url_for("espace_personnel.connexion", suivant="/mon-espace/abonnement"))
    if request.method == "POST":
        verifier_csrf_espace()


@abonnement_client_bp.after_request
def prive(reponse):
    reponse.headers["Cache-Control"] = "no-store, private"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    return reponse


def _stockage_pret():
    moteur = db.session.get_bind(mapper=CommandeAbonnementEspace)
    return all(inspect(moteur).has_table(n) for n in (
        "commandes_abonnements_espace", "inscriptions_mails_beta", "mails_evenements_abonnes", "revolutions_solaires_pack_beta"))


def _fuseau(profil):
    try:
        return ZoneInfo(profil.fuseau_cycles) if profil and profil.fuseau_cycles else ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Paris")


@abonnement_client_bp.route("/abonnement")
def mon_abonnement():
    utilisateur = utilisateur_connecte()
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    try:
        natal = bool(profil and json.loads(profil.theme_natal or "{}")["planetes"]["Lune"]["longitude"] is not None)
    except (ValueError, KeyError, TypeError):
        natal = False
    ville = bool(profil and profil.ville_cycles and profil.fuseau_cycles and
                 profil.latitude_cycles is not None and profil.longitude_cycles is not None)
    choix_journal = utilisateur.journal_mails_choix_le is not None
    pret = _stockage_pret()
    config = configuration_paiement()
    commande = CommandeAbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id, offre=OFFRE,
                sandbox=config["sandbox"]).first() if pret else None
    inscription = db.session.get(InscriptionMailsBeta, utilisateur.id) if pret else None
    rs_pack = db.session.get(RevolutionSolairePackBeta, commande.id) if commande else None
    prochains = MailEvenementAbonne.query.filter(MailEvenementAbonne.utilisateur_id == utilisateur.id,
        MailEvenementAbonne.date_prevue >= datetime.now(timezone.utc),
        MailEvenementAbonne.statut.in_(("planifie", "attente_analyse", "pret"))
    ).order_by(MailEvenementAbonne.date_prevue).limit(4).all() if pret and inscription and inscription.actif else []
    return render_template("espace_personnel/mon_abonnement.html", profil=profil,
        natal=natal, ville=ville, choix_journal=choix_journal, stockage_pret=pret,
        commande=commande, inscription=inscription, prochains=prochains, natures=NATURES,
        choix_commande=formule_commande(commande) if commande else None, rs_pack=rs_pack,
        offre=offre_publique(), utc=utc, fuseau=_fuseau(profil),
        invite_beta=adresse_invitee_beta(utilisateur.email),
        termine=bool(inscription and datetime.now(timezone.utc) >= utc(inscription.fin)))


@abonnement_client_bp.route("/abonnement/journal", methods=["POST"])
def choix_journal():
    valeur = request.form.get("autoriser_journal_mails")
    if valeur not in {"oui", "non"}:
        abort(400)
    utilisateur = utilisateur_connecte()
    utilisateur.autoriser_journal_mails = valeur == "oui"
    utilisateur.journal_mails_choix_le = datetime.now(timezone.utc)
    db.session.commit()
    flash("Ton choix pour le journal est enregistré. Tu peux le changer à tout moment.", "success")
    return redirect(url_for("abonnement_client.mon_abonnement"))


@abonnement_client_bp.route("/abonnement/paypal/creer", methods=["POST"])
def creer():
    if not adresse_invitee_beta(utilisateur_connecte().email):
        return jsonify(error="Cette offre bêta est réservée aux adresses invitées par Cécile."), 403
    if not _stockage_pret():
        return jsonify(error="La souscription est en cours de préparation."), 409
    try:
        from utils.souscription_espace import creer_commande
        commande = creer_commande(utilisateur_connecte(), request.form.get("conditions") == "oui",
                                 request.form.get("formule", "espace_seul"))
        return jsonify(id=commande.fournisseur_commande_id, formule=formule_commande(commande)["code"])
    except ValueError as erreur:
        db.session.rollback()
        return jsonify(error=str(erreur)), 409
    except Exception:
        db.session.rollback()
        return jsonify(error="La préparation n’a pas abouti. Vérifie ton abonnement avant de recommencer."), 503


@abonnement_client_bp.route("/abonnement/paypal/capturer", methods=["POST"])
def capturer():
    if not _stockage_pret():
        abort(409)
    config = configuration_paiement()
    commande = CommandeAbonnementEspace.query.filter_by(utilisateur_id=utilisateur_connecte().id,
        fournisseur_commande_id=request.form.get("orderID", ""), offre=OFFRE, sandbox=config["sandbox"]).first_or_404()
    try:
        from utils.souscription_espace import verifier_ou_capturer
        selection = FORMULES_BETA.get(request.form.get("formule"))
        if selection is None:
            return jsonify(error="Recharge la page pour confirmer ton option et le montant avant de payer."), 409
        verifier_ou_capturer(commande, capturer=True, montant_attendu=selection["prix_centimes"])
        return jsonify(redirect=url_for("abonnement_client.mon_abonnement"))
    except Exception:
        db.session.rollback()
        return jsonify(error="La confirmation n’a pas abouti. Vérifie le paiement depuis « Mon abonnement » ; ne paie pas une seconde fois."), 409


@abonnement_client_bp.route("/abonnement/verifier-paiement", methods=["POST"])
def verifier_paiement():
    if not _stockage_pret():
        abort(409)
    commande = CommandeAbonnementEspace.query.filter_by(utilisateur_id=utilisateur_connecte().id,
        offre=OFFRE, sandbox=configuration_paiement()["sandbox"]).first_or_404()
    try:
        from utils.souscription_espace import verifier_ou_capturer
        resultat = verifier_ou_capturer(commande)
        flash("Paiement confirmé. Ton inscription est enregistrée." if resultat.statut == "active" else resultat.erreur, "success")
    except Exception:
        db.session.rollback()
        flash("Le paiement n’a pas été confirmé. Cette vérification ne débite rien. Si tu as été débité, contacte Cécile avant de recommencer.", "error")
    return redirect(url_for("abonnement_client.mon_abonnement"))


@abonnement_client_bp.route("/abonnement/paypal/webhook", methods=["POST"])
def notification_paypal():
    if not _stockage_pret() or request.content_length is None or request.content_length > 131072:
        abort(400)
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        abort(400)
    try:
        from utils.souscription_espace import traiter_notification_paypal
        return jsonify(statut=traiter_notification_paypal(request.headers, donnees))
    except Exception:
        db.session.rollback()
        return jsonify(statut="verification_non_aboutie"), 503


@abonnement_client_bp.route("/mes-mails")
def mes_mails():
    utilisateur = utilisateur_connecte()
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    mails = MailEvenementAbonne.query.filter_by(utilisateur_id=utilisateur.id, statut="envoye").order_by(
        MailEvenementAbonne.date_envoi.desc()).all() if _stockage_pret() else []
    return render_template("espace_personnel/mes_mails.html", mails=mails,
        natures=NATURES, utc=utc, fuseau=_fuseau(profil))


@abonnement_client_bp.route("/abonnement/revolution-solaire", methods=["GET", "POST"])
def revolution_solaire_pack():
    if not _stockage_pret():
        abort(404)
    utilisateur = utilisateur_connecte()
    commande = CommandeAbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id,
        offre=OFFRE, sandbox=configuration_paiement()["sandbox"], statut="active").first_or_404()
    if not formule_commande(commande)["avec_rs"]:
        abort(404)
    droit = db.session.get(RevolutionSolairePackBeta, commande.id)
    if not droit or droit.utilisateur_id != utilisateur.id:
        abort(404)
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil is None:
        return redirect(url_for("espace_personnel.profil"))
    saisie = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            from utils.rs_pack_beta import preparer, generer
            if droit.statut != "a_preparer":
                raise ValueError("Ce rapport est déjà en cours, terminé ou à vérifier. Aucun nouvel appel lancé.")
            if request.form.get("confirmer_generation") != "oui":
                raise ValueError("Confirme la préparation de ton rapport avant de continuer.")
            preparation = preparer(profil, request.form)
            analyse = generer(commande, droit, profil, preparation)
            flash("Ta Révolution Solaire est disponible dans Mes analyses. Aucun mail supplémentaire envoyé.", "success")
            return redirect(url_for("espace_personnel.lire_analyse", analyse_id=analyse.id))
        except (ValueError, TypeError, KeyError) as erreur:
            db.session.rollback()
            flash(str(erreur) if isinstance(erreur, ValueError) else "Vérifie l’année et choisis une ville dans les suggestions.", "error")
    maintenant = datetime.now(_fuseau(profil))
    annee = maintenant.year - ((maintenant.month, maintenant.day) < (profil.date_naissance.month, profil.date_naissance.day))
    return render_template("espace_personnel/rs_pack_beta.html", profil=profil, droit=droit,
                           saisie=saisie, annee=annee)


@abonnement_client_bp.route("/mes-mails/<mail_id>")
def lire_mail(mail_id):
    if not _stockage_pret():
        abort(404)
    mail = MailEvenementAbonne.query.filter_by(id=mail_id, utilisateur_id=utilisateur_connecte().id, statut="envoye").first_or_404()
    from utils.journal_mails import notes_du_mail
    return render_template("espace_personnel/lire_mail.html", mail=mail, notes_liees=notes_du_mail(mail))


@abonnement_client_bp.route("/mes-mails/<mail_id>/contenu")
def contenu_mail(mail_id):
    if not _stockage_pret():
        abort(404)
    mail = MailEvenementAbonne.query.filter_by(id=mail_id, utilisateur_id=utilisateur_connecte().id, statut="envoye").first_or_404()
    reponse = Response(mail.contenu_html or "", mimetype="text/html")
    reponse.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data: https://lesfousdastro.fr; frame-ancestors 'self'; form-action 'none'"
    return reponse
