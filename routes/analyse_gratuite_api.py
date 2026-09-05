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
from utils.brevo_contacts import ajouter_contact_brevo
from utils.llm_system_prompts import SYSTEM_BASE
from threading import Thread
from html import escape
import textwrap
from textwrap import dedent
from dotenv import load_dotenv
import os

load_dotenv()

gratuite_api_bp = Blueprint("gratuite_api_bp", __name__)


def _texte_analyse_vers_html(texte):
    """Affiche la réponse LLM comme du texte, avec de vrais paragraphes."""
    paragraphes = [
        escape(paragraphe.strip()).replace("\n", "<br>")
        for paragraphe in texte.split("\n\n")
        if paragraphe.strip()
    ]
    return "".join(f'<p style="margin:0 0 16px;">{p}</p>' for p in paragraphes)


def _generer_texte_analyse_gratuite(prompt):
    """Choisit le fournisseur du gratuit sans modifier le fournisseur global."""
    provider = (
        os.getenv("FREE_ANALYSIS_LLM_PROVIDER")
        or os.getenv("LLM_PROVIDER")
        or "claude"
    ).strip().lower()

    if provider == "openai":
        print("🤖 Analyse gratuite générée avec OpenAI")
        return interroger_llm(prompt, provider="openai")

    if provider == "claude":
        # Import tardif : une production restée sur OpenAI ne dépend pas de
        # la présence d'une clé Anthropic au démarrage.
        from utils.claude_llm import ask_claude

        print("🤖 Analyse gratuite générée avec Claude")
        try:
            return ask_claude(
                prompt=prompt,
                system=SYSTEM_BASE,
                max_tokens=900,
                temperature=0.6,
            )
        except Exception as claude_error:
            print(
                "⚠️ Claude indisponible pour le gratuit, repli vers OpenAI : "
                f"{claude_error}"
            )
            return interroger_llm(prompt, provider="openai")

    raise ValueError(
        "FREE_ANALYSIS_LLM_PROVIDER doit valoir 'openai' ou 'claude' "
        f"(valeur reçue : {provider!r})."
    )

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
        gender          = str(data.get("gender") or "").strip().lower()

        if gender not in {"male", "female"}:
            return jsonify({
                "ok": False,
                "error": "Le genre déclaré est obligatoire pour générer l’analyse."
            }), 400

        genre_label = "femme" if gender == "female" else "homme"

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
                    👉 Pour continuer ton exploration, découvre ton <strong>Point Astral complet</strong> :<br>
                    <ul style="text-align:left; display:inline-block; margin:10px auto; padding:0; list-style:disc;">
                        <li>Lecture approfondie & psychologiques (4 pages)</li>
                        <li>PDF personnalisé à télécharger</li>
                    </ul>
                    <br>
                    <a href="/#flash_astral" style="display:inline-block; padding:12px 20px; background:#856404; color:#fff; border-radius:8px; text-decoration:none; font-weight:bold;">
                        💫 Découvrir mon Point Astral
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

        # 🤖 5) Prompt : un aperçu concret qui ouvre vers le Point Astral
        prompt = dedent(
            f"""
            Tu es une astrologue expérimentée, directe, lucide avec une pointe d'humour noir.

            OBJECTIF
            Écris une véritable mini-analyse astrologique qui donne une preuve
            de personnalisation et fait apparaître UN ou DEUX mécanismes centraux
            du thème, choisis selon leur importance réelle dans les données fournies.
            L'aperçu doit permettre à la personne de se reconnaître dans une
            situation observable, tout en lui faisant comprendre qu'il reste à
            explorer l'origine, les contextes d'activation et les ressources
            liées à ce ou ces mécanismes. Ne rédige pas une analyse complète.

            Tu parles directement à la personne.
            Tu utilises le tutoiement.
            Tu ne flattes pas et tu n'emploies pas de phrases creuses.
            Tu fondes l'analyse sur l'astrologie occidentale tropicale. Tu peux
            utiliser le Nakshatra lunaire fourni comme éclairage complémentaire
            s'il enrichit réellement l'un des mécanismes retenus. Ne le cite pas
            artificiellement et n'en déduis pas automatiquement une affirmation
            karmique ou un événement de vie.

            Personne analysée : {theme.get("nom", "la personne")}
            Genre déclaré obligatoire : {genre_label}

            RÉSUMÉ SYNTHÉTIQUE :

            {resume_str}

            POSITIONS PLANÉTAIRES :

            {positions_str}

            ASPECTS ASTROLOGIQUES :

            {aspects_str}


            CONSTRUCTION OBLIGATOIRE
            1. Premier paragraphe : décris la manière dont la personne construit
               son identité ou apparaît au monde. Choisis seulement les facteurs
               réellement structurants et n'énumère pas les placements.
            2. Deuxième paragraphe : décris son fonctionnement émotionnel et
               relie-le à l'identité pour faire apparaître le paradoxe central.
            3. Troisième paragraphe : donne DEUX manifestations concrètes de ce
               ce ou ces mécanismes dans deux domaines de vie différents. Choisis uniquement
               des domaines soutenus par les maisons, les angles ou les maîtrises
               fournis. N'invente aucun événement biographique.
            4. Quatrième paragraphe : montre la ressource ET le revers possible
               des mécanismes retenus, puis formule clairement ce qui resterait à
               explorer pour le comprendre plus complètement.
            5. Termine par UNE question d'observation personnelle précise dans
               un dernier paragraphe très court.

            RÈGLES :

            - Commence directement par une dynamique humaine, jamais par un placement.
            - Ne fais pas une liste de placements.
            - Cite au maximum trois termes astrologiques dans tout le texte.
            - Ne répète pas plusieurs fois la même idée.
            - N'invente aucun placement ni aucun aspect.
            - Pour toute manifestation concrète, croise les facteurs disponibles
              dans ce thème (planètes, signes, maisons, aspects, angles, maîtrises
              et, s'il est pertinent, Nakshatra lunaire). Ne transforme jamais
              le symbolisme isolé d'un seul facteur en certitude biographique.
            - Évite les compliments invérifiables comme « magnétique »,
              « charismatique », « exceptionnel » ou « don naturel ».
            - Évite les formulations dramatiques ou diagnostiques comme
              « tourmenté », « toxique », « traumatisme » ou « blessure profonde ».
            - Utilise « tu peux », « il est possible » ou « semble » lorsque
              l'interprétation n'est pas certaine.
            - Pas de conseil générique de développement personnel.
            - Pas de syntaxe Markdown.
            - Texte brut uniquement.
            - Respecte obligatoirement le genre déclaré dans tous les adjectifs
              et participes.
            - Quatre paragraphes courts, puis la question finale.
            - Entre 220 et 260 mots. Ne produis jamais moins de 220 mots.
            """
        ).strip()

        print("📤 Prompt envoyé à l'IA :", prompt)

        # 🤖 6) Appel à l'IA
        texte = _generer_texte_analyse_gratuite(prompt)
        print("✅ Analyse IA reçue :", texte[:100] + "...")
        texte_html = _texte_analyse_vers_html(texte)

        # 📧 7) Envoi email + Google Sheets (comme dans l'ancienne version)
        prenom = theme['nom'].split()[0]
        prenom_html = escape(prenom)
        nom_html = escape(str(theme['nom']))
        
        # Ajout au Google Sheet — logs détaillés
        print(f"[LEAD] Tentative d'ajout au Google Sheet — email='{email}', prenom='{prenom}'")

        try:
            if not email or "@" not in email:
                raise ValueError(f"Email invalide: {email!r}")

            ajouter_email_au_sheet(email, prenom)
            try:
                contact_brevo_ok = ajouter_contact_brevo(
                    email=email,
                    nom=nom,
                    liste="flash",
                )

                if contact_brevo_ok:
                    print(f"✅ Contact ajouté à Brevo : {email}")
                else:
                    print(f"❌ Échec ajout Brevo : {email}")

            except Exception as e:
                print(f"❌ Exception pendant l'ajout Brevo : {e}")
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

            Cet aperçu met en lumière un mécanisme central, mais pas encore ses origines,
            les situations dans lesquelles il s'active ni les ressources qui permettent de mieux le vivre.
            Le Point Astral Essentiel relie ces différentes dimensions dans une analyse personnalisée de 4 à 6 pages.

            👉 Découvrir mon Point Astral Essentiel — 25 € : https://lesfousdastro.fr/#flash_astral

            À très vite sur les réseaux...en vrai, ou dans les étoiles si on se croise jamais (c'est triste mais c'est une possibilité).
            Les Fous d'Astro by Cécile CL ✨
            """).strip()

        contenu_html = textwrap.dedent(f"""
            <p>Bonjour {prenom_html},</p>
            <p>Tu l'as demandé, Cécile l'a fait...Ou plutôt les étoiles ont répondu 🔭</p>
            <p>Allez, voici ce que disent tes étoiles :</p>
            <div style="margin:30px 0; padding:20px; background:#f9f6ff; border-radius:12px; line-height:1.8;">
            {texte_html}
            </div>
            <p><strong>Ton aperçu s'arrête là où l'exploration commence.</strong><br><br>
            Il met en lumière un mécanisme central, mais pas encore ses origines,
            les situations dans lesquelles il s'active ni les ressources qui permettent de mieux le vivre.
            Le <strong>Point Astral Essentiel</strong> relie ces dimensions dans une analyse personnalisée de 4 à 6 pages.</p>
            <p style="text-align:center; margin-top:30px;">
            <a href="https://lesfousdastro.fr/#flash_astral"
            style="display:inline-block;padding:14px 28px;background:#1f628e;color:white;
            border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;">
            Comprendre les mécanismes de mon thème — 25 €
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
            <h4>🌟 Bonjour {nom_html}, voici ton profil astrologique :</h4>
            <div style="margin: 20px 0; line-height: 1.6;">{texte_html}</div>
            
            <div style="margin-top:25px; padding:20px; background:rgba(31,98,142,0.1);
            border-radius:15px; text-align:center;">
                <p style="margin-bottom:15px; color:#555;">
                    Cet aperçu montre un mécanisme central. Le <strong>Point Astral Essentiel</strong>
                    explore ses origines, ses contextes d'activation et les ressources de ton thème
                    dans une analyse personnalisée de 4 à 6 pages.
                </p>

                <button type="button" onclick="choosePointAstralFromFreeAnalysis()"
                style="display:inline-block;padding:12px 24px;background:#1f628e;color:white;
                border:0;border-radius:8px;text-decoration:none;font-weight:bold;cursor:pointer;
                width:80%;max-width:300px;">
                Comprendre les mécanismes de mon thème — 25 €
                </button>
                <br>
                <a href="/static/pdfs/Exemple_Flash_Astral_Cecile.pdf" target="_blank" rel="noopener"
                style="display:inline-block;margin-top:14px;font-size:13px;color:#1f628e;text-decoration:underline;">
                Voir un exemple avant de choisir
                </a>
            </div>
        </div>
    """




    #     html = f"""
    #     <div class="analysis-summary">
    #         <h4>🌟 Bonjour {theme['nom']}, voici ton profil astrologique :</h4>
    #         <div style="margin: 20px 0; line-height: 1.6;">{texte}</div>
            
    #         <div style="margin-top:25px; padding:20px; background:rgba(31,98,142,0.1);
    #         border-radius:15px; text-align:center;">
    #             <p><strong>Tu veux aller plus loin ?</strong></p>
    #             <p style="margin-bottom:15px; color:#555;">
    #                 Cette analyse te donne une première lecture de ton thème.<br>
    #                 Deux façons de creuser selon ce qui t'attire :
    #             </p>

    #             <a href="/flash_astral"
    #             style="display:inline-block;padding:12px 24px;background:#1f628e;color:white;
    #             border-radius:8px;text-decoration:none;font-weight:bold;margin-bottom:10px;
    #             width:80%;max-width:300px;">
    #             ✨ Mon Point Astral
    #             </a>
    #             <p style="font-size:12px;color:#777;margin:0 0 15px 0;">
    #                 Tes grands mécanismes, forces et blocages — PDF complet
    #             </p>

    #             <a href="/analyse_karmique"
    #             style="display:inline-block;padding:12px 24px;background:#6b3fa0;color:white;
    #             border-radius:8px;text-decoration:none;font-weight:bold;margin-bottom:10px;
    #             width:80%;max-width:300px;">
    #             🔮 Mon Analyse Karmique
    #             </a>
    #             <p style="font-size:12px;color:#777;margin:0 0 20px 0;">
    #                 D'où viennent tes schémas répétitifs — nœuds, Chiron, Lilith
    #             </p>

    #             <a href="/static/pdfs/Exemple_Flash_Astral_Cecile.pdf" target="_blank"
    #             style="font-size:13px;color:#1f628e;text-decoration:underline;">
    #             📄 Voir un exemple du Point Astral avant d'acheter
    #             </a>
    #         </div>
    #     </div>
    # """

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
