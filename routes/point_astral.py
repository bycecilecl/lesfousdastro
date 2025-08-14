# routes/point_astral.py

from flask import Blueprint, session, render_template, jsonify
from utils.openai_utils import interroger_llm
from utils.pdf_utils import html_to_pdf
from utils.calcul_theme import calcul_theme
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.email_sender import envoyer_email_avec_analyse
from utils.google.upload_pdf_to_drive import upload_pdf_to_drive
from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs
from utils.utils_points_forts import extraire_points_forts
from analyse_point_astral_avec_sections import analyse_point_astral_avec_sections
from utils.email_sender import envoyer_email_point_astral_v2
from datetime import datetime
import uuid
import os
import threading
import logging

point_astral_bp = Blueprint("point_astral", __name__)

# 🆕 Stockage des tâches de génération
generation_status = {}

# ────────────────────────────────────────────────
# ROUTE : /afficher_point_astral - VERSION ASYNC
# Objectif : IDENTIQUE à ton code original, mais en async
# ────────────────────────────────────────────────

@point_astral_bp.route('/afficher_point_astral', methods=['GET'])
def afficher_point_astral():
    """Lance la génération async et affiche la progression"""
    infos = session.get("infos_utilisateur")

    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire."
    
    # 🎯 TES LOGS DE DEBUG ORIGINAUX
    gender = infos.get('gender')
    print(f"🔍 GENRE RÉCUPÉRÉ DE SESSION: '{gender}'")
    print(f"🔍 INFOS COMPLÈTES: {infos}")

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"🎬 ROUTE BLUEPRINT - Point Astral")
    logger.info(f"👤 Nom: {infos.get('nom', 'Anonyme')}")
    print("🔥 DEBUT FONCTION AFFICHER_POINT_ASTRAL")
    print(f"🔥 INFOS: {infos}")

    # 🆕 Créer ID tâche et lancer génération async
    task_id = str(uuid.uuid4())[:8]
    
    generation_status[task_id] = {
        'status': 'starting',
        'progress': 0,
        'message': '🚀 Initialisation...',
        'result_html': None,
        'pdf_url': None,
        'error': None
    }
    
    # 🆕 Lancer ton code original en arrière-plan
    thread = threading.Thread(target=generer_point_astral_complet, args=(task_id, infos))
    thread.daemon = True
    thread.start()
    
    # 🆕 Retourner immédiatement la page de progression
    return render_template('generation_async.html', task_id=task_id, nom=infos.get('nom', 'Client'))

# ────────────────────────────────────────────────
# FONCTION : generer_point_astral_complet - TON CODE ORIGINAL EN ASYNC
# ────────────────────────────────────────────────

def generer_point_astral_complet(task_id, infos):
    """TON CODE ORIGINAL, mais avec des updates de statut"""
    try:
        # 🔹 Enregistrement CSV + Zapier (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'registering', 'progress': 10, 'message': '📝 Enregistrement des données...'
        })
        
        enregistrer_utilisateur_et_envoyer(infos)

        # 🔹 Calcul du thème avec coordonnées précises (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'theme', 'progress': 25, 'message': '🧭 Calcul de votre thème natal...'
        })
        
        gender = infos.get('gender')
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
            data['gender'] = gender
        else:
            print("🎯 Fallback géocodage classique")
            data = calcul_theme(
                nom=infos["nom"],
                date_naissance=infos["date_naissance"],
                heure_naissance=infos["heure_naissance"],
                lieu_naissance=infos["lieu_naissance"]
            )
            data['gender'] = gender

        print(f"🔍 GENRE AJOUTÉ À DATA: '{data.get('gender')}'")

        # 🔹 TEST IMPORT (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'importing', 'progress': 35, 'message': '⚙️ Chargement des modules d\'analyse...'
        })
        
        print("🔥 TENTATIVE IMPORT analyse_point_astral_avec_sections")
        try:
            from analyse_point_astral_avec_sections import analyse_point_astral_avec_sections
            print("🔥 ✅ IMPORT REUSSI")
        except Exception as e:
            print(f"🔥 ❌ ERREUR IMPORT: {e}")
            raise Exception(f"Erreur d'import: {e}")
        
        # 🔹 Fallback axes majeurs (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'axes', 'progress': 45, 'message': '⭐ Calcul des axes majeurs...'
        })
        
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
                # tente l'extracteur si dispo
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

        # Debug minimal avant LLM (TON CODE EXACT)
        print("🔎 axes_majeurs_str present?", "axes_majeurs_str" in data, bool(data.get("axes_majeurs_str")))
        print(f"🔍 GENRE FINAL AVANT LLM: '{data.get('gender')}'")

        # 🔹 Génération de l'analyse (TON CODE EXACT, LA PARTIE LA PLUS LONGUE)
        generation_status[task_id].update({
            'status': 'ai_generation', 'progress': 50, 'message': '🤖 Génération IA personnalisée... (2-4mn)'
        })
        
        print("🔥 APPEL DE analyse_point_astral_avec_sections...")
        html_analyse = analyse_point_astral_avec_sections(data, interroger_llm, infos)
        
        try:
            print(f"🔥 ✅ HTML généré: {len(html_analyse)} caractères")
            
            # VERIFIER LE CONTENU (TON DEBUG EXACT)
            if "section" in html_analyse:
                print("🔥 ✅ SECTIONS DETECTEES dans le HTML")
            else:
                print("🔥 ❌ AUCUNE SECTION DETECTEE dans le HTML")
                print(f"🔥 Début HTML: {html_analyse[:200]}")
                
        except Exception as e:
            print(f"🔥 ❌ ERREUR lors de la génération: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Erreur génération: {e}")

        # 🔹 Génération du PDF (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'pdf', 'progress': 80, 'message': '📄 Génération du PDF...'
        })
        
        prenom = infos["nom"].split()[0]
        date_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
        filename = f"Point_Astral_{prenom}_{date_str}.pdf"
        output_path = os.path.join("static", "pdfs", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        html_to_pdf(html_analyse, output_path)

        # 🔹 Upload sur Google Drive (TON CODE EXACT)
        url_drive = f"/static/pdfs/{filename}"

        # 🔹 Envoi de l'e-mail (TON CODE EXACT)
        generation_status[task_id].update({
            'status': 'email', 'progress': 90, 'message': '📧 Envoi par email...'
        })
        
        try:
            envoyer_email_point_astral_v2(
                destinataire=infos["email"],
                prenom=prenom,
                url_drive=url_drive,
            )
        except Exception as e:
            print(f"⚠️ Email error (non critique): {e}")

        # 🔹 SUCCÈS FINAL
        generation_status[task_id].update({
            'status': 'completed', 'progress': 100, 'message': '✅ Votre Point Astral est prêt !',
            'result_html': html_analyse, 'pdf_url': f"/static/pdfs/{filename}"
        })

    except Exception as e:
        print(f"❌ Erreur génération complète: {e}")
        import traceback
        traceback.print_exc()
        
        generation_status[task_id].update({
            'status': 'error', 'progress': 0, 
            'message': f'❌ Erreur: {str(e)}', 'error': str(e)
        })

# ────────────────────────────────────────────────
# ROUTES API POUR LE SUIVI ASYNC
# ────────────────────────────────────────────────

@point_astral_bp.route('/api/status/<task_id>')
def check_status(task_id):
    """API pour vérifier le statut de génération"""
    status = generation_status.get(task_id, {'status': 'not_found'})
    return jsonify(status)

@point_astral_bp.route('/result/<task_id>')
def show_result(task_id):
    """Affiche le résultat final (identique à ton template original)"""
    status = generation_status.get(task_id)
    
    if not status or status['status'] != 'completed':
        return "Génération non terminée ou introuvable", 404
    
    # Récupérer les résultats
    result_html = status['result_html']
    pdf_url = status['pdf_url']
    
    # Nettoyer le cache (économiser mémoire)
    del generation_status[task_id]
    
    # 🔹 TON TEMPLATE ORIGINAL EXACT
    return render_template("resultat_point_astral.html",
                           analyse_html=result_html,
                           pdf_url=pdf_url)