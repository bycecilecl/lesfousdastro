# routes/point_astral.py

from flask import Blueprint, session, render_template
from analyse_point_astral import analyse_point_astral
from utils.openai_utils import interroger_llm
from utils.pdf_utils import html_to_pdf
from utils.calcul_theme import calcul_theme
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.email_sender import envoyer_email_avec_analyse
from utils.google.upload_pdf_to_drive import upload_pdf_to_drive
from datetime import datetime
import uuid
import os

point_astral_bp = Blueprint("point_astral", __name__)

@point_astral_bp.route('/afficher_point_astral', methods=['GET'])
def afficher_point_astral():
    infos = session.get("infos_utilisateur")

    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire."

    # 🔹 Enregistrement CSV + Zapier
    enregistrer_utilisateur_et_envoyer(infos)

    # 🔹 Calcul du thème
    data = calcul_theme(
        nom=infos["nom"],
        date_naissance=infos["date_naissance"],
        heure_naissance=infos["heure_naissance"],
        lieu_naissance=infos["lieu_naissance"]
    )

    # 🔹 Génération de l’analyse
    html_analyse = analyse_point_astral(data, interroger_llm, infos)

    # 🔹 Génération du PDF
    prenom = infos["nom"].split()[0]
    date_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f"Point_Astral_{prenom}_{date_str}.pdf"
    output_path = os.path.join("static", "pdfs", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html_to_pdf(html_analyse, output_path)

    # # 🔹 Upload sur Google Drive
    # try:
    #     url_drive = upload_pdf_to_drive(output_path, filename)
    # except Exception as e:
    #     print(f"❌ Erreur d'upload sur Google Drive : {e}")
    #     url_drive = f"/static/pdfs/{filename}"  # fallback local

    # 🔹 Upload sur Google Drive
    url_drive = f"/static/pdfs/{filename}"

    # 🔹 Envoi de l’e-mail avec lien Drive
    sujet = f"Ton Point Astral – Les Fous d’Astro"
    message_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #1f628e;">Bonjour {prenom} ✨</h2>
            <p>Merci pour ta confiance !</p>
            <p>Ton Point Astral est prêt. Tu peux le télécharger ici :</p>
            <p>
                👉<a href="https://tonsite.com{url_drive}" target="_blank"><strong>Télécharger ton Point Astral</strong></a>
            </p>
            <p>À bientôt,<br><strong>L’équipe des Fous d’Astro</strong> 🌟</p>
        </body>
    </html>
    """
    envoyer_email_avec_analyse(
        destinataire=infos["email"],
        sujet=sujet,
        contenu_html=message_html,
    )

    # 🔹 Affichage immédiat de l’analyse
    return render_template("resultat_point_astral.html",
                           analyse_html=html_analyse,
                           pdf_url=f"/static/pdfs/{filename}")