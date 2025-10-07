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
from utils.env_flags import env_bool
from datetime import datetime

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

from datetime import datetime  # en haut du fichier

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

    # ✅ Marquer clairement le paiement (ce que regarde point_astral_blocs)
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

    # 🔗 Où aller ensuite (endpoint défini dans config.products)
    try:
        next_url = url_for(product["success_route"])
    except Exception:
        # Fallback si l’endpoint a été renommé
        next_url = "/forces_defis/complet" if product_key == "forces_defis" else "/point_astral_blocs/complet"

    # 🧹 Anti-reload: on purge quelques clés de génération
    for k in ("last_pdf_url", "lock_until", "last_generation_key", "last_generation_at"):
        session.pop(k, None)

    return render_template('paiement_effectue.html',
                           next_url=next_url,
                           produit_titre=product["label"])

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