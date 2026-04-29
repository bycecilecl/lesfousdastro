from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import logging

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

SIGNS = [
    "Bélier", "Taureau", "Gémeaux", "Cancer",
    "Lion", "Vierge", "Balance", "Scorpion",
    "Sagittaire", "Capricorne", "Verseau", "Poissons"
]

ANGLES = {"Ascendant", "Descendant", "MC", "FC", "Fond du Ciel", "Milieu du Ciel"}
MIDPOINT_TARGETS = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter",
    "Saturne", "Uranus", "Neptune", "Pluton",
    "Ascendant", "Descendant", "MC", "FC",
    "Lune Noire", "Chiron", "Rahu", "Ketu", "Nœud Nord", "Nœud Sud",
    "Noeud Nord", "Noeud Sud", "Part de Fortune"
}

VALID_POINTS = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
    "Chiron", "Lune Noire",
    "Nœud Nord", "Nœud Sud",
    "Ascendant", "Descendant", "MC", "FC",
    "Part de Fortune"
}


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


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _sign_to_offset(sign: str) -> Optional[int]:
    if sign not in SIGNS:
        return None
    return SIGNS.index(sign) * 30


def _longitude_from_position(position: Dict[str, Any]) -> Optional[float]:
    """
    Attend un dict du type:
    {
        "signe": "Scorpion",
        "degre_dans_signe": 12.34
    }
    """
    if not isinstance(position, dict):
        return None

    sign = position.get("signe")
    deg = _safe_float(position.get("degre_dans_signe"))
    sign_offset = _sign_to_offset(sign)

    if sign_offset is None or deg is None:
        return None

    return sign_offset + deg


def _normalize_deg360(x: float) -> float:
    return x % 360.0


def _midpoint_deg(a: float, b: float) -> float:
    """
    Calcule le vrai mi-point sur un cercle.
    """
    a = _normalize_deg360(a)
    b = _normalize_deg360(b)
    diff = (b - a) % 360.0
    return _normalize_deg360(a + diff / 2.0)


def _deg_to_sign_house_style(deg360: float) -> Dict[str, Any]:
    deg360 = _normalize_deg360(deg360)
    sign_index = int(deg360 // 30)
    sign = SIGNS[sign_index]
    deg_in_sign = round(deg360 - sign_index * 30, 2)
    return {
        "signe": sign,
        "degre_dans_signe": deg_in_sign,
    }


def _angular_distance(a: float, b: float) -> float:
    diff = abs((a - b) % 360.0)
    return min(diff, 360.0 - diff)


def _get_house_from_longitude(theme: Dict[str, Any], longitude: float) -> Optional[int]:
    """
    Assigne une maison à partir des cuspides.
    Accepte :
    - theme["cusps"] = liste
    - theme["cuspides"] = liste
    - theme["cuspides"] = dict {1: ..., 2: ..., ..., 12: ...}
    """

    raw_cusps = theme.get("cusps")
    raw_cuspides = theme.get("cuspides")
    raw_maisons = theme.get("maisons")
    raw_houses = theme.get("houses")

    source = raw_cusps or raw_cuspides or raw_maisons or raw_houses

    if not source:
        logger.debug("_get_house_from_longitude -> aucune cuspide")
        return None

    # Si dict {1: ..., 2: ...}
    # Si dict {1: ...} ou {"1": ...} ou {"Maison 1": ...}
    if isinstance(source, dict):
        ordered = []
        for i in range(1, 13):
            if i in source:
                ordered.append(source[i])
            elif str(i) in source:
                ordered.append(source[str(i)])
            elif f"Maison {i}" in source:
                ordered.append(source[f"Maison {i}"])
            else:
                logger.debug("Cuspide manquante pour maison %s", i)
                return None
        source = ordered

    if not isinstance(source, list) or len(source) < 12:
        logger.debug("_get_house_from_longitude -> format cuspides invalide")
        return None

    cusp_lons: List[float] = []

    for c in source[:12]:
        if isinstance(c, (int, float)):
            cusp_lons.append(float(c) % 360.0)

        elif isinstance(c, dict):
            lon = _longitude_from_position(c)
            if lon is None:
                logger.debug("Impossible de convertir cuspide dict: %s", c)
                return None
            cusp_lons.append(lon % 360.0)

        else:
            logger.debug("Format cuspide non géré: %s", c)
            return None

    logger.debug("Cuspides longitudes normalisées: %s", cusp_lons)

    x = longitude % 360.0

    for i in range(12):
        start = cusp_lons[i]
        end = cusp_lons[(i + 1) % 12]

        if start < end:
            if start <= x < end:
                logger.debug("Maison trouvée = %s", i + 1)
                return i + 1
        else:
            # passage 360 -> 0
            if x >= start or x < end:
                logger.debug("Maison trouvée = %s", i + 1)
                return i + 1

    logger.debug("_get_house_from_longitude -> aucune maison trouvée après boucle")
    return None


def _normalize_point_name(name: str) -> str:
    mapping = {
        "Noeud Nord": "Nœud Nord",
        "Noeud Sud": "Nœud Sud",
        "Rahu": "Nœud Nord",
        "Ketu": "Nœud Sud",
        "Fond du Ciel": "FC",
        "Milieu du Ciel": "MC",
    }
    return mapping.get(name, name)


def _collect_midpoint_hits(
    theme: Dict[str, Any],
    midpoint_lon: float,
    opposite_lon: float,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Cherche les objets proches du mi-point et du point opposé.
    Orbes :
    - planètes rapides / angles / points personnels karmiques : 6°
    - lentes : 4°
    """
    planets = theme.get("planetes") or {}
    if not isinstance(planets, dict):
        return {"midpoint": [], "opposite": []}

    slow_planets = {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}

    hits_mid: List[Dict[str, Any]] = []
    hits_opp: List[Dict[str, Any]] = []

    for name, pos in planets.items():
        if name not in MIDPOINT_TARGETS:
            continue

        lon = _longitude_from_position(pos if isinstance(pos, dict) else {})
        if lon is None:
            continue

        norm_name = _normalize_point_name(str(name))
        if norm_name in {"Ascendant", "Descendant", "MC", "FC"}:
            orb_limit = 2.0
        elif norm_name in slow_planets:
            orb_limit = 2.0
        else:
            orb_limit = 3.0

        d_mid = _angular_distance(midpoint_lon, lon)
        d_opp = _angular_distance(opposite_lon, lon)

        if d_mid > orb_limit and d_opp > orb_limit:
            continue

        maison_obj = pos.get("maison")
        maison_obj_txt = maison_obj if maison_obj is not None else "non déterminée"

        item = {
            "name": norm_name,
            "signe": pos.get("signe"),
            "maison": maison_obj_txt,
            "degre_dans_signe": pos.get("degre_dans_signe"),
        }

        if d_mid <= orb_limit:
            hit = dict(item)
            hit["orb"] = round(d_mid, 2)
            hits_mid.append(hit)

        if d_opp <= orb_limit:
            hit = dict(item)
            hit["orb"] = round(d_opp, 2)
            hits_opp.append(hit)

    hits_mid.sort(key=lambda x: x["orb"])
    hits_opp.sort(key=lambda x: x["orb"])

    return {"midpoint": hits_mid, "opposite": hits_opp}


def _collect_aspects_to_planet(theme: Dict[str, Any], planet_name: str) -> Dict[str, List[Dict[str, Any]]]:
    aspects = theme.get("aspects") or []
    if not isinstance(aspects, list):
        return {"hard": [], "soft": [], "neutral": []}

    hard_names = {"Carré", "Opposition", "Quinconce", "Sesqui-carré"}
    soft_names = {"Trigone", "Sextile"}
    neutral_names = {"Conjonction"}

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

    hard: List[Dict[str, Any]] = []
    soft: List[Dict[str, Any]] = []
    neutral: List[Dict[str, Any]] = []

    for a in aspects:
        if not isinstance(a, dict):
            continue

        p1 = a.get("planete1")
        p2 = a.get("planete2")
        if p1 != planet_name and p2 != planet_name:
            continue

        other = p2 if p1 == planet_name else p1

        other = _normalize_point_name(str(other))

        if other not in VALID_POINTS:
            continue

        aspect_name = _norm_aspect_name(a.get("aspect"))
        orb = _safe_float(a.get("orbe"))

        item = {
            "with": _normalize_point_name(str(other)),
            "aspect": aspect_name,
            "orb": round(orb, 2) if orb is not None else None,
        }

        if aspect_name in hard_names:
            hard.append(item)
        elif aspect_name in soft_names:
            soft.append(item)
        elif aspect_name in neutral_names:
            neutral.append(item)

    hard.sort(key=lambda x: x["orb"] if x["orb"] is not None else 99)
    soft.sort(key=lambda x: x["orb"] if x["orb"] is not None else 99)
    neutral.sort(key=lambda x: x["orb"] if x["orb"] is not None else 99)

    return {"hard": hard, "soft": soft, "neutral": neutral}


def _bdd(astre: str, donnee: str, valeur: Any) -> str:
    if valeur is None:
        return ""
    txt = get_karmique_interp(astre, donnee, str(valeur))
    return txt.strip() if isinstance(txt, str) and txt.strip() else ""


# --------------------------------------------------
# Build block
# --------------------------------------------------

def build_block_saturne_pluton(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
 
    planets = theme.get("planetes") or {}
    saturne = planets.get("Saturne") if isinstance(planets.get("Saturne"), dict) else {}
    pluton = planets.get("Pluton") if isinstance(planets.get("Pluton"), dict) else {}

    if not saturne or not pluton:
        return None

    saturne_lon = _longitude_from_position(saturne)
    pluton_lon = _longitude_from_position(pluton)

    if saturne_lon is None or pluton_lon is None:
        return None

    # Saturne
    saturne_sign = saturne.get("signe")
    saturne_house = saturne.get("maison")
    saturne_retro = bool(saturne.get("retrograde"))
    saturne_aspects = _collect_aspects_to_planet(theme, "Saturne")
    saturne_sign_txt = _bdd("Saturne", "signe", _slug(saturne_sign))
    saturne_house_txt = _bdd("Saturne", "maison", saturne_house)

    # Pluton
    pluton_sign = pluton.get("signe")
    pluton_house = pluton.get("maison")
    pluton_aspects = _collect_aspects_to_planet(theme, "Pluton")
    pluton_house_txt = _bdd("Pluton", "maison", pluton_house)

    # Mi-point
    midpoint_lon = _midpoint_deg(saturne_lon, pluton_lon)
    opposite_lon = _normalize_deg360(midpoint_lon + 180.0)

    midpoint_pos = _deg_to_sign_house_style(midpoint_lon)
    opposite_pos = _deg_to_sign_house_style(opposite_lon)

    midpoint_house = _get_house_from_longitude(theme, midpoint_lon)
    opposite_house = _get_house_from_longitude(theme, opposite_lon)

    midpoint_house_txt = midpoint_house if midpoint_house is not None else "non déterminée"
    opposite_house_txt = opposite_house if opposite_house is not None else "non déterminée"

    midpoint_hits = _collect_midpoint_hits(theme, midpoint_lon, opposite_lon)



    # Contenu brut envoyé au LLM
    lines: List[str] = []

    lines.append(f"SATURNE : {saturne_sign} — Maison {saturne_house}")
    lines.append(f"SATURNE RETROGRADE : {'oui' if saturne_retro else 'non'}")
    if saturne_sign_txt:
        lines.append(f"SATURNE SIGNE BDD : {saturne_sign_txt}")
    if saturne_house_txt:
        lines.append(f"SATURNE MAISON BDD : {saturne_house_txt}")

    if saturne_aspects["hard"]:
        for a in saturne_aspects["hard"]:
            lines.append(
                f"SATURNE ASPECT DISSONANT : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )
    if saturne_aspects["neutral"]:
        for a in saturne_aspects["neutral"]:
            lines.append(
                f"SATURNE CONJONCTION : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )
    if saturne_aspects["soft"]:
        for a in saturne_aspects["soft"]:
            lines.append(
                f"SATURNE ASPECT BENEFIQUE : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )

    lines.append("")
    lines.append(f"PLUTON : {pluton_sign} — Maison {pluton_house}")
    if pluton_house_txt:
        lines.append(f"PLUTON MAISON BDD : {pluton_house_txt}")

    if pluton_aspects["hard"]:
        for a in pluton_aspects["hard"]:
            lines.append(
                f"PLUTON ASPECT DISSONANT : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )
    if pluton_aspects["neutral"]:
        for a in pluton_aspects["neutral"]:
            lines.append(
                f"PLUTON CONJONCTION : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )
    if pluton_aspects["soft"]:
        for a in pluton_aspects["soft"]:
            lines.append(
                f"PLUTON ASPECT BENEFIQUE : {a['aspect']} avec {a['with']} "
                f"(orbe {a['orb']}°)"
            )

    lines.append("")
    lines.append(
        f"MI-POINT SATURNE-PLUTON : {midpoint_pos['signe']} "
        f"{midpoint_pos['degre_dans_signe']}° — Maison {midpoint_house_txt}"
    )
    lines.append(
        f"POINT OPPOSE AU MI-POINT : {opposite_pos['signe']} "
        f"{opposite_pos['degre_dans_signe']}° — Maison {opposite_house_txt}"
    )

    if midpoint_hits["midpoint"]:
        for h in midpoint_hits["midpoint"]:
            lines.append(
                f"OBJET SUR MI-POINT : {h['name']} en {h.get('signe')} "
                f"(Maison {h.get('maison')}) orb {h['orb']}°"
            )

    if midpoint_hits["opposite"]:
        for h in midpoint_hits["opposite"]:
            lines.append(
                f"OBJET SUR POINT OPPOSE : {h['name']} en {h.get('signe')} "
                f"(Maison {h.get('maison')}) orb {h['orb']}°"
            )

    content = _join(lines)

    summary = summarize_chapter(
        chapter_title="Saturne – Pluton : compression karmique et point de résolution",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    return {
        "id": "saturne_pluton",
        "title": "Saturne – Pluton : le noyau karmique",
        "data": {
            "saturne": {
                "signe": saturne_sign,
                "maison": saturne_house,
                "retrograde": saturne_retro,
                "aspects_hard": saturne_aspects["hard"],
                "aspects_soft": saturne_aspects["soft"],
                "aspects_neutral": saturne_aspects["neutral"],
            },
            "pluton": {
                "signe": pluton_sign,
                "maison": pluton_house,
                "aspects_hard": pluton_aspects["hard"],
                "aspects_soft": pluton_aspects["soft"],
                "aspects_neutral": pluton_aspects["neutral"],
            },
            "midpoint": {
                "longitude": round(midpoint_lon, 2),
                "signe": midpoint_pos["signe"],
                "degre_dans_signe": midpoint_pos["degre_dans_signe"],
                "maison": midpoint_house_txt,
                "hits": midpoint_hits["midpoint"],
            },
            "opposite_midpoint": {
                "longitude": round(opposite_lon, 2),
                "signe": opposite_pos["signe"],
                "degre_dans_signe": opposite_pos["degre_dans_signe"],
                "maison": opposite_house_txt,
                "hits": midpoint_hits["opposite"],
            },
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


# --------------------------------------------------
# LLM interpretation
# --------------------------------------------------

def interpret_block_saturne_pluton_llm(
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
    saturne = data.get("saturne", {}) or {}
    pluton = data.get("pluton", {}) or {}
    midpoint = data.get("midpoint", {}) or {}
    opposite_midpoint = data.get("opposite_midpoint", {}) or {}

    saturne_retro = bool(saturne.get("retrograde"))

    saturne_retro_instruction = (
        "- Saturne est rétrograde : insiste sur l'intériorisation de la loi, la dette d'autorité, "
        "la difficulté à se sentir légitime face au temps, au père, aux cadres ou à la responsabilité. "
        "Présente cela comme une maturation intérieure lente, pas comme une punition.\n"
        if saturne_retro else
        "- Saturne n'est pas rétrograde : analyse surtout la confrontation concrète au réel, aux limites, "
        "aux responsabilités visibles et aux structures extérieures.\n"
    )

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    memoires_contextuelles = (global_ctx or {}).get("memoires_contextuelles", []) or []
    memories_txt = "\n\n".join(memoires_contextuelles[-6:]) if memoires_contextuelles else "aucune mémoire disponible"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("saturne_pluton", "")

    # 1) Analyse commune Saturne + Pluton
    prompt_saturne_pluton = f"""
Tu es expert en astrologie karmique et psychologue jungien. Tu rédiges la section principale du noyau karmique, couvrant Saturne et Pluton.

**TON ET STYLE**
- Tutoiement direct à {genre_txt}.
- Adresse-toi uniquement à la personne avec "tu".
- INTERDICTION ABSOLUE d'utiliser le prénom, "il", "elle", ou une formulation en troisième personne.
- Style dense, lucide, psychologique et incarné.
- Écris de manière directe et affirmée.
- Préfère les formulations concrètes plutôt que prudentes ou théoriques.
- Évite les tournures trop douces ou abstraites.
- Pas d'introduction générique. Entre directement dans le vif du sujet.

**STRUCTURE ATTENDUE**
Deux mouvements enchaînés en flux continu, sans titre ni liste :
1. Saturne en Maison {saturne.get('maison')} : la forge, l'exigence, la maturation consciente.
2. Pluton en Maison {pluton.get('maison')} : la purge, l'ombre, l'alchimie viscérale.

La transition entre les deux doit être fluide et organique : Pluton vient creuser là où Saturne structure.

**RÈGLES STRICTES**
{saturne_retro_instruction}
- Tu ne mentionnes QUE les données fournies ci-dessous. Aucune donnée inventée ou déduite.
- Intègre les signes, maisons et aspects de façon naturelle, sans liste technique.
- Pour Saturne : insiste sur structure, principe de réalité, maturation, responsabilité, fondation.
- Pour Pluton : insiste sur purge, instinct, viscéral, mue, transmutation, puissance souterraine.
- Ne parle pas de Pluton en signe comme si c'était central : c'est générationnel. Priorité à la maison et aux aspects.
- INTERDICTION ABSOLUE d’utiliser les mots "transformation", "transformer", "crise", "crises".
- INTERDICTION de faire référence explicite à une section précédente : pas de "comme évoqué", "déjà mentionné", "vu plus haut".
- Format brut : flux continu uniquement. Aucun sous-titre, aucune liste.
- Longueur : 3 paragraphes denses au total, environ 280 à 330 mots.

**MÉMOIRE DE RÉDACTION**
{memories_txt}

**CONSIGNE ANTI-REDONDANCE**
- INTERDICTION de ré-expliquer les concepts déjà dans la mémoire ci-dessus.
- Si un thème a déjà été abordé, montre seulement comment Saturne le structure ou comment Pluton le purifie, sans le répéter.

**DONNÉES TECHNIQUES**
Axe central : {axe_central}
Contexte global : {theme_brief}

{content}

[Analyse Saturne puis Pluton en flux continu :]
""".strip()

    texte_saturne_pluton = (call_llm(prompt_saturne_pluton) or "").strip()

    # 2) Synthèse Saturne + Pluton + mi-point
    hits_mid = midpoint.get("hits", [])
    hits_opp = opposite_midpoint.get("hits", [])

    donnees_hits = ""
    regles_hits = ""

    if hits_mid or hits_opp:
        if hits_mid:
            noms_mid = ", ".join([f"{h['name']} (orbe {h['orb']}°)" for h in hits_mid])
            donnees_hits += f"Objets présents sur le mi-point : {noms_mid}.\n"

        if hits_opp:
            noms_opp = ", ".join([f"{h['name']} (orbe {h['orb']}°)" for h in hits_opp])
            donnees_hits += f"Objets présents sur le point opposé : {noms_opp}.\n"

        regles_hits = "- Intègre explicitement les objets présents sur cet axe comme des leviers karmiques majeurs."
    else:
        regles_hits = "- N'évoque jamais l'absence d'objets, de planètes ou d'activation. Analyse directement l'axe signe/maison."

    mid_house_txt = midpoint.get("maison") or "non déterminée"
    opp_house_txt = opposite_midpoint.get("maison") or "non déterminée"

    prompt_midpoint = f"""
Tu es expert en astrologie karmique et psychologue jungien. Tu termines ce chapitre en réalisant la synthèse entre Saturne et Pluton à travers leur mi-point.

**TON ET STYLE**
- Tutoiement direct à {genre_txt}.
- Adresse-toi uniquement à la personne avec "tu".
- INTERDICTION ABSOLUE d'utiliser le prénom, "il", "elle", ou une formulation en troisième personne.
- Style direct, structuré, incarné.
- Va au fond du mécanisme psychique sans langage flou.
- Entre directement dans la synthèse et le point de jonction.
- Interdiction stricte de recommencer à analyser Saturne et Pluton séparément.

**OBJECTIF DU CHAPITRE**
Mettre en lumière le point de jonction entre l'effort saturnien et la purge plutonienne :
- Montrer où l'effort rencontre la mue.
- Montrer comment la structure sert de cadre à la purge.
- Montrer comment la purge empêche la structure de se scléroser.
- Analyser l'axe du mi-point Maison {mid_house_txt} / Maison {opp_house_txt} comme un levier de régulation, de résilience et de résolution.
- Ne repars pas dans une analyse de Pluton, de l'ombre ou des blessures. Cette partie doit uniquement faire la jonction dynamique.

**MÉMOIRE DE RÉDACTION**
{memories_txt}

**CONSIGNE ANTI-REDONDANCE**
- Ne répète pas ce que tu viens de dire ou ce qui est dans la mémoire.
- Fais uniquement la synthèse du point de jonction.

**RÈGLES STRICTES**
{regles_hits}
- S'il y a des objets sur le mi-point ou l'opposé, explique concrètement que cette fonction psychique agit comme détonateur, soupape ou levier de résolution.
- INTERDICTION ABSOLUE d’utiliser les mots "transformation", "transformer", "crise", "crises".
- Format brut : texte en flux continu uniquement. Aucun sous-titre, aucune liste.
- Longueur : 1 paragraphe dense, environ 120 à 160 mots.

**DONNÉES TECHNIQUES**
Axe central : {axe_central}
Contexte global : {theme_brief}

Mi-point Saturne/Pluton : {midpoint.get('signe')} {midpoint.get('degre_dans_signe')}° Maison {mid_house_txt}
Point opposé : {opposite_midpoint.get('signe')} {opposite_midpoint.get('degre_dans_signe')}° Maison {opp_house_txt}
Objets touchés : {donnees_hits}

[Synthèse Saturne-Pluton et mi-point en flux continu :]
""".strip()

    texte_midpoint = (call_llm(prompt_midpoint) or "").strip()

    final_text = "\n\n".join([
        texte_saturne_pluton.strip(),
        texte_midpoint.strip(),
    ])

    if intro_txt:
        return f"{intro_txt}\n\n{final_text}".strip()
    return final_text
