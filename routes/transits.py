import base64
import os
from datetime import datetime
from threading import Thread
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, render_template, request, session, url_for
from markupsafe import escape

from utils.calcul_theme import calcul_theme
from utils.email_sender import construire_email_analyse, envoyer_email_avec_analyse
from utils.genre import get_user_prefs
from utils.pdf_utils import html_to_pdf
from utils.s3_utils import upload_file_and_presign
from utils.transits.analyse_transits import formater_date_fr, generer_analyse_transits


transits_bp = Blueprint("transits", __name__, url_prefix="/transits")


def _env_on(name: str, default: str = "false") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _date_transit_depuis_session(infos: dict) -> datetime | None:
    mode = (infos.get("transit_date_mode") or "today").strip().lower()
    if mode != "custom":
        return None

    valeur = (infos.get("transit_date") or "").strip()
    try:
        return datetime.strptime(valeur, "%Y-%m-%d")
    except ValueError:
        abort(400, description="La date à explorer est invalide.")


def construire_html_pdf_transits(
    nom: str,
    date_affichee: str,
    contenu_html: str,
    logo_base64: str = "",
) -> str:
    logo_html = (
        f'<img src="data:image/webp;base64,{logo_base64}" alt="Les Fous d\'Astro">'
        if logo_base64 else ""
    )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Point Transits — {escape(nom)}</title>
    <style>
        body {{ font-family: Georgia, serif; color: #2c3e50; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .logo {{ text-align: center; margin-bottom: 18px; }}
        .logo img {{ max-width: 160px; max-height: 90px; }}
        h1 {{ color: #1f628e; text-align: center; margin-bottom: 8px; }}
        .period {{ color: #666; text-align: center; margin: 0 0 28px; }}
        h2 {{ color: #1f628e; border-bottom: 2px solid #1f628e; padding-bottom: 6px; margin-top: 28px; }}
        h3 {{ color: #144a6b; }}
        p {{ line-height: 1.65; text-align: justify; }}
        .transits-date {{ display: none; }}
        .transits-methodology {{
            background: #f7f3ef;
            border-left: 4px solid #b58b4c;
            border-radius: 8px;
            margin: 24px 0;
            padding: 14px 16px;
            font-size: 0.9em;
        }}
        .transits-methodology h3 {{ margin-top: 0; }}
        .transits-methodology p:last-child {{ margin-bottom: 0; }}
        .transit-card {{
            border: 1px solid #c9dbe5;
            border-left: 4px solid #1f628e;
            border-radius: 8px;
            padding: 14px 16px;
            margin: 14px 0;
            break-inside: avoid;
        }}
        .transit-card p {{ text-align: left; margin-bottom: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">{logo_html}</div>
        <h1>Point Transits — {escape(nom)}</h1>
        <p class="period">Période analysée : {escape(date_affichee)}</p>
        {contenu_html}
    </div>
</body>
</html>"""


@transits_bp.route("/complet")
def transits_complet():
    produits_payes = session.get("ordered_products") or []
    paiement = session.get("last_payment") or {}

    if (
        not session.get("paiement_valide")
        or "flash_transits" not in produits_payes
        or paiement.get("status") not in {"paid", "COMPLETED"}
    ):
        current_app.logger.warning("[TRANSITS] Accès refusé : paiement non validé")
        abort(403, description="Paiement requis pour générer le Point Transits.")

    infos = session.get("infos_utilisateur") or {}
    champs_obligatoires = (
        "nom", "date_naissance", "heure_naissance", "lieu_naissance", "lat", "lon"
    )
    if not all(infos.get(champ) for champ in champs_obligatoires):
        abort(400, description="Informations de naissance incomplètes.")

    date_transit = _date_transit_depuis_session(infos)

    try:
        theme = calcul_theme(
            nom=infos["nom"],
            date_naissance=infos["date_naissance"],
            heure_naissance=infos["heure_naissance"],
            lieu_naissance=infos["lieu_naissance"],
            lat=float(infos["lat"]),
            lon=float(infos["lon"]),
            tzid=infos.get("tzid"),
        )

        prefs = get_user_prefs(session, request)
        resultat = generer_analyse_transits(
            theme,
            date_transit=date_transit,
            genre=prefs.get("genre"),
        )
    except Exception:
        current_app.logger.exception("[TRANSITS] Échec de la génération")
        abort(500, description="Impossible de générer le Point Transits.")

    if resultat.erreur:
        current_app.logger.error("[TRANSITS] Génération incomplète : %s", resultat.erreur)
        return render_template(
            "transits_resultat.html",
            nom=theme.get("nom"),
            contenu_html=resultat.texte_html,
            pdf_url=None,
        ), 500

    date_effective = date_transit or datetime.now(ZoneInfo("Europe/Paris")).replace(
        tzinfo=None
    )
    date_affichee = formater_date_fr(date_effective)

    logo_base64 = ""
    logo_path = os.path.join(
        current_app.static_folder, "images", "logo_les_fous_dastro.webp"
    )
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as logo_file:
            logo_base64 = base64.b64encode(logo_file.read()).decode("utf-8")

    html_pdf = construire_html_pdf_transits(
        nom=theme.get("nom", "Analyse Anonyme"),
        date_affichee=date_affichee,
        contenu_html=resultat.texte_html,
        logo_base64=logo_base64,
    )

    nom_slug = "".join(
        caractere if caractere.isalnum() else "_"
        for caractere in theme.get("nom", "Anonyme")
    ).strip("_") or "Anonyme"
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nom_fichier = (
        f"Point_Transits_{nom_slug}_{date_effective:%Y-%m-%d}_{horodatage}.pdf"
    )
    dossier_pdf = os.path.join(current_app.static_folder, "pdfs")
    chemin_pdf = os.path.join(dossier_pdf, nom_fichier)

    if not html_to_pdf(html_pdf, chemin_pdf):
        abort(500, description="Impossible de créer le PDF du Point Transits.")

    pdf_url = url_for("static", filename=f"pdfs/{nom_fichier}", _external=True)
    try:
        s3_info = upload_file_and_presign(
            chemin_pdf,
            key_prefix="transits",
            content_type="application/pdf",
        )
        lien_s3 = s3_info.get("url") or s3_info.get("presigned_url")
        if lien_s3:
            pdf_url = lien_s3
    except Exception as erreur_s3:
        current_app.logger.warning(
            "[TRANSITS] PDF local disponible, mais envoi S3 impossible : %s",
            erreur_s3,
        )

    destinataire = (infos.get("email") or "").strip()
    if _env_on("SEND_EMAILS", "true") and destinataire:
        prenom = (theme.get("nom") or "").split()[0] or "toi"
        sujet, corps_texte, corps_html = construire_email_analyse(
            prenom, f"Point Transits du {date_affichee}", pdf_url
        )
        Thread(
            target=envoyer_email_avec_analyse,
            kwargs={
                "destinataire": destinataire,
                "sujet": sujet,
                "contenu_txt": corps_texte,
                "contenu_html": corps_html,
                "pdf_path": None,
            },
            daemon=True,
        ).start()

    current_app.logger.info(
        "[TRANSITS] Génération terminée | date=%s | provider=%s",
        date_affichee,
        paiement.get("provider"),
    )

    return render_template(
        "transits_resultat.html",
        nom=theme.get("nom"),
        contenu_html=resultat.texte_html,
        pdf_url=pdf_url,
    )
