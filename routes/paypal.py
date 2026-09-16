import os
import json
import requests
from flask import Blueprint, request, jsonify, session, current_app
import logging
from requests.auth import HTTPBasicAuth
from config.products import PRODUCTS


payments_bp = Blueprint("payments", __name__)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ⚙️ CONFIGURATION PAYPAL : Sélection automatique TEST/LIVE
# ─────────────────────────────────────────────────────────────────────────────

def _env_on(v: str | None) -> bool:
    """Convertit une variable d'environnement en booléen."""
    return (v or "").strip().lower() in ("1", "true", "on", "yes")

PAYMENTS_SANDBOX = _env_on(os.getenv("PAYMENTS_SANDBOX"))
APP_MAINTENANCE = _env_on(os.getenv("APP_MAINTENANCE"))

# 🔒 Sécurité : Désactiver sandbox si maintenance OFF
if PAYMENTS_SANDBOX and not APP_MAINTENANCE:
    logger.warning("⚠️ [PayPal] PAYMENTS_SANDBOX=on mais APP_MAINTENANCE=off → sandbox désactivé")
    PAYMENTS_SANDBOX = False

# 🔑 Choix du mode PayPal selon PAYMENTS_SANDBOX
PAYPAL_MODE = "sandbox" if PAYMENTS_SANDBOX else "live"
PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com" if PAYMENTS_SANDBOX else "https://api-m.paypal.com"

logger.info(f"🔑 [PayPal] Mode = {'SANDBOX TEST 🧪' if PAYMENTS_SANDBOX else 'LIVE 💳'} | URL = {PAYPAL_BASE_URL}")

def get_paypal_token():
    def _env_on(v):
        return (v or "").strip().lower() in ("1", "true", "on", "yes")
    
    payments_sandbox = _env_on(os.getenv("PAYMENTS_SANDBOX"))
    app_maint = _env_on(os.getenv("APP_MAINTENANCE"))
    
    use_sandbox = payments_sandbox and app_maint
    
    base_url = "https://api-m.sandbox.paypal.com" if use_sandbox else "https://api-m.paypal.com"

    if use_sandbox:
        client_id = os.getenv("PAYPAL_CLIENT_ID_SANDBOX", "").strip()
        secret = os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX", "").strip()
    else:
        client_id = (
            os.getenv("PAYPAL_CLIENT_ID_LIVE") or 
            os.getenv("PAYPAL_CLIENT_ID") or 
            ""
        ).strip()
        secret = (
            os.getenv("PAYPAL_CLIENT_SECRET_LIVE") or
            os.getenv("PAYPAL_SECRET") or 
            ""
        ).strip()

    current_app.logger.info(
        "🔑 [PayPal] Token request | mode=%s | base=%s | client_id=%s… | secret_set=%s",
        "sandbox" if use_sandbox else "live",
        base_url,
        (client_id or "")[:8],
        bool(secret)
    )

    if not client_id or not secret:
        raise RuntimeError(
            f"PAYPAL credentials manquants pour mode={'sandbox' if use_sandbox else 'live'}."
        )

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    r = requests.post(
        f"{base_url}/v1/oauth2/token",
        headers=headers,
        data=data,
        auth=HTTPBasicAuth(client_id, secret),
        timeout=10,
    )
    
    try:
        r.raise_for_status()
    except requests.HTTPError:
        try:
            body = r.json()
        except Exception:
            body = r.text
        current_app.logger.error(
            "❌ [PayPal] Erreur token %s | url=%s | body=%s", 
            r.status_code, r.url, body
        )
        raise

    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("Réponse PayPal sans access_token.")

    return token, base_url

# ─────────────────────────────────────────────────────────────────────────────
# POST /payments/create-order - MULTI-PRODUITS
# ─────────────────────────────────────────────────────────────────────────────

from services.analysis_orders import (
    create_order as create_analysis_order, bind_provider, owned_order,
    confirm_paypal, restore_order,
)


def paypal_beneficiary(data):
    info = data.get('userInfo') or {}
    return {
        'nom': info.get('nom'), 'email': info.get('email'),
        'gender': info.get('gender') or info.get('genre') or '',
        'date_naissance': info.get('birthDate'), 'heure_naissance': info.get('birthTime'),
        'lieu_naissance': info.get('birthPlace'),
        'lat': info.get('lat'), 'lon': info.get('lon'), 'tzid': info.get('tzid'),
        'transit_date_mode': info.get('transitDateMode') or 'today',
        'transit_date': info.get('transitDate') or '',
    }


@payments_bp.route('/payments/create-order', methods=['POST'])
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get('items') or [{'key': data.get('product_key')}]
    order = create_analysis_order('paypal', items, paypal_beneficiary(data), PAYMENTS_SANDBOX)
    token, base_url = get_paypal_token()
    payload = {'intent': 'CAPTURE', 'purchase_units': [{
        'reference_id': order.id, 'custom_id': order.id,
        'amount': {'currency_code': order.currency, 'value': f'{order.amount_cents / 100:.2f}'},
        'description': ', '.join(PRODUCTS[i['key']]['label'] for i in order.items)[:127],
    }]}
    try:
        response = requests.post(base_url + '/v2/checkout/orders',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}',
                     'PayPal-Request-Id': order.id}, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        bind_provider(order, result.get('id'))
        return jsonify(result), 201
    except (requests.RequestException, ValueError):
        return jsonify(error='Création PayPal indisponible.'), 502


@payments_bp.route('/payments/capture-order', methods=['POST'])
def capture_order():
    data = request.get_json(silent=True) or {}
    provider_id = data.get('orderID') or data.get('orderId')
    if not isinstance(provider_id, str) or not provider_id.isalnum():
        return jsonify(error='Identifiant PayPal invalide.'), 400
    order = owned_order(provider='paypal', provider_id=provider_id)
    # Beneficiary and cart from create-order are immutable, capture body ignored.
    if order.status == 'paid':
        restore_order(order)
        return jsonify(id=provider_id, status='COMPLETED'), 200
    token, base_url = get_paypal_token()
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}',
               'PayPal-Request-Id': order.id}
    endpoint = f'{base_url}/v2/checkout/orders/{provider_id}'
    try:
        response = requests.post(endpoint + '/capture', headers=headers, json={}, timeout=20)
        # A lost capture response or concurrent request is resolved from PayPal,
        # never from data supplied by the browser.
        if response.status_code not in (200, 201):
            response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
        result = response.json()
        confirm_paypal(order, result)
        restore_order(order)
        return jsonify(id=provider_id, status='COMPLETED'), 200
    except (requests.RequestException, ValueError):
        return jsonify(error='Confirmation PayPal indisponible. Réessaie sans repayer.'), 502
