from flask import Blueprint
from flask import render_template, request, redirect
from utils.email_sender import envoyer_email_contact
from utils.google.sheets_writer import ajouter_email_au_sheet
from utils.brevo_contacts import ajouter_contact_brevo
import os
import requests

pages_bp = Blueprint("pages_bp", __name__)

def verifier_turnstile():
    token = request.form.get("cf-turnstile-response", "").strip()
    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()

    if not token or not secret:
        return False

    try:
        reponse = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": secret,
                "response": token,
                "remoteip": request.remote_addr,
            },
            timeout=8,
        )

        resultat = reponse.json()

    except (requests.RequestException, ValueError):
        return False

    return (
        resultat.get("success") is True
        and resultat.get("hostname")
        in {"lesfousdastro.fr", "www.lesfousdastro.fr"}
    )

@pages_bp.app_context_processor
def injecter_cle_turnstile():
    return {
        "turnstile_site_key": os.getenv(
            "TURNSTILE_SITE_KEY",
            "",
        ).strip()
    }

@pages_bp.route("/analyses")
def analyses():
    return render_template("pages/analyses.html", active="analyses")

@pages_bp.route("/formations")
def formations():
    return render_template("pages/formations.html", active="formations")

@pages_bp.route("/ateliers")
def ateliers():
    return render_template("pages/ateliers.html", active="ateliers")


@pages_bp.route("/prestations")
def prestations():
    return render_template("pages/prestations.html", active="prestations")

@pages_bp.route("/prestations/demande", methods=["POST"])
def demande_prestation():
    prestations_autorisees = {
        "Lecture du Thème Natal",
        "Révolution Solaire",
        "Accompagnement en connaissance de soi",
    }

    prestation = request.form.get(
        "prestation",
        "",
    ).strip()

    nom = request.form.get(
        "nom",
        "",
    ).strip()

    email = request.form.get(
        "email",
        "",
    ).strip()

    message = request.form.get(
        "message",
        "",
    ).strip()

    accord_contact = (
        request.form.get("accord_contact") == "1"
    )

    if (
        prestation not in prestations_autorisees
        or not nom
        or not email
        or not accord_contact
    ):
        return render_template(
            "pages/prestations.html",
            active="prestations",
            demande_erreur=(
                "Merci de remplir les champs obligatoires "
                "et d’accepter d’être recontacté(e)."
            ),
        ), 400

    contenu = f"""
Nouvelle demande de prestation.

Prestation : {prestation}
Nom : {nom}
Email : {email}

Message :
{message or "Aucune précision renseignée."}

La personne a accepté d’être recontactée au sujet de cette demande.
"""

    email_envoye = envoyer_email_contact(
        nom=nom,
        email=email,
        sujet=f"Demande de prestation — {prestation}",
        message=contenu,
    )

    return render_template(
        "pages/prestations.html",
        active="prestations",
        demande_succes=email_envoye,
        demande_erreur=(
            None
            if email_envoye
            else "La demande n’a pas pu être envoyée. Merci de réessayer."
        ),
    )

# @pages_bp.route("/contact", methods=["GET", "POST"])
# def contact():
#     return render_template("pages/contact.html", active="contact")


@pages_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        if not verifier_turnstile():
            return render_template(
                "pages/contact.html",
                active="contact",
                erreur=(
                    "La vérification anti-spam a échoué. "
                    "Merci de réessayer."
                ),
            ), 400
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip()
        sujet = request.form.get("sujet", "").strip()
        message = request.form.get("message", "").strip()
        newsletter = request.form.get("newsletter") == "oui"

        # Envoi du message
        email_envoye = envoyer_email_contact(
            nom=nom,
            email=email,
            sujet=sujet,
            message=message,
        )

        # Inscription newsletter
        # Inscription newsletter depuis le formulaire de contact
        if newsletter:
            try:
                ajouter_email_au_sheet(email, nom or "Inconnu")
                print(f"✅ Newsletter ajoutée au Google Sheet : {email}")
            except Exception as e:
                print(f"❌ Erreur Google Sheet newsletter : {e}")

            try:
                brevo_ok = ajouter_contact_brevo(
                    email=email,
                    nom=nom,
                    liste="site",
                )

                if brevo_ok:
                    print(f"✅ Newsletter ajoutée à Brevo : {email}")
                else:
                    print(f"❌ Échec ajout newsletter Brevo : {email}")

            except Exception as e:
                print(f"❌ Exception ajout newsletter Brevo : {e}")

        return render_template(
            "pages/contact.html",
            active="contact",
            succes=email_envoye,
            erreur=(
                None
                if email_envoye
                else "Le message n’a pas pu être envoyé. Merci de réessayer."
            ),
)

    return render_template("pages/contact.html", active="contact")


@pages_bp.route("/newsletter/inscription", methods=["POST"])
def inscription_newsletter():
    nom = request.form.get("newsletter_nom", "").strip()
    email = request.form.get("newsletter_email", "").strip()

    if not email:
        return render_template(
            "pages/contact.html",
            active="contact",
            newsletter_erreur="Merci de renseigner ton adresse email.",
        )

    try:
        ajouter_email_au_sheet(email, nom or "Inconnu")
        print(f"✅ Newsletter ajoutée au Google Sheet : {email}")

    except Exception as e:
        print(f"❌ Erreur Google Sheet newsletter : {e}")

        return render_template(
            "pages/contact.html",
            active="contact",
            newsletter_erreur="Une erreur est survenue. Merci de réessayer.",
        )

    try:
        brevo_ok = ajouter_contact_brevo(
            email=email,
            nom=nom,
            liste="site",
        )

        if brevo_ok:
            print(f"✅ Newsletter ajoutée à Brevo : {email}")
        else:
            print(f"❌ Échec ajout newsletter Brevo : {email}")

    except Exception as e:
        print(f"❌ Exception ajout newsletter Brevo : {e}")

    # return render_template(
    #     "pages/contact.html",
    #     active="contact",
    #     newsletter_succes=True,
    # )

    return redirect(request.referrer or "/")