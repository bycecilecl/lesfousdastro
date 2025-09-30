from flask import Blueprint, render_template

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

@pages_bp.route("/contact")
def contact():
    return render_template("pages/contact.html", active="contact")