# routes/checkout.py
# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp — Stripe checkout multi-produits + succès
# ─────────────────────────────────────────────────────────────────────────────

import os
import uuid
import json
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

APP_MAINTENANCE = _env_on(os.getenv("APP_MAINTENANCE"))

# 🔒 Sécurité : Désactiver sandbox si maintenance OFF
if PAYMENTS_SANDBOX and not APP_MAINTENANCE:
    print("⚠️ [Stripe] PAYMENTS_SANDBOX=on mais APP_MAINTENANCE=off → sandbox désactivé par sécurité")
    PAYMENTS_SANDBOX = False

# 🔑 Choix de la clé Stripe selon le mode
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

stripe.api_key = STRIPE_KEY

print(f"🔑 [Stripe] Mode = {'TEST 🧪' if PAYMENTS_SANDBOX else 'LIVE 💳'} | "
      f"Clé = {STRIPE_KEY[:7]}... | "
      f"livemode_expected = {not STRIPE_KEY.startswith('sk_test_')}")

# ─────────────────────────────────────────────────────────────────────────────
# POST /checkout : crée une Session Stripe MULTI-PRODUITS
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

    # 2) 🛒 NOUVEAU : Récupération des items du panier
    items_json = request.form.get("items", "[]")
    try:
        cart_items = json.loads(items_json)
    except Exception as e:
        current_app.logger.error(f"❌ [CHECKOUT] Erreur parsing panier: {e}")
        cart_items = []
    
    # Fallback : si panier vide, utiliser product_key unique (ancien comportement)
    if not cart_items:
        product_key = (request.form.get("product_key") or "").strip()
        if product_key:
            cart_items = [{"key": product_key, "quantity": 1}]
    
    if not cart_items:
        current_app.logger.warning("❌ [CHECKOUT] Panier vide")
        abort(400, description="Panier vide.")
    
    current_app.logger.info(f"🛒 [CHECKOUT] Panier: {cart_items}")
    
    # 3) 📦 Construction des line_items Stripe
    line_items = []
    product_keys = []  # Pour tracking
    total_cents = 0
    
    for item in cart_items:
        pk = item.get("key")
        qty = item.get("quantity", 1)
        
        product = PRODUCTS.get(pk)
        if not product:
            current_app.logger.warning(f"⚠️ [CHECKOUT] Produit inconnu ignoré: {pk}")
            continue
        
        product_keys.append(pk)
        price_cents = product.get("price_cents") or 0
        total_cents += price_cents * qty
        price_id = (product.get("price_id") or "").strip()
        
        # Éviter les price_id live en mode test
        if price_id and PAYMENTS_SANDBOX and not price_id.startswith("price_test_"):
            current_app.logger.warning(f"⚠️ [CHECKOUT] Price ID live ignoré en test: {pk}")
            price_id = ""
        
        if price_id:
            line_items.append({'price': price_id, 'quantity': qty})
        else:
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': product["label"]},
                    'unit_amount': price_cents,
                },
                'quantity': qty,
            })
    
    if not line_items:
        current_app.logger.error("❌ [CHECKOUT] Aucun produit valide dans le panier")
        abort(400, description="Aucun produit valide.")
    
    current_app.logger.info(f"💰 [CHECKOUT] Total: {total_cents/100:.2f}€ | Produits: {product_keys}")
    
    # 4) Créer la session Stripe
    try:
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=line_items,
            success_url=url_for('checkout_bp.paiement_effectue', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.index', _external=True),
            metadata={
                "product_keys": ",".join(product_keys),  # ✅ Liste des produits
                "email": session['infos_utilisateur'].get('email', ''),
                "total_cents": str(total_cents),
            },
            client_reference_id=(session['infos_utilisateur'].get('email') or str(uuid.uuid4()))
        )
        
        current_app.logger.info(f"✅ [CHECKOUT] Session créée | mode={'TEST' if PAYMENTS_SANDBOX else 'LIVE'} | "
                              f"id={checkout_session.id} | produits={product_keys}")
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"❌ [CHECKOUT] Erreur Stripe: {e}")
        abort(500, description="Erreur lors de la création du paiement.")

    # ✅ Stocker les produits commandés en session
    session["ordered_products"] = product_keys
    session["cart_items"] = cart_items
    session.modified = True
    
    return redirect(checkout_session.url, code=303)

# ─────────────────────────────────────────────────────────────────────────────
# GET /paiement-effectue : vérifie la session Stripe et REDIRIGE vers les modules
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    session_id = request.args.get('session_id')
    provider_arg = request.args.get('provider')
    
    # ✅ Détection automatique du provider
    if provider_arg == "paypal" or (not session_id and session.get("last_payment", {}).get("provider") == "paypal"):
        provider = "paypal"
    else:
        provider = "stripe"
    
    current_app.logger.info(f"🎯 [PAIEMENT-EFFECTUE] Provider = {provider}")

    # ─────────────────────────────────────────────────────────────────────────
    # ── BRANCHE PAYPAL
    # ─────────────────────────────────────────────────────────────────────────
    if provider == "paypal":
        last_payment = session.get("last_payment") or {}
        
        current_app.logger.info(f"🎯 [PAIEMENT-EFFECTUE-PAYPAL] order_id={last_payment.get('order_id')} | "
                               f"valide={session.get('paiement_valide')}")
        
        if last_payment.get("provider") != "paypal" or not session.get("paiement_valide"):
            current_app.logger.warning("❌ [PAIEMENT-EFFECTUE-PAYPAL] Paiement non confirmé")
            return render_template('paiement_effectue_problem.html',
                                 message="Aucun paiement PayPal confirmé."), 400

        # 🛒 Multi-produits PayPal
        product_keys = session.get("ordered_products") or []
        if not product_keys:
            # Fallback ancien comportement
            pk = last_payment.get("product_key") or "flash_astral"
            product_keys = [pk]
        
        current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-PAYPAL] Produits: {product_keys}")
        
        # Marquer comme traité
        session["pending_generation"] = {
            "products": product_keys,
            "provider": "paypal",
            "order_id": last_payment.get("order_id")
        }
        session.modified = True
        
        # Redirection vers page de traitement multi-produits
        return redirect(url_for('checkout_bp.traiter_analyses'))

    # ─────────────────────────────────────────────────────────────────────────
    # ── BRANCHE STRIPE
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
        current_app.logger.error(f"❌ [PAIEMENT-EFFECTUE-STRIPE] Session introuvable: {e}")
        return render_template('paiement_effectue_problem.html',
                            message="Session introuvable. Vérifiez le mode test/live."), 400
    except Exception as e:
        current_app.logger.exception(f"❌ [PAIEMENT-EFFECTUE-STRIPE] Erreur: {e}")
        return render_template('paiement_effectue_problem.html',
                            message="Impossible de vérifier le paiement."), 400

    if s.get("payment_status") != "paid":
        current_app.logger.warning(f"⚠️ [PAIEMENT-EFFECTUE-STRIPE] Non payé: {s.get('payment_status')}")
        return render_template('paiement_effectue_problem.html',
                            message="Paiement non confirmé."), 402

    # 🛒 Récupérer les produits de la metadata
    metadata = s.get('metadata') or {}
    product_keys_str = metadata.get('product_keys', '')
    product_keys = [pk.strip() for pk in product_keys_str.split(',') if pk.strip()]
    
    # Fallback
    if not product_keys:
        product_keys = session.get("ordered_products") or []
    
    if not product_keys:
        pk = metadata.get('product_key') or "flash_astral"
        product_keys = [pk]
    
    current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-STRIPE] Produits: {product_keys}")

    # ✅ Marqueurs Stripe
    session["last_payment"] = {
        "provider": "stripe",
        "session_id": session_id,
        "status": s.get("payment_status"),
        "amount_total": s.get("amount_total"),
        "currency": s.get("currency"),
        "created": s.get("created"),
        "product_keys": product_keys,
        "livemode": s.get("livemode"),
        "mode": "SANDBOX" if PAYMENTS_SANDBOX else "LIVE",
    }
    session["ordered_products"] = product_keys
    session["stripe_session_id"] = session_id
    session["paiement_valide"] = True
    session["paiement_timestamp"] = datetime.utcnow().isoformat()
    session["pending_generation"] = {
        "products": product_keys,
        "provider": "stripe",
        "session_id": session_id
    }
    session.modified = True

    current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-STRIPE] Paiement validé | produits={product_keys}")

    # Anti-reload
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    # Redirection vers page de traitement multi-produits
    return redirect(url_for('checkout_bp.traiter_analyses'))


# ─────────────────────────────────────────────────────────────────────────────
# GET /traiter-analyses : génère toutes les analyses commandées
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/traiter-analyses')
def traiter_analyses():
    """Page intermédiaire qui génère toutes les analyses puis affiche les liens"""
    
    pending = session.get("pending_generation")
    if not pending:
        return render_template('paiement_effectue_problem.html',
                            message="Aucune analyse en attente."), 400
    
    product_keys = pending.get("products", [])
    if not product_keys:
        return render_template('paiement_effectue_problem.html',
                            message="Liste de produits vide."), 400
    
    current_app.logger.info(f"🔄 [TRAITER-ANALYSES] Génération de: {product_keys}")
    
    # Valider que les produits existent
    valid_products = []
    for pk in product_keys:
        if pk in PRODUCTS:
            valid_products.append(pk)
        else:
            current_app.logger.warning(f"⚠️ Produit inconnu ignoré: {pk}")
    
    if not valid_products:
        return render_template('paiement_effectue_problem.html',
                            message="Aucun produit valide à générer."), 400
    
    # Générer les analyses (stocke les URLs en session)
    resultats = {}
    for pk in valid_products:
        product = PRODUCTS[pk]
        route = product.get("success_route")
        
        if not route:
            current_app.logger.warning(f"⚠️ Pas de success_route pour {pk}")
            continue
        
        try:
            url = url_for(route, _external=True)
            resultats[pk] = {
                "label": product["label"],
                "url": url,
                "status": "ready"
            }
            current_app.logger.info(f"✅ URL générée pour {pk}: {url}")
        except Exception as e:
            current_app.logger.error(f"❌ Erreur URL pour {pk}: {e}")
            resultats[pk] = {
                "label": product["label"],
                "url": None,
                "status": "error",
                "error": str(e)
            }
    
    # Stocker en session
    session["generated_analyses"] = resultats
    session.pop("pending_generation", None)
    session.modified = True
    
    # Afficher la page de confirmation avec tous les liens
    return render_template('paiement_effectue_multi.html',
                         analyses=resultats,
                         provider=pending.get("provider"))