# routes/gift_codes.py

from flask import Blueprint, render_template, request, redirect, session, current_app, url_for
from config.gift_codes import get_gift_code, is_code_used, mark_code_as_used
from config.products import PRODUCTS

gift_bp = Blueprint("gift_bp", __name__, url_prefix="/carte-cadeau")


@gift_bp.route("/", methods=["GET"])
def entrer_code_cadeau():
    return render_template("carte_cadeau_form.html")


@gift_bp.route("/valider", methods=["POST"])
def valider_code_cadeau():
    code = (request.form.get("code") or "").strip().upper()

    if not code:
        return render_template("carte_cadeau_form.html",
                               error="Merci d’entrer un code.")

    # 1️⃣ Lire le code dans la base CSV
    gift = get_gift_code(code)
    if not gift:
        return render_template("carte_cadeau_form.html",
                            error="Code invalide ou inconnu.")

    # Vérifier si déjà utilisé
    if is_code_used(gift):
        return render_template("carte_cadeau_form.html",
                            error="Ce code a déjà été utilisé.")

    product_key = gift.get("product_key")

    # 2️⃣ Vérifier produit valide
    if product_key not in PRODUCTS:
        return render_template("carte_cadeau_form.html",
                               error="Ce code correspond à un produit inconnu.")

    # 4️⃣ Sauvegarder infos utilisateur (comme dans /checkout)
    session['infos_utilisateur'] = {
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

    # 5️⃣ Déterminer les analyses à générer
    product_conf = PRODUCTS[product_key]
    included = product_conf.get("included_products")

    if included:
        # Exemple : pack_essence → flash_astral + forces_defis + profil_amoureux
        products_to_generate = included
    else:
        # Exemple : flash_astral seul, profil_amoureux seul
        products_to_generate = [product_key]

    # 6️⃣ Marquer en session comme un paiement validé
    session["gift_code"] = code
    session["gift_product"] = product_key
    session["paiement_valide"] = True
    session["ordered_products"] = products_to_generate
    session["pending_generation"] = {
        "products": products_to_generate,
        "provider": "gift_code",
        "code": code,
    }
    session.modified = True

    # 7️⃣ Marquer le code comme utilisé
    mark_code_as_used(code)

    # 8️⃣ On passe par le même flux que Stripe/PayPal
    return redirect(url_for("checkout_bp.traiter_analyses"))