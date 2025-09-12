# routes/legales.py
from flask import Blueprint, render_template

legal_bp = Blueprint("legal_bp", __name__)

@legal_bp.route("/conditions", endpoint="conditions_utilisation")
def conditions_utilisation():
    return render_template("conditions-generales-utilisation.html")

@legal_bp.route("/mentions-legales", endpoint="mentions_legales")
def mentions_legales():
    return render_template("mentions-legales.html")

@legal_bp.route("/politique-confidentialite", endpoint="politique_confidentialite")
def politique_confidentialite():
    return render_template("politique-confidentialite.html")

@legal_bp.route("/aide", endpoint="aide_faq")
def aide_faq():
    return render_template("aide.html")