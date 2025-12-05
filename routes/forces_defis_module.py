# routes/forces_defis_module.py
from __future__ import annotations

from flask import Blueprint, render_template, session, request, redirect, url_for, current_app
import inspect
import re
from markupsafe import Markup
from datetime import datetime
from threading import Thread
import os, base64

from utils.pdf_utils import html_to_pdf
from utils.s3_utils import upload_file_and_presign   # si S3 dispo, sinon laisse try/except
from utils.email_sender import envoyer_email_avec_analyse
from utils.forces_defis import generer_forces_defis, extraire_forces_defis_par_maisons
from utils.convert_markdown_light import md_light_to_html
#from routes.forces_defis_module import forces_defis_module_bp
from config.analysis_sandbox import is_analysis_sandbox



# ─────────────────────────────────────────────────────────────────────────────
# 1) Imports analytiques robustes (nouvelle API sinon fallback ancienne)
# ─────────────────────────────────────────────────────────────────────────────
try:
    # Nouvelle API recommandée
    from utils.forces_defis_analyse import analyse_forces_defis
except Exception:
    # Ancienne API : on renomme pour garder le même appel plus bas
    from utils.forces_defis import generer_forces_defis as analyse_forces_defis  # type: ignore

# Calcul du thème (avec wrapper "safe" pour accepter les signatures variables)
from utils.calcul_theme import calcul_theme as _calcul_theme

# Optionnels (non bloquants)
try:
    from utils.utils_points_forts import extraire_points_forts
    from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs
except Exception:
    extraire_points_forts = None
    organiser_points_forts = None
    formater_axes_majeurs = None

try:
    from utils.genre import get_user_prefs
except Exception:
    def get_user_prefs(session, request):  # fallback neutre
        return {"tonalite": "tu", "genre": "neutre"}


# ─────────────────────────────────────────────────────────────────────────────
# 2) Blueprint
# ─────────────────────────────────────────────────────────────────────────────
forces_defis_module_bp = Blueprint(
    "forces_defis_module",
    __name__,
    url_prefix="/forces_defis"
)


# ─────────────────────────────────────────────────────────────────────────────
# 3) Helpers
# ─────────────────────────────────────────────────────────────────────────────
def calcul_theme_safe(**kwargs):
    """
    Passe à utils.calcul_theme UNIQUEMENT les kwargs qu'il accepte,
    pour éviter les TypeError si la signature diffère (local/prod).
    """
    sig = inspect.signature(_calcul_theme)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return _calcul_theme(**accepted)


def _to_float_or_none(x):
    try:
        return float(x) if x not in (None, "",) else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 4) Route principale (GET) appelée après paiement
# ─────────────────────────────────────────────────────────────────────────────

@forces_defis_module_bp.route("/complet", methods=["GET"])
def forces_defis_complet():


    # 🔐 Raccourci SANDBOX : on ne génère pas la vraie analyse
    if is_analysis_sandbox():
        infos = session.get("infos_utilisateur") or {}
        current_app.logger.info(
            "[SANDBOX] Forces & Défis NON généré pour %s",
            infos.get("nom", "N/A")
        )
        return render_template(
            "debug_sandbox.html",
            titre="Mes Potentiels & Défis – Analyse factice (SANDBOX)",
            infos=infos,
        )

    # 🔍 Debug utile (laisse-le pour l’instant)
    current_app.logger.info(f"[FD DEBUG] paiement_valide={session.get('paiement_valide')}")
    current_app.logger.info(f"[FD DEBUG] last_payment={session.get('last_payment')}")
    current_app.logger.info(f"[FD DEBUG] ordered_products={session.get('ordered_products')}")

    # ========== VALIDATION FLEXIBLE ==========

    # 1) On exige seulement qu’un paiement ait eu lieu
    if not session.get("paiement_valide"):
        return render_template("erreur.html",
                               titre="Mes Forces & Défis",
                               message="Aucun paiement confirmé."), 400

    # 2) Vérification que Forces & Défis fait partie des produits commandés
    ordered = session.get("ordered_products") or []
    if "forces_defis" not in ordered:
        current_app.logger.warning("[FD] Produit forces_defis non présent dans ordered_products")
        # → mais on CONTINUE quand même pour production (tu veux tester)
        # return render_template("erreur.html",
        #                        titre="Mes Forces & Défis",
        #                        message="Aucun paiement Forces & Défis confirmé."), 400
        pass


    
# @forces_defis_module_bp.route("/complet", methods=["GET"])
# def forces_defis_complet():
#     """
#     Lit les infos 'infos_utilisateur' en session (posées avant paiement),
#     calcule le thème, génère l'analyse Forces & Défis (≈ 1–2 pages) et affiche.
#     """
#     # ✅ exiger un paiement valide pour ce produit
#     last = session.get("last_payment") or {}
#     if not session.get("paiement_valide") or last.get("product_key") != "forces_defis":
#         return render_template("erreur.html",
#                                message="Aucun paiement Forces & Potentiels confirmé."), 400
    
    # ========== Données de naissance ==========
    infos = session.get("infos_utilisateur")
    if not infos:
        current_app.logger.warning("[FORCES_DEFIS] infos_utilisateur absentes → retour index")
        return redirect(url_for("main.index"))

    # 1) Calcul du thème (identique à Flash ; lat/lon/tzid si dispo)
    lat = _to_float_or_none(infos.get("lat"))
    lon = _to_float_or_none(infos.get("lon"))

    try:
        theme = calcul_theme_safe(
            nom=infos.get("nom"),
            date_naissance=infos.get("date_naissance"),
            heure_naissance=infos.get("heure_naissance"),
            lieu_naissance=infos.get("lieu_naissance"),
            lat=lat,
            lon=lon,
            tzid=infos.get("tzid")
        )
    except Exception as e:
        current_app.logger.error("[FORCES_DEFIS] calcul_theme a échoué : %s", e)
        return render_template(
            "erreur.html",
            titre="Erreur calcul du thème",
            message="Impossible de calculer le thème natal.",
            details=str(e)
        ), 500

    # 2) Axes majeurs (optionnel, non bloquant)
    try:
        if extraire_points_forts and organiser_points_forts and formater_axes_majeurs:
            raw_pf = theme.get("points_forts") or extraire_points_forts(theme)
            if isinstance(raw_pf, str):
                points_forts_list = [l.strip() for l in raw_pf.splitlines() if l.strip()]
            elif isinstance(raw_pf, (list, tuple)):
                points_forts_list = list(raw_pf)
            else:
                points_forts_list = []

            axes = organiser_points_forts(points_forts_list) if points_forts_list else {}
            axes_majeurs_str = formater_axes_majeurs(axes) if axes else ""
            theme["axes_majeurs_str"] = axes_majeurs_str
    except Exception as e:
        current_app.logger.warning("[FORCES_DEFIS] Axes majeurs ignorés : %s", e)

    # 3) Préférences d’énonciation (ton/genre)
    prefs = get_user_prefs(session, request) or {"tonalite": "tu", "genre": "neutre"}
    g_form = (infos.get("gender") or "").strip().lower()
    if g_form in ("female", "femme"):
        prefs["genre"] = "femme"
    elif g_form in ("male", "homme"):
        prefs["genre"] = "homme"

     
    # 4) Analyse (fonction résolue dynamiquement)
    try:
        # Signature moderne (préférée) : (theme, meta=...)
        resultat = analyse_forces_defis(theme, meta=prefs)  # type: ignore[arg-type]
    except TypeError:
        # Fallback ancien : (theme) seul
        resultat = analyse_forces_defis(theme)  # type: ignore[call-arg]

    # Extraire le texte (peut être dict ou str selon la fonction)
    if isinstance(resultat, dict):
        texte = resultat.get("texte") or resultat.get("analyse") or str(resultat)
    else:
        texte = str(resultat)

    # 5) Formatage lisible pour le template (Markdown léger → sections HTML)
    contenu_html = md_light_to_html(texte)

    print("\n" + "="*60)
    print("HTML GÉNÉRÉ PAR PARSER (300 premiers caractères):")
    print("="*60)
    print(str(contenu_html)[:300])
    print("="*60 + "\n")

    # --- Debug + filet de sécurité ---
    try:
        raw_len = len(texte or "")
        html_len = len(str(contenu_html or ""))
        current_app.logger.info("[FD] LLM len=%s | HTML len=%s", raw_len, html_len)
        current_app.logger.info("[FD] LLM head=%r", (texte or "")[:200])
        current_app.logger.info("[FD] HTML head=%r", str(contenu_html or "")[:200])
    except Exception:
        pass

    # Si le HTML est vide → on affiche au moins le markdown brut
    if not contenu_html or not str(contenu_html).strip():
        from markupsafe import Markup, escape
        contenu_html = Markup(
            "<div class='intro'><p><em>(Formatage minimal – fallback)</em></p>"
            "<pre style='white-space:pre-wrap'>"
            + escape(texte or "(aucun texte)") +
            "</pre></div>"
        )

    # ===== PDF + EMAIL + TRACE (même logique que Flash) =====
    # A) HTML dédié PDF (sobre/imprimable)
    def _html_pdf_forces_defis(texte_sections_html: str, infos: dict, logo_base64: str = "") -> str:
        nom = infos.get("nom", "Analyse Anonyme")
        date_naissance = infos.get("date_naissance", "")
        heure_naissance = infos.get("heure_naissance", "")
        lieu_naissance = infos.get("lieu_naissance", "")
        logo_html = f'<img src="data:image/webp;base64,{logo_base64}" alt="Logo" style="max-width:150px;max-height:80px;margin-bottom:8px" />' if logo_base64 else ""
        return f"""<!DOCTYPE html>
    <html lang="fr"><head><meta charset="utf-8">
    <title>Mes Potentiels & Défis – {nom}</title>
    <style>
    body{{font-family:Georgia,serif;color:#2c3e50;margin:0;padding:40px;}}
    .container{{max-width:800px;margin:0 auto;}}
    h1{{text-align:center;margin:0 0 6px;font-size:24px}}
    .info{{text-align:center;color:#666;font-size:14px;margin:0 0 16px}}
    h2{{color:#34495e;border-bottom:2px solid #3498db;padding-bottom:5px;margin-top:28px}}
    p{{text-align:justify;line-height:1.6}}
    .disclaimer{{background:#f8f9fa;border:1px solid #dee2e6;padding:16px;border-radius:8px;font-size:13px;color:#555;margin-top:22px}}
    </style></head>
    <body><div class="container">
    <div style="text-align:center">{logo_html}</div>
    <h1>Mes Potentiels & Défis</h1>
    <p class="info">{date_naissance} — {heure_naissance} — {lieu_naissance}</p>
    {texte_sections_html}
    <div class="disclaimer">
        <strong>Note :</strong> Analyse générée automatiquement depuis ton thème natal, focalisée sur tes appuis (FORCES) et tes axes de croissance (DÉFIS). 
        Elle n’est pas une consultation individuelle.
    </div>
    </div></body></html>"""

    # B) Logo optionnel
    logo_base64 = ""
    try:
        logo_path = os.path.join(current_app.static_folder, "images", "logo_les_fous_dastro.webp")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                logo_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

    # C) Construire HTML PDF
    html_pdf = _html_pdf_forces_defis(str(contenu_html), infos, logo_base64)

    # D) Écrire le PDF local
    nom_slug = (infos.get("nom","Anonyme").replace(" ", "_") or "Anonyme")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fname = f"Forces_Defis_{nom_slug}_{timestamp}"
    outdir = os.path.join(current_app.static_folder, "pdfs")
    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, f"{fname}.pdf")
    html_to_pdf(html_pdf, pdf_path)

    # E) URL finale (S3 si dispo, sinon locale)
    pdf_final_url = None
    try:
        s3_info = upload_file_and_presign(pdf_path, key_prefix="forces_defis", content_type="application/pdf")
        pdf_final_url = s3_info.get("url") or s3_info.get("presigned_url")
    except Exception as e:
        current_app.logger.info("[FD] Pas d'upload S3 (%s) → lien local.", e)

    if not pdf_final_url:
        rel = os.path.relpath(pdf_path, current_app.static_folder).replace("\\", "/")
        pdf_final_url = url_for("static", filename=rel, _external=True)

    # F) Email non bloquant (si email fourni)
    try:
        dest = (infos.get("email") or "").strip()
        if dest:
            prenom = (infos.get("nom","").split()[0] or "toi")
            sujet = "Ton module Mes Potentiels & Défis"
            body_txt = (
                f"Bonjour {prenom},\n\n"
                "Ton analyse « Mes Potentiels & Défis » est prête ✨\n\n"
                f"PDF : {pdf_final_url}\n\n"
                "Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.\n\n"
                "À bientôt,\nLes Fous d’Astro – By Cécile CL"
            )
            body_html = (
                f"<p>Bonjour {prenom},</p>"
                "<p>Ton analyse <strong>Mes Potentiels & Défis</strong> est prête ✨</p>"
                f"<p>📄 <a href=\"{pdf_final_url}\" target=\"_blank\">Télécharger le PDF</a></p>"
                "<p>Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.</p>"
                "<p>À bientôt,<br>Les Fous d’Astro – By Cécile CL</p>"
            )
            if os.getenv("SEND_EMAILS","true").lower() in ("1","true","yes"):
                Thread(target=envoyer_email_avec_analyse, kwargs=dict(
                    destinataire=dest, sujet=sujet, contenu_txt=body_txt, contenu_html=body_html, pdf_path=None
                ), daemon=True).start()
    except Exception as e:
        current_app.logger.warning("[FD] Email non envoyé : %s", e)

    # G) (optionnel) trace locale
    try:
        from utils.audit import log_event
        log_event("forces_defis_generated", {
            "nom": infos.get("nom"), "email": infos.get("email"),
            "pdf_url": pdf_final_url, "ts": timestamp
        })
    except Exception:
        pass

    # H) Rendu web (avec bouton PDF)
    nom_aff = infos.get("nom","Anonyme")
    return render_template(
        "forces_defis_resultat.html",
        nom=nom_aff,
        contenu_html=contenu_html,   # <- au lieu de texte_html
        pdf_url=pdf_final_url
    )



def format_forces_defis_html(texte_brut: str) -> str:
    """
    Convertit un texte (Markdown léger) en HTML structuré.
    Attend les titres '## FORCES' et '## DÉFIS' (ou fallback si absents).
    - Intro : paragraphes
    - Sections FORCES/DÉFIS : <h2> + <ul><li>...
    - Conserve la conclusion en paragraphes si présente après DÉFIS
    """
    if not texte_brut:
        return "<p>(texte vide)</p>"

    t = texte_brut.strip().replace("\r\n", "\n").replace("\r", "\n")

    # Normalisation minimale : titres en majuscules sans accents divers
    # Supporte aussi **FORCES** / **DÉFIS** en fallback
    t = re.sub(r'^\s*\*\*FORCES\*\*\s*$', '## FORCES', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\*\*D[ÉE]FIS\*\*\s*$', '## DÉFIS', t, flags=re.MULTILINE)

    # Split en trois parties : intro / forces / defis / (reste=conclusion)
    parts = re.split(r'(?m)^##\s*(FORCES|D[ÉE]FIS)\s*$', t)
    # re.split retourne: [intro, "FORCES", bloc_forces, "DÉFIS", bloc_defis, reste?]
    intro_html, forces_html, defis_html, conclusion_html = "", "", "", ""

    if len(parts) >= 3 and parts[1].upper().startswith("FORCES"):
        intro_raw = parts[0].strip()
        forces_raw = parts[2].strip()
        if len(parts) >= 5 and parts[3].upper().startswith("D"):
            defis_raw = parts[4].strip()
            conclusion_raw = parts[5].strip() if len(parts) >= 6 else ""
        else:
            defis_raw = ""
            conclusion_raw = ""
    else:
        # Pas de titres détectés → tout en intro
        intro_raw = t
        forces_raw = ""
        defis_raw = ""
        conclusion_raw = ""

    def _paragraphize(block: str) -> str:
        paras = ["<p>" + re.sub(r"\n+", " ", p).strip() + "</p>" 
         for p in re.split(r"\n\s*\n", block) if p.strip()]
        return "\n".join(paras) if paras else ""

    def _bullets(block: str) -> str:
        # Convertit lines commençant par -, •, — en <li>
        lis = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[-•—]\s+', line):
                lis.append(f"<li>{line[2:].strip()}</li>")
            else:
                # ligne orpheline → paragraphe dans le <li>
                lis.append(f"<li>{line}</li>")
        return f"<ul>\n{''.join(lis)}\n</ul>" if lis else ""

    if intro_raw:
        intro_html = f'<div class="intro">{_paragraphize(intro_raw)}</div>'

    if forces_raw:
        forces_html = f'''
        <div class="section forces">
            <h2 class="section-title">💪 Forces & Potentiels</h2>
            {_bullets(forces_raw)}
        </div>'''.strip()

    if defis_raw:
        defis_html = f'''
        <div class="section defis">
            <h2 class="section-title">⚠️ Défis & Points d'attention</h2>
            {_bullets(defis_raw)}
        </div>'''.strip()

    if conclusion_raw:
        conclusion_html = f'<div class="conclusion">{_paragraphize(conclusion_raw)}</div>'

    html = "\n".join([intro_html, forces_html, defis_html, conclusion_html])
    return Markup(html)  # pour éviter l’auto-échappement Jinja