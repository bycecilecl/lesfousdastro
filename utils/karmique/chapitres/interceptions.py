# utils/karmique/chapitres/interceptions.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import re

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


SIGN_RULERS = {
    "belier": ["Mars"],
    "taureau": ["Vénus"],
    "gemeaux": ["Mercure"],
    "cancer": ["Lune"],
    "lion": ["Soleil"],
    "vierge": ["Mercure"],
    "balance": ["Vénus"],
    "scorpion": ["Mars", "Pluton"],
    "sagittaire": ["Jupiter"],
    "capricorne": ["Saturne"],
    "verseau": ["Saturne", "Uranus"],
    "poissons": ["Jupiter", "Neptune"],
}


DIGNITIES = {
    "Vénus": {
        "exil": ["belier", "scorpion"],
        "chute": ["vierge"],
        "domicile": ["taureau", "balance"],
        "exaltation": ["poissons"],
    },
    "Mars": {
        "exil": ["taureau", "balance"],
        "chute": ["cancer"],
        "domicile": ["belier", "scorpion"],
        "exaltation": ["capricorne"],
    },
    "Mercure": {
        "exil": ["sagittaire", "poissons"],
        "chute": ["poissons"],
        "domicile": ["gemeaux", "vierge"],
        "exaltation": ["vierge"],
    },
    "Jupiter": {
        "exil": ["gemeaux", "vierge"],
        "chute": ["capricorne"],
        "domicile": ["sagittaire", "poissons"],
        "exaltation": ["cancer"],
    },
    "Saturne": {
        "exil": ["cancer", "lion"],
        "chute": ["belier"],
        "domicile": ["capricorne", "verseau"],
        "exaltation": ["balance"],
    },
    "Soleil": {
        "exil": ["verseau"],
        "chute": ["balance"],
        "domicile": ["lion"],
        "exaltation": ["belier"],
    },
    "Lune": {
        "exil": ["capricorne"],
        "chute": ["scorpion"],
        "domicile": ["cancer"],
        "exaltation": ["taureau"],
    },
}

EXCLUDED_INTERCEPTION_ASPECT_TARGETS = {"Lune Noire"}


def _slug(s: Any) -> str:
    """Normalisation pour matcher la BDD."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e")
    s = s.replace("à", "a").replace("â", "a")
    s = s.replace("î", "i").replace("ï", "i")
    s = s.replace("ô", "o").replace("ù", "u").replace("û", "u")
    s = s.replace("ç", "c").replace("œ", "oe")
    s = s.replace(" ", "_")
    return s


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _norm_aspect_name(x: Any) -> str:
    if not x:
        return ""
    x = str(x).strip().lower()
    if x in ("carre", "carré"):
        return "Carré"
    if x == "opposition":
        return "Opposition"
    if x == "conjonction":
        return "Conjonction"
    if x == "trigone":
        return "Trigone"
    if x == "sextile":
        return "Sextile"
    return str(x).capitalize()


def _collect_planet_aspects(theme: Dict[str, Any], planet_name: str) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    out: List[Dict[str, Any]] = []

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")

        if p1 in EXCLUDED_INTERCEPTION_ASPECT_TARGETS or p2 in EXCLUDED_INTERCEPTION_ASPECT_TARGETS:

            continue

        if p1 == planet_name:
            other = p2
        elif p2 == planet_name:
            other = p1
        else:
            continue

        if other in EXCLUDED_INTERCEPTION_ASPECT_TARGETS:
            continue

        out.append({
            "type": _norm_aspect_name(a.get("aspect")),
            "with": other,
            "orb": a.get("orbe"),
        })

    return out


def _find_aspects_between(theme: Dict[str, Any], p_a: str, p_b: str) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    out: List[Dict[str, Any]] = []

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")

        if {p1, p2} == {p_a, p_b}:
            out.append({
                "type": _norm_aspect_name(a.get("aspect")),
                "orb": a.get("orbe"),
            })

    return out


def _collect_rulers_details(theme: Dict[str, Any], rulers: List[str]) -> List[Dict[str, Any]]:
    planetes = theme.get("planetes") or {}
    intercepted_signs = {
        _slug(s) for s in ((theme.get("interceptions") or {}).get("signes_interceptes") or [])
    }

    out: List[Dict[str, Any]] = []

    for r in rulers:
        info = planetes.get(r)
        if not isinstance(info, dict):
            continue

        signe = info.get("signe")
        maison = info.get("maison")

        out.append({
            "name": r,
            "signe": signe,
            "maison": maison,
            "retrograde": bool(info.get("retrograde", False)),
            "intercepted": _slug(signe) in intercepted_signs if signe else False,
            "aspects": _collect_planet_aspects(theme, r),
        })

    return out


def _collect_intercepted_planets(theme: Dict[str, Any], signes_interceptes: List[str]) -> List[Dict[str, Any]]:
    planetes = theme.get("planetes") or {}
    signes_slugs = {_slug(s) for s in (signes_interceptes or [])}
    out: List[Dict[str, Any]] = []

    excluded = {"Ascendant", "MC", "Descendant", "FC"}

    # selon ce que ton calcul_theme renvoie
    house_rulers_map = theme.get("house_rulers_map") or theme.get("maitres_maisons") or {}

    for nom, info in planetes.items():
        if nom in excluded:
            continue
        if not isinstance(info, dict):
            continue

        signe = info.get("signe")
        if _slug(signe) not in signes_slugs:
            continue

        ruled_houses = house_rulers_map.get(nom, [])

        role_info = _get_intercepted_planet_role({
            "name": nom,
            "ruled_houses": ruled_houses
        })

        out.append({
            "name": nom,
            "signe": signe,
            "maison": info.get("maison"),
            "retrograde": bool(info.get("retrograde", False)),
            "ruled_houses": ruled_houses,
            "role": role_info["role"],
            "role_label": role_info["label"],
            "role_summary": role_info["summary"],
            "aspects": _collect_planet_aspects(theme, nom),
        })

    return out

def _score_ruler_damage(ruler_detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score simple de fragilité karmique d'un maître intercepté.
    Plus le score est haut, plus le maître est 'abîmé'.
    """
    score = 0
    reasons = []

    if ruler_detail.get("retrograde"):
        score += 2
        reasons.append("rétrograde")

    if ruler_detail.get("intercepted"):
        score += 2
        reasons.append("intercepté")

    aspects = ruler_detail.get("aspects") or []
    hard_count = 0

    for a in aspects:
        typ = a.get("type")
        if typ in ("Carré", "Opposition"):
            hard_count += 1

    if hard_count:
        score += hard_count
        reasons.append(f"{hard_count} aspect(s) dissonant(s)")

    signe = _slug(ruler_detail.get("signe"))
    name = ruler_detail.get("name")

    # dignités simplifiées
    dignity = DIGNITIES.get(name, {})

    if signe in dignity.get("chute", []):
        score += 3
        reasons.append(f"{name} en chute")

    elif signe in dignity.get("exil", []):
        score += 2
        reasons.append(f"{name} en exil")

    elif signe in dignity.get("domicile", []):
        reasons.append(f"{name} en domicile : force présente mais comprimée")

    elif signe in dignity.get("exaltation", []):
        reasons.append(f"{name} en exaltation : potentiel élevé mais difficile d’accès")

    return {
        "name": name,
        "score": score,
        "reasons": reasons,
    }

def _resolve_dominant_interception_problem(
    axes: List[Any],
    rulers_damage: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Détermine quel signe de l'axe intercepté semble le plus en difficulté
    selon l'état de ses maîtres.
    """
    if not axes or not rulers_damage:
        return {
            "dominant_problem_sign": None,
            "both_damaged": False,
            "summary": None,
        }
    
    if len(axes) > 1:
        logger.warning(
            "INTERCEPTIONS: plusieurs axes détectés (%s). "
            "Seul le premier axe sera utilisé pour déterminer le dominant.",
            len(axes)
        )

    # on prend le premier axe pour l’instant
    axe = axes[0]
    if not isinstance(axe, (list, tuple)) or len(axe) != 2:
        return {
            "dominant_problem_sign": None,
            "both_damaged": False,
            "summary": None,
        }

    s1, s2 = axe
    s1_slug = _slug(s1)
    s2_slug = _slug(s2)


    damage_map = {d["name"]: d["score"] for d in rulers_damage}

    s1_score = sum(damage_map.get(r, 0) for r in SIGN_RULERS.get(s1_slug, []))
    s2_score = sum(damage_map.get(r, 0) for r in SIGN_RULERS.get(s2_slug, []))

    both_damaged = s1_score > 0 and s2_score > 0

    if s1_score > s2_score:
        dominant = s1
    elif s2_score > s1_score:
        dominant = s2
    else:
        dominant = None

    return {
        "dominant_problem_sign": dominant,
        "score_sign_1": s1_score,
        "score_sign_2": s2_score,
        "both_damaged": both_damaged,
        "summary": f"{s1}={s1_score} / {s2}={s2_score}",
    }

def _get_intercepted_planet_role(planet_detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Détermine le rôle karmique principal d'une planète interceptée.
    - relai : dirige une ou plusieurs maisons
    - noyau : n'en dirige aucune
    """
    ruled_houses = planet_detail.get("ruled_houses") or []

    if ruled_houses:
        return {
            "role": "relai",
            "label": "relai karmique",
            "summary": (
                "Cette planète ne garde pas seulement l’interception en elle : "
                "elle la rejoue aussi dans les maisons qu’elle dirige."
            )
        }

    return {
        "role": "noyau",
        "label": "noyau karmique",
        "summary": (
            "Cette planète agit surtout comme un point de condensation du problème : "
            "elle intensifie l’énergie interceptée sans forcément la relayer vers un autre domaine."
        )
    }

def _debug_bdd_lookup(astre: str, donnee: str, valeur: str) -> str:
    """
    Lookup BDD avec log debug.
    TODO: désactiver ou alléger en production si trop verbeux.
    """
    txt = get_karmique_interp(astre, donnee, valeur)
    ok = bool(txt and str(txt).strip())
    preview = txt[:120].replace("\n", " ") if ok else "NONE"

    logger.debug(
        "[BDD INTERCEPTION] astre=%s | donnee=%s | valeur=%s | found=%s | preview=%s",
        astre,
        donnee,
        valeur,
        ok,
        preview,
    )

    return txt

def _find_intercepted_sign_for_ruler(ruler_name: str, signes_interceptes: List[str]) -> Optional[str]:
    """
    Retrouve à quel signe intercepté appartient un maître.
    Ex:
    - Vénus -> Taureau ou Balance
    - Mars -> Bélier ou Scorpion
    - Pluton -> Scorpion
    """


    r_slug = _slug(ruler_name)

    for signe in signes_interceptes or []:
        s_slug = _slug(signe)
        rulers = [r.lower() for r in SIGN_RULERS.get(s_slug, [])]
        if r_slug in rulers:
            return s_slug

    return None

def _extract_duplicate_signs(theme: Dict[str, Any]) -> Dict[str, List[int]]:
    """
    Détecte les signes gouvernant plusieurs cuspides.
    Retourne :
    {
        "balance": [1, 8],
        "belier": [2, 9]
    }
    """
    maisons = theme.get("maisons") or {}

    logger.debug("=== DEBUG DUPLICATE SIGNS ===")
    logger.debug("theme['maisons'] raw = %s", maisons)
    
    sign_to_houses: Dict[str, List[int]] = {}

    for maison_num, info in maisons.items():
        if not isinstance(info, dict):
            continue

        signe = info.get("signe")
        if not signe:
            continue

        slug = _slug(signe)

        try:
            house_num = int(maison_num)
        except Exception:
            match = re.search(r"\d+", str(maison_num))
            if not match:
                continue
            house_num = int(match.group())

        sign_to_houses.setdefault(slug, []).append(house_num)

    duplicates = {
        sign: houses
        for sign, houses in sign_to_houses.items()
        if len(houses) >= 2
    }

    logger.debug("sign_to_houses = %s", sign_to_houses)
    logger.debug("duplicates found = %s", duplicates)
    logger.debug("=== END DEBUG DUPLICATE SIGNS ===")

    return duplicates

def build_block_interceptions(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Bloc Interceptions :
    - signes interceptés
    - axes interceptés
    - maisons concernées
    - maîtres des signes interceptés
    - planètes présentes dans les signes interceptés
    - liens entre les maîtres
    """
    interceptions = theme.get("interceptions") or {}
    logger.debug("INTERCEPTIONS theme['maisons']=%s", theme.get("maisons"))
    meta = score.get("meta", {}) or {}

    logger.debug("INTERCEPTIONS theme.interceptions=%s", interceptions)
    logger.debug(
        "INTERCEPTIONS score.meta keys=%s",
        list(meta.keys()) if isinstance(meta, dict) else meta
    )
    logger.debug("INTERCEPTIONS theme keys=%s", list(theme.keys()))

    signes = interceptions.get("signes_interceptes") or []
    axes = interceptions.get("axes_interceptes") or []
    maisons = interceptions.get("maisons_interceptees") or interceptions.get("maisons_interceptées") or {}
    logger.debug("INTERCEPTIONS signes=%s", signes)
    logger.debug("INTERCEPTIONS axes=%s", axes)
    logger.debug("INTERCEPTIONS maisons_interceptees=%s", maisons)

    rulers = meta.get("intercepted_rulers", []) or []
    rulers_aspects = meta.get("intercepted_rulers_aspects", {}) or {}

    if not signes and not axes:
        logger.debug("INTERCEPTIONS skipped: aucun signe ni axe intercepté")
        return None

    # --------------------------
    # Collecte des données utiles
    # --------------------------
    rulers_details = _collect_rulers_details(theme, rulers)
    rulers_damage = [_score_ruler_damage(r) for r in rulers_details]
    dominant_problem = _resolve_dominant_interception_problem(axes, rulers_damage)
    dominant_sign = dominant_problem.get("dominant_problem_sign")
    both_damaged = dominant_problem.get("both_damaged")

    intercepted_planets = _collect_intercepted_planets(theme, signes)
    duplicate_signs = _extract_duplicate_signs(theme)
    nodes_in_interceptions = _detect_nodes_in_interceptions(theme, signes)

    dominant_planets_summary = _summarize_intercepted_planets_for_dominant_sign(
        intercepted_planets,
        dominant_sign
    )

    ruler_links: List[Dict[str, Any]] = []
    if len(rulers) >= 2:
        seen = set()
        for i, r1 in enumerate(rulers):
            for r2 in rulers[i + 1:]:
                key = tuple(sorted([r1, r2]))
                if key in seen:
                    continue
                seen.add(key)

                links = _find_aspects_between(theme, r1, r2)
                if links:
                    ruler_links.append({
                        "between": [r1, r2],
                        "aspects": links,
                    })

    ruler_links_summary = _summarize_ruler_links(ruler_links)


    # --------------------------
    # Rendu texte
    # --------------------------
    lines: List[str] = []

    intro = (
        "Les signes interceptés sont des zones du thème qui ne gouvernent aucune cuspide de maison : "
        "ils agissent en tâche de fond, moins visibles mais tout aussi actifs. "
        "En karmique, ils signalent des énergies mises de côté dans des vies antérieures, "
        "qui demandent aujourd'hui à être réintégrées consciemment."
    )

    # NOYAU KARMIQUE
    if dominant_sign:
        lines.append("## Noyau karmique de l’interception")
        lines.append("")
        if both_damaged:
            lines.append(
                f"L’axe intercepté semble actif des deux côtés, mais c’est surtout **{dominant_sign}** "
                f"qui porte ici la charge principale. C’est donc ce signe qui paraît le plus manquant, "
                f"le plus difficile à intégrer spontanément, et sans doute le plus révélateur du vécu karmique."
            )
        else:
            lines.append(
                f"Le signe qui semble porter l’essentiel de la problématique karmique est **{dominant_sign}**. "
                f"C’est cette énergie qui paraît la plus brouillée, la moins disponible naturellement, "
                f"et la plus importante à comprendre dans cette interception."
            )
        lines.append("")


    # AXES
    if axes:
        lines.append("## Axe intercepté")
        lines.append("")

        for axe in axes:
            if not isinstance(axe, (list, tuple)) or len(axe) != 2:
                continue

            s1, s2 = axe
            axe_key = f"{_slug(s1)}_{_slug(s2)}"

            # Texte BDD de l'axe de signes : ex. taureau_scorpion
            txt = _debug_bdd_lookup("INTERCEPTION", "axe", axe_key)

            logger.debug("INTERCEPTIONS axe signes key=%s", axe_key)
            logger.debug("INTERCEPTIONS axe signes txt found=%s", bool(txt))

            # Texte BDD de l'axe de maisons : ex. 6-12
            maison_axis_txt = ""
            maison_nums = []

            if isinstance(maisons, dict):
                for s in (s1, s2):
                    raw_maison = maisons.get(s) or maisons.get(_slug(s)) or ""
                    match = re.search(r"\d+", str(raw_maison))
                    if match:
                        maison_nums.append(int(match.group()))

            if len(maison_nums) == 2:
                maison_key = "-".join(str(x) for x in sorted(maison_nums))
                maison_axis_txt = _debug_bdd_lookup("INTERCEPTION", "axe", maison_key) or ""

                logger.debug("INTERCEPTIONS axe maisons key=%s", maison_key)
                logger.debug("INTERCEPTIONS axe maisons txt found=%s", bool(maison_axis_txt))

            # Affichage des maisons dans le titre
            maison_label_txt = ""

            if isinstance(maisons, dict):
                m1 = maisons.get(s1) or maisons.get(_slug(s1)) or ""
                m2 = maisons.get(s2) or maisons.get(_slug(s2)) or ""

                if m1 or m2:
                    morceaux = []
                    if m1:
                        morceaux.append(f"{s1} : {m1}")
                    if m2:
                        morceaux.append(f"{s2} : {m2}")
                    maison_label_txt = f" ({' — '.join(morceaux)})"

            lines.append(f"### {s1} – {s2}{maison_label_txt}")

            if txt:
                lines.append(txt.strip())
            else:
                lines.append("Cet axe intercepté met en tension deux polarités qui peinent à circuler librement.")

            if maison_axis_txt:
                lines.append("")
                lines.append(maison_axis_txt.strip())

            lines.append("")


    # MAÎTRES
    if rulers_details:
        lines.append("## Maîtres de l’axe intercepté")
        lines.append("")
        lines.append(
            "Les maîtres montrent où l'énergie interceptée cherche à se rejouer concrètement dans la vie."
        )
        lines.append("")

        for r in rulers_details:
            extra = []
            if r.get("signe"):
                extra.append(str(r["signe"]))
            if r.get("maison") is not None:
                extra.append(f"Maison {r['maison']}")
            if r.get("retrograde"):
                extra.append("rétrograde")
            if r.get("intercepted"):
                extra.append("intercepté")

            extra_txt = f" ({' — '.join(extra)})" if extra else ""
            lines.append(f"### {r['name']}{extra_txt}")

            signe_source = _find_intercepted_sign_for_ruler(r["name"], signes)
            txt = ""

            if signe_source:
                txt = _debug_bdd_lookup(
                    "INTERCEPTION",
                    f"maitre_{signe_source}",
                    _slug(r["name"])
                )

            if txt:
                lines.append(txt.strip())
            else:
                lines.append(
                    "Ce maître montre une zone où l’énergie interceptée tente de s’exprimer "
                    "sans le faire complètement de manière fluide."
                )
            lines.append("")
            aspects = r.get("aspects") or rulers_aspects.get(r["name"], []) or []
            if aspects:
                lines.append("**Aspects du maître :**")
                for a in aspects:
                    typ = a.get("type")
                    wit = a.get("with")
                    orb = a.get("orb")
                    orb_txt = f"{float(orb):.2f}" if isinstance(orb, (int, float)) else str(orb)
                    lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
                lines.append("")

    # LIENS ENTRE MAÎTRES
    if ruler_links:
        lines.append("## Lien entre les maîtres")
        lines.append("")

        if ruler_links_summary:
            lines.append(ruler_links_summary)
            lines.append("")

        for rl in ruler_links:
            r1, r2 = rl["between"]
            lines.append(f"### {r1} ↔ {r2}")
            for a in rl["aspects"]:
                orb = a.get("orb")
                orb_txt = f"{float(orb):.2f}" if isinstance(orb, (int, float)) else str(orb)
                lines.append(f"- {a['type']} (orbe {orb_txt}°)")
            lines.append("")

    # NŒUDS DANS INTERCEPTION
    if nodes_in_interceptions:
        lines.append("## Nœuds lunaires dans l’interception")
        lines.append("")
        lines.append(
            "Quand les Nœuds lunaires tombent dans une interception, "
            "le chemin karmique devient moins visible, moins spontané. "
            "L’évolution ne manque pas forcément de direction : elle manque surtout d’accès."
        )
        lines.append("")

        for node in nodes_in_interceptions:
            extra = []

            if node.get("signe"):
                extra.append(node["signe"])

            if node.get("maison") is not None:
                extra.append(f"Maison {node['maison']}")

            extra_txt = f" ({' — '.join(extra)})" if extra else ""

            lines.append(f"### {node['name']}{extra_txt}")

            txt = _debug_bdd_lookup(
                "INTERCEPTION",
                "noeud_intercepte",
                _slug(node["name"])
            )

            if txt:
                lines.append(txt.strip())
            else:
                lines.append(
                    "Ce nœud évolue dans une zone psychique difficile à mobiliser consciemment. "
                    "Le sentiment de direction peut exister, mais rester longtemps inaccessible, retardé ou mal formulé."
                )

            lines.append("")

    # SIGNES DUPLIQUÉS
    if duplicate_signs:
        lines.append("## Signes dupliqués")
        lines.append("")
        lines.append(
            "Les signes dupliqués compensent souvent les interceptions. "
            "Ils deviennent des zones surinvesties : là où l'énergie circule trop facilement, "
            "parfois pour éviter d'affronter la zone plus silencieuse de l'interception."
        )
        lines.append("")

        for sign_slug, houses in duplicate_signs.items():
            sign_name = sign_slug.capitalize()
            maisons_txt = ", ".join([f"Maison {m}" for m in houses])

            lines.append(f"### {sign_name} ({maisons_txt})")

            txt = _debug_bdd_lookup(
                "INTERCEPTION",
                "signe_duplique",
                sign_slug
            )

            if txt:
                lines.append(txt.strip())
            else:
                lines.append(
                    "Ce signe semble prendre davantage de place dans le fonctionnement psychique. "
                    "Il peut devenir une stratégie de compensation face à l'énergie interceptée."
                )

            lines.append("")

    # PLANÈTES INTERCEPTÉES
    if intercepted_planets:
        lines.append("## Planètes présentes dans les interceptions")
        lines.append("")

        if dominant_planets_summary:
            lines.append(dominant_planets_summary)
            lines.append("")

        lines.append(
            "Les planètes interceptées fonctionnent souvent de manière plus automatique, floue ou peu conscientisée. "
            "Mais leur présence aide aussi à comprendre l’énergie du signe intercepté."
        )
        lines.append("")

        for p in intercepted_planets:
            extra = []
            if p.get("signe"):
                extra.append(str(p["signe"]))
            if p.get("maison") is not None:
                extra.append(f"Maison {p['maison']}")
            if p.get("retrograde"):
                extra.append("rétrograde")

            ruled_houses = p.get("ruled_houses") or []
            if ruled_houses:
                maisons_txt = ", ".join([str(m) for m in ruled_houses])
                extra.append(f"dirige Maison(s) {maisons_txt}")

            extra_txt = f" ({' — '.join(extra)})" if extra else ""
            lines.append(f"### {p['name']}{extra_txt}")

            if p.get("role_label"):
                lines.append(f"**Rôle : {p['role_label']}**")
                lines.append("")

            if p.get("role_summary"):
                lines.append(p["role_summary"])
                lines.append("")

            #txt = get_karmique_interp("INTERCEPTION", "planete", _slug(p["name"]))
            txt = get_karmique_interp("INTERCEPTION", "planete", _slug(p["name"]))
            if txt:
                lines.append(txt.strip())
            else:
                lines.append(
                    "Cette planète interceptée agit comme une énergie difficile à canaliser consciemment, "
                    "souvent activée en réaction plutôt qu’en choix lucide."
                )
            lines.append("")

            if ruled_houses:
                maisons_txt = ", ".join([f"Maison {m}" for m in ruled_houses])
                lines.append(
                    f"Cette planète relaie aussi l’interception dans **{maisons_txt}**, "
                    f"ce qui montre que son brouillard ne reste pas enfermé dans le signe : "
                    f"il se rejoue aussi dans ce(s) domaine(s) de vie."
                )
                lines.append("")

            aspects = p.get("aspects") or []
            if aspects:
                lines.append("**Aspects de la planète interceptée :**")
                for a in aspects[:5]:
                    typ = a.get("type")
                    wit = a.get("with")
                    orb = a.get("orb")
                    orb_txt = f"{float(orb):.2f}" if isinstance(orb, (int, float)) else str(orb)
                    lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
                lines.append("")

    # ASSEMBLAGE FINAL
    content = _join([
        "# Interceptions — lecture karmique",
        "",
        intro,
        "",
        *lines,
    ])

    summary = summarize_chapter(
        chapter_title="Interceptions : ce qui tourne en tâche de fond",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    logger.debug("INTERCEPTIONS content_len=%s", len(content))
    logger.debug("INTERCEPTIONS preview=%s", content[:200])

    return {
        "id": "interceptions",
        "title": "Interceptions : ce qui tourne en tâche de fond",
        "data": {
            "signes_interceptes": signes,
            "axes_interceptes": axes,
            "maisons_interceptees": maisons,
            "intercepted_rulers": rulers,
            "intercepted_rulers_aspects": rulers_aspects,
            "rulers_details": rulers_details,
            "rulers_damage": rulers_damage,
            "dominant_problem": dominant_problem,
            "intercepted_planets": intercepted_planets,
            "duplicate_signs": duplicate_signs,
            "nodes_in_interceptions": nodes_in_interceptions,
            "ruler_links": ruler_links,
            "ruler_links_summary": ruler_links_summary,
            "dominant_planets_summary": dominant_planets_summary,
        },
        "content": content,
        "text": content,
        "summary": summary,
    }

def _summarize_ruler_links(ruler_links: List[Dict[str, Any]]) -> Optional[str]:
    """
    Produit un résumé simple du climat entre les maîtres de l'interception.
    """
    if not ruler_links:
        return (
            "Les maîtres de l’axe ne semblent pas reliés directement entre eux. "
            "Cela peut créer une sensation de dissociation intérieure : les deux pôles existent, "
            "mais peinent à dialoguer spontanément."
        )

    hard = 0
    soft = 0
    conj = 0

    for rl in ruler_links:
        for a in rl.get("aspects", []):
            typ = a.get("type")
            if typ in ("Carré", "Opposition"):
                hard += 1
            elif typ in ("Trigone", "Sextile"):
                soft += 1
            elif typ == "Conjonction":
                conj += 1

    if hard > 0:
        return (
            "Les maîtres de l’axe sont en tension entre eux. "
            "Cela renforce souvent la sensation de déchirement intérieur : "
            "une partie de la personnalité tire dans un sens, l’autre résiste ou contrecarre le mouvement."
        )

    if conj > 0:
        return (
            "Les maîtres de l’axe sont fortement liés. "
            "L’interception agit donc comme une problématique compacte, centrale, difficile à contourner, "
            "mais aussi très puissante à conscientiser."
        )

    if soft > 0:
        return (
            "Les maîtres de l’axe semblent pouvoir coopérer. "
            "Même si l’énergie interceptée reste floue, il existe un potentiel de réconciliation intérieure "
            "et de circulation plus harmonieuse entre les deux pôles."
        )

    return None


def _summarize_intercepted_planets_for_dominant_sign(
    intercepted_planets: List[Dict[str, Any]],
    dominant_sign: Optional[str]
) -> Optional[str]:
    """
    Résume le rôle des planètes interceptées situées dans le signe dominant.
    """
    if not dominant_sign:
        return None

    target = _slug(dominant_sign)
    planets_in_sign = [
        p for p in (intercepted_planets or [])
        if _slug(p.get("signe")) == target
    ]

    if not planets_in_sign:
        return (
            f"Le signe **{dominant_sign}** semble être le point le plus manquant de l’interception, "
            f"et l’absence de planète dans ce signe renforce encore son caractère flou ou difficile à cerner consciemment."
        )

    names = [p["name"] for p in planets_in_sign]
    names_txt = ", ".join(names)

    return (
        f"Le signe **{dominant_sign}** paraît être le point le plus sensible de l’interception. "
        f"La présence de {names_txt} dans ce signe montre que cette énergie n’est pas totalement absente : "
        f"elle cherche au contraire à se manifester, mais souvent de manière automatique, floue ou peu maîtrisée. "
        f"Ces planètes compliquent l’intégration du signe, tout en donnant aussi une porte d’entrée pour mieux le comprendre."
    )

def _detect_nodes_in_interceptions(
    theme: Dict[str, Any],
    signes_interceptes: List[str]
) -> List[Dict[str, Any]]:
    """
    Détecte si les Nœuds Lunaires tombent dans un signe intercepté.
    """
    planetes = theme.get("planetes") or {}
    signes_slug = {_slug(s) for s in signes_interceptes}

    out = []

    for node_name in ["Nœud Nord", "Nœud Sud"]:
        info = planetes.get(node_name)

        if not isinstance(info, dict):
            continue

        signe = info.get("signe")

        if _slug(signe) in signes_slug:
            out.append({
                "name": node_name,
                "signe": signe,
                "maison": info.get("maison"),
            })

    return out

def interpret_block_interceptions_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm=None,
    global_ctx: Dict[str, Any] | None = None,
) -> str:

    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    data = block.get("data", {}) or {}
    dominant_problem = data.get("dominant_problem") or {}
    dominant_sign = dominant_problem.get("dominant_problem_sign")
    both_damaged = dominant_problem.get("both_damaged")
    ruler_links_summary = data.get("ruler_links_summary") or ""
    duplicate_signs = data.get("duplicate_signs") or {}


    nodes_in_interceptions = data.get("nodes_in_interceptions") or []
    dominant_planets_summary = data.get("dominant_planets_summary") or ""

    if duplicate_signs:
        duplicate_txt = ", ".join(
            f"{sign} → maisons {', '.join(str(h) for h in houses)}"
            for sign, houses in duplicate_signs.items()
        )
    else:
        duplicate_txt = "aucun signe dupliqué détecté"

    if nodes_in_interceptions:
        nodes_txt = ", ".join(
            f"{n.get('name')} en {n.get('signe')} maison {n.get('maison')}"
            for n in nodes_in_interceptions
        )
    else:
        nodes_txt = "aucun nœud lunaire intercepté"
    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    karmic_ctx = (global_ctx or {}).get("karmic_context", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []
    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("interceptions", "")
    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n\n".join(memories[-8:]) if memories else "Aucune mémoire précédente"


    genre_instruction = (
    "Tu t'adresses à une femme. Tutoiement direct."
    if genre_label == "femme"
    else "Tu t'adresses à un homme. Tutoiement direct."
)

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique jungienne, directe, analytique, avec une pointe de mordant.
Ta mission : rédiger le chapitre "Interceptions" d’une analyse karmique profonde.

{genre_instruction}

Ce chapitre traite d’une énergie présente mais difficile d’accès.
Il ne s’agit ni d’une crise active (Maison 8), ni d’un inconscient diffus (Maison 12).
Ici, tu décris une énergie structurellement retenue : un potentiel latent, une fonction psychique mise en sourdine, une partie de la personnalité qui existe mais qui ne circule pas naturellement.

Tu dois montrer :
- ce qui reste bloqué,
- comment cela se manifeste concrètement,
- comment la personne contourne cette difficulté,
- ce que cela produit dans la vie quotidienne et intérieure.

Contexte global :
{theme_brief or "Non fourni"}

Contexte karmique :
{karmic_ctx or "Non fourni"}

Mémoire des chapitres précédents :
{memories_txt}

Données techniques :

- Signe dominant intercepté : {dominant_sign or "non déterminé"}
- Les deux côtés de l'axe sont-ils fragilisés : {"oui" if both_damaged else "non"}
- Dynamique entre les maîtres : {ruler_links_summary or "aucun lien direct détecté"}
- Planètes dans la zone interceptée : {dominant_planets_summary or "aucune"}
- Signes dupliqués / compensatoires : {duplicate_txt}
- Nœuds lunaires interceptés : {nodes_txt}
- Données BDD : {content}

IMPORTANT :
Les signes dupliqués doivent obligatoirement être intégrés.
Ils montrent comment la personne compense ou contourne l’énergie interceptée.

RÈGLES DE RÉDACTION

- Pas de prénom.
- Pas d’introduction.
- Pas de formule type "dans ton thème".
- Commence directement l’analyse.
- Texte en 3 paragraphes denses.
- Longueur : 350 à 450 mots.
- Aucun titre.
- Aucun bullet point.
- Aucun résumé final.
- Aucun ton pédagogique.
- Aucun jargon astrologique brut.
- Pas de paraphrase scolaire des placements.

STYLE ATTENDU

- Style incarné, dense, précis.
- Lecture psychologique concrète.
- Tu décris une mécanique intérieure, pas une théorie.
- Tu peux être incisif, mais jamais caricatural.
- Tu expliques le fonctionnement réel de la personne.
- Tu montres les contradictions internes.
- Tu écris comme quelqu’un qui observe une structure psychique, pas comme un professeur.

PRIORITÉS D’ANALYSE

1. La maison concernée est prioritaire :
   elle montre où le blocage se vit concrètement.

2. Le signe intercepté :
   il décrit la nature exacte de l’énergie retenue.

3. Les maîtres et les planètes interceptées :
   ils expliquent comment le blocage fonctionne.

4. Les signes dupliqués :
   ils montrent la stratégie compensatoire.

5. Les aspects :
   ils servent à préciser la tension ou la rigidité.

IMPORTANT — CONCRET OBLIGATOIRE

Pour chaque maison citée, tu dois montrer une manifestation concrète :
- santé
- corps
- habitudes
- argent
- famille
- sexualité
- travail
- image sociale
- communication
- rapport au temps
- lien affectif

Tu ne dois jamais rester dans une abstraction psychologique pure.

INTERDIT

- "transformation intérieure"
- "évolution personnelle"
- "travail sur soi"
- "prise de conscience"
- "potentiel créateur"
- "guérison"
- "accueillir"
- "lâcher prise"
- "harmonie"
- "équilibre"
- "énergie enfouie"
- "cela t'invite à"
- "cela te pousse à"

Ne termine jamais par une morale, une ouverture positive ou une solution.
Tu termines sur la texture réelle du blocage :
ce que cela fatigue, rigidifie, retarde, use ou empêche.

Si une donnée manque, n’invente pas.
Tu approfondis ce qui existe déjà.

Commence immédiatement.
""".strip()


    logger.debug("PROMPT INTERCEPTIONS\n%s", prompt)
    
    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte