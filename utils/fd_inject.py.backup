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
    # 1) priorité à la variable d'environnement
    env = os.getenv("FD_CSV_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p

    # 2) candidats usuels (utils/data, data/, rag/, etc.)
    here = Path(__file__).resolve().parent
    candidates = [
        here / "data",
        here.parent / "data",
        Path.cwd() / "data",
        Path("data"),
        Path.cwd() / "utils" / "data",
        here.parent / "rag",               # compat avec rag/
        here.parent.parent / "rag",        # au cas où
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    return (Path.cwd() / "data").resolve()

DATA_DIR = _resolve_data_dir()

# Si tu n'as QU'UN fichier global (ex: rag/data_forces_defis.csv),
# on l'utilise comme fallback pour tous les read_csv().
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
    return s

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
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")  # ← Ajoutez ";" en premier
        except Exception:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
        print(f"[FD_INJECT] lecture CSV: {p.name} (n={len(rows)})  DATA_DIR={DATA_DIR}")

           # >>> AJOUTEZ CECI <
        if rows and "forces" in name.lower():
            print(f"[DEBUG FORCES] Colonnes: {list(rows[0].keys())}")
            print(f"[DEBUG FORCES] Ligne 1: {rows[0]}")
            print(f"[DEBUG FORCES] PLANETE_1='{rows[0].get('PLANETE_1')}', SCORE='{rows[0].get('SCORE')}'")
    # >>> FIN DEBUG <
    print(f"[FD_INJECT] lecture CSV: {p.name} (n={len(rows)})  DATA_DIR={DATA_DIR}")
    return rows

# ─────────────────────────────────────────────────────────────
# Détection aspects à partir du thème
# ─────────────────────────────────────────────────────────────
def _collect_theme_aspects(theme: dict):
    """Renvoie une liste de dicts: {p1, p2, type, orb} depuis theme['aspects'] / 'aspects_significatifs'."""
    raw = theme.get("aspects_significatifs") or theme.get("aspects") or []
    out = []
    for a in raw:
        if isinstance(a, dict):
            p1 = a.get("p1") or a.get("planete1") or a.get("planet1") or a.get("A") or a.get("from")
            p2 = a.get("p2") or a.get("planete2") or a.get("planet2") or a.get("B") or a.get("to")
            t  = a.get("type") or a.get("aspect") or a.get("relation") or a.get("kind")
            orb = a.get("orb") or a.get("orbe") or a.get("delta")
        else:
            # format string très simple: "Soleil Carre Mars (orbe 2.1)"
            p1 = p2 = t = None
            orb = None
            s = str(a)
            import re
            m = re.search(r"^([\wÉÈÊÀÂÔÛÙéèêàâôûù'’ -]+)\s+([\w]+)\s+([\wÉÈÊÀÂÔÛÙéèêàâôûù'’ -]+)", s, flags=re.I)
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
    # "conjonction, carré, opposition" -> {"conjonction","carre","opposition"}
    parts = [x.strip() for x in (s or "").split(",")]
    return {_norm_aspect(x) for x in parts if x}

def detect_aspects_from_csv(theme: dict,
                            csv_name: str,
                            min_score: float = 4.0,
                            limit: int = 10):
    """
    Matche le thème sur un CSV d'aspects (forces ou defis).
    Retourne une liste triée: [{'p1','p2','aspect','score','comment','orb','type'}]
    """
    rows = _read_csv(csv_name)
    theme_aspects = _collect_theme_aspects(theme)

    # >>> DEBUG COLONNES <
    if rows:
        print(f"\n[DEBUG {csv_name}] Colonnes du CSV : {list(rows[0].keys())}")
        print(f"[DEBUG {csv_name}] 1ère ligne brute : {rows[0]}")
        print(f"[DEBUG {csv_name}] SCORE de la 1ère ligne : '{rows[0].get('SCORE')}' (type: {type(rows[0].get('SCORE'))})")
    # >>> FIN DEBUG <

    # >>> DEBUG <
    print(f"\n[DEBUG {csv_name}] Aspects du thème normalisés :")
    for ta in theme_aspects[:5]:  # montre les 5 premiers
        print(f"  - {ta['p1']} {ta['type']} {ta['p2']} (orb={ta.get('orb')})")
    print(f"\n[DEBUG {csv_name}] Lignes CSV avec score >= {min_score} :")
    # >>> FIN DEBUG <

    results = []
    for row in rows:
        p1 = _norm(row.get("PLANETE_1"))
        p2 = _norm(row.get("PLANETE_2"))
        aspects_ok = _parse_aspects_field(row.get("ASPECTS", ""))
        typ = _norm(row.get("TYPE", ""))
        try:
            score = float(row.get("SCORE", 0))
        except Exception:
            score = 0.0
        comment = (row.get("COMMENTAIRE") or "").strip()

        if score < min_score:
            continue

        key_csv = _pair_key(p1, p2)
        for ta in theme_aspects:
            key_theme = _pair_key(ta["p1"], ta["p2"])
            if key_theme != key_csv:
                continue
            if ta["type"] not in aspects_ok:
                continue
            results.append({
                "p1": ta["p1"], "p2": ta["p2"],
                "aspect": ta["type"],
                "orb": ta.get("orb"),
                "score": score,
                "comment": comment,
                "type": typ,
            })

    # tri: score desc, orbe serrée
    results.sort(key=lambda x: (-x["score"], x["orb"] if isinstance(x.get("orb"), (int, float)) else 99.0))
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# Détection état des planètes (ex: rétrograde)
# ─────────────────────────────────────────────────────────────
def detect_etat_planetes(theme: dict,
                         csv_name: str,
                         min_score: float = 4.0,
                         limit: int = 10):
    """
    Matche l'état des planètes : rétrograde, dignités (domicile, exaltation, exil, chute).
    Retourne: [{'planete','etat','score','comment','type'}]
    """
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

        # 1. Gérer les planètes rétrogrades
        if etat in {"retrograde", "rétrograde"}:
            for k, v in plan.items():
                if _norm(k) == planet and (v.get("retro") or v.get("r") or ("retro" in (v.get("flags") or []))):
                    results.append({
                        "planete": k,
                        "etat": "rétrograde",
                        "score": score,
                        "comment": comment,
                        "type": typ,
                    })
        
        # 2. Gérer les dignités (domicile, exaltation, exil, chute)
        elif etat in {"domicile", "exaltation", "exil", "chute"}:
            for k, v in plan.items():
                if _norm(k) != planet:
                    continue
                
                # Vérifier le signe de la planète dans le thème
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
    print("[FD_INJECT] DATA_DIR =", DATA_DIR)
    forces = detect_aspects_from_csv(theme, "aspects_forces.csv", min_score_aspect, limit_forces)
    defis  = detect_aspects_from_csv(theme, "aspects_defis.csv",  min_score_aspect, limit_defis)
    etats  = detect_etat_planetes(theme, "etat_planetes.csv",     min_score_etat,  limit_etat)
    print("[FD_INJECT] counts -> defis:", len(defis), "forces:", len(forces), "etats:", len(etats))

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

    if etats:
        lines.append("### ÉTAT DES PLANÈTES (CSV)")
        for e in etats:
            lines.append(f"- **{e['planete']} {e['etat']}** — score {e['score']}: {e['comment']}")

    return "\n".join(lines).strip()

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
        
        # Convertir romain → arabe
        maison_csv = _roman_to_int(maison_csv_str)  # ← AJOUTÉ
        
        typ = _norm(row.get("TYPE", ""))
        try:
            score = float(row.get("SCORE", 0))
        except:
            score = 0.0
        comment = (row.get("COMMENTAIRE") or "").strip()
        
        if score < min_score:
            continue
        
        # Vérifier si la planète est dans cette maison dans le thème
        for nom_planete, data in planetes.items():
            if _norm(nom_planete) != planete:
                continue
                
            maison_theme = data.get("maison") or data.get("house")  # ← déjà un int
            
            if maison_theme == maison_csv:  # ← Maintenant ça matche !
                results.append({
                    "planete": nom_planete,
                    "maison": maison_csv_str,  # Garde le format romain pour l'affichage
                    "score": score,
                    "comment": comment,
                    "type": typ
                })
    
    results.sort(key=lambda x: -x['score'])
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# Liste unifiée des priorités
# ─────────────────────────────────────────────────────────────
def build_unified_priorities(theme: dict,
                            min_score: float = 3.0,
                            limit: int = 30) -> str:
    """
    Crée une liste UNIFIÉE des 30 éléments les plus importants du thème,
    toutes catégories confondues (aspects, dignités, placements).
    """
    print("[FD_INJECT] Construction de la liste unifiée des priorités...")
    all_priorities = []
    
    # 1. Aspects défis
    defis = detect_aspects_from_csv(theme, "aspects_defis.csv", min_score, 999)
    for d in defis:
        all_priorities.append({
            "categorie": "DÉFI (aspect)",
            "description": f"{d['p1'].title()} {d['aspect']} {d['p2'].title()}",
            "orb": d.get('orb'),
            "score": d['score'],
            "comment": d['comment']
        })
    
    # 2. Aspects forces
    forces = detect_aspects_from_csv(theme, "aspects_forces.csv", min_score, 999)
    for f in forces:
        all_priorities.append({
            "categorie": "FORCE (aspect)",
            "description": f"{f['p1'].title()} {f['aspect']} {f['p2'].title()}",
            "orb": f.get('orb'),
            "score": f['score'],
            "comment": f['comment']
        })
    
    # 3. État des planètes (dignités)
    etats = detect_etat_planetes(theme, "etat_planetes.csv", min_score, 999)
    for e in etats:
        all_priorities.append({
            "categorie": f"{e['type'].upper()} (dignité)",
            "description": f"{e['planete'].title()} {e['etat']}",
            "orb": None,
            "score": e['score'],
            "comment": e['comment']
        })
    
    # 4. Placements en maisons
    try:
        placements = detect_placements_maisons(theme, "placements_maisons.csv", min_score, 999)
        for p in placements:
            all_priorities.append({
                "categorie": f"{p['type'].upper()} (maison)",
                "description": f"{p['planete'].title()} en maison {p['maison']}",
                "orb": None,
                "score": p['score'],
                "comment": p['comment']
            })
    except Exception as e:
        print(f"[FD_INJECT] Placements maisons ignorés: {e}")

    # Tri par score décroissant
    all_priorities.sort(key=lambda x: -x['score'])
    
    # Prendre le top X
    top = all_priorities[:limit]
    
    print(f"[FD_INJECT] {len(all_priorities)} éléments trouvés, top {len(top)} sélectionnés")
    
    # Générer le markdown
    lines = [
        "# 🎯 ÉLÉMENTS PRIORITAIRES À ANALYSER",
        "",
        f"**Les {len(top)} éléments suivants ont été sélectionnés selon leur importance (score).**",
        "**Traite UNIQUEMENT ces éléments en détail. Utilise le contexte global pour nuancer, mais ne développe pas d'autres points.**",
        ""
    ]
    
    for i, item in enumerate(top, 1):
        orb_str = f" (orbe {item['orb']:.2f}°)" if item['orb'] else ""
        lines.append(f"{i}. **[{item['categorie']}]** {item['description']}{orb_str}")
        lines.append(f"   Score: **{item['score']}** — {item['comment']}")
        lines.append("")
    
    return "\n".join(lines)