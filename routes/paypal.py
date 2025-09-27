import os, requests
from flask import Blueprint, request, jsonify, session
import logging

payments_bp = Blueprint("payments", __name__)
logger = logging.getLogger(__name__)

# def get_paypal_token():
#     mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
#     client_id = os.getenv("PAYPAL_CLIENT_ID_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_ID_SANDBOX")
#     client_secret = os.getenv("PAYPAL_CLIENT_SECRET_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX")
#     base_url = "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"

#     r = requests.post(
#         f"{base_url}/v1/oauth2/token",
#         headers={"Accept": "application/json", "Accept-Language": "en_US"},
#         data={"grant_type": "client_credentials"},
#         auth=(client_id, client_secret)
#     )
#     r.raise_for_status()
#     return r.json()["access_token"], base_url


# 🔐 Helpers QA mode
QA_FLAG_PARAM = "qa"
QA_HEADER = "X-QA"
QA_WHITELIST = {e.strip().lower() for e in os.getenv("QA_WHITELIST_EMAILS", "").split(",") if e.strip()}

def is_qa_request():
    """
    Vérifie si la requête est un test QA.
    Conditions :
      - paramètre ?qa=1 OU header X-QA=1
      - ET email dans la whitelist
    """
    flag = (request.args.get(QA_FLAG_PARAM) == "1") or (request.headers.get(QA_HEADER) == "1")
    if not flag:
        return False

    email = None
    try:
        body = request.get_json(silent=True) or {}
        ui = body.get("userInfo") or {}
        email = (ui.get("email") or "").lower()
    except Exception:
        pass

    if email and email in QA_WHITELIST:
        logger.info("[QA] QA mode enabled for %s", email)
        return True

    logger.info("[QA] QA flag present but email not whitelisted: %r", email)
    return False

def get_paypal_token():
    mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
    if mode not in ("live", "sandbox"):
        mode = "sandbox"

    client_id = os.getenv("PAYPAL_CLIENT_ID_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_ID_SANDBOX")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX")
    base_url = "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"

    logger.info("[PayPal] MODE=%s BASE=%s CID=%s…", mode, base_url, (client_id or "")[:8])

    r = requests.post(
        f"{base_url}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"], base_url

@payments_bp.route("/payments/create-order", methods=["POST"])
def create_order():

    # 🔐 QA bypass: ne parle pas à PayPal, renvoie un order factice
    if is_qa_request():
        fake = {"id": "TEST-ORDER", "status": "CREATED", "qa": True}
        logger.info("[QA] create-order → fake response %s", fake)
        return jsonify(fake), 200
    
    token, base_url = get_paypal_token()
    logger.info("[PayPal] create-order → %s", base_url)

    # 👉 Prix unique pour PayPal & Stripe (env: POINT_ASTRAL_PRICE_CENTS)
    logger.info("[PayPal] ENV POINT_ASTRAL_PRICE_CENTS=%r",
                os.environ.get("POINT_ASTRAL_PRICE_CENTS"))

    amount_cents = int(os.getenv("POINT_ASTRAL_PRICE_CENTS", "2900"))
    amount_eur = f"{amount_cents / 100:.2f}"  # ex: 2900 → "29.00"

    logger.info("[PayPal] amount=%s EUR (src POINT_ASTRAL_PRICE_CENTS=%s)",
                amount_eur, amount_cents)

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": os.getenv("PAYPAL_CURRENCY", "EUR"),
                "value": amount_eur
            }
        }]
    }

    r = requests.post(
        f"{base_url}/v2/checkout/orders",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json=payload,
        timeout=20,
    )
    return jsonify(r.json()), r.status_code

@payments_bp.route("/payments/capture-order", methods=["POST"])
def capture_order():
    token, base_url = get_paypal_token()
    logger.info("[PayPal] capture-order → %s", base_url)
    payload = request.get_json() or {}
    order_id = payload.get("orderID")
    user_info = payload.get("userInfo")
    items = payload.get("items", [])

    r = requests.post(
        f"{base_url}/v2/checkout/orders/{order_id}/capture",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    data = r.json()

    # Si succès → on mémorise en session pour la génération derrière
    try:
        if r.status_code == 201 or (isinstance(data, dict) and data.get("status") == "COMPLETED"):
            # 🔄 Purge anti-reload car nouveau paiement validé
            for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
                session.pop(k, None)
                
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
            session["last_payment"] = {
                "provider": "paypal",
                "order_id": order_id,
                "items": items
            }
    except Exception:
        pass

    return jsonify(data), r.status_code