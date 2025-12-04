# routes/gift_api.py

import os
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
        # Si pas de token défini, on loggue un warning mais on autorise (pour tests)
        current_app.logger.warning("[GIFT_API] Aucun GIFT_API_TOKEN défini → API non protégée")
        return True

    header_token = (req.headers.get("X-API-KEY") or "").strip()
    if not header_token or header_token != API_TOKEN:
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
    order_id = (data.get("order_id") or "").strip()
    email = (data.get("email") or "").strip()

    if not product_key:
        return jsonify({"success": False, "error": "Missing product_key"}), 400

    if product_key not in PRODUCTS:
        return jsonify({"success": False, "error": f"Unknown product_key: {product_key}"}), 400

    # Chercher un code non utilisé pour ce produit
    row = get_unused_code_for_product(product_key)
    if not row:
        current_app.logger.error(f"[GIFT_API] Plus aucun code dispo pour {product_key}")
        return jsonify({
            "success": False,
            "error": f"No available gift code for {product_key}"
        }), 409

    code = row["code"].strip()
    current_app.logger.info(
        f"[GIFT_API] Attribution code {code} pour produit {product_key} "
        f"(order={order_id}, email={email})"
    )

    # Marquer le code comme utilisé
    try:
        mark_code_as_used(code)
    except Exception as e:
        current_app.logger.exception(f"[GIFT_API] Erreur mark_code_as_used({code}): {e}")
        return jsonify({
            "success": False,
            "error": "Internal error when marking code as used"
        }), 500

    # Réponse JSON que WooCommerce pourra utiliser dans ses e-mails
    return jsonify({
        "success": True,
        "code": code,
        "product_key": product_key,
        "order_id": order_id,
        "email": email,
    }), 200