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


import os, json, requests
import yagmail
import logging
import re
import html as htmllib

logger = logging.getLogger(__name__)


def construire_email_analyse(
    prenom: str,
    nom_analyse: str,
    pdf_url: str,
    *,
    possessif: str = "Ton",
    etat: str = "est prêt",
) -> tuple[str, str, str]:
    """Construit l'e-mail commun envoyé avec une analyse téléchargeable."""
    sujet = f"{possessif} {nom_analyse} {etat} ✨"
    contenu_txt = (
        f"Bonjour {prenom},\n\n"
        f"{possessif} {nom_analyse} {etat} ✨\n\n"
        "Merci pour ta confiance !\n"
        f"📄 Télécharger {possessif.lower()} {nom_analyse}\n"
        f"{pdf_url}\n\n"
        "Pense à télécharger le document et à le sauvegarder sur ton appareil. "
        "Si le lien ne s’ouvre pas, copie-colle l’URL dans ton navigateur.\n\n"
        "Envie d’explorer une autre facette de ton thème ?\n"
        "Découvrir toutes les analyses : https://lesfousdastro.fr/analyses\n\n"
        "À très vite,\n"
        "Cécile CL ✨\n"
        "Les Fous d’Astro"
    )
    contenu_html = (
        f"<p>Bonjour {htmllib.escape(prenom)},</p>"
        f"<p>{htmllib.escape(possessif)} <strong>{htmllib.escape(nom_analyse)}</strong> "
        f"{htmllib.escape(etat)} ✨</p>"
        "<p>Merci pour ta confiance !</p>"
        "<div style=\"margin:30px 0;text-align:center;\">"
        f"<a href=\"{htmllib.escape(pdf_url, quote=True)}\" target=\"_blank\" "
        "style=\"display:inline-block;padding:14px 28px;background:#1f628e;color:#ffffff;"
        "border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;\">"
        f"📄 Télécharger {htmllib.escape(possessif.lower())} {htmllib.escape(nom_analyse)}</a></div>"
        "<p>Pense à télécharger le document et à le sauvegarder sur ton appareil. "
        "Si le lien ne s’ouvre pas, copie-colle l’URL dans ton navigateur.</p>"
        "<p><strong>Envie d’explorer une autre facette de ton thème ?</strong><br>"
        "<a href=\"https://lesfousdastro.fr/analyses\" target=\"_blank\">"
        "Découvrir toutes les analyses</a></p>"
        "<p>À très vite,<br>Cécile CL ✨<br>Les Fous d’Astro</p>"
    )
    return sujet, contenu_txt, contenu_html

SMTP_HOST = os.getenv("SMTP_HOST", "node175-eu.n0c.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() in ("1","true","yes")
SMTP_USE_STARTTLS = os.getenv("SMTP_USE_STARTTLS", "false").lower() in ("1","true","yes")


def _send_with_brevo(to_email: str, subject: str, body_txt: str | None, body_html: str | None):
    api_key = os.getenv("BREVO_API_KEY", "")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Les Fous d’Astro")
    if not api_key or not sender_email:
        raise RuntimeError("BREVO_API_KEY ou BREVO_SENDER_EMAIL manquant")

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body_txt or "",
    }
    if body_html:
        payload["htmlContent"] = body_html

    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=20,
    )
    r.raise_for_status()


def _html_to_plain(html_str: str) -> str:
    if not html_str:
        return ""
    s = htmllib.unescape(html_str)
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s).strip()
    return s

def envoyer_email_avec_analyse(destinataire: str,
                               sujet: str,
                               contenu_txt: str | None = None,
                               contenu_html: str | None = None,
                               pdf_path: str | None = None) -> bool:
    
    # ---- NOUVEAU : route vers Brevo en PROD ----
    if os.getenv("EMAIL_PROVIDER", "smtp").lower() == "brevo":
        try:
            if contenu_txt is None and contenu_html:
                contenu_txt = _html_to_plain(contenu_html)
            _send_with_brevo(destinataire, sujet, contenu_txt, contenu_html)
            logger.info("📤 Brevo → email queued to %s", destinataire)
            return True
        except Exception as e:
            logger.exception("❌ Brevo error for %s : %s", destinataire, e)
            return False
    # ---- FIN bloc Brevo ----
    
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app   = os.getenv("EMAIL_PASSWORD")

    if not email_exp or not mdp_app:
        logger.error("🚫 EMAIL_ENVOI ou EMAIL_PASSWORD manquant dans .env")
        return False

    try:
        yag = yagmail.SMTP(
        user=email_exp,
        password=mdp_app,
        host=SMTP_HOST,
        port=SMTP_PORT,
        smtp_ssl=SMTP_USE_SSL,
        smtp_starttls=SMTP_USE_STARTTLS,
        oauth2_file=None,              # ⬅️ coupe l’utilisation du fichier OAuth ~/.yagmail
    )
        logger.info("SMTP → host=%s port=%s ssl=%s starttls=%s user=%s",
                    SMTP_HOST, SMTP_PORT, SMTP_USE_SSL, SMTP_USE_STARTTLS, email_exp)
        
        if contenu_txt is None and contenu_html:
            contenu_txt = _html_to_plain(contenu_html)

        if not (contenu_txt or contenu_html):
            contenu_txt = "Bonjour,\n\nTon document est prêt."

        contents = [contenu_txt]
        if contenu_html:
            contents.append(yagmail.raw(contenu_html))

        attachments = [pdf_path] if pdf_path else None

        yag.send(
            to=destinataire,
            subject=sujet,
            contents=contents,
            attachments=attachments,
        )
        logger.info("✅ Email envoyé à %s", destinataire)
        return True

    except Exception as e:
        logger.exception("❌ Erreur lors de l'envoi de l'email à %s : %s", destinataire, e)
        return False
    

def envoyer_email_clarification_questions(email, nom):
    sujet = "Tes 3 questions de clarification"

    corps = f"""
Bonjour {nom},

Tu as ajouté l’option “3 questions de clarification” à ton analyse.

Envoie moi tes questions dans un délai de 30 jours après réception de ton analyse.

Je te répondrai par retour écrit sous 10 jours ouvrés maximum après réception de tes 3 questions.

Astrologiquement vôtre,
Les Fous d'Astro by Cécile CL ✨
"""

    return envoyer_email_avec_analyse(
        destinataire=email,
        sujet=sujet,
        contenu_txt=corps
    )

def envoyer_email_notification_clarification_admin(
    nom,
    email_client,
    analyse,
    date_naissance,
    heure_naissance,
    lieu_naissance,
):
    sujet = "Nouvelle option 3 questions"

    corps = f"""
Nouvelle option clarification achetée.

Client : {nom}
Email : {email_client}
Analyse : {analyse}

Coordonnées :
- Date : {date_naissance}
- Heure : {heure_naissance}
- Lieu : {lieu_naissance}
"""

    return envoyer_email_avec_analyse(
        destinataire=os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI"),
        sujet=sujet,
        contenu_txt=corps
    )

def envoyer_notification_formulaire_commande_admin(
    reference_commande,
    nom,
    prenom,
    email_client,
    date_naissance,
    heure_naissance,
    lieu_naissance,
    creneau_realisation,
    attentes=None,
    approfondir=None,
):
    sujet = (
        f"Nouveau formulaire reçu — {reference_commande}"
    )

    corps = f"""
Un formulaire de commande vient d’être complété.

Commande :
- Référence : {reference_commande}
- Créneau : {creneau_realisation}

Bénéficiaire :
- Nom : {nom}
- Prénom : {prenom}
- Email : {email_client}
- Date de naissance : {date_naissance}
- Heure de naissance : {heure_naissance}
- Lieu de naissance : {lieu_naissance}

Attentes :
{attentes or "Aucune précision renseignée."}

Éléments à approfondir :
{approfondir or "Aucune précision renseignée."}
"""

    return envoyer_email_avec_analyse(
        destinataire=(
            os.getenv("EMAIL_ADMIN")
            or os.getenv("EMAIL_ENVOI")
        ),
        sujet=sujet,
        contenu_txt=corps,
    )

def envoyer_email_contact(nom: str, email: str, sujet: str, message: str) -> bool:
    """Envoie le contenu du formulaire de contact à l'adresse du site."""

    destinataire = os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI")

    if not destinataire:
        logger.error("🚫 EMAIL_ADMIN ou EMAIL_ENVOI manquant")
        return False

    contenu_txt = f"""
Nouveau message reçu depuis le formulaire de contact.

Nom : {nom}
Email : {email}
Sujet : {sujet}

-------------------------

{message}
"""

    sujet_email = f"[Contact] {sujet or 'Nouveau message'}"

    return envoyer_email_avec_analyse(
        destinataire=destinataire,
        sujet=sujet_email,
        contenu_txt=contenu_txt,
    )
