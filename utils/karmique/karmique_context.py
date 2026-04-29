# utils/karmique/karmique_context.py

from typing import Any, Dict, List, Optional, Tuple
from utils.utils_points_forts import extraire_points_forts
import re



def _get(p: Dict[str, Any], *keys, default=None):
    """Retourne la 1ère clé trouvée parmi keys."""
    for k in keys:
        if isinstance(p, dict) and k in p and p[k] is not None:
            return p[k]
    return default


def _format_pos(p: Dict[str, Any]) -> str:
    """Formate une position planète de manière lisible pour le LLM."""
    deg = _get(p, "deg_in_sign", "degre_dans_signe")
    sign = _get(p, "sign", "signe")
    house = _get(p, "house", "maison")

    if deg is None or sign is None:
        return ""

    # arrondi clean
    try:
        deg = round(float(deg), 2)
    except Exception:
        pass

    if house is not None:
        return f"{deg}° {sign} – Maison {house}"
    return f"{deg}° {sign}"

def get_moon_prev_next(theme: dict, max_orb_deg: float = 15.0) -> dict:
    planetes = theme.get("planetes", {}) or {}
    moon = planetes.get("Lune")
    if not isinstance(moon, dict):
        return {}

    moon_deg = moon.get("degre")
    if moon_deg is None:
        return {}

    try:
        moon_deg = float(moon_deg)
    except Exception:
        return {}


    items = []
    for name, p in planetes.items():
        if not isinstance(p, dict):
            continue
        if name == "Lune":
            continue
        deg = p.get("degre")
        if deg is None:
            continue
        try:
            degf = float(deg)
        except Exception:
            continue

        items.append((degf, name, p))

    if not items:
        return {}

    items.sort(key=lambda x: x[0])

    # trouver index d'insertion de la lune
    # prev = dernier deg < lune, next = premier deg > lune (avec wrap)
    prev = None
    nextp = None

    for deg, name, p in items:
        if deg < moon_deg:
            prev = (deg, name, p)
        elif deg > moon_deg and nextp is None:
            nextp = (deg, name, p)

    if prev is None:
        prev = items[-1]
    if nextp is None:
        nextp = items[0]

    prev_deg, prev_name, prev_p = prev
    next_deg, next_name, next_p = nextp

    # orbes en avançant sur le cercle
    orb_prev = (moon_deg - prev_deg) % 360
    orb_next = (next_deg - moon_deg) % 360

    out = {"moon_deg": moon_deg}

    # inclure seulement si <= max_orb_deg
    if orb_prev <= max_orb_deg:
        out["prev"] = {
            "name": prev_name,
            "orb": round(orb_prev, 2),
            "pos": {
                "degre": prev_deg,
                "signe": _get(prev_p, "signe", "sign"),
                "degre_dans_signe": _get(prev_p, "degre_dans_signe", "deg_in_sign"),
                "maison": _get(prev_p, "maison", "house"),
                "retrograde": prev_p.get("retrograde", False),
            }
        }

    if orb_next <= max_orb_deg:
        out["next"] = {
            "name": next_name,
            "orb": round(orb_next, 2),
            "pos": {
                "degre": next_deg,
                "signe": _get(next_p, "signe", "sign"),
                "degre_dans_signe": _get(next_p, "degre_dans_signe", "deg_in_sign"),
                "maison": _get(next_p, "maison", "house"),
                "retrograde": next_p.get("retrograde", False),
            }
        }

    # si rien retenu, on renvoie {} (tu voulais "s'il y a lieu seulement")
    if "prev" not in out and "next" not in out:
        return {}

    return out

def build_global_context(theme: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    meta = score.get("meta", {}) or {}
    planetes = theme.get("planetes", {}) or {}

    # --- Positions planétaires occidentales (TOUT) ---
    planets_western: Dict[str, str] = {}

    for nom, p in planetes.items():
        if not isinstance(p, dict):
            continue
        txt = _format_pos(p)
        if txt:
            planets_western[nom] = txt

    # Bonus : ajouter l’Ascendant aussi dans planets_western (comme tu veux l’avoir)
    asc = theme.get("ascendant")
    if "Ascendant" not in planets_western and isinstance(asc, dict):
        asc_txt = _format_pos(asc)
        if asc_txt:
            planets_western["Ascendant"] = asc_txt

    context = {
        "identity": {"name": theme.get("nom")},
        "theme_brief": build_theme_brief_for_llm(theme, max_lines=20),

        "planets_western": planets_western,

        "astro_global": {
            "ascendant": theme.get("ascendant"),
            "sun": planetes.get("Soleil"),
            "moon": planetes.get("Lune"),
        },

        "elements": {
            "dominant_elements": _get(meta, "dominant_elements"),
            "elements_count": _get(meta, "elements_count"),
        },

        "karmic_score": {
            "total": score.get("total"),
            "label": score.get("label"),
            "level_code": score.get("level_code"),
            "breakdown": score.get("breakdown"),
        },

        "lunar_nodes": {
            "nn_sign": _get(meta, "nn_sign"),
            "nn_house": _get(meta, "nn_house"),
            "ns_sign": _get(meta, "ns_sign"),
            "ns_house": _get(meta, "ns_house"),
            "nn_rulers": _get(meta, "nn_rulers"),
            "ns_rulers": _get(meta, "ns_rulers"),
        },

        "karmic_flags": {
            "houses_karmic": _get(meta, "houses_karmic"),
            "anaretic_29": _get(meta, "anaretic_29"),
            "saturn_pluto": _get(meta, "saturn_pluto"),
        },

        "context_moon_flow": get_moon_prev_next(theme, max_orb_deg=15.0),
    }

    return context

def build_karmic_context_for_llm(theme: Dict[str, Any], score: Dict[str, Any], max_lines: int = 20) -> str:
    """
    Contexte karmique compact à injecter dans tous les prompts LLM.
    Objectif : donner au LLM les signaux "karmiques" déjà calculés (rétros, interceptions, anaretic, etc.)
    + focus sur maîtres des Nœuds (NS/NN) si disponibles dans score.meta.
    """
    meta = (score or {}).get("meta", {}) or {}
    planetes = (theme or {}).get("planetes", {}) or {}
    pf = extraire_points_forts(theme) or []

    lines: List[str] = []
    lines.append("Contexte karmique (signaux rapides) :")

    # --- Axe nodal + maîtres (si présents) ---
    ns_sign = meta.get("ns_sign")
    nn_sign = meta.get("nn_sign")
    ns_house = meta.get("ns_house")
    nn_house = meta.get("nn_house")

    if ns_sign and nn_sign:
        lines.append(f"- Axe : {ns_sign} (NS) → {nn_sign} (NN)")
    if ns_house is not None and nn_house is not None:
        lines.append(f"- Maisons : NS {ns_house} / NN {nn_house}")

    # Détails des maîtres (les tiens existent : ns_rulers_details / nn_rulers_details)
    ns_details = meta.get("ns_rulers_details") or []
    nn_details = meta.get("nn_rulers_details") or []

    def _fmt_ruler(d: Dict[str, Any]) -> str:
        name = d.get("name")
        house = d.get("house")
        if not name:
            return ""
        p = planetes.get(name, {}) if isinstance(planetes.get(name), dict) else {}
        sign = p.get("signe")
        deg = p.get("degre_dans_signe")
        rx = p.get("retrograde")
        rx_txt = " rétrograde" if rx else ""
        if deg is not None and sign:
            try:
                deg = round(float(deg), 2)
                pos = f"{sign} {deg}°"
            except Exception:
                pos = f"{sign}"
        else:
            pos = sign or ""
        htxt = f" M{house}" if house is not None else ""
        return f"{name} ({pos}{htxt}{rx_txt})".strip()

    if ns_details:
        lines.append("- Maître(s) du Nœud Sud : " + " ; ".join(filter(None, [_fmt_ruler(d) for d in ns_details])))
    if nn_details:
        lines.append("- Maître(s) du Nœud Nord : " + " ; ".join(filter(None, [_fmt_ruler(d) for d in nn_details])))

    # --- “Flags” déjà calculés dans ton score/meta ---
    flags = (meta.get("houses_karmic") or []) + (meta.get("anaretic_29") or [])
    if meta.get("saturn_pluto"):
        flags.append("Saturne/Pluton activé")
    if flags:
        lines.append("- Drapeaux : " + ", ".join([str(x) for x in flags if x]))

    # --- Rétrogrades / interceptions / dignités / degrés karmiques (si déjà dans points forts) ---
    # On prend quelques lignes "parlantes" sans refaire les calculs ici.
    keywords = ("rétro", "intercept", "domicile", "exalt", "chute", "détriment", "29°", "0°")
    picked = [l for l in pf if any(k in l.lower() for k in keywords)]
    for l in picked[:6]:
        lines.append(f"- {l}")

    # --- Nettoyage / limite ---
    clean = [x.strip() for x in lines if x and x.strip()]
    if max_lines:
        clean = clean[:max_lines]
    return "\n".join(clean)

# --- helpers -------------------------------------------------

def _occ(data: Dict[str, Any]) -> Dict[str, Any]:
    return data.get("planetes") or data.get("placements_occidentaux") or data.get("placements_occ") or {}

def _fmt_basic(p: Dict[str, Any]) -> str:
    """ex: 'Balance (14.39°)'"""
    if not isinstance(p, dict):
        return ""
    signe = p.get("signe")
    deg = p.get("degre_dans_signe")
    if signe is None:
        return ""
    if deg is None:
        return f"{signe}"
    try:
        deg = round(float(deg), 2)
        return f"{signe} ({deg}°)"
    except Exception:
        return f"{signe}"

def _get_node_positions(occ: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    # tolère Rahu/Ketu + Nœud Nord/Sud
    nn = occ.get("Rahu") or occ.get("Nœud Nord") or occ.get("Noeud Nord")
    ns = occ.get("Ketu") or occ.get("Nœud Sud") or occ.get("Noeud Sud")
    def _pos(x):
        if not isinstance(x, dict):
            return None
        s = x.get("signe")
        h = x.get("maison")
        if s is None and h is None:
            return None
        return f"{s or '?'} maison {h if h is not None else '?'}"
    return _pos(nn), _pos(ns)

_ASP_ORB_RE = re.compile(r"\(orbe\s*([\d\.,]+)°\)", re.I)

def _orbe_of(line: str) -> Optional[float]:
    m = _ASP_ORB_RE.search(line or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None

def _is_aspect_line(line: str) -> bool:
    t = (line or "").lower()
    return any(k in t for k in [" conjonction ", " opposition ", " carré ", " carre ", " trigone ", " sextile "])

def _is_amas_line(line: str) -> bool:
    t = (line or "").lower()
    return "amas" in t

def _is_angulaire_line(line: str) -> bool:
    t = (line or "").lower()
    return "maison angulaire" in t or "angle" in t or "conjonction avec l'angle" in t

def _is_dominance_line(line: str) -> bool:
    t = (line or "").lower()
    return t.startswith("dominance ") or "dominance" in t or "singleton/absence" in t

def _house_clusters(occ: Dict[str, Any], min_n: int = 3) -> List[str]:
    """Maison X : A, B, C (classiques uniquement)"""
    classiques = {"Soleil","Lune","Mercure","Vénus","Mars","Jupiter","Saturne","Uranus","Neptune","Pluton"}
    by_house: Dict[int, List[str]] = {}
    for pl, d in (occ or {}).items():
        if pl not in classiques:
            continue
        if not isinstance(d, dict):
            continue
        h = d.get("maison")
        try:
            h = int(h)
        except Exception:
            continue
        by_house.setdefault(h, []).append(pl)

    out = []
    for h, membres in sorted(by_house.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(membres) >= min_n:
            out.append(f"Maison {h} : {', '.join(membres)}")
    return out


# --- main ----------------------------------------------------

def build_theme_brief_for_llm(data_theme: Dict[str, Any], max_lines: int = 25) -> str:
    """
    Brief hiérarchisé pour injection LLM.
    Priorités :
    1. Identité (Asc / Soleil / Lune)
    2. Amas personnels forts
    3. Dignités majeures
    4. Planètes angulaires structurantes
    5. Dominante
    6. Axe karmique
    7. Aspects serrés structurants
    """

    occ = data_theme.get("planetes", {}) or {}
    ident = data_theme.get("nom") or "—"

    # Dépendance centrale : extraire_points_forts() doit retourner une liste de chaînes lisibles.
    # Ce fichier filtre ces chaînes par mots-clés pour construire un brief LLM compact.

    pf = extraire_points_forts(data_theme) or []

    # --------- IDENTITÉ ---------
    asc = occ.get("Ascendant", {})
    sun = occ.get("Soleil", {})
    moon = occ.get("Lune", {})

    lines = []
    lines.append(f"Identité : {ident}")

    if asc:
        deg = asc.get("degre_dans_signe")
        try:
            deg = round(float(deg), 2)
            lines.append(f"Ascendant {asc.get('signe')} ({deg}°)")
        except Exception:
            lines.append(f"Ascendant {asc.get('signe')}")

    if sun:
        lines.append(f"Soleil {sun.get('signe')} — Maison {sun.get('maison')}")

    if moon:
        lines.append(f"Lune {moon.get('signe')} — Maison {moon.get('maison')}")

    # --------- AMAS (uniquement personnels, sans Junon/POF) ---------
    amas = []
    seen_groups = set()

    for line in pf:
        if "🌟 Amas personnel" in line:
            if any(x in line for x in ["Junon", "Part de Fortune"]):
                continue
            try:
                key = tuple(sorted([p.strip() for p in line.split("(")[1].split(")")[0].split(",")]))
            except Exception:
                key = (line,)
            if key not in seen_groups:
                amas.append(line)
                seen_groups.add(key)

    if amas:
        lines.append("")
        lines.extend(amas[:2])

    # --------- DIGNITÉS ---------
    dignites = [
        l for l in pf
        if "domicile" in l.lower() or "exaltation" in l.lower()
    ]
    if dignites:
        lines.append("")
        lines.append("Dignités fortes :")
        for d in dignites[:3]:
            lines.append(f"- {d}")

    # --------- ANGULAIRES STRUCTURANTES ---------
    angulaires = [
        l for l in pf
        if "maison angulaire" in l
        and any(x in l for x in ["Soleil", "Pluton", "Saturne", "Uranus", "Lune Noire", "Rahu", "Ketu"])
    ]

    if angulaires:
        lines.append("")
        lines.append("Planètes angulaires majeures :")
        for a in angulaires[:4]:
            lines.append(f"- {a}")

    # --------- DOMINANTE ---------
    dominantes = [l for l in pf if "Dominance" in l]
    if dominantes:
        lines.append("")
        lines.append("Dominante :")
        lines.append(f"- {dominantes[0]}")

    # --------- AXE KARMIQUE ---------
    nn = occ.get("Rahu")
    ns = occ.get("Ketu")

    if nn and ns:
        lines.append("")
        lines.append("Axe karmique :")
        lines.append(
            f"Ketu {ns.get('signe')} Maison {ns.get('maison')} → "
            f"Rahu {nn.get('signe')} Maison {nn.get('maison')}"
        )

    # --------- ASPECTS STRUCTURANTS (≤3°) ---------
    aspects_serres = []
    for l in pf:
        if any(x in l.lower() for x in ["conjonction", "opposition", "carré", "carre"]):
            if "orbe" in l.lower():
                o = _orbe_of(l)
                if o is not None and o <= 3:
                    aspects_serres.append(l)

    if aspects_serres:
        lines.append("")
        lines.append("Aspects structurants :")
        for a in aspects_serres[:5]:
            lines.append(f"- {a}")

    # --------- NETTOYAGE ---------
    clean = [l.strip() for l in lines if l.strip() != ""]
    if max_lines:
        clean = clean[:max_lines]

    return "\n".join(clean)


