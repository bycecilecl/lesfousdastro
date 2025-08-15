# routes/point_astral.py

from flask import Blueprint, session, render_template
#from analyse_point_astral import analyse_point_astral
from utils.openai_utils import interroger_llm
from utils.pdf_utils import html_to_pdf
from utils.calcul_theme import calcul_theme
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.email_sender import envoyer_email_avec_analyse
from utils.google.upload_pdf_to_drive import upload_pdf_to_drive
from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs
from utils.utils_points_forts import extraire_points_forts
from analyse_point_astral_avec_sections import analyse_point_astral_avec_sections
from datetime import datetime
import uuid
import os

point_astral_bp = Blueprint("point_astral", __name__)

# ────────────────────────────────────────────────
# ROUTE : /afficher_point_astral
# Objectif :
#   - Récupère les infos utilisateur depuis la session après paiement.
#   - Enregistre ces infos dans un CSV + envoi Zapier.
#   - Calcule le thème astrologique complet avec calcul_theme().
#   - Appelle analyse_point_astral_avec_sections() pour générer l’analyse HTML.
#   - Génère le PDF associé et crée un lien de téléchargement.
#   - Envoie un e-mail avec le lien du PDF (Drive ou local).
#   - Affiche directement l’analyse en ligne dans resultat_point_astral.html.
#
# Étapes clés :
#   1. Vérification des données en session.
#   2. Enregistrement des infos + fallback axes majeurs si absents.
#   3. Génération HTML via LLM.
#   4. Conversion en PDF.
#   5. Envoi de l’e-mail.
#   6. Rendu HTML au navigateur.
# ────────────────────────────────────────────────

@point_astral_bp.route('/afficher_point_astral', methods=['GET'])
def afficher_point_astral():
    infos = session.get("infos_utilisateur")

    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire."

    # 🔹 LOGS DE DEBUG AMÉLIORÉS
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"🎬 ROUTE BLUEPRINT - Point Astral")
    logger.info(f"👤 Nom: {infos.get('nom', 'Anonyme')}")
    print("🔥 DEBUT FONCTION AFFICHER_POINT_ASTRAL")
    print(f"🔥 INFOS: {infos}")

    # 🔹 Enregistrement CSV + Zapier
    enregistrer_utilisateur_et_envoyer(infos)

    # # 🔹 Calcul du thème
    # data = calcul_theme(
    #     nom=infos["nom"],
    #     date_naissance=infos["date_naissance"],
    #     heure_naissance=infos["heure_naissance"],
    #     lieu_naissance=infos["lieu_naissance"]
    # )

    # 🔹 Calcul du thème avec coordonnées précises si disponibles
    lat_precise = infos.get("lat")
    lon_precise = infos.get("lon") 
    tzid_precise = infos.get("tzid")

    if lat_precise and lon_precise:
        print(f"🎯 Utilisation coordonnées précises: {lat_precise}, {lon_precise}")
        data = calcul_theme(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"],
            lat=float(lat_precise),
            lon=float(lon_precise),
            tzid=tzid_precise
        )
    else:
        print("🎯 Fallback géocodage classique")
        data = calcul_theme(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"]
        )

    # 🔹 TEST IMPORT
    print("🔥 TENTATIVE IMPORT analyse_point_astral_avec_sections")
    try:
        from analyse_point_astral_avec_sections import analyse_point_astral_avec_sections
        print("🔥 ✅ IMPORT REUSSI")
    except Exception as e:
        print(f"🔥 ❌ ERREUR IMPORT: {e}")
        return f"Erreur d'import: {e}"
    
    # === Fallback : fabriquer axes_majeurs_str si absent ===
    if not data.get("axes_majeurs_str"):
        # 1) récupérer les points forts bruts depuis data (plusieurs emplacements possibles)
        raw_pf = (
            data.get("points_forts")
            or (data.get("placements_occ") or {}).get("points_forts")
            or (data.get("placements_fusion") or {}).get("points_forts")
        )

        # 2) normaliser en liste propre
        if isinstance(raw_pf, str):
            lignes = [l.strip("•-–—* ").strip() for l in raw_pf.splitlines() if l.strip()]
            points_forts_list = [l for l in lignes if l]
        elif isinstance(raw_pf, list):
            points_forts_list = [str(l).strip() for l in raw_pf if str(l).strip()]
        else:
            # tente l’extracteur si dispo
            try:
                ext = extraire_points_forts(data)
                points_forts_list = [str(l).strip() for l in (ext or []) if str(l).strip()]
            except Exception as e:
                print("⚠️ extraire_points_forts a échoué:", e)
                points_forts_list = []

    # 3) organiser → Axes Majeurs + formatage
        try:
            axes = organiser_points_forts(points_forts_list)
            axes_str = formater_axes_majeurs(axes)
            # mapping termes
            axes_str = (axes_str or "").replace("Rahu", "Nœud Nord").replace("Ketu", "Nœud Sud")
            data["axes_majeurs"] = axes
            data["axes_majeurs_str"] = axes_str
            print("✅ Axes majeurs injectés (fallback route).")
            print((axes_str or "")[:250])
        except Exception as e:
            print("⚠️ Construction axes_majeurs_str impossible:", e)

    # Debug minimal avant LLM
    print("🔎 axes_majeurs_str present?", "axes_majeurs_str" in data, bool(data.get("axes_majeurs_str")))

    print("🔥 APPEL DE analyse_point_astral_avec_sections...")
    html_analyse = analyse_point_astral_avec_sections(data, interroger_llm, infos)

    # 🔹 Génération de l'analyse
    print(f"🔥 APPEL DE analyse_point_astral_avec_sections...")
    try:
        html_analyse = analyse_point_astral_avec_sections(data, interroger_llm, infos)
        print(f"🔥 ✅ HTML généré: {len(html_analyse)} caractères")
        
        # VERIFIER LE CONTENU
        if "section" in html_analyse:
            print("🔥 ✅ SECTIONS DETECTEES dans le HTML")
        else:
            print("🔥 ❌ AUCUNE SECTION DETECTEE dans le HTML")
            print(f"🔥 Début HTML: {html_analyse[:200]}")
            
    except Exception as e:
        print(f"🔥 ❌ ERREUR lors de la génération: {e}")
        import traceback
        traceback.print_exc()
        return f"Erreur: {e}"

    # 🔹 Génération du PDF
    prenom = infos["nom"].split()[0]
    date_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f"Point_Astral_{prenom}_{date_str}.pdf"
    output_path = os.path.join("static", "pdfs", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html_to_pdf(html_analyse, output_path)

#     # # 🔹 Upload sur Google Drive
#     # try:
#     #     url_drive = upload_pdf_to_drive(output_path, filename)
#     # except Exception as e:
#     #     print(f"❌ Erreur d'upload sur Google Drive : {e}")
#     #     url_drive = f"/static/pdfs/{filename}"  # fallback local

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