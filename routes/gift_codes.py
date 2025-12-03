import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app

from config.products import PRODUCTS
from config.gift_codes import get_gift_code   # <<< IMPORT
# Plus besoin de GIFT_CODES_STATIC ici

gift_bp = Blueprint("gift_bp", __name__)
logger = logging.getLogger(__name__)


def expand_to_analysis_products(raw_product_keys):
    """
    Transforme ["pack_essence"] en ["flash_astral", "forces_defis", "analyse_amour"]
    en se basant sur included_products du store PRODUCTS.
    """
    analysis_keys = []

    for pk in raw_product_keys:
        product = PRODUCTS.get(pk)
        if not product:
            current_app.logger.warning(f"⚠️ [GIFT] Produit inconnu: {pk}")
            continue

        included = product.get("included_products")
        if included:
            analysis_keys.extend(included)
        else:
            analysis_keys.append(pk)

    return analysis_keys


@gift_bp.route("/code-cadeau", methods=["GET"])
def code_cadeau_form():
    return render_template("code_cadeau.html")


@gift_bp.route("/code-cadeau", methods=["POST"])
def code_cadeau_submit():
    code = (request.form.get("code") or "").strip().upper()

    if not code:
        return render_template("code_cadeau.html", error="Merci d’entrer un code cadeau.")

    # 👉 Recherche du code dans STATIC + JSON dynamique
    gift = get_gift_code(code)

    if not gift or not gift.get("active", True):
        logger.warning(f"❌ [GIFT] Code invalide: {code}")
        return render_template(
            "code_cadeau.html",
            error="Ce code est invalide ou expiré.",
            form=request.form
        )

    # Récupération infos utilisateur
    infos = {
        "nom": request.form.get("nom"),
        "email": request.form.get("email"),
        "gender": request.form.get("gender"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance"),
        "lat": (request.form.get("lat") or "").strip(),
        "lon": (request.form.get("lon") or "").strip(),
        "tzid": (request.form.get("tzid") or "").strip(),
    }

    session["infos_utilisateur"] = infos

    raw_products = gift.get("products") or []
    analyses = expand_to_analysis_products(raw_products)

    if not analyses:
        logger.error(f"❌ [GIFT] Aucun produit analysable pour code {code}")
        return render_template(
            "code_cadeau.html",
            error="Ce code ne permet pas de générer une analyse.",
            form=request.form
        )

    logger.info(f"🎁 [GIFT] Code utilisé={code} → analyses={analyses}")

    # On prépare la génération EXACTEMENT comme un paiement réussi
    session["ordered_products"] = analyses
    session["paiement_valide"] = True
    session["pending_generation"] = {
        "products": analyses,
        "provider": "gift",
        "gift_code": code,
    }
    session.modified = True

    # Supprimer anciens locks
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    return redirect(url_for("checkout_bp.traiter_analyses"))