# routes/point_astral_blocs.py - VERSION HARMONISÉE
from flask import Blueprint, render_template, session, send_from_directory, abort, request, url_for,current_app
import inspect
from datetime import datetime
import re
import os
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
import logging
logger = logging.getLogger(__name__)

# # 1) Essayer d'importer l'overlay (fond Canva)
# try:
#     from utils.chart_overlay import draw_overlay_on_background  # type: ignore
#     _OVERLAY_OK = True
#     print("✅ Overlay Canva dispo (utils.chart_overlay.draw_overlay_on_background).")
# except Exception as _e:
#     _OVERLAY_OK = False
#     draw_overlay_on_background = None  # type: ignore
#     print(f"ℹ️ Pas d’overlay Canva: {_e}")

# # 2) Essayer d'importer une wheel matplotlib (plusieurs alias possibles)
# _WHEEL_FN = None
# try:
#     from utils.chart_wheel import draw_natal_chart as _WHEEL_FN  # type: ignore
#     print("✅ Wheel: utils.chart_wheel.draw_natal_chart")
# except Exception:
#     try:
#         from utils.chart_wheel import generate_natal_chart as _WHEEL_FN  # type: ignore
#         print("✅ Wheel: utils.chart_wheel.generate_natal_chart")
#     except Exception:
#         try:
#             from utils.chart_wheel import draw_chart_wheel as _WHEEL_FN  # type: ignore
#             print("✅ Wheel: utils.chart_wheel.draw_chart_wheel")
#         except Exception as _err_wheel:
#             print(f"ℹ️ Aucune wheel importable: {_err_wheel}")
#             _WHEEL_FN = None

# # 3) Fallback 1×1 (permet de continuer le pipeline sans casser le PDF/email)
# _PNG_1x1 = base64.b64decode(
#     "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO1GQhQAAAAASUVORK5CYII="
# )
# def _write_placeholder(path: str):
#     try:
#         os.makedirs(os.path.dirname(path), exist_ok=True)
#         with open(path, "wb") as f:
#             f.write(_PNG_1x1)
#         print("🟡 Fallback carte: PNG 1×1 écrit (pas de rendu réel).")
#     except Exception as e:
#         print(f"⚠️ Impossible d’écrire le placeholder {path}: {e}")

# # 4) Wrapper unifié exposé sous le NOM attendu: draw_natal_chart(...)
# def draw_natal_chart(planetes_deg, maisons_deg, asc=None, mc=None, outfile=None, **kwargs):
#     """
#     Rendu de la carte : OVERLAY CANVA UNIQUEMENT.
#     - Conserve tous les paramètres personnalisés
#     """
#     if not outfile:
#         return

#     # On récupère uniquement ce qui est utile à l’overlay
#     background_path = kwargs.get("background_path", None)  # ← .get() au lieu de .pop()
#     glyphs_png_map = kwargs.get("glyphs_png_map", None)    # ← .get() au lieu de .pop()


#     # On JETTE tous les autres kwargs (c’est eux qui imposaient planet_size_px=24, etc.)
#     #kwargs.clear()

#     # Valeur par défaut si rien n’est passé
#     if not background_path:
#         background_path = "static/images/zodiaque_base.png"

#     # Si pas de fond valide → placeholder
#     if not os.path.exists(background_path):
#         print(f"🟡 Pas de background valide ({background_path}) → placeholder 1×1.")
#         _write_placeholder(outfile)
#         return outfile

#     try:
#         # Appel OVERLAY UNIQUEMENT (aucun override parasite)
#         return draw_overlay_on_background(
#             background_path=background_path,
#             outfile=outfile,
#             planetes_deg=planetes_deg,
#             maisons_deg=maisons_deg,
#             asc=asc,
#             mc=mc,
#             glyphs_png_map=(glyphs_png_map or {}),
#             # ⚠️ Forcez les paramètres pour les maisons à l'extérieur :
#             house_label_on_sign=False,     # Numéros à l'extérieur
#             draw_house_ring=True,          # Anneau des maisons visible
#             house_label_offset=30,         # Distance des numéros
#             house_ring_margin=40,          # Taille de l'anneau externe
#             cusp_tick_len_px=20,          # Longueur des cuspides
#             **kwargs  # Autres paramètres personnalisés
#         )
#     except Exception as e:
#         print(f"⚠️ Erreur overlay: {e} → placeholder.")
#         _write_placeholder(outfile)
#         return outfile

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
    
    # Récupération des infos depuis la session
    infos = session.get("infos_utilisateur")
    if not infos:
        return "❌ Données manquantes. Veuillez recommencer depuis le formulaire."
    
    warnings_list = []
    contexte = {}
    
    task_id = session.get('current_task_id')
    print(f"Début analyse Point Astral avec progression - Task ID: {task_id}")
    print(f"🔍 DEBUG SESSION COMPLÈTE: {infos}")
    print(f"🔍 DEBUG CLÉS SESSION: {list(infos.keys()) if infos else 'None'}")
    print(f"\n{'='*60}")
    print(f"🎬 Point_Astral_Bloc DÉBUT ANALYSE POINT ASTRAL BLOCS (harmonisé)")
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

            
        # # --- B) Générer la CARTE (PNG) + Data URI ---
        # charts_dir = os.path.join(current_app.static_folder, "charts")
        # os.makedirs(charts_dir, exist_ok=True)
        # carte_png = os.path.join(charts_dir, f"carte_{nom_fichier}.png")

        # # Fond Canva prioritaire (overlay)
        # fond_canva = os.path.join(current_app.static_folder, "images", "zodiaque_base.png")
        # if not os.path.exists(fond_canva):
        #     print("⚠️ Fond Canva manquant, fallback matplotlib.")
        #     fond_canva = None

        # # Remap planètes -> overlay/wheel
        # PLANET_KEY_MAP = {
        #     "Soleil": "Sun", "Lune": "Moon", "Mercure": "Mercury",
        #     "Vénus": "Venus", "Venus": "Venus", "Mars": "Mars",
        #     "Jupiter": "Jupiter", "Saturne": "Saturn", "Uranus": "Uranus",
        #     "Neptune": "Neptune", "Pluton": "Pluto",
        # }
        # ALLOWED_PLANETS = {"Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"}

        # def _to_float(x):
        #     try:
        #         return float(x)
        #     except Exception:
        #         return None

        # def _pluck_lon(v):
        #     if isinstance(v, (int, float, str)):
        #         return _to_float(v)
        #     if isinstance(v, dict):
        #         for k in ("degre", "deg", "lon", "longitude", "degree"):
        #             if k in v:
        #                 return _to_float(v[k])
        #     return None

        # planets_chart = {}
        # if isinstance(planetes_deg, dict):
        #     for k, v in planetes_deg.items():
        #         key = PLANET_KEY_MAP.get(k, k)
        #         if key not in ALLOWED_PLANETS:
        #             continue
        #         deg = _pluck_lon(v) if isinstance(v, dict) else _to_float(v)
        #         if deg is not None:
        #             planets_chart[key] = deg

        # print("ASC:", asc, "| MC:", mc)
        # print("Maisons (1-12):", [maisons_deg.get(i) for i in range(1, 13)])
        # print("Planètes:", sorted(planets_chart.keys()))

        # overlay_opts = dict(
        #     draw_house_ring=False,
        #     house_label_on_sign=True,
        #     house_label_offset=10,
        #     cusp_tick_len_px=16,
        #     planet_offset_px=36,
        #     planet_size_px=24,
        #     planet_text_font_px=42,
        #     house_font_px=18,
        #     planet_font_path="static/fonts/AstroSymbols.ttf",
        #     house_font_path="static/fonts/DejaVuSans.ttf",
        #     respect_background_orientation=True,
        # )

        # # --- Génération de la carte avec fallback proprement imbriqué ---
        # try:
        #     # 1) Overlay sur fond Canva si dispo
        #     draw_natal_chart(
        #         planets_chart,
        #         maisons_deg,
        #         asc=asc, mc=mc,
        #         outfile=carte_png,
        #         background_path=fond_canva,
        #         glyphs_png_map=None,
        #         **overlay_opts
        #     )
        #     print("✅ Carte astrale (overlay) générée.")
        # except Exception as overlay_err:
        #     print(f"⚠️ Overlay échoué: {overlay_err} → fallback matplotlib")
        #     try:
        #         # 2) Fallback matplotlib
        #         from utils.astro_chart import draw_chart_basic
        #         maisons_list = [maisons_deg.get(i) for i in range(1, 13)]
        #         draw_chart_basic(
        #             asc_deg=float(asc) if asc is not None else 0.0,
        #             house_cusps_deg=maisons_list,
        #             output_path=carte_png,
        #             planets_deg=planets_chart,
        #             figsize=(5, 5),
        #             dpi=150,
        #             show_axes=False,
        #         )
        #         print("✅ Carte astrale (matplotlib) générée.")
        #     except Exception as mpl_err:
        #         # 3) Dernier recours : placeholder 1x1
        #         print(f"⚠️ Fallback matplotlib indisponible: {mpl_err} → placeholder")
        #         _write_placeholder(carte_png)

        # # --- URLs & Data URI ---
        # rel = os.path.relpath(carte_png, current_app.static_folder).replace("\\", "/")
        # carte_astrale_url = url_for("static", filename=rel, _external=False)
        # with open(carte_png, "rb") as f:
        #     carte_astrale_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

        # # Fallback affichage web si pas d’URL fichier
        # if not carte_astrale_url and carte_astrale_data_uri:
        #     carte_astrale_url = carte_astrale_data_uri
        #     print("ℹ️ Fallback: carte_astrale_url = data URI (affichage web).")

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

        # --- E) Envoi d’email NON bloquant ---
        try:
            dest_email = (infos.get("email") or "").strip()
            if dest_email:
                prenom = (infos.get("nom") or "").split()[0] or "toi"
                sujet_email = "✨ Ton Point Astral est prêt"
                body_txt = (
                    f"Bonjour {prenom},\n\n"
                    "Merci pour ta commande ! Ton Point Astral est prêt ✨\n\n"
                    "Télécharge ton PDF ici :\n"
                    f"{pdf_final_url}\n\n"
                    "Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.\n\n"
                    "À bientôt,\n"
                    "Les Fous d’Astro – By Cécile CL"
                )
                body_html = (
                    f"<p>Bonjour {prenom},</p>"
                    "<p>Merci pour ta commande ! Ton Point Astral est prêt ✨</p>"
                    f"<p>📄 <a href=\"{pdf_final_url}\" target=\"_blank\">Télécharge ton PDF ici</a></p>"
                    "<p>Si le lien ne s’ouvre pas, copie/colle l’URL dans ton navigateur.</p>"
                    "<p>À bientôt,<br>Les Fous d’Astro – By Cécile CL</p>"
                )
                # Utilise ton sender existant (sans PJ, non bloquant)
                from utils.email_sender import envoyer_email_avec_analyse
                envoyer_email_avec_analyse(
                    destinataire=dest_email,
                    sujet=sujet_email,
                    contenu_txt=body_txt,
                    contenu_html=body_html,
                    pdf_path=None
                )
        except Exception as e:
            logger.warning(f"Email non envoyé (réseau/SMTP) : {e}")
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
    <title>Point Astral - {nom}</title>
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
            🌟 Point Astral - {nom}
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
                <strong>⚠️ À propos de cette analyse :</strong><br>
                Ce Point Astral n'est pas fait pour te brosser dans le sens du poil ! 
                Il explore tes zones d'ombre autant que tes forces, dans l'objectif de révéler ton potentiel authentique. 
                Cette analyse peut soulever des aspects inconfortables de ta personnalité, 
                mais ne te laisse pas décourager : chaque ombre révélée est une opportunité de croissance.
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