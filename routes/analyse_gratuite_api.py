# routes/analyse_gratuite_api.py
from flask import Blueprint, request, jsonify, render_template, current_app
from utils.calcul_theme import calcul_theme
from utils.utils_analyse import analyse_gratuite
from utils.formatage import formater_positions_planetes
from utils.analyse_gratuite_formatage import formater_aspects
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.enregistrement_placements import enregistrer_placements_utilisateur
from utils.google.sheets_writer import ajouter_email_au_sheet, ajouter_reponse_analyse_gratuite
from utils.email_sender import envoyer_email_avec_analyse
from utils.email_quota import check_and_log_email_quota
from utils.brevo_contacts import ajouter_contact_brevo
from utils.llm_system_prompts import SYSTEM_ANALYSE_GRATUITE as SYSTEM_BASE
from utils.analyse_gratuite_figures import preparer_figures_analyse_gratuite
from threading import Thread
from html import escape
import textwrap
from textwrap import dedent
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

gratuite_api_bp = Blueprint("gratuite_api_bp", __name__)

RAISONS_ANALYSE_GRATUITE = {
    "enough": "L’analyse gratuite me suffit",
    "choice": "Je ne sais pas quelle analyse choisir",
    "sample": "Je veux voir un rapport complet",
    "price": "Le prix me freine",
    "personalization": "Je ne comprends pas ce qui est personnalisé",
    "not_ready": "Je ne suis pas prête maintenant",
    "other": "Autre",
}


@gratuite_api_bp.post("/api/analyse_gratuite/feedback")
def enregistrer_reponse_analyse_gratuite():
    data = request.get_json(silent=True) or {}
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("reason"), str)
        or data["reason"] not in RAISONS_ANALYSE_GRATUITE
    ):
        return jsonify({"ok": False}), 400
    try:
        analysis_id = str(uuid.UUID(data.get("analysis_id", "")))
    except (ValueError, TypeError, AttributeError):
        return jsonify({"ok": False}), 400
    try:
        saved = ajouter_reponse_analyse_gratuite(
            analysis_id, RAISONS_ANALYSE_GRATUITE[data["reason"]]
        )
    except Exception:
        current_app.logger.exception("Échec de l'enregistrement du retour de l'analyse gratuite")
        return jsonify({"ok": False}), 503
    return jsonify({"ok": saved}), 200 if saved else 404


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
        from openai import OpenAI

        reponse = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), max_retries=0
        ).chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8000,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0,
        )
        choix = reponse.choices[0]
        texte = choix.message.content or ""
        print("=== OPENAI : RÉPONSE BRUTE ET TOKENS ===", reponse.model_dump_json(indent=2))
        if choix.finish_reason != "stop" or getattr(choix.message, "refusal", None) or not texte.strip():
            raise RuntimeError("Réponse IA incomplète : génération gratuite interrompue.")
        return texte

    if provider == "claude":
        # Import tardif : une production restée sur OpenAI ne dépend pas de
        # la présence d'une clé Anthropic au démarrage.
        from utils.claude_llm import ask_claude

        print("🤖 Analyse gratuite générée avec Claude")
        # Une seule tentative : conserver l'échec sans nouvelle génération payante.
        return ask_claude(
            prompt=prompt,
            model="claude-sonnet-5-5",  # Modèle du local validé, sans changer les autres rapports.
            system=SYSTEM_BASE,
            max_tokens=900,
            temperature=0.6,
            single_attempt=True,
        )

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
                    👉 Pour continuer ton exploration, découvre ton <strong>Point Astral Essentiel à 25 €</strong> :<br>
                    <ul style="text-align:left; display:inline-block; margin:10px auto; padding:0; list-style:disc;">
                        <li>Lecture des grandes dynamiques de ton thème (environ 4 à 6 pages)</li>
                        <li>PDF personnalisé à télécharger</li>
                    </ul>
                    <br>
                    <a href="/#flash_astral" style="display:inline-block; padding:12px 20px; background:#856404; color:#fff; border-radius:8px; text-decoration:none; font-weight:bold;">
                        💫 Découvrir mon Point Astral Essentiel à 25 €
                    </a>
                </div>
            """
            print(f"[QUOTA] Bloqué: email={email} ({email_count}), ip={ip} ({ip_count})")
            return jsonify({"ok": True, "limited": True, "html": html_limit}), 200

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

        from utils.filtrage_rapports import sans_point_illumination
        theme = sans_point_illumination(theme)

        # 📝 2) Résumé + formats
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
        configurations, configurations_str = preparer_figures_analyse_gratuite(theme)
        maitre_ascendant = theme.get("maitre_ascendant") or {}
        maitre_ascendant_nom = (
            maitre_ascendant.get("nom")
            if isinstance(maitre_ascendant, dict) else maitre_ascendant
        ) or "non fourni"
        print(f"🪐 Figures et conjonctions détectées : {len(configurations)}")
        print(configurations_str)

        # 🤖 3) Prompt : un aperçu concret qui ouvre vers le Point Astral
        prompt = dedent(
            f"""
            Tu es une astrologue expérimentée, directe, lucide avec une pointe d'humour noir.

            OBJECTIF
            Écris une mini-analyse astrologique et fait apparaître UN ou DEUX mécanismes centraux
            du thème, choisis selon leur importance réelle dans les données fournies.
            L'aperçu doit permettre à la personne de se reconnaître dans une
            situation observable, tout en lui faisant comprendre qu'il reste beaucoup plus à
            explorer. Cette analyse doit être uniquement une mise en bouche.

            Tu parles directement à la personne.
            Tu utilises le tutoiement.
            Tu ne flattes pas et tu n'emploies pas de phrases creuses.
            Tu fondes l'analyse sur l'astrologie occidentale tropicale. Tu peux
            utiliser le Nakshatra lunaire fourni comme éclairage complémentaire. 

            Termine par UNE question d'observation personnelle précise dans
            un dernier paragraphe très court.
            

            Personne analysée : {theme.get("nom", "la personne")}
            Genre déclaré obligatoire : {genre_label}

            RÉSUMÉ SYNTHÉTIQUE :

            {resume_str}

            POSITIONS PLANÉTAIRES :

            {positions_str}

            ASPECTS ASTROLOGIQUES :

            {aspects_str}

            FIGURES ET CONJONCTIONS VÉRIFIÉES PAR LE MOTEUR :

            {configurations_str}

            Maître de l'Ascendant calculé : {maitre_ascendant_nom}

                
            RÈGLES :

            - Commence directement par une dynamique humaine, jamais par un placement.
            - Ne fais pas une liste de placements.
            - Cite au maximum trois termes astrologiques dans tout le texte.
            - Ne répète pas plusieurs fois la même idée.
            - N'invente aucun placement ni aucun aspect.
            - Pour toute manifestation concrète, croise les facteurs disponibles
              dans ce thème (planètes, signes, maisons, aspects, figures vérifiées, angles, maîtrises
              et, s'il est pertinent, Nakshatra lunaire). Ne transforme jamais
              le symbolisme isolé d'un seul facteur en certitude biographique.
            - Pas de syntaxe Markdown.
            - Texte brut uniquement.
            - Respecte obligatoirement le genre déclaré dans tous les adjectifs
              et participes.
            - Quatre paragraphes courts, puis la question finale.
            - Entre 220 et 260 mots. Ne produis jamais moins de 220 mots.
            """
        ).strip()

        print("📤 Prompt envoyé à l'IA :", prompt)

        # 🤖 4) Appel à l'IA
        texte = _generer_texte_analyse_gratuite(prompt)
        print("✅ Analyse IA reçue (texte intégral) :", texte)
        print(f"📏 Nombre de mots reçu : {len(texte.split())} (consigne : 220–260, sans réécriture automatique)")
        texte_html = _texte_analyse_vers_html(texte)

        # 📧 7) Envoi email + Google Sheets (comme dans l'ancienne version)
        prenom = theme['nom'].split()[0]
        prenom_html = escape(prenom)
        nom_html = escape(str(theme['nom']))
        
        # Ajout au Google Sheet — logs détaillés
        print(f"[LEAD] Tentative d'ajout au Google Sheet — email='{email}', prenom='{prenom}'")

        analysis_id = str(uuid.uuid4())
        sheet_saved = False
        try:
            if not email or "@" not in email:
                raise ValueError(f"Email invalide: {email!r}")

            ajouter_email_au_sheet(email, prenom, analysis_id=analysis_id)
            sheet_saved = True
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

            Exemple complet : https://lesfousdastro.fr/static/pdfs/Exemple_Flash_Astral_Cecile.pdf
            Réception par email après paiement et génération, généralement en quelques minutes.

            👉 Découvrir mon Point Astral Essentiel à 25 € : https://lesfousdastro.fr/?utm_source=newsletter&utm_campaign=free_analysis#flash_astral

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
            <p><a href="https://lesfousdastro.fr/static/pdfs/Exemple_Flash_Astral_Cecile.pdf">Lire un rapport complet d’exemple (PDF)</a></p>
            <p>Réception par email après paiement et génération, généralement en quelques minutes.</p>
            <p style="text-align:center; margin-top:30px;">
            <a href="https://lesfousdastro.fr/?utm_source=newsletter&utm_campaign=free_analysis#flash_astral"
            style="display:inline-block;padding:14px 28px;background:#1f628e;color:white;
            border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;">
            Comprendre les mécanismes de mon thème à 25 €
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
            
            <div class="free-analysis-offer">
                <p>Le <strong>Point Astral Essentiel</strong> relie les grandes dynamiques
                    de ton thème dans un PDF personnalisé de 4 à 6 pages.</p>
                <p><strong>25 € au total.</strong> Reçu par email après le paiement et la génération.</p>
                <div class="free-analysis-offer-actions">
                <a href="/static/pdfs/Exemple_Flash_Astral_Cecile.pdf" target="_blank" rel="noopener"
                style="display:inline-block;font-size:14px;min-height:44px;padding:12px;color:#1f628e;text-decoration:underline;">
                Lire le rapport complet d’exemple (PDF)
                </a>
                <br><button type="button" onclick="exploreMoreAnalyses()" style="background:none;border:0;color:#1f628e;padding:8px;text-decoration:underline;cursor:pointer;">Voir les autres analyses</button>
                </div>
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
    #             style="font-size:16px;min-height:44px;padding:12px;color:#1f628e;text-decoration:underline;">
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
            'configurations_majeures': configurations,
            'ascendant': theme.get('ascendant', 'Non calculé')
        }

        
        return jsonify({
            "ok": True, 
            "html": html,
            "analysis_id": analysis_id if sheet_saved else None,
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
