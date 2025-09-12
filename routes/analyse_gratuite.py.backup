import os, csv
from utils.openai_utils import interroger_llm
from utils.calcul_theme import calcul_theme
from utils.utils_analyse import analyse_gratuite
from utils.formatage import formater_positions_planetes, formater_aspects
from flask import Blueprint, request, render_template
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.enregistrement_placements import enregistrer_placements_utilisateur
from dotenv import load_dotenv
from utils.google.sheets_writer import ajouter_email_au_sheet
from utils.email_sender import envoyer_email_avec_analyse

load_dotenv()

gratuite_bp = Blueprint('gratuite_bp', __name__)


# 📌 Route /analyse_gratuite
# Cette route génère une analyse gratuite en 8 étapes :
# 1. Vérifie le consentement, enregistre l'utilisateur.
# 2. Calcule le thème natal avec calcul_theme().
# 3. Produit un résumé synthétique avec analyse_gratuite().
# 4. Formate les positions et aspects.
# 5. Construit le prompt personnalisé pour le LLM.
# 6. Interroge l'IA et récupère le texte de l'analyse.
# 7. Ajoute l'email de l'utilisateur au Google Sheet.
# 8. Envoie l'analyse gratuite par email et l'affiche dans le template.

@gratuite_bp.route('/analyse_gratuite', methods=['POST'])
def analyse_gratuite_post():
    print("✅ Route /analyse_gratuite appelée")
    print("📝 Données reçues :", request.form)

    if 'consentement' not in request.form:
        return "Consentement obligatoire pour générer l'analyse", 400
    
    enregistrer_utilisateur_et_envoyer(request.form)

    # 2. Calcul du thème
    data = calcul_theme(
        nom=request.form['nom'],
        date_naissance=request.form['date_naissance'],
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )

    infos_personnelles = {
    'nom': request.form['nom'],
    'date_naissance': request.form['date_naissance'],
    'heure_naissance': request.form['heure_naissance'],
    'lieu_naissance': request.form['lieu_naissance']
    }
    enregistrer_placements_utilisateur(data, infos_personnelles)

    print("🧭 ASCENDANT renvoyé par calcul_theme :", data.get("ascendant"))

    # 3. Analyse gratuite
    texte_resume = analyse_gratuite(
        planetes=data['planetes'],
        aspects=data['aspects'],
        lune_vedique=data['planetes_vediques'].get('Lune', {})
    )

    texte_resume_str = "\n".join(texte_resume)
    if len(texte_resume_str) > 600:
        texte_resume_str = texte_resume_str[:600] + "..."


    # 4. Préparer les textes à injecter dans le prompt
    positions_str = formater_positions_planetes(data['planetes'])
    aspects_str = formater_aspects(data['aspects'])

    # 5. Construction du prompt pour l'IA
    prompt = f"""
Tu es une astrologue expérimentée, à la plume fine, directe, drôle et lucide.
Tu proposes des analyses psychologiques profondes, qui vont à l’essentiel.
Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
Ton style est vivant mais jamais niais. Tu évites les clichés astrologiques.
Tu ne parles pas *de* la personne, tu lui parles *directement*.
Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

Voici les données du thème de {data['nom']} :

Résumé synthétique :
{texte_resume_str}

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
- Utilise uniquement l’astrologie occidentale tropicale (signes, maisons, aspects) comme base d’interprétation.
- N’intègre pas les données védiques (signe sidéral, maisons égales, logique karmique, etc.).
- Fais exception uniquement pour le Nakshatra de la Lune védique, si celui-ci permet un éclairage complémentaire précis.
- Ne mélange pas les deux systèmes dans une même phrase ou logique d’interprétation.

Tu peux conclure par une ou deux questions qui ouvrent à la réflexion. 
Cette analyse doit donner envie d'en savoir plus, d'explorer plus en profondeur.

Fais une analyse de max 15 lignes.
"""

    print("📤 Prompt envoyé à l'IA :", prompt)

    # 6. Appel à OpenAI
    texte_analyse_complete = interroger_llm(prompt)
    print("✅ Analyse IA reçue :", texte_analyse_complete)

    # 7. Extraction des données
    prenom = request.form['nom'].split()[0]
    email = request.form['email']

    # 8. Ajout au Google Sheet
    try:
        ajouter_email_au_sheet(email, prenom)
    except Exception as e:
        print(f"❌ Erreur ajout Google Sheet : {e}")

        # 9. Envoi direct par email
    print("📧 Envoi de l'analyse par email...")
    try:
        sujet = f"Ton analyse astrologique gratuite – {prenom}"
        contenu = f"""
        Bonjour {prenom},<br><br>
        Voici ton analyse astrologique gratuite générée par Les Fous d’Astro 👁️‍🗨️<br><br>
        <hr>
        {texte_analyse_complete}
        <hr><br>
        Si tu veux en savoir plus : Le Point Astral
        À bientôt,<br>L’équipe des Fous d’Astro ✨
        """
        envoyer_email_avec_analyse(destinataire=email, sujet=sujet, contenu_html=contenu)
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi du mail : {e}")

    return render_template(
        'analyse_gratuite.html',
        nom=data['nom'],
        date=data['date'],
        analyse=texte_analyse_complete,
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )