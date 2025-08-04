import yagmail
import os
from dotenv import load_dotenv

load_dotenv()

def envoyer_email_avec_analyse(destinataire, sujet, contenu_html, pdf_path=None):
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app = os.getenv("EMAIL_PASSWORD")

    try:
        yag = yagmail.SMTP(user=email_exp, password=mdp_app)

        attachments = [pdf_path] if pdf_path else None

        yag.send(
            to=destinataire,
            subject=sujet,
            contents=contenu_html,
            attachments=attachments
        )

        print(f"✅ Email envoyé à {destinataire}", flush=True)

    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email à {destinataire} : {e}", flush=True)