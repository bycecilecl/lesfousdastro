import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

# Charge les variables d’environnement
load_dotenv()

# Utiliser la variable d'environnement pour le chemin du credentials.json
credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")

if not credentials_path:
    # Fallback si la variable n’est pas définie : on cherche dans utils/google/
    credentials_path = os.path.join(os.path.dirname(__file__), "utils", "google", "credentials.json")

def ajouter_email_au_sheet(email, nom="Inconnu"):
    # Scopes d’accès aux Google Sheets et Drive
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Crée l’objet d’identification
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)

    # Ouvre ton Google Sheet
    sheet = client.open("mailing_list_astro").sheet1  # Change éventuellement ici le nom du fichier/onglet

    # Ajoute une ligne
    sheet.append_row([email, nom])

    print(f"✅ Ajouté dans Google Sheet : {nom} - {email}")