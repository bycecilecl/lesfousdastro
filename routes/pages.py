from flask import Blueprint
from flask import render_template, request, redirect
from utils.email_sender import envoyer_email_contact
from utils.google.sheets_writer import ajouter_email_au_sheet
from utils.brevo_contacts import ajouter_contact_brevo

pages_bp = Blueprint("pages_bp", __name__)

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

# @pages_bp.route("/contact", methods=["GET", "POST"])
# def contact():
#     return render_template("pages/contact.html", active="contact")


@pages_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
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
            erreur=not email_envoye,
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