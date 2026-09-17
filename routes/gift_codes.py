# routes/gift_codes.py

from flask import Blueprint, render_template, request, redirect, session, url_for
from config.gift_codes import get_gift_code, is_code_used
from config.products import PRODUCTS

gift_bp = Blueprint("gift_bp", __name__, url_prefix="/carte-cadeau")


# ---------- FORMULAIRE ----------
@gift_bp.route("/", methods=["GET"])
def entrer_code_cadeau():
    return render_template("carte_cadeau_form.html")


# ---------- TRAITEMENT DU CODE + GÉNÉRATION ----------
@gift_bp.route("/valider", methods=["POST"])
def valider_code_cadeau():
    code = (request.form.get("code") or "").strip().upper()

    if not code:
        return render_template("carte_cadeau_form.html",
                               error="Merci d’entrer un code.")

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

    from services.analysis_orders import redeem_gift, restore_order
    order = redeem_gift(code, session['infos_utilisateur'])
    restore_order(order)

    # 8️⃣ On passe par le même flux que Stripe/PayPal
    return redirect(url_for("checkout_bp.traiter_analyses"))


# ---------- CARTE CADEAU IMPRIMABLE ----------
@gift_bp.route("/carte/<code>", methods=["GET"])
def afficher_carte_cadeau(code):
    from flask import current_app
    

    
    code = (code or "").strip().upper()
    gift = get_gift_code(code)
    

    
    if not gift:

        return render_template("carte_cadeau_invalide.html", code=code), 404

    product_key = gift.get("product_key")
    product = PRODUCTS.get(product_key, {})
    product_label = product.get("label", product_key)
    

    
    result = render_template(
        "carte_cadeau_print.html",
        code=code,
        product_label=product_label,
    )
    
    current_app.logger.info(f"🎁 Template rendu, longueur = {len(result)} caractères")
    
    return result