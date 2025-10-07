# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp
# Rôle : Stripe checkout + atterrissage succès (pose des marqueurs en session)
# ─────────────────────────────────────────────────────────────────────────────

import os, uuid
from datetime import datetime
import stripe
from flask import Blueprint, request, session, redirect, url_for, render_template, abort, current_app
from config.products import PRODUCTS

checkout_bp = Blueprint("checkout_bp", __name__)

# Config Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()

def env_bool(name: str, default=False) -> bool:
    val = (os.getenv(name, "1" if default else "0") or "").strip().lower()
    return val in ("1", "true", "yes", "on")

# ─────────────────────────────────────────────────────────────────────────────
# POST /checkout : crée une Session Stripe et redirige vers Hosted Checkout
# ─────────────────────────────────────────────────────────────────────────────
@checkout_bp.route("/checkout", methods=["POST"])
def checkout():
    # 1) Infos utilisateur
    session['infos_utilisateur'] = {
        "nom":  request.form.get("nom"),
        "email": request.form.get("email"),
        "gender": request.form.get("gender"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance"),
        "lat": (request.form.get("lat") or "").strip(),
        "lon": (request.form.get("lon") or "").strip(),
        "tzid": (request.form.get("tzid") or "").strip(),
    }

    # 2) Produit choisi — obligatoire
    product_key = (request.form.get("product_key") or "").strip()
    if not product_key:
        current_app.logger.warning("[CHECKOUT] product_key manquant")
        abort(400, description="Produit non spécifié.")
    product = PRODUCTS.get(product_key)
    if not product:
        current_app.logger.warning("[CHECKOUT] product_key inconnu: %s", product_key)
        abort(400, description="Produit non reconnu.")

    # 3) Prix
    price_cents = product.get("price_cents") or 0
    price_id = (product.get("price_id") or "").strip()

    if price_id:
        line_items = [{'price': price_id, 'quantity': 1}]
    else:
        line_items = [{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': product["label"]},
                'unit_amount': price_cents,
            },
            'quantity': 1,
        }]

    # 4) Créer la session Stripe
    checkout_session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=line_items,
        success_url=url_for('checkout_bp.paiement_effectue', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('main.index', _external=True),
        metadata={
            "product_key": product_key,
            "email": session['infos_utilisateur'].get('email', ''),
        },
        client_reference_id=(session['infos_utilisateur'].get('email') or str(uuid.uuid4()))
    )

    session["selected_product"] = product_key
    return redirect(checkout_session.url, code=303)

# ─────────────────────────────────────────────────────────────────────────────
# GET /paiement-effectue : vérifie la session Stripe et POSE les marqueurs
# ─────────────────────────────────────────────────────────────────────────────
@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    session_id = request.args.get('session_id')
    if not session_id:
        return render_template('paiement_effectue_problem.html',
                               message="Session paiement manquante."), 400

    try:
        s = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        current_app.logger.exception("[PAIEMENT] retrieve session fail: %s", e)
        return render_template('paiement_effectue_problem.html',
                               message="Impossible de vérifier le paiement."), 400

    if s.get("payment_status") != "paid":
        return render_template('paiement_effectue_problem.html',
                               message="Paiement non confirmé."), 402

    product_key = (s.get('metadata') or {}).get('product_key')
    product = PRODUCTS.get(product_key or "")
    if not product:
        return render_template('paiement_effectue_problem.html',
                               message="Produit inconnu après paiement."), 400

    # ✅ Marqueurs de paiement (lus ensuite par point_astral_blocs)
    session["last_payment"] = {
        "provider": "stripe",
        "session_id": session_id,
        "status": s.get("payment_status"),
        "amount_total": s.get("amount_total"),
        "currency": s.get("currency"),
        "created": s.get("created"),
        "product_key": product_key,
    }
    session["selected_product"] = product_key
    session["stripe_session_id"] = session_id
    session["paiement_valide"] = True
    session["paiement_timestamp"] = datetime.utcnow().isoformat()
    session.modified = True

    # Où aller ensuite
    try:
        next_url = url_for(product["success_route"])
    except Exception:
        next_url = "/forces_defis/complet" if product_key == "forces_defis" else "/point_astral_blocs/complet"

    # Anti-reload : purge d’anciennes clés de génération
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    return render_template('paiement_effectue.html',
                           next_url=next_url,
                           produit_titre=product["label"])