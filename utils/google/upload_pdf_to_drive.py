# utils/drive_uploader.py

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
from dotenv import load_dotenv

load_dotenv()

def upload_pdf_to_drive(pdf_path, nom_fichier):
    try:
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/drive']
        )

        service = build('drive', 'v3', credentials=creds)

        # Lire le dossier Drive depuis .env
        folder_id = os.getenv("DRIVE_FOLDER_ID")

        file_metadata = {
            'name': nom_fichier,
            'mimeType': 'application/pdf',
            'parents': [folder_id] if folder_id else []  # Ajout ici
        }

        media = MediaFileUpload(pdf_path, mimetype='application/pdf')

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = uploaded_file.get('id')

        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    except Exception as e:
        print(f"❌ Erreur d'upload sur Google Drive : {e}")
        return None