"""Prévenir la cliente et l'équipe quand une analyse payée reste à vérifier."""

import os


def notifier_generation_interrompue(*, commande_id, produit, email_client, nom_client,
                                    sender=None):
    if sender is None:
        from utils.email_sender import envoyer_email_avec_analyse
        sender = envoyer_email_avec_analyse

    nom_produit = {
        "forces_defis": "Mes Potentiels & Défis",
        "revolution_solaire": "Ma Révolution Solaire",
    }.get(produit, produit)
    admin = (os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI") or "").strip()
    resultat = {"admin": False, "client": False}

    if admin:
        try:
            resultat["admin"] = bool(sender(
                destinataire=admin,
                sujet=f"À traiter : {nom_produit} non livrée — commande {commande_id}",
                contenu_txt=(
                    f"Une analyse payée n'a pas été livrée automatiquement.\n\n"
                    f"Commande : {commande_id}\n"
                    f"Analyse : {nom_produit}\n"
                    f"Cliente : {nom_client or 'Non renseigné'}\n"
                    f"Adresse : {email_client or 'Non renseignée'}\n\n"
                    "Vérifier la commande et la génération conservée avant toute nouvelle "
                    "tentative ou décision de remboursement."
                ),
            ))
        except Exception:
            pass  # L'échec de l'alerte admin ne doit pas empêcher l'avis client.

    if email_client:
        prenom = (nom_client or "").strip().split(" ")[0] or "toi"
        try:
            resultat["client"] = bool(sender(
                destinataire=email_client,
                sujet=f"Ta commande {nom_produit} : un peu plus de temps est nécessaire",
                contenu_txt=(
                    f"Bonjour {prenom},\n\n"
                    f"Ta commande {nom_produit} est bien enregistrée, mais ton analyse "
                    "n'a pas pu être finalisée automatiquement. Je vais vérifier ce qui s'est "
                    "passé et revenir vers toi avec la suite. Tu n'as rien à repayer.\n\n"
                    "Si tu souhaites me joindre, réponds à ce message ou écris à "
                    "contact@lesfousdastro.fr.\n\n"
                    f"Référence de ta commande : {commande_id}\n\n"
                    "Cécile CL — Les Fous d'Astro"
                ),
            ))
        except Exception:
            pass

    return resultat
