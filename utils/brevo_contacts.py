# utils/brevo_contacts.py

import logging
import os

import requests


logger = logging.getLogger(__name__)


def ajouter_contact_brevo(
    email: str,
    nom: str = "",
    liste: str = "site",
) -> bool:
    """
    Ajoute ou met à jour un contact dans une liste Brevo.

    liste="flash" : analyse gratuite
    liste="site"  : newsletter du site
    """

    api_key = os.getenv("BREVO_API_KEY")

    variables_listes = {
        "flash": "BREVO_LIST_FLASH_ID",
        "site": "BREVO_LIST_SITE_ID",
    }

    variable_liste = variables_listes.get(liste)

    if not variable_liste:
        logger.error("❌ Liste Brevo inconnue : %s", liste)
        return False

    liste_id = os.getenv(variable_liste)

    if not api_key:
        logger.error("❌ BREVO_API_KEY manquante")
        return False

    if not liste_id:
        logger.error("❌ %s manquante", variable_liste)
        return False

    email = (email or "").strip().lower()
    nom = (nom or "").strip()

    if not email:
        logger.error("❌ Adresse email absente pour l'ajout Brevo")
        return False

    payload = {
        "email": email,
        "listIds": [int(liste_id)],
        "updateEnabled": True,
    }

    # Ton attribut Brevo s'appelle bien NOM.
    if nom:
        payload["attributes"] = {
            "NOM": nom,
        }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.brevo.com/v3/contacts",
            headers=headers,
            json=payload,
            timeout=15,
        )

        if response.status_code in (200, 201, 204):
            logger.info(
                "✅ Contact Brevo ajouté à la liste %s : %s",
                liste,
                email,
            )
            return True

        logger.error(
            "❌ Erreur Brevo %s : %s",
            response.status_code,
            response.text,
        )
        return False

    except (TypeError, ValueError):
        logger.exception(
            "❌ Identifiant de liste Brevo invalide dans %s",
            variable_liste,
        )
        return False

    except requests.RequestException:
        logger.exception(
            "❌ Erreur réseau pendant l'ajout du contact Brevo"
        )
        return False