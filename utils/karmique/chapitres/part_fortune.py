from __future__ import annotations
from typing import Any, Dict, Optional, Callable, List

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging
logger = logging.getLogger(__name__)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _slug(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    s = s.replace("à", "a").replace("â", "a")
    s = s.replace("î", "i").replace("ï", "i")
    s = s.replace("ô", "o")
    s = s.replace("ù", "u").replace("û", "u").replace("ü", "u")
    s = s.replace("ç", "c")
    s = s.replace("œ", "oe")
    s = s.replace("’", "'")
    s = s.replace(" ", "_")
    return s

SIGNS = [
    "Bélier", "Taureau", "Gémeaux", "Cancer",
    "Lion", "Vierge", "Balance", "Scorpion",
    "Sagittaire", "Capricorne", "Verseau", "Poissons"
]

def _angular_distance(a: float, b: float) -> float:
    diff = abs((a - b) % 360.0)
    return min(diff, 360.0 - diff)


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _norm_aspect_name(x: Any) -> str:
    if not x:
        return ""
    x = str(x).strip().lower()
    mapping = {
        "carre": "Carré",
        "carré": "Carré",
        "opposition": "Opposition",
        "conjonction": "Conjonction",
        "trigone": "Trigone",
        "sextile": "Sextile",
        "quinconce": "Quinconce",
        "sesqui-carre": "Sesqui-carré",
        "sesqui carré": "Sesqui-carré",
        "sesquicarre": "Sesqui-carré",
    }
    return mapping.get(x, str(x).capitalize())


def _bdd(astre: str, donnee: str, valeur: Any) -> str:
    if valeur is None:
        return ""
    txt = get_karmique_interp(astre, donnee, str(valeur))
    return txt.strip() if isinstance(txt, str) and txt.strip() else ""


def _get_house_from_longitude(theme: Dict[str, Any], longitude: float) -> Optional[int]:
    """
    Recalcule la maison à partir de theme['maisons'] si besoin.
    """
    maisons = theme.get("maisons")
    if not isinstance(maisons, dict):
        return None

    ordered = []
    for i in range(1, 13):
        key = f"Maison {i}"
        if key not in maisons:
            logger.debug("POF | Maison manquante dans theme['maisons'] : %s", key)
            return None
        ordered.append(maisons[key])

    cusp_lons = []
    for m in ordered:
        deg = _safe_float(m.get("degre"))
        if deg is None:
            logger.debug("POF | Degré cuspide invalide pour %s", key)
            return None
        cusp_lons.append(deg % 360.0)

    x = longitude % 360.0

    for i in range(12):
        start = cusp_lons[i]
        end = cusp_lons[(i + 1) % 12]

        if start < end:
            if start <= x < end:
                return i + 1
        else:
            # passage 360 -> 0
            if x >= start or x < end:
                return i + 1

    return None


# --------------------------------------------------
# Aspects Part de Fortune
# --------------------------------------------------

def _collect_pof_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Calcule mathématiquement les aspects à la Part de Fortune avec des orbes sur-mesure,
    indépendamment des aspects renvoyés par l'API source.
    """
    planetes = theme.get("planetes") or {}
    pof = planetes.get("Part de Fortune") or theme.get("part_de_fortune") or {}
    
    pof_lon = _safe_float(pof.get("degre"))
    if pof_lon is None:
        return []

    # Les objets autorisés
    allowed_points = {
        "Soleil", "Lune", "Mercure", "Vénus", "Mars",
        "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
        "Chiron", "Lune Noire",
        "Rahu", "Ketu", "Nœud Nord", "Nœud Sud", "Noeud Nord", "Noeud Sud",
        "Ascendant", "Descendant", "MC", "FC"
    }

    # Ton mapping pour les clés de BDD
    label_map = {
        "Soleil": "soleil", "Lune": "lune", "Mercure": "mercure", "Vénus": "venus",
        "Mars": "mars", "Jupiter": "jupiter", "Saturne": "saturne", "Uranus": "uranus",
        "Neptune": "neptune", "Pluton": "pluton", "Chiron": "chiron", "Lune Noire": "lune_noire",
        "Rahu": "noeud_nord", "Nœud Nord": "noeud_nord", "Noeud Nord": "noeud_nord",
        "Ketu": "noeud_sud", "Nœud Sud": "noeud_sud", "Noeud Sud": "noeud_sud",
        "Ascendant": "ascendant", "Descendant": "descendant", "MC": "mc", "FC": "fc",
    }

    out: List[Dict[str, Any]] = []

    # ORBES SUR MESURE POUR LA PART DE FORTUNE
    ORB_MAJEUR = 5.5  # Conjonction / Opposition
    ORB_MINEUR = 3.0  # Carré uniquement

    for name, data in planetes.items():
        if name not in allowed_points or not isinstance(data, dict):
            continue
            
        p_lon = _safe_float(data.get("degre"))
        if p_lon is None:
            continue

        # Distance la plus courte sur le cercle
        dist = _angular_distance(pof_lon, p_lon)
        
        aspect_name = None
        orb = None

        # Vérification des aspects mathématiques
        if dist <= ORB_MAJEUR:
            aspect_name = "Conjonction"
            orb = dist
        elif abs(dist - 180.0) <= ORB_MAJEUR:
            aspect_name = "Opposition"
            orb = abs(dist - 180.0)
        elif abs(dist - 90.0) <= ORB_MINEUR:
            aspect_name = "Carré"
            orb = abs(dist - 90.0)

        # Si un aspect est détecté, on l'ajoute
        if aspect_name:
            other_key = label_map.get(name, _slug(name))
            out.append({
                "with": name,
                "aspect": aspect_name,
                "orb": round(orb, 2),
                "bdd_key": f"aspect_{other_key}",
            })

    # On trie du plus précis (orbe 0) au plus large
    out.sort(key=lambda x: x["orb"])
    return out


# --------------------------------------------------
# Build block
# --------------------------------------------------

def build_block_part_fortune(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    planetes = theme.get("planetes") or {}

    pof = (
        planetes.get("Part de Fortune")
        or theme.get("part_de_fortune")
        or {}
    )

    resultats_tropical = theme.get("resultats_tropical", {}) or {}
    point_illumination = (
        resultats_tropical.get("Point d’Illumination")
        or theme.get("point_illumination")
        or {}
    )

    logger.debug("POF | theme keys=%s", list(theme.keys()))
    logger.debug("POF | resultats_tropical exists=%s", "resultats_tropical" in theme)
    logger.debug(
        "POF | resultats_tropical keys=%s",
        list(resultats_tropical.keys()) if isinstance(resultats_tropical, dict) else resultats_tropical
    )
    logger.debug("POF | Point d’Illumination raw=%s", point_illumination)

    if not isinstance(pof, dict) or not pof:
        return None

    signe = pof.get("signe") or pof.get("sign")
    maison = pof.get("maison") or pof.get("house")
    deg = pof.get("degre_dans_signe")

    # --------------------------------------------------
    # CALCUL DYNAMIQUE DU POINT D'ILLUMINATION
    # --------------------------------------------------
    longitude = _safe_float(pof.get("degre"))
    
    # On récupère les valeurs de l'API s'elles existent (au cas où)
    signe_illum = point_illumination.get("signe")
    maison_illum = point_illumination.get("maison")
    deg_illum = point_illumination.get("degre_dans_signe") or point_illumination.get("degree_in_sign")

    # SI L'API NE DONNE RIEN, ON LE CALCULE (+ 180°)
    if not signe_illum and longitude is not None:
        illum_lon = (longitude + 180.0) % 360.0
        
        # Trouver le signe et le degré
        sign_index = int(illum_lon // 30)
        signe_illum = SIGNS[sign_index]
        deg_illum = round(illum_lon - (sign_index * 30), 2)
        
        # Trouver la maison avec ta fonction robuste
        maison_illum = _get_house_from_longitude(theme, illum_lon)

    logger.debug("POF | signe_illum=%s", signe_illum)
    logger.debug("POF | maison_illum=%s", maison_illum)
    logger.debug("POF | deg_illum=%s", deg_illum)

    if deg is None:
        deg = pof.get("degree_in_sign")

    if maison is None and longitude is not None:
        maison = _get_house_from_longitude(theme, longitude)

    if not signe and maison is None:
        return None

    # BDD
    txt_signe = _bdd("part_fortune", "signe", _slug(signe)) if signe else ""
    txt_maison = _bdd("part_fortune", "maison", maison) if maison is not None else ""

    txt_illum_maison = _bdd("point_illumination", "Maison", maison_illum) if maison_illum is not None else ""

    aspects_pof = _collect_pof_aspects(theme)

    # --------------------------------------------------
    # Synthèse enrichie selon ta doctrine
    # --------------------------------------------------
    profil = []

    # Maison prioritaire
    if maison in [1, 4, 7, 10]:
        profil.append("point de fortune fortement valorisé (maison angulaire)")

    if maison == 10:
        profil.append("réalisation professionnelle favorisée")
    elif maison == 6:
        profil.append("épanouissement par le travail, le quotidien ou le service")
    elif maison == 2:
        profil.append("rapport favorable aux ressources, aux talents concrets ou à la sécurité matérielle")
    elif maison == 5:
        profil.append("valorisation personnelle, créativité ou reconnaissance facilitées")
    elif maison in [3, 9]:
        profil.append("expression intellectuelle, transmission ou reconnaissance mentale soutenues")

    # Signe secondaire mais important
    signe_slug = _slug(signe)

    if signe_slug in ["cancer", "poissons", "scorpion"]:
        profil.append("dimension intime, instinctive et refuge intérieur accentués (signe d'eau)")

    if signe_slug == "taureau":
        profil.append("placement particulièrement favorable (exaltation lunaire + terrain de stabilité)")

    if signe_slug in ["balance", "taureau"]:
        profil.append("soutien naturel de Vénus")

    if signe_slug in ["sagittaire", "poissons"]:
        profil.append("soutien naturel de Jupiter")

    if signe_slug == "cancer":
        profil.append("forte affinité avec les qualités lunaires, intimes et protectrices")

    # Raffinement Nœuds / Luminaires / hiérarchie aspects
    for a in aspects_pof:
        # Nœud Sud
        if a["with"] in ["Nœud Sud", "Ketu", "Noeud Sud"]:
            profil.append("talent ancien ou facilité déjà connue, dont il faut apprendre à ne pas dépendre")

        # Nœud Nord
        elif a["with"] in ["Nœud Nord", "Rahu", "Noeud Nord"]:
            profil.append("potentiel de chance relié à l'évolution demandée dans cette vie")

        # Luminaires harmonieux
        if a["with"] in ["Soleil", "Lune"] and a["aspect"] in ["Trigone", "Sextile", "Conjonction"]:
            profil.append("harmonie forte entre les besoins profonds et la zone de fluidité karmique")

        # Hiérarchie générale des aspects
        if a["aspect"] == "Conjonction":
            profil.append(f"activation directe par {a['with']}")
        elif a["aspect"] == "Opposition":
            profil.append(f"activation par complémentarité avec {a['with']}")
        elif a["aspect"] in ("Trigone", "Sextile"):
            profil.append(f"soutien supplémentaire via {a['with']}")

    synthese = ""
    if profil:
        synthese = "Dynamique de la Part de Fortune : " + " ; ".join(profil) + "."

    # --------------------------------------------------
    # Aspects + BDD Part de Fortune
    # --------------------------------------------------
    aspects_lines: List[str] = []

    for a in aspects_pof:
        planet_slug = _slug(a["with"])       # ex: jupiter
        aspect_slug = _slug(a["aspect"])     # ex: conjonction, opposition, carre
        orb_txt = f" (orbe {a['orb']}°)" if a.get("orb") is not None else ""

        print("DEBUG POF BDD TEST =", ("part_de_fortune", planet_slug, aspect_slug))

        interp = get_karmique_interp(
            "part_de_fortune",
            planet_slug,
            aspect_slug
        )

        aspects_lines.append(f"**{a['aspect']} avec {a['with']}**{orb_txt}")

        if interp:
            print("DEBUG POF INTERP FOUND =", interp[:80])
            aspects_lines.append(interp.strip())
        else:
            print("DEBUG POF INTERP MISSING =", (planet_slug, aspect_slug))

        aspects_lines.append("")

    # --------------------------------------------------
    # Content brut pour le LLM
    # --------------------------------------------------
    content_parts: List[str] = []

    if synthese:
        content_parts.append(synthese)

    content_parts.append(f"PART DE FORTUNE : {signe} — Maison {maison}")
    if deg is not None:
        content_parts.append(f"DEGRE DANS LE SIGNE : {deg}°")

    if signe_illum and maison_illum is not None:
        content_parts.append(
            f"POINT D’ILLUMINATION : {signe_illum} — Maison {maison_illum}"
        )
        if deg_illum is not None:
            content_parts.append(f"DEGRE DU POINT D’ILLUMINATION : {deg_illum}°")

    if txt_maison:
        content_parts.append(f"POSITION EN MAISON :\n{txt_maison}")

    if txt_signe:
        content_parts.append(f"POSITION EN SIGNE :\n{txt_signe}")
    
    if signe_illum and maison_illum is not None:
        content_parts.append(
            "POINT D’ILLUMINATION : "
            "point opposé à la Part de Fortune ; "
            "voie plus intérieure, plus subtile, moins spontanée ; "
            "complément du talent ou de la fluidité indiqués par la Part de Fortune."
        )
    
    if txt_illum_maison:
        content_parts.append(f"POINT D’ILLUMINATION EN MAISON :\n{txt_illum_maison}")


    if aspects_lines:
        content_parts.append("ASPECTS DE LA PART DE FORTUNE :\n" + "\n".join(aspects_lines).strip())

    content = "\n\n".join([p for p in content_parts if p]).strip()

    logger.debug("POF | content built:\n%s", content)

    summary = summarize_chapter(
        chapter_title="Part de Fortune : la voie de fluidité karmique",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    print("DEBUG POF | return data point_illumination =", point_illumination)
    print("DEBUG POF | return data signe_illumination =", signe_illum)
    print("DEBUG POF | return data maison_illumination =", maison_illum)

    return {
        "id": "part_fortune",
        "title": "Part de Fortune : le point de résolution",
        "data": {
            "signe": signe,
            "maison": maison,
            "degre_dans_signe": deg,
            "point_illumination": point_illumination,
            "signe_illumination": signe_illum,
            "maison_illumination": maison_illum,
            "degre_illumination": deg_illum,
            "txt_illum_maison": txt_illum_maison,
            "aspects": aspects_pof,
            "synthese": synthese,
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


# --------------------------------------------------
# LLM interpretation
# --------------------------------------------------

def interpret_block_part_fortune_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    data = block.get("data", {}) or {}
    signe = data.get("signe")
    maison = data.get("maison")

    signe_illum = data.get("signe_illumination")
    maison_illum = data.get("maison_illumination")

    aspects_txt = "\n".join(
        f"{a['aspect']} avec {a['with']} (orbe {a['orb']}°)"
        for a in data.get("aspects", [])
    )

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    karmic_ctx = (global_ctx or {}).get("karmic_context", "").strip()
    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []
    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("part_fortune", "")

    # --------------------------------------------------
    # GESTION DYNAMIQUE DES RÈGLES ET DONNÉES
    # --------------------------------------------------
    regles_illumination = ""
    donnees_illumination = ""
    if signe_illum and maison_illum is not None:
        regles_illumination = "- Si le point d’illumination est disponible, mentionne-le comme un point opposé et complémentaire, indiquant une voie plus intérieure ou plus subtile d’approfondissement, sans en faire le centre du chapitre."
        donnees_illumination = f"Point d’Illumination : {signe_illum} (Maison {maison_illum})"

    regles_aspects = ""
    donnees_aspects = ""
    if aspects_txt.strip():
        regles_aspects = (
            "- Intègre l'aspect (Conjonction ou Opposition) dans ton récit.\n"
            "- INTERDICTION ABSOLUE de faire un résumé générique ou d'inventer. Tu dois réutiliser toute la richesse, les concepts précis et les mots forts de l'interprétation fournie dans les 'Données brutes' (ne dilue pas les détails !).\n"
            "- Tisse organiquement ces détails précis avec la signification de la Maison."
        )
        donnees_aspects = f"Aspects :\n{aspects_txt}"
    else:
        # L'ordre de verrouillage absolu
        regles_aspects = "- Ne fais AUCUNE mention des aspects planétaires. N'indique pas qu'ils sont absents. Ignore totalement ce point."

    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n".join(memories[-3:]) if memories else "aucune mémoire disponible"
    logger.debug("POF | memories_txt=%s", memories_txt)

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Tu rédiges le chapitre consacré à la Part de Fortune dans une analyse karmique déjà en cours.

TON ET STYLE
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Ce texte s’inscrit dans une analyse déjà commencée.
- Il est strictement interdit de commencer par le prénom.
- Il est strictement interdit de refaire une introduction générale.
- Ne fais jamais de commentaires méta sur la structure des données (ex: ne dis jamais "bien que non mentionnés").
- Style fluide, psychologique, incarné, lucide.

OBJECTIF
- Montrer la Part de Fortune comme un point de fluidité intérieure, de ressource instinctive, de refuge intime et de don karmique.
- Insister sur le fait que la maison est prioritaire : elle indique le domaine de vie où la personne retrouve un accord naturel avec elle-même.
- Le signe vient nuancer cette dynamique, sans être central.
- Montrer comment cette zone peut servir de levier pour sortir de schémas karmiques plus lourds.

RÈGLES DYNAMIQUES
- Tu ne fais pas un catalogue technique.
- Tu respectes la hiérarchie suivante : 1. Maison (prioritaire) 2. Aspects (s'ils existent) 3. Signe (secondaire).
{regles_illumination}
{regles_aspects}
- Tu ne sépares pas maison / signe / aspects de façon scolaire.
- Texte en flux continu uniquement.
- Aucun sous-titre. Aucune liste.
- Environ 300 à 380 mots.

CONTEXTE
- Axe karmique central : {axe_central}
- Thèmes déjà abordés : {themes_txt}
- Contexte global : {theme_brief}
- Contexte karmique : {karmic_ctx}

DONNÉES
Part de Fortune : {signe} (Maison {maison})
{donnees_illumination}
{donnees_aspects}
Contenu brut : 
{content}

[Analyse Part de Fortune en flux continu :]
""".strip()
    
    texte = (call_llm(prompt) or "").strip()
    logger.debug(
        "\n%s\nPROMPT PART DE FORTUNE\n%s\n%s\n%s",
        "=" * 80,
        "=" * 80,
        prompt,
        "=" * 80,
    )
    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte