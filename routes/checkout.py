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
from config.gift_codes import get_gift_code, is_code_used, mark_code_as_used
from utils.email_sender import (
    envoyer_email_clarification_questions,
    envoyer_email_notification_clarification_admin,
    envoyer_email_avec_analyse
)
#from utils.brevo_utils import ajouter_contact_brevo
from threading import Thread
from utils.s3_utils import upload_file_and_presign
from routes.point_astral_blocs import generer_flash_astral_pdf_s3
from point_astral_famille.routes import generer_point_astral_famille_pdf_s3
from routes.forces_defis_module import generer_forces_defis_pdf_s3
from routes.profil_amoureux_module import generer_profil_amoureux_pdf_s3
from routes.analyse_karmique import generer_analyse_karmique_pdf_s3
import traceback


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


@checkout_bp.route('/debug-session')
def debug_session():
    return {
        "ordered_products": session.get("ordered_products"),
        "pending_generation": session.get("pending_generation"),
        "last_payment": session.get("last_payment"),
        "cart_items": session.get("cart_items"),
    }

@checkout_bp.route("/checkout", methods=["POST"])
def checkout():

    # 🧹 Nettoyage ancienne commande / anciens PDF / anti-reload
    for k in (
        "ordered_products",
        "pending_generation",
        "last_payment",
        "cart_items",
        "paiement_valide",
        "paiement_timestamp",
        "stripe_session_id",
        "paypal_order_id",
        "clarification_email_sent",

        "last_pdf_url",
        "lock_until",
        "last_generation_key",
        "last_generation_at",
        "last_fingerprint",

        "last_pdf_url_profil_amoureux",
        "lock_until_profil_amoureux",
        "last_fingerprint_profil_amoureux",

        "last_pdf_url_forces_defis",
        "lock_until_forces_defis",
        "last_fingerprint_forces_defis",

        "last_pdf_url_analyse_karmique",
        "lock_until_analyse_karmique",
        "last_fingerprint_analyse_karmique",
    ):
        session.pop(k, None)

    session.modified = True

    
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
        "transit_date_mode": (request.form.get("transit_date_mode") or "today").strip(),
        "transit_date": (request.form.get("transit_date") or "").strip(),
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
    # try:
    #     infos = session.get("infos_utilisateur") or {}
    #     email = infos.get("email")
    #     prenom = (infos.get("nom") or "").split()[0]

    #     if "flash_astral" in product_keys and email:
    #         ajouter_contact_brevo(
    #             email=email,
    #             prenom=prenom,
    #             list_id_env="BREVO_LIST_FLASH_ID"
    #         )
    #         current_app.logger.info(f"✅ [BREVO] Client Point Astral ajouté : {email}")

    # except Exception as e:
    #     current_app.logger.warning(f"⚠️ [BREVO] Ajout client Point Astral impossible : {e}")

    fixed_cart = []
    for item in cart_items:
        if not isinstance(item, dict):
            continue

        item_id = item.get("id") or item.get("key")
        if not item_id:
            continue

        if "items" in item and isinstance(item["items"], list):
            fixed_cart.append({
                "key": item_id,
                "quantity": int(item.get("quantity", 1) or 1)
            })
        else:
            fixed_cart.append({
                "key": item_id,
                "quantity": int(item.get("quantity", 1) or 1)
            })

    cart_items = fixed_cart
    current_app.logger.info(f"🔄 [CHECKOUT] Corrigé: {cart_items}")
    
    # 3) 📦 Construction des line_items Stripe
    line_items = []
    payment_product_keys = []   # ce qui est effectivement payé (peut contenir pack_essence)
    analysis_product_keys = []  # ce qui sera généré comme analyses
    total_cents = 0
    
    for item in cart_items:
        # 👇 Accepte soit "key", soit "id" venant du frontend
        pk = item.get("key") or item.get("id")
        qty = item.get("quantity", 1)

        product = PRODUCTS.get(pk)
        if not product:
            current_app.logger.warning(f"⚠️ [CHECKOUT] Produit inconnu ignoré: {pk}")
            continue
        
        price_cents = product.get("price_cents") or 0
        total_cents += price_cents * qty
        price_id = (product.get("price_id") or "").strip()

        # 👉 1) côté paiement : on ajoute tel quel (pack ou module)
        payment_product_keys.append(pk)

        # 👉 2) côté analyses :
        included = product.get("included_products")
        if included:
            # pack : on ajoute les modules réels à générer
            for _ in range(qty):
                analysis_product_keys.extend(included)
        else:
            # produit simple
            for _ in range(qty):
                analysis_product_keys.append(pk)
        
        # ⚙️ création du line_item Stripe (comme avant)
        if price_id:
            # Éviter les price_id live en mode test
            if PAYMENTS_SANDBOX and not price_id.startswith("price_test_"):
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

    if "flash_transits" in payment_product_keys and len(payment_product_keys) > 1:
        abort(400, description="Le Flash Transits doit être commandé séparément.")
    
    current_app.logger.info(
        f"💰 [CHECKOUT] Total: {total_cents/100:.2f}€ | "
        f"Payés: {payment_product_keys} | Analyses: {analysis_product_keys}"
    )
    
    # 4) Créer la session Stripe
    try:
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=line_items,
            success_url=url_for('checkout_bp.paiement_effectue', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.index', _external=True),
            metadata={
                # 👉 on enregistre les ANALYSES à générer, pas juste ce qui est payé
                "product_keys": ",".join(analysis_product_keys),
                "email": session['infos_utilisateur'].get('email', ''),
                "total_cents": str(total_cents),
                "transit_date_mode": session['infos_utilisateur'].get('transit_date_mode', 'today'),
                "transit_date": session['infos_utilisateur'].get('transit_date', ''),
            },
            client_reference_id=(session['infos_utilisateur'].get('email') or str(uuid.uuid4()))
        )
        
        current_app.logger.info(
            f"✅ [CHECKOUT] Session créée | mode={'TEST' if PAYMENTS_SANDBOX else 'LIVE'} | "
            f"id={checkout_session.id} | payés={payment_product_keys} | analyses={analysis_product_keys}"
        )
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"❌ [CHECKOUT] Erreur Stripe: {e}")
        abort(500, description="Erreur lors de la création du paiement.")

    # ✅ Stocker les produits commandés en session
    session["ordered_products"] = analysis_product_keys
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

        infos = session.get("infos_utilisateur", {})

        nom = infos.get("nom")
        email = infos.get("email")
        date_naissance = infos.get("date_naissance")
        heure_naissance = infos.get("heure_naissance")
        lieu_naissance = infos.get("lieu_naissance")

        clarification_achetee = "clarification_questions" in product_keys
        
        # Marquer comme traité
        session["pending_generation"] = {
            "products": product_keys,
            "provider": "paypal",
            "order_id": last_payment.get("order_id")
        }
    
        if clarification_achetee and email:

            envoyer_email_clarification_questions(
                email=email,
                nom=nom
            )

            envoyer_email_notification_clarification_admin(
                nom=nom,
                email_client=email,
                analyse=", ".join(product_keys),
                date_naissance=date_naissance,
                heure_naissance=heure_naissance,
                lieu_naissance=lieu_naissance,
            )

            current_app.logger.info(
                f"📩 Option clarification PayPal envoyée pour {email}"
                )
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

    infos = session.get("infos_utilisateur", {})

    if "flash_transits" in product_keys:
        infos["transit_date_mode"] = (
            infos.get("transit_date_mode")
            or metadata.get("transit_date_mode")
            or "today"
        )
        infos["transit_date"] = (
            infos.get("transit_date")
            or metadata.get("transit_date")
            or ""
        )
        session["infos_utilisateur"] = infos

    nom = infos.get("nom")
    email = infos.get("email")
    date_naissance = infos.get("date_naissance")
    heure_naissance = infos.get("heure_naissance")
    lieu_naissance = infos.get("lieu_naissance")

    clarification_achetee = "clarification_questions" in product_keys

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
    if clarification_achetee and email and not session.get("clarification_email_sent"):

        # mail client
        envoyer_email_clarification_questions(
            email=email,
            nom=nom
        )

        # mail admin
        envoyer_email_notification_clarification_admin(
            nom=nom,
            email_client=email,
            analyse=", ".join(product_keys),
            date_naissance=date_naissance,
            heure_naissance=heure_naissance,
            lieu_naissance=lieu_naissance,
        )

        session["clarification_email_sent"] = True

        current_app.logger.info(
            f"📩 Option clarification envoyée pour {email}"
        )

    session.modified = True

    current_app.logger.info(f"✅ [PAIEMENT-EFFECTUE-STRIPE] Paiement validé | produits={product_keys}")

    # Anti-reload
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    # Redirection vers page de traitement multi-produits
    return redirect(url_for('checkout_bp.traiter_analyses'))


def expand_products(product_keys):
    """
    Transforme les packs en produits réellement générables.

    Exemple :
    pack_integral
    → flash_astral
    → analyse_karmique
    → profil_amoureux
    → forces_defis
    """
    expanded = []

    for pk in product_keys:
        product = PRODUCTS.get(pk)

        if not product:
            current_app.logger.warning(f"⚠️ Produit inconnu ignoré: {pk}")
            continue

        included = product.get("included_products")

        if included:
            current_app.logger.info(f"📦 Pack détecté {pk} → {included}")
            expanded.extend(included)
        else:
            expanded.append(pk)

    return expanded


# ─────────────────────────────────────────────────────────────────────────────
# GET /traiter-analyses : génère toutes les analyses commandées
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/traiter-analyses')
def traiter_analyses():
    """Page intermédiaire qui prépare les analyses commandées."""

    pending = session.get("pending_generation")
    if not pending:
        return render_template(
            'paiement_effectue_problem.html',
            message="Aucune analyse en attente."
        ), 400
    
    infos_utilisateur = session.get("infos_utilisateur") or {}

    infos_client = {
        "email": infos_utilisateur.get("email"),
        "nom": infos_utilisateur.get("nom"),
        "prenom": infos_utilisateur.get("prenom"),
        "provider": pending.get("provider"),
        "infos_utilisateur": infos_utilisateur,
    }
    current_app.logger.info(f"📧 Email client détecté: {infos_client.get('email')}")

    product_keys = pending.get("products", [])
    if not product_keys:
        return render_template(
            'paiement_effectue_problem.html',
            message="Liste de produits vide."
        ), 400

    current_app.logger.info(f"🔄 [TRAITER-ANALYSES] Produits demandés: {product_keys}")

    expanded_product_keys = expand_products(product_keys)

    valid_products = []
    for pk in expanded_product_keys:
        product = PRODUCTS.get(pk)

        if product and product.get("success_route"):
            valid_products.append(pk)
        else:
            current_app.logger.warning(f"⚠️ Produit non générable ignoré: {pk}")

    if not valid_products:
        return render_template(
            'paiement_effectue_problem.html',
            message="Aucun produit valide à générer."
        ), 400

    # ============================================================
    # CAS 1 : UNE SEULE ANALYSE
    # → on garde ton fonctionnement actuel
    # → redirection vers la route de succès du produit
    # ============================================================
    if len(valid_products) == 1:
        current_app.logger.info("🟢 Achat solo détecté : affichage direct")

        product_id = valid_products[0]
        product = PRODUCTS[product_id]
        route = product.get("success_route")

        if not route:
            return render_template(
                'paiement_effectue_problem.html',
                message=f"Aucune route de génération trouvée pour {product.get('label', product_id)}."
            ), 400

        return render_template(
            'paiement_effectue.html',
            produit_titre=product.get("label", "analyse"),
            next_url=url_for(route),
            already=False,
        )

    # ============================================================
    # CAS 2 : PACK / PLUSIEURS ANALYSES
    # → génération en arrière-plan + email final
    # ============================================================
    current_app.logger.info("🟣 Pack détecté : génération en arrière-plan")

    fallback_urls = {}

    for pk in valid_products:
        product = PRODUCTS.get(pk)
        route = product.get("success_route") if product else None

        if route:
            fallback_urls[pk] = url_for(route, _external=True)

    pending["fallback_urls"] = fallback_urls

    app = current_app._get_current_object()
    pending["infos_utilisateur"] = infos_utilisateur

    thread = Thread(
        target=lancer_generation_pack_en_arriere_plan,
        args=(app, valid_products, infos_client, pending),
        daemon=True,
    )
    thread.start()

    session.pop("pending_generation", None)
    session.modified = True

    return render_template(
        "analyses_en_cours.html",
        email=infos_client.get("email"),
        nombre_analyses=len(valid_products),
    )

def lancer_generation_pack_en_arriere_plan(app, valid_products, infos_client, pending):
    """
    Génère les analyses d'un pack en arrière-plan.
    Important : on recrée un app_context Flask car le Thread n'a pas accès
    automatiquement au contexte de la requête.
    """
    with app.app_context():
        try:
            current_app.logger.info("🚀 Génération pack démarrée en arrière-plan")

            # Ici on appellera la génération complète des analyses du pack
            # puis l'envoi email final.
            generer_pack_et_envoyer_email(valid_products, infos_client, pending)

            current_app.logger.info("✅ Génération pack terminée avec succès")

        except Exception as e:
            current_app.logger.error("❌ Erreur génération pack arrière-plan")
            current_app.logger.error(str(e))
            current_app.logger.error(traceback.format_exc())

def get_success_route_from_product(product_id):
    """
    Retourne la success_route Flask d'un produit.
    """
    product = PRODUCTS.get(product_id)

    if not product:
        return None

    return product.get("success_route")


def generer_analyse_pack(product_id, pending):
    """
    Génère une analyse complète pour un pack
    et retourne un lien PDF S3.
    """

    current_app.logger.info(f"🚀 Génération réelle : {product_id}")

    try:
        product = PRODUCTS.get(product_id)

        if not product:
            return None

        route = product.get("success_route")

        if not route:
            return None

        infos = pending.get("infos_utilisateur") or {}

        # =====================================================
        # POINT ASTRAL
        # =====================================================
        if product_id == "flash_astral":

            resultat = generer_flash_astral_pdf_s3(
                infos=infos,
                envoyer_email=False,
            )

            return {
                "product_id": product_id,
                "label": product["label"],
                "pdf_url": resultat.get("pdf_url"),
                "pdf_path": resultat.get("pdf_path"),
                "s3_ready": True,
            }

        # =====================================================
        # POINT ASTRAL – RACINES FAMILIALES
        # =====================================================
        if product_id == "point_astral_famille":

            resultat = generer_point_astral_famille_pdf_s3(
                infos=infos,
                envoyer_email=False,
            )

            return {
                "product_id": product_id,
                "label": product["label"],
                "pdf_url": resultat.get("pdf_url"),
                "pdf_path": resultat.get("pdf_path"),
                "s3_ready": True,
            }

        # =====================================================
        # FORCES & DÉFIS
        # =====================================================
        if product_id == "forces_defis":

            resultat = generer_forces_defis_pdf_s3(
                infos=infos,
                envoyer_email=False,
            )

            return {
                "product_id": product_id,
                "label": product["label"],
                "pdf_url": resultat.get("pdf_url"),
                "pdf_path": resultat.get("pdf_path"),
                "s3_ready": True,
            }
        
        
        # =====================================================
        # PROFIL AMOUREUX
        # =====================================================
        if product_id == "profil_amoureux":

            resultat = generer_profil_amoureux_pdf_s3(
                infos=infos,
                envoyer_email=False,
            )

            return {
                "product_id": product_id,
                "label": product["label"],
                "pdf_url": resultat.get("pdf_url"),
                "pdf_path": resultat.get("pdf_path"),
                "s3_ready": True,
            }
        
        # =====================================================
        # ANALYSE KARMIQUE
        # =====================================================
        if product_id == "analyse_karmique":

            resultat = generer_analyse_karmique_pdf_s3(
                infos=infos,
                envoyer_email=False,
            )

            return {
                "product_id": product_id,
                "label": product["label"],
                "pdf_url": resultat.get("pdf_url"),
                "pdf_path": resultat.get("pdf_path"),
                "s3_ready": True,
            }
        
        # =====================================================
        # FALLBACK — PRODUIT PAS ENCORE BRANCHÉ
        # =====================================================
        current_app.logger.warning(
            f"⚠️ Génération pack non encore branchée pour : {product_id}"
        )

        return {
            "product_id": product_id,
            "label": product["label"],
            "pdf_url": None,
            "pdf_path": None,
            "fallback_url": pending.get("fallback_urls", {}).get(product_id),
            "s3_ready": False,
        }

    except Exception as e:
        current_app.logger.error(f"❌ Erreur génération analyse {product_id}: {e}")
        current_app.logger.error(traceback.format_exc())
        return None

def generer_pack_et_envoyer_email(valid_products, infos_client, pending):
    analyses_generees = []

    for product_id in valid_products:
        current_app.logger.info(f"🔮 Génération pack : {product_id}")

        resultat = generer_analyse_pack(product_id, pending)

        if resultat:
            analyses_generees.append(resultat)
            current_app.logger.info(f"✅ Analyse générée : {product_id}")

    if analyses_generees:
        envoyer_email_pack_termine(
            infos_client=infos_client,
            analyses_generees=analyses_generees,
        )
    else:
        current_app.logger.error("❌ Aucune analyse générée, email non envoyé")


def envoyer_email_pack_termine(infos_client, analyses_generees):
    email = infos_client.get("email")
    if not email:
        current_app.logger.warning("⚠️ Aucun email client : impossible d'envoyer le pack")
        return

    prenom = (infos_client.get("nom") or "").split()[0] or "toi"

    lignes_txt = []
    lignes_html = []

    for analyse in analyses_generees:
        lien = (
            analyse.get("pdf_url")
            or analyse.get("fallback_url")
            or "https://lesfousdastro.fr"
        )
        label = analyse.get("label", "Analyse")
        lignes_txt.append(f"- {label} : {lien}")
        lignes_html.append(f"""
            <div style='margin:15px 0; text-align:center;'>
                <a href='{lien}' target='_blank'
                style='display:inline-block;padding:12px 24px;background:#1f628e;color:white;
                border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px;'>
                📄 {label}
                </a>
            </div>
        """)

    contenu_txt = (
        f"Bonjour {prenom},\n\n"
        "Tes analyses sont prêtes ✨ Merci pour ta confiance !\n\n"
        + "\n".join(lignes_txt)
        + "\n\n⚠️ Veille à bien télécharger chaque document et à le sauvegarder sur ton appareil.\n"
        "Si un lien ne s'ouvre pas, copie/colle l'URL dans ton navigateur.\n\n"
        "À très vite sur les réseaux...en vrai, ou dans les étoiles si on se croise jamais (c'est triste mais c'est une possibilité),\n"
        "Les Fous d'Astro by Cécile CL ✨"
    )

    contenu_html = f"""
    <p>Bonjour {prenom},</p>
    <p>Tes analyses sont prêtes ✨ Merci pour ta confiance !</p>
    <div style='margin:30px 0;'>
    {"".join(lignes_html)}
    </div>
    <p style='font-size:13px;color:#777;text-align:center;'>
    ⚠️ Veille à bien télécharger chaque document et à le sauvegarder sur ton appareil.<br>
    Si un lien ne s'ouvre pas, copie/colle l'URL directement dans ton navigateur.
    </p>
    <div style='margin:30px 0;padding:20px;background:#f9f6ff;border-radius:12px;'>
    <p style='color:#534AB7;line-height:1.7;margin:0;'>
    Tu as maintenant entre les mains des clés pour mieux te comprendre.<br>
    Prends le temps de lire, de relire. Certaines choses ne résonnent pas tout de suite,
    et puis un jour ça fait tilt.
    </p>
    </div>
    <p style='margin-top:40px;'>À très vite sur les réseaux..., en vrai, ou dans les étoiles si on se croise jamais (c'est triste mais c'est une possibilité),<br>
    Les Fous d'Astro by Cécile CL ✨</p>
    """

    ok = envoyer_email_avec_analyse(
        destinataire=email,
        sujet="Tes analyses astrologiques sont prêtes ✨",
        contenu_txt=contenu_txt,
        contenu_html=contenu_html,
    )

    if ok:
        current_app.logger.info(f"✅ Email pack envoyé à {email}")
    else:
        current_app.logger.error(f"❌ Échec envoi email pack à {email}")
