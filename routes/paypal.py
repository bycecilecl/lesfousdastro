import os, requests
from flask import Blueprint, request, jsonify, session

payments_bp = Blueprint("payments", __name__)

def get_paypal_token():
    mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
    client_id = os.getenv("PAYPAL_CLIENT_ID_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_ID_SANDBOX")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET_LIVE") if mode == "live" else os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX")
    base_url = "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"

    r = requests.post(
        f"{base_url}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret)
    )
    r.raise_for_status()
    return r.json()["access_token"], base_url

@payments_bp.route("/payments/create-order", methods=["POST"])
def create_order():
    token, base_url = get_paypal_token()
    r = requests.post(
        f"{base_url}/v2/checkout/orders",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": os.getenv("PAYPAL_CURRENCY", "EUR"),
                    "value": os.getenv("POINT_ASTRAL_PRICE", "29.00")
                }
            }]
        }
    )
    return jsonify(r.json()), r.status_code

@payments_bp.route("/payments/capture-order", methods=["POST"])
def capture_order():
    token, base_url = get_paypal_token()
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