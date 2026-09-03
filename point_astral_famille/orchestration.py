# orchestration/point_astral_blocs.py - VERSION BLOCS (sans affinage)

from typing import List, Dict, Optional
import logging
import re
from copy import deepcopy


from point_astral_famille.blocs.bloc_1 import (
    generer_bloc_1,
    build_resume_bloc1,
)
from point_astral_famille.blocs.bloc_2 import (
    generer_bloc_2_identite_v2,
    generer_bloc_2_famille_v2,
)
from point_astral_famille.blocs.bloc_3 import generer_bloc_3
from point_astral_famille.blocs.bloc_5 import generer_bloc_5
from utils.formatage import formater_positions_planetes
from point_astral_famille.calculs_astrologiques import get_maitres_ascendant
from point_astral_famille.selection_donnees import (
    extraire_axes_majeurs_payload,
    aspects_maitre_ascendant,
    construire_axes_conj_maitre_ascendant,
    construire_axes_majeurs_global,
    axes_payload_items,
    axes_payload_to_str,
    filtrer_items_pour_bloc3,
    formater_axes_majeurs,
    _get_points_forts_str,
    construire_conjonctions_angles_pour_prompts,
)

from point_astral_famille.database import charger_base_theme
from point_astral_famille.axes_utilises import extraire_axes_utilises

logger = logging.getLogger(__name__)

# TOPIC_PATTERNS = [
#     ("Ascendant",   re.compile(r"\basc(endant)?\b", re.I)),
#     ("Maison I",    re.compile(r"\b(maison\s*1|maison\s*i)\b", re.I)),
#     ("MaîtreAsc",   re.compile(r"\b(ma[iî]tre.*asc|r[eé]genteur.*asc)\b", re.I)),
#     ("Soleil",      re.compile(r"\bsoleil\b", re.I)),
#     ("Lune",        re.compile(r"\blune\b", re.I)),
#     ("Vénus",       re.compile(r"\bv[eé]nus\b", re.I)),
#     ("Mars",        re.compile(r"\bmars\b", re.I)),
#     ("Jupiter",     re.compile(r"\bjupiter\b", re.I)),
#     ("Saturne",     re.compile(r"\bsaturne\b", re.I)),
#     ("Uranus",      re.compile(r"\buranus\b", re.I)),
#     ("Neptune",     re.compile(r"\bneptune\b", re.I)),
#     ("Pluton",      re.compile(r"\bpluton\b", re.I)),
#     ("Amas",        re.compile(r"\bamas\b", re.I)),
#     ("Angles",      re.compile(r"\b(angle|asc|mc|fc|dc)\b", re.I)),
#     ("Dominantes",  re.compile(r"\bdominante(s)?\b", re.I)),
#     ("Nakshatra",   re.compile(r"\bnakshatra\b", re.I)),
# ]

SEPARATEUR = "\n\n---\n\n"


ENCADRE_FAMILLE = """
<div class="encadre-note">
<p class="encadre-titre">À propos de cette analyse familiale</p>
<p>IMPORTANT : Cette partie ne décrit pas tes parents tels qu'ils étaient objectivement, mais la manière dont tu as pu vivre ton environnement familial et les mécanismes psychologiques qui en ont découlé.</p>
<p>En astrologie, des situations très différentes peuvent laisser une empreinte intérieure similaire : une figure parentale absente, malade, débordée, autoritaire, protectrice à l'excès ou émotionnellement inaccessible peut générer des ressentis proches chez l'enfant : manque de sécurité, besoin de contrôle, difficulté à faire confiance, recherche de validation.</p>
<p>Lis cette partie comme une exploration de ton monde intérieur, pas comme un jugement sur tes proches. L'IA ne connaît pas le vécu réel des figures parentales. L'essentiel n'est pas de savoir si chaque détail correspond exactement à la réalité vécue, mais de comprendre les dynamiques qui ont façonné ta manière d'aimer, de te protéger et de construire tes relations.</p>
</div>
"""

# --- Bloc 3 : helpers d'exclusion ---
_FC_PATTERNS = (" FC", " Fond du Ciel", " Imum Coeli")

ALLOW_AMAS_NEUTRES = True

def generer_bloc_safe(nom_bloc: str, fonction_bloc, contexte_bloc: dict) -> str:
    try:
        return fonction_bloc(contexte_bloc)
    except Exception:
        logger.exception("ORCH: erreur génération %s", nom_bloc)
        return f"""
## {nom_bloc}

Une erreur est survenue pendant la génération de cette section.
"""

def est_exclu_bloc3(item: str) -> bool:
    """
    Exclut les placements isolés déjà traités dans les Blocs 1 et 2,
    mais conserve les aspects très serrés impliquant Soleil, Lune
    ou Ascendant lorsqu'ils structurent réellement le thème.
    """
    t = (item or "").lower()

    # Les conjonctions au FC restent réservées au Bloc 2 famille.
    if "conjonction" in t and any(
        pat.lower() in t
        for pat in _FC_PATTERNS
    ):
        return True

    implique_point_identitaire = (
        "ascendant" in t
        or "soleil" in t
        or ("lune" in t and "lune noire" not in t)
    )

    if not implique_point_identitaire:
        return False

    # On ne conserve que les véritables aspects.
    est_aspect = any(
        mot in t
        for mot in (
            "conjonction",
            "conjoint",
            "carré",
            "carre",
            "opposition",
        )
    )

    if not est_aspect:
        return True

    # Exception : un aspect identitaire extrêmement serré
    # reste un grand axe du thème.
    match_orbe = re.search(r"orbe\s+([\d\.,]+)", t)

    if not match_orbe:
        return True

    try:
        orbe = float(match_orbe.group(1).replace(",", "."))
    except (TypeError, ValueError):
        return True

    return orbe > 2.0

def orbe_trop_large_bloc3(item: str, max_orbe: float = 5.0) -> bool:
    """
    Exclut les aspects dont l'orbe dépasse le seuil du Bloc 3.
    Si aucune orbe n'est trouvée, on ne bloque pas l'item.
    """
    m = re.search(r"orbe\s+([\d\.,]+)", item.lower())
    if not m:
        return False

    try:
        orbe = float(m.group(1).replace(",", "."))
        return orbe > max_orbe
    except Exception:
        return False

def neutraliser_amas(item: str) -> Optional[str]:
    """
    Si 'item' est un amas qui mentionne Lune/Soleil,
    on les retire de la liste pour éviter les redites.
    Retourne la ligne réécrite, ou None si rien d'utile ne reste.
    """
    t = item.strip()
    if "amas" not in t.lower():
        return None

    # On essaye d'identifier la parenthèse "(...)" listant les planètes
    # et de retirer Lune/Soleil de cette liste.
    m = re.search(r"\(([^)]+)\)", t)
    if not m:
        # pas de parenthèses -> on laisse tel quel (ou None si tu préfères)
        return t

    contenu = m.group(1)
    # split naïf par virgule
    noms = [x.strip() for x in contenu.split(",")]
    # on retire Lune / Soleil (insensible à la casse)
    filtres = [n for n in noms if n.lower() not in ("lune", "soleil")]

    if not filtres:
        # il ne restait que Lune/Soleil -> on ne garde pas l'amas
        return None

    # réécriture
    contenu_neutre = ", ".join(filtres)
    # exemple: "Amas en Scorpion (Lune, Mercure, Mars)" -> "Amas en Scorpion (planètes : Mercure, Mars)"
    t_neutre = re.sub(r"\([^)]+\)", f"(planètes : {contenu_neutre})", t)
    return t_neutre

def _build_faits_autorises(data_theme: dict, placements_str: str) -> str:
    occ = (data_theme.get("planetes") 
           or data_theme.get("placements_occidentaux") 
           or data_theme.get("resultats_tropical") 
           or {})
    lignes = []
    for nom, d in (occ or {}).items():
        try:
            s = d.get("signe")
            m = d.get("maison")
            if s: lignes.append(f"{nom} en {s}")
            if m: lignes.append(f"{nom} en maison {m}")
        except Exception:
            pass
    angles_deg = data_theme.get("angles_deg") or {}
    for angle in ("Ascendant","MC","Descendant","FC"):
        if angle in angles_deg:
            lignes.append(f"{angle} défini")
    for a in (data_theme.get("aspects") or []):
        p1 = a.get("p1") or a.get("planete1")
        p2 = a.get("p2") or a.get("planete2")
        asp = (a.get("aspect") or "").capitalize()
        if asp in ("Conjonction","Opposition","Carré"):
            lignes.append(f"{p1} {asp} {p2}")
    pf = (data_theme.get("points_forts_compacts") 
          or data_theme.get("points_forts") 
          or "")
    if isinstance(pf, str) and pf.strip():
        for l in pf.splitlines():
            l = l.strip(" -•\t")
            if l:
                lignes.append(l)
    seen, out = set(), []
    for l in lignes:
        k = l.lower()
        if k not in seen:
            seen.add(k); out.append(l)
    return "\n".join(out)

# def rag_string_to_snippets(rag_text: str) -> List[Dict]:
#     if not rag_text:
#         return []
#     chunks = re.split(r"\n{2,}|[•\-]\s+|;\s+(?=[A-ZÉÈÀ])", rag_text)
#     out: List[Dict] = []
#     for raw in chunks:
#         t = (raw or "").strip()
#         if len(t) < 40:
#             continue
#         topic = "general"
#         for name, pat in TOPIC_PATTERNS:
#             if pat.search(t):
#                 topic = name; break
#         out.append({"texte": t, "source": "rag", "score": 0.5, "topic": topic})
#     return out

def _mini_apercu_bloc_1(texte: str, max_chars: int = 600) -> str:
    if not texte:
        return ""
    cut = texte[:max_chars]
    last_dot = cut.rfind(".")
    if last_dot > 100:
        cut = cut[:last_dot+1]
    return cut.strip()

def _assert_placements_ok(contexte: dict):
    p = (contexte.get("placements_str") or contexte.get("placements") or "").strip()
    if len(p) < 40 or "Ascendant" not in p:
        raise ValueError("PLACEMENTS_VIDES_OU_INCOMPLETS")

def nettoyer_bloc(contenu_bloc: str) -> str:
    return re.sub(r'^##\s*Bloc\s*\d+\s*[–-].*?\n', '', (contenu_bloc or "").strip(), flags=re.MULTILINE).strip()

def _normalize_maitre_nom(maitre):
    if isinstance(maitre, dict):
        nom = maitre.get("planete") or maitre.get("nom") or ""
    else:
        nom = str(maitre or "").strip()
        if nom:
            nom = nom.split()[0]
    return nom.capitalize()

# ⛔️ supprimé: toute la partie “Affinage final” (fonction produire_analyse_finale)

def generer_point_astral_blocs(contexte: dict) -> str:
    """
    Génère le point astral par blocs et retourne l’assemblage brut,
    sans aucune étape d’affinage.
    """
    logger.debug("ORCH: clés dispo : %s", list(contexte.keys()))
    logger.debug("ORCH: len(placements_str) = %s", len(contexte.get("placements_str", "")))


    # 🔑 RÉCUPÉRER LE THEME ICI
    theme = contexte.get("data_theme") or contexte.get("theme")
    if not theme:
        raise ValueError("ORCH: 'theme' manquant (ni 'data_theme' ni 'theme' dans le contexte)")

    # Assurer que placements_str et aspects sont présents dans le contexte
  
    if not contexte.get("placements_str"):
        try:
            contexte["placements_str"] = formater_positions_planetes(theme["planetes"])
            logger.info("ORCH: placements_str construit depuis theme")
        except Exception:
            logger.exception("ORCH: impossible de construire placements_str")

    # garder theme dispo partout
    contexte["theme"] = theme

    # sécuriser les aspects pour tous les blocs
    if not contexte.get("aspects") and theme.get("aspects"):
        contexte["aspects"] = theme["aspects"]
        logger.info(
            "ORCH: aspects injectés depuis theme (%s)",
            len(theme["aspects"]),
        )

    ps = contexte.get("placements_str", "")
    if "### Spécificités védiques utiles" in ps:
        bloc = ps.split("### Spécificités védiques utiles", 1)[1].split("###", 1)[0]
        apercu_vedique = "\n".join(bloc.splitlines()[:12])
        logger.debug("ORCH: extrait védique transmis:\n%s", apercu_vedique)
    else:
        logger.debug("ORCH: pas de bloc védique détecté dans placements_str")

    logger.info("ORCH: Début génération 4 blocs")

    _assert_placements_ok(contexte)

    # rag_par_topic = contexte.get("rag_par_topic")
    # if not rag_par_topic:
    #     rag_list = contexte.get("rag_list")
    #     if isinstance(rag_list, list) and len(rag_list) > 0:
    #         logger.info("ORCH: RAG en liste détecté (%s items)", len(rag_list))
    #         rag_par_topic = selectionner_snippets_par_topic(
    #             rag_list,
    #             top_k_par_topic=6,
    #             min_score=0.35,
    #             max_chars_par_snippet=350,
    #         )
    #     else:
    #         rag_text = (contexte.get("rag_snippets") or contexte.get("corpus_rag") or "") or ""
    #         rag_text = rag_text if isinstance(rag_text, str) else ""

    #         if rag_text.strip():
    #             logger.info(
    #                 "ORCH: RAG texte détecté (%s chars) → conversion en snippets",
    #                 len(rag_text),
    #             )
    #             snippets = rag_string_to_snippets(rag_text)
    #             logger.debug("ORCH: %s snippets construits", len(snippets))

    #             rag_par_topic = selectionner_snippets_par_topic(
    #                 snippets,
    #                 top_k_par_topic=6,
    #                 min_score=0.35,
    #                 max_chars_par_snippet=350,
    #             )
    #         else:
    #             rag_par_topic = {}

    # rag_bloc1 = digest_pour_bloc(rag_par_topic, ["Ascendant", "Maison I", "MaîtreAsc", "Soleil"], max_chars=1500) if rag_par_topic else ""
    # rag_bloc2 = digest_pour_bloc(rag_par_topic, ["Lune", "Nakshatra"], max_chars=1500) if rag_par_topic else ""
    # rag_bloc3 = digest_pour_bloc(rag_par_topic, ["Amas", "Conjonctions", "Dominantes", "Angles"], max_chars=1500) if rag_par_topic else ""
    # rag_bloc5 = digest_pour_bloc(rag_par_topic, ["Dominantes", "Ascendant", "Soleil", "Lune"], max_chars=1500) if rag_par_topic else ""

    # logger.debug(
    #     "ORCH: RAG digests chars: bloc1=%s, bloc2=%s, bloc3=%s, bloc5=%s",
    #     len(rag_bloc1),
    #     len(rag_bloc2),
    #     len(rag_bloc3),
    #     len(rag_bloc5),
    # )


    faits_aut = _build_faits_autorises(
        contexte.get("data_theme", {}),
        contexte.get("placements_str", ""),
    )
    contexte["faits_autorises"] = faits_aut
    logger.debug("ORCH: faits_autorises construits (%s chars)", len(faits_aut))
    base_interpretations = charger_base_theme(theme)
    contexte["base_interpretations"] = base_interpretations

    logger.info(
        "ORCH: base_interpretations chargée (%s astres)",
        len(base_interpretations),
    )

    ASC_SIGN_PAT = re.compile(r"Ascendant\s*:\s*[\d\.,]+\s*°\s*en\s+([A-Za-zÉÈÊÙÂÔÎäëïöüéèêàç\-]+)", re.I)

    if not contexte.get("maitre_ascendant"):
        m = ASC_SIGN_PAT.search(ps) or re.search(
            r"Ascendant\s*:\s*(?:[\d\.,]+\s*°?\s*(?:en\s+)?)?"
            r"(Bélier|Taureau|Gémeaux|Cancer|Lion|Vierge|Balance|Scorpion|"
            r"Sagittaire|Capricorne|Verseau|Poissons)\b",
            ps,
            re.IGNORECASE,
        )

        if m:
            signe = m.group(1).capitalize()
            maitre, second_maitre = get_maitres_ascendant(signe)

            if maitre:
                contexte["maitre_ascendant"] = maitre
                contexte["second_maitre_ascendant"] = second_maitre

                logger.info(
                    "ORCH: Maîtres Ascendant déduits : %s -> principal=%s | secondaire=%s",
                    signe,
                    maitre,
                    second_maitre or "aucun",
                )

    maitre_raw = contexte.get("maitre_ascendant")

    if isinstance(maitre_raw, dict):
        second_maitre = maitre_raw.get("second_nom")

        if second_maitre:
            contexte["second_maitre_ascendant"] = second_maitre

    maitre_nom = _normalize_maitre_nom(maitre_raw)

    logger.debug("ORCH: maitre_ascendant (raw) : %s", maitre_raw)
    logger.debug("ORCH: maitre_ascendant (norm) : %s", maitre_nom)

    aspects_dbg = contexte.get("aspects", [])

    logger.debug("ORCH: nb aspects : %s", len(aspects_dbg))

    for a in aspects_dbg[:5]:
        logger.debug("ORCH: sample aspect : %s", a)

    try:
        maitre_asc = contexte.get("maitre_ascendant")
        aspects = contexte.get("aspects", [])

        contexte["conj_maitre_asc"] = aspects_maitre_ascendant(
            maitre_asc,
            aspects,
            contexte.get("second_maitre_ascendant"),
        )

        logger.info(
            "ORCH: Conjonctions maître Ascendant trouvées : %s",
            contexte["conj_maitre_asc"],
        )

    except Exception:
        logger.exception("ORCH: Erreur détection conjonctions maître Ascendant")
        contexte["conj_maitre_asc"] = []

    if contexte.get("conj_maitre_asc"):
        try:
            contexte["conj_maitre_asc_str"] = "\n".join(
                f"- {str(a.get('p1'))} conjoint {str(a.get('p2'))} (orbe {float(str(a.get('orbe')).replace(',', '.')):.1f}°)"
                for a in contexte["conj_maitre_asc"]
            )
        except Exception:
            contexte["conj_maitre_asc_str"] = ""
    else:
        contexte["conj_maitre_asc_str"] = ""

    try:
        maitre_asc = contexte.get("maitre_ascendant")
        conj_list = contexte.get("conj_maitre_asc", [])
        axes_existants = contexte.get("axes_majeurs_list", [])
        axes_conj = construire_axes_conj_maitre_ascendant(maitre_asc, conj_list, max_items=3)
        axes_tous = (axes_existants or []) + axes_conj
        contexte["axes_majeurs_list"] = axes_tous

        try:
            contexte["axes_majeurs_str"] = formater_axes_majeurs(axes_tous)
        except Exception:
            contexte["axes_majeurs_str"] = "\n".join(f"- {ax.get('titre')}: {ax.get('resume')}" for ax in axes_tous)

        logger.info(
            "ORCH: Axes majeurs MAJ (maître Asc) : +%s entrée(s)",
            len(axes_conj),
        )

    except Exception:
        logger.exception("ORCH: Erreur intégration axes maître Asc")

    axes_global = construire_axes_majeurs_global(contexte)
    contexte["axes_majeurs_global"] = axes_global

    logger.debug(
        "ORCH: axes_majeurs_global length : %s",
        len(axes_global),
    )

    contexte_base = deepcopy(contexte)


    # ➜ construire placements_str comme dans l'analyse gratuite
    placements_str = contexte["placements_str"]

    ctx_b1 = {
        **contexte_base,
        "theme": theme,                     # 👈 INDISPENSABLE pour build_resume_bloc1()
        "placements_str": placements_str,   # 👈 base factuelle du prompt (comme la gratuite)
        # "rag_snippets": digest_pour_bloc(
        #     rag_par_topic,
        #     ["Ascendant", "Maison I", "MaîtreAsc", "Soleil"],
        #     max_chars=1500
        # ) if rag_par_topic else "",
        "faits_autorises": contexte_base.get("faits_autorises", ""),
        # (optionnel mais utile)
        "genre": contexte_base.get("genre", "non précisé"),
        "tonalite": "tu",
    }

    # traçage utile
    logger.debug("ORCH: theme ok ? %s", bool(ctx_b1.get("theme")))
    logger.debug("ORCH: len(placements_str) = %s", len(placements_str))

    b1 = generer_bloc_safe(
        "Bloc 1 - Personnalité & Identité",
        generer_bloc_1,
        ctx_b1,
    )

    b1, axes_utilises_bloc1 = extraire_axes_utilises(b1)

    logger.info("ORCH: Bloc 1 généré (len=%s)", len(b1))
    logger.info(
        "ORCH: Bloc 1 - axes utilisés : %s",
        axes_utilises_bloc1,
    )

    try:
        meta_bloc_1 = build_resume_bloc1(
            theme,
            placements_str,
        )

        points_bloc_1 = [
            ligne.strip()
            for ligne in (
                meta_bloc_1.get("points_prioritaires_bloc1")
                or ""
            ).splitlines()
            if ligne.strip() and ligne.strip() != "—"
        ]

        memoire_bloc_1 = {
            "axes_principaux": points_bloc_1,
        }

        logger.info(
            "ORCH: mémoire Bloc 1 construite (%s axes)",
            len(points_bloc_1),
        )

    except Exception:
        logger.exception(
            "ORCH: impossible de construire la mémoire du Bloc 1"
        )
        memoire_bloc_1 = {}

    apercu_b1 = _mini_apercu_bloc_1(nettoyer_bloc(b1))

    logger.info("ORCH: Génération Bloc 2...")

    # 1) S'assurer que placements_str est dispo (sinon on le reconstruit depuis theme)
    placements_str_b2 = contexte_base.get("placements_str", "")
    if (not placements_str_b2 or len(placements_str_b2) < 50) and theme.get("planetes"):
        try:
            
            placements_str_b2 = formater_positions_planetes(theme["planetes"])
            logger.info("ORCH: Bloc 2 — placements_str reconstruit depuis theme")

        except Exception:
            logger.exception("ORCH: Bloc 2 — reconstruction placements_str impossible")
            placements_str_b2 = contexte_base.get("placements_str", "") or ""

    # 2) S'assurer que les aspects sont bien présents (certains helpers en ont besoin)
    if not contexte_base.get("aspects") and theme.get("aspects"):
        contexte_base["aspects"] = theme["aspects"]
        logger.info(
            "ORCH: Bloc 2 — aspects injectés (%s)",
            len(theme["aspects"]),
        )

    # 3) RAG ciblé pour le monde intérieur + pôle père/autorité
    # rag_topics_b2 = ["Lune", "Nakshatra", "Maison IV", "IC", "Soleil", "Saturne", "Maison X", "MC"]
    # rag_b2 = digest_pour_bloc(rag_par_topic, rag_topics_b2, max_chars=1500) if rag_par_topic else ""

    

    # 1) S'assurer que theme possède bien planetes_deg / angles_deg (side-effects)
    try:
        _ = _get_points_forts_str(theme)  # remplit theme["planetes_deg"] et theme["angles_deg"]
    except Exception:
        logger.exception(
            "ORCH: _get_points_forts_str(theme) a échoué (deg angles)"
        )

    # 2) Construire les blocs texte par angle et injecter dans le contexte
    try:
        angles_blocks_b2 = construire_conjonctions_angles_pour_prompts(theme, orb_max=5.0)
        contexte_base["conjonctions_ic"]  = (angles_blocks_b2.get("conjonctions_ic")  or "").strip()
        contexte_base["conjonctions_mc"]  = (angles_blocks_b2.get("conjonctions_mc")  or "").strip()
        # optionnel :
        contexte_base["conjonctions_asc"] = (angles_blocks_b2.get("conjonctions_asc") or "").strip()
        contexte_base["conjonctions_dsc"] = (angles_blocks_b2.get("conjonctions_dsc") or "").strip()

        # debug lisible
        logger.debug("DEBUG B2 <conjonctions_ic>")
        logger.debug("%s", contexte_base["conjonctions_ic"] or "—")

        logger.debug("DEBUG B2 <conjonctions_mc>")
        logger.debug("%s", contexte_base["conjonctions_mc"] or "—")

    except Exception:
        logger.exception(
            "ORCH: construction conjonctions d’angles (B2) impossible"
        )

    # 4) Construire le contexte Bloc 2 (⚠️ 'theme' et 'placements_str' sont indispensables)
    ctx_b2 = {
        **contexte_base,
        "theme": theme,                      # requis par build_resume_bloc2()
        "placements_str": placements_str_b2, # base factuelle
        #"rag_snippets": rag_b2,
        "genre": contexte_base.get("genre", "femme"),
        "tonalite": contexte_base.get("tonalite", "tu"),
    }

    # 5) Générer Bloc 2
    b2_identite = generer_bloc_safe(
        "Bloc 2 - Identité émotionnelle",
        generer_bloc_2_identite_v2,
        ctx_b2,
    )

    ctx_b2["bloc_2_identite"] = b2_identite

    b2_famille = generer_bloc_safe(
        "Bloc 2bis - Dynamique familiale",
        generer_bloc_2_famille_v2,
        ctx_b2,
    )

    logger.info("ORCH: Bloc 2 identité généré (len=%s)", len(b2_identite))
    logger.info("ORCH: Bloc 2bis famille généré (len=%s)", len(b2_famille))

    apercu_b2 = _mini_apercu_bloc_1(nettoyer_bloc(b2_identite + "\n\n" + b2_famille))

    # 6) Préparer les axes majeurs pour le bloc suivant

    # ⬇️ 1) Récupérer et injecter les Points forts AVANT d’extraire le payload
    try:
        pf_md = _get_points_forts_str(theme)
        if pf_md and pf_md.strip():
            contexte["points_forts"] = pf_md

            logger.info(
                "ORCH: points_forts injectés (%s chars)",
                len(pf_md),
            )

        else:
            logger.info("ORCH: pas de points_forts MD disponible")

    except Exception:
        logger.exception(
            "ORCH: _get_points_forts_str(theme) a échoué"
        )

    # ⬇️ 2) Maintenant on construit le payload puis on filtre pour le Bloc 3
    axes_payload = extraire_axes_majeurs_payload(contexte)  # ← APRES injection
    axes_all_items = axes_payload_items(axes_payload)

    # 2) Premier filtrage métier :
    # retirer les éléments interdits ou déjà traités dans les Blocs 1 et 2.
    axes_items_preselectionnes = [
        it
        for it in axes_all_items
        if not est_exclu_bloc3(it)
        and not orbe_trop_large_bloc3(it)
        and not it.strip().startswith("###")
        and "junon" not in it.lower()
        and "juno" not in it.lower()
        and "chiron" not in it.lower()
        and "point d’illumination" not in it.lower()
        and "point d'illumination" not in it.lower()
        and "point illumination" not in it.lower()
    ]

    # 3) Priorisation et limitation réelle du nombre d’indices.
    #
    # Cette fonction était déjà importée mais n’était jamais utilisée.
    # Elle trie les éléments et limite le volume transmis au LLM.
    axes_items = filtrer_items_pour_bloc3(
        axes_items_preselectionnes,
        max_items=10,
    )

    # 4) Conserver éventuellement un amas après retrait de Soleil/Lune.
    if ALLOW_AMAS_NEUTRES:
        for item in axes_all_items:
            texte_item = item.lower()

            if "amas" not in texte_item:
                continue

            if "lune" not in texte_item and "soleil" not in texte_item:
                continue

            item_neutre = neutraliser_amas(item)

            if (
                item_neutre
                and item_neutre.lower()
                not in {axe.lower() for axe in axes_items}
            ):
                axes_items.append(item_neutre)

            break

    # On conserve au maximum 10 éléments après l’ajout éventuel de l’amas.
    axes_items = axes_items[:10]

    # 5) Fallback maison angulaire uniquement s’il reste de la place.
    if (
        len(axes_items) < 10
        and not any(
            "maison angulaire" in item.lower()
            for item in axes_items
        )
    ):
        for item in axes_all_items:
            if "maison angulaire" not in item.lower():
                continue

            axes_items.insert(0, item)
            axes_items = axes_items[:10]

            logger.info(
                "ORCH: maison angulaire ajoutée dans axes_items : %s",
                item,
            )
            break

    axes_str = "\n".join(
        f"- {item}"
        for item in axes_items
    )

    # Les deux formats sont conservés temporairement :
    # - axes_items pour le traitement ;
    # - axes_majeurs_input pour la compatibilité avec l’ancien Bloc 3.
    contexte["axes_items"] = axes_items
    contexte["axes_majeurs_input"] = axes_str

    # Les configurations ont normalement été calculées par la route.
    configurations_majeures = (
        contexte_base.get("configurations_majeures")
        or []
    )

    configurations_majeures_str = (
        contexte_base.get("configurations_majeures_str")
        or ""
    )

    logger.info(
        "ORCH: Bloc 3 reçoit %s axe(s) et %s configuration(s)",
        len(axes_items),
        len(configurations_majeures),
    )

    logger.info("ORCH: Génération Bloc 3...")

    ctx_b3 = {
        **contexte_base,

        "theme": theme,

        # "rag_snippets": digest_pour_bloc(
        #     rag_par_topic,
        #     [
        #         "Amas",
        #         "Conjonctions",
        #         "Dominantes",
        #         "Angles",
        #     ],
        #     max_chars=1500,
        # ) if rag_par_topic else "",

        # Ancien système nettoyé et limité.
        "axes_items": axes_items,
        "axes_majeurs_input": axes_str,

        # Nouveau moteur structuré.
        "configurations_majeures": configurations_majeures,
        "configurations_majeures_str": configurations_majeures_str,

        "points_forts": contexte.get(
            "points_forts",
            "",
        ),

        "faits_autorises": contexte.get(
            "faits_autorises",
            "",
        ),

        # Les deux blocs précédents sont maintenant transmis.
        "apercu_bloc_1": apercu_b1,
        "apercu_bloc_2": apercu_b2,
    }

    print("\n===== DEBUG ORCH AVANT BLOC 3 =====")
    print("axes_items =", axes_items)
    print(
        "configurations_majeures =",
        [
            configuration.get("type")
            for configuration in configurations_majeures
        ],
    )
    print(
        "apercu_bloc_1 présent =",
        bool(ctx_b3.get("apercu_bloc_1")),
    )
    print(
        "apercu_bloc_2 présent =",
        bool(ctx_b3.get("apercu_bloc_2")),
    )
    print("===== FIN DEBUG ORCH AVANT BLOC 3 =====\n")

    b3 = generer_bloc_safe(
        "Bloc 3 - Axes majeurs",
        generer_bloc_3,
        ctx_b3,
    )
    logger.info("ORCH: Génération Bloc 5...")

    ctx_b5 = {
        **contexte_base,
        #"rag_snippets": digest_pour_bloc(rag_par_topic, ["Dominantes","Ascendant","Soleil","Lune"], max_chars=1500) if rag_par_topic else "",
    }
    memoires_precedentes = {
        "bloc_1": ctx_b1.get("resume_bloc1", ""),
        "bloc_2_identite": ctx_b2.get("resume_bloc2_identite", ""),
        "bloc_2_famille": ctx_b2.get("resume_bloc2_famille", ""),
        "bloc_3": ctx_b3.get("resume_bloc3", ""),
    }

    b5 = generer_bloc_5(
        ctx_b5,
        memoires_precedentes=memoires_precedentes,
    )

    logger.info("ORCH: Nettoyage des blocs...")
    b1_clean = nettoyer_bloc(b1)
    b2_identite_clean = nettoyer_bloc(b2_identite)
    b2_famille_clean = nettoyer_bloc(b2_famille)
    famille_en_erreur = (
        "Une erreur est survenue pendant la génération"
        in b2_famille_clean
    )

    section_famille = (
        "## Racines & dynamique familiale\n\n"
        + ("" if famille_en_erreur else ENCADRE_FAMILLE + "\n\n")
        + b2_famille_clean
    )
    b3_clean = nettoyer_bloc(b3)
    b5_clean = nettoyer_bloc(b5)
    b5_clean = re.sub(
        r"^\s*(?:#{1,6}\s*)?(?:Synthèse(?: psychologique| globale| intégrée)?|Mode d['’]emploi)\s*:?\s*\n+",
        "",
        b5_clean,
        flags=re.IGNORECASE,
    )

    assemblage_brut = SEPARATEUR.join([
        "## Personnalité & Identité\n\n" + b1_clean,
        "## Lune & Monde intérieur\n\n" + b2_identite_clean,
        section_famille,
        "## Les Axes Majeurs\n\n" + b3_clean,
        "## Synthèse\n\n" + b5_clean,
    ]).strip()


    
    # ✅ Pas d’affinage : on retourne directement l’assemblage des blocs
    return assemblage_brut
