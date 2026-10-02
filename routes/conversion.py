"""Minimal, allowlisted funnel telemetry. No form data or raw URLs accepted."""
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, current_app, request, jsonify, session
from config.products import PRODUCTS

conversion_bp = Blueprint('conversion', __name__)
EVENTS = {'funnel_visit', 'free_analysis_start', 'free_analysis_success',
          'free_analysis_error', 'free_analysis_close', 'paid_offer_click',
          'offer_view', 'view_item', 'add_to_cart', 'begin_checkout', 'checkout_error', 'offer_feedback'}
REASONS = {'enough', 'choice', 'sample', 'price', 'personalization', 'not_ready', 'other'}
SOURCES = {'instagram', 'google', 'newsletter', 'direct', 'other'}
CAMPAIGNS = {'free_analysis', 'free_j1', 'free_j3', 'free_j5', 'other'}


def connect():
    path = Path(current_app.config.get('CONVERSION_DB') or os.getenv('CONVERSION_DB')
                or Path(current_app.instance_path) / 'conversion.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, date TEXT NOT NULL, '
                 'sid TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL, transaction_id TEXT UNIQUE)')
    conn.execute('CREATE INDEX IF NOT EXISTS event_date ON events(date)')
    return conn


def clean(data):
    if not isinstance(data, dict) or data.get('event') not in EVENTS:
        raise ValueError()
    sid = str(uuid.UUID(data['session_id']))
    event = data['event']
    payload = {}
    product = data.get('product')
    if product in PRODUCTS:
        payload.update(product=product, price=PRODUCTS[product]['price_cents'] / 100)
    if data.get('offered_product') in {'flash_astral', 'forces_defis'}:
        payload['offered_product'] = data['offered_product']
    if event == 'offer_feedback':
        if data.get('reason') not in REASONS:
            raise ValueError()
        # Feedback contains only reason, date, anonymous session and offer.
        return sid, event, {k: v for k, v in dict(reason=data['reason'],
            offered_product=payload.get('offered_product', 'flash_astral')).items()}
    for key, allowed in {
        'location': {'home', 'free_result', 'catalog', 'cart', 'stripe', 'paypal'},
        'source': SOURCES, 'campaign': CAMPAIGNS,
        'device': {'mobile', 'desktop'},
        'error_type': {'generation', 'quota', 'network', 'payment', 'validation'},
        'stage': {'loading', 'success', 'error'},
    }.items():
        if data.get(key) in allowed:
            payload[key] = data[key]
    return sid, event, payload


def record(sid, event, payload, transaction=None):
    with closing(connect()) as conn, conn:
        # Limit a single session; no IP storage.
        if event != 'purchase' and conn.execute('SELECT COUNT(*) FROM events WHERE sid=?', (sid,)).fetchone()[0] >= 500:
            return False
        if event == 'offer_feedback' and conn.execute(
                "SELECT 1 FROM events WHERE sid=? AND event='offer_feedback'", (sid,)).fetchone():
            return False
        cursor = conn.execute('INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)',
            (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), sid, event,
             json.dumps(payload), transaction))
        return cursor.rowcount == 1


@conversion_bp.post('/api/conversion/events')
def collect():
    if request.content_length and request.content_length > 2048:
        return '', 413
    try:
        sid, event, payload = clean(request.get_json(silent=True))
    except (ValueError, TypeError, KeyError, AttributeError):
        return '', 400
    try:
        session['conversion_sid'] = sid
        record(sid, event, payload)
    except (OSError, sqlite3.Error):
        current_app.logger.warning('Conversion storage unavailable')
        return '', 503
    return '', 204


@conversion_bp.post('/api/conversion/purchase')
def purchase():
    from services.analysis_orders import owned_order
    order = owned_order(paid=True)
    # Never treat gift grants or QA bypasses as paid sales.
    if order.provider not in {'stripe', 'paypal'} or not order.payment_id:
        return '', 204
    data = request.get_json(silent=True) or {}
    try:
        sid = str(uuid.UUID(data['session_id']))
    except (ValueError, TypeError, KeyError, AttributeError):
        return '', 400
    payload = dict(transaction_id=order.id, value=order.amount_cents / 100,
                   currency=order.currency, sandbox=order.sandbox,
                   items=[dict(item_id=i['key'], item_name=PRODUCTS[i['key']]['label'],
                               price=i['price_cents'] / 100, quantity=1) for i in order.items])
    if isinstance(data.get('offered_product'), str) and data['offered_product'] in {'flash_astral', 'forces_defis'}:
        payload['offered_product'] = data['offered_product']
    try:
        record(sid, 'purchase', payload, order.id)
    except (OSError, sqlite3.Error):
        current_app.logger.warning('Conversion purchase storage unavailable')
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'no-store'
    return response


@conversion_bp.after_app_request
def checkout_failure(response):
    sid = session.get('conversion_sid')
    if sid and request.path == '/checkout' and response.status_code >= 400:
        try:
            record(sid, 'checkout_error', {'location':'stripe', 'error_type':'payment'})
        except (OSError, sqlite3.Error):
            current_app.logger.warning('Conversion checkout error storage unavailable')
    return response
