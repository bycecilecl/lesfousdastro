"""Invitations, inscriptions et paiements de la bêta, sans envoi ni génération."""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import inspect

from extensions import db
from models.espace_personnel import (
    CommandeAbonnementEspace, InscriptionMailsBeta, InvitationOffreBeta, UtilisateurEspace,
)
from utils.auth_espace import administratrice_connectee, verifier_csrf_espace
from utils.invitations_beta import OFFRE_BETA, autoriser_adresses_beta, stockage_invitations_pret
from utils.mails_evenements import DEBUT_BETA, FIN_BETA, PARIS, utc
from utils.souscription_espace import configuration_paiement

admin_beta_bp = Blueprint('admin_beta', __name__, url_prefix='/admin/beta-testeurs')
STATUTS_PAIEMENT = {
    'creation_en_cours': 'Préparation du paiement', 'prete': 'Paiement à terminer',
    'creation_incertaine': 'Préparation à vérifier', 'capture_en_cours': 'Confirmation en cours',
    'modification_en_cours': 'Changement d’option en cours', 'modification_incertaine': 'Changement d’option à reprendre',
    'capture_incertaine': 'Confirmation à vérifier', 'payee': 'Payé · profil à compléter',
    'active': 'Payé · inscription confirmée', 'rembourse': 'Remboursé', 'revoque': 'Révoqué',
}


@admin_beta_bp.before_request
def proteger():
    if not administratrice_connectee():
        abort(404)
    if request.method == 'POST':
        verifier_csrf_espace()


@admin_beta_bp.after_request
def prive(reponse):
    reponse.headers['Cache-Control'] = 'private, no-store'
    reponse.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return reponse


def _table_prete(modele):
    return inspect(db.session.get_bind(mapper=modele)).has_table(modele.__tablename__)


@admin_beta_bp.route('')
@admin_beta_bp.route('/')
def index():
    invitations_pretes = stockage_invitations_pret()
    invitations = InvitationOffreBeta.query.filter_by(offre=OFFRE_BETA).order_by(
        InvitationOffreBeta.email).all() if invitations_pretes else []
    paiements_prets = _table_prete(CommandeAbonnementEspace)
    commandes = CommandeAbonnementEspace.query.filter_by(offre=OFFRE_BETA).order_by(
        CommandeAbonnementEspace.date_creation.desc()).limit(100).all() if paiements_prets else []
    inscriptions_pretes = _table_prete(InscriptionMailsBeta)
    inscriptions = InscriptionMailsBeta.query.order_by(
        InscriptionMailsBeta.date_creation.desc()).all() if inscriptions_pretes else []
    ids = {c.utilisateur_id for c in commandes} | {i.utilisateur_id for i in inscriptions}
    utilisateurs = {u.id: u for u in UtilisateurEspace.query.filter(
        UtilisateurEspace.id.in_(ids)).all()} if ids else {}
    return render_template('admin/beta_testeurs.html', invitations=invitations,
        invitations_pretes=invitations_pretes, commandes=commandes, paiements_prets=paiements_prets,
        inscriptions=inscriptions, inscriptions_pretes=inscriptions_pretes, utilisateurs=utilisateurs,
        paiement_ouvert=configuration_paiement()['ouvert'], statuts_paiement=STATUTS_PAIEMENT,
        debut=DEBUT_BETA.astimezone(PARIS), fin=(FIN_BETA - timedelta(days=1)).astimezone(PARIS), utc=utc, paris=PARIS)


@admin_beta_bp.route('/invitations', methods=['POST'])
def invitations():
    if not stockage_invitations_pret():
        abort(503)
    try:
        action = request.form.get('action')
        if action == 'retirer':
            invitation = db.session.get(InvitationOffreBeta, (request.form.get('email', '').strip().lower(), OFFRE_BETA))
            if invitation is None:
                abort(404)
            invitation.actif = False
            message = 'Adresse retirée. Un abonnement déjà payé est conservé.'
        elif action == 'ajouter':
            total = autoriser_adresses_beta(request.form.get('adresses', ''))
            message = f'{total} adresse(s) autorisée(s). Aucun compte créé ni message envoyé.'
        else:
            abort(400)
        db.session.commit()
        flash(message, 'success')
    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), 'error')
    return redirect(url_for('admin_beta.index', _anchor='invitations'))
