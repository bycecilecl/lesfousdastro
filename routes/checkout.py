# routes/checkout.py
# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp — Stripe checkout + succès (pose des marqueurs)
# ─────────────────────────────────────────────────────────────────────────────

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template, abort, current_app
from config.products import PRODUCTS
import stripe

checkout_bp = Blueprint("checkout_bp", __name__)
# ✅ Détection du mode Sandbox global (pour Stripe)
def _env_on(v): 
    return (v or "").strip().lower() in ("1", "true", "on", "yes")

PAYMENTS_SANDBOX = _env_on(os.getenv("PAYMENTS_SANDBOX"))

# ─────────────────────────────────────────────────────────────────────────────
# ⚙️ CONFIGURATION STRIPE : Sélection automatique TEST/LIVE
# ─────────────────────────────────────────────────────────────────────────────

def _env_on(v: str | None) -> bool:
    """Convertit une variable d'environnement en booléen."""
    return (v or "").strip().lower() in ("1", "true", "on", "yes")

PAYMENTS_SANDBOX = _env_on(os.getenv("PAYMENTS_SANDBOX"))
APP_MAINTENANCE = _env_on(os.getenv("APP_MAINTENANCE"))

# 🔒 Sécurité : Désactiver sandbox si maintenance OFF (évite paiements test en prod)
if PAYMENTS_SANDBOX and not APP_MAINTENANCE:
    print("⚠️ [Stripe] PAYMENTS_SANDBOX=on mais APP_MAINTENANCE=off → sandbox désactivé par sécurité")
    PAYMENTS_SANDBOX = False

# 🔑 Choix de la clé Stripe selon le mode (avec compat sur plusieurs noms d'env)
if PAYMENTS_SANDBOX:
    STRIPE_KEY = (
        os.getenv("STRIPE_SECRET_KEY_TEST") or
        os.getenv("STRIPE_TEST_SECRET_KEY") or
        ""
    ).strip()
else:
    STRIPE_KEY = (
        os.getenv("STRIPE_SECRET_KEY") or
        os.getenv("STRIPE_LIVE_SECRET_KEY") or
        ""
    ).strip()

if not STRIPE_KEY:
    raise RuntimeError("❌ Aucune clé Stripe trouvée (ni test ni live).")

import stripe
stripe.api_key = STRIPE_KEY

# 📊 Log de démarrage pour vérifier le mode
print(f"🔑 [Stripe] Mode = {'TEST 🧪' if PAYMENTS_SANDBOX else 'LIVE 💳'} | "
      f"Clé = {STRIPE_KEY[:7]}... | "
      f"livemode_expected = {not STRIPE_KEY.startswith('sk_test_')}")

# ─────────────────────────────────────────────────────────────────────────────
# POST /checkout : crée une Session Stripe et redirige vers Hosted Checkout
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route("/checkout", methods=["POST"])
def checkout():
    # 1) Infos utilisateur → stockées en session
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

    # 2) Produit choisi — obligatoire et valide
    product_key = (request.form.get("product_key") or "").strip()
    if not product_key:
        current_app.logger.warning("❌ [CHECKOUT] product_key manquant")
        abort(400, description="Produit non spécifié.")
    
    product = PRODUCTS.get(product_key)
    if not product:
        current_app.logger.warning(f"❌ [CHECKOUT] product_key inconnu: {product_key}")
        abort(400, description="Produit non reconnu.")

    # 3) Montant / Price
    price_cents = product.get("price_cents") or 0
    price_id = (product.get("price_id") or "").strip()

    # ⚠️ En test : évite les price_id live avec clé test (et vice-versa)
    # → Laisse price_id vide ou utilise des price_id correspondant au mode
    if price_id and PAYMENTS_SANDBOX and not price_id.startswith("price_test_"):
        current_app.logger.warning(f"⚠️ [CHECKOUT] Price ID live utilisé en mode test, passage en price_data")
        price_id = ""
    
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

    # 4) Créer la session Stripe (Hosted Checkout)
    try:
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
        
        current_app.logger.info(f"✅ [CHECKOUT] Session créée | mode={'TEST' if PAYMENTS_SANDBOX else 'LIVE'} | "
                              f"id={checkout_session.id} | livemode={checkout_session.livemode}")
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"❌ [CHECKOUT] Erreur Stripe: {e}")
        abort(500, description="Erreur lors de la création du paiement.")

    session["selected_product"] = product_key
    return redirect(checkout_session.url, code=303)

# ─────────────────────────────────────────────────────────────────────────────
# GET /paiement-effectue : vérifie la session Stripe et POSE les marqueurs
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    session_id = request.args.get('session_id')
    provider_arg = request.args.get('provider')
    
    # ✅ Détection automatique du provider (plus robuste)
    if provider_arg == "paypal" or (not session_id and session.get("last_payment", {}).get("provider") == "paypal"):
        provider = "paypal"
    else:
        provider = "stripe"
    
    current_app.logger.info(f"🎯 [PAIEMENT-EFFECTUE] Provider détecté = {provider}")

    # ─────────────────────────────────────────────────────────────────────────
    # ── BRANCHE PAYPAL : On lit ce que /payments/capture-order a posé
    # ─────────────────────────────────────────────────────────────────────────
    if provider == "paypal":
        last_payment = session.get("last_payment") or {}

        # On récupère un product_key si dispo, sinon défaut
        product_key = (
            last_payment.get("product_key")
            or request.args.get("product_key")
            or "flash_astral"
        )
        product = PRODUCTS.get(product_key) or PRODUCTS.get("flash_astral")

        # On journalise, mais on NE BLOQUE PAS si les marqueurs ne sont pas posés
        if last_payment.get("provider") != "paypal" or not session.get("paiement_valide"):
            current_app.logger.warning(
                "⚠️ [PAIEMENT-EFFECTUE-PAYPAL] Aucun marqueur en session "
                "(capture client). On poursuit vers la page de succès."
            )

        # Anti-reload : purge d'anciennes clés
        for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
            session.pop(k, None)

        try:
            next_url = url_for(product["success_route"])
        except Exception as e:
            current_app.logger.warning(f"⚠️ [PAIEMENT-EFFECTUE-PAYPAL] Fallback route: {e}")
            next_url = "/forces_defis/complet" if product_key == "forces_defis" else "/point_astral_blocs/complet"

        return render_template('paiement_effectue.html',
                               next_url=next_url,
                               produit_titre=product["label"])

    # ─────────────────────────────────────────────────────────────────────────
    # ── BRANCHE STRIPE : Vérification via l'API Stripe
    # ─────────────────────────────────────────────────────────────────────────
    
    # ─────────────────────────────────────────────────────────────────────────
# ── BRANCHE STRIPE : Vérification via l'API Stripe
# ─────────────────────────────────────────────────────────────────────────

    current_app.logger.info(f"🎯 [PAIEMENT-EFFECTUE-STRIPE] session_id = {session_id}")

    if not session_id:
        current_app.logger.warning("❌ [PAIEMENT-EFFECTUE-STRIPE] Pas de session_id")
        return render_template('paiement_effectue_problem.html',
                            message="Session paiement manquante."), 400

    try:
        s = stripe.checkout.Session.retrieve(session_id)
        
        current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-STRIPE] Session récupérée | "
                            f"id={s.id} | payment_status={s.get('payment_status')} | "
                            f"livemode={s.get('livemode')}")
        
    except stripe.error.InvalidRequestError as e:
        current_app.logger.error(f"❌ [PAIEMENT-EFFECTUE-STRIPE] Session introuvable (mismatch test/live ?): {e}")
        return render_template('paiement_effectue_problem.html',
                            message="Session introuvable. Vérifiez le mode test/live."), 400
    except Exception as e:
        current_app.logger.exception(f"❌ [PAIEMENT-EFFECTUE-STRIPE] Erreur inattendue: {e}")
        return render_template('paiement_effectue_problem.html',
                            message="Impossible de vérifier le paiement."), 400

    if s.get("payment_status") != "paid":
        current_app.logger.warning(f"⚠️ [PAIEMENT-EFFECTUE-STRIPE] Paiement non payé: {s.get('payment_status')}")
        return render_template('paiement_effectue_problem.html',
                            message="Paiement non confirmé."), 402

    product_key = (s.get('metadata') or {}).get('product_key')

    # ✅ ✅ ✅ LOGS DE DEBUG AJOUTÉS ✅ ✅ ✅
    current_app.logger.info(f"🔍 [DEBUG-STRIPE] product_key extrait des metadata = '{product_key}'")

    product = PRODUCTS.get(product_key or "")

    current_app.logger.info(f"🔍 [DEBUG-STRIPE] product trouvé = {product is not None}")
    if product:
        current_app.logger.info(f"🔍 [DEBUG-STRIPE] product_label = '{product.get('label')}'")
        current_app.logger.info(f"🔍 [DEBUG-STRIPE] success_route = '{product.get('success_route')}'")

    if not product:
        current_app.logger.error(f"❌ [PAIEMENT-EFFECTUE-STRIPE] Produit inconnu: {product_key}")
        return render_template('paiement_effectue_problem.html',
                            message="Produit inconnu après paiement."), 400

    # ✅ Marqueurs Stripe
    session["last_payment"] = {
        "provider": "stripe",
        "session_id": session_id,
        "status": s.get("payment_status"),
        "amount_total": s.get("amount_total"),
        "currency": s.get("currency"),
        "created": s.get("created"),
        "product_key": product_key,
        "livemode": s.get("livemode"),
        "mode": "SANDBOX" if PAYMENTS_SANDBOX else "LIVE",
    }
    session["selected_product"] = product_key
    session["stripe_session_id"] = session_id
    session["paiement_valide"] = True
    session["paiement_timestamp"] = datetime.utcnow().isoformat()
    session.modified = True

    current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-STRIPE] Paiement validé | product={product_key} | mode={session['last_payment']['mode']}")

    # ✅ ✅ ✅ GÉNÉRATION URL AVEC DEBUG ✅ ✅ ✅
    try:
        current_app.logger.info(f"🔍 [DEBUG-STRIPE] Tentative url_for('{product['success_route']}')")
        next_url = url_for(product["success_route"])
        current_app.logger.info(f"✅ [DEBUG-STRIPE] URL générée avec succès = '{next_url}'")
        
    except Exception as e:
        current_app.logger.error(f"❌ [DEBUG-STRIPE] Erreur url_for: {type(e).__name__}: {e}")
        current_app.logger.error(f"❌ [DEBUG-STRIPE] Le blueprint '{product['success_route'].split('.')[0]}' est-il enregistré ?")
        
        # Fallback avec URL en dur
        if product_key == "forces_defis":
            next_url = "/forces_defis/complet"
            current_app.logger.warning(f"⚠️ [DEBUG-STRIPE] Utilisation fallback URL: {next_url}")
        else:
            next_url = "/point_astral_blocs/complet"
            current_app.logger.warning(f"⚠️ [DEBUG-STRIPE] Utilisation fallback URL: {next_url}")

    # Anti-reload : purge d'anciennes clés
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    current_app.logger.info(f"🎯 [DEBUG-STRIPE] Redirection finale vers: {next_url}")

    return render_template('paiement_effectue.html',
                        next_url=next_url,
                        produit_titre=product["label"])