from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from typing import Callable
import logging

logger = logging.getLogger(__name__)


# -------------------------
# Constantes
# -------------------------

PLANETES_LOURDES = {"Saturne", "Pluton", "Neptune", "Uranus"}
PLANETES_KARMIQUES = {"Saturne", "Pluton", "Chiron", "Lune Noire", "Nœud Nord", "Nœud Sud"}
LUMINAIRES = {"Soleil", "Lune"}
LUMINAIRE_HEAVY_ORB_LIMIT = 6.0
MAX_KARMIC_MARKERS_IN_PROMPT = 6



# -------------------------
# Helpers de base
# -------------------------

def _planet(theme: Dict[str, Any], name: str) -> Dict[str, Any]:
    return (theme.get("planetes") or {}).get(name, {}) or {}


def _get_signe(data: Dict[str, Any]) -> str:
    return str(data.get("signe") or "").strip()


def _get_maison(data: Dict[str, Any]) -> Any:
    return data.get("maison")


def _get_asc(theme: Dict[str, Any]) -> Dict[str, Any]:
    asc = theme.get("ascendant") or {}
    if asc:
        return asc

    angles = theme.get("angles") or {}
    if isinstance(angles, dict) and angles.get("Ascendant"):
        return angles.get("Ascendant") or {}

    logger.debug("Ascendant introuvable dans theme.ascendant et theme.angles")
    return {}

def _add_marker(markers: List[str], marker: str) -> None:
    marker = (marker or "").strip()
    if marker and marker not in markers:
        markers.append(marker)


# -------------------------
# Helpers aspects
# -------------------------

def _normalize_aspect_type(aspect: Dict[str, Any]) -> str:
    raw = str(aspect.get("type") or aspect.get("aspect") or "").strip().lower()

    mapping = {
        "conjunction": "conjonction",
        "conjonction": "conjonction",
        "square": "carré",
        "carre": "carré",
        "carré": "carré",
        "opposition": "opposition",
        "opposite": "opposition",
        "trine": "trigone",
        "trigone": "trigone",
        "sextile": "sextile",
    }
    return mapping.get(raw, raw)


def _aspect_planets(aspect: Dict[str, Any]) -> Tuple[str, str]:
    """
    Rend la lecture robuste selon les variantes possibles :
    - planete_1 / planete_2
    - planete1 / planete2
    - astre_1 / astre_2
    - astre1 / astre2
    """
    p1 = str(
        aspect.get("planete_1")
        or aspect.get("planete1")
        or aspect.get("astre_1")
        or aspect.get("astre1")
        or ""
    ).strip()

    p2 = str(
        aspect.get("planete_2")
        or aspect.get("planete2")
        or aspect.get("astre_2")
        or aspect.get("astre2")
        or ""
    ).strip()

    return p1, p2


# -------------------------
# Comptages
# -------------------------

def _count_signs(theme: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for _, data in (theme.get("planetes") or {}).items():
        signe = _get_signe(data)
        if not signe:
            continue
        counts[signe] = counts.get(signe, 0) + 1
    return counts


def _count_houses(theme: Dict[str, Any]) -> Dict[Any, int]:
    counts: Dict[Any, int] = {}
    for _, data in (theme.get("planetes") or {}).items():
        maison = _get_maison(data)
        if maison in [None, ""]:
            continue
        counts[maison] = counts.get(maison, 0) + 1
    return counts


def _extract_sign_dominants(theme: Dict[str, Any], min_count: int = 3) -> List[Dict[str, Any]]:
    sign_counts = _count_signs(theme)
    result = []

    for signe, count in sorted(sign_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= min_count:
            result.append({
                "signe": signe,
                "count": count,
            })

    return result


def _extract_house_dominants(theme: Dict[str, Any], min_count: int = 3) -> List[Dict[str, Any]]:
    """
    On passe à 3 par défaut pour éviter de surinterpréter
    une simple concentration modérée.
    """
    house_counts = _count_houses(theme)
    result = []

    for maison, count in sorted(house_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= min_count:
            result.append({
                "maison": maison,
                "count": count,
            })

    return result


# -------------------------
# Extraction karmique
# -------------------------

def _extract_luminaire_heavy_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    result = []

    for a in aspects:
        aspect_type = _normalize_aspect_type(a)
        if aspect_type not in {"conjonction", "carré", "opposition"}:
            continue

        try:
            orbe = float(a.get("orbe") or 999)
        except Exception:
            orbe = 999

        if orbe > LUMINAIRE_HEAVY_ORB_LIMIT:
            continue

        p1, p2 = _aspect_planets(a)

        if not p1 or not p2:
            continue

        if (
            (p1 in LUMINAIRES and p2 in PLANETES_LOURDES)
            or (p2 in LUMINAIRES and p1 in PLANETES_LOURDES)
        ):
            result.append({
                "planete_1": p1,
                "planete_2": p2,
                "type": aspect_type,
                "orbe": orbe,
            })

    return result


def _extract_karmic_markers(theme: Dict[str, Any]) -> List[str]:
    markers: List[str] = []

    # Planètes en maison 12
    for nom, data in (theme.get("planetes") or {}).items():
        if _get_maison(data) == 12:
            _add_marker(markers, f"{nom} en maison 12")

    # Planètes en maison 8
    for nom, data in (theme.get("planetes") or {}).items():
        if _get_maison(data) == 8:
            _add_marker(markers, f"{nom} en maison 8")

    # Planètes en maison 4
    for nom, data in (theme.get("planetes") or {}).items():
        if _get_maison(data) == 4:
            _add_marker(markers, f"{nom} en maison 4")

    # Marqueurs lourds
    for nom in ["Saturne", "Pluton", "Chiron", "Lune Noire"]:
        p = _planet(theme, nom)
        if p:
            signe = _get_signe(p)
            maison = _get_maison(p)
            _add_marker(markers, f"{nom} en {signe} maison {maison}")

    # Nœuds
    nn = _planet(theme, "Rahu") or _planet(theme, "Nœud Nord") or _planet(theme, "Noeud Nord")
    ns = _planet(theme, "Ketu") or _planet(theme, "Nœud Sud") or _planet(theme, "Noeud Sud")

    if nn:
        _add_marker(markers, f"Nœud Nord en {_get_signe(nn)} maison {_get_maison(nn)}")
    if ns:
        _add_marker(markers, f"Nœud Sud en {_get_signe(ns)} maison {_get_maison(ns)}")

    return markers


def _extract_identity_tone(theme: Dict[str, Any]) -> List[str]:
    tone: List[str] = []

    asc = _get_asc(theme)
    if asc:
        tone.append(f"Ascendant en {_get_signe(asc)}")

    soleil = _planet(theme, "Soleil")
    lune = _planet(theme, "Lune")
    pluton = _planet(theme, "Pluton")

    if soleil:
        tone.append(f"Soleil en {_get_signe(soleil)} maison {_get_maison(soleil)}")
    if lune:
        tone.append(f"Lune en {_get_signe(lune)} maison {_get_maison(lune)}")
    if pluton:
        tone.append(f"Pluton en {_get_signe(pluton)} maison {_get_maison(pluton)}")

    return tone


def _extract_global_tension_points(theme: Dict[str, Any]) -> List[str]:
    """
    Bloc plus synthétique : ce qui donne immédiatement la couleur du thème,
    sans déjà raconter tout le détail des chapitres suivants.
    """
    tensions: List[str] = []

    sign_dominants = _extract_sign_dominants(theme, min_count=3)
    house_dominants = _extract_house_dominants(theme, min_count=3)
    luminaire_heavy_aspects = _extract_luminaire_heavy_aspects(theme)

    if sign_dominants:
        tensions.append(
            "dominante(s) de signe : " +
            ", ".join(f"{x['signe']} ({x['count']})" for x in sign_dominants)
        )

    if house_dominants:
        tensions.append(
            "dominante(s) de maison : " +
            ", ".join(f"maison {x['maison']} ({x['count']})" for x in house_dominants)
        )

    if luminaire_heavy_aspects:
        tensions.append(
            "tensions majeures sur les luminaires : " +
            ", ".join(
                f"{a['planete_1']} {a['type']} {a['planete_2']}"
                for a in luminaire_heavy_aspects[:4]
            )
        )

    return tensions


# -------------------------
# Construction du bloc
# -------------------------

def build_block_resume_karmique_global(
    theme: Dict[str, Any],
    score: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    identity_tone = _extract_identity_tone(theme)
    sign_dominants = _extract_sign_dominants(theme)
    house_dominants = _extract_house_dominants(theme)
    luminaire_heavy_aspects = _extract_luminaire_heavy_aspects(theme)
    karmic_markers = _extract_karmic_markers(theme)
    global_tension_points = _extract_global_tension_points(theme)

    # Important :
    # content = version synthétique, destinée au prompt d’introduction
    # data = version riche, exploitable plus tard si besoin
    content_parts: List[str] = []

    if identity_tone:
        content_parts.append("Tonalité identitaire : " + ", ".join(identity_tone))

    if global_tension_points:
        content_parts.append("Climat global : " + " ; ".join(global_tension_points))

    if karmic_markers:
        content_parts.append(
            "Marqueurs karmiques principaux : "
            + ", ".join(karmic_markers[:MAX_KARMIC_MARKERS_IN_PROMPT])
        )

    return {
        "key": "resume_karmique_global",
        "title": "Climat karmique d’incarnation",
        "content": "\n\n".join(content_parts).strip(),
        "data": {
            "identity_tone": identity_tone,
            "sign_dominants": sign_dominants,
            "house_dominants": house_dominants,
            "luminaire_heavy_aspects": luminaire_heavy_aspects,
            "karmic_markers": karmic_markers,
            "global_tension_points": global_tension_points,
        },
        "score_impact": 0,
    }





def interpret_block_resume_karmique_global_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Optional[Dict[str, Any]] = None,
    call_llm: Optional[Callable[[str], str]] = None,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    
    global_ctx = global_ctx or {}

    content = (block.get("content") or "").strip()
    data = block.get("data", {}) or {}

    if not content or not call_llm:
        return content

    # Données structurantes
    identity_tone = data.get("identity_tone", [])
    global_tension_points = data.get("global_tension_points", [])
    karmic_markers = data.get("karmic_markers", [])

    identity_txt = ", ".join(identity_tone)
    tensions_txt = "; ".join(global_tension_points)
    markers_txt = ", ".join(karmic_markers[:MAX_KARMIC_MARKERS_IN_PROMPT])
    genre_label = global_ctx.get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.

Tu rédiges le chapitre d'ouverture : "Climat karmique d’incarnation".

OBJECTIF
- Poser la tonalité globale du thème.
- Donner une lecture claire de la dynamique centrale de l’âme.
- Mettre en évidence les grandes tensions et le type de fonctionnement psychique.
- Donner une sensation de cohérence globale.

IMPORTANT
- Tu ne dois PAS analyser chaque élément en détail (pas de zoom sur Chiron, Saturne, etc.).
- Tu ne dois PAS faire une liste d’interprétations.
- Tu ne dois PAS spoiler les chapitres suivants.
- Tu restes global, synthétique, structurant.

STYLE
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Ton profond, lucide, incarné
- Pas de blabla, pas de phrases creuses
- Pas de listes
- Flux continu
- Environ 180 à 250 mots

DONNÉES DU THÈME

Tonalité identitaire :
{identity_txt}

Climat global :
{tensions_txt}

Marqueurs karmiques principaux :
{markers_txt}

INSTRUCTION CLÉ

Tu dois répondre à cette question implicite :
👉 "Quel type de terrain psychique et karmique cette personne habite-t-elle ?"

Tu décris :
- la dynamique dominante (intensité, contrôle, fuite, dépendance, etc.)
- le type de tension intérieure
- la manière dont la personne entre dans la vie et vit ses expériences
- la logique globale du thème

Tu ne détailles pas les causes.
Tu poses le décor.

[Texte :]
"""

    try:
        response = call_llm(prompt)
        return response.strip() if isinstance(response, str) and response.strip() else content
    except Exception:
        logger.exception("Erreur LLM dans interpret_block_resume_karmique_global_llm")
        return content