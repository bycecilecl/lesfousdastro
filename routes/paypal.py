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
        secret = os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX", "").strip()  # ✅ BON NOM
    else:
        client_id = (
            os.getenv("PAYPAL_CLIENT_ID_LIVE") or 
            os.getenv("PAYPAL_CLIENT_ID") or 
            ""
        ).strip()
        secret = (
            os.getenv("PAYPAL_CLIENT_SECRET_LIVE") or  # ✅ BON NOM
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
            f"Vérifie PAYPAL_CLIENT_ID_{'SANDBOX' if use_sandbox else 'LIVE'} et PAYPAL_CLIENT_SECRET_{'SANDBOX' if use_sandbox else 'LIVE'}"
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
    
    # ✅ STOCKER dans la session pour le récupérer au capture
    session["pending_paypal_product"] = product_key
    session.modified = True
    
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
            },
            # 👇 Ajout: items pour tracer le produit côté PayPal
            "items": [{
                "name": product_key,
                "description": product_key,
                "sku": product_key,
                "quantity": "1",
                "unit_amount": {
                    "currency_code": currency,
                    "value": amount_eur
                }
            }]
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
            logger.info(f"✅ [PayPal] Order créé: {order_id} | product={product_key}")
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
    items = payload.get("items", [])

    # ⚙️ Produits autorisés (adapte si besoin)
    KNOWN_PRODUCTS = {"flash_astral", "forces_defis", "point_astral"}

    # 1) Source prioritaire: ce qu’on sait côté app
    product_key = (
        session.get("pending_paypal_product")        # posé dans create_order
        or payload.get("product_key")
        or session.get("selected_product")
        or ""
    )

    # 2) Si la valeur app n'est pas valide, on essaie depuis PayPal
    #    (mais JAMAIS "default")
    def pick_from_paypal(order_json: dict) -> str | None:
        pu = (order_json.get("purchase_units") or [{}])[0]
        # PayPal peut renvoyer ces champs… ou pas
        c = pu.get("custom_id")
        r = pu.get("reference_id")
        # Parfois dispo dans items[0]
        items_pp = pu.get("items") or []
        i0 = items_pp[0] if items_pp else {}
        sku = i0.get("sku")
        name = i0.get("name")
        for cand in (c, r, sku, name):
            if cand and cand in KNOWN_PRODUCTS and cand != "default":
                return cand
        return None

    logger.info(
        "🎯 [PayPal] capture-order | order_id=%s | mode=%s | product_from_app=%s",
        order_id, PAYPAL_MODE, product_key
    )

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

        # 3) Décision finale du product_key
        paypal_key = pick_from_paypal(data)
        logger.info("🔎 [PayPal] paypal_key=%s | app_key=%s", paypal_key, product_key)

        if product_key in KNOWN_PRODUCTS:
            # On garde la clé session/front. On ignore 'default' venant de PayPal.
            final_product = product_key
            logger.info("✅ [PayPal] Clé conservée depuis app: %s", final_product)
        elif paypal_key:
            final_product = paypal_key
            logger.info("✅ [PayPal] Clé prise depuis PayPal: %s", final_product)
        else:
            final_product = "flash_astral"
            logger.warning("⚠️ [PayPal] Aucune clé fiable -> fallback: %s", final_product)

        # 4) Montant réel depuis la capture
        pu = (data.get("purchase_units") or [{}])[0]
        payments_obj = pu.get("payments") or {}
        captures = payments_obj.get("captures") or []
        first_cap = captures[0] if captures else {}
        cap_amount = first_cap.get("amount") or {}

        logger.info(
            "✅ [PayPal] Paiement capturé | order_id=%s | product=%s | amount=%s",
            order_id, final_product, cap_amount
        )

        # 5) Purge anti-reload
        for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at", "pending_paypal_product"):
            session.pop(k, None)

        # 6) Infos utilisateur
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

        # 7) Marqueurs de paiement
        session["last_payment"] = {
            "provider": "paypal",
            "order_id": order_id,
            "items": items,
            "status": "COMPLETED",
            "mode": PAYPAL_MODE,
            "product_key": final_product,
            "amount": cap_amount.get("value"),
            "currency": cap_amount.get("currency_code"),
        }
        session["paiement_valide"] = True
        session["paypal_order_id"] = order_id
        session["selected_product"] = final_product
        session.modified = True

        logger.info("✅ [PayPal] Marqueurs posés | product=%s | mode=%s", final_product, PAYPAL_MODE)
        return jsonify(data), r.status_code

    except requests.exceptions.RequestException as e:
        logger.error("❌ [PayPal] Exception capture: %s", e)
        return jsonify({"error": "Erreur PayPal"}), 500