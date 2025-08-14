# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT : checkout_bp - VERSION MISE À JOUR
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, request, session, redirect, url_for
import stripe
import os
import json

checkout_bp = Blueprint('checkout_bp', __name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@checkout_bp.route('/checkout', methods=['POST'])
def checkout():
    # Stocker les infos complètes en session
    session['infos_utilisateur'] = {
        "nom": request.form.get("nom"),
        "email": request.form.get("email"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance"),
        "lat": request.form.get("lat"),
        "lon": request.form.get("lon"),
        "tzid": request.form.get("tzid"),
        "gender": request.form.get("gender"),
        "type_commande": request.form.get("type_commande"),
        "items": request.form.get("items"),
        "total": request.form.get("total")
    }

    # Pour l'instant, on garde le Point Astral simple à 35€
    # Plus tard on pourra adapter selon les items/packs
    total_amount = int(float(request.form.get("total", "35")) * 100)  # en centimes
    
    # Déterminer le nom du produit
    type_commande = request.form.get("type_commande", "individual")
    if type_commande == "pack":
        product_name = "Pack d'analyses astrologiques"
    else:
        product_name = "Point Astral complet"

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': product_name},
                'unit_amount': total_amount,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('checkout_bp.paiement_effectue', _external=True),
        cancel_url=url_for('formulaire', _external=True),
    )

    return redirect(checkout_session.url, code=303)

# @checkout_bp.route('/paiement-effectue')
# def paiement_effectue():
#     return redirect(url_for('point_astral.afficher_point_astral'))

@checkout_bp.route('/paiement-effectue')
def paiement_effectue():
    html_confirmation = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Paiement réussi ✅</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
            .container {{ background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
            .success {{ color: #10B981; font-size: 48px; margin-bottom: 20px; }}
            h1 {{ color: #1f628e; margin-bottom: 20px; }}
            p {{ color: #666; line-height: 1.6; margin-bottom: 15px; }}
            .btn {{ background: linear-gradient(135deg, #1f628e, #00a8a8); color: white; padding: 15px 30px; border: none; border-radius: 25px; font-size: 16px; cursor: pointer; text-decoration: none; display: inline-block; margin: 10px; }}
            .btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(31, 98, 142, 0.3); }}
            .btn-secondary {{ background: #f8f9fa; color: #1f628e; border: 2px solid #1f628e; }}
            .btn-secondary:hover {{ background: #1f628e; color: white; }}
            .info {{ background: #f0f8ff; padding: 15px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #1f628e; }}
            .buttons {{ margin: 25px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅</div>
            <h1>Paiement réussi !</h1>
            <p>Merci pour ta confiance ! Nous avons bien reçu ton paiement.</p>
            
            <div class="info">
                <p><strong>📋 Étape suivante :</strong></p>
                <p>Clique sur le bouton ci-dessous pour lancer la génération de ton Point Astral personnalisé.</p>
            </div>
            
            <div class="buttons">
                <a href="/afficher_point_astral" target="_blank" class="btn">
                    🔮 Générer mon Point Astral
                </a>
                <br>
                <a href="/" class="btn btn-secondary">
                    ← Retour aux analyses
                </a>
            </div>
            
            <p style="font-size: 14px; color: #888;">
                ⏱️ La génération prendra quelques minutes<br>
                📂 Ton analyse s'ouvrira dans un nouvel onglet<br>
                📧 Tu recevras aussi le PDF par email
            </p>
        </div>
    </body>
    </html>
    """
    
    return html_confirmation

# ─────────────────────────────────────────────────────────────────────────────
# NOUVELLE ROUTE : PayPal
# ─────────────────────────────────────────────────────────────────────────────

@checkout_bp.route('/create-paypal-payment', methods=['POST'])
def create_paypal_payment():
    # Stocker les mêmes infos qu'avec Stripe
    session['infos_utilisateur'] = {
        "nom": request.form.get("nom"),
        "email": request.form.get("email"),
        "date_naissance": request.form.get("date_naissance"),
        "heure_naissance": request.form.get("heure_naissance"),
        "lieu_naissance": request.form.get("lieu_naissance"),
        "lat": request.form.get("lat"),
        "lon": request.form.get("lon"),
        "tzid": request.form.get("tzid"),
        "gender": request.form.get("gender"),
        "type_commande": request.form.get("type_commande"),
        "items": request.form.get("items"),
        "total": request.form.get("total")
    }
    
    # TODO: Implémenter PayPal SDK ici
    # Pour l'instant, redirection temporaire
    return redirect(url_for('checkout_bp.paiement_effectue'))