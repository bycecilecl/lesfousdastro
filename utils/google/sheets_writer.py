# utils/google/sheets_writer.py
import os, json
from dotenv import load_dotenv
load_dotenv()

try:
    import gspread
except Exception as e:
    gspread = None
    _IMPORT_ERR = e

# ID de la feuille (prioritaire en prod)
SPREADSHEET_ID = os.getenv("SHEETS_SPREADSHEET_ID")  # ex: 1AbCdEf... (entre /d/ et /edit)
SPREADSHEET_TITLE = os.getenv("SHEETS_SPREADSHEET_TITLE", "mailing_list_astro")

def _get_client():
    """Choisit automatiquement la bonne méthode de credentials.
       - PROD (Railway) : GOOGLE_CREDS_JSON (contenu JSON complet)
       - LOCAL : chemin de fichier (GOOGLE_CREDENTIALS_PATH ou utils/google/credentials.json)
    """
    if gspread is None:
        raise ImportError(f"Google Sheets indisponible: {_IMPORT_ERR}")

    creds_json = os.getenv("GOOGLE_CREDS_JSON")  # VAR déjà présente sur Railway chez toi
    if creds_json:
        data = json.loads(creds_json)
        return gspread.service_account_from_dict(data)

    path = os.getenv("GOOGLE_CREDENTIALS_PATH", "utils/google/credentials.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Credentials introuvables : {path}")
    return gspread.service_account(filename=path)

def ajouter_email_au_sheet(email, nom="Inconnu"):
    if not email:
        raise ValueError("Email vide")

    client = _get_client()

    # Ouvrir par ID si dispo (plus robuste), sinon par titre (legacy)
    if SPREADSHEET_ID:
        sh = client.open_by_key(SPREADSHEET_ID)
    else:
        sh = client.open(SPREADSHEET_TITLE)

    sheet = sh.sheet1
    sheet.append_row([email, nom])
    print(f"✅ Email ajouté à Google Sheet : {email}, {nom}")