# utils/karmique/chapitres/noeud_lunaires.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique._slug import slug, house_int
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging
logger = logging.getLogger(__name__)


# ✅ Fix #3 : Orbe configurable
NODE_ORB_LIMIT = 5.0  # Orbe max global pour les aspects des Nœuds
NODE_STRONG_CONJUNCTION_ORB = 3.0  # Conjonction nodale très forte

MAX_ASPECTS = 5

MASTER_ASPECT_TARGETS = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
    "Chiron", "Lune Noire",
    "Ascendant", "MC", "Milieu du Ciel",
    "Descendant", "Fond du Ciel"
}


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

NODE_PLANETS = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
    "Chiron", "Lune Noire"
}


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _norm_aspect(s: str) -> str:
    """Normalise les noms d'aspects."""
    if not s:
        return ""
    s = str(s).strip()
    low = s.lower()
    
    if low in ("carre", "carré"):
        return "Carré"
    if low == "trigone":
        return "Trigone"
    if low == "sextile":
        return "Sextile"
    if low == "opposition":
        return "Opposition"
    if low == "conjonction":
        return "Conjonction"
    return s

def _aspect_priority(a: Dict[str, Any]) -> tuple:
    """
    Classe les aspects des maîtres nodaux par puissance karmique.
    Plus le score est bas, plus l'aspect est prioritaire.
    """
    typ = _norm_aspect(a.get("type"))
    target = a.get("with")
    orb = a.get("orb", 99)

    try:
        orb = float(orb)
    except (TypeError, ValueError):
        orb = 99

    aspect_weight = {
        "Conjonction": 0,
        "Carré": 0,
        "Opposition": 1,
        "Trigone": 3,
        "Sextile": 4,
    }.get(typ, 9)

    target_weight = {
        "Pluton": 0,
        "Lune Noire": 0,
        "Ascendant": 0,
        "MC": 0,
        "Milieu du Ciel": 0,
        "Saturne": 1,
        "Uranus": 1,
        "Neptune": 1,
        "Mars": 2,
        "Soleil": 2,
        "Lune": 2,
        "Chiron": 2,
        "Jupiter": 3,
        "Vénus": 3,
        "Mercure": 3,
    }.get(target, 5)

    return (aspect_weight, target_weight, orb)

def _is_retrograde(info: Dict[str, Any]) -> bool:
    """
    Détecte si une planète est rétrograde selon les clés possibles du thème.
    """
    if not isinstance(info, dict):
        return False

    return bool(
        info.get("retrograde")
        or info.get("rx")
        or info.get("is_retrograde")
        or info.get("retro")
    )


def _collect_node_aspects(theme: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Collecte les aspects karmiques des Nœuds (Rahu/Ketu) avec les planètes.
    """
    aspects = theme.get("aspects") or []
    
    KARMIC_ASPECTS = {"Conjonction", "Carré", "Opposition"}
    
    nn_hits = []
    ns_hits = []
    
    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        typ = _norm_aspect(a.get("aspect"))
        orb = a.get("orbe")
        
        if typ not in KARMIC_ASPECTS:
            continue
        
        try:
            orbf = float(orb) if orb is not None else None
        except (TypeError, ValueError):
            orbf = None
        
        # ✅ Utilisation de la constante
        if orbf is None or orbf > NODE_ORB_LIMIT:
            continue
        
        # Nœud Nord (Rahu)
        if p1 == "Rahu" and p2 in NODE_PLANETS:
            nn_hits.append({"with": p2, "type": typ, "orb": round(orbf, 2)})
        elif p2 == "Rahu" and p1 in NODE_PLANETS:
            nn_hits.append({"with": p1, "type": typ, "orb": round(orbf, 2)})
        
        # Nœud Sud (Ketu)
        elif p1 == "Ketu" and p2 in NODE_PLANETS:
            ns_hits.append({"with": p2, "type": typ, "orb": round(orbf, 2)})
        elif p2 == "Ketu" and p1 in NODE_PLANETS:
            ns_hits.append({"with": p1, "type": typ, "orb": round(orbf, 2)})
    
    nn_hits.sort(key=lambda x: x.get("orb", 999))
    ns_hits.sort(key=lambda x: x.get("orb", 999))
    
    return {"nn_aspects": nn_hits, "ns_aspects": ns_hits}

def _collect_planet_aspects(theme: Dict[str, Any], planet: str) -> List[Dict[str, Any]]:
    """
    Collecte les aspects d'une planète (ex: Mars, Vénus...) depuis theme["aspects"].
    Retourne une liste triée par orbe : [{with, type, orb}, ...]
    """
    aspects = theme.get("aspects_avec_angles") or theme.get("aspects") or []
    KEEP = {"Conjonction", "Carré", "Opposition", "Trigone", "Sextile"}

    out: List[Dict[str, Any]] = []

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        typ = _norm_aspect(a.get("aspect"))
        orb = a.get("orbe")

        if typ not in KEEP:
            continue

        try:
            orbf = float(orb) if orb is not None else None
        except (TypeError, ValueError):
            orbf = None

        if orbf is None:
            continue

        if p1 in ("Rahu", "Ketu") or p2 in ("Rahu", "Ketu"):
            continue
        if p1 == planet and p2 in MASTER_ASPECT_TARGETS:
            out.append({"with": p2, "type": typ, "orb": round(orbf, 2)})
        elif p2 == planet and p1 in MASTER_ASPECT_TARGETS:
            out.append({"with": p1, "type": typ, "orb": round(orbf, 2)})

    out.sort(key=lambda x: x.get("orb", 999))
    return out

def build_block_lunar_nodes(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Bloc Nœuds Lunaires : axe évolutif complet avec BDD.
    """
    planets = theme.get("planetes") or {}
    meta = score.get("meta", {}) or {}

    nn = planets.get("Rahu")
    ns = planets.get("Ketu")

    if not isinstance(nn, dict) or not isinstance(ns, dict):
        return None

    nn_sign = nn.get("signe")
    nn_house = house_int(nn.get("maison"))
    ns_sign = ns.get("signe")
    ns_house = house_int(ns.get("maison"))

    # Maîtres (format détaillé si dispo, sinon fallback)
    nn_rulers_details = meta.get("nn_rulers_details", []) or []
    ns_rulers_details = meta.get("ns_rulers_details", []) or []
    interceptions = theme.get("interceptions", {}) or {}
    signes_interceptes = interceptions.get("signes_interceptes", []) or []

    # ✅ Fallback maîtres si meta vide
    if not ns_rulers_details and ns_sign:
        for r in SIGN_RULERS.get(slug(ns_sign), []):
            ns_rulers_details.append({"name": r, "house": None, "aspects": []})

    if not nn_rulers_details and nn_sign:
        for r in SIGN_RULERS.get(slug(nn_sign), []):
            nn_rulers_details.append({"name": r, "house": None, "aspects": []})

    # ✅ Remplit les aspects des maîtres si absents / vides
    for d in ns_rulers_details:
        nm = d.get("name")
        if nm:
            d["aspects"] = _collect_planet_aspects(theme, nm)[:MAX_ASPECTS]

    for d in nn_rulers_details:
        nm = d.get("name")
        if nm:
            d["aspects"] = _collect_planet_aspects(theme, nm)[:MAX_ASPECTS]

    # ==================
    # MAÎTRES NODAUX INTERCEPTÉS
    # ==================
    interceptions = theme.get("interceptions", {}) or {}
    signes_interceptes = interceptions.get("signes_interceptes", []) or []

    ns_rulers_intercepted = []
    nn_rulers_intercepted = []

    for d in ns_rulers_details:
        nm = d.get("name")
        info = planets.get(nm, {})
        signe_maitre = info.get("signe")

        if signe_maitre in signes_interceptes:
            ns_rulers_intercepted.append(nm)

    for d in nn_rulers_details:
        nm = d.get("name")
        info = planets.get(nm, {})
        signe_maitre = info.get("signe")

        if signe_maitre in signes_interceptes:
            nn_rulers_intercepted.append(nm)

    # ✅ Fix #6 : Fallback ancien format
    nn_ruler = meta.get("nn_ruler")
    nn_ruler_aspects = meta.get("nn_ruler_aspects", []) or []

    ns_ruler = meta.get("ns_ruler")
    ns_ruler_aspects = meta.get("ns_ruler_aspects", []) or []

    # Aspects aux nœuds
    node_aspects = _collect_node_aspects(theme)
    nn_aspects = node_aspects.get("nn_aspects", []) or []
    ns_aspects = node_aspects.get("ns_aspects", []) or []

    axis_square_seen = {}

    for a in nn_aspects + ns_aspects:
        if a.get("type") != "Carré":
            continue

        planet_name = a.get("with")
        if not planet_name:
            continue

        if (
            planet_name not in axis_square_seen
            or a.get("orb", 99) < axis_square_seen[planet_name].get("orb", 99)
        ):
            axis_square_seen[planet_name] = a

    axis_square_planets = list(axis_square_seen.values())

    nn_conjuncts_strong = [
        a for a in nn_aspects
        if a.get("type") == "Conjonction" and a.get("orb", 99) <= NODE_STRONG_CONJUNCTION_ORB
    ]

    ns_conjuncts_strong = [
        a for a in ns_aspects
        if a.get("type") == "Conjonction" and a.get("orb", 99) <= NODE_STRONG_CONJUNCTION_ORB
    ]


    # ==================
    # CROISEMENTS MAÎTRES / MAISONS NODALES
    # ==================
    ns_ruler_in_nn_house = []
    nn_ruler_in_ns_house = []

    ns_rulers_retrograde = []
    nn_rulers_retrograde = []

    for d in ns_rulers_details:
        nm = d.get("name")
        if not nm:
            continue

        info = planets.get(nm, {})
        h = house_int(info.get("maison"))

        if _is_retrograde(info):
            ns_rulers_retrograde.append(nm)

        if h == nn_house:
            ns_ruler_in_nn_house.append(nm)

    for d in nn_rulers_details:
        nm = d.get("name")
        if not nm:
            continue

        info = planets.get(nm, {})
        h = house_int(info.get("maison"))

        if _is_retrograde(info):
            nn_rulers_retrograde.append(nm)

        if h == ns_house:
            nn_ruler_in_ns_house.append(nm)

    lines: List[str] = []
    
    # ==================
    # INTRO GÉNÉRALE
    # ==================
    intro = (
        "L'axe des Nœuds Lunaires trace le chemin évolutif de l'âme : "
        "du Nœud Sud (mémoires, automatismes, zone de confort) "
        "vers le Nœud Nord (direction d'évolution, apprentissages nouveaux). "
        "Il ne s'agit pas d'effacer le passé, mais d'apprendre à ne plus s'y réfugier automatiquement."
    )
    
    # ==================
    # AXE GLOBAL
    # ==================
    if ns_sign and nn_sign:
        axe_key = f"{slug(ns_sign)}_{slug(nn_sign)}"
        axe_txt = get_karmique_interp("NOEUDS", "axe", axe_key)
        
        if axe_txt:
            lines.append(f"## Axe {ns_sign} → {nn_sign}")
            lines.append("")
            lines.append(axe_txt.strip())
            lines.append("")


    logger.debug("NS rulers_details: %s", ns_rulers_details)
    logger.debug("NN rulers_details: %s", nn_rulers_details)

    
    # ==================
    # NŒUD SUD
    # ==================
    lines.append("## Nœud Sud : ce que tu connais déjà")
    lines.append("")
    
    # ✅ Fix #1 : "signe" en minuscule
    if ns_sign:
        txt = get_karmique_interp("NOEUD_SUD", "signe", slug(ns_sign))
        if txt:
            lines.append(f"### Nœud Sud en {ns_sign}")
            lines.append(txt.strip())
            lines.append("")
        # ✅ Fix #5 : Fallback si BDD vide
        else:
            lines.append(f"### Nœud Sud en {ns_sign}")
            lines.append("Mémoire karmique à explorer. (Interprétation en cours de rédaction)")
            lines.append("")
    
    # ✅ Fix #1 : "maison" en minuscule
    if ns_house is not None:
        txt = (
            get_karmique_interp("NOEUD_SUD", "maison", str(ns_house))
            or get_karmique_interp("NOEUD_SUD", "Maison", str(ns_house))
        )
        if txt:
            lines.append(f"### Nœud Sud en Maison {ns_house}")
            lines.append(txt.strip())
            lines.append("")
        # sinon : on n'affiche rien (pas de fallback)
    
    # Aspects du Nœud Sud
    if ns_aspects:
        lines.append("### Aspects du Nœud Sud")
        lines.append("")
        lines.append("Le Nœud Sud en aspect avec des planètes révèle des liens karmiques spécifiques :")
        lines.append("")
        
        for asp in ns_aspects[:MAX_ASPECTS]:
            typ = asp.get("type")
            wit = asp.get("with")
            orb = asp.get("orb")
            
            # ✅ Fix #2 : slug() appliqué (gère les accents via _slug.py)
            key = slug(f"{typ}_{wit}")
            txt = get_karmique_interp("NOEUD_SUD", "aspect", key)
            
            if txt:
                lines.append(f"**{typ} avec {wit}** (orbe {orb}°)")
                lines.append(txt.strip())
                lines.append("")
            else:
                lines.append(f"- {typ} avec {wit} (orbe {orb}°)")
        
        lines.append("")
    
    # ✅ Fix #6 : Maîtres du NS (avec fallback)
    if ns_rulers_details:
        lines.append("### Maître(s) du Nœud Sud")
        lines.append("")
        
        for d in ns_rulers_details:
            nm = d.get("name")
            hs = house_int(d.get("house"))
            if not nm:
                continue
            
            info = planets.get(nm) if isinstance(planets.get(nm), dict) else {}
            logger.debug("PLANET INFO %s: %s", nm, info)
            sig = info.get("signe") or info.get("sign")
            
            hs2 = house_int(info.get("maison"))  # on se base sur le thème (fiable)

            parts = []
            if sig: parts.append(str(sig))
            if hs2 is not None: parts.append(f"Maison {hs2}")
            extra = " — ".join(parts) if parts else "—"

            lines.append(f"**{nm}** ({extra})")
            lines.append("")
            
            txt = get_karmique_interp("NOEUD_SUD", "maître", slug(nm))
            if txt:
                lines.append(txt.strip())
                lines.append("")
            
            aspects = d.get("aspects") or []
            if aspects:
                lines.append("**Aspects du maître :**")
                for a in aspects[:MAX_ASPECTS]:
                    typ = a.get("type")
                    wit = a.get("with")
                    orb = a.get("orb")
                    orb_txt = f"{orb:.2f}" if isinstance(orb, (int, float)) else str(orb)
                    
                    lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
                    
                    key = slug(f"{typ}_{wit}")
                    txt = get_karmique_interp("MAITRE_NS", "aspect", key)
                    if txt:
                        lines.append(f"  → {txt.strip()}")
                
                lines.append("")
    
    elif ns_ruler:
        info = planets.get(ns_ruler, {})
        sig = info.get("signe")
        hs = house_int(info.get("maison"))

        lines.append(
            f"### Maître du Nœud Sud : {ns_ruler} "
            f"({sig or '—'} — Maison {hs if hs is not None else '—'})"
        )
        lines.append("")
        
        txt = get_karmique_interp("NOEUD_SUD", "maître", slug(ns_ruler))
        if txt:
            lines.append(txt.strip())
            lines.append("")
        
        if ns_ruler_aspects:
            lines.append("**Aspects du maître :**")
            for a in ns_ruler_aspects[:MAX_ASPECTS]:
                typ = a.get("type")
                wit = a.get("with")
                orb = a.get("orb")
                orb_txt = f"{orb:.2f}" if isinstance(orb, (int, float)) else str(orb)
                lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
            lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # ==================
    # NŒUD NORD
    # ==================
    lines.append("## Nœud Nord : là où tu dois aller")
    lines.append("")
    
    # ✅ Fix #1 : "signe" en minuscule
    if nn_sign:
        txt = (
            get_karmique_interp("NOEUD_NORD", "signe", slug(nn_sign))
            or get_karmique_interp("NOEUD_NORD", "Signe", slug(nn_sign))
        )
        if txt:
            lines.append(f"### Nœud Nord en {nn_sign}")
            lines.append(txt.strip())
            lines.append("")
        else:
            lines.append(f"### Nœud Nord en {nn_sign}")
            lines.append("Direction d'évolution à explorer. (Interprétation en cours de rédaction)")
            lines.append("")
    
    # ✅ Fix #1 : "maison" en minuscule
    if nn_house is not None:
        txt = (
            get_karmique_interp("NOEUD_NORD", "maison", str(nn_house))
            or get_karmique_interp("NOEUD_NORD", "Maison", str(nn_house))
        )
        if txt:
            lines.append(f"### Nœud Nord en Maison {nn_house}")
            lines.append(txt.strip())
            lines.append("")
        else:
            lines.append(f"### Nœud Nord en Maison {nn_house}")
            lines.append("Secteur de vie où cultiver les nouveaux apprentissages.")
            lines.append("")
    
    # Aspects du Nœud Nord
    if nn_aspects:
        lines.append("### Aspects du Nœud Nord")
        lines.append("")
        lines.append("Le Nœud Nord en aspect avec des planètes montre les ressources disponibles pour ton évolution :")
        lines.append("")
        
        for asp in nn_aspects[:MAX_ASPECTS]:
            typ = asp.get("type")
            wit = asp.get("with")
            orb = asp.get("orb")
            
            key = slug(f"{typ}_{wit}")
            txt = get_karmique_interp("NOEUD_NORD", "aspect", key)
            
            if txt:
                lines.append(f"**{typ} avec {wit}** (orbe {orb}°)")
                lines.append(txt.strip())
                lines.append("")
            else:
                lines.append(f"- {typ} avec {wit} (orbe {orb}°)")
        
        lines.append("")
    
    # ✅ Fix #6 : Maîtres du NN (avec fallback)
    if nn_rulers_details:
        lines.append("### Maître(s) du Nœud Nord")
        lines.append("")
        
        for d in nn_rulers_details:
            nm = d.get("name")
            hs = house_int(d.get("house"))
            if not nm:
                continue
            
            info = planets.get(nm) if isinstance(planets.get(nm), dict) else {}
            sig = info.get("signe")
            hs2 = house_int(info.get("maison"))  # on se base sur le thème (fiable)

            parts = []
            if sig: parts.append(str(sig))
            if hs2 is not None: parts.append(f"Maison {hs2}")
            extra = " — ".join(parts) if parts else "—"

            lines.append(f"**{nm}** ({extra})")
            lines.append("")
            
            txt = get_karmique_interp("NOEUD_NORD", "maître", slug(nm))
            if txt:
                lines.append(txt.strip())
                lines.append("")
            
            aspects = d.get("aspects") or []
            if aspects:
                lines.append("**Aspects du maître :**")
                for a in aspects[:MAX_ASPECTS]:
                    typ = a.get("type")
                    wit = a.get("with")
                    orb = a.get("orb")
                    orb_txt = f"{orb:.2f}" if isinstance(orb, (int, float)) else str(orb)
                    
                    lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
                    
                    key = slug(f"{typ}_{wit}")
                    txt = get_karmique_interp("MAITRE_NN", "aspect", key)
                    if txt:
                        lines.append(f"  → {txt.strip()}")
                
                lines.append("")
    
    elif nn_ruler:
        info = planets.get(nn_ruler, {})
        sig = info.get("signe")
        hs = house_int(info.get("maison"))

        lines.append(
            f"### Maître du Nœud Nord : {nn_ruler} "
            f"({sig or '—'} — Maison {hs if hs is not None else '—'})"
        )
        lines.append("")
        
        txt = get_karmique_interp("NOEUD_NORD", "maître", slug(nn_ruler))
        if txt:
            lines.append(txt.strip())
            lines.append("")
        
        if nn_ruler_aspects:
            lines.append("**Aspects du maître :**")
            for a in nn_ruler_aspects[:MAX_ASPECTS]:
                typ = a.get("type")
                wit = a.get("with")
                orb = a.get("orb")
                orb_txt = f"{orb:.2f}" if isinstance(orb, (int, float)) else str(orb)
                lines.append(f"- {typ} avec {wit} (orbe {orb_txt}°)")
            lines.append("")
    
    # ==================
    # ASSEMBLAGE FINAL
    # ==================
    content = _join([
        "# Nœuds Lunaires — la boussole de ton âme",
        "",
        intro,
        "",
        *lines,
    ])

    summary = summarize_chapter(
        chapter_title="Nœuds Lunaires : ta boussole karmique",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )
    
    logger.debug("build_block_lunar_nodes: content_len=%s", len(content))
    logger.debug("contains maître section? %s", "Maître(s) du Nœud" in content)
    logger.debug("contains Conjonction? %s", "Conjonction" in content)
    logger.debug("sample: %s", content[0:600])
    
    return {
        "id": "lunar_nodes",
        "title": "Nœuds Lunaires : ta boussole karmique",
        "data": {
            "nn_sign": nn_sign,
            "nn_house": nn_house,
            "ns_sign": ns_sign,
            "ns_house": ns_house,
            "nn_rulers_details": nn_rulers_details,
            "ns_rulers_details": ns_rulers_details,
            "nn_aspects": nn_aspects,
            "ns_aspects": ns_aspects,
            "axis_square_planets": axis_square_planets,
            "nn_conjuncts_strong": nn_conjuncts_strong,
            "ns_conjuncts_strong": ns_conjuncts_strong,
            "ns_ruler_in_nn_house": ns_ruler_in_nn_house,
            "nn_ruler_in_ns_house": nn_ruler_in_ns_house,
            "ns_rulers_retrograde": ns_rulers_retrograde,
            "nn_rulers_retrograde": nn_rulers_retrograde,
            "ns_rulers_intercepted": ns_rulers_intercepted,
            "nn_rulers_intercepted": nn_rulers_intercepted,             
        },
        "content": content,
        "text": content,
        "summary": summary,

    }

def interpret_block_lunar_nodes_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Chapitre Nœuds Lunaires : version Point Astral karmique.
    On transforme le bloc 'content' en un texte client-friendly.
    """
    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    data = block.get("data") or {}

    nn_sign = data.get("nn_sign")
    ns_sign = data.get("ns_sign")
    nn_house = data.get("nn_house")
    ns_house = data.get("ns_house")
    nn_conjuncts_strong = data.get("nn_conjuncts_strong", [])
    ns_conjuncts_strong = data.get("ns_conjuncts_strong", [])
    ns_ruler_in_nn_house = data.get("ns_ruler_in_nn_house", [])
    nn_ruler_in_ns_house = data.get("nn_ruler_in_ns_house", [])
    ns_rulers_retrograde = data.get("ns_rulers_retrograde", [])
    nn_rulers_retrograde = data.get("nn_rulers_retrograde", [])
    ns_rulers_intercepted = data.get("ns_rulers_intercepted", [])
    nn_rulers_intercepted = data.get("nn_rulers_intercepted", [])
    axis_square_planets = data.get("axis_square_planets", [])
    nn_rulers_details = data.get("nn_rulers_details", [])
    ns_rulers_details = data.get("ns_rulers_details", [])   

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    karmic_ctx_txt = (global_ctx or {}).get("karmic_context", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("lunar_nodes", "")

    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    # 🔥 on limite pour éviter surcharge
    memories_txt = "\n".join(memories[-3:]) if memories else "aucune mémoire disponible"
    logger.debug("memories_txt = %s", memories_txt)

    cross_pattern_lines = []

    if ns_ruler_in_nn_house:
        cross_pattern_lines.append(
            f"Le maître du Nœud Sud tombe dans la maison du Nœud Nord : {', '.join(ns_ruler_in_nn_house)}"
        )

    if nn_ruler_in_ns_house:
        cross_pattern_lines.append(
            f"Le maître du Nœud Nord tombe dans la maison du Nœud Sud : {', '.join(nn_ruler_in_ns_house)}"
        )

    cross_pattern_txt = "\n".join(cross_pattern_lines) if cross_pattern_lines else "aucun croisement nodal majeur"
    axis_square_lines = []

    for a in axis_square_planets:
        planet = a.get("with")
        orb = a.get("orb")

        axis_square_lines.append(
            f"{planet} est en carré à l'axe nodal (orbe {orb}°)"
        )

    axis_square_txt = "\n".join(axis_square_lines) if axis_square_lines else "aucun carré majeur à l'axe nodal"

    strong_conj_txt_parts = []

    for a in ns_conjuncts_strong:
        strong_conj_txt_parts.append(
            f"Nœud Sud conjoint à {a.get('with')} (orbe {a.get('orb')}°)"
        )

    for a in nn_conjuncts_strong:
        strong_conj_txt_parts.append(
            f"Nœud Nord conjoint à {a.get('with')} (orbe {a.get('orb')}°)"
        )

    strong_conj_txt = "\n".join(strong_conj_txt_parts) if strong_conj_txt_parts else "Aucune conjonction nodale majeure."

    retro_lines = []

    if ns_rulers_retrograde:
        retro_lines.append(
            f"Maître(s) du Nœud Sud rétrograde(s) : {', '.join(ns_rulers_retrograde)}"
        )

    if nn_rulers_retrograde:
        retro_lines.append(
            f"Maître(s) du Nœud Nord rétrograde(s) : {', '.join(nn_rulers_retrograde)}"
        )

    retro_txt = "\n".join(retro_lines) if retro_lines else "Aucun maître rétrograde."

    master_aspects_lines = []

    for d in ns_rulers_details:
        nm = d.get("name")
        aspects = sorted(d.get("aspects", []) or [], key=_aspect_priority)


        for asp in aspects[:MAX_ASPECTS]:
            master_aspects_lines.append(
                f"Maître du Nœud Sud {nm} : {asp.get('type')} avec {asp.get('with')} (orbe {asp.get('orb')}°)"
            )

    for d in nn_rulers_details:
        nm = d.get("name")
        aspects = sorted(d.get("aspects", []) or [], key=_aspect_priority)

        for asp in aspects[:MAX_ASPECTS]:
            master_aspects_lines.append(
                f"Maître du Nœud Nord {nm} : {asp.get('type')} avec {asp.get('with')} (orbe {asp.get('orb')}°)"
            )

    master_aspects_txt = "\n".join(master_aspects_lines) if master_aspects_lines else "Aucun aspect majeur des maîtres nodaux."

    intercept_lines = []

    if ns_rulers_intercepted:
        intercept_lines.append(
            f"Maître(s) du Nœud Sud intercepté(s) : {', '.join(ns_rulers_intercepted)}"
        )

    if nn_rulers_intercepted:
        intercept_lines.append(
            f"Maître(s) du Nœud Nord intercepté(s) : {', '.join(nn_rulers_intercepted)}"
        )

    intercept_txt = "\n".join(intercept_lines) if intercept_lines else "Aucune interception des maîtres nodaux."

    content_for_prompt = content[:3000] if len(content) > 3000 else content


    prompt = f"""
Tu es astrologue karmique à l’approche psychologique jungienne, directe avec une pointe de mordant.  
Tu réécris le chapitre dédié à l’Axe des Nœuds Lunaires d’une analyse karmique déjà en cours.  

**TON ET STYLE**
- Tutoiement direct {genre_txt}.  
- Adresse‑toi directement à la personne, sans jamais citer son prénom ni son thème.  
- INTERDIT : « Dans le thème de... », « Le Soleil pousse... », « Ton Nœud Sud te montre... ».  
- Style incarné, psychologique, dense : pas de phrases creuses, pas de développement personnel cliché type « chemin de lumière » ou « mission de l’âme ».  
- Ton sérieux, avec une légère touche d’ironie qui relativise les illusions du Nœud Sud sans tendresse ni jugement.  
- L’analyse démarre directement dans le vif du sujet : pas d’introduction, pas de prénom, pas de rappel évident. Elle prolonge naturellement le chapitre précédent.  

**RÉPONSE REQUISE (STRUCTURE IMPLICITE)**
- Paragraphe 1 : Nœud Sud comme automatisme refuge, compétence innée devenue piège d’involution, « déjà‑vu » karmique.  
- Paragraphe 2 : Nœud Nord comme saut évolutif exigé, zone de croissance inconfortable mais salvatrice, avec les freins et leviers psychologiques.  
- Paragraphe 3 : Trajectoire de vie concrète : comment l’individu traverse la tension Sud/Nord, sans mélanger crises de destruction (Maison 8) ni arrière‑plan inconscient (Maison 12).  
- Format : flux continu, 3 paragraphes denses (~250–300 mots). Zéro titre, zéro liste, zéro jargon vaseux.  

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
Montrer la boussole évolutive de l’individu, le passage du connu à l’inconnu :  
- Nœud Sud : l’automatisme refuge, la compétence innée devenue un piège d’involution, le « déjà‑vu » karmique.  
- Nœud Nord : le saut évolutif exigé, la zone de croissance inconfortable mais salvatrice.  
- Focus exclusif : la tension et le mouvement entre ces deux pôles.  
- Ne touche ni aux crises de destruction/régénération (Maison 8) ni à l’arrière‑plan inconscient (Maison 12).  
- Ici, tu décris une *trajectoire* de vie, pas une photo statique.  

**MÉMOIRE DE RÉDACTION (ACQUIS PSYCHOLOGIQUES)**
Voici les concepts psychologiques déjà explorés dans les chapitres précédents :  
{memories_txt}  

**RÈGLES ANTI-REDONDANCE IMPÉRATIVES**
- Ne ré‑explique pas les dynamiques déjà listées ci‑dessus.  
- Si le Nœud Sud s’appuie sur une peur ou un schéma déjà évoqué, traite‑le comme un acquis psychologique de l’utilisateur et concentre‑toi sur *comment s’en extraire* via le Nœud Nord.  
- N’oxyte pas le thème central précédent : apporte uniquement la clé de mouvement (comment on passe d’un Nœud à l’autre).  
- Si une dynamique est déjà décrite, tu ne la répètes pas, seulement tu montres comment l’évoquer à travers le Nœud Nord.  

**UNITÉ DE L'AXE ET INTÉGRATION TECHNIQUE**
- Parle toujours l’Axe des Nœuds dans son ensemble : ne sépare jamais le Nœud Sud du Nœud Nord.  
- Intègre les maîtres des Nœuds et leurs aspects comme leviers ou freins psychologiques, jamais comme analyse technique isolée.  
- Utilise les placements, aspects et croisements pour donner des pistes concrètes : comportements, stratégies, blocages, ruptures.  
- Limite le jargon astrologique : explique les effets plutôt que les formules.  

**RÈGLES STRICTES DE RÉDACTION**
- Flux continu uniquement.  
- Zéro titre, zéro liste à puces, zéro numérotation.  
- Pas de métaphores New‑Age du type « chemin de lumière », « mission de l’âme », « se reconnecter à soi ».  
- Remplace les formulations vagues par des verbes d’action psychologique : s’extraire, déjouer, intégrer, trahir, répéter, forcer, fuir, tracter.  
- Si le texte devient flou, ramène‑toi immédiatement à un signe, une maison, un maître, un aspect, un carré ou une rétrogradation comme support concret.  

**CONTEXTE ET DONNÉES TECHNIQUES À TRANSFORMER**
Axe central : {axe_central}  
Contexte global : {theme_brief}  
Contexte karmique spécifique : {karmic_ctx_txt}  

Placements à analyser :  
- Nœud Sud : {ns_sign} en Maison {ns_house}  
- Nœud Nord : {nn_sign} en Maison {nn_house}  

Conjonctions nodales majeures à prioriser :  
{strong_conj_txt}  

Croisements karmiques majeurs :  
{cross_pattern_txt}  

Planètes en carré à l’axe nodal :  
{axis_square_txt}  

Rétrogradations karmiques importantes :  
{retro_txt}  

Interceptions karmiques importantes :
{intercept_txt}

Aspects importants des maîtres nodaux :  
{master_aspects_txt}  

Données brutes BDD : {content_for_prompt}  

[Début de l'analyse en flux continu :]
""".strip()


    logger.debug("PROMPT NOEUDS LUNAIRES:\n%s", prompt)
    print("\n=== DEBUG BLOCS STRUCTURÉS NOEUDS ===")
    print("strong_conj_txt =", strong_conj_txt)
    print("cross_pattern_txt =", cross_pattern_txt)
    print("axis_square_txt =", axis_square_txt)
    print("intercept_txt =", intercept_txt)
    print("retro_txt =", retro_txt)
    print("master_aspects_txt =", master_aspects_txt)
    print("content_for_prompt présent =", "content_for_prompt" in locals())
    print("=== FIN DEBUG BLOCS STRUCTURÉS ===\n")

    texte = (call_llm(prompt) or "").strip()

    logger.debug("RÉPONSE LLM NOEUDS LUNAIRES:\n%s", texte)

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte