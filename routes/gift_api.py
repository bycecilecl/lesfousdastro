# routes/gift_api.py

import os
import secrets
from flask import Blueprint, request, jsonify, current_app
from config.gift_codes import (
    get_unused_code_for_product,
    mark_code_as_used,
)
from config.products import PRODUCTS

gift_api_bp = Blueprint("gift_api_bp", __name__, url_prefix="/api/gift")


def _env_on(v):
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


API_TOKEN = os.getenv("GIFT_API_TOKEN", "").strip()


def _check_auth(req: request) -> bool:
    """
    Vérifie que la requête vient bien de WooCommerce :
    - via un header X-API-KEY qui contient le token partagé
    """
    if not API_TOKEN:
        # Sans secret configuré, aucune attribution n’est autorisée.
        current_app.logger.warning("[GIFT_API] Aucun GIFT_API_TOKEN défini → attribution refusée")
        return False

    header_token = (req.headers.get("X-API-KEY") or "").strip()
    if not header_token or not secrets.compare_digest(header_token, API_TOKEN):
        current_app.logger.warning("[GIFT_API] Auth échouée (X-API-KEY incorrect)")
        return False
    return True


@gift_api_bp.route("/allocate", methods=["POST"])
def allocate_gift_code():
    """
    Endpoint appelé par WooCommerce :
    - Body JSON attendu : { "product_key": "flash_astral", "order_id": "...", "email": "..." }
    - Retour : { success, code, product_key, error }
    """

    if not _check_auth(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    product_key = (data.get("product_key") or "").strip()
    order_id_raw = data.get("order_id")
    order_id = str(order_id_raw).strip() if order_id_raw else ""
    email = (data.get("email") or "").strip()

    if not product_key:
        return jsonify({"success": False, "error": "Missing product_key"}), 400

    if product_key not in PRODUCTS:
        return jsonify({"success": False, "error": f"Unknown product_key: {product_key}"}), 400

    if not order_id or len(order_id) > 200:
        return jsonify(error='Identifiant de commande requis'), 400
    from services.gift_grants import allocate
    code = allocate(order_id, product_key)
    return jsonify(success=True, code=code, product_key=product_key, order_id=order_id), 200
