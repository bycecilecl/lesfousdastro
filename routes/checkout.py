# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp
# Rôle : gère le paiement Stripe pour le "Point Astral complet".
# Dépendances :
#   - STRIPE_SECRET_KEY (env) : clé secrète Stripe (compte live ou test)
#   - flask.session : stocke les infos utilisateur avant redirection vers Stripe
#   - url_for(...)  : URLs absolues (_external=True) exigées par Stripe
# Remarques :
#   - Le prix est en centimes d’euro (ici 3500 = 35,00 €).
#   - Pas de webhook ici : la confirmation s’appuie sur l’URL de succès.
#     (à sécuriser avec un webhook Stripe en prod)
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template, session, redirect, url_for, request
import stripe
import os
import uuid
import time

checkout_bp = Blueprint('checkout_bp', __name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE : POST /checkout
# Rôle : crée une Session de paiement Stripe et redirige l’utilisateur
#        vers la page de paiement hébergée par Stripe.
# Entrées (form-data) :
#   - nom, email, date_naissance, heure_naissance, lieu_naissance
# Effets :
#   - Stocke ces infos dans flask.session['infos_utilisateur'] pour les réutiliser
#     après paiement (génération du Point Astral).
#   - Crée stripe.checkout.Session avec 1 ligne "Point Astral complet" à 35 €.
#   - Redirige (303) vers checkout_session.url (Stripe Hosted Checkout).
# URLs :
#   - success_url → checkout_bp.paiement_effectue (confirmation locale)
#   - cancel_url  → formulaire (retour au formulaire si annulation)
# À savoir :
#   - Les montants sont en centimes.
#   - Pense à passer en mode live + clé live en production.
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/checkout', methods=['POST'])
def checkout():
    session['infos_utilisateur'] = {
        "nom": request.form.get("nom"),
        "email": request.form.get("email"),
        "gender": request.form.get("gender"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance"), 
        "lat": request.form.get("lat", "").strip(),     
        "lon": request.form.get("lon", "").strip(),
        "tzid": request.form.get("tzid", "").strip(),
    }
    

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': 'Point Astral complet'},
                'unit_amount': 2900,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('checkout_bp.paiement_effectue', _external=True),
        cancel_url = url_for('main.index', _external=True)
    )

    return redirect(checkout_session.url, code=303)

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE : GET /paiement-effectue
# Rôle : point d’atterrissage après succès Stripe.
# Effets :
#   - Redirige vers point_astral.afficher_point_astral
#     (qui lira session['infos_utilisateur'], calculera le thème,
#      générera le Point Astral et l’enverra).
# Remarques :
#   - Sans webhook, cette confirmation repose uniquement sur la redirection
#     Stripe : pour une validation anti-fraude/anti-recharge, implémente
#     un webhook (event "checkout.session.completed") côté serveur.
# ─────────────────────────────────────────────────────────────────────────────

# @checkout_bp.route('/paiement-effectue')
# def paiement_effectue():
#     # Redirection directe comme avant, mais avec le task_id en session
#     return redirect(url_for('point_astral_blocs.point_astral_blocs_complet'))


@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    # Page intermédiaire avec popup de patience
    return render_template('paiement_effectue.html')