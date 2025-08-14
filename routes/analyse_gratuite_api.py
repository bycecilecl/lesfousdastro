# routes/analyse_gratuite_api.py
from flask import Blueprint, request, jsonify, render_template
from utils.openai_utils import interroger_llm
from utils.calcul_theme import calcul_theme
from utils.utils_analyse import analyse_gratuite
from utils.formatage import formater_positions_planetes, formater_aspects
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.enregistrement_placements import enregistrer_placements_utilisateur
from utils.google.sheets_writer import ajouter_email_au_sheet
from utils.email_sender import envoyer_email_avec_analyse
from dotenv import load_dotenv
import os

load_dotenv()

gratuite_api_bp = Blueprint("gratuite_api_bp", __name__)

@gratuite_api_bp.route("/api/analyse_gratuite", methods=["POST"])
def api_analyse_gratuite():
    """
    Version AJAX pour le nouveau formulaire.
    Reçoit JSON et renvoie { ok: True, html: "<div>...</div>" }
    + toutes les fonctionnalités de l'ancienne version (email, sheets, enregistrements)
    """
    print("🚀 API analyse gratuite appelée !")
    print("📊 Data reçue :", request.get_json())
    
    try:
        data = request.get_json(force=True)

        # ✅ Données reçues du front
        nom             = data["nom"]
        email           = data["email"]
        date_naissance  = data["date_naissance"]
        heure_naissance = data["heure_naissance"]
        lieu_naissance  = data["lieu_naissance"]
        lat             = data.get("lat")
        lon             = data.get("lon")
        tzid            = data.get("tzid")
        gender          = data.get("gender")  # "male" | "female" | None

        # 📋 1) Enregistrement utilisateur (comme dans l'ancienne version)
        # Simuler request.form pour la fonction existante
        form_data_simulation = {
            'nom': nom,
            'email': email,
            'date_naissance': date_naissance,
            'heure_naissance': heure_naissance,
            'lieu_naissance': lieu_naissance,
            'consentement': 'on'  # Déjà vérifié côté front
        }
        
        try:
            enregistrer_utilisateur_et_envoyer(form_data_simulation)
            print("✅ Utilisateur enregistré")
        except Exception as e:
            print(f"⚠️ Erreur enregistrement utilisateur : {e}")

        # 🧮 2) Calcul du thème
        theme = calcul_theme(
            nom=nom,
            date_naissance=date_naissance,
            heure_naissance=heure_naissance,
            lieu_naissance=lieu_naissance,
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
            tzid=tzid or None
        )

        # 📊 3) Enregistrement des placements (comme dans l'ancienne version)
        infos_personnelles = {
            'nom': nom,
            'date_naissance': date_naissance,
            'heure_naissance': heure_naissance,
            'lieu_naissance': lieu_naissance
        }
        try:
            enregistrer_placements_utilisateur(theme, infos_personnelles)
            print("✅ Placements enregistrés")
        except Exception as e:
            print(f"⚠️ Erreur enregistrement placements : {e}")

        print("🧭 ASCENDANT renvoyé par calcul_theme :", theme.get("ascendant"))

        # 📝 4) Résumé + formats (comme dans l'ancienne version)
        resume_list = analyse_gratuite(
            planetes=theme['planetes'],
            aspects=theme['aspects'],
            lune_vedique=theme['planetes_vediques'].get('Lune', {})
        )
        resume_str = "\n".join(resume_list)
        if len(resume_str) > 600:
            resume_str = resume_str[:600] + "..."

        positions_str = formater_positions_planetes(theme['planetes'])
        aspects_str   = formater_aspects(theme['aspects'])

        # 🤖 5) Prompt (même que l'ancienne version + genre)
        prompt = f"""
Tu es une astrologue expérimentée, à la plume fine, directe, drôle et lucide.
Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
Ton style est vivant mais jamais niais. Tu évites les clichés astrologiques.
Tu ne parles pas *de* la personne, tu lui parles *directement*.
Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

Voici les données du thème de {theme['nom']} :
- Genre déclaré (facultatif) : {gender or "non précisé"}

Résumé synthétique :
{resume_str}

Positions planétaires :
{positions_str}

Aspects astrologiques :
{aspects_str}

Instruction :
Écris une lecture globale, cohérente et incarnée du thème natal.
- Ne commente pas les positions une par une.
- Repère les tensions internes (les dissonances, les contradictions).
- Parle des dynamiques psychologiques sous-jacentes.
- Mets en lumière les ressources intérieures.
- Parle vrai, pas besoin de brosser dans le sens du poil.
- Ose montrer les tiraillements, les paradoxes, les excès ou inhibitions.
- Tu peux ajouter un regard existentiel si pertinent.
- Ne déduis pas que la personne est extravertie ou sociable sans raison valable.
- Utilise uniquement l'astrologie occidentale tropicale (signes, maisons, aspects) comme base d'interprétation.
- N'intègre pas les données védiques (signe sidéral, maisons égales, logique karmique, etc.).
- Fais exception uniquement pour le Nakshatra de la Lune védique, si celui-ci permet un éclairage complémentaire précis.
- Ne mélange pas les deux systèmes dans une même phrase ou logique d'interprétation.

Tu peux conclure par une ou deux questions qui ouvrent à la réflexion. 
Cette analyse doit donner envie d'en savoir plus, d'explorer plus en profondeur.

Fais une analyse de max 15 lignes.
"""

        print("📤 Prompt envoyé à l'IA :", prompt[:200] + "...")

        # 🤖 6) Appel à l'IA
        texte = interroger_llm(prompt)
        print("✅ Analyse IA reçue :", texte[:100] + "...")

        # 📧 7) Envoi email + Google Sheets (comme dans l'ancienne version)
        prenom = theme['nom'].split()[0]
        
        # Ajout au Google Sheet
        try:
            ajouter_email_au_sheet(email, prenom)
            print("✅ Email ajouté au Google Sheet")
        except Exception as e:
            print(f"⚠️ Erreur ajout Google Sheet : {e}")

        # Envoi par email
        print("📧 Envoi de l'analyse par email...")
        try:
            sujet = f"Ton analyse astrologique gratuite – {prenom}"
            contenu = f"""
            Bonjour {prenom},<br><br>
            Voici ton analyse astrologique gratuite générée par Les Fous d'Astro 👁️‍🗨️<br><br>
            <hr>
            {texte}
            <hr><br>
            Si tu veux en savoir plus : Le Point Astral<br>
            À bientôt,<br>L'équipe des Fous d'Astro ✨
            """
            envoyer_email_avec_analyse(destinataire=email, sujet=sujet, contenu_html=contenu)
            print("✅ Email envoyé avec succès")
        except Exception as e:
            print(f"⚠️ Erreur lors de l'envoi du mail : {e}")

        # 🎨 8) Génération du HTML pour le modal
        html = f"""
            <div class="analysis-summary">
                <h4>🌟 Bonjour {theme['nom']}, voici votre profil astrologique :</h4>
                <div style="margin: 20px 0; line-height: 1.6;">{texte}</div>
                
                <div style="margin-top: 25px; padding: 20px; background: rgba(31, 98, 142, 0.1); border-radius: 15px; text-align: center;">
                    <p><strong>🎯 Cette analyse vous plaît ?</strong></p>
                    <p>Découvrez bien plus avec nos analyses approfondies !</p>
                </div>
            </div>
        """

        # 🔍 9) Données de debug pour toi (ajoutées à la réponse mais cachées)
        debug_data = {
            'placements_url': f"/placements?nom={nom}&date={date_naissance}&heure={heure_naissance}&lieu={lieu_naissance}&lat={lat}&lon={lon}&tzid={tzid}",
            'positions': positions_str[:200] + "..." if len(positions_str) > 200 else positions_str,
            'aspects_count': len(theme.get('aspects', [])),
            'ascendant': theme.get('ascendant', 'Non calculé')
        }

        print(f"🔍 DEBUG URL pour placements : {debug_data['placements_url']}")
        
        return jsonify({
            "ok": True, 
            "html": html,
            "debug": debug_data  # Tu peux récupérer ça côté JS si besoin
        })

    except Exception as e:
        print(f"❌ Erreur dans API analyse gratuite : {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "ok": False, 
            "error": f"Erreur lors de la génération : {str(e)}"
        }), 500