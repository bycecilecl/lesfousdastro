# utils/google/sheets_writer.py
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
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

     # 🕒 Ajout date/heure
    now = datetime.now(ZoneInfo("Europe/Paris"))
    date = now.strftime("%Y-%m-%d")
    heure = now.strftime("%H:%M:%S")

    sheet.append_row([email, nom, date, heure])
    print(f"✅ Email ajouté à Google Sheet : {email}, {nom}, {date}, {heure}")

    # --- Placements -> Google Sheets (onglet "placements") -----------------------

def _get_spreadsheet(client):
    """Ouvre la feuille soit par ID (si SHEETS_SPREADSHEET_ID), soit par titre."""
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    spreadsheet_title = os.getenv("SHEETS_SPREADSHEET_TITLE", "mailing_list_astro")
    return client.open_by_key(spreadsheet_id) if spreadsheet_id else client.open(spreadsheet_title)

def _get_or_create_worksheet(sh, title="placements", rows=1000, cols=40):
    try:
        return sh.worksheet(title)
    except Exception:
        # crée l’onglet s’il n’existe pas
        return sh.add_worksheet(title=title, rows=str(rows), cols=str(cols))

def ajouter_placements_au_sheet(donnees: dict):
    """
    Push une ligne dans l’onglet 'placements'.
    -> Crée l’onglet si besoin
    -> Ajoute l’en-tête si vide
    -> Log très détaillé pour comprendre ce qui se passe en prod
    """
    if not isinstance(donnees, dict) or not donnees:
        print("❌ [PLACEMENTS] donnees invalide (pas un dict non vide).")
        return

    client = _get_client()
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    spreadsheet_title = os.getenv("SHEETS_SPREADSHEET_TITLE", "mailing_list_astro")

    # Ouvrir le spreadsheet (ID prioritaire)
    if spreadsheet_id:
        print(f"🔎 [PLACEMENTS] Ouverture par ID: {spreadsheet_id}")
        sh = client.open_by_key(spreadsheet_id)
    else:
        print(f"🔎 [PLACEMENTS] Ouverture par Titre: {spreadsheet_title}")
        sh = client.open(spreadsheet_title)

    # Récupérer ou créer l’onglet 'placements'
    try:
        ws = sh.worksheet("placements")
        print("ℹ️ [PLACEMENTS] Onglet 'placements' trouvé.")
    except Exception:
        print("ℹ️ [PLACEMENTS] Onglet 'placements' absent -> création.")
        ws = sh.add_worksheet(title="placements", rows="1000", cols="50")

    # Lire l’existant pour savoir si on doit écrire l’en-tête
    existing = ws.get_all_values()
    headers = list(donnees.keys())
    print(f"ℹ️ [PLACEMENTS] Colonnes à écrire: {len(headers)} -> {headers[:6]}{' ...' if len(headers)>6 else ''}")

    if not existing:
        print("ℹ️ [PLACEMENTS] Onglet vide -> écriture de l'en-tête.")
        ws.append_row(headers)

    # Écrire la ligne
    row = [str(donnees.get(k, "")) for k in headers]
    ws.append_row(row)
    print("✅ [PLACEMENTS] Ligne ajoutée dans Google Sheets (onglet 'placements').")