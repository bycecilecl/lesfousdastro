# ─────────────────────────────────────────────────────────────────────────────
# UTIL : envoyer_email_avec_analyse()
# Rôle : envoie un email (HTML) au destinataire via yagmail, avec option de PDF
#        en pièce jointe.
# Entrées :
#   - destinataire (str) : adresse email de réception
#   - sujet (str)        : sujet du message
#   - contenu_html (str) : corps du mail en HTML
#   - pdf_path (str|None): chemin du PDF à joindre (optionnel)
# Dépendances :
#   - Variables d’environnement chargées via .env :
#       EMAIL_ENVOI   → adresse expéditrice (ex : ton Gmail)
#       EMAIL_PASSWORD→ mot de passe applicatif (Gmail : “App Password”)
#   - yagmail (SMTP simplifié)
# Sortie : log console “✅ Email envoyé …” ou message d’erreur.
# Où c’est utilisé :
#   - Analyse gratuite : envoi du texte généré à l’utilisateur
#   - Point Astral (route afficher_point_astral) : envoi du lien de téléchargement PDF
# Remarques :
#   - Si tu utilises Gmail : nécessite un “mot de passe d’application”.
#   - `attachments` n’est ajouté que si `pdf_path` est fourni.
# ─────────────────────────────────────────────────────────────────────────────

# import yagmail
# import os
# from dotenv import load_dotenv

# load_dotenv()

# def envoyer_email_avec_analyse(destinataire, sujet, contenu_html, pdf_path=None):
#     email_exp = os.getenv("EMAIL_ENVOI")
#     mdp_app = os.getenv("EMAIL_PASSWORD")

#     try:
#         yag = yagmail.SMTP(user=email_exp, password=mdp_app)

#         attachments = [pdf_path] if pdf_path else None

#         yag.send(
#             to=destinataire,
#             subject=sujet,
#             contents=contenu_html,
#             attachments=attachments
#         )

#         print(f"✅ Email envoyé à {destinataire}")

#     except Exception as e:
#         print(f"❌ Erreur lors de l'envoi de l'email à {destinataire} : {e}")

import os
import re
import html as htmllib
import yagmail
from dotenv import load_dotenv

load_dotenv()

def _html_to_plain(html_str: str) -> str:
    """Fallback très simple pour générer un texte brut depuis du HTML."""
    if not html_str:
        return ""
    # unescape & remplacements basiques de sauts de ligne
    s = htmllib.unescape(html_str)
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    # retirer toutes les balises
    s = re.sub(r"<[^>]+>", "", s)
    # normaliser espaces
    s = re.sub(r"[ \t]+\n", "\n", s).strip()
    return s

def envoyer_email_avec_analyse(destinataire: str,
                               sujet: str,
                               contenu_txt: str | None = None,
                               contenu_html: str | None = None,
                               pdf_path: str | None = None):
    """
    Envoie un email multipart/alternative.
    - rétro-compatible : si contenu_txt est None mais contenu_html est fourni,
      on génère un TXT automatiquement.
    """
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app   = os.getenv("EMAIL_PASSWORD")

    try:
        yag = yagmail.SMTP(user=email_exp, password=mdp_app)

        # Fallback si on n'a que du HTML
        if contenu_txt is None and contenu_html:
            contenu_txt = _html_to_plain(contenu_html)

        # Sécurité : au moins un contenu
        if not (contenu_txt or contenu_html):
            contenu_txt = "Bonjour,\n\nVotre document est prêt."

        contents = []
        contents.append(contenu_txt or "")
        if contenu_html:
            contents.append(yagmail.raw(contenu_html))

        attachments = [pdf_path] if pdf_path else None

        yag.send(
            to=destinataire,
            subject=sujet,
            contents=contents,
            attachments=attachments,
            headers={"From": f"Les Fous d’Astro <{email_exp}>"}
        )
        print(f"✅ Email envoyé à {destinataire}")

    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email à {destinataire} : {e}")