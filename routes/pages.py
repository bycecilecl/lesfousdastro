from flask import Blueprint
from flask import render_template, request

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

@pages_bp.route("/contact", methods=["GET", "POST"])
def contact():
    return render_template("pages/contact.html", active="contact")


@pages_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        nom = request.form.get("nom")
        email = request.form.get("email")
        sujet = request.form.get("sujet")
        message = request.form.get("message")

        print("NOUVEAU MESSAGE CONTACT")
        print("Nom :", nom)
        print("Email :", email)
        print("Sujet :", sujet)
        print("Message :", message)

        return render_template("contact.html", succes=True)

    return render_template("contact.html")