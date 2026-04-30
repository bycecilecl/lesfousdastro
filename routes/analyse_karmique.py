from flask import (
    Blueprint,
    render_template,
    session,
    send_from_directory,
    abort,
    current_app,
    url_for,
)
from datetime import datetime
import os
import base64
import logging

from utils.pdf_utils import html_to_pdf
from utils.calcul_theme import calcul_theme
from utils.karmique.karmique_score import calculer_poids_karmique
from utils.karmique.analyse_karmique_engine import KarmicEngine
from utils.karmique.analyse_karmique_interpretation import interpret_all
from threading import Thread

from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
from utils.s3_utils import upload_file_and_presign
from utils.email_sender import envoyer_email_avec_analyse
from config.analysis_sandbox import is_analysis_sandbox

logger = logging.getLogger(__name__)

analyse_karmique_bp = Blueprint(
    "analyse_karmique",
    __name__,
    url_prefix="/analyse_karmique",
)


# =============================================================================
# HELPERS
# =============================================================================

def charger_logo_base64() -> str:
    logo_base64 = ""
    logo_path = os.path.join("static", "images", "logo_les_fous_dastro.webp")
    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        logger.warning("Erreur chargement logo : %s", e)
    return logo_base64


def generer_table_des_matieres(chapitres: list) -> str:
    """
    Génère le HTML de la table des matières.
    chapitres = liste de dicts {"titre": str, "intro": str}
    """
    if not chapitres:
        return ""

    lignes = []
    for chap in chapitres:
        titre = chap.get("titre", "")
        lignes.append(f"""
        <div class="toc-entry">
            <div class="toc-title">{titre}</div>
        </div>
        """)

    return f"""
<section class="toc-page">
    <h2 class="toc-heading">Sommaire</h2>
    <div class="toc-list">
        {"".join(lignes)}
    </div>
</section>
"""


def generer_analyse_karmique_html(infos: dict) -> tuple:
    """
    Génère le HTML karmique + la liste des titres pour la table des matières.
    Retourne (html_content, titres)
    """
    if infos.get("lat") and infos.get("lon"):
        theme = calcul_theme(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"],
            lat=float(infos["lat"]),
            lon=float(infos["lon"]),
            tzid=infos.get("tzid"),
        )
    else:
        theme = calcul_theme(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"]
        )

    score = calculer_poids_karmique(theme)

    engine = KarmicEngine(theme, score)
    blocks = engine.run()

    blocks = interpret_all(
        blocks=blocks,
        theme=theme,
        score=score,
        global_ctx=engine.global_ctx,
    )

    html_parts = []
    chapitres_toc = []
    chapter_index = 0

    for block in blocks:
        bid = block.get("id") or block.get("key") or ""
        if bid in ("header", "sensitive_points"):
            continue

        titre = (block.get("title") or "").strip()
        contenu = (block.get("llm_content") or block.get("content") or "").strip()

        logger.debug("Bloc karmique HTML | bid=%s | debut=%r", bid, contenu[:100])

        if not titre and not contenu:
            continue

        intro_toc = CHAPTER_INTROS.get(bid, "")

        if contenu:
            paragraphes = []
            for para in contenu.split("\n\n"):
                para = para.strip()
                if para:
                    paragraphes.append(para.replace("\n", " "))

            intro_html = ""
            if (
                paragraphes
                and len(paragraphes[0]) < 200
                and paragraphes[0].endswith(".")
                and len(paragraphes) > 1
            ):
                intro_html = f'<div class="chapter-intro">{paragraphes[0]}</div>'
                paragraphes = paragraphes[1:]

            contenu_html = intro_html + "\n".join(
                f"<p>{para}</p>" for para in paragraphes if para
            )
        else:
            contenu_html = "<p>Contenu en cours de génération.</p>"

        if titre:
            chapitres_toc.append({"titre": titre, "intro": intro_toc})

        first_class = " first" if chapter_index == 0 else ""
        chapter_index += 1

        html_parts.append(f"""
<section class="section chapter{first_class}" data-block-id="{bid}">
    <div class="chapter-header">
        <h2>{titre}</h2>
    </div>
    <div class="section-content">
        {contenu_html}
    </div>
</section>
""")

    return "\n".join(html_parts), chapitres_toc


def generer_html_final_karmique_pdf(
    texte_structure: str,
    table_des_matieres: str,
    infos_personnelles: dict,
    logo_base64: str = "",
) -> str:
    nom = infos_personnelles.get("nom", "Analyse Anonyme")
    date_naissance = infos_personnelles.get("date_naissance", "")
    heure_naissance = infos_personnelles.get("heure_naissance", "")
    lieu_naissance = infos_personnelles.get("lieu_naissance", "")

    logo_html = (
        f'<img src="data:image/webp;base64,{logo_base64}" alt="Logo Les Fous d\'Astro" class="logo">'
        if logo_base64 else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Analyse Karmique - {nom}</title>
    <style>

        /* ─── PAGE ─── */
        @page {{
            size: A4;
            margin: 20mm 18mm 22mm 18mm;

            @top-center {{
                content: "Les Fous d'Astro";
                font-size: 9px;
                color: #00a8a8;
                font-family: Georgia, serif;
            }}

            @bottom-left {{
                content: "© Droits réservés - Les Fous d'Astro";
                font-size: 8px;
                color: #999;
                font-family: Georgia, serif;
            }}

            @bottom-right {{
                content: "Page " counter(page) " / " counter(pages);
                font-size: 8px;
                color: #999;
                font-family: Georgia, serif;
            }}
        }}

        /* ─── BASE ─── */
        body {{
            font-family: Georgia, serif;
            font-size: 11px;
            line-height: 1.85;
            color: #222;
            background: #fff;
            margin: 0;
            padding: 0;
        }}

        /* ─── PAGE DE GARDE ─── */
        .cover-page {{
            page-break-after: always;
        }}

        .logo-header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #e0e0e0;
        }}

        .logo {{
            max-width: 160px;
            max-height: 90px;
            width: auto;
            height: auto;
            object-fit: contain;
        }}

        .header {{
            text-align: center;
            margin-bottom: 28px;
        }}

        .header h1 {{
            color: #00a8a8;
            font-size: 24px;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }}

        .personal-info {{
            font-size: 10px;
            color: #777;
            font-style: italic;
        }}

        /* ─── DISCLAIMER ─── */
        .disclaimer {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-left: 4px solid #00a8a8;
            padding: 14px 16px;
            margin: 0 0 0 0;
            border-radius: 4px;
            font-size: 9.5px;
            line-height: 1.6;
            color: #444;
            page-break-inside: avoid;
        }}

        .disclaimer p {{
            margin: 0 0 7px 0;
            text-align: left;
        }}

        .disclaimer p:last-child {{
            margin-bottom: 0;
        }}

        .disclaimer strong {{
            color: #00a8a8;
        }}

        /* ─── TABLE DES MATIÈRES ─── */
        .toc-page {{
            page-break-after: always;
            padding-top: 10px;
        }}

        .toc-heading {{
            color: #00a8a8;
            font-size: 18px;
            font-weight: bold;
            margin: 0 0 24px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #00a8a8;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}

        .toc-list {{
            margin-top: 10px;
        }}

        .toc-entry {{
            padding: 9px 0;
            border-bottom: 1px dotted #ddd;
        }}

        .toc-title {{
            font-size: 11px;
            color: #222;
            font-weight: bold;
        }}

        .toc-intro {{
            font-style: italic;
            font-size: 9.5px;
            color: #777;
            margin-top: 3px;
            padding-left: 4px;
            line-height: 1.5;
        }}

        /* ─── CHAPITRES ─── */
        section.chapter {{
            margin-top: 36px;
            margin-bottom: 0;
        }}

        section.chapter.first {{
            margin-top: 0;
        }}

        /* Bandeau titre chapitre */
        .chapter-header {{
            background: #00a8a8;
            margin: 0 0 16px 0;
            padding: 8px 14px;
            border-radius: 3px;
            page-break-after: avoid;
        }}

        .chapter-header .chapter-num {{
            display: none;
        }}

        .chapter-header h2 {{
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
            margin: 0;
            padding: 0;
            border: none;
            letter-spacing: 0.3px;
            page-break-after: avoid;
        }}

        /* Phrase d'intro/cadrage */
        .chapter-intro {{
            font-style: italic;
            color: #555;
            background: #f4fafa;
            border-left: 3px solid #00a8a8;
            padding: 9px 13px;
            margin: 0 0 18px 0;
            font-size: 10.5px;
            line-height: 1.7;
            page-break-inside: avoid;
        }}

        .section-content {{
            margin-top: 4px;
        }}

        section.chapter p {{
            margin: 0 0 13px 0;
            text-align: justify;
            orphans: 3;
            widows: 3;
        }}

        section.chapter p:last-child {{
            margin-bottom: 0;
        }}

        section.chapter h3 {{
            color: #00a8a8;
            font-size: 12px;
            margin: 22px 0 10px 0;
            padding: 6px 10px;
            background: #eefafa;
            border-left: 3px solid #00a8a8;
            page-break-after: avoid;
        }}

        /* ─── BLOCKQUOTE ─── */
        blockquote {{
            margin: 16px 0;
            padding: 11px 15px;
            border-left: 4px solid #00a8a8;
            background: #f4fafa;
            color: #444;
            font-style: italic;
            font-size: 10.5px;
        }}

        /* ─── FOOTER ─── */
        footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #eee;
            font-size: 9px;
            color: #999;
        }}

        footer p {{
            margin: 3px 0;
        }}

        a {{
            color: #00a8a8;
            text-decoration: none;
        }}

    </style>
</head>
<body>

    <!-- PAGE DE GARDE -->
    <div class="cover-page">

        <div class="logo-header">
            {logo_html}
        </div>

        <div class="header">
            <h1>Profil Karmique — {nom}</h1>
            <div class="personal-info">
                {date_naissance} — {heure_naissance} — {lieu_naissance}
            </div>
        </div>

        <div class="disclaimer">
            <p>
                <strong>⚠️ L'analyse karmique est une lecture symbolique automatisée.</strong><br>
                Elle propose une exploration des schémas profonds, des tensions intérieures, des répétitions de vie
                et des dynamiques inconscientes visibles dans le thème natal.
                Elle ne constitue ni un diagnostic, ni une vérité absolue sur la personne.
            </p>
            <p>
                <strong>❗️ Important :</strong> Une lecture karmique parle de potentiels, de mécanismes et de zones
                de travail intérieur. Elle ne dit pas qui une personne est de manière figée, et encore moins ce
                qu'elle est "condamnée" à vivre. Un même thème peut se manifester à des niveaux de conscience très
                différents selon l'histoire de vie, l'environnement, les choix et le travail personnel.
            </p>
            <p>
                <strong>🧠 À garder en tête :</strong> Le langage karmique peut parfois être intense, car il touche
                à des mécanismes anciens, sensibles ou répétitifs. Le but n'est pas de coller une étiquette, mais
                de mettre en lumière ce qui agit parfois en arrière-plan, afin de gagner en lucidité.
            </p>
            <p>
                <strong>♻️ Note technique :</strong> Cette analyse est générée automatiquement avec l'aide d'un
                système d'IA à partir de données astrologiques. Malgré le soin apporté à la structure et à
                l'interprétation, de petites répétitions, maladresses ou approximations peuvent subsister.
            </p>
            <p>
                <strong>💫 Pour aller plus loin :</strong> Une analyse manuelle permet d'aller beaucoup plus loin,
                avec prise en compte du vécu, du contexte personnel et d'une lecture réellement sur mesure.
                Pour une consultation personnalisée : <a href="https://bycecilecl.com">www.bycecilecl.com</a>
            </p>
        </div>

    </div>

    <!-- TABLE DES MATIÈRES -->
    {table_des_matieres}

    <!-- CHAPITRES -->
    <div class="content-wrapper">
        {texte_structure}
    </div>

    <footer>
        <p><strong>Les Fous d'Astro</strong> — Analyse générée automatiquement</p>
        <p>lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr</p>
        <p>IG : @lesfousdastro • @bycecilecl</p>
    </footer>

</body>
</html>"""
    return html

def generer_analyse_karmique_pdf_s3(infos, envoyer_email=False):
    """
    Génère l'analyse karmique en PDF + S3.
    Utilisable depuis les packs/background.
    """

    if is_analysis_sandbox():
        logger.info("🧪 SANDBOX Analyse karmique")

        return {
            "product_id": "analyse_karmique",
            "label": "Analyse karmique",
            "pdf_url": "https://sandbox.lesfousdastro.fr/karmique-test",
            "pdf_path": None,
            "status": "sandbox",
        }

    if not infos:
        raise ValueError("infos_utilisateur manquant pour Analyse Karmique")

    html_content, chapitres_toc = generer_analyse_karmique_html(infos)

    if not html_content or len(html_content.strip()) < 50:
        raise ValueError("Analyse karmique vide ou trop courte")

    logo_base64 = charger_logo_base64()
    toc_html = generer_table_des_matieres(chapitres_toc)

    nom = infos.get("nom", "Anonyme").replace(" ", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nom_fichier = f"Analyse_Karmique_{nom}_{timestamp}"

    output_dir = os.path.join(current_app.static_folder, "pdfs")
    os.makedirs(output_dir, exist_ok=True)

    pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

    html_pdf = generer_html_final_karmique_pdf(
        texte_structure=html_content,
        table_des_matieres=toc_html,
        infos_personnelles=infos,
        logo_base64=logo_base64,
    )

    ok_pdf = html_to_pdf(html_pdf, pdf_path)

    if not ok_pdf:
        raise RuntimeError("Échec génération PDF analyse karmique")

    pdf_final_url = None

    try:
        s3_info = upload_file_and_presign(
            pdf_path,
            key_prefix="analyse_karmique",
            content_type="application/pdf",
        )
        pdf_final_url = s3_info.get("url") or s3_info.get("presigned_url")

    except Exception as e:
        logger.warning("[KARMIQUE PACK] Upload S3 KO : %s", e)

    return {
        "product_id": "analyse_karmique",
        "label": "Analyse karmique",
        "pdf_url": pdf_final_url,
        "pdf_path": pdf_path,
        "status": "completed",
    }

# =============================================================================
# ROUTES
# =============================================================================

@analyse_karmique_bp.route("/complet", methods=["GET"])
def analyse_karmique_complete():
    infos = session.get("infos_utilisateur")

    if is_analysis_sandbox():
        current_app.logger.info(
            "[SANDBOX] Analyse karmique NON générée pour %s",
            (infos or {}).get("nom", "N/A")
        )
        return render_template(
            "debug_sandbox.html",
            titre="Analyse karmique – Analyse factice (SANDBOX)",
            infos=infos or {},
        )

    if not infos:
        return render_template(
            "erreur.html",
            titre="Données manquantes",
            message="Impossible de générer l'analyse karmique.",
            details="Les informations utilisateur sont absentes de la session."
        ), 400

    try:
        # 1) HTML chapitres + chapitres pour la TDM
        html_content, chapitres_toc = generer_analyse_karmique_html(infos)

        if not html_content or len(html_content.strip()) < 50:
            return render_template(
                "erreur.html",
                titre="Analyse vide",
                message="Le contenu de l'analyse karmique est insuffisant.",
                details="La génération a renvoyé un résultat vide ou trop court."
            ), 500

        # 2) Logo
        logo_base64 = charger_logo_base64()

        # 3) Table des matières
        toc_html = generer_table_des_matieres(chapitres_toc)

        # 4) Nom du fichier PDF
        nom = infos.get("nom", "Anonyme").replace(" ", "_")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nom_fichier = f"Analyse_Karmique_{nom}_{timestamp}"

        output_dir = os.path.join(current_app.static_folder, "pdfs")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

        # 5) HTML PDF final
        html_pdf = generer_html_final_karmique_pdf(
            texte_structure=html_content,
            table_des_matieres=toc_html,
            infos_personnelles=infos,
            logo_base64=logo_base64,
        )

        # 6) Génération PDF
        ok_pdf = html_to_pdf(html_pdf, pdf_path)

        pdf_url = None
        if ok_pdf:
            pdf_url = url_for(
                "analyse_karmique.telecharger_analyse_karmique",
                nom_fichier=nom_fichier,
                _external=True
            )

        # 7) Upload S3
        download_url = None
        if ok_pdf and pdf_path:
            try:
                s3_info = upload_file_and_presign(
                    pdf_path,
                    key_prefix="analyse_karmique",
                    content_type="application/pdf"
                )
                download_url = s3_info.get("url") or s3_info.get("presigned_url")
                if not download_url:
                    raise KeyError(f"URL présignée manquante: {s3_info!r}")
                logger.info("✅ Upload S3 OK → %s", download_url)
            except Exception as e:
                logger.warning("❌ Upload S3 KO (%s) → fallback local", e)

        pdf_final_url = download_url or pdf_url

        # 8) Envoi email
        try:
            dest_email = (infos.get("email") or "").strip()
            if dest_email and pdf_final_url:
                prenom = (infos.get("nom") or "").split()[0] or "toi"
                sujet_email = "Ton Analyse Karmique est prête ✨"

                body_txt = (
                    f"Bonjour {prenom},\n\n"
                    "Ton Analyse Karmique est prête 🔮 Merci pour ta confiance !\n\n"
                    "📄 Télécharge ton document ici :\n"
                    f"{pdf_final_url}\n\n"
                    "⚠️ Veille à bien télécharger ton document et à le sauvegarder sur ton appareil.\n"
                    "Si le lien ne s'ouvre pas, copie/colle l'URL dans ton navigateur.\n\n"
                    "Ce que tu tiens entre les mains, c'est pas rien.\n"
                    "Les nœuds lunaires, Chiron, Lilith, les planètes rétrogrades...\n"
                    "C'est tout ce qui explique pourquoi tu te retrouves toujours dans les mêmes situations\n"
                    "— et surtout, comment t'en sortir.\n\n"
                    "Prends le temps de le lire, de le relire. Certaines choses ne résonnent pas\n"
                    "tout de suite, et puis un jour ça fait tilt.\n\n"
                    "À très vite sur les réseaux...ou dans les étoiles si on se croise jamais,\n"
                    "Cécile CL ✨"
                )

                body_html = (
                    f"<p>Bonjour {prenom},</p>"
                    "<p>Ton <strong>Analyse Karmique</strong> est prête 🔮 Merci pour ta confiance !</p>"
                    "<div style='margin:30px 0; text-align:center;'>"
                    f"<a href='{pdf_final_url}' target='_blank' "
                    "style='display:inline-block;padding:14px 28px;background:#6b3fa0;color:white;"
                    "border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;'>"
                    "🔮 Télécharger mon Analyse Karmique"
                    "</a>"
                    "<p style='margin-top:12px;font-size:13px;color:#777;'>"
                    "⚠️ Veille à bien télécharger ton document et à le sauvegarder sur ton appareil.<br>"
                    "Si le lien ne s'ouvre pas, copie/colle l'URL directement dans ton navigateur."
                    "</p>"
                    "</div>"
                    "<div style='margin:30px 0;padding:20px;background:#f9f6ff;border-radius:12px;'>"
                    "<p style='color:#3C3489;'>Ce que tu tiens entre les mains, c'est pas rien.</p>"
                    "<p style='color:#534AB7;line-height:1.7;'>"
                    "Les nœuds lunaires, Chiron, Lilith, les planètes rétrogrades...<br>"
                    "C'est tout ce qui explique pourquoi tu te retrouves toujours dans les mêmes situations "
                    "— et surtout, comment t'en sortir.<br><br>"
                    "Prends le temps de le lire, de le relire. Certaines choses ne résonnent pas "
                    "tout de suite, et puis un jour ça fait tilt."
                    "</p>"
                    "</div>"
                    "<p style='margin-top:40px;'>À très vite sur les réseaux...ou dans les étoiles si on se croise jamais,<br>"
                    "Cécile CL ✨</p>"
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
                        daemon=True
                    ).start()
                    logger.info("✉️ Email karmique en file d'envoi pour %s", dest_email)
                else:
                    logger.info("✉️ Email non envoyé (SEND_EMAILS=false)")
            else:
                logger.info("✉️ Email non envoyé (email ou lien PDF manquant)")
        except Exception as e:
            logger.warning("Email karmique non envoyé : %s", e)

        # 9) Rendu web
        return render_template(
            "analyse_karmique_resultat.html",
            nom=infos.get("nom", ""),
            html_content=html_content,
            nom_fichier=nom_fichier,
            infos=infos,
            logo_base64=logo_base64,
            pdf_url=pdf_final_url,
        )

    except Exception as e:
        logger.exception("Erreur génération analyse karmique")
        return render_template(
            "erreur.html",
            titre="Erreur génération analyse karmique",
            message=f"Erreur : {str(e)}",
            details="Veuillez réessayer."
        ), 500


@analyse_karmique_bp.route("/telecharger_analyse_karmique/<nom_fichier>", methods=["GET"])
def telecharger_analyse_karmique(nom_fichier):
    path = os.path.join(current_app.static_folder, "pdfs")
    fname = f"{nom_fichier}.pdf"

    if not os.path.exists(os.path.join(path, fname)):
        abort(404)

    return send_from_directory(path, fname, as_attachment=True)

