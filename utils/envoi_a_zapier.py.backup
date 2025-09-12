import os
import requests
from dotenv import load_dotenv

# Charge le fichier .env
load_dotenv(dotenv_path="clé_api.env")  # ou .env si c'est le nom que tu utilises

def envoyer_a_zapier(form_data):
    zapier_webhook_url = os.getenv("ZAPIER_WEBHOOK_URL")

    if not zapier_webhook_url:
        raise ValueError("❌ ZAPIER_WEBHOOK_URL non défini dans clé_api.env")

    data = {
        "email": form_data.get("email"),
        "nom": form_data.get("nom"),
        "date_naissance": form_data.get("date_naissance")
    }

    response = requests.post(zapier_webhook_url, json=data)
    response.raise_for_status()
    print("📨 Données envoyées à Zapier :", data)