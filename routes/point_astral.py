# routes/point_astral.py

from flask import Blueprint, session, render_template, redirect, url_for
from analyse_point_astral import analyse_point_astral
from utils.openai_utils import interroger_llm
from utils.pdf_utils import html_to_pdf
from utils.calcul_theme import calcul_theme
import uuid
import os


point_astral_bp = Blueprint("point_astral", __name__)

@point_astral_bp.route('/afficher_point_astral', methods=['GET'])
def afficher_point_astral():
    infos = session.get("infos_utilisateur")

    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire."

    # Recalculer les données astrologiques à la volée
    data = calcul_theme(
        nom=infos["nom"],
        date_naissance=infos["date_naissance"],
        heure_naissance=infos["heure_naissance"],
        lieu_naissance=infos["lieu_naissance"]
    )

    # Générer analyse
    html_analyse = analyse_point_astral(data, interroger_llm, infos)

    # Générer le PDF
    filename = f"point_astral_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join("static", "pdfs", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html_to_pdf(html_analyse, output_path)

    return render_template("resultat_point_astral.html",
                           analyse_html=html_analyse,
                           pdf_url=f"/static/pdfs/{filename}")