"""Invitations, inscriptions et paiements de la bêta, sans envoi ni génération."""
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import and_, case, inspect, or_

from extensions import db
from models.espace_personnel import (
    AbonnementEspace, CommandeAbonnementEspace, InscriptionMailsBeta, InvitationOffreBeta, UtilisateurEspace,
)
from utils.acces_abonnement import FORMULES_ABONNEMENT, STATUTS_ACTIFS, acces_abonnement
from utils.auth_espace import administratrice_connectee, verifier_csrf_espace
from utils.invitations_beta import OFFRE_BETA, autoriser_adresses_beta, stockage_invitations_pret
from utils.mails_evenements import PARIS, utc
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


@admin_beta_bp.route('/comptes')
def comptes():
    """Tous les comptes et leurs droits actuels, sans charger leurs données privées."""
    maintenant = datetime.now(timezone.utc)
    recherche = request.args.get('q', '').strip()[:200]
    formules = {
        'toutes': 'Toutes les formules',
        'gratuit': 'Espace gratuit',
        'rl': 'Boussole lunaire · RL',
        'complet': 'Accompagnement complet · bêta incluse',
    }
    filtre = request.args.get('formule', 'toutes')
    if filtre not in formules:
        filtre = 'toutes'
    requete = db.session.query(
        UtilisateurEspace.id, UtilisateurEspace.prenom, UtilisateurEspace.email,
        UtilisateurEspace.actif, UtilisateurEspace.est_administratrice,
        UtilisateurEspace.date_creation, AbonnementEspace,
    ).select_from(UtilisateurEspace).outerjoin(
        AbonnementEspace, AbonnementEspace.utilisateur_id == UtilisateurEspace.id)
    total = requete.count()
    if recherche:
        terme = '%' + recherche.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        requete = requete.filter(or_(
            UtilisateurEspace.prenom.ilike(terme, escape='\\'),
            UtilisateurEspace.email.ilike(terme, escape='\\'),
        ))
    # Même règle de statut et de dates que acces_abonnement(), appliquée au filtre SQL.
    formule_effective = case((and_(
        UtilisateurEspace.actif == 1,
        AbonnementEspace.statut.in_(tuple(STATUTS_ACTIFS)),
        AbonnementEspace.formule.in_(tuple(FORMULES_ABONNEMENT)),
        or_(AbonnementEspace.date_debut.is_(None), AbonnementEspace.date_debut <= maintenant),
        or_(AbonnementEspace.date_fin.is_(None), AbonnementEspace.date_fin > maintenant),
    ), AbonnementEspace.formule), else_='espace_gratuit')
    codes = {
        'gratuit': ('espace_gratuit',),
        'rl': ('boussole_lunaire',),
        'complet': ('accompagnement_astral', 'beta_accompagnement'),
    }
    if filtre in codes:
        requete = requete.filter(formule_effective.in_(codes[filtre]))
    nombre = requete.count() if recherche or filtre != 'toutes' else total
    pages = max(1, (nombre + 49) // 50)
    page = min(pages, max(1, request.args.get('page', 1, type=int)))
    lignes = requete.order_by(UtilisateurEspace.date_creation.desc(), UtilisateurEspace.id.desc()).offset(
        (page - 1) * 50).limit(50).all()
    comptes_affiches = []
    for identifiant, prenom, email, actif, admin, creation, abonnement in lignes:
        droits = acces_abonnement(abonnement, maintenant)
        etat = 'Gratuit'
        if abonnement:
            if abonnement.formule not in FORMULES_ABONNEMENT:
                etat = 'Formule à vérifier'
            elif abonnement.statut not in STATUTS_ACTIFS:
                etat = 'Inactif'
            elif abonnement.date_fin and utc(abonnement.date_fin) <= maintenant:
                etat = 'Terminé'
            elif abonnement.date_debut and utc(abonnement.date_debut) > maintenant:
                etat = 'À venir'
            elif droits['actif']:
                etat = 'Test / accès offert' if abonnement.statut == 'test' else 'Actif'
        comptes_affiches.append({
            'id': identifiant, 'prenom': prenom, 'email': email, 'actif': actif == 1,
            'administratrice': admin, 'creation': creation,
            'formule': FORMULES_ABONNEMENT.get(abonnement.formule, {}).get('libelle', 'Formule inconnue')
                if abonnement else 'Espace gratuit',
            'acces': droits['libelle'] if actif == 1 else 'Aucun accès · compte désactivé',
            'etat': etat, 'debut': abonnement.date_debut if abonnement else None,
            'fin': abonnement.date_fin if abonnement else None,
        })
    return render_template('admin/comptes_abonnements.html', comptes=comptes_affiches,
        total=total, nombre=nombre, page=page, pages=pages, recherche=recherche,
        filtre=filtre, formules=formules, utc=utc, paris=PARIS)


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
        utc=utc, paris=PARIS)


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
