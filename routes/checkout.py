# routes/checkout.py

from flask import Blueprint, request, session, redirect, url_for
import stripe
import os

checkout_bp = Blueprint('checkout_bp', __name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@checkout_bp.route('/checkout', methods=['POST'])
def checkout():
    session['infos_utilisateur'] = {
        "nom": request.form.get("nom"),
        "email": request.form.get("email"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance")
    }

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': 'Point Astral complet'},
                'unit_amount': 3500,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('checkout_bp.paiement_effectue', _external=True),
        cancel_url=url_for('formulaire', _external=True),
    )

    return redirect(checkout_session.url, code=303)

@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    return redirect(url_for('point_astral.afficher_point_astral'))