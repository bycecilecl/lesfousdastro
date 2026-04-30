# routes/profil_amoureux_module.py
# Module complet pour l'Analyse Amoureuse (4 modules + PDF + email)

from flask import Blueprint, render_template, session, current_app, url_for, request
import os
import base64
from datetime import datetime
import inspect
import logging
from threading import Thread

from utils.calcul_theme import calcul_theme as _calcul_theme
from utils.pdf_utils import html_to_pdf
from utils.genre import get_user_prefs
from utils.s3_utils import upload_file_and_presign
from utils.email_sender import envoyer_email_avec_analyse
import json, hashlib, time

# Modules amour (génération des 4 blocs)
from module.amour_blocs.maniere_aimer import generer_bloc_maniere_aimer
from module.amour_blocs.partenaire_ideal import generer_bloc_partenaire_ideal
from module.amour_blocs.couple_ideal import generer_bloc_couple_ideal
from module.amour_blocs.intimite_sexualite import generer_bloc_intimite_sexualite
from module.amour_blocs.maniere_aimer import generer_snippets_maniere_aimer
from config.analysis_sandbox import is_analysis_sandbox

logger = logging.getLogger(__name__)

# Blueprint pour le module Profil Amoureux
profil_amoureux_module = Blueprint(
    "profil_amoureux_module",
    __name__,
    url_prefix="/profil-amoureux"
)

def _fingerprint_infos(infos: dict) -> str:
    """Empreinte stable des infos utilisateur pour idempotence."""
    try:
        payload = json.dumps(infos or {}, sort_keys=True, ensure_ascii=False)
    except Exception:
        payload = str(infos or {})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def debug_snippets_profil_amoureux(theme, polarite: str) -> str:
    """
    Retourne une grosse string avec TOUS les snippets utilisés
    pour les 4 modules, pour un thème donné.
    """

    # Module 1 : on a déjà une fonction dédiée
    m1_snip = generer_snippets_maniere_aimer(theme, polarite=polarite)

    # Modules 2, 3, 4 : on utilise call_llm=False
    m2_snip = generer_bloc_partenaire_ideal(theme, call_llm=False, polarite=polarite)
    m3_snip = generer_bloc_couple_ideal(theme, call_llm=False, polarite=polarite)
    m4_snip = generer_bloc_intimite_sexualite(theme, call_llm=False, polarite=polarite)

    # On assemble tout proprement
    big_dump = [
        "===== DEBUG SNIPPETS PROFIL AMOUREUX =====",
        "",
        "### MODULE 1 · MA MANIÈRE D'AIMER (SNIPPETS BRUTS) ###",
        m1_snip or "(aucun)",
        "",
        "### MODULE 2 · PARTENAIRE IDÉAL (SNIPPETS BRUTS) ###",
        m2_snip or "(aucun)",
        "",
        "### MODULE 3 · COUPLE & DYNAMIQUE RELATIONNELLE (SNIPPETS BRUTS) ###",
        m3_snip or "(aucun)",
        "",
        "### MODULE 4 · INTIMITÉ & SEXUALITÉ (SNIPPETS BRUTS) ###",
        m4_snip or "(aucun)",
    ]

    return "\n".join(big_dump)

# ---------- Wrapper sûr pour calcul_theme ----------
def calcul_theme_safe(**kwargs):
    """
    Appelle utils.calcul_theme en ne passant QUE les paramètres qu'il accepte.
    Évite les TypeError 'unexpected keyword' et 'missing required positional'.
    """
    sig = inspect.signature(_calcul_theme)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    for name, param in sig.parameters.items():
        if param.default is inspect._empty and name not in accepted:
            if name == "nom":
                accepted[name] = "Analyse Amour"
    return _calcul_theme(**accepted)


def _texte_en_html_paragraphes(texte: str) -> str:
    """Transforme un texte brut en <p>…</p> propres pour le HTML/PDF."""
    if not texte:
        return ""
    blocs = [b.strip() for b in texte.split("\n\n") if b.strip()]
    out = []
    for b in blocs:
        out.append(f"<p>{b.replace(chr(10), ' ')}</p>")
    return "\n".join(out)


def generer_html_final_amour_pdf(
    texte_modules_html: str,
    infos_personnelles: dict,
    logo_base64: str = "",
) -> str:
    """HTML final pour le PDF de l'Analyse Amoureuse (titre + disclaimers)."""

    nom = infos_personnelles.get("nom", "Analyse Anonyme")
    date_naissance = infos_personnelles.get("date_naissance", "")
    heure_naissance = infos_personnelles.get("heure_naissance", "")
    lieu_naissance = infos_personnelles.get("lieu_naissance", "")

    logo_html = (
        f'<img src="data:image/webp;base64,{logo_base64}" '
        f'alt="Logo Les Fous d&#39;Astro" class="logo">'
        if logo_base64 else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Analyse Amoureuse - {nom}</title>
    <style>
        body {{
            font-family: Georgia, serif;
            margin: 0;
            padding: 40px;
            background: #ffffff;
            color: #2c3e50;
            line-height: 1.6;
        }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }}
        .logo {{
            max-width: 150px;
            max-height: 80px;
            width: auto;
            height: auto;
            object-fit: contain;
            margin-bottom: 12px;
        }}
        .personal-info {{
            text-align: center !important;
            margin: 2px 0 0 0;
            font-size: 0.9em;
            color: #666;
        }}
        main {{ margin: 0; }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 12px;
            font-size: 2.0em;
        }}
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #e91e63;
            padding-bottom: 5px;
            margin-top: 40px;
            page-break-after: avoid;
        }}
        h3 {{ color: #34495e; margin-top: 30px; }}
        main p {{ margin-bottom: 15px; text-align: justify; }}
        .section {{ margin-bottom: 40px; page-break-inside: avoid; }}
        .disclaimer {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            page-break-inside: avoid;
        }}
        footer {{
            text-align: center;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        @media print {{
            body {{ background: white; padding: 20px; }}
            .container {{ max-width: none; }}
            .header {{ page-break-after: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        {logo_html}
        <h1>💗 Mon Profil Amoureux - {nom}</h1>
        <div class="personal-info">
            <p>{date_naissance} — {heure_naissance} — {lieu_naissance}</p>
        </div>
    </div>

    <div class="disclaimer">
        <p><strong>⚠️ À propos de cette analyse amoureuse :</strong><br>
        Ce document est une lecture automatisée de ton thème natal centrée sur ta manière d'aimer,
        ce qui t'attire, ta dynamique de couple et ton rapport à l'intimité. 
        Il ne prédit pas si tu vas « finir en couple » ou non, ni avec qui.</p>

        <p>Il parle de <u>tendances intérieures</u>, de scénarios fréquents, de blessures et de forces.
        La façon dont tu les vis dépend de ton niveau de conscience, de ton histoire, de tes choix.
        Tu peux t'y reconnaître totalement, partiellement, ou pas encore — certains thèmes se révèlent avec le temps.</p>

        <p>Cette analyse n'est pas un verdict sur ta vie affective, ni un avis médical ou psychologique.
        C'est un miroir symbolique pour t'aider à comprendre ce qui se joue en toi dans le lien amoureux,
        afin de reprendre du pouvoir sur tes choix et tes relations.</p>

        <p><strong>💬 Pour aller plus loin :</strong> rien ne remplacera un échange en direct 
        pour croiser ton vécu, ton histoire et ton thème. 
        Tu peux réserver une séance personnalisée sur 
        <a href="https://bycecilecl.com" target="_blank">bycecilecl.com</a>.</p>
    </div>

    <main>
        {texte_modules_html}
    </main>

    <footer>
        <p><strong>Les Fous d'Astro</strong> – Mon Profil Amoureux généré automatiquement</p>
        <p>lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr</p>
        <p>IG : @lesfousdastro • @bycecilecl</p>
    </footer>
</body>
</html>"""
    return html

def generer_profil_amoureux_pdf_s3(infos, envoyer_email=False):
    """
    Génère le Profil Amoureux en PDF + S3.
    Utilisable depuis les packs/background.
    """

    if is_analysis_sandbox():
        logger.info("🧪 SANDBOX Profil amoureux")

        return {
            "product_id": "profil_amoureux",
            "label": "Profil amoureux",
            "pdf_url": "https://sandbox.lesfousdastro.fr/profil-amoureux-test",
            "pdf_path": None,
            "status": "sandbox",
        }
    

    if not infos:
        raise ValueError("infos_utilisateur manquant pour Profil Amoureux")

    if infos.get("lat") and infos.get("lon"):
        data_theme = calcul_theme_safe(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"],
            lat=float(infos["lat"]),
            lon=float(infos["lon"]),
            tzid=infos.get("tzid"),
        )
    else:
        data_theme = calcul_theme_safe(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"],
        )

    genre_form = (infos.get("gender") or "").lower()
    polarite = "Femme" if genre_form == "female" else "Homme"

    snippets_m1 = generer_snippets_maniere_aimer(data_theme, polarite=polarite)

    m1 = generer_bloc_maniere_aimer(data_theme, call_llm=True, polarite=polarite)
    m2 = generer_bloc_partenaire_ideal(data_theme, call_llm=True, polarite=polarite)
    m3 = generer_bloc_couple_ideal(
        data_theme,
        call_llm=True,
        polarite=polarite,
        bilan_amour=snippets_m1,
    )
    m4 = generer_bloc_intimite_sexualite(data_theme, call_llm=True, polarite=polarite)

    sections_html = []

    if m1:
        sections_html.append(f"""
            <section class="section">
                <h2>Module 1 · Ma manière d'aimer</h2>
                <div class="section-content">
                    {_texte_en_html_paragraphes(m1)}
                </div>
            </section>
        """)

    if m2:
        sections_html.append(f"""
            <section class="section">
                <h2>Module 2 · Partenaire idéal : ce qui t'attire</h2>
                <div class="section-content">
                    {_texte_en_html_paragraphes(m2)}
                </div>
            </section>
        """)

    if m3:
        sections_html.append(f"""
            <section class="section">
                <h2>Module 3 · Couple idéal & dynamique relationnelle</h2>
                <div class="section-content">
                    {_texte_en_html_paragraphes(m3)}
                </div>
            </section>
        """)

    if m4:
        sections_html.append(f"""
            <section class="section">
                <h2>Module 4 · Intimité & sexualité</h2>
                <div class="section-content">
                    {_texte_en_html_paragraphes(m4)}
                </div>
            </section>
        """)

    html_content = "\n".join(sections_html).strip()

    if not html_content:
        raise ValueError("Profil Amoureux : aucun contenu généré")

    logo_base64 = ""
    logo_path = os.path.join(current_app.static_folder, "images", "logo_les_fous_dastro.webp")

    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        current_app.logger.warning("[PA PACK] Logo non chargé : %s", e)

    nom_clean = (infos.get("nom") or "Analyse_Amour").replace(" ", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nom_fichier = f"Profil_Amoureux_{nom_clean}_{timestamp}"

    output_dir = os.path.join(current_app.static_folder, "pdfs")
    os.makedirs(output_dir, exist_ok=True)

    pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

    html_pdf = generer_html_final_amour_pdf(
        texte_modules_html=html_content,
        infos_personnelles=infos,
        logo_base64=logo_base64,
    )

    html_to_pdf(html_pdf, pdf_path)

    pdf_final_url = None

    try:
        s3_info = upload_file_and_presign(
            pdf_path,
            key_prefix="profil_amoureux",
            content_type="application/pdf",
        )
        pdf_final_url = s3_info.get("url") or s3_info.get("presigned_url")
    except Exception as e:
        current_app.logger.warning("[PA PACK] Upload S3 KO : %s", e)

    return {
        "product_id": "profil_amoureux",
        "label": "Analyse Amoureuse complète",
        "pdf_url": pdf_final_url,
        "pdf_path": pdf_path,
        "status": "completed",
    }

@profil_amoureux_module.route("/complet")
def profil_amoureux_complet():
    """
    Workflow complet de l'Analyse Amoureuse :
    1. Récupère les infos depuis la session
    2. Calcule le thème natal
    3. Génère les 4 modules via LLM
    4. Crée le PDF
    5. Upload S3 + envoie l'email
    6. Affiche le résultat HTML
    """

    # 🔐 Raccourci SANDBOX : on ne génère rien de lourd
    if is_analysis_sandbox():
        infos = session.get("infos_utilisateur") or {}
        current_app.logger.info(
            f"[SANDBOX] Profil Amoureux non généré pour {infos.get('nom', 'N/A')}"
        )
        return render_template(
            "debug_sandbox.html",
            titre="Profil Amoureux – Analyse factice (SANDBOX)",
            infos=infos,
        )
    
    # 🔍 Debug paiement (comme Forces & Défis)
    current_app.logger.info(f"[PA DEBUG] paiement_valide={session.get('paiement_valide')}")
    current_app.logger.info(f"[PA DEBUG] last_payment={session.get('last_payment')}")
    current_app.logger.info(f"[PA DEBUG] ordered_products={session.get('ordered_products')}")

    # 1) On exige au moins un paiement validé
    if not session.get("paiement_valide"):
        return render_template(
            "erreur.html",
            titre="Profil Amoureux",
            message="Aucun paiement confirmé."
        ), 400

    # 2) Vérifier que profil_amoureux est dans les produits (mais on ne bloque pas en prod)
    ordered = session.get("ordered_products") or []
    if "profil_amoureux" not in ordered:
        current_app.logger.warning("[PA] Produit profil_amoureux non présent dans ordered_products")
        # On laisse passer pour ne pas casser tes tests en prod.
    
    infos = session.get("infos_utilisateur")
    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire.", 400
    

    # === Anti-reload minimal (TTL 15 min) spécifique Profil Amoureux ===
    current_fingerprint = _fingerprint_infos(infos)
    ANTI_RELOAD = os.getenv("ANTI_RELOAD", "true").lower() in ("1", "true", "yes")

    if ANTI_RELOAD:
        last_fingerprint = session.get("last_fingerprint_profil_amoureux")
        lock_until = float(session.get("lock_until_profil_amoureux", 0))

        # Si le verrou est encore actif et que c'est la même commande
        if time.time() < lock_until and current_fingerprint == last_fingerprint:
            last_url = session.get("last_pdf_url_profil_amoureux")
            if last_url:
                # On renvoie vers la page standard avec le PDF existant
                return render_template(
                    "paiement_effectue.html",
                    pdf_url=last_url,
                    already=True
                )
            # Pas d'URL en mémoire → on refuse gentiment
            return "Cette action a déjà été effectuée. Réessaie dans quelques minutes.", 429

        # Sinon, on pose / prolonge le verrou pour 15 minutes
        session["last_fingerprint_profil_amoureux"] = current_fingerprint
        session["lock_until_profil_amoureux"] = time.time() + 15 * 60
    # -------------------------------------------------------------------

    print("\n" + "=" * 60)
    print("💗 DÉBUT ANALYSE PROFIL AMOUREUX")
    print(f"👤 Nom: {infos.get('nom', 'Anonyme')}")
    print("=" * 60)

    try:
        # ═══════════════════════════════════════════════════════════
        # 1) CALCUL DU THÈME NATAL
        # ═══════════════════════════════════════════════════════════
        print("🔧 Étape 1: Calcul du thème natal...")
        
        if infos.get("lat") and infos.get("lon"):
            print(f"🎯 Coordonnées précises: {infos['lat']}, {infos['lon']}")
            data_theme = calcul_theme_safe(
                nom=infos["nom"],
                date_naissance=infos["date_naissance"],
                heure_naissance=infos["heure_naissance"],
                lieu_naissance=infos["lieu_naissance"],
                lat=float(infos["lat"]),
                lon=float(infos["lon"]),
                tzid=infos.get("tzid"),
            )
        else:
            print("🎯 Fallback géocodage")
            data_theme = calcul_theme_safe(
                nom=infos["nom"],
                date_naissance=infos["date_naissance"],
                heure_naissance=infos["heure_naissance"],
                lieu_naissance=infos["lieu_naissance"],
            )
        print("✅ Thème natal calculé")

        # ═══════════════════════════════════════════════════════════
        # 2) DÉTERMINATION DE LA POLARITÉ (genre)
        # ═══════════════════════════════════════════════════════════
        prefs = get_user_prefs(session, request)
        genre_form = (infos.get("gender") or "").lower()
        
        if genre_form == "female":
            polarite = "Femme"
        elif genre_form == "male":
            polarite = "Homme"
        else:
            polarite = "Homme"  # fallback
            
        print(f"👤 Polarité utilisée : {polarite}")

        # ═══════════════════════════════════════════════════════════
        # DEBUG SNIPPETS GLOBAL (si ?debug_snippets=1)
        # ═══════════════════════════════════════════════════════════
        if request.args.get("debug_snippets") == "1":
            dump = debug_snippets_profil_amoureux(data_theme, polarite)

            print("\n===== DEBUG : SNIPPETS COMPLETS PROFIL AMOUREUX =====")
            print(dump)
            print("💻 Pour afficher tous les snippets : ajouter ?debug_snippets=1 à l’URL")
            print("======================================================\n")

            # On affiche les snippets directement dans le navigateur
            return f"<pre>{dump}</pre>"

        # ═══════════════════════════════════════════════════════════
        # 3) GÉNÉRATION DES 4 MODULES VIA LLM
        # ═══════════════════════════════════════════════════════════
        print("✨ Étape 2: Génération des 4 modules LLM...")

        # 🔍 Récupération des snippets bruts du Module 1
        snippets_m1 = generer_snippets_maniere_aimer(data_theme, polarite=polarite)

        print("\n===== DEBUG SNIPPETS M1 (pour Module 3) =====")
        print(snippets_m1)
        print("==============================================\n")
        
        print("   → Module 1: Ma manière d'aimer...")
        m1 = generer_bloc_maniere_aimer(data_theme, call_llm=True, polarite=polarite)
        print(f"   ✅ Module 1: {len(m1)} caractères")
        
        print("   → Module 2: Partenaire idéal...")
        m2 = generer_bloc_partenaire_ideal(data_theme, call_llm=True, polarite=polarite)
        print(f"   ✅ Module 2: {len(m2)} caractères")

        print("   → Module 3: Couple idéal...")
        m3 = generer_bloc_couple_ideal(
            data_theme,
            call_llm=True,
            polarite=polarite,      # on passe la polarité aussi
            bilan_amour=snippets_m1  # 🔥 on injecte les données du Module 1
        )
        print(f"   ✅ Module 3: {len(m3)} caractères")
        
        print("   → Module 4: Intimité & sexualité...")
        m4 = generer_bloc_intimite_sexualite(data_theme, call_llm=True, polarite=polarite)
        print(f"   ✅ Module 4: {len(m4)} caractères")

        # ═══════════════════════════════════════════════════════════
        # 4) MISE EN FORME HTML (pour web + PDF)
        # ═══════════════════════════════════════════════════════════
        print("🎨 Étape 3: Mise en forme HTML...")
        
        sections_html = []

        if m1:
            sections_html.append(f"""
                <section class="section">
                    <h2>Module 1 · Ma manière d'aimer</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m1)}
                    </div>
                </section>
            """)
        
        if m2:
            sections_html.append(f"""
                <section class="section">
                    <h2>Module 2 · Partenaire idéal : ce qui t'attire</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m2)}
                    </div>
                </section>
            """)
        
        if m3:
            sections_html.append(f"""
                <section class="section">
                    <h2>Module 3 · Couple idéal & dynamique relationnelle</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m3)}
                    </div>
                </section>
            """)
        
        if m4:
            sections_html.append(f"""
                <section class="section">
                    <h2>Module 4 · Intimité & sexualité</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m4)}
                    </div>
                </section>
            """)

        html_content = "\n".join(sections_html).strip()
        
        if not html_content:
            return render_template(
                "erreur.html",
                titre="Profil Amoureux",
                message="Aucun contenu n'a pu être généré.",
                details="Les quatre modules ont renvoyé un texte vide.",
            ), 500

        print(f"✅ HTML content: {len(html_content)} caractères")

        # ═══════════════════════════════════════════════════════════
        # 5) CHARGEMENT DU LOGO
        # ═══════════════════════════════════════════════════════════
        logo_base64 = ""
        logo_path = os.path.join(current_app.static_folder, "images", "logo_les_fous_dastro.webp")
        try:
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img_file:
                    logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
                print("✅ Logo chargé")
        except Exception as e:
            print(f"⚠️ Erreur chargement logo : {e}")

        # ═══════════════════════════════════════════════════════════
        # 6) GÉNÉRATION DU PDF
        # ═══════════════════════════════════════════════════════════
        print("📄 Étape 4: Génération du PDF...")
        
        nom_clean = (infos.get("nom") or "Analyse_Amour").replace(" ", "_")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nom_fichier = f"Profil_Amoureux_{nom_clean}_{timestamp}"

        output_dir = os.path.join(current_app.static_folder, "pdfs")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

        html_pdf = generer_html_final_amour_pdf(
            texte_modules_html=html_content,
            infos_personnelles=infos,
            logo_base64=logo_base64,
        )

        html_to_pdf(html_pdf, pdf_path)
        print(f"✅ PDF généré : {pdf_path}")

        # URL locale pour téléchargement (fallback)
        pdf_url_local = url_for(
            "profil_amoureux_module.telecharger_profil_amoureux_pdf",
            nom_fichier=nom_fichier,
            _external=True,
        )

        # ═══════════════════════════════════════════════════════════
        # 7) UPLOAD S3 (optionnel)
        # ═══════════════════════════════════════════════════════════
        warnings = []
        download_url = None
        
        try:
            print("☁️ Étape 5: Upload S3...")
            s3_info = upload_file_and_presign(
                pdf_path,
                key_prefix="profil_amoureux",
                content_type="application/pdf",
            )
            download_url = s3_info.get("url") or s3_info.get("presigned_url")
            if not download_url:
                raise KeyError(f"URL présignée manquante: {s3_info!r}")
            print(f"✅ Upload S3 → {download_url[:60]}...")
        except Exception as e:
            print(f"❌ Upload S3 KO ({e}) → fallback local")
            warnings.append("Upload S3 indisponible, lien local utilisé.")

        pdf_final_url = download_url or pdf_url_local

        # --- Mémo anti-reload pour Profil Amoureux ---
        try:
            session["last_fingerprint_profil_amoureux"] = current_fingerprint
            session["last_pdf_url_profil_amoureux"] = pdf_final_url
            session["lock_until_profil_amoureux"] = time.time() + 15 * 60  # 15 minutes
            logger.info("✅ [PA] Anti-reload: fingerprint + URL mémorisés.")
        except Exception as e:
            logger.warning("[PA] Anti-reload: impossible d'enregistrer l'état : %s", e)

        # ═══════════════════════════════════════════════════════════
        # 8) ENVOI EMAIL (optionnel)
        # ═══════════════════════════════════════════════════════════
        try:
            dest_email = (infos.get("email") or "").strip()
            if dest_email:
                print(f"✉️ Étape 6: Envoi email à {dest_email}...")
                prenom = (infos.get("nom") or "").split()[0] or "toi"
                sujet_email = "Ton Profil Amoureux est prêt 💗"
                
                body_txt = (
                    f"Bonjour {prenom},\n\n"
                    "Ton Profil Amoureux est prêt 💗 Merci pour ta confiance !\n\n"
                    "📄 Télécharge ton document ici :\n"
                    f"{pdf_final_url}\n\n"
                    "⚠️ Veille à bien télécharger ton document et à le sauvegarder sur ton appareil.\n"
                    "Si le lien ne s'ouvre pas, copie/colle l'URL dans ton navigateur.\n\n"
                    "🔮 Et si tu voulais aller encore plus loin ?\n"
                    "L'Analyse Karmique explore ce que le Profil Amoureux ne couvre pas : "
                    "tes schémas inconscients, tes nœuds karmiques, Chiron, Lilith... "
                    "Tout ce qui explique pourquoi certains patterns reviennent encore et encore en amour.\n"
                    "👉 https://lesfousdastro.fr/#analyse_karmique\n\n"
                    "À très vite sur les réseaux...ou dans les étoiles si on se croise jamais,\n"
                    "Cécile CL ✨ - Les Fous d'Astro 🪐</p>"
                )

                body_html = (
                    f"<p>Bonjour {prenom},</p>"
                    "<p>Ton <strong>Profil Amoureux</strong> est prêt 💗 Merci pour ta confiance !</p>"
                    "<div style='margin:30px 0; text-align:center;'>"
                    f"<a href='{pdf_final_url}' target='_blank' "
                    "style='display:inline-block;padding:14px 28px;background:#c2185b;color:white;"
                    "border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;'>"
                    "💗 Télécharger mon Profil Amoureux"
                    "</a>"
                    "<p style='margin-top:12px;font-size:13px;color:#777;'>"
                    "⚠️ Veille à bien télécharger ton document et à le sauvegarder sur ton appareil.<br>"
                    "Si le lien ne s'ouvre pas, copie/colle l'URL directement dans ton navigateur."
                    "</p>"
                    "</div>"
                    "<div style='margin:30px 0;padding:20px;background:#f9f6ff;border-radius:12px;'>"
                    "<p>🔮 <strong>Et si tu voulais aller encore plus loin ?</strong></p>"
                    "<p>L'Analyse Karmique explore ce que le Profil Amoureux ne couvre pas : "
                    "tes schémas inconscients, tes nœuds karmiques, Chiron, Lilith... "
                    "Tout ce qui explique pourquoi certains patterns reviennent encore et encore en amour.</p>"
                    "<p style='text-align:center;margin-top:15px;'>"
                    "<a href='https://lesfousdastro.fr/#analyse_karmique' target='_blank' "
                    "style='display:inline-block;padding:12px 24px;background:#6b3fa0;color:white;"
                    "border-radius:8px;text-decoration:none;font-weight:bold;'>"
                    "🔮 Découvrir l'Analyse Karmique"
                    "</a></p>"
                    "</div>"
                    "<p style='margin-top:40px;'>À très vite sur les réseaux...ou dans les étoiles si on se croise jamais,<br>"
                    "Cécile CL ✨ - Les Fous d'Astro 🪐</p>"
                )

                send_emails = os.getenv("SEND_EMAILS", "true").lower() in ("1", "true", "yes")
                if send_emails:
                    Thread(
                        target=envoyer_email_avec_analyse,
                        kwargs=dict(
                            destinataire=dest_email,
                            sujet=sujet_email,
                            contenu_txt=body_txt,
                            contenu_html=body_html,
                            pdf_path=None,  # On envoie le lien, pas la pièce jointe
                        ),
                        daemon=True,
                    ).start()
                    logger.info("✉️ Email Profil Amoureux en file d'envoi pour %s", dest_email)
            else:
                logger.info("✉️ Email non envoyé (adresse manquante)")
        except Exception as e:
            logger.warning("Email Profil Amoureux non envoyé : %s", e)
            warnings.append(f"Email non envoyé : {e}")

        # ═══════════════════════════════════════════════════════════
        # 9) RENDU HTML FINAL
        # ═══════════════════════════════════════════════════════════
        print("🎉 Analyse terminée avec succès !")
        print("=" * 60)
        
        return render_template(
            "profil_amoureux_result.html",
            nom=infos["nom"],
            html_content=html_content,
            nom_fichier=nom_fichier,
            pdf_url=pdf_final_url,
            infos=infos,
            logo_base64=logo_base64,
            warnings=warnings,
        )

    except Exception as e:
        print(f"❌ Erreur workflow Profil Amoureux : {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            "erreur.html",
            titre="Erreur génération Profil Amoureux",
            message=f"Erreur : {str(e)}",
            details="Veuillez réessayer ou contacter le support.",
        ), 500


@profil_amoureux_module.route("/telecharger/<nom_fichier>", methods=["GET"])
def telecharger_profil_amoureux_pdf(nom_fichier):
    """Téléchargement du PDF du Profil Amoureux (fallback local)"""
    from flask import send_from_directory, abort
    
    path = os.path.join(current_app.static_folder, "pdfs")
    fname = f"{nom_fichier}.pdf"
    full = os.path.join(path, fname)
    
    if not os.path.exists(full):
        abort(404)
    
    return send_from_directory(path, fname, as_attachment=True)