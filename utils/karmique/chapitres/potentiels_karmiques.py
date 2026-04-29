from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
import logging

from utils.forces_defis import generer_forces_defis
from utils.placements_occ import build_resume_occidental
from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs

logger = logging.getLogger(__name__)


# ─── helpers internes ────────────────────────────────────────────────────────

def _signe_of(p: Dict[str, Any]) -> str:
    return str(p.get("signe") or "").strip()


def _maison_of(p: Dict[str, Any]) -> Any:
    return p.get("maison")


def _orb_sort_value(item: Dict[str, Any]) -> float:
    try:
        return float(item.get("orbe") or 999)
    except Exception:
        return 999.0


def _build_theme_full_context(theme: Dict[str, Any], score: Optional[Dict[str, Any]] = None) -> str:
    """Vue lisible du thème complet pour le LLM."""
    lignes = []

    asc = theme.get("ascendant") or {}
    if asc:
        lignes.append(f"Ascendant : {asc.get('signe', '?')}")

    planetes = theme.get("planetes") or {}
    if planetes:
        lignes.append("Placements :")
        ordre = [
            "Soleil", "Lune", "Mercure", "Vénus", "Mars",
            "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
            "Chiron", "Lune Noire", "Nœud Nord", "Nœud Sud",
        ]
        for nom in ordre:
            p = planetes.get(nom)
            if not p:
                continue
            signe = p.get("signe", "?")
            maison = p.get("maison", "?")
            degre = p.get("degre")
            suffix = f" ({degre}°)" if degre is not None else ""
            lignes.append(f"- {nom} en {signe} maison {maison}{suffix}")

    aspects = theme.get("aspects") or []
    aspects_filtres = []
    allowed_points = {
        "Ascendant", "Soleil", "Lune", "Mercure", "Vénus", "Mars",
        "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
        "Chiron", "Lune Noire", "Rahu", "Ketu", "Nœud Nord", "Nœud Sud",
    }
    types_retenus = {"conjonction", "conjunction", "carré", "carre", "opposition", "trigone", "sextile"}

    for a in aspects:
        t = str(a.get("type") or a.get("aspect") or "").strip().lower()
        if t not in types_retenus:
            continue
        try:
            if float(a.get("orbe") or 0) > 6:
                continue
        except Exception:
            pass

        p1 = a.get("planete_1") or a.get("planete1") or a.get("astre_1") or a.get("source") or ""
        p2 = a.get("planete_2") or a.get("planete2") or a.get("astre_2") or a.get("cible") or ""
        if p1 not in allowed_points or p2 not in allowed_points:
            continue
        aspects_filtres.append(a)

    aspects_filtres.sort(key=_orb_sort_value)

    if aspects_filtres:
        nb_tensions = sum(
            1 for a in aspects_filtres
            if str(a.get("type") or a.get("aspect") or "").strip().lower() in {"carré", "carre", "opposition"}
        )
        nb_harmoniques = sum(
            1 for a in aspects_filtres
            if str(a.get("type") or a.get("aspect") or "").strip().lower() in {"trigone", "sextile"}
        )
        lignes.append(
            f"Polarité : {nb_tensions} aspects de tension / {nb_harmoniques} harmoniques (orbe ≤ 6°)"
        )
        lignes.append("Aspects majeurs :")
        for a in aspects_filtres[:15]:
            p1 = a.get("planete_1") or a.get("planete1") or a.get("astre_1") or a.get("source") or "?"
            p2 = a.get("planete_2") or a.get("planete2") or a.get("astre_2") or a.get("cible") or "?"
            t = a.get("type") or a.get("aspect") or "?"
            orbe = a.get("orbe")
            suffix = f" (orbe {orbe})" if orbe is not None else ""
            lignes.append(f"- {p1} {t} {p2}{suffix}")

    return "\n".join(lignes).strip()


# ─── build block ─────────────────────────────────────────────────────────────

def build_block_potentiels_karmiques(
    theme: Dict[str, Any],
    score: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    forces_defis = generer_forces_defis(theme)

    points_forts = theme.get("points_forts") or []
    if isinstance(points_forts, dict):
        pf_list = []
        for v in points_forts.values():
            if isinstance(v, list):
                pf_list.extend(v)
        points_forts = pf_list

    axes_majeurs = organiser_points_forts(points_forts)
    axes_majeurs_txt = formater_axes_majeurs(axes_majeurs)

    resume_occidental = build_resume_occidental(theme, orbe_max=6.0, max_aspects=999)
    theme_full_context = _build_theme_full_context(theme, score)

    return {
        "key": "potentiels_karmiques",
        "title": "Ressources et potentiels d'incarnation",
        "content": axes_majeurs_txt,
        "data": {
            "theme_full_context": theme_full_context,
            "resume_occidental": resume_occidental,
            "axes_majeurs_txt": axes_majeurs_txt,
            "forces_defis": forces_defis,
        },
        "score_impact": 0,
    }


# ─── interprétation LLM ──────────────────────────────────────────────────────

def interpret_block_potentiels_karmiques_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:

    global_ctx = global_ctx or {}

    # contexte narratif
    theme_brief = global_ctx.get("theme_brief", "").strip()
    axe_central = global_ctx.get("axe_karmique_central", "").strip()
    genre_label = global_ctx.get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    # mémoire et blocages déjà abordés
    tensions_txt = "\n".join(
        f"- {t}" for t in (global_ctx.get("global_tension_points") or [])
    ) or "Aucune tension signalée."

    memoires = global_ctx.get("memoires_contextuelles") or []
    memories_txt = "\n\n".join(memoires[-9:]) if memoires else "Aucune mémoire disponible."

    themes_abordes = global_ctx.get("themes_abordes") or []
    themes_txt = "\n".join(f"- {t}" for t in themes_abordes) if themes_abordes else "Aucun thème préalable."

    # données du bloc
    data = block.get("data", {}) or {}
    theme_full_context = data.get("theme_full_context", "")
    resume_occidental = data.get("resume_occidental", "")
    axes_majeurs_txt = data.get("axes_majeurs_txt", "")
    forces_defis = data.get("forces_defis", {}) or {}
    forces_txt = ", ".join((forces_defis.get("forces") or [])[:8])
    synthese_forces = forces_defis.get("synthese_courte", "")

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique jungienne.
Tu rédiges le chapitre "Ressources et potentiels d'incarnation".

GENRE : {genre_txt} — tutoiement direct. Jamais de prénom, jamais "il" ou "elle".

━━━ CE QUI A DÉJÀ ÉTÉ DIT DANS LE RAPPORT ━━━

Thèmes abordés :
{themes_txt}

Blocages et blessures déjà explorés :
{tensions_txt}

Mémoire narrative (extraits des chapitres précédents) :
{memories_txt}

━━━ LE THÈME ━━━

Axe central : {axe_central}

Résumé du thème : {theme_brief}

Thème complet :
{theme_full_context}

Résumé occidental complet :
{resume_occidental}

━━━ POINTS FORTS ET GRANDS AXES (par ordre d'importance) ━━━

{axes_majeurs_txt}

Forces repérées : {forces_txt}
Synthèse : {synthese_forces}

━━━ TA MISSION ━━━

À partir des points forts et grands axes ci-dessus, identifie 3 à 4 ressources réellement structurantes pour ce thème.

Chaque ressource doit répondre à un blocage ou une blessure déjà nommé dans ce rapport.
Explique le mécanisme psychologique profond : comment cette ressource compense, contient ou transforme ce qui a été identifié comme blessure ou tension.

Règles absolues :
- Pas d'inventaire. Pas de liste planète par planète.
- Pas d'introduction méta sur le chapitre.
- Pas de conclusion morale.
- Ne cite rien qui n'apparaît pas dans les données fournies.
- Texte continu, 300 à 350 mots.
- Entre directement dans la matière dès la première phrase.

[Texte final :]
""".strip()

    logger.debug("PROMPT POTENTIELS :\n%s", prompt)

    try:
        response = call_llm(prompt) if call_llm else ""
        texte_final = (response or "").strip()
        logger.debug("RESPONSE POTENTIELS :\n%s", texte_final)
        return texte_final
    except Exception as e:
        logger.exception("Erreur LLM potentiels_karmiques : %s", e)
        return ""