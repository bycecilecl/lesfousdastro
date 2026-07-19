# routes/amour_blocs.py

from flask import Blueprint, render_template, session, current_app, url_for
import os
from datetime import datetime
import inspect

from utils.calcul_theme import calcul_theme as _calcul_theme
from utils.pdf_utils import html_to_pdf
from utils.genre import get_user_prefs
from utils.s3_utils import upload_file_and_presign
from utils.email_sender import envoyer_email_avec_analyse
from threading import Thread
import logging

# Tes modules amour
from module.amour_blocs.maniere_aimer import generer_bloc_maniere_aimer
from module.amour_blocs.partenaire_ideal import generer_bloc_partenaire_ideal
from module.amour_blocs.couple_ideal import generer_bloc_couple_ideal
from module.amour_blocs.intimite_sexualite import generer_bloc_intimite_sexualite

logger = logging.getLogger(__name__)

amour_bp = Blueprint(
    "amour_blocs",
    __name__,
    url_prefix="/amour"
)

# ---------- Wrapper calcul_theme identique ----------
def calcul_theme_safe(**kwargs):
    """
    Appelle utils.calcul_theme en ne passant QUE les paramètres qu'il accepte.
    Copié depuis point_astral_blocs pour éviter les TypeError.
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
        out.append(f"<p>{b.replace('\n', ' ')}</p>")
    return "\n".join(out)


def generer_html_final_amour_pdf_only(
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
        <h1>💗 Analyse Amoureuse - {nom}</h1>
        <div class="personal-info">
            <p>{date_naissance} — {heure_naissance} — {lieu_naissance}</p>
        </div>
    </div>

    <div class="disclaimer">
        <p><strong>⚠️ À propos de cette analyse amoureuse :</strong><br>
        Ce document est une lecture automatisée de ton thème natal centrée sur ta manière d’aimer,
        ce qui t’attire, ta dynamique de couple et ton rapport à l’intimité. 
        Il ne prédit pas si tu vas « finir en couple » ou non, ni avec qui.</p>

        <p>Il parle de <u>tendances intérieures</u>, de scénarios fréquents, de blessures et de forces.
        La façon dont tu les vis dépend de ton niveau de conscience, de ton histoire, de tes choix.
        Tu peux t’y reconnaître totalement, partiellement, ou pas encore — certains thèmes se révèlent avec le temps.</p>

        <p>Cette analyse n’est pas un verdict sur ta vie affective, ni un avis médical ou psychologique.
        C’est un miroir symbolique pour t’aider à comprendre ce qui se joue en toi dans le lien amoureux,
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
        <p><strong>Les Fous d'Astro</strong> – Analyse Amoureuse générée automatiquement</p>
        <p>lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr</p>
        <p>IG : @lesfousdastro • @bycecilecl</p>
    </footer>
</body>
</html>"""
    return html


@amour_bp.route("/complet", methods=["GET"])
def amour_complet():
    """Workflow complet de l'Analyse Amoureuse (4 modules + PDF + bouton download)"""

    infos = session.get("infos_utilisateur")
    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire.", 400

    print("\n" + "="*60)
    print("💗 DÉBUT ANALYSE AMOUREUSE")
    print(f"Nom: {infos.get('nom', 'Anonyme')}")
    print("="*60)

    try:
        # 1) Calcul thème (même logique que Point Astral)
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
        print("✅ Thème calculé pour module Amour")

        # 2) Polarité / genre
        prefs = get_user_prefs(session, None)
        genre_form = (infos.get("gender") or "").lower()
        if genre_form == "female":
            polarite = "Femme"
        elif genre_form == "male":
            polarite = "Homme"
        else:
            polarite = "Homme"
        print(f"👤 Polarité utilisée pour l'Amour : {polarite}")

        # 3) Génération des 4 modules
        m1 = generer_bloc_maniere_aimer(data_theme, call_llm=True, polarite=polarite)
        m2 = generer_bloc_partenaire_ideal(data_theme, call_llm=True, polarite=polarite)
        m3 = generer_bloc_couple_ideal(data_theme, call_llm=True, polarite=polarite)
        m4 = generer_bloc_intimite_sexualite(data_theme, call_llm=True, polarite=polarite)

        # 4) Mise en forme HTML “corps” (pour web + PDF)
        sections_html = []

        if m1:
            sections_html.append(
                f"""
                <section class="section">
                    <h2>Module 1 · Ma manière d'aimer</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m1)}
                    </div>
                </section>
                """
            )
        if m2:
            sections_html.append(
                f"""
                <section class="section">
                    <h2>Module 2 · Partenaire idéal : ce qui t'attire</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m2)}
                    </div>
                </section>
                """
            )
        if m3:
            sections_html.append(
                f"""
                <section class="section">
                    <h2>Module 3 · Couple idéal & dynamique relationnelle</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m3)}
                    </div>
                </section>
                """
            )
        if m4:
            sections_html.append(
                f"""
                <section class="section">
                    <h2>Module 4 · Intimité & sexualité</h2>
                    <div class="section-content">
                        {_texte_en_html_paragraphes(m4)}
                    </div>
                </section>
                """
            )

        html_content = "\n".join(sections_html).strip()
        if not html_content:
            return render_template(
                "erreur.html",
                titre="Analyse Amoureuse",
                message="Aucun contenu n'a pu être généré.",
                details="Les quatre modules ont renvoyé un texte vide.",
            ), 500

        # 5) Logo (comme pour Point Astral)
        logo_base64 = ""
        logo_path = os.path.join(current_app.static_folder, "images", "logo_les_fous_dastro.webp")
        try:
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img_file:
                    import base64
                    logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as e:
            print(f"⚠️ Erreur logo Analyse Amour : {e}")

        # 6) Génération PDF
        nom = infos["nom"].replace(" ", "_")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nom_fichier = f"Analyse_Amoureuse_{nom}_{timestamp}"

        output_dir = os.path.join(current_app.static_folder, "pdfs")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

        html_pdf = generer_html_final_amour_pdf_only(
            texte_modules_html=html_content,
            infos_personnelles=infos,
            logo_base64=logo_base64,
        )

        html_to_pdf(html_pdf, pdf_path)
        print(f"✅ PDF Amour généré : {pdf_path}")

        # URL locale pour téléchargement (blueprint)
        pdf_url_local = url_for(
            "amour_blocs.telecharger_amour_pdf",
            nom_fichier=nom_fichier,
            _external=True,
        )

        # 7) Upload S3 (facultatif, comme Point Astral)
        warnings = []
        try:
            s3_info = upload_file_and_presign(
                pdf_path,
                key_prefix="analyse_amour",
                content_type="application/pdf",
            )
            download_url = s3_info.get("url") or s3_info.get("presigned_url")
            if not download_url:
                raise KeyError(f"URL présignée manquante: {s3_info!r}")
            print(f"✅ Upload S3 Analyse Amour → {download_url}")
        except Exception as e:
            print(f"❌ Upload S3 KO pour Analyse Amour ({e}) → fallback local")
            download_url = None
            warnings.append("Upload S3 indisponible, lien local utilisé.")

        pdf_final_url = download_url or pdf_url_local

        # 8) Email (optionnel, comme pour Point Astral)
        try:
            dest_email = (infos.get("email") or "").strip()
            if dest_email:
                prenom = (infos.get("nom") or "").split()[0] or "toi"
                sujet_email = "Ton Analyse Amoureuse est prête"
                body_txt = (
                    f"Bonjour {prenom},\n\n"
                    "Merci pour ta commande ! Ton Analyse Amoureuse est prête 💗\n\n"
                    "Télécharge ton PDF ici :\n"
                    f"{pdf_final_url}\n\n"
                    "Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.\n\n"
                    "À bientôt,\n"
                    "Les Fous d’Astro – By Cécile CL"
                )
                body_html = (
                    f"<p>Bonjour {prenom},</p>"
                    "<p>Merci pour ta commande ! Ton <strong>Analyse Amoureuse</strong> est prête 💗</p>"
                    f"<p>📄 <a href=\"{pdf_final_url}\" target=\"_blank\">Télécharge ton PDF ici</a></p>"
                    "<p>Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.</p>"
                    "<p>À bientôt,<br>Les Fous d’Astro – By Cécile CL</p>"
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
                            pdf_path=None,
                        ),
                        daemon=True,
                    ).start()
                    logger.info("✉️  Email Analyse Amour en file d'envoi pour %s", dest_email)
            else:
                logger.info("✉️  Email Analyse Amour non envoyé (adresse manquante)")
        except Exception as e:
            logger.warning("Email Analyse Amour non envoyé : %s", e)
            warnings.append(f"Email non envoyé : {e}")

        # 9) Rendu HTML (comme Flash Astral)
        return render_template(
            "amour_resultat.html",
            nom=infos["nom"],
            html_content=html_content,  # corps des 4 modules
            nom_fichier=nom_fichier,
            pdf_url=pdf_final_url,
            infos=infos,
            logo_base64=logo_base64,
            warnings=warnings,
        )

    except Exception as e:
        print(f"❌ Erreur workflow Analyse Amour : {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            "erreur.html",
            titre="Erreur génération Analyse Amoureuse",
            message=f"Erreur : {str(e)}",
            details="Veuillez réessayer.",
        ), 500


@amour_bp.route("/telecharger_amour/<nom_fichier>", methods=["GET"])
def telecharger_amour_pdf(nom_fichier):
    """Téléchargement du PDF de l'Analyse Amoureuse (local)"""
    path = os.path.join(current_app.static_folder, "pdfs")
    fname = f"{nom_fichier}.pdf"
    full = os.path.join(path, fname)
    if not os.path.exists(full):
        from flask import abort
        abort(404)
    from flask import send_from_directory
    return send_from_directory(path, fname, as_attachment=True)