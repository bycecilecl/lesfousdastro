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

    # 🔥 FIX: Aplatir structure imbriquée (packs avec items internes)
    fixed_cart = []
    for item in cart_items:
        if not isinstance(item, dict):
            continue  # sécurité, au cas où

        item_id = item.get("id") or item.get("key")
        if not item_id:
            continue  # on ne garde que ce qui a un id/clé

        if "items" in item and isinstance(item["items"], list):
            # Cas pack WooCommerce-like : on garde juste le pack
            fixed_cart.append({
                "key": item_id,
                "quantity": int(item.get("quantity", 1) or 1)
            })
        else:
            fixed_cart.append({
                "key": item_id,
                "quantity": int(item.get("quantity", 1) or 1)
            })

    cart_items = fixed_cart
    logger.info(f"🔄 [PayPal] Panier aplati: {cart_items}")
    
    # Construire les items PayPal
    items_paypal = []
    total_amount = 0.0
    payment_product_keys = []    # ce qui est facturé (pack + autres)
    analysis_product_keys = []   # ce qui est généré comme analyses
    currency = os.getenv("PAYPAL_CURRENCY", "EUR")
    
    for item in cart_items:
        pk = item.get("key") or item.get("id")
        
        # 🔥 FIX: Forcer qty en int (le front peut envoyer "1" en string)
        qty_raw = item.get("quantity", 1)
        try:
            qty = int(qty_raw)
        except (TypeError, ValueError):
            qty = 1
        
        product = PRODUCTS.get(pk)
        if not product:
            logger.warning(f"⚠️ Produit inconnu ignoré: {pk}")
            continue
        
        price_cents = product.get("price_cents", 0)
        unit_price = price_cents / 100.0
        total_amount += unit_price * qty

        # 👉 côté paiement
        payment_product_keys.append(pk)

        # 👉 côté analyses
        included = product.get("included_products")
        if included:
            for _ in range(qty):
                analysis_product_keys.extend(included)
        else:
            for _ in range(qty):
                analysis_product_keys.append(pk)
        
        # Ligne PayPal visible (Pack ou module)
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
        logger.error("❌ [PayPal] Aucun item PayPal construit (produits inconnus ? panier=%s)", cart_items)
        return jsonify({"error": "Panier vide ou produits inconnus"}), 400

    if "flash_transits" in payment_product_keys and len(payment_product_keys) > 1:
        return jsonify({
            "error": "Le Flash Transits doit être commandé séparément."
        }), 400
    
    # 🔥 FIX: Stocker AUSSI payment_product_keys pour avoir l'info complète
    session["pending_paypal_products"] = analysis_product_keys
    session["pending_payment_keys"] = payment_product_keys  # 👈 AJOUT
    session["cart_items"] = cart_items
    session.modified = True
    
    token, base_url = get_paypal_token()
    
    logger.info(
        f"💰 [PayPal] Total: {total_amount:.2f} {currency} | "
        f"Payés: {payment_product_keys} | Analyses: {analysis_product_keys}"
    )

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": ",".join(payment_product_keys),  
            "custom_id": ",".join(payment_product_keys),     
            "description": (
                f"Analyses: "
                f"{', '.join([PRODUCTS[pk]['label'] for pk in payment_product_keys if pk in PRODUCTS])}"
            ),
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
            # 🔥 FIX: Utiliser les bonnes variables
            logger.info(
                f"✅ [PayPal] Order créé: {order_id} | "
                f"payés: {payment_product_keys} | analyses: {analysis_product_keys}"
            )
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

    # 🔥 FIX: Récupérer les produits depuis la session avec fallback
    product_keys = session.get("pending_paypal_products") or []
    payment_keys = session.get("pending_payment_keys") or []
    cart_items = session.get("cart_items") or []

    # 2️⃣ Purge TOTALE de l'ancienne session
    for k in (
        "ordered_products", "pending_generation", "last_payment",
        "paiement_valide", "paiement_timestamp", "paypal_order_id",
        "clarification_email_sent", "last_pdf_url", "lock_until",
        "last_generation_key", "last_generation_at", "last_fingerprint",
        "last_pdf_url_profil_amoureux", "lock_until_profil_amoureux",
        "last_fingerprint_profil_amoureux",
        "last_pdf_url_forces_defis", "lock_until_forces_defis",
        "last_fingerprint_forces_defis",
        "last_pdf_url_analyse_karmique", "lock_until_analyse_karmique",
        "last_fingerprint_analyse_karmique",
        "infos_utilisateur",
    ):
        session.pop(k, None)

    session.modified = True
    
    # 🔥 DIAGNOSTIC: Logger l'état de la session
    logger.info(
        f"🎯 [PayPal] capture-order | order_id={order_id} | "
        f"analyses={product_keys} | payés={payment_keys} | cart={cart_items}"
    )
    
    if not product_keys:
        logger.error(
            "❌ [PayPal] Session vide ! order_id=%s | "
            "Vérifier: cookies, session timeout, domain", 
            order_id
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

        # Montant capturé
        pu = (data.get("purchase_units") or [{}])[0]
        payments_obj = pu.get("payments") or {}
        captures = payments_obj.get("captures") or []
        first_cap = captures[0] if captures else {}
        cap_amount = first_cap.get("amount") or {}

        logger.info(
            f"✅ [PayPal] Capture OK | order={order_id} | "
            f"analyses={product_keys} | montant={cap_amount}"
        )

        # Purge anciens marqueurs
        for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
            session.pop(k, None)

        # Infos utilisateur
        if user_info:
            session["infos_utilisateur"] = {
                'nom': user_info.get('nom'),
                'date_naissance': user_info.get('birthDate'),
                'heure_naissance': user_info.get('birthTime'),
                'lieu_naissance': user_info.get('birthPlace'),
                'email': user_info.get('email'),
                'gender': user_info.get('gender') or user_info.get('genre') or user_info.get('sex') or '',
                'lat': user_info.get('lat'),
                'lon': user_info.get('lon'),
                'tzid': user_info.get('tzid'),
                'transit_date_mode': user_info.get('transitDateMode') or 'today',
                'transit_date': user_info.get('transitDate') or '',
            }

        # 🔥 FIX: Marqueurs avec info complète
        session["last_payment"] = {
            "provider": "paypal",
            "order_id": order_id,
            "items": cart_items,
            "status": "COMPLETED",
            "mode": PAYPAL_MODE,
            "product_keys": product_keys,  # analyses à générer
            "payment_keys": payment_keys,  # ce qui a été payé
            "amount": cap_amount.get("value"),
            "currency": cap_amount.get("currency_code"),
        }
        session["paiement_valide"] = True
        session["paypal_order_id"] = order_id
        session["ordered_products"] = product_keys  # 👈 Ce que le backend doit générer
        session.modified = True

        # 🔥 FIX: Supprimer les pending_ APRÈS avoir tout stocké
        session.pop("pending_paypal_products", None)
        session.pop("pending_payment_keys", None)
        session.modified = True

        logger.info(
            f"✅ [PayPal] Marqueurs posés | ordered_products={product_keys} | "
            f"paiement_valide=True"
        )
        
        return jsonify(data), r.status_code

    except requests.exceptions.RequestException as e:
        logger.error("❌ [PayPal] Exception capture: %s", e)
        return jsonify({"error": "Erreur PayPal"}), 500
