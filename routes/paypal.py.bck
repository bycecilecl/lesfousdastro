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

# ─────────────────────────────────────────────────────────────────────────────
# QA Mode (tests automatisés)
# ─────────────────────────────────────────────────────────────────────────────

QA_WHITELIST = {e.strip().lower() for e in os.getenv("QA_WHITELIST_EMAILS", "").split(",") if e.strip()}

def is_qa_request():
    flag = (request.args.get("qa") == "1") or (request.headers.get("X-QA") == "1")
    if not flag:
        return False
    try:
        body = request.get_json(silent=True) or {}
        email = (body.get("userInfo", {}).get("email") or "").lower()
        if email in QA_WHITELIST:
            logger.info("✅ [QA] Mode activé pour %s", email)
            return True
    except Exception:
        pass
    return False

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

@payments_bp.route("/payments/create-order", methods=["POST"])
def create_order():
    # 🔐 QA bypass
    if is_qa_request():
        return jsonify({"id": "TEST-ORDER-QA", "status": "CREATED", "qa": True}), 200
    
    payload_in = request.get_json() or {}
    
    # 🛒 Récupérer le panier depuis le frontend
    cart_items = payload_in.get("items", [])
    
    # Fallback ancien comportement
    if not cart_items:
        product_key = payload_in.get("product_key", "flash_astral")
        cart_items = [{"key": product_key, "quantity": 1}]
    
    logger.info(f"🛒 [PayPal] create-order | panier: {cart_items}")
    
    # Construire les items PayPal
    items_paypal = []
    total_amount = 0.0
    product_keys = []
    currency = os.getenv("PAYPAL_CURRENCY", "EUR")
    
    for item in cart_items:
        pk = item.get("key")
        qty = item.get("quantity", 1)
        
        product = PRODUCTS.get(pk)
        if not product:
            logger.warning(f"⚠️ Produit inconnu ignoré: {pk}")
            continue
        
        product_keys.append(pk)
        price_cents = product.get("price_cents", 0)
        unit_price = price_cents / 100.0
        total_amount += unit_price * qty
        
        items_paypal.append({
            "name": product["label"],
            "description": product["label"],
            "sku": pk,
            "quantity": str(qty),
            "unit_amount": {
                "currency_code": currency,
                "value": f"{unit_price:.2f}"
            }
        })
    
    if not items_paypal:
        return jsonify({"error": "Panier vide"}), 400
    
    # Stocker les produits en session
    session["pending_paypal_products"] = product_keys
    session["cart_items"] = cart_items
    session.modified = True
    
    token, base_url = get_paypal_token()
    
    logger.info(f"💰 [PayPal] Total: {total_amount:.2f} {currency} | Produits: {product_keys}")
    
    # Payload PayPal avec items
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": ",".join(product_keys),  # Concaténation pour référence
            "custom_id": ",".join(product_keys),
            "description": f"Analyses: {', '.join([PRODUCTS[pk]['label'] for pk in product_keys])}",
            "amount": {
                "currency_code": currency,
                "value": f"{total_amount:.2f}",
                "breakdown": {
                    "item_total": {
                        "currency_code": currency,
                        "value": f"{total_amount:.2f}"
                    }
                }
            },
            "items": items_paypal
        }]
    }

    try:
        r = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            json=payload,
            timeout=20,
        )
        
        if r.status_code == 201:
            order_data = r.json()
            order_id = order_data.get('id')
            logger.info(f"✅ [PayPal] Order créé: {order_id} | produits: {product_keys}")
        else:
            logger.error(f"❌ [PayPal] Erreur création: {r.status_code} - {r.text}")
        
        return jsonify(r.json()), r.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [PayPal] Exception create-order: {e}")
        return jsonify({"error": "Erreur PayPal"}), 500

# ─────────────────────────────────────────────────────────────────────────────
# POST /payments/capture-order - MULTI-PRODUITS
# ─────────────────────────────────────────────────────────────────────────────

@payments_bp.route("/payments/capture-order", methods=["POST"])
def capture_order():
    # 🔐 QA bypass
    if is_qa_request():
        return jsonify({"id": "TEST-CAPTURE-QA", "status": "COMPLETED", "qa": True}), 201

    token, base_url = get_paypal_token()
    payload = request.get_json() or {}
    order_id = payload.get("orderID") or payload.get("orderId")
    user_info = payload.get("userInfo")

    # Récupérer les produits depuis la session
    product_keys = session.get("pending_paypal_products") or []
    cart_items = session.get("cart_items") or []
    
    logger.info(f"🎯 [PayPal] capture-order | order_id={order_id} | produits={product_keys}")

    try:
        r = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            timeout=20,
        )
        data = r.json()

        ok = (r.status_code == 201) or (isinstance(data, dict) and data.get("status") == "COMPLETED")
        if not ok:
            logger.error("❌ [PayPal] Capture échouée: %s - %s", r.status_code, data)
            return jsonify(data), r.status_code

        # Montant capturé
        pu = (data.get("purchase_units") or [{}])[0]
        payments_obj = pu.get("payments") or {}
        captures = payments_obj.get("captures") or []
        first_cap = captures[0] if captures else {}
        cap_amount = first_cap.get("amount") or {}

        logger.info(f"✅ [PayPal] Capture OK | order={order_id} | produits={product_keys} | montant={cap_amount}")

        # Purge
        for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at", "pending_paypal_products"):
            session.pop(k, None)

        # Infos utilisateur
        if user_info:
            session["infos_utilisateur"] = {
                'nom': user_info.get('nom'),
                'date_naissance': user_info.get('birthDate'),
                'heure_naissance': user_info.get('birthTime'),
                'lieu_naissance': user_info.get('birthPlace'),
                'email': user_info.get('email'),
                'gender': user_info.get('gender'),
                'lat': user_info.get('lat'),
                'lon': user_info.get('lon'),
                'tzid': user_info.get('tzid'),
            }

        # Marqueurs
        session["last_payment"] = {
            "provider": "paypal",
            "order_id": order_id,
            "items": cart_items,
            "status": "COMPLETED",
            "mode": PAYPAL_MODE,
            "product_keys": product_keys,
            "amount": cap_amount.get("value"),
            "currency": cap_amount.get("currency_code"),
        }
        session["paiement_valide"] = True
        session["paypal_order_id"] = order_id
        session["ordered_products"] = product_keys
        session.modified = True

        logger.info(f"✅ [PayPal] Marqueurs posés | produits={product_keys}")
        return jsonify(data), r.status_code

    except requests.exceptions.RequestException as e:
        logger.error("❌ [PayPal] Exception capture: %s", e)
        return jsonify({"error": "Erreur PayPal"}), 500