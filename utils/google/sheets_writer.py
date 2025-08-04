import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

# Charge les variables d’environnement (.env)
load_dotenv()

# ✅ Détermine dynamiquement le bon chemin vers credentials.json
credentials_path = (
    "/app/utils/google/credentials.json"
    if os.getenv("RAILWAY_ENVIRONMENT")
    else os.getenv("GOOGLE_CREDENTIALS_PATH") or "utils/google/credentials.json"
)

def ajouter_email_au_sheet(email, nom="Inconnu"):
    # Scopes d’accès aux Google Sheets et Drive
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Crée l’objet d’identification
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)

    # Ouvre ton Google Sheet
    sheet = client.open("mailing_list_astro").sheet1  # Change le nom si besoin

    # Ajoute une ligne
    sheet.append_row([email, nom])

    print(f"✅ Ajouté dans Google Sheet : {nom} - {email}", flush=True)