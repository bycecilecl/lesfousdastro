import os
import requests
from flask import Blueprint, request, jsonify, session, current_app
import logging
from requests.auth import HTTPBasicAuth


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
    # ✅ MÊME logique que main.py et Stripe
    def _env_on(v):
        return (v or "").strip().lower() in ("1", "true", "on", "yes")
    
    payments_sandbox = _env_on(os.getenv("PAYMENTS_SANDBOX"))
    app_maint = _env_on(os.getenv("APP_MAINTENANCE"))
    
    # PayPal sandbox SEULEMENT si PAYMENTS_SANDBOX=on ET APP_MAINTENANCE=on
    use_sandbox = payments_sandbox and app_maint
    
    base_url = "https://api-m.sandbox.paypal.com" if use_sandbox else "https://api-m.paypal.com"

    # ✅ Choix des credentials selon le mode calculé
    if use_sandbox:
        client_id = os.getenv("PAYPAL_CLIENT_ID_SANDBOX", "").strip()
        secret = os.getenv("PAYPAL_SECRET_SANDBOX", "").strip()
    else:
        client_id = (
            os.getenv("PAYPAL_CLIENT_ID_LIVE") or 
            os.getenv("PAYPAL_CLIENT_ID") or 
            ""
        ).strip()
        secret = (
            os.getenv("PAYPAL_SECRET_LIVE") or 
            os.getenv("PAYPAL_SECRET") or 
            ""
        ).strip()

    # Log non sensible
    current_app.logger.info(
        "🔑 [PayPal] Token request | mode=%s | PAYMENTS_SANDBOX=%s | APP_MAINTENANCE=%s | base=%s | client_id=%s… | secret_set=%s",
        "sandbox" if use_sandbox else "live",
        payments_sandbox,
        app_maint,
        base_url,
        (client_id or "")[:8],
        bool(secret)
    )

    if not client_id or not secret:
        raise RuntimeError(
            f"PAYPAL credentials manquants pour mode={'sandbox' if use_sandbox else 'live'}. "
            f"Vérifie PAYPAL_CLIENT_ID_{'SANDBOX' if use_sandbox else 'LIVE'} et PAYPAL_SECRET_{'SANDBOX' if use_sandbox else 'LIVE'}"
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
# POST /payments/create-order
# ─────────────────────────────────────────────────────────────────────────────

@payments_bp.route("/payments/create-order", methods=["POST"])
def create_order():
    # 🔐 QA bypass
    if is_qa_request():
        return jsonify({"id": "TEST-ORDER-QA", "status": "CREATED", "qa": True}), 200
    
    # ✅ Récupérer product_key depuis le frontend
    payload_in = request.get_json() or {}
    product_key = payload_in.get("product_key", "flash_astral")  # fallback
    
    token, base_url = get_paypal_token()
    
    # 💰 Prix depuis env (cohérence avec Stripe)
    amount_cents = int(os.getenv("POINT_ASTRAL_PRICE_CENTS", "2900"))
    amount_eur = f"{amount_cents / 100:.2f}"
    currency = os.getenv("PAYPAL_CURRENCY", "EUR")

    logger.info(f"📦 [PayPal] create-order | mode={PAYPAL_MODE} | product={product_key} | amount={amount_eur} {currency}")

    # ✅ Payload avec product_key propagé
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": product_key,      # ✅ récupérable après capture
            "custom_id": product_key,         # ✅ alternative
            "description": f"Analyse {product_key}",
            "amount": {
                "currency_code": currency,
                "value": amount_eur
            }
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
            logger.info(f"✅ [PayPal] Order créé: {r.json().get('id')}")
        else:
            logger.error(f"❌ [PayPal] Erreur création: {r.status_code} - {r.text}")
        
        return jsonify(r.json()), r.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [PayPal] Exception create-order: {e}")
        return jsonify({"error": "Erreur PayPal"}), 500

# ─────────────────────────────────────────────────────────────────────────────
# POST /payments/capture-order
# ─────────────────────────────────────────────────────────────────────────────

@payments_bp.route("/payments/capture-order", methods=["POST"])
def capture_order():
    # 🔐 QA bypass
    if is_qa_request():
        return jsonify({"id": "TEST-CAPTURE-QA", "status": "COMPLETED", "qa": True}), 201
    
    token, base_url = get_paypal_token()
    payload = request.get_json() or {}
    order_id = payload.get("orderID")
    user_info = payload.get("userInfo")
    product_key = payload.get("product_key", "flash_astral")
    items = payload.get("items", [])

    # ✅ Log avec mode
    logger.info(f"🎯 [PayPal] capture-order | order_id={order_id} | mode={PAYPAL_MODE}")

    try:
        r = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            timeout=20,
        )
        data = r.json()

        # ✅ Si succès
        if r.status_code == 201 or (isinstance(data, dict) and data.get("status") == "COMPLETED"):
            
            # ✅ Récupérer product_key depuis la réponse PayPal
            pu = (data.get("purchase_units") or [{}])[0]
            product_key = pu.get("custom_id") or pu.get("reference_id") or "flash_astral"
            amount = pu.get("amount", {})
            
            logger.info(f"✅ [PayPal] Paiement capturé | order_id={order_id} | product={product_key}")
            
            # 🔄 Purge anti-reload
            for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
                session.pop(k, None)
            
            # 📝 Infos utilisateur
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
            
            # ✅ ✅ ✅ MARQUEURS DE PAIEMENT (comme Stripe) ✅ ✅ ✅
            session["last_payment"] = {
                "provider": "paypal",
                "order_id": order_id,
                "items": items,
                "status": "COMPLETED",
                "mode": PAYPAL_MODE,
                "product_key": product_key,        # ✅ depuis la réponse
                "amount": amount.get("value"),     # ✅ montant
                "currency": amount.get("currency_code"),  # ✅ devise
            }
            session["paiement_valide"] = True
            session["paypal_order_id"] = order_id
            session["selected_product"] = product_key  # ✅ plus de hardcode
            session.modified = True
            
            logger.info(f"✅ [PayPal] Marqueurs posés | product={product_key} | mode={PAYPAL_MODE}")
        else:
            logger.error(f"❌ [PayPal] Capture échouée: {r.status_code} - {data}")

        return jsonify(data), r.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [PayPal] Exception capture: {e}")
        return jsonify({"error": "Erreur PayPal"}), 500