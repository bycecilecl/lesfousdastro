# utils/google/sheets_writer.py
import os
from dotenv import load_dotenv
load_dotenv()

try:
    import gspread
except Exception as e:
    gspread = None
    _IMPORT_ERR = e

credentials_path = (
    "/app/utils/google/credentials.json"
    if os.getenv("RAILWAY_ENVIRONMENT")
    else os.getenv("GOOGLE_CREDENTIALS_PATH") or "utils/google/credentials.json"
)

def ajouter_email_au_sheet(email, nom="Inconnu"):
    if gspread is None:
        raise ImportError(f"Google Sheets indisponible: {_IMPORT_ERR}")

    client = gspread.service_account(filename=credentials_path)  # utilise google-auth
    sheet = client.open("mailing_list_astro").sheet1
    sheet.append_row([email, nom])