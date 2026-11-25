"""Ouverture de PayPal en pleine page, sans accès accordé par le navigateur."""
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _signature():
    if not current_app.secret_key:
        raise RuntimeError("La signature du retour de paiement est indisponible.")
    return URLSafeTimedSerializer(current_app.secret_key, salt="paypal-espace-pleine-page-v1")


def lire_retour(etat, utilisateur_id):
    """Le retour est lié au membre, à la commande et au montant choisis."""
    try:
        donnees = _signature().loads(etat, max_age=10800)
    except (BadSignature, SignatureExpired):
        raise ValueError("Le lien de retour a expiré ou est invalide. Vérifie ton paiement depuis Mon abonnement.") from None
    if not isinstance(donnees, dict) or donnees.get("utilisateur") != utilisateur_id:
        raise ValueError("Reconnecte-toi au compte utilisé pour ce paiement.")
    if not all(donnees.get(cle) for cle in ("commande", "paypal", "montant")):
        raise ValueError("Le retour de paiement est incomplet.")
    return donnees


def preparer_redirection(commande):
    """Réutilise la commande existante ; ne capture et ne débite rien."""
    from utils.souscription_espace import _configuration_ouverte, _requete

    config = _configuration_ouverte()
    if commande.sandbox != config["sandbox"] or commande.statut != "prete":
        raise ValueError("Vérifie le paiement dans Mon abonnement avant de recommencer.")
    chemin = "/v2/checkout/orders/" + commande.fournisseur_commande_id
    resultat = _requete(config, "GET", chemin)
    unites = resultat.get("purchase_units") or []
    if (resultat.get("id") != commande.fournisseur_commande_id
            or resultat.get("status") not in {"CREATED", "APPROVED", "PAYER_ACTION_REQUIRED"}
            or len(unites) != 1 or unites[0].get("reference_id") != commande.id
            or unites[0].get("custom_id") != commande.id or unites[0].get("payments")):
        raise ValueError("Cette commande doit être vérifiée depuis Mon abonnement. Ne paie pas une seconde fois.")
    montant = unites[0].get("amount") or {}
    try:
        conforme = (montant.get("currency_code") == commande.devise == "EUR"
                    and Decimal(str(montant.get("value"))) * 100 == commande.montant_centimes)
    except (InvalidOperation, TypeError, ValueError):
        conforme = False
    if not conforme:
        raise ValueError("L’option ou le montant a changé. Recharge la page avant de continuer.")
    etat = _signature().dumps({"utilisateur": commande.utilisateur_id, "commande": commande.id,
                               "paypal": commande.fournisseur_commande_id, "montant": commande.montant_centimes})
    # PayPal permet de préciser les URL d'une commande déjà créée via cette étape.
    # Cela couvre aussi les commandes commencées auparavant dans la fenêtre SDK.
    resultat = _requete(config, "POST", chemin + "/confirm-payment-source", donnees={
        "payment_source": {"paypal": {"experience_context": {
            "shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW",
            "return_url": url_for("abonnement_client.retour_paypal", etat=etat, _external=True),
            "cancel_url": url_for("abonnement_client.annuler_paypal", _external=True),
        }}}
    })
    if resultat.get("id") != commande.fournisseur_commande_id:
        raise ValueError("La page de paiement n’a pas pu être préparée.")
    hote = "www.sandbox.paypal.com" if config["sandbox"] else "www.paypal.com"
    for lien in resultat.get("links") or []:
        if lien.get("rel") not in {"payer-action", "approve"} or lien.get("method", "GET") != "GET":
            continue
        adresse = lien.get("href", "")
        cible = urlsplit(adresse)
        if (cible.scheme == "https" and cible.netloc == hote
                and parse_qs(cible.query).get("token") == [commande.fournisseur_commande_id]):
            return adresse
    raise ValueError("PayPal n’a pas fourni de page de paiement. Vérifie ton abonnement avant de recommencer.")
