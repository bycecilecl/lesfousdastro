# routes/gift_codes.py

import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app

from config.products import PRODUCTS
from config.gift_codes import GIFT_CODES

gift_bp = Blueprint("gift_bp", __name__)
logger = logging.getLogger(__name__)


def expand_to_analysis_products(raw_product_keys):
    """
    Prend une liste de product_keys (ex: ["pack_essence"])
    et la transforme en liste d'analyses réelles à générer
    (ex: ["flash_astral", "forces_defis", "analyse_amour"]).
    On réutilise la même logique que checkout/payments.
    """
    analysis_keys = []

    for pk in raw_product_keys:
        product = PRODUCTS.get(pk)
        if not product:
            current_app.logger.warning(f"⚠️ [GIFT] Produit inconnu ignoré: {pk}")
            continue

        included = product.get("included_products")
        if included:
            # pack -> on déroule
            analysis_keys.extend(included)
        else:
            analysis_keys.append(pk)

    # Optionnel : dédoublonner si tu veux éviter 2x la même analyse
    # analysis_keys = list(dict.fromkeys(analysis_keys))

    return analysis_keys


@gift_bp.route("/code-cadeau", methods=["GET"])
def code_cadeau_form():
    """
    Affiche le formulaire permettant d'entrer un code cadeau
    + les infos de naissance.
    """
    return render_template("code_cadeau.html")


@gift_bp.route("/code-cadeau", methods=["POST"])
def code_cadeau_submit():
    """
    Vérifie le code cadeau, prépare les analyses (sans paiement)
    puis redirige vers /traiter-analyses qui va générer les PDF.
    """
    code = (request.form.get("code") or "").strip().upper()

    if not code:
        return render_template(
            "code_cadeau.html",
            error="Merci de renseigner un code cadeau.",
            form=request.form
        )

    gift = GIFT_CODES.get(code)
    if not gift or not gift.get("active", True):
        logger.warning(f"❌ [GIFT] Code invalide ou inactif: {code}")
        return render_template(
            "code_cadeau.html",
            error="Ce code cadeau est invalide ou expiré.",
            form=request.form
        )

    # Récupérer les infos utilisateur depuis le formulaire
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

    # Stocker comme pour le checkout classique
    session["infos_utilisateur"] = infos

    # Produits bruts associés au code (peut contenir pack_essence)
    raw_products = gift.get("products") or []
    analyses = expand_to_analysis_products(raw_products)

    if not analyses:
        logger.error(f"❌ [GIFT] Aucun produit analysable pour code: {code}")
        return render_template(
            "code_cadeau.html",
            error="Ce code ne permet pas de générer d'analyse pour le moment.",
            form=request.form
        )

    logger.info(f"✅ [GIFT] Code {code} -> produits={raw_products} -> analyses={analyses}")

    # Poser les mêmes marqueurs que après un paiement
    session["ordered_products"] = analyses
    session["paiement_valide"] = True
    session["pending_generation"] = {
        "products": analyses,
        "provider": "gift",
        "gift_code": code,
    }
    session.modified = True

    # Purger d'éventuels anciens locks
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    # On réutilise EXACTEMENT la même route que pour Stripe/PayPal
    return redirect(url_for("checkout_bp.traiter_analyses"))