"""Transport dédié aux mails bêta : une tentative, aucun repli vers un autre fournisseur."""
from email.message import EmailMessage
import os
import smtplib
import ssl


def verifier_transport():
    if os.getenv("EMAIL_PROVIDER", "smtp").lower() == "brevo":
        requis = ("BREVO_API_KEY", "BREVO_SENDER_EMAIL")
    else:
        requis = ("EMAIL_ENVOI", "EMAIL_PASSWORD")
    if not all(os.getenv(c) for c in requis):
        raise ValueError("Le transport des mails n’est pas configuré. Aucun appel IA effectué.")


def envoyer_evenement(mail, destinataire):
    """L’appelant a déjà persisté l’état envoi_en_cours. Toute exception est incertaine."""
    verifier_transport()
    if os.getenv("EMAIL_PROVIDER", "smtp").lower() == "brevo":
        import requests
        reponse = requests.post("https://api.brevo.com/v3/smtp/email", timeout=20,
            headers={"api-key": os.environ["BREVO_API_KEY"], "Content-Type": "application/json"},
            json={"sender": {"email": os.environ["BREVO_SENDER_EMAIL"], "name": os.getenv("BREVO_SENDER_NAME", "Les Fous d’Astro")},
                  "to": [{"email": destinataire}], "subject": mail.objet,
                  "textContent": mail.contenu_texte, "htmlContent": mail.contenu_html})
        reponse.raise_for_status()
        return str(reponse.json().get("messageId") or "accepte_par_brevo")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = os.environ["EMAIL_ENVOI"], destinataire, mail.objet
    message["Message-ID"] = f"<{mail.id}@lesfousdastro.fr>"
    message.set_content(mail.contenu_texte)
    message.add_alternative(mail.contenu_html, subtype="html")
    securise = os.getenv("SMTP_USE_SSL", "true").lower() in {"1", "true", "yes"}
    classe = smtplib.SMTP_SSL if securise else smtplib.SMTP
    with classe(os.getenv("SMTP_HOST", "node175-eu.n0c.com"), int(os.getenv("SMTP_PORT", "465")), timeout=20) as smtp:
        if not securise and os.getenv("SMTP_USE_STARTTLS", "false").lower() in {"1", "true", "yes"}:
            smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ["EMAIL_ENVOI"], os.environ["EMAIL_PASSWORD"])
        if smtp.send_message(message):
            raise RuntimeError("Le destinataire a été refusé par le transport.")
    return str(message["Message-ID"])
