# routes/stripe_webhook.py
import os
import stripe
from flask import Blueprint, request, jsonify

stripe_webhook_bp = Blueprint("stripe_webhook", __name__)
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@stripe_webhook_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # Mode neutre : on loggue juste
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"[WEBHOOK] checkout.session.completed reçu: {session.get('id')}")

    return jsonify({"ok": True}), 200