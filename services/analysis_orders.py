"""Single authority for payment, beneficiary binding and execution ownership."""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import abort, session
from sqlalchemy.exc import IntegrityError
from extensions import db
from models.analysis_orders import AnalysisOrder, AnalysisJob, GiftGrant
from config.products import PRODUCTS


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def owner_hash():
    if not session.get('analysis_owner'):
        session['analysis_owner'] = secrets.token_urlsafe(32)
    return digest(session['analysis_owner'])


def catalog_items(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        abort(400, 'Panier invalide.')
    normalized, products = [], []
    for item in items:
        if not isinstance(item, dict):
            abort(400, 'Produit invalide.')
        key = item.get('key') or item.get('id')
        product = PRODUCTS.get(key)
        # One beneficiary per order; quantities >1 cannot create additional rights.
        if not product or str(item.get('quantity', 1)) != '1':
            abort(400, 'Produit inconnu ou quantité différente de 1.')
        included = product.get('included_products') or [key]
        if any(p not in PRODUCTS or p in products for p in included):
            abort(400, 'Produit indisponible ou présent plusieurs fois.')
        products.extend(included)
        cents = product['price_cents']
        if not isinstance(cents, int) or cents <= 0:
            abort(503, 'Catalogue invalide.')
        normalized.append({'key': key, 'quantity': 1, 'price_cents': cents})
    if 'flash_transits' in products and len(products) != 1:
        abort(400, 'Le Point Transits doit être commandé séparément.')
    return normalized, products


def create_order(provider, items, infos, sandbox=False, commit=True):
    items, products = catalog_items(items)
    if not isinstance(infos, dict) or not all(infos.get(k) for k in
            ('nom', 'email', 'date_naissance', 'heure_naissance', 'lieu_naissance', 'lat', 'lon', 'tzid')):
        abort(400, 'Informations du bénéficiaire incomplètes.')
    order = AnalysisOrder(owner_hash=owner_hash(), provider=provider, items=items,
        products=products, beneficiary=dict(infos), sandbox=sandbox,
        amount_cents=sum(i['price_cents'] for i in items), currency='EUR')
    db.session.add(order)
    db.session.flush()
    for product in products:
        db.session.add(AnalysisJob(order_id=order.id, product=product))
    db.session.add(AnalysisJob(order_id=order.id, product='__delivery'))
    db.session.add(AnalysisJob(order_id=order.id, product='__clarification'))
    if commit:
        db.session.commit()
    session['analysis_order_id'] = order.id
    return order


def owned_order(provider=None, provider_id=None, paid=False):
    order = db.session.get(AnalysisOrder, session.get('analysis_order_id')) if session.get('analysis_order_id') else None
    if (not order or not secrets.compare_digest(order.owner_hash, owner_hash())
            or (provider and order.provider != provider)
            or (provider_id and order.provider_id != f'{provider}:{provider_id}')):
        abort(403, 'Commande introuvable dans cette session.')
    if paid and (order.status != 'paid' or not environment_matches(order)):
        abort(403, 'Paiement non confirmé.')
    return order


def bind_provider(order, provider_id):
    if not provider_id:
        abort(502, 'Identifiant de paiement manquant.')
    value = f'{order.provider}:{provider_id}'
    if order.provider_id and order.provider_id != value:
        abort(409, 'Commande déjà associée à un paiement.')
    order.provider_id = value
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, 'Paiement déjà associé à une commande.')


def mark_paid(order, payment_id):
    value = f'{order.provider}:{payment_id}'
    if not payment_id or (order.payment_id and order.payment_id != value):
        abort(409, 'Identifiant de transaction invalide.')
    if order.status not in ('pending', 'paid'):
        abort(403, 'Commande annulée.')
    order.payment_id, order.status = value, 'paid'
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, 'Transaction déjà utilisée.')


def confirm_stripe(order, data):
    if (order.provider != 'stripe' or order.provider_id != 'stripe:' + str(data.get('id'))
        or data.get('mode') != 'payment' or data.get('payment_status') != 'paid'
        or data.get('client_reference_id') != order.id
        or (data.get('metadata') or {}).get('order_id') != order.id
        or data.get('amount_total') != order.amount_cents
        or (data.get('currency') or '').upper() != order.currency
        or data.get('livemode') is not (not order.sandbox)):
        abort(403, 'Le paiement ne correspond pas à la commande.')
    mark_paid(order, data.get('payment_intent'))


def money_cents(amount, currency):
    try:
        value = Decimal(str(amount.get('value'))) * 100
        if amount.get('currency_code') != currency or not value.is_finite() or value != value.to_integral_value():
            raise ValueError()
        return int(value)
    except (InvalidOperation, ValueError, TypeError):
        abort(403, 'Montant ou devise invalides.')


def confirm_paypal(order, data):
    units = data.get('purchase_units') or []
    if (order.provider != 'paypal' or order.provider_id != 'paypal:' + str(data.get('id'))
        or data.get('status') != 'COMPLETED' or len(units) != 1):
        abort(403, 'Le paiement ne correspond pas à la commande.')
    captures = (units[0].get('payments') or {}).get('captures') or []
    if (len(captures) != 1 or captures[0].get('status') != 'COMPLETED'
        or money_cents(captures[0].get('amount') or {}, order.currency) != order.amount_cents):
        abort(403, 'Capture ou montant non confirmé.')
    # PayPal Sandbox may omit custom_id from a capture response. The order ID is
    # already bound server-side before approval; reject any returned mismatch.
    for custom_id in (units[0].get('custom_id'), captures[0].get('custom_id')):
        if custom_id is not None and custom_id != order.id:
            abort(403, 'Le paiement ne correspond pas à la commande.')
    mark_paid(order, captures[0].get('id'))


def restore_order(order):
    session['infos_utilisateur'] = dict(order.beneficiary)
    session['ordered_products'] = list(order.products)
    session['paiement_valide'] = True
    session['last_payment'] = {'provider': order.provider, 'status': 'paid',
        'product_keys': order.products, 'order_id': (order.provider_id or '').split(':', 1)[-1]}
    session['pending_generation'] = {'products': list(order.products),
        'provider': order.provider, 'secure_order_id': order.id}


class JobBusy(Exception):
    pass


class JobReview(Exception):
    pass


def run_job(order_id, product, generate):
    order = db.session.get(AnalysisOrder, order_id)
    if not order or order.status != 'paid' or not environment_matches(order) or product not in order.products:
        abort(403, 'Produit non acheté pour ce bénéficiaire.')
    job = AnalysisJob.query.filter_by(order_id=order.id, product=product).one()
    if job.status == 'complete':
        return job.result
    # Atomic compare-and-set, shared by every worker and HTTP/pack path.
    updated = AnalysisJob.query.filter_by(id=job.id, status='pending').update(
        {'status': 'running', 'started_at': datetime.now(timezone.utc)}, synchronize_session=False)
    db.session.commit()
    if not updated:
        db.session.refresh(job)
        if job.status == 'complete':
            return job.result
        if job.status == 'review':
            raise JobReview()
        raise JobBusy()
    try:
        result = generate(dict(order.beneficiary))
        if not isinstance(result, dict) or not result.get('pdf_url'):
            raise ValueError('Aucun PDF confirmé')
        job.result, job.status = result, 'complete'
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        # Never restart an uncertain LLM call automatically, even after a crash.
        AnalysisJob.query.filter_by(id=job.id, status='running').update({'status': 'review'})
        db.session.commit()
        raise


def redeem_gift(code, infos):
    key = digest(code.strip().upper())
    grant = db.session.get(GiftGrant, key)
    if not grant or grant.redeemed_order:
        abort(403, 'Cadeau invalide ou déjà consommé.')
    order = create_order('gift', [{'key': grant.product}], infos, commit=False)
    claimed = GiftGrant.query.filter_by(code_hash=key, redeemed_order=None).update(
        {'redeemed_order': order.id}, synchronize_session=False)
    if not claimed:
        db.session.rollback()
        abort(409, 'Cadeau déjà consommé.')
    order.provider_id = 'gift:' + key
    order.payment_id = 'gift:' + key
    order.status = 'paid'
    db.session.commit()
    return order


def claim_notice(order_id, kind):
    claimed = AnalysisJob.query.filter_by(order_id=order_id, product=kind, status='pending').update(
        {'status': 'running'}, synchronize_session=False)
    db.session.commit()
    return bool(claimed)


def environment_matches(order):
    on = lambda key: (os.getenv(key) or '').strip().lower() in {'1', 'true', 'on', 'yes'}
    sandbox = on('PAYMENTS_SANDBOX') and on('APP_MAINTENANCE')
    return order.provider == 'gift' or order.sandbox == sandbox
