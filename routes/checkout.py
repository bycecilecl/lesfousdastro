# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp
# Rôle : gère le paiement Stripe pour le "Flash Astral complet".
# Dépendances :
#   - STRIPE_SECRET_KEY (env) : clé secrète Stripe (compte live ou test)
#   - flask.session : stocke les infos utilisateur avant redirection vers Stripe
#   - url_for(...)  : URLs absolues (_external=True) exigées par Stripe
# Remarques :
#   - Le prix est en centimes d’euro (ici 3500 = 35,00 €).
#   - Pas de webhook ici : la confirmation s’appuie sur l’URL de succès.
#     (à sécuriser avec un webhook Stripe en prod)
# ─────────────────────────────────────────────────────────────────────────────

import os, uuid
import stripe
from flask import Blueprint, request, session, redirect, url_for, render_template, abort, current_app
from config.products import PRODUCTS  # ⬅️ nouveau

# 🧪─────────────────────────────────────────────
# Mode sandbox / production pour Stripe
# ───────────────────────────────────────────────
def _env_bool(name, default="off"):
    return (os.getenv(name, default) or "").strip().lower() in {"1","true","on","yes"}

PAYMENTS_SANDBOX = _env_bool("PAYMENTS_SANDBOX", "off")
APP_MAINT = _env_bool("APP_MAINTENANCE", "off")

# 🔒 Sécurité : pas de sandbox si le site est public
if PAYMENTS_SANDBOX and not APP_MAINT:
    raise RuntimeError("PAYMENTS_SANDBOX=on alors que APP_MAINTENANCE=off — active la maintenance ou désactive le sandbox.")

# 🔑 Sélection automatique de la bonne clé Stripe
STRIPE_SECRET_KEY = (
    os.getenv("STRIPE_SECRET_KEY_TEST")
    if PAYMENTS_SANDBOX
    else os.getenv("STRIPE_SECRET_KEY")  # ta clé live actuelle
)

if not STRIPE_SECRET_KEY:
    raise RuntimeError("❌ Aucune clé Stripe valide trouvée (test ou live).")

stripe.api_key = STRIPE_SECRET_KEY
print(f"[Stripe] Mode = {'SANDBOX TEST' if PAYMENTS_SANDBOX else 'LIVE'} | Clé utilisée = {STRIPE_SECRET_KEY[:8]}…")
# 🧪─────────────────────────────────────────────

checkout_bp = Blueprint("checkout_bp", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE : POST /checkout
# Rôle : crée une Session de paiement Stripe et redirige l’utilisateur
#        vers la page de paiement hébergée par Stripe.
# Entrées (form-data) :
#   - nom, email, date_naissance, heure_naissance, lieu_naissance
# Effets :
#   - Stocke ces infos dans flask.session['infos_utilisateur'] pour les réutiliser
#     après paiement (génération du Flash Astral).
#   - Crée stripe.checkout.Session avec 1 ligne "Flash Astral complet" à 35 €.
#   - Redirige (303) vers checkout_session.url (Stripe Hosted Checkout).
# URLs :
#   - success_url → checkout_bp.paiement_effectue (confirmation locale)
#   - cancel_url  → formulaire (retour au formulaire si annulation)
# À savoir :
#   - Les montants sont en centimes.
#   - Pense à passer en mode live + clé live en production.
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route("/checkout", methods=["POST"])
def checkout():
    # 1) Infos utilisateur (inchangé)
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

    # 2) Produit choisi — OBLIGATOIRE et VALIDE
    product_key = (request.form.get("product_key") or "").strip()
    if not product_key:
        current_app.logger.warning("[CHECKOUT] product_key manquant")
        abort(400, description="Produit non spécifié.")
    product = PRODUCTS.get(product_key)
    if not product:
        current_app.logger.warning("[CHECKOUT] product_key inconnu: %s", product_key)
        abort(400, description="Produit non reconnu.")

    # 3) Sécurité “prix test” (si tu gardes la possibilité de unit_amount)
    price_cents = product.get("price_cents") or 0
    if price_cents and price_cents < 500 and (os.getenv("APP_MAINTENANCE","off").strip().lower() != "on"):
        abort(403)  # empêche 1€ en public

    # 4) Construire line_items selon Price ID ou unit_amount
    price_id = product.get("price_id")
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

    # 5) Créer la session Stripe (toujours avec metadata.product_key)
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

    # Mémorise côté session (utile mais pas source de vérité)
    session["selected_product"] = product_key
    return redirect(checkout_session.url, code=303)

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE : GET /paiement-effectue
# Rôle : point d’atterrissage après succès Stripe.
# Effets :
#   - Redirige vers point_astral.afficher_point_astral
#     (qui lira session['infos_utilisateur'], calculera le thème,
#      générera le Flash Astral et l’enverra).
# Remarques :
#   - Sans webhook, cette confirmation repose uniquement sur la redirection
#     Stripe : pour une validation anti-fraude/anti-recharge, implémente
#     un webhook (event "checkout.session.completed") côté serveur.
# ─────────────────────────────────────────────────────────────────────────────



@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    session_id = request.args.get('session_id')
    if not session_id:
        return render_template('paiement_effectue_problem.html', message="Session paiement manquante."), 400

    try:
        s = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        current_app.logger.exception("[PAIEMENT] retrieve session fail: %s", e)
        return render_template('paiement_effectue_problem.html', message="Impossible de vérifier le paiement."), 400

    if s.get("payment_status") != "paid":
        return render_template('paiement_effectue_problem.html', message="Paiement non confirmé."), 402

    product_key = s.get('metadata', {}).get('product_key')
    product = PRODUCTS.get(product_key or "")
    if not product:
        return render_template('paiement_effectue_problem.html', message="Produit inconnu après paiement."), 400

    # Construire la destination
    try:
        next_url = url_for(product["success_route"])
    except Exception:
        # fallback safe si endpoint renommé
        next_url = "/forces_defis/complet" if product_key == "forces_defis" else "/point_astral_blocs/complet"

    # Purge anti-reload
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    return render_template('paiement_effectue.html',
                           next_url=next_url, produit_titre=product["label"])