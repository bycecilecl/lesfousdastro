"""Offre de lancement et PayPal Orders. Aucun appel externe à l’import."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os
from uuid import uuid4

from utils.mails_evenements import _donnees_profil
from utils.invitations_beta import OFFRE_BETA, verifier_invitation_beta

OFFRE = OFFRE_BETA
PRIX_CENTIMES = 3500
FORMULES_BETA = {
    "espace_seul": {"prix_centimes": 3500, "prix": "35", "libelle": "Trois mois d’espace abonné", "avec_rs": False},
    "espace_et_rs": {"prix_centimes": 7400, "prix": "74", "libelle": "Trois mois d’espace abonné + une Révolution Solaire", "avec_rs": True},
}
CGV_VERSION = "lancement_2026_11_trois_mois_activation"


def formule_commande(commande):
    for code, formule in FORMULES_BETA.items():
        if commande.montant_centimes == formule["prix_centimes"]:
            return {"code": code, **formule}
    raise ValueError("Le montant de cette commande ne correspond à aucune formule bêta.")


def configuration_paiement():
    mode = os.getenv("PAYPAL_ABONNEMENTS_MODE", "sandbox").lower()
    production = bool(os.getenv("RAILWAY_ENVIRONMENT_ID")) or os.getenv("APP_ENV") == "production"
    ouvert = os.getenv("ABONNEMENTS_OUVERTS", "0") == "1"
    if mode not in {"sandbox", "live"} or (production and mode != "live"):
        return {"ouvert": False, "sandbox": True, "client_id": "", "base": ""}
    suffixe = "SANDBOX" if mode == "sandbox" else "LIVE"
    client = os.getenv("PAYPAL_CLIENT_ID_" + suffixe, "").strip()
    secret = os.getenv("PAYPAL_CLIENT_SECRET_" + suffixe, "").strip()
    if mode == "live" and not os.getenv("PAYPAL_WEBHOOK_ID_ABONNEMENTS"):
        ouvert = False
    return {"ouvert": ouvert and bool(client and secret), "sandbox": mode == "sandbox",
            "client_id": client, "base": "https://api-m.sandbox.paypal.com" if mode == "sandbox" else "https://api-m.paypal.com"}


def offre_publique():
    return {"prix": "35", "formules": FORMULES_BETA, "duree_mois": 3,
            "demarrage": "activation", "paiement": configuration_paiement()}


def verifier_preparation(utilisateur):
    from models.espace_personnel import ProfilAstral
    if not utilisateur or not utilisateur.actif:
        raise ValueError("Le compte est indisponible.")
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if not profil:
        raise ValueError("Complète ton profil astral avant de continuer.")
    _donnees_profil(profil)
    if utilisateur.journal_mails_choix_le is None:
        raise ValueError("Choisis si tu souhaites utiliser ton journal dans les mails. Oui ou non : les deux permettent de continuer.")
    return profil


def _jeton(config):
    import requests
    from requests.auth import HTTPBasicAuth
    suffixe = "SANDBOX" if config["sandbox"] else "LIVE"
    reponse = requests.post(config["base"] + "/v1/oauth2/token", timeout=15,
        auth=HTTPBasicAuth(config["client_id"], os.environ["PAYPAL_CLIENT_SECRET_"+suffixe].strip()),
        data={"grant_type": "client_credentials"}, headers={"Accept": "application/json"})
    reponse.raise_for_status()
    jeton = reponse.json().get("access_token")
    if not jeton:
        raise ValueError("Connexion au paiement indisponible.")
    return jeton


def _requete(config, methode, chemin, *, cle=None, donnees=None):
    import requests
    entetes = {"Authorization": "Bearer " + _jeton(config), "Content-Type": "application/json"}
    if chemin.startswith("/v2/checkout/orders"):
        entetes["Prefer"] = "return=representation"  # Les contrôles exigent les montants et références.
    if cle:
        entetes["PayPal-Request-Id"] = cle
    reponse = requests.request(methode, config["base"]+chemin, headers=entetes, json=donnees, timeout=20)
    reponse.raise_for_status()
    return {} if reponse.status_code == 204 else reponse.json()


def _configuration_ouverte():
    config = configuration_paiement()
    if not config["ouvert"]:
        raise ValueError("La souscription n’est pas encore ouverte.")
    return config


def _modifier_commande(commande, selection, config):
    """Révise une commande non réglée, en excluant toute capture simultanée."""
    from sqlalchemy import update
    from extensions import db
    from models.espace_personnel import CommandeAbonnementEspace
    identifiant = commande.fournisseur_commande_id
    reservation = db.session.execute(update(CommandeAbonnementEspace).where(
        CommandeAbonnementEspace.id == commande.id,
        CommandeAbonnementEspace.fournisseur_commande_id == identifiant,
        CommandeAbonnementEspace.statut.in_(("prete", "modification_incertaine")),
    ).values(statut="modification_en_cours"))
    db.session.commit()
    if reservation.rowcount != 1:
        raise ValueError("Le paiement est déjà en cours. Recharge la page pour vérifier son état.")
    chemin = "/v2/checkout/orders/" + identifiant
    try:
        resultat = _requete(config, "GET", chemin)
        unites = resultat.get("purchase_units") or []
        if (resultat.get("id") != identifiant or resultat.get("status") not in {"CREATED", "APPROVED"}
                or len(unites) != 1 or unites[0].get("reference_id") != commande.id
                or unites[0].get("custom_id") != commande.id or unites[0].get("payments")):
            raise ValueError("Cette commande ne peut plus être modifiée.")
        montant = {"currency_code": "EUR", "value": f"{selection['prix_centimes'] / 100:.2f}"}
        description = selection["libelle"] + " — décembre 2026 à février 2027"
        cible = "/purchase_units/@reference_id=='" + commande.id + "'"
        _requete(config, "PATCH", chemin, donnees=[
            {"op": "replace", "path": cible + "/amount", "value": montant},
            {"op": "replace", "path": cible + "/description", "value": description},
        ])
        resultat = _requete(config, "GET", chemin)
        unites = resultat.get("purchase_units") or []
        if (resultat.get("id") != identifiant or resultat.get("status") not in {"CREATED", "APPROVED"}
                or len(unites) != 1 or unites[0].get("reference_id") != commande.id
                or unites[0].get("custom_id") != commande.id or unites[0].get("payments")
                or (unites[0].get("amount") or {}).get("currency_code") != "EUR"
                or Decimal(str((unites[0].get("amount") or {}).get("value"))) * 100 != selection["prix_centimes"]):
            raise ValueError("Le nouveau montant n’est pas confirmé.")
        commande.montant_centimes = selection["prix_centimes"]
        commande.cgv_version, commande.cgv_acceptees_le = CGV_VERSION, datetime.now(timezone.utc)
        commande.statut, commande.erreur = "prete", None
        db.session.commit()
        return commande
    except Exception:
        db.session.rollback()
        commande.statut = "modification_incertaine"
        commande.erreur = "Le changement d’option reste à confirmer. Aucun nouveau débit demandé."
        db.session.commit()
        raise ValueError("Le changement d’option n’a pas été confirmé. Recharge la page puis réessaie. Si tu as déjà payé, utilise « Vérifier mon paiement ».") from None


def creer_commande(utilisateur, accepter, formule="espace_seul"):
    from extensions import db
    from models.espace_personnel import CommandeAbonnementEspace, InscriptionMailsBeta
    verifier_invitation_beta(utilisateur)
    verifier_preparation(utilisateur)
    config = _configuration_ouverte()
    if not accepter:
        raise ValueError("Accepte les conditions de l’offre avant de continuer.")
    if formule not in FORMULES_BETA:
        raise ValueError("Choisis l’espace seul ou le pack avec une Révolution Solaire.")
    selection = FORMULES_BETA[formule]
    inscription = db.session.get(InscriptionMailsBeta, utilisateur.id)
    if inscription and inscription.actif:
        raise ValueError("Tu es déjà inscrit à cette période. Aucun nouveau paiement nécessaire.")
    commande = CommandeAbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id, offre=OFFRE, sandbox=config["sandbox"]).first()
    if commande:
        if commande.statut in {"prete", "modification_incertaine"} and commande.fournisseur_commande_id:
            commande.cgv_version, commande.cgv_acceptees_le = CGV_VERSION, datetime.now(timezone.utc)
            db.session.commit()
            if commande.montant_centimes != selection["prix_centimes"] or commande.statut == "modification_incertaine":
                return _modifier_commande(commande, selection, config)
            return commande
        raise ValueError("Une commande existe déjà : utilise « Vérifier mon paiement » dans ton abonnement avant de recommencer.")
    commande = CommandeAbonnementEspace(id=str(uuid4()), utilisateur_id=utilisateur.id,
        offre=OFFRE, montant_centimes=selection["prix_centimes"], devise="EUR", sandbox=config["sandbox"],
        statut="creation_en_cours", cgv_version=CGV_VERSION, cgv_acceptees_le=datetime.now(timezone.utc))
    db.session.add(commande)
    db.session.commit()  # Contrainte unique : un seul parcours d’achat par compte/offre/mode.
    try:
        resultat = _requete(config, "POST", "/v2/checkout/orders", cle=commande.id,
            donnees={"intent": "CAPTURE", "purchase_units": [{"reference_id": commande.id,
                "custom_id": commande.id, "description": selection["libelle"] + " — décembre 2026 à février 2027",
                "amount": {"currency_code": "EUR", "value": f"{commande.montant_centimes / 100:.2f}"}}],
                "payment_source": {"paypal": {"experience_context": {"shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW"}}}})
        identifiant = resultat.get("id")
        if not identifiant:
            raise ValueError("Réponse de paiement incomplète.")
        commande.fournisseur_commande_id, commande.statut = identifiant, "prete"
        db.session.commit()
        return commande
    except Exception:
        db.session.rollback()
        commande.statut, commande.erreur = "creation_incertaine", "Création non confirmée. Aucun accès payant accordé. Vérification nécessaire avant un nouvel achat."
        db.session.commit()
        raise ValueError("Le paiement n’a pas pu être préparé. Aucun paiement confirmé ; contacte Cécile avant de recommencer.") from None


def _verifier_capture(commande, resultat):
    if resultat.get("id") != commande.fournisseur_commande_id or resultat.get("status") != "COMPLETED":
        raise ValueError("Le paiement n’est pas confirmé.")
    unites = resultat.get("purchase_units") or []
    if len(unites) != 1 or unites[0].get("custom_id") != commande.id or unites[0].get("reference_id") != commande.id:
        raise ValueError("La référence du paiement est incorrecte.")
    captures = (unites[0].get("payments") or {}).get("captures") or []
    if len(captures) != 1 or captures[0].get("status") != "COMPLETED" or not captures[0].get("id"):
        raise ValueError("Le paiement n’est pas définitivement confirmé.")
    montant = captures[0].get("amount") or {}
    try:
        valeur = Decimal(str(montant.get("value"))) * 100
        formule_commande(commande)
        if montant.get("currency_code") != commande.devise or commande.devise != "EUR" or valeur != commande.montant_centimes:
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Le montant du paiement ne correspond pas à l’offre.") from None
    marchand = os.getenv("PAYPAL_MERCHANT_ID_ABONNEMENTS")
    if marchand and (unites[0].get("payee") or {}).get("merchant_id") != marchand:
        raise ValueError("Le destinataire du paiement ne correspond pas.")
    return captures[0]["id"]


def enregistrer_paiement(commande_id, resultat):
    """Capture vérifiée, puis accès et inscription, dans la même transaction locale."""
    from sqlalchemy import select
    from extensions import db
    from models.espace_personnel import AbonnementEspace, CommandeAbonnementEspace, RevolutionSolairePackBeta, UtilisateurEspace
    from utils.mails_evenements import inscrire_beta
    commande = db.session.execute(select(CommandeAbonnementEspace).where(CommandeAbonnementEspace.id == commande_id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    capture = _verifier_capture(commande, resultat)
    if commande.statut == "active":
        return commande
    if commande.statut in {"rembourse", "revoque"}:
        raise ValueError("Cet achat a été annulé.")
    commande.fournisseur_paiement_id = capture
    commande.date_paiement = commande.date_paiement or datetime.now(timezone.utc)
    commande.statut = "payee"
    if formule_commande(commande)["avec_rs"] and db.session.get(RevolutionSolairePackBeta, commande.id) is None:
        db.session.add(RevolutionSolairePackBeta(commande_id=commande.id, utilisateur_id=commande.utilisateur_id, statut="a_preparer"))
    utilisateur = db.session.get(UtilisateurEspace, commande.utilisateur_id)
    try:
        verifier_preparation(utilisateur)
        inscription = inscrire_beta(utilisateur)
    except ValueError:
        commande.erreur = "Paiement confirmé. Complète ton profil pour activer ton accès, sans payer à nouveau."
    else:
        abonnement = AbonnementEspace.query.filter_by(utilisateur_id=utilisateur.id).one()
        abonnement.source = "paypal:" + commande.id
        commande.statut, commande.date_activation, commande.erreur = "active", inscription.debut, None
    db.session.commit()
    return commande


def verifier_ou_capturer(commande, *, capturer=False, montant_attendu=None):
    from sqlalchemy import update
    from extensions import db
    from models.espace_personnel import CommandeAbonnementEspace, UtilisateurEspace
    config = configuration_paiement()
    if config["sandbox"] != commande.sandbox or not config["client_id"]:
        raise ValueError("Le mode du paiement ne correspond plus à la configuration.")
    if commande.statut == "active":
        return commande
    if capturer and (montant_attendu is None or montant_attendu != commande.montant_centimes):
        raise ValueError("L’option a changé depuis la préparation du paiement. Recharge la page avant de payer.")
    if not commande.fournisseur_commande_id:
        raise ValueError("Cette commande nécessite une vérification par Cécile.")
    chemin = "/v2/checkout/orders/" + commande.fournisseur_commande_id
    if capturer and commande.statut == "prete":
        verifier_invitation_beta(db.session.get(UtilisateurEspace, commande.utilisateur_id))
        _configuration_ouverte()
        reservation = db.session.execute(update(CommandeAbonnementEspace).where(
            CommandeAbonnementEspace.id == commande.id, CommandeAbonnementEspace.statut == "prete",
            CommandeAbonnementEspace.fournisseur_commande_id == commande.fournisseur_commande_id,
            CommandeAbonnementEspace.montant_centimes == montant_attendu,
        ).values(statut="capture_en_cours"))
        db.session.commit()
        if reservation.rowcount != 1:
            raise ValueError("Paiement déjà en cours. Vérifie son état depuis ton abonnement.")
        try:
            resultat = _requete(config, "POST", chemin+"/capture", cle="capture-"+commande.id, donnees={})
        except Exception:
            db.session.rollback()
            commande.statut, commande.erreur = "capture_incertaine", "Vérifie le paiement ; aucun second débit automatique."
            db.session.commit()
            raise ValueError("La confirmation n’a pas abouti. Utilise « Vérifier mon paiement » ; ne paie pas une seconde fois.") from None
    else:
        resultat = _requete(config, "GET", chemin)  # Contrôle seulement, jamais de débit.
    return enregistrer_paiement(commande.id, resultat)


def traiter_notification_paypal(entetes, evenement):
    """Authentifie chez PayPal, puis relit l’achat ; aucune confiance au navigateur."""
    from sqlalchemy import or_, select
    from extensions import db
    from models.espace_personnel import AbonnementEspace, CommandeAbonnementEspace, InscriptionMailsBeta
    config = configuration_paiement()
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID_ABONNEMENTS", "")
    if not webhook_id or not config["client_id"]:
        raise ValueError("Notifications PayPal non configurées.")
    verification = _requete(config, "POST", "/v1/notifications/verify-webhook-signature", donnees={
        "auth_algo": entetes.get("PAYPAL-AUTH-ALGO"), "cert_url": entetes.get("PAYPAL-CERT-URL"),
        "transmission_id": entetes.get("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": entetes.get("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": entetes.get("PAYPAL-TRANSMISSION-TIME"),
        "webhook_id": webhook_id, "webhook_event": evenement})
    if verification.get("verification_status") != "SUCCESS":
        raise ValueError("Notification non authentifiée.")
    nature = evenement.get("event_type")
    if nature not in {"PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"}:
        return "ignore"
    ressource = evenement.get("resource") or {}
    liens = (ressource.get("supplementary_data") or {}).get("related_ids") or {}
    criteres = []
    if liens.get("order_id"):
        criteres.append(CommandeAbonnementEspace.fournisseur_commande_id == liens["order_id"])
    capture_id = liens.get("capture_id") or (ressource.get("id") if nature != "PAYMENT.CAPTURE.REFUNDED" else None)
    if capture_id:
        criteres.append(CommandeAbonnementEspace.fournisseur_paiement_id == capture_id)
    if not criteres:
        return "autre_paiement"
    commande = CommandeAbonnementEspace.query.filter(or_(*criteres), CommandeAbonnementEspace.sandbox == config["sandbox"]).first()
    if commande is None:
        return "autre_paiement"
    if nature == "PAYMENT.CAPTURE.COMPLETED":
        if commande.statut in {"rembourse", "revoque"}:
            return "deja_annule"
        return verifier_ou_capturer(commande).statut
    if not commande.fournisseur_paiement_id:
        raise ValueError("Capture à vérifier avant d’annuler l’accès.")
    etat = _requete(config, "GET", "/v2/payments/captures/"+commande.fournisseur_paiement_id)
    if etat.get("id") != commande.fournisseur_paiement_id:
        raise ValueError("Capture différente de l’achat enregistré.")
    annuler = etat.get("status") == "REFUNDED" or (nature == "PAYMENT.CAPTURE.REVERSED" and capture_id == commande.fournisseur_paiement_id)
    if not annuler:
        return "remboursement_partiel_ou_en_attente"
    commande = db.session.execute(select(CommandeAbonnementEspace).where(CommandeAbonnementEspace.id == commande.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    commande.statut = "rembourse" if nature == "PAYMENT.CAPTURE.REFUNDED" else "revoque"
    abonnement = AbonnementEspace.query.filter_by(utilisateur_id=commande.utilisateur_id).first()
    if abonnement and abonnement.source == "paypal:"+commande.id:
        abonnement.statut, abonnement.date_fin = "inactif", datetime.now(timezone.utc)
        inscription = db.session.get(InscriptionMailsBeta, commande.utilisateur_id)
        if inscription:
            inscription.actif = False
    db.session.commit()
    return commande.statut
