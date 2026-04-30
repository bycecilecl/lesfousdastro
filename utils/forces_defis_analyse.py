# utils/forces_defis_analyse.py
from __future__ import annotations

from utils.selection_donnees import construire_selection_point_astral
from utils.openai_utils import interroger_llm
from utils.convert_markdown_light import md_light_to_html
from utils.fd_inject import build_unified_priorities
import logging
logger = logging.getLogger(__name__)

# ---------- Intro hint: générique & robuste ----------
_PERSONNELLES = {"Soleil","Lune","Mercure","Vénus","Venus","Mars"}
_SOCIALES     = {"Jupiter","Saturne"}

def _list_retrogrades(theme: dict) -> list[str]:
    occ = theme.get("planetes", {}) or {}
    out = []
    for nom, p in occ.items():
        flags = p.get("flags") or []
        if p.get("retro") or p.get("retrograde") or p.get("r") or ("retro" in flags):
            out.append(nom)
    def _key(n):
        if n in _PERSONNELLES: return (0, n)
        if n in _SOCIALES:     return (1, n)
        return (2, n)
    return sorted(out, key=_key)

def _list_angulaires(theme: dict) -> list[str]:
    occ = theme.get("planetes", {}) or {}
    out = []
    for nom, p in occ.items():
        h = p.get("maison") or p.get("house")
        if str(h) in {"1","10"}:
            out.append(f"{nom} (M{h})")
    def _key(s):
        if "(M1)" in s:  return (0, s)
        if "(M10)" in s: return (1, s)
        return (2, s)
    return sorted(out, key=_key)

def _list_stelliums(theme: dict) -> list[str]:
    """
    1) Si theme['amas'] existe: on résume.
    2) Sinon, stellium = ≥3 planètes dans le même signe (avec au moins 2 perso/sociales).
    """
    amas = theme.get("amas")
    lines = []
    if isinstance(amas, list) and amas:
        for a in amas:
            try:
                signe = a.get("signe") or a.get("sign")
                pls = a.get("planetes") or a.get("planets") or []
                if signe and len(pls) >= 3:
                    lines.append(f"Stellium en {signe} ({', '.join(pls[:6])}{'…' if len(pls)>6 else ''})")
            except Exception:
                continue
        if lines:
            return lines

    occ = theme.get("planetes", {}) or {}
    par_signe = {}
    for nom, p in occ.items():
        if nom in {"Ascendant","Milieu du Ciel","MC"}: 
            continue
        signe = p.get("signe") or p.get("sign")
        if not signe: 
            continue
        par_signe.setdefault(signe, []).append(nom)

    out = []
    for signe, noms in par_signe.items():
        if len(noms) >= 3:
            nb_ps = sum(1 for n in noms if (n in _PERSONNELLES or n in _SOCIALES))
            if nb_ps >= 2:
                out.append(f"Stellium en {signe} ({', '.join(sorted(noms)[:6])}{'…' if len(noms)>6 else ''})")
    return out

def _retro_personnelles(theme: dict) -> list[str]:
    occ = theme.get("planetes", {}) or {}
    perso = {"Mercure", "Vénus", "Venus", "Mars"}
    out = []
    for nom, p in occ.items():
        if nom not in perso:
            continue
        flags = p.get("flags") or []
        if p.get("retro") or p.get("retrograde") or p.get("r") or ("retro" in flags):
            out.append("Vénus" if nom == "Venus" else nom)
    ordre = {"Mercure": 0, "Vénus": 1, "Mars": 2}
    return sorted(out, key=lambda x: ordre.get(x, 99))

def build_intro_hint(theme: dict, max_parts: int = 3) -> str:
    """Construit un résumé compact : stelliums, angulaires, et rétrogrades si >= 2 personnelles."""
    parts = []

    sts = _list_stelliums(theme)
    if sts:
        parts.extend(sts[:2])

    ang = _list_angulaires(theme)
    if ang:
        parts.append(
            "Planètes angulaires (I/X) : "
            + (", ".join(ang[:3]) + ("…" if len(ang) > 3 else ""))
        )

    ret_pers = _retro_personnelles(theme)
    if len(ret_pers) >= 2:
        parts.append(f"- Planètes personnelles rétrogrades : {', '.join(ret_pers)}")

    parts = [p for p in parts if p][:max_parts]
    return " — ".join(parts)

# --- Détection locale des planètes rétrogrades ---
DISPLAY_FIX = {"Venus": "Vénus"}

def _detecter_retrogrades_locales(occ: dict) -> list[str]:
    """Détecte les planètes rétrogrades sans dépendre de selection_donnees.py."""
    retro_list = []
    for nom, data in (occ or {}).items():
        if not isinstance(data, dict):
            continue
        is_retro = (
            data.get("retrograde") is True
            or data.get("retro") is True
            or data.get("r") is True
            or ("flags" in data and isinstance(data["flags"], list) and "retro" in data["flags"])
        )
        if is_retro:
            retro_list.append(nom)
    return retro_list

def get_retrogrades_occidentales(data_theme: dict) -> list[str]:
    """Récupère la liste des planètes rétrogrades (occidentales)."""
    occ = (
        data_theme.get("planetes")
        or data_theme.get("placements_occidentaux")
        or data_theme.get("placements_occ")
        or data_theme.get("resultats_tropical")
        or {}
    )
    return [DISPLAY_FIX.get(name, name) for name in _detecter_retrogrades_locales(occ)]

DISCLAIMER_FORCES_DEFIS_HTML = r"""
<div style="display:flex;justify-content:center;margin:12px 0 18px;">
  <div style="max-width:720px;width:100%;
              border-top:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;
              padding:10px 14px;font-size:12.5px;line-height:1.55;color:#555;">
    <p style="margin:0 0 6px 0;">
      <strong style="font-weight:600;">À lire avant l'analyse</strong> — texte généré automatiquement à partir de
      placements saillants (aspects, maisons, angles). Les « forces » et « défis » sont analysés
      <strong>de manière isolée</strong>, sans prendre en compte tout l'ensemble du thème.
      Ce n'est <em>pas</em> une consultation : l'interprétation dépend de ton histoire et de ton niveau d'intégration.
      Pour une lecture <strong>plus complète</strong> (liens entre tous les éléments), consulte le <em>Flash Astral</em>
      — ou réserve une <strong>consultation</strong> personnalisée.
      <a href="https://bycecilecl.com" target="_blank" style="color:#1f628e;text-decoration:none;">Prendre rendez-vous</a>
    </p>
  </div>
</div>
"""

try:
    from utils.forces_defis import generer_forces_defis as _GENERER_FORCES_DEFIS
except Exception:
    _GENERER_FORCES_DEFIS = None

try:
    from utils.forces_defis import extraire_forces_defis_par_maisons
except Exception:
    def extraire_forces_defis_par_maisons(_):
        return None

def _build_bloc_theme_occidental_depuis_selector(theme: dict) -> str:
    """Construction des placements via construire_selection_point_astral."""
    try:
        bloc = construire_selection_point_astral(theme, max_orbe=5.0)
        return bloc if isinstance(bloc, str) else ""
    except Exception:
        return ""

def _coerce_name(x):
    """Convertit id/dict/label -> nom lisible."""
    if x is None:
        return None
    if isinstance(x, dict):
        for k in ("name", "nom", "label", "planet", "body", "point"):
            if x.get(k):
                return str(x[k])
        for k in ("id", "key", "code"):
            if x.get(k):
                return str(x[k])
        return None
    if isinstance(x, (str, int)):
        return str(x)
    return None

def _extract_names_types_orb(a):
    """Extrait p1, type, p2, orbe d'un aspect."""
    if isinstance(a, str):
        import re
        m = re.search(
            r"([A-Za-zÀ-ÖØ-öø-ÿ''\-]+)\s+"
            r"(Conjonction|Sextile|Trigone|Carr[ée]?|Opposition|Quinconce|"
            r"Conjunction|Trine|Square|Opposition|Quincunx)"
            r"\s+([A-Za-zÀ-ÖØ-öø-ÿ''\-]+)",
            a, flags=re.I
        )
        orb = None
        m_orb = re.search(r"orbe\s*([0-9]+(?:\.[0-9]+)?)", a, flags=re.I)
        if m_orb:
            try:
                orb = float(m_orb.group(1))
            except Exception:
                pass
        if m:
            return m.group(1), m.group(2), m.group(3), orb
        return "?", "?", "?", orb

    if not isinstance(a, dict):
        return "?", "?", "?", None

    t = (a.get("type") or a.get("aspect") or a.get("relation") or 
         a.get("aspect_type") or a.get("kind") or "?")

    p1 = (a.get("p1") or a.get("planet1") or a.get("A") or a.get("a") or 
          a.get("body1") or a.get("point1") or a.get("planete1") or
          a.get("from") or a.get("source"))
    p2 = (a.get("p2") or a.get("planet2") or a.get("B") or a.get("b") or 
          a.get("body2") or a.get("point2") or a.get("planete2") or
          a.get("to") or a.get("target"))

    if isinstance(p1, dict): p1 = _coerce_name(p1)
    if isinstance(p2, dict): p2 = _coerce_name(p2)

    if not p1 or not p2:
        planets_list = a.get("planets") or a.get("p") or a.get("bodies") or a.get("points") or a.get("pair") or []
        if isinstance(planets_list, (list, tuple)) and len(planets_list) >= 2:
            p1 = p1 or _coerce_name(planets_list[0])
            p2 = p2 or _coerce_name(planets_list[1])

    if (not p1 or not p2) and (a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text")):
        label = a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text")
        import re
        m = re.search(
            r"([A-Za-zÀ-ÖØ-öø-ÿ''\-]+)\s+"
            r"(Conjonction|Sextile|Trigone|Carr[ée]?|Opposition|Quinconce|"
            r"Conjunction|Trine|Square|Opposition|Quincunx)"
            r"\s+([A-Za-zÀ-ÖØ-öø-ÿ''\-]+)",
            label, flags=re.I
        )
        if m:
            p1 = p1 or m.group(1)
            t  = t  if t != "?" else m.group(2)
            p2 = p2 or m.group(3)

    orb = a.get("orb") or a.get("orbe") or a.get("delta") or a.get("d")
    try:
        orb = float(orb) if orb is not None else None
    except Exception:
        orb = None

    t_low = (t or "").lower()
    MAP = {"conjunction": "Conjonction", "trine": "Trigone", "square": "Carré"}
    if t_low in MAP: t = MAP[t_low]
    elif t == "?":   t = "?"

    p1 = p1 or "?"
    p2 = p2 or "?"

    return p1, t, p2, orb

def _fallback_generer_forces_defis(data_theme: dict) -> dict:
    forces, defis = [], []
    synthese = ""

    aspects = data_theme.get("aspects") or []
    if isinstance(aspects, list):
        for a in aspects[:40]:
            try:
                a_type = (a.get("type") or a.get("aspect") or "").lower()
                p1 = a.get("p1") or a.get("planet1") or a.get("A") or "Planète A"
                p2 = a.get("p2") or a.get("planet2") or a.get("B") or "Planète B"
                orb = a.get("orb") or a.get("orbe") or ""
                label = f"{p1} {a_type} {p2}".strip()
                if a_type in ("trigone", "sextile", "conjonction", "conjunction"):
                    forces.append(f"• {label} (orbe {orb}) : soutien naturel à mobiliser au quotidien.")
                elif a_type in ("carré", "carre", "opposition", "quincunx", "quinconce"):
                    defis.append(f"• {label} (orbe {orb}) : tension formatrice à intégrer avec méthode.")
            except Exception:
                continue

    for k in ("chiron", "Chiron"):
        if k in data_theme:
            defis.append("• Chiron actif : travail de guérison/réconciliation sur un axe clé.")
            break

    for k in ("lune_noire", "Lune Noire", "black_moon", "lilith"):
        if k in data_theme:
            defis.append("• Lune Noire présente : zones de radicalité ou de tabou à apprivoiser.")
            break

    noeuds = data_theme.get("noeuds") or data_theme.get("noeuds_lunaires") or {}
    if isinstance(noeuds, dict) and any(noeuds.values()):
        defis.append("• Nœuds lunaires marqués : trajectoire karmique/évolutive à harmoniser.")

    if forces or defis:
        synthese = "Potentiels identifiés à activer et tensions structurantes à transmuter."

    return {"forces": forces, "defis": defis, "synthese_courte": synthese}

def _normalize_aspect_type(t: str) -> str:
    """Ramène le type d'aspect à un libellé FR canonique."""
    if not t:
        return "?"
    if not isinstance(t, str):
        t = str(t)
    tl = t.strip().lower()
    mapping = {
        "conjunction": "conjonction",
        "conjonction": "conjonction",
        "trine": "trigone",
        "trigone": "trigone",
        "sextile": "sextile",
        "square": "carré",
        "carre": "carré",
        "carré": "carré",
        "opposition": "opposition",
        "quinconce": "quinconce",
        "quincunx": "quinconce",
    }
    return mapping.get(tl, tl)

_PLANET_ALIASES = {
    "sun": "Soleil", "soleil": "Soleil",
    "moon": "Lune", "lune": "Lune",
    "mercury": "Mercure", "mercure": "Mercure",
    "venus": "Vénus", "vénus": "Vénus", "venus": "Vénus",
    "mars": "Mars",
    "jupiter": "Jupiter",
    "saturn": "Saturne", "saturne": "Saturne",
    "uranus": "Uranus",
    "neptune": "Neptune",
    "pluto": "Pluton", "pluton": "Pluton",
    "asc": "Ascendant", "ascendant": "Ascendant",
    "mc": "Milieu du Ciel", "milieu du ciel": "Milieu du Ciel",
}

def _norm_planet(x: str) -> str:
    if not isinstance(x, str):
        return str(x or "?")
    key = x.strip().lower()
    return _PLANET_ALIASES.get(key, x.strip().title())

def _is_luminaire(x: str) -> bool:
    return _norm_planet(x) in {"Soleil", "Lune"}

def _is_lourde(x: str) -> bool:
    return _norm_planet(x) in {"Saturne", "Uranus", "Neptune", "Pluton", "Mars"}

def _is_personnelle(x: str) -> bool:
    return _norm_planet(x) in {"Soleil","Lune","Mercure","Vénus","Mars"}

def _is_angle(x: str) -> bool:
    return _norm_planet(x) in {"Ascendant","Milieu du Ciel"}

def _tight_orb_bonus(orb: float) -> int:
    if orb <= 1.0: return 6
    if orb <= 2.0: return 4
    if orb <= 3.0: return 2
    if orb <= 4.0: return 1
    return 0

def _pair_bonus(p1: str, typ: str, p2: str, orb: float) -> int:
    """Barème d'importance pour ne PAS rater les paires clés."""
    A, B = _norm_planet(p1), _norm_planet(p2)
    lum_lourde = ( (_is_luminaire(A) and _is_lourde(B)) or (_is_luminaire(B) and _is_lourde(A)) )
    if not lum_lourde:
        return 0

    lourde = B if _is_lourde(B) else A
    base = {
        "Pluton": 12,
        "Saturne": 10,
        "Mars": 9,
        "Uranus": 8,
        "Neptune": 7,
    }.get(_norm_planet(lourde), 6)

    if typ == "carré":
        base += 5
    elif typ == "conjonction":
        base += 4
    elif typ == "opposition":
        base += 2

    if typ == "conjonction":
        if orb > 7.0:
            return -999
        base += _tight_orb_bonus(orb)
        if orb <= 3.0 and (_is_personnelle(A) or _is_personnelle(B)):
            base += 1

    if _is_angle(A) or _is_angle(B):
        base += 2

    return base

def _filtrer_aspects_par_type(aspects_all, max_aspects=None):
    """Filtre et tri des aspects par importance."""
    ORB_LIMITS = {
        "conjonction": 8.0,
        "carré":       8.0,
        "opposition":  8.0,
        "trigone":     6.0,
        "sextile":     6.0,
    }

    HARD = {"carré", "opposition"}
    SOFT = {"trigone", "sextile"}

    keep = []

    for a in (aspects_all or []):
        p1, t, p2, orb = _extract_names_types_orb(a if isinstance(a, dict) else {"label": str(a)})
        typ = _normalize_aspect_type(t)

        if typ not in ORB_LIMITS:
            continue

        if orb is None and isinstance(a, dict):
            label = a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text") or ""
            import re
            m = re.search(r"orbe\s*([0-9]+(?:\.[0-9]+)?)", label, flags=re.I)
            if m:
                try:
                    orb = float(m.group(1))
                except Exception:
                    pass

        if not isinstance(orb, (int, float)):
            continue
        orb = float(orb)
        if orb > ORB_LIMITS[typ]:
            continue

        p1n, p2n = _norm_planet(p1), _norm_planet(p2)

        w = 0
        if typ in HARD:         w += 4
        elif typ == "conjonction": w += 3
        elif typ in SOFT:       w += 2

        w += _tight_orb_bonus(orb)
        w += _pair_bonus(p1n, typ, p2n, orb)

        if _is_angle(p1n) or _is_angle(p2n):
            w += 2

        keep.append({
            "p1": p1n, "p2": p2n, "typ": typ, "orb": orb, "w": w
        })

    keep.sort(key=lambda x: (-x["w"], x["orb"]))

    if isinstance(max_aspects, int) and max_aspects > 0:
        keep = keep[:max_aspects]

    def _fmt(row):
        return f"- {row['p1']} {row['typ'].capitalize()} {row['p2']} (orbe {row['orb']:.2f}°)"

    return [_fmt(r) for r in keep]

def _build_contexte_compact(theme: dict, max_aspects=20) -> dict:
    """Rassemble la matière utile pour Forces & Défis."""
    interceptions = theme.get("interceptions", {})
    inter_lines = []
    if isinstance(interceptions, dict) and interceptions:
        for axe, data in interceptions.items():
            if isinstance(data, dict):
                signes  = data.get("signes") or data.get("signs") or []
                maisonA = data.get("maisonA") or data.get("houseA")
                maisonB = data.get("maisonB") or data.get("houseB")
                if signes:
                    inter_lines.append(
                        f"- Axe {axe} intercepté : {', '.join(signes)} (Maisons {maisonA} / {maisonB})"
                    )

    def _fmt_placement(nom):
        obj = (theme.get("planetes") or {}).get(nom) or theme.get(nom.lower()) or {}
        signe = obj.get("signe") or obj.get("sign") or obj.get("zodiaque")
        maison = obj.get("maison") or obj.get("house")
        return f"{nom} : {signe or '?'} (Maison {maison or '?'})"
    
    sol_line  = _fmt_placement("Soleil")
    lune_line = _fmt_placement("Lune")

    aspects_all = theme.get("aspects_significatifs") or theme.get("aspects") or []
    aspects_lines = _filtrer_aspects_par_type(aspects_all, max_aspects=max_aspects)

    amas_lines = []
    amas = theme.get("amas") or []
    if isinstance(amas, list):
        for a in amas[:3]:
            try:
                signe = a.get("signe") or a.get("sign")
                pls   = ", ".join(a.get("planetes") or [])
                amas_lines.append(f"- Amas en {signe}: {pls}")
            except Exception:
                continue

    dignites_lines = []
    lune  = (theme.get("planetes") or {}).get("Lune")  or {}
    venus = (theme.get("planetes") or {}).get("Vénus") or (theme.get("planetes") or {}).get("Venus") or {}
    if (lune.get("signe") or "").lower().startswith("capri"):
        dignites_lines.append("- Lune en Capricorne (exil) → froideur/maîtrise émotionnelle à travailler.")
    if (venus.get("signe") or "").lower().startswith("scorp"):
        dignites_lines.append("- Vénus en Scorpion (exil) → intensité relationnelle / enjeux de confiance/pouvoir.")

    ctx_lines = []

    if inter_lines:
        ctx_lines += ["### Axes interceptés (PRIORITAIRES)"] + inter_lines

    ctx_lines += ["### Clés rapides",
                  f"- {sol_line}",
                  f"- {lune_line}"]

    if amas_lines:
        ctx_lines += ["### Amas (si pertinents)"] + amas_lines
    if dignites_lines:
        ctx_lines += ["### Dignités ciblées (utile ici)"] + dignites_lines

    return {
        "placements_compacts": "\n".join(ctx_lines).strip()
    }

def _build_contexte_global(data_theme) -> dict:
    ctx_compact = _build_contexte_compact(data_theme)
    placements_compacts = ctx_compact.get("placements_compacts", "")

    try:
        sel = construire_selection_point_astral(data_theme) or {}
        contexte_global = (
            sel.get("contexte_global")
            or sel.get("resume_global")
            or sel.get("axes_majeurs")
            or ""
        )
        if not isinstance(contexte_global, str):
            contexte_global = str(contexte_global)
    except Exception:
        contexte_global = ""

    if contexte_global.strip():
        placements_str = f"{placements_compacts}\n\n### Contexte global\n{contexte_global.strip()}"
    else:
        placements_str = placements_compacts

    return {
        "placements_str": placements_str,
        "axes_majeurs_str": "",
        "rag_snippets": ""
    }

def _construire_configurations(data_theme: dict) -> str:
    """Construit le bloc 'Configurations majeures'."""
    plan = data_theme.get("planetes", {}) or {}

    EXCLURE = {"Rahu", "Ketu", "Noeud Nord", "Nœud Nord", "Noeud Sud", "Nœud Sud", "Lune Noire", "Lilith", "Chiron"}
    PERSONNELLES_SOCIALES = {"Soleil", "Lune", "Mercure", "Vénus", "Venus", "Mars", "Jupiter", "Saturne"}

    entries = []
    for nom, p in plan.items():
        if nom in {"Ascendant", "Milieu du Ciel", "MC"}:
            continue
        try:
            lon = p.get("longitude") or p.get("lon") or p.get("ecliptic_longitude")
            lon = float(lon) if lon is not None else None
        except Exception:
            lon = None
        entries.append({
            "nom": nom,
            "lon": lon,
            "signe": p.get("signe") or p.get("sign"),
            "maison": p.get("maison") or p.get("house"),
            "countable": nom not in EXCLURE,
            "is_ps": nom in PERSONNELLES_SOCIALES
        })

    lines = []

    amas_lines = []
    groupable = [e for e in entries if e["countable"] and isinstance(e["lon"], (int, float))]
    groupable.sort(key=lambda x: x["lon"])

    i = 0
    while i < len(groupable):
        ref = groupable[i]
        grp = [ref]
        j = i + 1
        while j < len(groupable):
            d = abs(groupable[j]["lon"] - ref["lon"])
            d = d if d <= 180 else 360 - d
            if d <= 10.0:
                grp.append(groupable[j])
                j += 1
            else:
                break

        if len(grp) >= 3 and sum(1 for g in grp if g["is_ps"]) >= 2:
            noms = ", ".join(g["nom"] for g in grp)
            signe = grp[0]["signe"] or "?"
            maison = grp[0]["maison"]
            if maison:
                amas_lines.append(f"- Amas en {signe} maison {maison} ({noms})")
            else:
                amas_lines.append(f"- Amas en {signe} ({noms})")

        i = j if j > i + 1 else i + 1

    lines += amas_lines

    from collections import Counter
    by_sign = {}
    for e in entries:
        if not e["countable"]:
            continue
        s = e["signe"]
        if not s:
            continue
        by_sign.setdefault(s, []).append(e)

    for s, lst in by_sign.items():
        if len(lst) < 3 or sum(1 for g in lst if g["is_ps"]) < 2:
            continue

        deja_amas_ce_signe = any((f" Amas en {s} " in line or line.startswith(f"- Amas en {s}"))
                                 for line in lines)
        if deja_amas_ce_signe:
            continue

        noms = ", ".join(g["nom"] for g in lst)
        maisons = [str(g["maison"]) for g in lst if g.get("maison")]
        maison_dom = None
        if maisons:
            maison_dom, _ = Counter(maisons).most_common(1)[0]

        if maison_dom:
            lines.append(f"- Stellium en {s} maison {maison_dom} ({noms})")
        else:
            lines.append(f"- Stellium en {s} ({noms})")

    ret_pers = []
    for nom in ("Mercure", "Vénus", "Venus", "Mars"):
        d = plan.get(nom) or {}
        flags = d.get("flags") or []
        if d.get("retro") or d.get("retrograde") or d.get("r") or ("retro" in flags):
            ret_pers.append("Vénus" if nom == "Venus" else nom)

    if len(ret_pers) >= 2:
        lines.append(f"- Planètes personnelles rétrogrades : {', '.join(ret_pers)}")

    angulaires = [f"{e['nom']} (M{e['maison']})" for e in entries if str(e.get("maison")) in ("1", "10")]
    if angulaires:
        lines.append(f"- Planètes angulaires : {', '.join(angulaires)}")

    for maison in range(1, 13):
        group = [e for e in entries
                if e["countable"] and str(e.get("maison")) == str(maison)]
        if len(group) >= 3 and sum(1 for e in group if e.get("is_ps")) >= 2:
            noms = ", ".join(e["nom"] for e in group)
            lines.append(f"- Stellium en maison {maison} : {noms}")

    return "\n".join(lines).strip()

def _genre_directives(meta: dict) -> str:
    genre = (meta or {}).get("genre", "neutre")
    if genre == "femme":
        return ("- Prends en compte une réception lunaire/Vénus possiblement plus sensible.\n"
                "- Évite les injonctions dures ; privilégie l'accompagnement et la nuance.")
    if genre == "homme":
        return ("- Prends en compte un axe solaire/Mars possiblement plus saillant.\n"
                "- Évite les stéréotypes ; parle d'alignement et de responsabilité.")
    return "- Reste neutre, inclusif et respectueux des nuances individuelles."

def _birth_header_html(data_theme: dict, meta: dict | None = None) -> str:
    """Affiche 'date — heure — lieu' si disponible."""
    meta = meta or {}

    birth_dt = (
        meta.get("date_naissance")
        or meta.get("date")
        or (data_theme.get("naissance") or {}).get("date")
        or data_theme.get("date_naissance")
        or ""
    )
    birth_tm = (
        meta.get("heure_naissance")
        or meta.get("heure")
        or meta.get("time")
        or (data_theme.get("naissance") or {}).get("heure")
        or data_theme.get("heure_naissance")
        or ""
    )
    birth_pl = (
        meta.get("lieu_naissance")
        or meta.get("lieu")
        or meta.get("place")
        or meta.get("ville")
        or (data_theme.get("naissance") or {}).get("lieu")
        or data_theme.get("lieu_naissance")
        or ""
    )

    if not any([birth_dt, birth_tm, birth_pl]):
        return ""

    line = " — ".join([x for x in (birth_dt, birth_tm, birth_pl) if x])

    return (
        f"<p style='margin:4px 0 8px; text-align:center; font-size:14px; color:#666;'>{line}</p>"
    )

def analyse_forces_defis(data_theme, meta=None) -> str:
    """Génère une analyse Forces & Défis structurée."""
    html_final = ""

    meta = meta or {"tonalite": "tu", "genre": "neutre"}
    ctx = _build_contexte_global(data_theme)
    placements_str = ctx["placements_str"]

    try:
        sel = construire_selection_point_astral(data_theme) or {}
        ctx_global = (
            sel.get("contexte_global")
            or sel.get("axes_majeurs")
            or sel.get("resume_global")
            or ""
        )
        if not isinstance(ctx_global, str):
            ctx_global = ""
    except Exception:
        ctx_global = ""

    bloc_contexte = placements_str if isinstance(placements_str, str) else str(placements_str)
    if ctx_global.strip():
        bloc_contexte = f"{bloc_contexte}\n\n### Contexte global\n{ctx_global.strip()}"

    try:
        priorities_md = build_unified_priorities(
            data_theme,
            min_score=3.0,
            limit=30
        )
        if priorities_md:
            bloc_contexte = f"{bloc_contexte}\n\n{priorities_md}"
    except Exception as e:
        print(f"[FD_INJECT] Erreur: {e}")
        import traceback
        traceback.print_exc()

    if not placements_str or len(placements_str) < 40:
        raise ValueError("placements_str insuffisant pour générer l'analyse Forces & Défis.")

    if callable(_GENERER_FORCES_DEFIS):
        fd = _GENERER_FORCES_DEFIS(data_theme)
    else:
        fd = _fallback_generer_forces_defis(data_theme)

    try:
        fd_maisons = extraire_forces_defis_par_maisons(data_theme)
        if isinstance(fd_maisons, dict):
            fd["forces"] = (fd.get("forces") or []) + (fd_maisons.get("forces") or [])
            fd["defis"]  = (fd.get("defis")  or []) + (fd_maisons.get("defis")  or [])
    except Exception:
        pass

    genre_rules = _genre_directives(meta)

    bloc_placements_simple = f"""
- Ascendant : {data_theme['ascendant']['signe']}
- Soleil : {data_theme['planetes']['Soleil']['signe']} (Maison {data_theme['planetes']['Soleil']['maison']})
- Lune : {data_theme['planetes']['Lune']['signe']} (Maison {data_theme['planetes']['Lune']['maison']})
- Mercure : {data_theme['planetes']['Mercure']['signe']} (Maison {data_theme['planetes']['Mercure']['maison']})
- Vénus : {data_theme['planetes']['Vénus']['signe']} (Maison {data_theme['planetes']['Vénus']['maison']})
- Mars : {data_theme['planetes']['Mars']['signe']} (Maison {data_theme['planetes']['Mars']['maison']})
- Jupiter : {data_theme['planetes']['Jupiter']['signe']} (Maison {data_theme['planetes']['Jupiter']['maison']})
- Saturne : {data_theme['planetes']['Saturne']['signe']} (Maison {data_theme['planetes']['Saturne']['maison']})
- Uranus : {data_theme['planetes']['Uranus']['signe']} (Maison {data_theme['planetes']['Uranus']['maison']})
- Neptune : {data_theme['planetes']['Neptune']['signe']} (Maison {data_theme['planetes']['Neptune']['maison']})
- Pluton : {data_theme['planetes']['Pluton']['signe']} (Maison {data_theme['planetes']['Pluton']['maison']})
"""

    bloc_configurations = _construire_configurations(data_theme)

    # --- Comptage + limitation à 10 éléments par section ---
    import re

    try:
        txt_source = priorities_md if isinstance(priorities_md, str) and priorities_md.strip() else bloc_contexte
    except NameError:
        txt_source = bloc_contexte
    txt_source = txt_source or ""
    lignes = txt_source.splitlines()

    nb_defis = nb_forces = nb_mixtes = 0
    current_section = None

    # Conteneurs (pour éventuellement les afficher ou debug)
    defis_items, forces_items, mixtes_items = [], [], []

    for line in lignes:
        s = line.strip()
        low = s.lower()

        # Détection de section
        if s.startswith("##"):
            if "défis" in low or "defis" in low:
                current_section = "defis";  continue
            if "potentiels" in low:
                current_section = "forces"; continue
            if "dynamiques mixtes" in low or "mixtes" in low:
                current_section = "mixtes"; continue
            current_section = None
            continue

        # Comptage et enregistrement des items numérotés
        if current_section and re.match(r"^\s*\d+\.\s+\*\*", s):
            if current_section == "defis":
                defis_items.append(s)
            elif current_section == "forces":
                forces_items.append(s)
            elif current_section == "mixtes":
                mixtes_items.append(s)

    # ✅ Limite à 10 par catégorie
    defis_items = defis_items[:10]
    forces_items = forces_items[:10]
    mixtes_items = mixtes_items[:10]

    # ✅ Comptages
    nb_defis = len(defis_items)
    nb_forces = len(forces_items)
    nb_mixtes = len(mixtes_items)
    total_elements = nb_defis + nb_forces + nb_mixtes

    # (Optionnel) log
    print(f"[COMPTAGE LIMITÉ] Défis={nb_defis} Forces={nb_forces} Mixtes={nb_mixtes} Total={total_elements}")

    

    prompt = f"""
Tu es une astrologue-psychologue experte (20+ ans), spécialisée en astrologie psychologique (Jung, Alice Bailey).

ANALYSE PAYANTE - Thème : {meta.get("prenom", "la personne")}
Objectif : Révéler les dynamiques profondes du thème via FORCES et DÉFIS concrets.

═══ CONTEXTE MINIMAL DU THÈME ═══

**Placements de base :**
{bloc_placements_simple}

**Configurations majeures :**
{bloc_configurations}

---

🚨 ÉLÉMENTS À ANALYSER (TOTAL : {total_elements})
- DÉFIS : {nb_defis} éléments
- FORCES : {nb_forces} éléments  
- MIXTES : {nb_mixtes} éléments

{bloc_contexte}

---


╔══ STRUCTURE DE SORTIE OBLIGATOIRE ══╗

**Introduction** (2-3 paragraphes)
Accroche incarnée et personnalisée basée sur les configurations majeures. 
Pas de liste, uniquement de la prose fluide et cohérente.

**## Tes Défis**
Texte continu en paragraphes. Tu intègres les {nb_defis} dynamiques de fond 
de manière narrative — pas de liste, pas de tirets. Tu tisses les tensions 
entre elles pour montrer comment elles interagissent dans la vie concrète.
Chaque dynamique doit être développée sur au moins 2 paragraphes complets avec exemples concrets.
MINIMUM ABSOLU : 700 mots pour cette section. Ne passe pas à la suivante avant d'avoir atteint ce minimum.

**## Tes Potentiels**
Même chose : prose fluide, {nb_forces} ressources intégrées dans un récit cohérent.
Chaque potentiel développé sur au moins 2 paragraphes avec exemples d'activation concrète.
MINIMUM ABSOLU : 700 mots pour cette section. Ne passe pas à la suivante avant d'avoir atteint ce minimum.

**## Ce qui joue dans les deux sens**
Les {nb_mixtes} dynamiques mixtes racontées en paragraphes — leur double face, 
leur complexité, comment les apprivoiser.
MINIMUM ABSOLU : 500 mots pour cette section.

**Conclusion** (1-2 paragraphes)
Synthèse intégrative et ouverture concrète.

---
⚠️ VÉRIFICATION FINALE OBLIGATOIRE :
Avant de terminer, compte tes analyses :
- DÉFIS analysés : {nb_defis}/{nb_defis} ✓
- POTENTIELS analysés : {nb_forces}/{nb_forces} ✓
- MIXTES analysés : {nb_mixtes}/{nb_mixtes} ✓
TOTAL = {total_elements} éléments

Si un élément manque, ajoute-le MAINTENANT. Ne dis JAMAIS "je continuerai plus tard".


═══ CONSIGNES D'ANALYSE ═══

✅ Analyse CHAQUE élément numéroté dans la section ci-dessus
✅ Respecte l'ordre d'importance (scores décroissants)
✅ Écris en prose continue, jamais de tirets ou de listes
✅ Chaque section est un texte narratif cohérent
✅ Les aspects/placements sont nommés dans le fil du texte, pas en entêtes
✅ Développe les mécanismes psychiques avec exemples concrets
✅ Paragraphes complets (6 lignes minimum)
✅ MINIMUM TOTAL du document : 2500 mots hors introduction et conclusion
✅ Si tu approches de la fin d'une section avant d'avoir atteint le minimum, développe davantage avec des exemples supplémentaires

❌ NE PAS analyser d'aspects non listés
❌ NE PAS mentionner Chiron ou éléments non prioritaires
❌ NE PAS résumer ou regrouper les éléments
❌ NE PAS s'arrêter avant d'avoir traité les {total_elements} éléments

Développe chaque point avec beaucoup de profondeur, 
en expliquant les mécanismes psychiques ou comportementaux associés. 
N'hésite pas à donner des exemples concrets ou des situations types.
Fais des paragraphes complets (6 lignes par point minimum).

═══ STYLE D'ÉCRITURE ═══

✓ Ton : Lucide, direct, bienveillant mais sans complaisance
✓ Profondeur : Psychologie jungienne, symbolisme archétypal
✓ Style : psychologique, sobre, sans humour cosmique, sans tournures poétiques ou métaphores excessives
✓ Concret : Exemples de vie, situations tangibles
✓ Empathie : Reconnaître la difficulté sans dramatiser
⚠️ Important : utilise le tutoiement uniquement

✗ INTERDIT :
- Phrases vides type "tu es unique", "le cosmos t'appelle", PAS DE METAPHORE COSMIQUE
- Images farfelues gratuites
- Psychologie de comptoir
- Prédictions, jugements moraux
- Ton professoral ou condescendant

Métadonnées :
- Tonalité: {meta.get("tonalite","tu")}
- Genre: {meta.get("genre","neutre")}
"""

    
    # 🛠 Voir le prompt entier dans la console
    print("\n=== PROMPT FORCES & DEFIS ===\n")
    print(prompt)
    print("\n=== FIN PROMPT ===\n")

    texte = ""
    html_core = ""

    try:
        resultat_llm = interroger_llm(prompt)

        if isinstance(resultat_llm, dict):
            texte = (
                resultat_llm.get("content")
                or resultat_llm.get("text")
                or resultat_llm.get("message")
                or resultat_llm.get("response")
                or str(resultat_llm)
            )
        else:
            texte = str(resultat_llm)

        try:
            html_core = md_light_to_html(texte or "")
        except Exception as conv_err:
            print(f"[FD] Erreur conversion md_light_to_html: {conv_err}")
            html_core = f"<pre style='white-space:pre-wrap'>{(texte or '')}</pre>"

    except Exception as gen_err:
        print(f"[FD] Erreur génération: {gen_err}")
        html_core = (
            "<div class='error' style='border:1px solid #e00;padding:8px;margin:8px 0'>"
            "<strong>Erreur de génération</strong></div>"
            f"<pre style='white-space:pre-wrap'>{prompt[:1000]}</pre>"
        )

    header_birth = _birth_header_html(data_theme, meta)
    html_final = f"{header_birth}{DISCLAIMER_FORCES_DEFIS_HTML}\n{html_core}"

    return html_final