# routes/point_astral_blocs.py - VERSION HARMONISÉE
from flask import Blueprint, render_template, session, send_from_directory, abort, request, url_for,current_app
import inspect
from datetime import datetime
import re
import os, time, json, hashlib, logging
import base64
import uuid
from utils.calcul_theme import calcul_theme as _calcul_theme
from orchestration.point_astral_blocs import generer_point_astral_blocs
from utils.rendu_point_astral import transformer_en_sections
from utils.rag_utils_optimized import generer_corpus_rag_optimise
from utils.genre import get_user_prefs
from utils.selection_donnees import construire_selection_point_astral
from utils.pdf_utils import html_to_pdf
from utils.gestion_utilisateur import enregistrer_utilisateur_et_envoyer
from utils.s3_utils import upload_file_and_presign
from email.mime.text import MIMEText
from threading import Thread
from utils.email_sender import envoyer_email_avec_analyse
from config.analysis_sandbox import is_analysis_sandbox


logger = logging.getLogger(__name__)

# from config.analysis_sandbox import is_analysis_sandbox

# @flash_astral_bp.route("/complet")
# def flash_astral_complet():
#     if is_analysis_sandbox():
#         infos = session.get("infos_utilisateur") or {}
#         current_app.logger.info(
#             f"[SANDBOX] Flash Astral non généré pour {infos.get('nom', 'N/A')}"
#         )
#         return render_template(
#             "debug_sandbox.html",
#             titre="Flash Astral – Analyse factice (SANDBOX)",
#             infos=infos,
#         )


def _fingerprint_infos(infos: dict) -> str:
    """Empreinte stable des infos utilisateur pour idempotence."""
    try:
        payload = json.dumps(infos or {}, sort_keys=True, ensure_ascii=False)
    except Exception:
        payload = str(infos or {})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ---------- Wrapper sûr pour calcul_theme ----------
def calcul_theme_safe(**kwargs):
    """
    Appelle utils.calcul_theme en ne passant QUE les paramètres qu'il accepte.
    Évite les TypeError 'unexpected keyword' et 'missing required positional'.
    """
    sig = inspect.signature(_calcul_theme)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    # Valeur par défaut si 'nom' est requis
    for name, param in sig.parameters.items():
        if param.default is inspect._empty and name not in accepted:
            if name == "nom":
                accepted[name] = "Eric (test)"
    return _calcul_theme(**accepted)



# --- Helpers d'extraction robustes depuis data_theme (PAS de recalcul !) ---

def _dig(d, *path):
    """Accède à une valeur potentiellement imbriquée: _dig(d, 'angles','ASC')"""
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k in cur:
            cur = cur[k]
        else:
            return None
    return cur

def _first_key(d, *candidates):
    """Renvoie la 1re valeur trouvée dans d parmi une liste de clés simples."""
    if not isinstance(d, dict):
        return None
    for k in candidates:
        if k in d:
            return d[k]
    return None

def _as_houses_dict(val):
    """
    Normalise maisons → dict {1:deg, …, 12:deg}
    """
    def _pluck_lon(v):
        if isinstance(v, (int, float, str)):
            try:
                return float(v)
            except Exception:
                return None
        if isinstance(v, dict):
            # Ton format spécifique : cherche 'degre' en premier
            for k in ("degre", "deg", "lon", "longitude", "degree"):
                if k in v:
                    try:
                        return float(v[k])
                    except Exception:
                        pass
        return None

    if isinstance(val, dict):
        out = {}
        for n in range(1, 13):
            got = None
            # Tes clés : 'Maison 1', 'Maison 2', etc.
            for key in (f"Maison {n}", n, str(n), f"H{n}", f"house{n}"):
                if key in val:
                    got = val[key]
                    break
                    
            if got is not None:
                deg = _pluck_lon(got)
                if deg is not None:
                    out[n] = deg
        return out if out else {}
        
    return {}


# ---------- Blueprint ----------
point_astral_blocs_bp = Blueprint(
    "point_astral_blocs",
    __name__,
    url_prefix="/point_astral_blocs"
)


@point_astral_blocs_bp.route("/__ping", methods=["GET"])
def ping_blocs():
    return "ok blocs"


# ---------- Route principale HARMONISÉE ----------
@point_astral_blocs_bp.route("/complet", methods=["GET"])
def point_astral_blocs_complet():
    """Workflow complet harmonisé : mêmes données que l'ancien système + approche par blocs"""

    # 🔐 Raccourci SANDBOX : on ne génère pas le vrai Flash Astral
    if is_analysis_sandbox():
        infos = session.get("infos_utilisateur") or {}
        current_app.logger.info(
            "[SANDBOX] Flash Astral (Point Astral blocs) NON généré pour %s",
            infos.get("nom", "N/A")
        )
        return render_template(
            "debug_sandbox.html",
            titre="Flash Astral – Analyse factice (SANDBOX)",
            infos=infos,
        )

    # === DEBUG DÉTAILLÉ SESSION ===
    logger.info("=== DEBUG SESSION COMPLET START ===")
    logger.info("Session keys: %s", list(session.keys()))
    logger.info("Full session: %s", dict(session))
    
    # Récupération des infos depuis la session
    infos = session.get("infos_utilisateur")
    logger.info("infos_utilisateur raw: %s", infos)
    logger.info("infos_utilisateur type: %s", type(infos))

    if not infos:
        logger.error("❌ AUCUNE infos_utilisateur en session")
        logger.info("Session disponible: %s", dict(session))
        
        # Chercher des variations possibles
        possible_keys = [k for k in session.keys() if 'info' in k.lower() or 'user' in k.lower()]
        logger.info("Clés possibles trouvées: %s", possible_keys)
        
        return f"❌ Données manquantes. Session keys: {list(session.keys())}. Possible keys: {possible_keys}. Veuillez recommencer depuis le formulaire."
    
    logger.info("✅ infos_utilisateur trouvé: %s", infos)

        # === Pare-chocs données critiques (avant tout calcul/génération) ===
    order_id = (session.get("last_payment") or {}).get("order_id")
    logger.info("last_payment: %s", session.get("last_payment"))
    logger.info("order_id: %s", order_id)

    email = (infos.get("email") or "").strip()
    nom = infos.get("nom")
    lieu = infos.get("lieu_naissance")
    lat  = infos.get("lat")
    lon  = infos.get("lon")
    tzid = infos.get("tzid")

    logger.info("=== DONNÉES EXTRAITES ===")
    logger.info("email: %r", email)
    logger.info("nom: %r", nom)
    logger.info("lieu: %r", lieu)
    logger.info("lat: %r", lat)
    logger.info("lon: %r", lon)
    logger.info("tzid: %r", tzid)
    logger.info("date_naissance: %r", infos.get("date_naissance"))
    logger.info("heure_naissance: %r", infos.get("heure_naissance"))

    # Log d’état complet pour corréler avec /payments/capture-order
    logger.info(
        "[GEN] START order=%s email=%s nom=%s lieu=%r lat=%r lon=%r tzid=%r",
        order_id, email, nom, lieu, lat, lon, tzid
    )

    # Champs obligatoires côté astro : lat/lon/tzid (+ date/heure)
    required_fields = {
        "lat": lat, 
        "lon": lon, 
        "tzid": tzid,
        "date_naissance": infos.get("date_naissance"),
        "heure_naissance": infos.get("heure_naissance"),
    }

    logger.info("=== VÉRIFICATION CHAMPS REQUIS ===")
    for field, value in required_fields.items():
        logger.info("%s: %r (bool: %s)", field, value, bool(value))
    
    missing = [k for k, v in required_fields.items() if not v]

    if missing:
        logger.warning(
            "[GEN] ABORT — données manquantes=%s — order=%s — infos=%r",
            missing, order_id, infos
        )
        
        # Message d'erreur plus détaillé
        debug_info = {
            'missing_fields': missing,
            'all_infos_keys': list(infos.keys()) if infos else [],
            'session_keys': list(session.keys()),
            'order_id': order_id,
            'infos_content': infos
        }
        
        return render_template(
            "erreur.html",
            titre="Données insuffisantes - DEBUG MODE",
            message="Impossible de générer l'analyse.",
            details=f"DEBUG INFO: {debug_info}"
        ), 400
    
    # # Champs obligatoires côté astro : lat/lon/tzid (+ date/heure)
    # missing = [k for k, v in {
    #     "lat": lat, "lon": lon, "tzid": tzid,
    #     "date_naissance": infos.get("date_naissance"),
    #     "heure_naissance": infos.get("heure_naissance"),
    # }.items() if not v]

    # if missing:
    #     logger.warning(
    #         "[GEN] ABORT — données manquantes=%s — order=%s — infos=%r",
    #         missing, order_id, infos
    #     )
    #     return render_template(
    #         "erreur.html",
    #         titre="Données insuffisantes",
    #         message="Impossible de générer l'analyse.",
    #         details=f"Champs manquants : {', '.join(missing)}. "
    #                 "Ré-sélectionne le lieu via l’autocomplétion et vérifie date/heure."
    #     ), 400

    # Protection “appel direct sans paiement” (sauf QA)
    if not session.get("last_payment") and request.args.get("qa") != "1":
        logger.warning("[GEN] ABORT — aucun paiement en session — email=%s nom=%s", email, nom)
        logger.info("Session pour debug paiement: %s", dict(session))
        return render_template(
            "erreur.html",
            titre="Paiement requis",
            message="Session de paiement introuvable ou expirée.",
            details="Merci de relancer la commande."
        ), 403
    
    logger.info("=== DEBUG SESSION COMPLET END ===")
    
    # Empreinte (fingerprint) unique des infos utilisateur
    current_fingerprint = _fingerprint_infos(infos)
    
    # --- Anti-reload minimal (TTL 15 min) --------------------------------
    ANTI_RELOAD = False
    #ANTI_RELOAD = os.getenv("ANTI_RELOAD", "true").lower() in ("1", "true", "yes")
    # if ANTI_RELOAD:
    #     last_fingerprint = session.get("last_fingerprint")
    #     lock_until = float(session.get("lock_until", 0))

    #     if time.time() < lock_until and current_fingerprint == last_fingerprint:
    #         last_url = session.get("last_pdf_url")
    #         if last_url:
    #             return render_template(
    #                 "paiement_effectue.html", 
    #                 pdf_url=last_url, 
    #                 already=True
    #             )
    #         return "Cette action a déjà été effectuée. Réessaie dans quelques minutes.", 429
# ---------------------------------------------------------------------
    warnings_list = []
    contexte = {}
    
    task_id = session.get('current_task_id')
    print(f"Début analyse Flash Astral avec progression - Task ID: {task_id}")
    print(f"🔍 DEBUG SESSION COMPLÈTE: {infos}")
    print(f"🔍 DEBUG CLÉS SESSION: {list(infos.keys()) if infos else 'None'}")
    print(f"\n{'='*60}")
    print(f"🎬 Point_Astral_Bloc DÉBUT ANALYSE FLASH ASTRAL BLOCS (harmonisé)")
    print(f"👤Point_Astral_Bloc Nom: {infos.get('nom', 'Anonyme')}")
    print(f"{'='*60}")
    
    try:
        # 1) Enregistrement utilisateur
        try:
            enregistrer_utilisateur_et_envoyer(infos)
            print("✅ Point_Astral_Bloc Utilisateur enregistré")
        except Exception as e:
            print(f"⚠️ Point_Astral_Bloc Erreur enregistrement : {e}")
        
        # 2) Calcul du thème IDENTIQUE à l'ancien système
        print("🔧 Point_Astral_Bloc Étape 1: Calcul du thème...")
        if infos.get('lat') and infos.get('lon'):
            print(f"🎯 Coordonnées précises: {infos['lat']}, {infos['lon']}")
            data_theme = calcul_theme_safe(
                nom=infos["nom"],
                date_naissance=infos["date_naissance"],
                heure_naissance=infos["heure_naissance"],
                lieu_naissance=infos["lieu_naissance"],
                lat=float(infos["lat"]),
                lon=float(infos["lon"]),
                tzid=infos.get("tzid")
            )
        else:
            print("🎯 Point_Astral_Bloc Fallback géocodage")
            data_theme = calcul_theme_safe(
                nom=infos["nom"],
                date_naissance=infos["date_naissance"],
                heure_naissance=infos["heure_naissance"],
                lieu_naissance=infos["lieu_naissance"]
            )
        print("✅ Point_Astral_Bloc Thème calculé")

        # === Extraction depuis data_theme (sans recalcul) ===
        # Planètes : plusieurs alias possibles
        planetes_deg = (
            _first_key(data_theme, "planetes_deg", "planets_deg", "positions_deg", "positions_planetes", "planetes", "planets")
            or _dig(data_theme, "positions", "planetes") 
            or _dig(data_theme, "astro", "planetes")
            or {}
        )

        # Maisons / cuspides : on teste dicts simples puis chemins imbriqués fréquents
        raw_maisons = (
            _first_key(data_theme, "maisons_deg", "houses_deg", "maisons", "houses", "cusps", "cuspides")
            or _dig(data_theme, "houses", "cusps")
            or _dig(data_theme, "astro", "houses")
            or _dig(data_theme, "astro", "cuspides")
            or {}
        )
        maisons_deg = _as_houses_dict(raw_maisons)

        # ASC / MC : souvent à plat, parfois dans 'angles' ou 'ascmc'
        asc = (
            _first_key(data_theme, "asc", "asc_deg", "Ascendant", "ascendant", "ASC")
            or _dig(data_theme, "angles", "ASC")
            or _dig(data_theme, "ascmc", "ASC")
            or _dig(data_theme, "angles", "asc")
        )
        mc = (
            _first_key(data_theme, "mc", "mc_deg", "Midheaven", "milieu_ciel", "milieu_du_ciel", "MC")
            or _dig(data_theme, "angles", "MC")
            or _dig(data_theme, "ascmc", "MC")
            or _dig(data_theme, "angles", "midheaven")
        )

        # Cast en float si ce sont des strings
        def safe_float(val):
            if val is None:
                return None
            if isinstance(val, dict) and 'degre' in val:
                try:
                    return float(val['degre'])
                except:
                    return None
            try:
                return float(val)
            except:
                return None

        asc = safe_float(asc)
        mc = safe_float(mc)

        if mc is None and maisons_deg and 10 in maisons_deg:
            mc = maisons_deg[10]
            print("🔄 MC déduit de la maison 10:", mc)

        print("🔧 CHART input → planets:", list(planetes_deg.keys())[:8] if isinstance(planetes_deg, dict) else type(planetes_deg))
        print("🔧 CHART input → houses :", (list(maisons_deg.items())[:3] if isinstance(maisons_deg, dict) else type(maisons_deg)))
        print("🔧 CHART input → ASC/MC :", asc, mc)
        # DEBUG pour voir les vraies données
        print("🔍 DEBUG raw_maisons:", raw_maisons)
        print("🔍 DEBUG data_theme keys avec 'house':", [k for k in data_theme.keys() if 'house' in k.lower()])
        print("🔍 DEBUG data_theme keys avec 'maison':", [k for k in data_theme.keys() if 'maison' in k.lower()])



        # 🔎 DEBUG DE BASE : vois vraiment les clés/tailles
        print("🧭 data_theme keys:", list(data_theme.keys())[:40])
        for k in ("planetes_deg","planetes","positions_deg","positions_planetes","planets_deg","planets",
                "maisons_deg","maisons","houses_deg","houses","cuspides","cusps","houses_cusps",
                "asc","ASC","ascendant","ascendant_deg","mc","MC","midheaven","mc_deg"):
            v = data_theme.get(k)
            if isinstance(v, dict):
                print(f"   - {k}: dict({len(v)}) sample=", list(v.items())[:3])
            elif isinstance(v, (list,tuple)):
                print(f"   - {k}: list({len(v)}) sample=", v[:3])
            else:
                print(f"   - {k}: {v!r}")



        print("🟪 Point_Astral_Bloc interceptions (brut):", data_theme.get("interceptions"))
        
        # 3) Construction des placements IDENTIQUE à l'ancien système
        placements_str = construire_selection_point_astral(data_theme, max_orbe=5.0)
        print("✅ Section OCC ?" , "### Placements occidentaux" in placements_str)
        print("✅ Section Aspects?", "### Aspects (≤ 5° d'orbe)" in placements_str)

        # -- DEBUG ciblé occidental/axes/védique (temporaire) --
        if "### Planètes rétrogrades" in placements_str:
            bloc = placements_str.split("### Planètes rétrogrades", 1)[1].split("###", 1)[0]
            print("♻️ Point_Astral_Bloc Rétrogrades transmis:\n", "\n".join(bloc.strip().splitlines()[:8]))
        else:
            print("♻️ Point_Astral_Bloc Aucun rétrograde détecté.")
        if "### Axes interceptés" in placements_str:
            bloc = placements_str.split("### Axes interceptés", 1)[1].split("###", 1)[0]
            print("🧭 Point_Astral_Bloc Axes interceptés transmis:\n", "\n".join(bloc.strip().splitlines()[:12]))
        else:
            print("🧭 Point_Astral_Bloc Aucun axe intercepté détecté.")
        if "### Spécificités védiques utiles" in placements_str:
            bloc = placements_str.split("### Spécificités védiques utiles", 1)[1].split("###", 1)[0]
            print("🔱 Point_Astral_Bloc Védique transmis:\n", "\n".join(bloc.strip().splitlines()[:12]))

        print(f"\n🔍 Point_Astral_Bloc DEBUG PLACEMENTS_STR ({len(placements_str)} caractères):")
        print("="*80)
        print(placements_str)
        print("="*80)
        print("🔍 Point_Astral_Bloc FIN DEBUG PLACEMENTS_STR\n")
        print(f"✅ Point_Astral_Bloc Placements construits: {len(placements_str)} caractères")
        debug_url = (
            f"/placements?nom={infos.get('nom','')}"
            f"&date={infos.get('date_naissance','')}"
            f"&heure={infos.get('heure_naissance','')}"
            f"&lieu={infos.get('lieu_naissance','')}"
            f"&lat={infos.get('lat','')}"
            f"&lon={infos.get('lon','')}"
            f"&tzid={infos.get('tzid','')}"
        )
        print(f"URL POUR PLACEMENTS USER : {debug_url}")

        # --- DEBUG VÉDIQUE : données brutes + extrait transmis ---
        asc_sid = (data_theme.get("ascendant_sidereal") or {})
        print("🟣 Point_Astral_Bloc VED Asc sidéral  :", asc_sid)
        maitre_v = (data_theme.get("maitre_ascendant_vedique") or {})
        print("🟣 Point_Astral_Bloc VED Maître Asc   :", maitre_v)
        plan_ved = (data_theme.get("planetes_vediques") or {})
        print("🟣 Point_Astral_Bloc VED planètes dispos :", list(plan_ved.keys())[:8], "…")
        titre_ved = "### Spécificités védiques utiles"
        bloc_ved = []
        if titre_ved in placements_str:
            lignes = placements_str.splitlines()
            i = lignes.index(titre_ved)
            bloc_ved = lignes[i : i + 15]
            print("🟣 VED Bloc transmis au LLM :")
            for l in bloc_ved:
                print("   ", l)
        else:
            print("🟣 Point_Astral_Bloc VED Bloc non trouvé dans placements_str")
        SIGN_LORD = {
            "Bélier":"Mars","Taureau":"Vénus","Gémeaux":"Mercure","Cancer":"Lune",
            "Lion":"Soleil","Vierge":"Mercure","Balance":"Vénus","Scorpion":"Mars",
            "Sagittaire":"Jupiter","Capricorne":"Saturne","Verseau":"Saturne","Poissons":"Jupiter",
        }
        asc_signe = asc_sid.get("signe")
        maitre_attendu = SIGN_LORD.get(asc_signe) if asc_signe else None
        ligne_maitre = next((l for l in bloc_ved if "Maître d'Ascendant" in l), "")
        print("🟣 Point_Astral_Bloc VED Maître attendu :", maitre_attendu, "| Ligne placements_str :", ligne_maitre)
        if maitre_attendu and ligne_maitre and (maitre_attendu not in ligne_maitre):
            print("⚠️ VED MISMATCH : la ligne ne correspond pas au maître sidéral attendu.")


        # 4) --- RAG non bloquant ---
        try:
            rag_snippets = generer_corpus_rag_optimise(data_theme) or ""
            if len(rag_snippets) > 8000:
                rag_snippets = rag_snippets[:8000]
            print(f"✅ Point_Astral_Bloc RAG chargé: {len(rag_snippets)} caractères")
        except Exception as e:
            print(f"⚠️ RAG indisponible: {e}")
            rag_snippets = ""
            warnings_list.append("RAG indisponible (désactivé ou en erreur).")
    

        # 5) Axes majeurs IDENTIQUE à l'ancien système
        try:
            from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs
            from utils.utils_points_forts import extraire_points_forts
            raw_pf = data_theme.get("points_forts") or extraire_points_forts(data_theme)
            if isinstance(raw_pf, str):
                points_forts_list = [l.strip() for l in raw_pf.splitlines() if l.strip()]
            else:
                points_forts_list = list(raw_pf) if raw_pf else []
            axes = organiser_points_forts(points_forts_list)
            axes_majeurs_str = formater_axes_majeurs(axes)
            data_theme["axes_majeurs_str"] = axes_majeurs_str
            print(f"✅ Point_Astral_Bloc Axes majeurs construits: {len(axes_majeurs_str)} caractères")
        except Exception as e:
            print(f"⚠️ Erreur axes majeurs : {e}")
            axes_majeurs_str = ""

        # Vérification des données RENFORCÉE
        if not placements_str or len(placements_str) < 40:
            return render_template(
                "erreur.html",
                titre="Données insuffisantes",
                message="Impossible de générer l'analyse - placements_str incomplet",
                details=f"placements_str: {len(placements_str)} chars, rag: {len(rag_snippets or '') } chars"
            )

        # ----- PREFERENCES CENTRALISÉES -----
        prefs = get_user_prefs(session, request)
        genre_form = infos.get("gender", "").lower()
        print(f"🔍 Genre depuis infos: '{genre_form}'")
        if genre_form == "female":
            prefs["genre"] = "femme"
        elif genre_form == "male":
            prefs["genre"] = "homme"
        else:
            prefs["genre"] = "homme"  # fallback
        print(f"🔧 Genre final forcé: '{prefs['genre']}'")

        # 6) Contexte ENRICHI pour les 5 blocs
        contexte = {
            "placements_str": placements_str,
            "axes_majeurs_str": axes_majeurs_str,
            "data_theme": data_theme,
            "rag_snippets": rag_snippets,
            "corpus_rag": rag_snippets,       # compat si ailleurs tu lis "corpus_rag"
            "placements": placements_str,
            "points_forts": axes_majeurs_str or "",
            "aspects": data_theme.get("aspects") or [],
            "amas_axes": {},
            "tonalite": prefs["tonalite"],
            "genre": prefs["genre"],
        }

        print("🔵 Point_Astral_Bloc ORCH contexte keys:", list(contexte.keys()))
        print(f"🔵 Point_Astral_Bloc ORCH prefs -> tonalite={contexte['tonalite']} | genre={contexte['genre']}")
        print("✨ Point_Astral_Bloc Lancement des 5 blocs LLM…")

        # 7) GÉNÉRATION par 5 blocs AMÉLIORÉE
        texte_brut = generer_point_astral_blocs(contexte)
        print(f"🧪 DEBUG texte_brut: {len(texte_brut)} chars | head={texte_brut[:180]!r}")
        print(f"✅ Point_Astral_Bloc Texte généré: {len(texte_brut)} caractères")

        def _extract_section(full_text: str, title: str) -> str:
            pattern = re.compile(rf"^##\s*{re.escape(title)}\s*\n", re.MULTILINE)
            m = pattern.search(full_text or "")
            if not m: return ""
            start = m.end()
            next_h = re.search(r"^##\s+", (full_text or "")[start:], re.MULTILINE)
            end = start + next_h.start() if next_h else len(full_text)
            return (full_text[m.start():end]).strip()

        bloc_1_txt = _extract_section(texte_brut, "Personnalité & Identité")
        bloc_2_txt = _extract_section(texte_brut, "Lune & Monde intérieur")
        bloc_3_txt = _extract_section(texte_brut, "Les Axes Majeurs")
        bloc_5_txt = _extract_section(texte_brut, "Synthèse")

        blocs_dict = {
            "bloc_1": bloc_1_txt or "",
            "bloc_2": bloc_2_txt or "",
            "bloc_3": bloc_3_txt or "",
            "bloc_5": bloc_5_txt or "",
        }

        meta = { "tonalite": contexte.get("tonalite", "tu"), "genre": contexte.get("genre", "femme") }
        data_theme_aff = {
            "placements_str": contexte.get("placements_str", ""),
            "points_forts":   (contexte.get("points_forts") or contexte.get("axes_majeurs_str") or ""),
            "rag_snippets":   contexte.get("rag_snippets", ""),
        }

        # 8) Post-traitement
        H_TITLES = [
            "Personnalité & Identité",
            "Lune & Monde intérieur",
            "Les Axes Majeurs",
            "Synthèse",
        ]
        def _normalize_h2_titles(text: str) -> str:
            for title in H_TITLES:
                text = re.sub(rf"(?m)^(?!\#\#\s*){re.escape(title)}\s*$", f"## {title}", text)
            text = re.sub(r"(?m)^\#(?!\#)\s+", "## ", text)
            return text
        texte_affine = _normalize_h2_titles(texte_brut)

        try:
            texte_structure = transformer_en_sections(texte_affine)
            print(f"✅ Sections HTML créées: {len(texte_structure)} caractères")
        except Exception as e:
            print(f"⚠️ transformer_en_sections a levé une exception: {e}")
            texte_structure = ""
        if not texte_structure or len(texte_structure.strip()) < 50:
            print("⚠️ transformeur a retourné vide → fallback minimal.")
            texte_structure = transformer_en_sections_fallback(texte_affine)
            print(f"✅ Fallback sections HTML: {len(texte_structure)} caractères")

        # 9) Logo IDENTIQUE à l'ancien système
        logo_base64 = ""
        logo_path = "static/images/logo_les_fous_dastro.webp"
        try:
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img_file:
                    logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement du logo : {e}")

        # 10) HTML final IDENTIQUE à l'ancien système
        html_content = texte_structure  # <= uniquement les sections (sans header/disclaimer)
        print(f"✅ Point_Astral_Bloc Sections prêtes pour web: {len(html_content)} caractères")

        
        
        # 11) PDF + Email (version unifiée avec CARTE + DISCLAIMERS)
        nom_fichier = None
        carte_astrale_url = None
        carte_astrale_data_uri = None

        nom = infos["nom"].replace(' ', '_')
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nom_fichier = f"Point_Astral_{nom}_{timestamp}"

        output_dir = os.path.join(current_app.static_folder, "pdfs")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")

        # --- C) Construire le HTML PDF (avec carte + disclaimers) ---
        html_pdf = generer_html_final_harmonise_pdf_only(
            texte_structure=html_content,
            infos_personnelles=infos,
            logo_base64=logo_base64,
            #carte_astrale_data_uri=carte_astrale_data_uri,
        )

        html_to_pdf(html_pdf, pdf_path)
        print(f"✅ PDF généré: {pdf_path}")

        # URL locale (fallback)
        pdf_url = url_for(
            "point_astral_blocs.telecharger_point_astral",
            nom_fichier=nom_fichier,
            _external=True
        )
        # --- Upload S3 (non bloquant pour la suite) ---
        try:
            s3_info = upload_file_and_presign(
                pdf_path,
                key_prefix="point_astral",
                content_type="application/pdf"
            )
            download_url = s3_info.get("url") or s3_info.get("presigned_url")
            if not download_url:
                raise KeyError(f"URL présignée manquante: {s3_info!r}")
            print(f"✅ Upload S3 OK → {download_url}")
        except Exception as e:
            print(f"❌ Upload S3 KO ({e}) → fallback local")
            download_url = None

        # --- D) Choisir l’URL finale à renvoyer ---
        pdf_final_url = download_url or pdf_url  # S3 si dispo, sinon local
        if not download_url:
            warnings_list.append("Upload S3 indisponible, lien local utilisé.")

        # --- Mémo anti-reload : on garde fingerprint, URL et verrou ---
        try:
            session["last_fingerprint"] = current_fingerprint
            session["last_pdf_url"] = pdf_final_url
            session["lock_until"] = time.time() + 15 * 60  # 15 minutes
            logger.info("✅ Anti-reload: fingerprint + URL mémorisés, verrou activé.")
        except Exception as e:
            logger.warning("Anti-reload: impossible d'enregistrer l'état : %s", e)

        # --- E) Envoi d’email NON bloquant ---
        try:
            dest_email = (infos.get("email") or "").strip()
            if dest_email:
                prenom = (infos.get("nom") or "").split()[0] or "toi"
                sujet_email = "Ton Flash Astral est prêt ✨"
                body_txt = (
                    f"Bonjour {prenom},\n\n"
                    "Merci pour ta commande ! Ton Flash Astral est prêt ✨\n\n"
                    "Télécharge ton PDF ici :\n"
                    f"{pdf_final_url}\n\n"
                    "Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.\n\n"
                    "🎁 Bonus : je t’offre 10% de réduction sur l’analyse complète de ton thème natal.\n"
                    "Découvre les prestations ici : https://bycecilecl.com/categorie-produit/services/\n"
                    "Et contacte-moi pour bénéficier de ton offre : contact@lesfousdastro.fr\n\n"
                    "À bientôt,\n"
                    "Les Fous d’Astro – By Cécile CL"
                )
                body_html = (
                    f"<p>Bonjour {prenom},</p>"
                    "<p>Merci pour ta commande ! Ton Flash Astral est prêt ✨</p>"
                    f"<p>📄 <a href=\"{pdf_final_url}\" target=\"_blank\">Télécharge ton PDF ici</a></p>"
                    "<p>Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.</p>"
                    "<p>🎁 <strong>Bonus :</strong> je t’offre <strong>10% de réduction</strong> sur "
                    "l’analyse complète de ton thème natal.</p>"
                    "<p>➡️ Découvre les prestations ici : "
                    "<a href=\"https://bycecilecl.com/categorie-produit/services/\" target=\"_blank\">"
                    "https://bycecilecl.com/categorie-produit/services/</a></p>"
                    "<p>Et contacte-moi pour bénéficier de ton offre : "
                    "<a href=\"mailto:contact@lesfousdastro.fr\">contact@lesfousdastro.fr</a></p>"
                    "<p>À bientôt,<br>Les Fous d’Astro – By Cécile CL</p>"
                )
                
                # Flag ON/OFF côté env (.env: SEND_EMAILS=true|false)
                send_emails = os.getenv("SEND_EMAILS", "true").lower() in ("1", "true", "yes")

                if send_emails:
                    # Envoi en thread pour ne pas bloquer la réponse HTTP
                    Thread(
                        target=envoyer_email_avec_analyse,
                        kwargs=dict(
                            destinataire=dest_email,
                            sujet=sujet_email,
                            contenu_txt=body_txt,
                            contenu_html=body_html,
                            pdf_path=None,  # on envoie l'URL, pas la PJ
                        ),
                        daemon=True
                    ).start()
                    logger.info("✉️  Email en file d'envoi pour %s", dest_email)
                else:
                    logger.info("✉️  Email non envoyé (SEND_EMAILS=false)")
            else:
                logger.info("✉️  Email non envoyé (adresse manquante)")
        except Exception as e:
            logger.warning("Email non envoyé (erreur thread/SMTP) : %s", e)
            warnings_list.append(f"Email non envoyé : {e}")

        # --- F) Rendu HTML (pas de JSON ici, on reste sur le template) ---
        return render_template(
            'point_astral_resultat.html',
            nom=infos["nom"],
            html_content=html_content,
            nom_fichier=nom_fichier,
            infos=infos,
            logo_base64=logo_base64,
            carte_astrale_url=carte_astrale_url,
            pdf_url=pdf_final_url,         # <-- pour bouton "Télécharger"
            warnings=warnings_list         # <-- optionnel à afficher dans le template
        )
        
    # ⬇️⬇️⬇️  CE BLOC MANQUAIT : il ferme le try PRINCIPAL  ⬇️⬇️⬇️
    except Exception as e:
        print(f"❌ Erreur workflow blocs harmonisé : {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            'erreur.html',
            titre="Erreur génération blocs",
            message=f"Erreur : {str(e)}",
            details="Veuillez réessayer."
        ), 500
    
@point_astral_blocs_bp.route("/apercu_point_astral/<nom_fichier>", methods=["GET"])
def apercu_point_astral(nom_fichier):
    path = os.path.join("static", "html")
    fname = f"{nom_fichier}.html"
    if not os.path.exists(os.path.join(path, fname)):
        abort(404)
    return send_from_directory(path, fname)

@point_astral_blocs_bp.route("/telecharger_point_astral/<nom_fichier>", methods=["GET"])
def telecharger_point_astral(nom_fichier):
    path = os.path.join("static", "pdfs")
    fname = f"{nom_fichier}.pdf"
    if not os.path.exists(os.path.join(path, fname)):
        abort(404)
    return send_from_directory(path, fname, as_attachment=True)

def transformer_en_sections_fallback(texte_brut: str) -> str:
    """
    Fonction fallback pour transformer le texte en sections HTML 
    si utils.formatage.transformer_en_sections n'est pas disponible
    """
    
    # Si le texte contient déjà des sections, les détecter
    if "---" in texte_brut:
        blocs = texte_brut.split("---")
    else:
        # Sinon, essayer de détecter des titres
        lignes = texte_brut.split('\n')
        blocs = []
        bloc_actuel = []
        
        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne:
                continue
                
            # Détecter les titres (lignes courtes avec ** ou ## ou majuscules)
            if (len(ligne) < 80 and 
                ('**' in ligne or ligne.startswith('#') or 
                 ligne.isupper() or ':' in ligne)):
                
                # Finir le bloc précédent
                if bloc_actuel:
                    blocs.append('\n'.join(bloc_actuel))
                    bloc_actuel = []
                
                # Commencer nouveau bloc
                bloc_actuel = [ligne]
            else:
                bloc_actuel.append(ligne)
        
        # Ajouter le dernier bloc
        if bloc_actuel:
            blocs.append('\n'.join(bloc_actuel))
    
    # Si on n'a qu'un seul bloc, créer une structure artificielle
    if len(blocs) <= 1:
        texte_complet = texte_brut
        blocs = [
            "## Profil Général\n" + texte_complet[:len(texte_complet)//3],
            "## Personnalité et Caractère\n" + texte_complet[len(texte_complet)//3:2*len(texte_complet)//3],
            "## Potentiels et Défis\n" + texte_complet[2*len(texte_complet)//3:],
        ]
    
    # Convertir chaque bloc en section HTML
    sections_html = []
    for i, bloc in enumerate(blocs, 1):
        if not bloc.strip():
            continue
            
        lignes = bloc.strip().split('\n')
        
        # Extraire le titre
        titre = lignes[0].replace('##', '').replace('#', '').replace('**', '').strip()
        if not titre:
            titre = f"Section {i}"
        
        # Extraire le contenu
        contenu_lignes = lignes[1:] if len(lignes) > 1 else lignes
        contenu = '\n'.join(contenu_lignes).strip()
        
        # Convertir en paragraphes HTML
        paragraphes = contenu.split('\n\n')
        contenu_html = ""
        for para in paragraphes:
            para_clean = para.strip().replace('\n', ' ')
            if para_clean:
                contenu_html += f"<p>{para_clean}</p>\n"
        
        # Déterminer la classe CSS
        classe = "conclusion" if i == len(blocs) else "section"
        
        # Créer la section HTML
        section_html = f'''
        <section class="{classe}">
            <h2>{titre}</h2>
            <div class="section-content">
                {contenu_html}
            </div>
        </section>'''
        
        sections_html.append(section_html)
    
    return '\n'.join(sections_html)

def generer_html_final_harmonise_pdf_only(
    texte_structure: str,
    infos_personnelles: dict,
    logo_base64: str = "",
    carte_astrale_data_uri: str | None = None,
) -> str:
    """Génère le HTML final pour le PDF (avec carte astrale + disclaimers)."""

    nom = infos_personnelles.get("nom", "Analyse Anonyme")
    date_naissance = infos_personnelles.get("date_naissance", "")
    heure_naissance = infos_personnelles.get("heure_naissance", "")
    lieu_naissance = infos_personnelles.get("lieu_naissance", "")

    # Fragments sûrs (évite les antislashs dans f-strings)
    logo_html = (
        f'<img src="data:image/webp;base64,{logo_base64}" '
        f'alt="Logo Les Fous d&#39;Astro" class="logo">'
        if logo_base64 else ""
    )

    carte_html = (
        f"""
        <section id="carte-astrale" class="section">
            <h2>Carte astrale</h2>
            <img src="{carte_astrale_data_uri}" alt="Carte astrale">
        </section>
        """.strip()
        if carte_astrale_data_uri else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Flash Astral - {nom}</title>
    <style>
        body {{
            font-family: Georgia, serif;
            margin: 0;
            padding: 40px;
            background: #ffffff;
            color: #2c3e50;
            line-height: 1.6;
            font-size: 15px;
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
            border-bottom: 2px solid #3498db;
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
        /* Carte astrale en PDF */
        #carte-astrale img {{
            width: 100%;
            height: auto;
            border-radius: 12px;
        }}
        @media print {{
            body {{ background: white; padding: 20px; }}
            .container {{ max-width: none; }}
            .header {{ page-break-after: avoid; }}
            #carte-astrale {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header" style="text-align: center; margin-bottom: 20px;">
        {logo_html}
        <h1 style="margin: 0; font-size: 24px; color: #333;">
            🌟 Flash Astral - {nom}
        </h1>

        <!-- ↓ AJOUT : centrage sûr -->
        <div class="personal-info" style="text-align: center;">
            <p style="margin: 5px 0; font-size: 14px; color: #666;">
                {date_naissance} — {heure_naissance} — {lieu_naissance}
            </p>
        </div>
    </div>
        <div class="disclaimer" style="background:#f8f9fa;border:1px solid #dee2e6;
            padding:16px;margin:20px 0;border-radius:8px;font-size:13px;line-height:1.5;">
            <p style="margin:0 0 8px 0;">
                <strong>⚠️ Le Flash Astral est une lecture automatisée express (≈4 pages).</strong><br>
                Il n’est en aucun cas <u>comparable</u> avec une analyse manuelle réalisée par mes soins, 
                où je prends en compte ton vécu, ton niveau de conscience, et où j’apporte une interprétation incarnée et sur mesure.  
                <br>Le Flash Astral donne un aperçu rapide de tes grands axes ; l’analyse manuelle est une plongée profonde et unique.
            </p>

            <p style="margin:0 0 8px 0;">
                <strong>❗️Important :</strong> Cette analyse reflète les potentiels énergétiques de ton thème natal. 
                <u>Chaque personne exprime ses énergies à des niveaux de conscience différents</u> selon son parcours, 
                sa culture, son environnement et ses choix. Certaines qualités peuvent rester en dormance, 
                s’exprimer de façon subtile, ou même par <em>compensation</em> (tu peux incarner l’inverse de ce qui est inscrit).
                <br>Il est normal de ne pas te reconnaître dans tous les aspects décrits. 
                L’astrologie révèle des tendances, pas des vérités absolues. 
                Cette analyse est un outil de réflexion, qui peut parfois résonner plus tard dans ta vie plutôt qu’aujourd’hui.
            </p>

            <p style="margin:0 0 8px 0;">
                <strong>🌙 À propos du Nakshatra :</strong> En astrologie védique, la Lune est reliée à un « nakshatra », 
                une constellation symbolique associée à une divinité ou une énergie. 
                Ce n’est pas une croyance religieuse, mais une image archétypale pour comprendre ton monde intérieur. 
                Par exemple, si ton nakshatra est <em>Swati</em>, il est lié au dieu du vent (Vayu) et reflète indépendance, 
                mouvement et quête de liberté. Cela donne une couleur particulière à ta sensibilité et à ta manière de ressentir.
            </p>

            <p style="margin:0 0 8px 0;">
                <strong>♻️ Note technique :</strong> Cette analyse est générée automatiquement avec l’aide d’un système d’IA. 
                De petites répétitions ou incohérences peuvent apparaître. Rien ne remplace un échange humain direct 
                pour approfondir ton thème.
            </p>

            <p style="margin:0;">
                <strong>💫 Pour aller plus loin :</strong> 
                Réserve une consultation personnalisée sur 
                <a href="https://bycecilecl.com" target="_blank" style="color:#1f628e; text-decoration:none;">
                www.bycecilecl.com
                </a>
            </p>
            </div>
        <main>
            {texte_structure}
        </main>

        <footer style="
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;  
            text-align: center;
            font-size: 12px;
            color: #666;
            line-height: 1.5;
        ">
            <p style="margin: 5px 0;">
                <strong>Les Fous d'Astro</strong> - Analyse générée automatiquement
            </p>
            
            <p style="margin: 5px 0;">
                lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr
            </p>
            
            <p style="margin: 5px 0;">
                IG : @lesfousdastro • @bycecilecl
            </p>
        </footer>
    </div>
</body>
</html>"""
    return html