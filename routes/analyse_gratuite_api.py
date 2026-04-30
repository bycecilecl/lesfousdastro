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
from utils.email_quota import check_and_log_email_quota
from threading import Thread
import textwrap
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

        print(f"DEBUG: nom reçu = '{nom}'")

        # 🔒 Limite : email + IP
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        try:
            allowed, info = check_and_log_email_quota(email, ip=ip)
        except Exception as e:
            print(f"[QUOTA] KO (fail-open) — email={email} ip={ip} err={e}")
            allowed, info = True, {"email_count": 0, "ip_count": 0}

        email_count = info.get("email_count", 0)
        ip_count = info.get("ip_count", 0)

        if not allowed:
            html_limit = f"""
                <div style="padding:20px; border-radius:12px; background:#fff3cd; border:1px solid #ffeeba; color:#856404; text-align:center; font-family:sans-serif;">
                    <strong>🚫 Limite atteinte</strong><br><br>
                    👉 Pour continuer ton exploration, découvre ton <strong>Flash Astral complet</strong> :<br>
                    <ul style="text-align:left; display:inline-block; margin:10px auto; padding:0; list-style:disc;">
                        <li>Lecture approfondie & psychologiques (4 pages)</li>
                        <li>PDF personnalisé à télécharger</li>
                    </ul>
                    <br>
                    <a href="/#flash_astral" style="display:inline-block; padding:12px 20px; background:#856404; color:#fff; border-radius:8px; text-decoration:none; font-weight:bold;">
                        💫 Découvrir mon Flash Astral
                    </a>
                </div>
            """
            print(f"[QUOTA] Bloqué: email={email} ({email_count}), ip={ip} ({ip_count})")
            return jsonify({"ok": True, "html": html_limit}), 200

        # Optionnel : log pour savoir qu'on a autorisé et où on en est
        print(f"[QUOTA] Autorisé: email={email} ({email_count}), ip={ip} ({ip_count})")

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

        print(f"DEBUG: theme['nom'] = '{theme.get('nom')}'")

        # 📊 3) Enregistrement des placements (CSV) + push Google Sheets
        infos_personnelles = {
            'nom': nom,
            'date_naissance': date_naissance,
            'heure_naissance': heure_naissance,
            'lieu_naissance': lieu_naissance
        }

        print("[PLACEMENTS] Début bloc placements")
        try:
            donnees_placements = enregistrer_placements_utilisateur(theme, infos_personnelles)
            print(f"[PLACEMENTS] CSV OK — {len(donnees_placements) if donnees_placements else 0} champs")
        except Exception as e:
            donnees_placements = None
            print(f"[PLACEMENTS] ⚠️ CSV KO — {e}")

        # ➜ Envoi vers Google Sheets (onglet 'placements')
        if donnees_placements:
            try:
                from utils.google.sheets_writer import ajouter_placements_au_sheet
                ajouter_placements_au_sheet(donnees_placements)
                print("[PLACEMENTS] ✅ Sheets OK — ligne ajoutée dans onglet 'placements'")
            except Exception as e:
                print(f"[PLACEMENTS] ⚠️ Sheets KO — {e}")
        else:
            print("[PLACEMENTS] Rien à pousser vers Sheets (donnees_placements=None)")

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

        print("📤 Prompt envoyé à l'IA :", prompt)

        # 🤖 6) Appel à l'IA
        texte = interroger_llm(prompt)
        print("✅ Analyse IA reçue :", texte[:100] + "...")

        # 📧 7) Envoi email + Google Sheets (comme dans l'ancienne version)
        prenom = theme['nom'].split()[0]
        
        # Ajout au Google Sheet — logs détaillés
        print(f"[LEAD] Tentative d'ajout au Google Sheet — email='{email}', prenom='{prenom}'")

        try:
            if not email or "@" not in email:
                raise ValueError(f"Email invalide: {email!r}")

            ajouter_email_au_sheet(email, prenom)
            print("✅ [LEAD] Ajout Google Sheet OK")
        except Exception as e:
            import traceback
            print(f"❌ [LEAD] Ajout Google Sheet KO — type={type(e).__name__} — msg={e}")
            traceback.print_exc()

        # Envoi par email
        print("📧 Envoi de l'analyse par email...")

        send_emails = os.getenv("SEND_EMAILS", "true").lower() in ("1","true","yes")
        sujet = f"Ton analyse astrologique gratuite - {prenom}"  # tiret simple

        contenu_txt = textwrap.dedent(f"""
            Bonjour {prenom},

            Tu l'as demandé, Cécile l'a fait...Ou plutôt les étoiles ont répondu 🔭

            Allez, voici ce que disent tes étoiles :

            {texte}

            Allez avoue, tu veux en savoir plus 😏

            Cette analyse n'est qu'une première lecture. Le Flash Astral va plus loin :
            il met en lumière tes grands mécanismes, tes forces, tes blocages, et les zones de ton thème
            qui demandent à être comprises plus finement.

            👉 https://lesfousdastro.fr

            À très vite sur les réseaux...en vrai, ou dans les étoiles si on se croise jamais (c'est triste mais c'est une possibilité).
            Les Fous d'Astro by Cécile CL ✨
            """).strip()

        contenu_html = textwrap.dedent(f"""
            <p>Bonjour {prenom},</p>
            <p>Tu l'as demandé, Cécile l'a fait...Ou plutôt les étoiles ont répondu 🔭</p>
            <p>Allez, voici ce que disent tes étoiles :</p>
            <div style="margin:30px 0; padding:20px; background:#f9f6ff; border-radius:12px; line-height:1.8;">
            {texte}
            </div>
            <p><strong>Allez avoue, tu veux en savoir plus 😏</strong><br><br>
            Cette analyse n'est qu'une première lecture. Le <strong>Flash Astral</strong> va plus loin :
            il met en lumière tes grands mécanismes, tes forces, tes blocages, et les zones de ton thème
            qui demandent à être comprises plus finement.</p>
            <p style="text-align:center; margin-top:30px;">
            <a href="https://lesfousdastro.fr"
            style="display:inline-block;padding:14px 28px;background:#1f628e;color:white;
            border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;">
            → Je veux en savoir plus !
            </a>
            </p>
            <p style="margin-top:40px;">À très vite sur les réseaux...en vrai, ou dans les étoiles si on se croise jamais (c'est triste mais c'est une possibilité).<br>
            Les Fous d'Astro by Cécile CL ✨</p>
            """).strip()


        if send_emails and email:
            try:
                Thread(
                    target=envoyer_email_avec_analyse,
                    kwargs=dict(
                        destinataire=email,
                        sujet=sujet,
                        contenu_txt=contenu_txt,
                        contenu_html=contenu_html,
                        pdf_path=None
                    ),
                    daemon=True
                ).start()
                print(f"✉️  Email en file d’envoi pour {email}")
            except Exception as e:
                print(f"⚠️ Email non envoyé (thread/SMTP) : {e}")
        else:
            print("✉️  Email non envoyé (SEND_EMAILS=false ou email manquant)")

        # 🎨 8) Génération du HTML pour le modal
        html = f"""
        <div class="analysis-summary">
            <h4>🌟 Bonjour {theme['nom']}, voici ton profil astrologique :</h4>
            <div style="margin: 20px 0; line-height: 1.6;">{texte}</div>
            
            <div style="margin-top:25px; padding:20px; background:rgba(31,98,142,0.1);
            border-radius:15px; text-align:center;">
                <p><strong>Tu veux aller plus loin ?</strong></p>
                <p style="margin-bottom:15px; color:#555;">
                    Cette analyse te donne une première lecture de ton thème.<br>
                    Deux façons de creuser selon ce qui t'attire :
                </p>

                <a href="/flash_astral"
                style="display:inline-block;padding:12px 24px;background:#1f628e;color:white;
                border-radius:8px;text-decoration:none;font-weight:bold;margin-bottom:10px;
                width:80%;max-width:300px;">
                ✨ Mon Flash Astral
                </a>
                <p style="font-size:12px;color:#777;margin:0 0 15px 0;">
                    Tes grands mécanismes, forces et blocages — PDF complet
                </p>

                <a href="/analyse_karmique"
                style="display:inline-block;padding:12px 24px;background:#6b3fa0;color:white;
                border-radius:8px;text-decoration:none;font-weight:bold;margin-bottom:10px;
                width:80%;max-width:300px;">
                🔮 Mon Analyse Karmique
                </a>
                <p style="font-size:12px;color:#777;margin:0 0 20px 0;">
                    D'où viennent tes schémas répétitifs — nœuds, Chiron, Lilith
                </p>

                <a href="/static/Exemple_Flash_Astral_Cecile.pdf" target="_blank"
                style="font-size:13px;color:#1f628e;text-decoration:underline;">
                📄 Voir un exemple du Flash Astral avant d'acheter
                </a>
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