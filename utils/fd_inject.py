# utils/fd_inject.py
from __future__ import annotations

import os
import csv
import unicodedata
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Conversion chiffres romains
# ─────────────────────────────────────────────────────────────
def _roman_to_int(roman: str) -> int:
    """Convertit un chiffre romain en entier."""
    roman_map = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
        'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12
    }
    return roman_map.get(roman.strip().upper(), 0)

# ─────────────────────────────────────────────────────────────
# Localisation des CSV
# ─────────────────────────────────────────────────────────────
def _resolve_data_dir() -> Path:
    env = os.getenv("FD_CSV_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p

    here = Path(__file__).resolve().parent
    candidates = [
        here / "data",
        here.parent / "data",
        Path.cwd() / "data",
        Path("data"),
        Path.cwd() / "utils" / "data",
        here.parent / "rag",
        here.parent.parent / "rag",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    return (Path.cwd() / "data").resolve()

DATA_DIR = _resolve_data_dir()

_FALLBACK_SINGLE_FILE: Path | None = None
for name in ["data_forces_defis.csv", "forces_defis.csv", "fd.csv"]:
    p = DATA_DIR / name
    if p.exists():
        _FALLBACK_SINGLE_FILE = p
        break

# ─────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    
    aliases = {
        "venus": "venus",
        "vénus": "venus",
        "pluton": "pluton",
        "pluto": "pluton",
        "uranus": "uranus",
    }
    return aliases.get(s, s)

_ASPECT_MAP = {
    "conjonction": "conjonction", "conjunction": "conjonction",
    "trigone": "trigone", "trine": "trigone",
    "sextile": "sextile",
    "carré": "carre", "carre": "carre", "square": "carre",
    "opposition": "opposition",
    "quinconce": "quinconce", "quincunx": "quinconce",
}

def _norm_aspect(t: str) -> str:
    return _ASPECT_MAP.get(_norm(t), _norm(t))

def _forcer_retrogrades_reels(theme: dict):
    """Corrige les rétrogrades mal détectées en analysant la vitesse."""
    planetes = theme.get("planetes", {}) or {}
    for nom, data in planetes.items():
        if data.get("retrograde") is True:
            data["retro"] = True
            continue
        speed = (data.get("speed") or data.get("vitesse") or
                 data.get("daily_motion") or data.get("v"))
        if speed is None:
            continue
        try:
            if float(speed) < 0:
                data["retro"] = True
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────
# Patch : récupération via forces_defis_analyse
# ─────────────────────────────────────────────────────────────
try:
    from utils.forces_defis_analyse import get_retrogrades_occidentales

    def _forcer_retrogrades_reels(theme: dict):
        """Corrige les rétrogrades mal détectées."""
        planetes = theme.get("planetes", {})

        retro_detectees = get_retrogrades_occidentales(theme)
        if retro_detectees:
            for nom in retro_detectees:
                clef = next((k for k in planetes.keys() if k.lower().startswith(nom.lower())), None)
                if clef and not planetes[clef].get("retro"):
                    planetes[clef]["retro"] = True

        for nom, data in planetes.items():
            if data.get("retrograde") is True:
                data["retro"] = True
                continue

            speed = data.get("speed") or data.get("vitesse") or data.get("daily_motion") or data.get("v")
            if speed is not None:
                try:
                    if float(speed) < 0:
                        data["retro"] = True
                except:
                    pass
except Exception:
    pass

def _pair_key(a: str, b: str) -> tuple[str, str]:
    a, b = _norm(a), _norm(b)
    return tuple(sorted([a, b]))

def _read_csv(name: str):
    """Lit un CSV par nom, avec fallback 'fichier unique' si présent."""
    p = (DATA_DIR / name)
    if not p.exists() and _FALLBACK_SINGLE_FILE is not None:
        p = _FALLBACK_SINGLE_FILE
    if not p.exists():
        raise FileNotFoundError(f"CSV introuvable: {p} (DATA_DIR={DATA_DIR})")

    with p.open(encoding="utf-8") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    
    return rows

# ─────────────────────────────────────────────────────────────
# Détection aspects à partir du thème
# ─────────────────────────────────────────────────────────────
def _collect_theme_aspects(theme: dict):
    """Renvoie une liste de dicts: {p1, p2, type, orb} depuis theme['aspects']."""
    raw = theme.get("aspects_significatifs") or theme.get("aspects") or []
    out = []
    for a in raw:
        if isinstance(a, dict):
            p1 = a.get("p1") or a.get("planete1") or a.get("planet1") or a.get("A") or a.get("from")
            p2 = a.get("p2") or a.get("planete2") or a.get("planet2") or a.get("B") or a.get("to")
            t  = a.get("type") or a.get("aspect") or a.get("relation") or a.get("kind")
            orb = a.get("orb") or a.get("orbe") or a.get("delta")
        else:
            p1 = p2 = t = None
            orb = None
            s = str(a)
            import re
            m = re.search(r"^([\wÉÈÊÀÂÔÛÙéèêàâôûù'' -]+)\s+([\w]+)\s+([\wÉÈÊÀÂÔÛÙéèêàâôûù'' -]+)", s, flags=re.I)
            if m:
                p1, t, p2 = m.group(1), m.group(2), m.group(3)
            mo = re.search(r"orbe\s*([0-9]+(?:\.[0-9]+)?)", s, flags=re.I)
            if mo:
                try:
                    orb = float(mo.group(1))
                except Exception:
                    orb = None

        if p1 and p2 and t:
            out.append({
                "p1": _norm(p1),
                "p2": _norm(p2),
                "type": _norm_aspect(t),
                "orb": float(orb) if isinstance(orb, (int, float, str)) and str(orb).replace('.', '', 1).isdigit() else None,
            })
    return out

def _parse_aspects_field(s: str) -> set[str]:
    parts = [x.strip() for x in (s or "").split(",")]
    return {_norm_aspect(x) for x in parts if x}

def detect_aspects_from_csv(theme: dict,
                            wanted_type: str,
                            min_score: float = 3.0,
                            limit: int = 10):
    """
    Matche le thème sur le CSV unique des aspects (forces_defis.csv),
    en filtrant sur TYPE = force / defis / mixte.
    """
    rows = _read_csv("forces_defis.csv")
    theme_aspects_all = _collect_theme_aspects(theme)

    wt = (wanted_type or "").strip().lower()
    if wt == "defi":
        wt = "defis"
    if wt not in {"force", "defis", "mixte"}:
        wt = "force"

    def _row_type_ok(row):
        t = (row.get("TYPE") or "").strip().lower()
        if t == "defi":
            t = "defis"
        return t == wt

    rows = [r for r in rows if _row_type_ok(r)]

    ORB_LIMITS = {
        "conjonction": 8.0,
        "carre": 7.0, "carré": 7.0,
        "opposition": 7.0,
        "trigone": 5.0,
        "sextile": 5.0,
    }

    def _type_norm(t: str) -> str:
        t = (t or "").lower().strip()
        if t == "carré":
            t = "carre"
        return t
    
    def _get_sign(theme, name_norm: str) -> str:
        plan = theme.get("planetes") or {}
        for k, v in plan.items():
            if _norm(k) == _norm(name_norm):
                return _norm(v.get("signe") or v.get("sign") or "")
        return ""

    def _conj_limit_for_pair(theme, p1_norm: str, p2_norm: str, base_lim=8.0, dissoc_lim=4.0) -> float:
        s1 = _get_sign(theme, p1_norm)
        s2 = _get_sign(theme, p2_norm)
        if s1 and s2 and s1 == s2:
            return base_lim
        return dissoc_lim

    def _keep_valid_orb(ta: dict) -> bool:
        t = _type_norm(ta.get("type"))
        orb = ta.get("orb")

        if not isinstance(orb, (int, float)):
            return False

        lim = ORB_LIMITS.get(t)
        if lim is None:
            return False

        if t == "conjonction":
            lim = _conj_limit_for_pair(
                theme,
                ta.get("p1"), ta.get("p2"),
                base_lim=ORB_LIMITS["conjonction"],
                dissoc_lim=4.0
            )

        return float(orb) <= float(lim)

    theme_aspects = [ta for ta in theme_aspects_all if _keep_valid_orb(ta)]

    results = []
    for row in rows:
        try:
            p1 = _norm(row.get("PLANETE_1"))
            p2 = _norm(row.get("PLANETE_2"))
            aspects_ok = _parse_aspects_field(row.get("ASPECTS", ""))
            typ = _norm(row.get("TYPE", ""))
            score = float(row.get("SCORE", 0))
            comment = (row.get("COMMENTAIRE") or "").strip()
        except Exception:
            continue

        if score < min_score:
            continue

        key_csv = _pair_key(p1, p2)

        for ta in theme_aspects:
            key_theme = _pair_key(ta["p1"], ta["p2"])
            if key_theme != key_csv:
                continue
            if ta["type"] not in aspects_ok:
                continue

            t_norm = _type_norm(ta["type"])
            orb_val = ta.get("orb")
            if not isinstance(orb_val, (int, float)):
                continue

            lim = ORB_LIMITS.get(t_norm)
            if lim is None:
                continue

            if t_norm == "conjonction":
                lim = _conj_limit_for_pair(
                    theme,
                    ta["p1"], ta["p2"],
                    base_lim=ORB_LIMITS["conjonction"],
                    dissoc_lim=4.0
                )

            if float(orb_val) > float(lim):
                continue

            results.append({
                "p1": ta["p1"], "p2": ta["p2"],
                "aspect": ta["type"],
                "orb": float(orb_val),
                "score": score,
                "comment": comment,
                "type": typ,
            })

    results.sort(key=lambda x: (-x["score"], x["orb"] if isinstance(x.get("orb"), (int, float)) else 99.0))
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# Détection état des planètes
# ─────────────────────────────────────────────────────────────
def detect_etat_planetes(theme: dict,
                         csv_name: str,
                         min_score: float = 3.0,
                         limit: int = 10):
    """Matche l'état des planètes : rétrograde, dignités."""
    rows = _read_csv(csv_name)
    plan = theme.get("planetes") or {}
    results = []
    
    for row in rows:
        planet = _norm(row.get("PLANETE"))
        signe_csv = _norm(row.get("SIGNE", ""))
        etat = _norm(row.get("ETAT"))
        typ = _norm(row.get("TYPE", ""))
        try:
            score = float(row.get("SCORE", 0))
        except Exception:
            score = 0.0
        comment = (row.get("COMMENTAIRE") or "").strip()

        if score < min_score:
            continue

        if etat in {"retrograde", "rétrograde"}:
            for k, v in plan.items():
                k_norm = _norm(k)
                is_retro = (
                    v.get("retro") is True
                    or v.get("r") is True
                    or v.get("retrograde") is True
                    or ("retro" in (v.get("flags") or []))
                )
                
                if k_norm == planet and is_retro:
                    results.append({
                        "planete": k,
                        "etat": "rétrograde",
                        "score": score,
                        "comment": comment,
                        "type": typ,
                    })
        
        elif etat in {"domicile", "exaltation", "exil", "chute"}:
            for k, v in plan.items():
                if _norm(k) != planet:
                    continue
                
                signe_theme = _norm(v.get("signe") or v.get("sign") or "")
                
                if signe_theme == signe_csv:
                    results.append({
                        "planete": k,
                        "etat": f"{etat} {signe_csv.title()}",
                        "score": score,
                        "comment": comment,
                        "type": typ,
                    })
    
    results.sort(key=lambda x: -x["score"])
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# Rendu Markdown prêt à insérer dans le prompt
# ─────────────────────────────────────────────────────────────
def build_markdown_blocks(theme: dict,
                          min_score_aspect: float = 4.0,
                          limit_forces: int = 10,
                          limit_defis: int = 10,
                          min_score_etat: float = 4.0,
                          limit_etat: int = 10) -> str:
    defis  = detect_aspects_from_csv(theme, "defis",  min_score_aspect, limit_defis)
    forces = detect_aspects_from_csv(theme, "force",  min_score_aspect, limit_forces)
    mixtes = detect_aspects_from_csv(theme, "mixte",  min_score_aspect, 10)
    etats  = detect_etat_planetes(theme, "etat_planetes.csv",     min_score_etat,  limit_etat)

    lines = []
    if defis:
        lines.append("### DÉFIS détectés (règles CSV)")
        for d in defis:
            orb = f" (orbe {d['orb']:.2f}°)" if isinstance(d.get("orb"), (int, float)) else ""
            lines.append(f"- **{d['p1'].title()} {d['aspect']} {d['p2'].title()}**{orb} — score {d['score']}: {d['comment']}")
        lines.append("")

    if forces:
        lines.append("### FORCES détectées (règles CSV)")
        for f in forces:
            orb = f" (orbe {f['orb']:.2f}°)" if isinstance(f.get("orb"), (int, float)) else ""
            lines.append(f"- **{f['p1'].title()} {f['aspect']} {f['p2'].title()}**{orb} — score {f['score']}: {f['comment']}")
        lines.append("")

    if mixtes:
        lines.append("### DYNAMIQUES MIXTES détectées (règles CSV)")
        for m in mixtes:
            orb = f" (orbe {m['orb']:.2f}°)" if isinstance(m.get("orb"), (int, float)) else ""
            lines.append(f"- **{m['p1'].title()} {m['aspect']} {m['p2'].title()}**{orb} — score {m['score']}: {m['comment']}")
        lines.append("")

    if etats:
        lines.append("### ÉTAT DES PLANÈTES (CSV)")
        for e in etats:
            lines.append(f"- **{e['planete']} {e['etat']}** — score {e['score']}: {e['comment']}")

    return "\n".join(lines).strip()

def detect_conjonctions_angles_simple(theme: dict, orbe_max: float = 8.0, min_score: float = 3.0) -> list:
    """Détecte les conjonctions aux angles en lisant les cuspides des maisons."""
    planetes = theme.get("planetes", {})
    maisons = theme.get("maisons_occidentales") or theme.get("maisons") or {}
    
    def _signe_to_base(signe: str) -> float:
        signes = {
            "belier": 0, "bélier": 0,
            "taureau": 30,
            "gemeaux": 60, "gémeaux": 60,
            "cancer": 90,
            "lion": 120,
            "vierge": 150,
            "balance": 180,
            "scorpion": 210,
            "sagittaire": 240,
            "capricorne": 270,
            "verseau": 300,
            "poissons": 330
        }
        return signes.get(_norm(signe), 0.0)
    
    def _to_abs_deg(signe: str, deg: float) -> float:
        return (_signe_to_base(signe) + float(deg)) % 360.0
    
    def _ecart(a: float, b: float) -> float:
        d = abs(a - b)
        return d if d <= 180 else 360 - d
    
    angles = {}
    mapping = {
        1: ("ASC", "I"),
        4: ("FC", "IV"),
        7: ("DSC", "VII"),
        10: ("MC", "X")
    }
    
    for num, (label, roman) in mapping.items():
        maison = (
            maisons.get(f"Maison {num}") 
            or maisons.get(f"Maison {roman}")
            or maisons.get(str(num))
            or maisons.get(roman)
        )
        
        if maison:
            signe = maison.get("signe") or maison.get("sign")
            deg = (
                maison.get("degre_dans_signe") 
                or maison.get("degree_in_sign")
                or maison.get("deg_signe")
            )
            
            if signe and deg is not None:
                angles[label] = _to_abs_deg(signe, deg)
    
    if not angles:
        return []
    
    results = []
    matched = set()
    
    for nom, data in planetes.items():
        if nom in ["Ascendant", "Milieu du Ciel", "MC"]:
            continue
        
        signe = data.get("signe") or data.get("sign")
        deg = (
            data.get("degre_dans_signe")
            or data.get("degree_in_sign")
            or data.get("deg_signe")
            or data.get("deg")
        )
        
        if not signe or deg is None:
            continue
        
        pl_lon = _to_abs_deg(signe, deg)
        
        for angle_label, angle_lon in angles.items():
            ecart = _ecart(pl_lon, angle_lon)
            
            if ecart <= orbe_max:
                key = f"{nom}-{angle_label}"
                if key in matched:
                    continue
                matched.add(key)
                
                if nom in ["Saturne", "Neptune", "Pluton"]:
                    typ = "mixte"
                    score = 5.0
                elif nom in ["Uranus"]:
                    typ = "force"
                    score = 5.0
                elif nom in ["Jupiter"]:
                    typ = "force"
                    score = 4.5
                else:
                    typ = "force"
                    score = 4.0
                
                comment = f"{nom} à {ecart:.1f}° de {angle_label} - Impact majeur sur "
                if angle_label == "ASC":
                    comment += "l'identité et l'image"
                elif angle_label == "DSC":
                    comment += "les relations et partenariats"
                elif angle_label == "MC":
                    comment += "la carrière et la destinée publique"
                else:
                    comment += "les racines et le foyer"
                
                categorie = f"{typ.upper()} (angle)"
                
                results.append({
                    "categorie": categorie,
                    "description": f"{nom} conjoint {angle_label}",
                    "orb": round(ecart, 2),
                    "score": score,
                    "comment": comment
                })
    
    results.sort(key=lambda x: (-x["score"], x["orb"]))
    return results

# ─────────────────────────────────────────────────────────────
# Détection placements en maisons
# ─────────────────────────────────────────────────────────────
def detect_placements_maisons(theme: dict,
                              csv_name: str,
                              min_score: float = 3.0,
                              limit: int = 10):
    """Détecte les placements planétaires en maisons importants."""
    rows = _read_csv(csv_name)
    planetes = theme.get("planetes", {})
    
    results = []
    for row in rows:
        planete = _norm(row.get("PLANETE"))
        maison_csv_str = str(row.get("MAISON", "")).strip()
        maison_csv = _roman_to_int(maison_csv_str)
        
        typ = _norm(row.get("TYPE", ""))
        try:
            score = float(row.get("SCORE", 0))
        except:
            score = 0.0
        comment = (row.get("COMMENTAIRE") or "").strip()
        
        if score < min_score:
            continue
        
        for nom_planete, data in planetes.items():
            nom_norm = _norm(nom_planete)
            maison_theme = data.get("maison") or data.get("house")
            
            if nom_norm != planete:
                continue
            
            try:
                maison_theme_int = int(maison_theme)
            except:
                continue
            
            if maison_theme_int == maison_csv:
                if typ == "mixte":
                    categorie = "MIXTE (maison)"
                elif typ == "defi":
                    categorie = "DÉFI (maison)"
                elif typ == "force":
                    categorie = "FORCE (maison)"
                else:
                    categorie = f"{typ.upper()} (maison)"
                
                results.append({
                    "planete": nom_planete,
                    "maison": maison_csv_str,
                    "score": score,
                    "comment": comment,
                    "type": typ,
                    "categorie": categorie
                })
    
    results.sort(key=lambda x: -x['score'])
    return results[:limit]

def _regrouper_dignites_par_planete(items: list[dict]) -> list[dict]:
    """Fusionne les entrées de dignités/rétro pour une même planète."""
    from collections import defaultdict
    import unicodedata

    def _cat_key(s: str) -> str:
        s = unicodedata.normalize("NFKD", (s or "")).encode("ascii","ignore").decode("ascii")
        return s.upper()

    def _is_dignite(it):
        ck = _cat_key(it.get("categorie"))
        return "DIGNITE" in ck

    groupes = defaultdict(list)
    autres = []

    for it in items:
        if _is_dignite(it):
            desc = it.get("description", "") or ""
            nom = desc.split()[0] if desc else ""
            if nom:
                groupes[nom.lower()].append(it)
            else:
                autres.append(it)
        else:
            autres.append(it)

    fusionnes = []
    for nom, bloc in groupes.items():
        if len(bloc) == 1:
            fusionnes.append(bloc[0])
            continue

        cats = {_cat_key(x.get("categorie")) for x in bloc}
        if any("DEFI" in c for c in cats):
            cat_final = "DEFI (dignite)"
        elif any("MIXTE" in c for c in cats):
            cat_final = "MIXTE (dignite)"
        else:
            cat_final = "FORCE (dignite)"

        scores = [x.get("score", 0) for x in bloc]
        score_final = min(5.0, max(scores) + (0.5 if len(bloc) >= 2 else 0))

        planete_nom = (bloc[0].get("description","").split()[0] or nom).title()
        etats = []
        for x in bloc:
            d = x.get("description","")
            etat = " ".join(d.split()[1:]).strip() or d
            if etat:
                etats.append(etat)
        etats = sorted({e for e in etats if e})

        comments = [x.get("comment","").strip() for x in bloc if x.get("comment")]
        comment_final = " / ".join([c for c in comments if c])[:500]

        fusionnes.append({
            "categorie": cat_final,
            "description": f"{planete_nom} : " + " + ".join(etats),
            "orb": None,
            "score": score_final,
            "comment": comment_final
        })

    return autres + fusionnes

# ─────────────────────────────────────────────────────────────
# Liste unifiée des priorités
# ─────────────────────────────────────────────────────────────
def build_unified_priorities(theme: dict,
                             min_score: float = 3.0,
                             limit: int = 30,
                             style: str = "v2") -> str:
    _forcer_retrogrades_reels(theme)

    all_priorities = []

    # 1) Conjonctions planète ↔ angles
    try:
        conj_angles = detect_conjonctions_angles_simple(theme, orbe_max=8.0, min_score=min_score)
        all_priorities.extend(conj_angles)
    except Exception as e:
        print(f"[FD_INJECT] Erreur conjonctions angles: {e}")

    # Fallback : maisons I et X
    if not any("(angle)" in (x.get("categorie") or "") for x in all_priorities):
        try:
            maisons_I_X = []
            for nom, p in (theme.get("planetes") or {}).items():
                h = p.get("maison") or p.get("house")
                if str(h) in ("1", "10"):
                    maisons_I_X.append(nom)
            if maisons_I_X:
                all_priorities.append({
                    "categorie": "MIXTE (angle)",
                    "description": f"Planètes angulaires (I/X) : {', '.join(maisons_I_X)}",
                    "orb": None,
                    "score": 3.8,
                    "comment": "Présence directe, visibilité, impact sur l'identité (I) et la vocation (X)."
                })
        except Exception:
            pass

    # 2) DÉFIS (aspects)
    defis = detect_aspects_from_csv(theme, "defis", min_score, 999)
    for d in defis:
        all_priorities.append({
            "categorie": "DÉFI (aspect)",
            "description": f"{d['p1'].title()} {d['aspect']} {d['p2'].title()}",
            "orb": d.get('orb'),
            "score": d['score'],
            "comment": d['comment']
        })

    # 3) FORCES (aspects)
    forces = detect_aspects_from_csv(theme, "force", min_score, 999)
    for f in forces:
        all_priorities.append({
            "categorie": "FORCE (aspect)",
            "description": f"{f['p1'].title()} {f['aspect']} {f['p2'].title()}",
            "orb": f.get('orb'),
            "score": f['score'],
            "comment": f['comment']
        })

    # 3b) MIXTES (aspects)
    mixtes = detect_aspects_from_csv(theme, "mixte", min_score, 999)
    for m in mixtes:
        all_priorities.append({
            "categorie": "MIXTE (aspect)",
            "description": f"{m['p1'].title()} {m['aspect']} {m['p2'].title()}",
            "orb": m.get('orb'),
            "score": m['score'],
            "comment": m['comment']
        })

    # 4) Dignités / rétrogrades
    etats = detect_etat_planetes(theme, "etat_planetes.csv", min_score, 999)
    for e in etats:
        all_priorities.append({
            "categorie": f"{e['type'].upper()} (dignité)",
            "description": f"{e['planete'].title()} {e['etat']}",
            "orb": None,
            "score": e['score'],
            "comment": e['comment']
        })

    # 5) Placements en maisons
    try:
        placements = detect_placements_maisons(theme, "placements_maisons.csv", min_score, 999)

        planetes_sur_angles = {
            item["description"].split()[0]
            for item in all_priorities
            if "conjoint" in item.get("description", "") and "(angle)" in (item.get("categorie") or "")
        }

        for p in placements:
            planete = p["planete"].title()

            if planete in planetes_sur_angles:
                for a in all_priorities:
                    if a["description"].startswith(f"{planete} conjoint"):
                        a["comment"] += f" / {p['comment']}"
                        a["score"] = max(a["score"], p["score"])
                        break
                continue

            categorie = p.get("categorie") or f"{p['type'].upper()} (maison)"
            all_priorities.append({
                "categorie": categorie,
                "description": f"{planete} en maison {p['maison']}",
                "orb": None,
                "score": p['score'],
                "comment": p['comment']
            })

    except Exception as e:
        print(f"[FD_INJECT] Erreur placements maisons: {e}")

    def _cat_key(s: str) -> str:
        s = unicodedata.normalize("NFKD", (s or "")).encode("ascii","ignore").decode("ascii")
        return s.upper()

    all_priorities = _regrouper_dignites_par_planete(all_priorities)

    # Fusion angle + rétrograde
    def _is_retro_planet(theme, name: str) -> bool:
        plan = theme.get("planetes", {}) or {}
        key = next((k for k in plan.keys() if _norm(k) == _norm(name)), None)
        if not key:
            return False
        d = plan[key] or {}
        flags = d.get("flags") or []
        return bool(d.get("retro") or d.get("retrograde") or d.get("r") or ("retro" in flags))

    angle_items_idx = {}
    for i, it in enumerate(all_priorities):
        desc = (it.get("description") or "").lower()
        cat  = (it.get("categorie") or "").lower()
        if "conjoint" in desc and "(angle)" in cat:
            planet = it.get("description","").split()[0]
            angle_items_idx[_norm(planet)] = i

    to_remove = set()
    for planet_norm, idx in angle_items_idx.items():
        item = all_priorities[idx]
        planet_display = item["description"].split()[0]

        if not _is_retro_planet(theme, planet_display):
            continue

        if "(rétrograde)" not in item["description"].lower():
            item["description"] += " (rétrograde)"

        cat_u = (item.get("categorie") or "")
        if "MIXTE" not in unicodedata.normalize("NFKD", cat_u).upper():
            item["categorie"] = "MIXTE (angle)"

        extra = " — Mouvement rétrograde : introspection, reprises, possibles temps de latence dans l'expression."
        if extra not in item.get("comment",""):
            item["comment"] = (item.get("comment","") + extra).strip()

        item["score"] = min(5.0, float(item.get("score", 0)) + 0.2)

        for j, it2 in enumerate(all_priorities):
            if j == idx:
                continue
            cat2 = (it2.get("categorie") or "")
            desc2 = (it2.get("description") or "")
            if "DIGNITE" in unicodedata.normalize("NFKD", cat2).upper():
                if _norm(desc2.split()[0]) == planet_norm and "retro" in _norm(desc2):
                    to_remove.add(j)

    if to_remove:
        all_priorities = [it for k, it in enumerate(all_priorities) if k not in to_remove]

    def _fam_rank(cat: str) -> int:
        ck = _cat_key(cat)
        if " (ANGLE)" in ck:
            return 0
        if "DEFI" in ck and "(DIGNITE)" in ck:
            return 1
        if "DEFI" in ck:
            return 2
        if "MIXTE" in ck and "(DIGNITE)" in ck:
            return 3
        if "MIXTE" in ck:
            return 4
        if "FORCE" in ck and "(DIGNITE)" in ck:
            return 5
        if "FORCE" in ck:
            return 6
        return 7

    all_priorities.sort(
        key=lambda x: (
            _fam_rank(x.get("categorie")),
            -x.get("score", 0),
            (x.get("orb") if isinstance(x.get("orb"), (int, float)) else 99.0)
        )
    )

    def _take_with_quotas(items, quotas={"DEFI": 7, "FORCE": 7, "MIXTE": 6}, total_limit=30):
        buckets = {"DEFI": [], "FORCE": [], "MIXTE": [], "OTHER": []}
        for it in items:
            ck = _cat_key(it.get("categorie"))
            if "DEFI" in ck:
                buckets["DEFI"].append(it)
            elif "FORCE" in ck:
                buckets["FORCE"].append(it)
            elif "MIXTE" in ck:
                buckets["MIXTE"].append(it)
            else:
                buckets["OTHER"].append(it)

        out = []
        for k in ("DEFI", "FORCE", "MIXTE"):
            out.extend(buckets[k][:quotas.get(k, 0)])

        if len(out) < total_limit:
            pool = (
                buckets["OTHER"]
                + buckets["DEFI"][quotas.get("DEFI", 0):]
                + buckets["FORCE"][quotas.get("FORCE", 0):]
                + buckets["MIXTE"][quotas.get("MIXTE", 0):]
            )
            for it in pool:
                if len(out) >= total_limit:
                    break
                out.append(it)
        return out

    top = _take_with_quotas(all_priorities, total_limit=limit)

    defis_md  = [x for x in top if "DEFI" in _cat_key(x.get('categorie')) and "MIXTE" not in _cat_key(x.get('categorie'))]
    forces_md = [x for x in top if "FORCE" in _cat_key(x.get('categorie'))]
    mixtes_md = [x for x in top if "MIXTE" in _cat_key(x.get('categorie'))]

    lines = [
        "# 🎯 ÉLÉMENTS PRIORITAIRES À ANALYSER",
        "",
        f"**{len(top)} éléments sélectionnés (Défis: {len(defis_md)}, Potentiels: {len(forces_md)}, Mixtes: {len(mixtes_md)})**",
        "**Traite UNIQUEMENT ces éléments. Structure ton analyse en 3 sections : DÉFIS / POTENTIELS / DYNAMIQUES MIXTES**",
        ""
    ]

    if defis_md:
        lines.append("## 🔴 DÉFIS (à intégrer)\n")
        for i, item in enumerate(defis_md, 1):
            orb = f" (orbe {item['orb']:.2f}°)" if isinstance(item.get('orb'), (int,float)) else ""
            lines.append(f"{i}. **{item['description']}**{orb}")
            lines.append(f"   Score: **{item['score']}** — {item['comment']}\n")

    if forces_md:
        lines.append("## 🟢 POTENTIELS (à mobiliser)\n")
        for i, item in enumerate(forces_md, 1):
            orb = f" (orbe {item['orb']:.2f}°)" if isinstance(item.get('orb'), (int,float)) else ""
            lines.append(f"{i}. **{item['description']}**{orb}")
            lines.append(f"   Score: **{item['score']}** — {item['comment']}\n")

    if mixtes_md:
        lines.append("## 🟡 DYNAMIQUES MIXTES (à conscientiser)\n")
        for i, item in enumerate(mixtes_md, 1):
            orb = f" (orbe {item['orb']:.2f}°)" if isinstance(item.get('orb'), (int,float)) else ""
            lines.append(f"{i}. **{item['description']}**{orb}")
            lines.append(f"   Score: **{item['score']}** — {item['comment']}\n")

    return "\n".join(lines).strip()