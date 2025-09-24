# utils/selection_donnees.py

from typing import Dict, Any, List
from utils.formatage import formater_positions_planetes, formater_aspects_significatifs
import re as regex
import math
import unicodedata

ALIASES = {
    "milieu du ciel": "mc",
    "carre": "carré",
    "venus": "vénus",
    "noeud nord": "rahu",
    "nœud nord": "rahu",
    "noeud sud": "ketu",
    "nœud sud": "ketu",
}

def _is_node(name: str) -> bool:
    t = (name or "").strip().lower()
    return t in {"rahu", "ketu", "nœud nord", "noeud nord", "nœud sud", "noeud sud"}

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _norm_sign(x: str) -> str:
    return _norm(x or "")

def _sign_of(occ: Dict[str, Any], pl_name: str) -> str | None:
    """
    Récupère le signe tropical d'une planète depuis le dict des placements occidentaux.
    Gère Vénus/Venus, accents, capitalisations, etc.
    """
    if not isinstance(occ, dict):
        return None
    # tentatives directes
    d = occ.get(pl_name) or occ.get(pl_name.capitalize())
    if isinstance(d, dict) and d.get("signe"):
        return str(d.get("signe"))
    # fallback: boucle tolérante aux variantes
    target = _norm(pl_name)
    for k, v in occ.items():
        if _norm(k) == target and isinstance(v, dict) and v.get("signe"):
            return str(v.get("signe"))
    return None

def _canon_pf_key(line: str) -> str:
    """
    Clé de déduplication 'intelligente' :
    - minuscule + sans accents
    - remplace MC/Milieu du Ciel, carre/carré, venus/vénus, noeud/nœud…
    - supprime (orbe/écart 0.69°), nombres d’angle, etc.
    - ordonne la paire (A … B) pour éviter les inversions
    """
    t = _strip_accents(line.lower())

    # aliases (mc, carre, venus, noeuds…)
    for k, v in ALIASES.items():
        t = regex.sub(rf"\b{k}\b", v, t)

    # normaliser formulation angle
    t = regex.sub(r"en\s+conjonction\s+avec\s+l'?angle\s+", "conjonction ", t)

    # virer (orbe/écart 0.69°) & nombres d’angle
    t = regex.sub(r"\((?:orbe|ecart|écart)\s*[\d\.,]+°?\)", "", t)
    t = regex.sub(r"[\d\.,]+\s*°", "", t)
    t = regex.sub(r"\s+", " ", t).strip()

    # détecter aspect et 2 corps/angles, puis trier la paire
    corps = r"(soleil|lune|mercure|v[ée]nus|mars|jupiter|saturne|uranus|neptune|pluton|chiron|rahu|ketu|lune noire|ascendant|mc|descendant|fc)"
    asp = r"(conjonction|opposition|carr[ée]|trigone|sextile)"
    m = regex.search(rf"\b{corps}\b.*\b{asp}\b.*\b{corps}\b", t)
    if m:
        a, aspect, b = m.group(1), m.group(2), m.group(3)
        pair = " ".join(sorted([a, b]))
        return f"{pair} {aspect}"
    return t


# --- Règles & helpers pour points marquants ---
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))  # enlève les accents

RAPIDES = {"soleil", "lune", "mercure", "venus", "mars"}  # = PERSONNELLES
PERSONNELLES = RAPIDES
SEMI = {"jupiter", "saturne"}
TRANSPERSO = {"uranus", "neptune", "pluton", "rahu", "ketu", "lune noire", "chiron"}
# Alias occidentaux pour Nœuds (si présents dans les aspects/occidentaux)
TRANSPERSO.update({"nœud nord", "noeud nord", "nœud sud", "noeud sud"})
# Nombre maximum d'éléments dans "Points forts"
TOP_N_POINTS_FORTS = 15

def _is_personnelle(planete: str) -> bool:
    return planete in {"Mercure", "Vénus", "Mars"}  # rétro marquants

def _has_conjonction_so_mercure(aspects: list, max_orbe: float = 5.0) -> tuple[bool, float | None]:
    """Détecte une conjonction Soleil–Mercure et retourne (True, orbe) si présente."""
    for a in aspects or []:
        p1, p2 = a.get("p1"), a.get("p2")
        asp = (a.get("aspect") or "").lower()
        try:
            orbe = float(str(a.get("orbe")).replace(",", "."))
        except Exception:
            continue
        if orbe <= max_orbe and asp.startswith("conjonction"):
            if {p1, p2} == {"Soleil", "Mercure"}:
                return True, orbe
    return (False, None)


def aspects_maitre_ascendant(maitre_asc: str | dict, aspects: list, max_orbe: float = 5.0) -> list:
    """
    Retourne les conjonctions serrées au maître d'Ascendant (≤ max_orbe),
    robuste aux variations de clés (p1/p2 vs planete1/planete2) et de formats.
    """
    if not maitre_asc:
        return []

    # 1) Normaliser le nom du maître (dict ou str "Mercure en ...")
    if isinstance(maitre_asc, dict):
        maitre_nom = (maitre_asc.get("planete") or maitre_asc.get("nom") or "").strip()
    else:
        maitre_nom = str(maitre_asc or "").strip()
        if maitre_nom:
            maitre_nom = maitre_nom.split()[0]  # "Mercure en Scorpion" -> "Mercure"
    if not maitre_nom:
        return []
    maitre_nom_norm = maitre_nom.capitalize()

    # 2) Parcours des aspects et filtrage
    out = []
    for a in aspects or []:
        asp_label = (a.get("aspect") or "").strip().lower()

        # lire p1/p2 OU planete1/planete2
        p1_raw = a.get("p1") or a.get("planete1") or ""
        p2_raw = a.get("p2") or a.get("planete2") or ""
        p1 = str(p1_raw).strip().capitalize()
        p2 = str(p2_raw).strip().capitalize()

        # orbe -> float robuste ("1,8" -> 1.8)
        try:
            orbe = float(str(a.get("orbe")).replace(",", "."))
        except Exception:
            continue

        if asp_label.startswith("conjonction") and orbe <= max_orbe:
            if p1 == maitre_nom_norm or p2 == maitre_nom_norm:
                b = dict(a)
                # harmoniser les clés + orbe normalisée
                b["p1"] = p1
                b["p2"] = p2
                b["orbe"] = orbe
                out.append(b)
    return out

# --- Axes majeurs : conjonctions au maître d'Ascendant -----------------------

def _autre_planete_dans_conj(maitre_asc: str, a: dict) -> str:
    p1, p2 = a.get("p1"), a.get("p2")
    return p2 if p1 == maitre_asc else (p1 if p2 == maitre_asc else "")

def construire_axes_conj_maitre_ascendant(
    maitre_asc: str,
    conjonctions: list,
    max_items: int = 3,
    poids_base: float = 0.95,
) -> list[dict]:
    """
    Construit des 'axes majeurs' à partir des conjonctions serrées au maître d'Ascendant.
    Pondère la priorité selon la planète conjointe (transperso > semi > personnelles).
    """
    if not maitre_asc or not conjonctions:
        return []

    def _coerce_orbe(v):
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return 99.0

    axes = []
    conjs = sorted(conjonctions, key=lambda x: _coerce_orbe(x.get("orbe")))[:max_items]

    for a in conjs:
        autre = _autre_planete_dans_conj(maitre_asc, a)
        if not autre:
            continue
        orbe = _coerce_orbe(a.get("orbe"))

        # pondération par catégorie planétaire
        if autre in TRANSPERSO:
            bonus = 0.04
        elif autre in SEMI:
            bonus = 0.02
        elif autre in PERSONNELLES or autre in RAPIDES:
            bonus = 0.0
        else:
            bonus = 0.0

        priorite = poids_base + bonus - min(orbe, 5.0) * 0.03
        priorite = round(max(0.0, min(1.0, priorite)), 3)

        titre = f"Maître d’Ascendant ({maitre_asc}) conjoint {autre}"
        resume = (
            f"Conjonction serrée {maitre_asc}-{autre} (orbe {orbe:.1f}°) → "
            "impact direct sur l’image sociale, le corps (Maison I) et l’élan de vie."
        )
        axes.append({
            "type": "ConjonctionMaîtreAsc",
            "titre": titre,
            "resume": resume,
            "priorite": priorite,
            "tags": ["Ascendant", "Maison I", "Image", "Corps", "Chemin de vie"],
        })
    return axes


def _count_in_house(occ: dict, house: int) -> int:
    n = 0
    for p, d in (occ or {}).items():
        try:
            if int(d.get("maison")) == house:
                n += 1
        except Exception:
            continue
    return n


def _is_valid_amas(occ: dict, house: int, min_total: int = 3, min_personnelles: int = 2) -> bool:
    """Amas = ≥3 planètes dans la même maison, dont ≥2 planètes personnelles (Soleil/Lune/Mercure/Vénus/Mars)."""
    membres = []
    perso = 0
    for p, d in (occ or {}).items():
        try:
            if int(d.get("maison")) == house:
                membres.append(p)
                if p in PERSONNELLES:
                    perso += 1
        except Exception:
            continue
    return len(membres) >= min_total and perso >= min_personnelles

# --- Détection conjonctions aux angles (Asc, MC, Desc, FC) -------------------

def _delta_deg(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d


def detecter_conj_angles(planetes_deg: dict, angles_deg: dict, orb_max: float = 5.0):
    """
    Retourne une liste de dicts: [{'planete','angle','ecart'}] triée par écart croissant.
    - planetes_deg: ex {'Mercure': 318.47, 'Jupiter': 248.39, ...}
    - angles_deg:   ex {'Ascendant': 319.16, 'MC': 248.90, 'Descendant': 139.16, 'FC': 68.90}
    """
    res = []
    for pl, d1 in (planetes_deg or {}).items():
        for angle, d2 in (angles_deg or {}).items():
            ecart = _delta_deg(float(d1), float(d2))
            if ecart <= orb_max:
                res.append({"planete": pl, "angle": angle, "ecart": round(ecart, 2)})
    return sorted(res, key=lambda x: x["ecart"])

def construire_conjonctions_angles_pour_prompts(data: Dict[str, Any], orb_max: float = 5.0) -> Dict[str, str]:
    """
    Utilise detecter_conj_angles(planetes_deg, angles_deg) déjà présent,
    et renvoie des chaînes prêtes pour les prompts :
      {
        "conjonctions_asc": "- Vénus conjonction Ascendant (écart 0.20°)\n- ...",
        "conjonctions_mc":  "...",
        "conjonctions_ic":  "...",
        "conjonctions_dsc": "..."
      }
    """
    planetes_deg = data.get("planetes_deg") or {}
    angles_deg   = data.get("angles_deg") or {}
    if not planetes_deg or not angles_deg:
        return {"conjonctions_asc": "", "conjonctions_mc": "", "conjonctions_ic": "", "conjonctions_dsc": ""}

    items = detecter_conj_angles(planetes_deg, angles_deg, orb_max=orb_max)

    out = {"Ascendant": [], "MC": [], "FC": [], "Descendant": []}
    planetes_valides = {
        "Soleil","Lune","Mercure","Vénus","Venus","Mars",
        "Jupiter","Saturne","Uranus","Neptune","Pluton"
    }
    for it in items:
        pl = it.get("planete")
        ang = it.get("angle")
        ec  = it.get("ecart")
        if pl in planetes_valides and ang in out:
            pl_aff = "Vénus" if pl == "Venus" else pl
            out[ang].append(f"- {pl_aff} conjonction {ang} (écart {ec:.2f}°)")

    return {
        "conjonctions_asc": "\n".join(out["Ascendant"]),
        "conjonctions_mc":  "\n".join(out["MC"]),
        "conjonctions_ic":  "\n".join(out["FC"]),     # IC = FC (alias)
        "conjonctions_dsc": "\n".join(out["Descendant"]),
    }

def _rewrite_maitre_ascendant_line(line: str, occ: dict, data: dict) -> str:
    """
    Replace 'Maître d'Ascendant (...) en position neutre' par
    'Maître d’Ascendant (Mercure) : Balance maison 12' si données dispo.
    """
    # détection du maître (tropical) depuis data
    maitre = (data.get("maitre_ascendant") or data.get("maitre_ascendant_tropical") or data.get("maitre_ascendant_occ"))
    if isinstance(maitre, dict):
        nom = maitre.get("planete") or maitre.get("nom")
    elif isinstance(maitre, str) and maitre.strip():
        nom = maitre.strip().split()[0]
    else:
        nom = None

    if not nom:
        return line

    d = (occ or {}).get(nom) or {}
    signe = d.get("signe")
    maison = d.get("maison")
    if signe or maison:
        suffix = []
        if signe: suffix.append(signe)
        if maison: suffix.append(f"maison {maison}")
        suffix_txt = " ".join(suffix) if suffix else "—"
        return f"Maître d’Ascendant ({nom}) : {suffix_txt}"
    return line

def _filter_retrogrades_line(line: str) -> str | None:
    """
    Garde uniquement les rétrogrades personnelles.
    Retourne None si la ligne ne doit pas être gardée.
    """
    if not line.lower().startswith("planètes rétrogrades"):
        return line
    # ex: "Planètes rétrogrades: Mars rétrograde, Jupiter rétrograde, Saturne rétrograde"
    keep = []
    for token in line.split(":")[-1].split(","):
        name = token.strip().split()[0]
        if _is_personnelle(name):
            keep.append(f"{name} rétrograde")
    if not keep:
        return None
    return "Planètes rétrogrades : " + ", ".join(keep)

# --- Helpers compacts ---

def _lister_planetes_retrogrades(occ: Dict[str, Any]) -> list[str]:
    """Retourne la liste des planètes occidentales marquées rétrogrades (occ[planète]['retrograde'] == True)."""
    retro = []
    if isinstance(occ, dict):
        for nom, p in occ.items():
            try:
                if isinstance(p, dict) and p.get("retrograde") is True:
                    retro.append(str(nom))
            except Exception:
                continue
    return retro

def detecter_amas_personnels(occ: Dict[str, Any], min_perso: int = 3) -> Dict[str, list]:
    """
    Détecte des amas composés uniquement de planètes personnelles (Soleil/Lune/Mercure/Vénus/Mars)
    groupées par SIGNE et par MAISON.
    Retourne:
      {
        "signes": [{"signe": "Scorpion", "membres": ["Lune","Mercure","Mars"]}, ...],
        "maisons": [{"maison": 7, "membres": ["Lune","Mercure","Mars"]}, ...]
      }
    """
    if not isinstance(occ, dict):
        return {"signes": [], "maisons": []}

    # 1) collecter placements perso uniquement
    perso_par_signe: Dict[str, list] = {}
    perso_par_maison: Dict[int, list] = {}

    for pl, d in occ.items():
        try:
            pl_norm = _norm(pl)
            print(f"Planète: {pl} -> normalisée: {pl_norm} -> dans PERSONNELLES: {pl_norm in PERSONNELLES}")
            if pl_norm not in PERSONNELLES:
                continue

            signe = str(d.get("signe") or "").strip()
            maison = int(d.get("maison")) if d.get("maison") is not None else None
        except Exception:
            continue

        if signe:
            perso_par_signe.setdefault(signe, []).append(pl)   # on garde le libellé original pour l’affichage
        if maison is not None:
            perso_par_maison.setdefault(maison, []).append(pl)

    # 2) filtrer >= min_perso
    out_signes = []
    for signe, membres in perso_par_signe.items():
        uniq = sorted(set(membres), key=membres.index)
        if len(uniq) >= min_perso:
            out_signes.append({"signe": signe, "membres": uniq})

    out_maisons = []
    for maison, membres in perso_par_maison.items():
        uniq = sorted(set(membres), key=membres.index)
        if len(uniq) >= min_perso:
            out_maisons.append({"maison": maison, "membres": uniq})

    # trier pour la stabilité (par taille puis alpha/num)
    out_signes.sort(key=lambda x: (-len(x["membres"]), x["signe"]))
    out_maisons.sort(key=lambda x: (-len(x["membres"]), x["maison"]))

    return {"signes": out_signes, "maisons": out_maisons}

def _extraire_axes_interceptes(data: Dict[str, Any]) -> dict:
    """
    Récupère les interceptions calculées en amont.
    Tolère plusieurs orthographes/clés.
    Retourne un dict standardisé:
      {
        'signes': [...],
        'maisons_par_signe': { 'Sagittaire': 'Maison V', ... }
      }
    """
    inter = data.get("interceptions") or {}
    signes = inter.get("signes_interceptes") or inter.get("signes") or []
    maisons = (
        inter.get("maisons_interceptées")    # clé avec accent (ta version)
        or inter.get("maisons_interceptees") # fallback sans accent
        or {}
    )
    return {"signes": signes, "maisons_par_signe": maisons}

def _filtrer_aspects(aspects: List[Dict[str, Any]], max_orbe: float = 5.0) -> List[Dict[str, Any]]:
    """Garde seulement les aspects dont l'orbe <= max_orbe (nombre).
    Tolère que 'orbe' soit str, met en float proprement."""
    out = []
    for a in aspects or []:
        o_raw = a.get("orbe")
        try:
            o = float(str(o_raw).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if o <= max_orbe:
            out.append(a)
    return out

def filtrer_aspects_ascendant(aspects: list, orb_max: float = 5.0) -> list:
    """
    Garde uniquement les aspects pertinents à l’Ascendant pour le Bloc 1 :
    - exclut les oppositions à l’Ascendant (conjonction DSC à traiter ailleurs)
    - orbe <= orb_max (strict)
    - tolère p1/p2 ou planete1/planete2, aspect en str, orbe en str/float
    """
    out = []
    for a in aspects or []:
        asp = (a.get("aspect") or "").strip().lower()
        p1  = (a.get("p1") or a.get("planete1") or "").strip()
        p2  = (a.get("p2") or a.get("planete2") or "").strip()

        # on ne garde que les aspects qui impliquent l'Ascendant
        if p1 != "Ascendant" and p2 != "Ascendant":
            continue

        # orbe → float robuste
        try:
            orbe = float(str(a.get("orbe")).replace(",", "."))
        except Exception:
            continue

        # borne stricte
        if orbe > orb_max:
            continue

        # on retire les oppositions à l’Ascendant
        if asp.startswith("opposition"):
            continue

        out.append(a)
    return out

def filtrer_planetes_maison_occidentale(noms: list[str]) -> list[str]:
    """
    Garde uniquement les vraies planètes occidentales dans une maison.
    Exclut Rahu/Ketu (et abréviations possibles comme 'K').
    Normalise 'Venus' -> 'Vénus'.
    """
    if not noms:
        return []

    PLANETES_OCC = {
        "Soleil","Lune","Mercure","Vénus","Venus","Mars",
        "Jupiter","Saturne","Uranus","Neptune","Pluton"
    }
    NOEUDS_ABBR = {"Rahu","Ketu","Nœud Nord","Noeud Nord","Nœud Sud","Noeud Sud","NN","NS","R","K","Noeud"}

    out = []
    for p in noms:
        p_str = str(p).strip()
        if not p_str:
            continue

        # Exclure nœuds et abréviations douteuses
        if p_str in NOEUDS_ABBR:
            continue

        if p_str in PLANETES_OCC:
            out.append("Vénus" if p_str == "Venus" else p_str)

    return out


def exclure_aspects_aux_noeuds(aspects: list) -> list:
    """
    Supprime les aspects impliquant Rahu/Ketu (ou leurs libellés noeud nord/sud).
    Tolère p1/p2 ou planete1/planete2.
    """
    NOEUDS = {"Rahu","Ketu","Nœud Nord","Noeud Nord","Nœud Sud","Noeud Sud"}
    out = []
    for a in aspects or []:
        p1 = str(a.get("p1") or a.get("planete1") or "").strip()
        p2 = str(a.get("p2") or a.get("planete2") or "").strip()
        if (p1 in NOEUDS) or (p2 in NOEUDS):
            continue
        out.append(a)
    return out

def _extraire_nakshatra_lune_et_maitre_asc(data_theme: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne {'lune_nakshatra': str|None, 'maitre_asc_planete': str|None, 'maitre_asc_nakshatra': str|None}"""
    res = {"lune_nakshatra": None, "maitre_asc_planete": None, "maitre_asc_nakshatra": None}
    # 1) Lune
    ved = data_theme.get("placements_vediques") or data_theme.get("resultats_vediques") or {}
    lune_v = ved.get("Lune") or {}
    res["lune_nakshatra"] = lune_v.get("nakshatra")

    # 2) Maître d’Ascendant (planète)
    # On essaye plusieurs emplacements/format possibles
    maitre_occ = (data_theme.get("maitre_ascendant_occ")
                  or data_theme.get("maitre_ascendant_tropical")
                  or data_theme.get("maitre_ascendant") )
    planete_nom = None
    if isinstance(maitre_occ, dict):
        planete_nom = maitre_occ.get("planete") or maitre_occ.get("nom")
    elif isinstance(maitre_occ, str):
        # ex: "Mercure en Scorpion (Maison 3)" -> "Mercure"
        planete_nom = maitre_occ.strip().split()[0] if maitre_occ.strip() else None

    res["maitre_asc_planete"] = planete_nom

    # 3) Nakshatra du maître (via placements védiques de la planète)
    if planete_nom and isinstance(ved, dict):
        p_v = ved.get(planete_nom) or {}
        res["maitre_asc_nakshatra"] = p_v.get("nakshatra")

    return res

def construire_payload_analyse_gratuite(data_theme: Dict[str, Any], max_orbe: float = 5.0) -> Dict[str, Any]:
    """Filtrage pour l'analyse gratuite : placements occidentaux + maison, aspects <= 5°, points forts."""
    
    # ✅  Utiliser les vraies clés
    occ = (data_theme.get("planetes")            # ← VOS VRAIES DONNÉES
           or data_theme.get("placements_occidentaux")
           or data_theme.get("placements_occ")
           or data_theme.get("resultats_tropical")
           or {})
    
    aspects = data_theme.get("aspects") or data_theme.get("aspects_occidentaux") or []
    points_forts = (data_theme.get("points_forts_compacts")
                    or data_theme.get("points_forts")
                    or data_theme.get("axes_majeurs_str")
                    or "")

    return {
        "placements_occidentaux": occ,
        "aspects_filtrés": _filtrer_aspects(aspects, max_orbe),
        "points_forts": points_forts,
    }

def construire_payload_point_astral(data_theme: Dict[str, Any], max_orbe: float = 5.0) -> Dict[str, Any]:
    """Filtrage pour le flash astral : idem analyse gratuite + nakshatra(Lune) + nakshatra(maître Asc)."""
    base = construire_payload_analyse_gratuite(data_theme, max_orbe)
    nk = _extraire_nakshatra_lune_et_maitre_asc(data_theme)

    base.update({
        "lune_nakshatra": nk["lune_nakshatra"],
        "maitre_asc_planete": nk["maitre_asc_planete"],
        "maitre_asc_nakshatra": nk["maitre_asc_nakshatra"],
    })
    return base


def _get_points_forts_str(data: Dict[str, Any]) -> str:
    """Construit la liste **nettoyée** de points marquants à partir de tes données existantes."""
    # base brute (tes sources possibles)
    raw = (data.get("axes_majeurs_str")
           or data.get("points_forts")
           or (data.get("placements_occ") or {}).get("points_forts")
           or (data.get("placements_fusion") or {}).get("points_forts")
           or "")
    print(f"Selection_Données : DEBUG raw: {raw}")
    
    # Occidentaux utiles pour enrichir/valider
    occ = (data.get("planetes")
           or data.get("placements_occidentaux")
           or data.get("placements_occ")
           or data.get("resultats_tropical")
           or {})
    aspects = data.get("aspects") or data.get("aspects_occidentaux") or []

    # 1) tokeniser proprement
    lines = []
    if isinstance(raw, list):
        lines = [str(l).strip() for l in raw if str(l).strip()]
    else:
        for l in str(raw).splitlines():
            l = l.strip(" -•\t")
            if l:
                lines.append(l)

    cleaned_lines = []
    for line in lines:
        # Si c'est un amas personnel, vérifier qu'il ne contient que des planètes personnelles
        if "🌟 Amas personnel" in line:
            match = regex.search(r'\((.*?)\)', line)
            if match:
                planetes = [p.strip() for p in match.group(1).split(',')]
                planetes_perso = [p for p in planetes if _norm(p) in PERSONNELLES]
                if len(planetes_perso) < 3:
                    continue
                if " en " in line:
                    partie = line.split(" en ")[1].split(" (")[0]
                    line = f"🌟 Amas personnel en {partie} ({', '.join(planetes_perso)})"
        cleaned_lines.append(line)

    lines = cleaned_lines  # Remplacer la liste originale

    cleaned = []
    seen_keys = set()

    # 2) combustion (via ta détection Soleil–Mercure)
    conj_sm, orbe_sm = _has_conjonction_so_mercure(aspects, max_orbe=5.0)
    combustion_label = None
    if conj_sm and orbe_sm is not None:
        combustion_label = f"Soleil conjoint Mercure ({round(orbe_sm, 2)}°) → combustion"

    for line in lines:
        base = line.lower()

        if base.startswith("ascendant en "):
            continue
        if "aspect harmonique soleil-lune" in base:
            continue
        if "maître d'ascendant" in base and "position neutre" in base:
            line = _rewrite_maitre_ascendant_line(line, occ, data)
        if base.startswith("planètes rétrogrades"):
            line = _filter_retrogrades_line(line)
            if not line:
                continue

        key = _canon_pf_key(line)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned.append(line)

    # --- Fallback générique pour angles/planètes en degrés (sans hardcodes) ---
    planetes_deg = (data.get("planetes_deg") or {})
    angles_deg   = (data.get("angles_deg")   or {})

    def _long_from_signe_deg(signe: str, deg: float) -> float:
        z = {"bélier":0,"belier":0,"taureau":30,"gémeaux":60,"gemeaux":60,"cancer":90,
            "lion":120,"vierge":150,"balance":180,"scorpion":210,"sagittaire":240,
            "capricorne":270,"verseau":300,"poissons":330}
        base = z.get((signe or "").lower(), 0)
        try:
            return (base + float(str(deg).replace(",", "."))) % 360.0
        except Exception:
            return base

    # 1) Planètes → longitude
    if not planetes_deg:
        occ_for_deg = (data.get("planetes")
                    or data.get("placements_occidentaux")
                    or data.get("placements_occ")
                    or data.get("resultats_tropical")
                    or {})
        tmp = {}
        for pl, d in (occ_for_deg or {}).items():
            signe = (d or {}).get("signe")
            degre = (d or {}).get("deg") or (d or {}).get("degre") or (d or {}).get("degré")
            if signe is not None and degre is not None:
                tmp[pl] = _long_from_signe_deg(signe, degre)
        planetes_deg = tmp


    # 2) Angles → longitude
    if not angles_deg:
        asc_long = data.get("asc_long") or data.get("asc_deg")
        mc_long  = data.get("mc_long")  or data.get("mc_deg")

        maisons = data.get("maisons_occidentales") or {}
        if asc_long is None:
            m1 = maisons.get("Maison 1") or maisons.get("Maison I") or {}
            s1 = m1.get("signe"); d1 = m1.get("deg") or m1.get("degre") or m1.get("degré")
            if s1 is not None and d1 is not None:
                asc_long = _long_from_signe_deg(s1, d1)
        if mc_long is None:
            m10 = maisons.get("Maison 10") or maisons.get("Maison X") or {}
            s10 = m10.get("signe"); d10 = m10.get("deg") or m10.get("degre") or m10.get("degré")
            if s10 is not None and d10 is not None:
                mc_long = _long_from_signe_deg(s10, d10)

        tmp_angles = {}
        if asc_long is not None:
            tmp_angles["Ascendant"]  = float(asc_long) % 360.0
            tmp_angles["Descendant"] = (float(asc_long) + 180.0) % 360.0
        if mc_long is not None:
            tmp_angles["MC"] = float(mc_long) % 360.0
            tmp_angles["FC"] = (float(mc_long) + 180.0) % 360.0

        angles_deg = tmp_angles

    # expose pour le bloc suivant
    data["planetes_deg"] = planetes_deg
    data["angles_deg"]   = angles_deg


    # === Conjonctions planète/angle (Asc, MC, Desc, FC) — injection fiable + debug ===
    try:
        
        # Détection réelle
        conj_angles = detecter_conj_angles(planetes_deg, angles_deg, orb_max=5.0)
        print("[PF DEBUG] conj_angles détectées (brut) :", conj_angles)

        # Autoriser uniquement les VRAIES planètes
        planetes_valides = {
            "Soleil","Lune","Mercure","Vénus","Venus","Mars",
            "Jupiter","Saturne","Uranus","Neptune","Pluton"
        }
        angles_valides = {"Ascendant","MC","Descendant","FC"}

        added = 0
        for ca in (conj_angles or []):
            pl = ca.get("planete")
            ang = ca.get("angle")
            ec  = ca.get("ecart")
            if (pl not in planetes_valides) or (ang not in angles_valides):
                # Exclut Lune Noire, Rahu/Ketu, Chiron, etc.
                continue

            line_ca = f"{pl} conjonction {ang} (écart {ec}°)"
            key_ca  = _canon_pf_key(line_ca)
            if key_ca not in seen_keys:
                cleaned.append(line_ca)
                seen_keys.add(key_ca)
                added += 1
                print("[PF DEBUG] ADDED PF (angle) →", line_ca)
            else:
                print("[PF DEBUG] SKIP duplicate (angle) →", line_ca)

        if added == 0:
            print("[PF DEBUG] Aucun PF ajouté depuis conj_angles (vérifier orb_max, noms, ou dédup).")

    except Exception as e:
        print("[PF DEBUG] ERREUR conj_angles :", e)


    # 3.ter) Injecter les aspects majeurs directement depuis la liste des aspects
    for aspect_dict in aspects:
        p1 = aspect_dict.get("planete1") or aspect_dict.get("p1") or ""
        p2 = aspect_dict.get("planete2") or aspect_dict.get("p2") or ""
        asp_type = aspect_dict.get("aspect") or ""
        orbe = aspect_dict.get("orbe", 0)

        # ❌ On ne promeut jamais l'opposition à l'Ascendant dans les "Points forts"
        if asp_type.lower().startswith("opposition") and (_norm(p1) == "ascendant" or _norm(p2) == "ascendant"):
            continue

        if asp_type.lower() in ["conjonction", "opposition", "carré", "carre"]:
            if _is_node(p1) or _is_node(p2):
                continue

            # 🔹 détecter conjonction dissociée (même orbe, signes différents)
            label = asp_type
            if asp_type.lower() == "conjonction":
                s1 = _sign_of(occ, p1)
                s2 = _sign_of(occ, p2)
                if s1 and s2 and _norm_sign(s1) != _norm_sign(s2):
                    label = "Conjonction (dissociée)"

            line_aspect = f"{p1} {label} {p2} (orbe {orbe}°)"
            key_aspect = _canon_pf_key(line_aspect)
            if key_aspect not in seen_keys:
                cleaned.append(line_aspect)
                seen_keys.add(key_aspect)

    # 3) Injecter combustion propre (et retirer variantes moches/duplicatives)
    if combustion_label:
        cleaned = [l for l in cleaned if "combustion" not in l.lower()]
        cleaned = [l for l in cleaned if "soleil conjonction mercure" not in l.lower()]
        cleaned.append(combustion_label)

    # 3.quater) Injecter les AMAS PERSONNELS (réservés comme points forts)
    occ_for_amas = (
        data.get("planetes")
        or data.get("placements_occidentaux")
        or data.get("placements_occ")
        or data.get("resultats_tropical")
        or {}
    )
    try:
        amas = detecter_amas_personnels(occ_for_amas, min_perso=3)
        print(f"Selection_données EBUG amas détectés: {amas}")
        amas_lines = []
        for item in amas.get("signes", []):
            signe = item["signe"]
            membres = ", ".join(item["membres"])
            amas_lines.append(f"🌟 Amas personnel en {signe} ({membres})")
        for item in amas.get("maisons", []):
            maison = item["maison"]
            membres = ", ".join(item["membres"])
            amas_lines.append(f"🌟 Amas personnel en {maison} ({membres})")
        for l in amas_lines:
            k = _canon_pf_key(l)
            if k not in seen_keys:
                cleaned.append(l)
                seen_keys.add(k)
    except Exception:
        pass

    # 4) Amas : filtrage strict (≥3 planètes, ≥2 personnelles, ≤1 transsaturnienne)
    out = []
    SIGNS_RE = r"(bélier|belier|taureau|gémeaux|gemeaux|cancer|lion|vierge|balance|scorpion|sagittaire|capricorne|verseau|poissons)"
    TRANSSAT_LOCAL = {"uranus", "neptune", "pluton"}  # en minuscules

    for l in cleaned:
        ll = l.lower()

        if ll.startswith("amas"):
            house = None
            sign_txt = None

            # a) essaie d’attraper une MAISON (nombre)
            m_house = regex.search(r"maison\s+(\d+)|\ben\s+(\d+)\b", ll)
            if m_house:
                house = int(next(g for g in m_house.groups() if g))

            # b) sinon, essaie d’attraper un SIGNE (Amas en Verseau, etc.)
            if house is None:
                m_sign = regex.search(rf"\ben\s+{SIGNS_RE}\b", ll)
                if m_sign:
                    sign_txt = m_sign.group(1)

            # c) validation stricte directement ici (sans nouveau helper)
            total = 0
            perso = 0
            transsat = 0

            for pl, d in (occ or {}).items():
                try:
                    pl_norm = _norm(pl)  # minuscules, sans accents
                    pl_sign = (d.get("signe") or "")
                    pl_house = d.get("maison")
                except Exception:
                    continue

                # Filtre “portée” (maison OU signe)
                if house is not None:
                    try:
                        if int(pl_house) != house:
                            continue
                    except Exception:
                        continue
                elif sign_txt is not None:
                    if _norm(pl_sign) != _norm(sign_txt):
                        continue
                else:
                    # pas de maison ni de signe lisible → on rejette par prudence
                    total = 0
                    break

                total += 1
                if pl_norm in PERSONNELLES:
                    perso += 1
                if pl_norm in TRANSSAT_LOCAL:
                    transsat += 1

            # garde l’amas seulement s’il respecte les 3 conditions
            if not (total >= 3 and perso >= 2 and transsat <= 1):
                continue  # on jette la ligne d’amas

        out.append(l)

    # 4.5) Filtrer les sextiles et trigones (garder seulement les aspects marquants)
    filtered = []
    for line in out:
        ll = line.lower()
        if "sextile" in ll or "trigone" in ll:
            continue
        filtered.append(line)
    out = filtered

    # 4.6) Retirer explicitement l'opposition à l'Ascendant des points forts
    out = [l for l in out if not ("ascendant" in _strip_accents(l).lower() and "opposition" in _strip_accents(l).lower())]

    # 5) TRI global par score (angles boostés) puis déduplication finale
    sorted_all = trier_points_forts(out)

    # 5) TRI global par score (angles boostés) puis déduplication finale

    sorted_all = trier_points_forts(out)

    # 6) Séparer en Points forts et Informations complémentaires
    def _is_major_aspect(s: str) -> bool:
        t = s.lower()
        if any(k in t for k in ["rahu", "ketu", "nœud", "noeud"]):
            return False
        return any(k in t for k in ["conjonction", "opposition", "carré", "carre"])

    def _is_luminaire_lourde(s: str) -> bool:
        t = s.lower()
        a_luminaire = ("soleil" in t) or ("lune" in t)
        a_lourde = any(x in t for x in ["saturne","uranus","neptune","pluton"])
        return a_luminaire and a_lourde and _is_major_aspect(s)

    majors = [s for s in sorted_all if _is_major_aspect(s)]

    # 6.2) MUST-HAVE : 2 luminaires+lourdes max
    must = []
    seen_local = set()
    for s in majors:
        if _is_luminaire_lourde(s):
            k = s.lower()
            if k not in seen_local:
                must.append(s); seen_local.add(k)
            if len(must) == 2:
                break

    # + 1 amas personnel si présent
    def _is_amas_personnel(s: str) -> bool:
        return s.startswith("🌟 Amas personnel")
    for s in sorted_all:
        if _is_amas_personnel(s):
            must.append(s)
            break

    # 6.3) Compléter
    rest = [s for s in majors if s.lower() not in set(x.lower() for x in must)]
    points_forts = (must + rest)[:TOP_N_POINTS_FORTS]

    # — Déclassement “maison angulaire (…)" s’il existe la conjonction angle correspondante
    demote_lines = []
    def _planet_of(line: str) -> str | None:
        for pl in ["Soleil","Lune","Mercure","Vénus","Venus","Mars",
                   "Jupiter","Saturne","Uranus","Neptune","Pluton"]:
            if pl.lower() in line.lower():
                return "Vénus" if pl.lower() == "venus" else pl
        return None
    def _angle_tag(line: str) -> str | None:
        t = line.lower()
        if "ascendant" in t: return "Ascendant"
        if " mc" in t or "milieu du ciel" in t: return "MC"
        if "descendant" in t: return "Descendant"
        if " fc" in t or "fond du ciel" in t: return "FC"
        return None

    conj_angle_keys = set()
    for s in points_forts:
        if "conjonction" in s.lower() and _angle_tag(s):
            conj_angle_keys.add(_canon_pf_key(s))

    for s in points_forts:
        if "maison angulaire" in s.lower():
            pl = _planet_of(s)
            for ck in conj_angle_keys:
                if pl and pl.lower() in ck:
                    demote_lines.append(s)
                    break

    if demote_lines:
        points_forts = [x for x in points_forts if x not in set(demote_lines)]

    # 6.4) Informations complémentaires
    infos_compl = [l for l in sorted_all if l not in points_forts]

    # 7) Format final
    result = "### Points forts\n"
    result += "\n".join(f"- {x}" for x in points_forts)
    if infos_compl:
        result += "\n\n### Informations complémentaires\n"
        result += "\n".join(f"- {x}" for x in infos_compl)
    return result

def construire_selection_analyse_gratuite(data: Dict[str, Any], max_orbe: float = 5.0) -> str:
    occ = (data.get("planetes")
           or data.get("placements_occidentaux")
           or data.get("placements_occ")
           or data.get("resultats_tropical")
           or {})
    aspects = data.get("aspects") or data.get("aspects_occidentaux") or []
    aspects_filtrés = _filtrer_aspects(aspects, max_orbe)
    points_forts = _get_points_forts_str(data)

    blocs = []
    blocs.append("### Placements occidentaux")
    blocs.append(formater_positions_planetes(occ))

    retro_list = _lister_planetes_retrogrades(occ)
    if retro_list:
        blocs.append("\n### Planètes rétrogrades")
        blocs.append(", ".join(retro_list))

    blocs.append("\n### Aspects (≤ 5° d'orbe)")
    blocs.append(formater_aspects_significatifs(aspects_filtrés, seuil_orbe=max_orbe, avec_arrondi=True))

    if points_forts:
        # Ajoute une ligne blanche si le bloc précédent n'est pas vide
        if blocs and blocs[-1].strip():
            blocs.append("")  # ligne vide pour séparer visuellement
        blocs.append(points_forts.strip())

    return "\n".join(blocs).strip()


def _is_noeud_label(x: str) -> bool:
    t = (x or "").strip().lower()
    return t in {"rahu","ketu","nœud nord","noeud nord","nœud sud","noeud sud","nn","ns"}

def _to_noeud_display(x: str) -> str:
    t = (x or "").strip().lower()
    if t in {"rahu","nœud nord","noeud nord","nn"}:
        return "Nœud Nord"
    if t in {"ketu","nœud sud","noeud sud","ns"}:
        return "Nœud Sud"
    return x

def extraire_noeuds_pour_bloc5(data: Dict[str, Any], max_orbe: float = 5.0) -> Dict[str, Any]:
    """
    Retourne un paquet propre pour le Bloc 5 :
      {
        "placements": {"Nœud Nord": "Signe — Maison X", "Nœud Sud": "Signe — Maison Y"},
        "aspects_list": ["Soleil Trigone Nœud Nord (orbe 1.20°)", ...],   # format prêt pour prompt
        "aspects_raw":  [ {p1,p2,aspect,orbe}, ... ]                       # si besoin d’un traitement ultérieur
      }
    NB : On laisse les PF exclure les nœuds ; ici on les **réintroduit** pour la synthèse finale.
    """
    occ = (data.get("planetes")
           or data.get("placements_occidentaux")
           or data.get("placements_occ")
           or data.get("resultats_tropical")
           or {})

    # --- Placements (signe + maison) ---
    placements = {}
    for k in occ.keys():
        if _is_noeud_label(k):
            d = occ.get(k) or {}
            signe = d.get("signe")
            maison = d.get("maison")
            label = _to_noeud_display(k)
            if signe or maison is not None:
                placements[label] = f"{signe or '?'} — Maison {maison if maison is not None else '?'}"

    # --- Aspects (≤ max_orbe) impliquant un nœud ---
    aspects_all = data.get("aspects") or data.get("aspects_occidentaux") or []
    aspects_raw = []
    aspects_list = []

    def _norm_orbe(v):
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return 99.0

    for a in aspects_all:
        p1 = a.get("p1") or a.get("planete1") or ""
        p2 = a.get("p2") or a.get("planete2") or ""
        if not (_is_noeud_label(p1) or _is_noeud_label(p2)):
            continue
        orbe = _norm_orbe(a.get("orbe"))
        if orbe > max_orbe:
            continue
        aspect = (a.get("aspect") or a.get("type") or "").strip()
        # Format d’affichage cohérent
        disp_p1 = _to_noeud_display(p1)
        disp_p2 = _to_noeud_display(p2)
        aspects_list.append(f"{disp_p1} {aspect} {disp_p2} (orbe {orbe:.2f}°)")
        aspects_raw.append({
            "p1": disp_p1, "p2": disp_p2, "aspect": aspect, "orbe": orbe
        })

    # Tri par orbe croissante
    aspects_raw.sort(key=lambda x: x.get("orbe", 99.0))
    # Re-génère la liste formatée triée
    aspects_list = [f"{x['p1']} {x['aspect']} {x['p2']} (orbe {x['orbe']:.2f}°)" for x in aspects_raw]

    return {
        "placements": placements,
        "aspects_list": aspects_list,
        "aspects_raw": aspects_raw,
    }

def construire_selection_point_astral(data: Dict[str, Any], max_orbe: float = 5.0) -> str:
    """Même base que l'analyse gratuite + Nakshatra Lune et Maître d'Ascendant (uniquement)."""
    base = construire_selection_analyse_gratuite(data, max_orbe)

    sections = [base]  # on part de la partie occidentale (placements, aspects, points forts)

    # === Axes interceptés (OCCIDENTAL) — à placer avant le védique ===
    axes = _extraire_axes_interceptes(data)
    signes_int = axes["signes"]
    maisons_int = axes["maisons_par_signe"]

    extras_axes = []
    if signes_int or maisons_int:
        extras_axes.append("### Axes interceptés")
        if signes_int:
            extras_axes.append("- Signes interceptés : " + ", ".join(signes_int))
        if maisons_int:
            for signe in sorted(maisons_int.keys(), key=lambda s: s):
                extras_axes.append(f"- {signe} intercepté en {maisons_int[signe]}")
    if extras_axes:
        sections.append("\n".join(extras_axes))

    # ✅  : Utiliser les vraies clés védiques
    ved = (
        data.get("planetes_vediques")         # tes planètes en sidéral avec nakshatra
        or data.get("placements_vediques")
        or data.get("resultats_vediques")
        or {}
    )

    # 1) Nakshatra de la Lune (sidéral)
    lune_nak = (ved.get("Lune") or {}).get("nakshatra")

    # 2) Maître d'Ascendant **sidéral** (déjà calculé en amont)
    maitre_v = data.get("maitre_ascendant_vedique") or {}
    maitre_nom = maitre_v.get("nom")
    maitre_nak = maitre_v.get("nakshatra")  # s’il existe
    # (tu as aussi degre/signe/maison si tu veux enrichir plus tard)

    # --- VÉDIQUE ---
    extras_ved = ["### Spécificités védiques utiles"]
    if lune_nak:
        extras_ved.append(f"- Lune — Nakshatra : {lune_nak}")
    if maitre_nom:
        ligne = f"- Maître d'Ascendant (sidéral) : {maitre_nom}"
        if maitre_nak:
            ligne += f" — Nakshatra : {maitre_nak}"
        extras_ved.append(ligne)
    if len(extras_ved) > 1:
        sections.append("\n".join(extras_ved))

    # ✅ Assemblage final : on JOINT *sections* (et pas juste base + extras_str)
    return "\n\n".join(s for s in sections if s).strip()

def formater_axes_majeurs(axes: list[dict]) -> str:
    """
    Rend une liste d'axes sous forme de puces lisibles.
    Si 'priorite' existe, on ordonne du plus prioritaire au moins prioritaire.
    """
    if not axes:
        return ""
    try:
        axes_sorted = sorted(axes, key=lambda x: x.get("priorite", 0), reverse=True)
    except Exception:
        axes_sorted = axes
    lignes = []
    for ax in axes_sorted:
        titre = ax.get("titre") or "Axe majeur"
        resume = ax.get("resume") or ""
        lignes.append(f"- {titre} : {resume}")
    return "\n".join(lignes)

def construire_axes_majeurs_global(data: dict) -> str:
    """
    Construit un bloc unique 'axes majeurs globaux' à partir :
      - axes_majeurs_str (si tu en as déjà)
      - conj_maitre_asc_str (liste lisible des conjonctions au maître de l’Ascendant)
      - points forts (via _get_points_forts_str)
    Retourne une seule chaîne, sections concaténées.
    """
    # 1) Récupère chaque source, tolérant l’absence
    axes_str = (data.get("axes_majeurs_str") or "").strip()
    conj_str = (data.get("conj_maitre_asc_str") or "").strip()
    pf_str   = _get_points_forts_str(data).strip()

    sections = []
    if axes_str:
        sections.append("### Axes déjà identifiés\n" + axes_str)
    if conj_str:
        sections.append("### Conjonctions au maître d’Ascendant\n" + conj_str)
    if pf_str:
        sections.append(pf_str)  # contient déjà "### Points forts" + "### Informations complémentaires"

    return "\n\n".join(sections).strip()


PLANET_WEIGHTS: Dict[str, float] = {
    # Luminaires (forts, mais moins “tranchants” que Mars/Pluton)
    "Soleil": 1.25, "Lune": 1.25,
    # Personnelles
    "Mercure": 0.60, "Vénus": 0.60, "Mars": 1.20,
    # Sociales
    "Jupiter": 0.80, "Saturne": 1.10,
    # Transpersonnelles
    "Uranus": 1.00, "Neptune": 0.90, "Pluton": 1.30,
    # Points
    "Chiron": 0.70, "Lune Noire": 0.70, "Rahu": 1.00, "Ketu": 1.00,
}

ASPECT_WEIGHTS: Dict[str, float] = {
    "Conjonction": 1.30,
    "Opposition": 1.20,
    "Carré": 1.15,
    "Trigone": 0.90,
    "Sextile": 0.80,
}

# Orbes “de référence” pour la pénalité
ASPECT_ORB_REF: Dict[str, float] = {
    "Conjonction": 8.0,
    "Opposition": 6.0,
    "Carré": 6.0,
    "Trigone": 5.0,
    "Sextile": 4.0,
}

# Orbe max spécifique pour conjonctions aux angles
ANGLE_ORB_MAX = 5.0
# Bonus multiplicatif sur conjonctions aux angles (Asc, MC, Desc, FC)
ANGLE_BONUS: Dict[str, float] = {
    "Ascendant": 1.80,
    "MC": 1.90,
    "Descendant": 1.60,
    "FC": 1.50,
}

HEAVY_SET = {"Mars", "Saturne", "Uranus", "Neptune", "Pluton"}

# Planètes sociales/transpersonnelles (deux lentes ensemble = moins personnel)
SLOW_SET = {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}

def _planet_weight(p: str) -> float:
    return PLANET_WEIGHTS.get(p, 0.65)

def _aspect_weight(a: str) -> float:
    return ASPECT_WEIGHTS.get(a, 0.85)

def _orb_factor(aspect: str, orbe: float) -> float:
    ref = ASPECT_ORB_REF.get(aspect, 5.0)
    # pénalité lissée : 1 à orbe=0, puis chute linéaire jusqu’à ~0.2 au-delà du ref
    factor = max(0.2, 1.0 - (orbe / max(1e-9, ref)))
    return factor

def _pair_weight(p1: str, p2: str) -> float:
    """Poids duo : somme + bonus si duo 'tranchant' (Mars/Pluton/Saturne etc.)."""
    w1, w2 = _planet_weight(p1), _planet_weight(p2)
    base = w1 + w2
    # petit bonus si au moins une lourde + Mars (ex: Mars–Pluton) ou duo de lourdes
    heavy_count = int(p1 in HEAVY_SET) + int(p2 in HEAVY_SET)
    if heavy_count == 2 or ("Mars" in {p1, p2} and heavy_count >= 1):
        base *= 1.15
    return base

def score_aspect_dict(a: Dict[str, Any]) -> float:
    """
    Score un aspect structuré: {'p1','p2','aspect','orbe'}
    """
    p1, p2 = a.get("p1",""), a.get("p2","")
    aspect = a.get("aspect","")
    orbe = float(a.get("orbe", 5.0))

    pair = _pair_weight(p1, p2)                   # planètes
    aw = _aspect_weight(aspect)                   # type d’aspect
    of = _orb_factor(aspect, orbe)                # orbe

    score = pair * aw * of * 100.0
    return score

def score_angle_conjunction(item: Dict[str, Any]) -> float:
    """
    Score une conjonction planète–angle: {'planete','angle','ecart'}
    """
    planete = item.get("planete","")
    angle = item.get("angle","")
    ecart = float(item.get("ecart", 99.0))

    if ecart > ANGLE_ORB_MAX:
        return 0.0

    base = _planet_weight(planete) * 120.0  # base forte
    bonus = ANGLE_BONUS.get(angle, 1.4)
    # plus c'est serré, plus c'est gros
    tight = max(0.35, 1.0 - (ecart / ANGLE_ORB_MAX))
    return base * bonus * tight

# -------------------------------
# Si tu dois encore scorer depuis des strings "points_forts"
# (fallback parser simple ; recommandé : travailler en dicts)
# -------------------------------

_RE_NUM = regex.compile(r"(?:orbe|écart|ecart)\s*([\d\.,]+)")

def _parse_orbe(text: str) -> float:
    t = text.replace(",", ".").lower()
    m = _RE_NUM.search(t)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # fallback: cherche un nombre isolé style "0.69°"
    m2 = regex.search(r"([\d\.]+)\s*°", t)
    return float(m2.group(1)) if m2 else 5.0

def score_point_fort_text(pf: str) -> float:
    t = pf.lower()
    t_no_acc = _strip_accents(t)
    

    # Debug spécifique pour Neptune MC
    if "neptune" in t_no_acc and ("mc" in t_no_acc or "milieu du ciel" in t_no_acc):
        print(f"DEBUG Neptune MC détecté dans: {pf}")
        print(f"t_no_acc: {t_no_acc}")
        print(f"PLANET_WEIGHTS.keys(): {list(PLANET_WEIGHTS.keys())}")
        
        # Test de correspondance
        for pl in PLANET_WEIGHTS.keys():
            if pl.lower() in t_no_acc:
                print(f"Planète trouvée: {pl} -> {pl.lower()}")


    # PRIORITÉ TRÈS HAUTE : Planètes personnelles vs planètes difficiles (aspects tendus)
    personnelles = ["soleil", "lune", "mercure", "vénus", "mars"]
    difficiles = ["mars", "saturne", "uranus", "pluton"]

    planetes_dans_aspect = [pl for pl in personnelles + difficiles if pl in t]
    a_personnelle = any(pl in planetes_dans_aspect for pl in personnelles)
    a_difficile = any(pl in planetes_dans_aspect for pl in difficiles)

    if (a_personnelle and a_difficile and 
        any(asp in t for asp in ["carré", "carre", "opposition", "conjonction"])):
        orbe = _parse_orbe(t)
        if orbe <= 2.0:
            base_score = 420.0
            if "opposition" in t:
                base_score *= 1.1
            elif "carré" in t or "carre" in t:
                base_score *= 1.15
            elif "conjonction" in t:
                base_score *= 1.05
            tight_factor = max(0.4, 1.0 - (orbe / 2.0))

            # DEBUG pour voir Lune–Saturne / Soleil–Uranus quand on sort par ce chemin
            if ("lune" in t and "saturne" in t) or ("soleil" in t and "uranus" in t):
                who = "Lune–Saturne" if ("lune" in t and "saturne" in t) else "Soleil–Uranus"
                print(f"DEBUG[HP pers+difficiles] {who} orbe={orbe} base={base_score:.1f} factor={tight_factor:.3f} score={base_score*tight_factor:.1f}  | pf='{pf}'")
        
            return base_score * tight_factor
        

    # PRIORITÉ TRÈS HAUTE : Luminaires (Soleil/Lune) avec planètes lourdes
    luminaires = ["soleil", "lune"]
    lourdes = ["saturne", "uranus", "neptune", "pluton"]

    planetes_dans_aspect = [pl for pl in luminaires + lourdes if pl in t]
    a_luminaire = any(pl in planetes_dans_aspect for pl in luminaires)
    a_lourde = any(pl in planetes_dans_aspect for pl in lourdes)

    if (a_luminaire and a_lourde and 
    any(asp in t for asp in ["carré", "carre", "opposition", "conjonction"])):

        orbe = _parse_orbe(t)
        if orbe <= 6:
            base_score = 520.0  # ↑ léger boost
            if "soleil" in t:
                base_score *= 1.1
            # bonus ciblés
            if ("lune" in t and "saturne" in t) or ("soleil" in t and "uranus" in t):
                base_score *= 1.08
            if "opposition" in t:
                base_score *= 1.15
            elif "carré" in t or "carre" in t:
                base_score *= 1.2
            elif "conjonction" in t:
                base_score *= 1.05

            tight_factor = max(0.5, 1.0 - (orbe / 3.5))

            # ⬇️ pénalité douce si conjonction dissociée (on regarde le texte)
            if "conjonction" in t and "dissocie" in _strip_accents(t).lower():
                base_score *= 0.85

            # DEBUG optionnel
            if ("lune" in t and "saturne" in t) or ("soleil" in t and "uranus" in t):
                who = "Lune–Saturne" if ("lune" in t and "saturne" in t) else "Soleil–Uranus"
                print(f"DEBUG[HP luminaires+lourdes] {who} orbe={orbe} base={base_score:.1f} "
                    f"factor={tight_factor:.3f} score={base_score*tight_factor:.1f} | pf='{pf}'")

            return base_score * tight_factor
        
    # PRIORITÉ ÉLEVÉE : Conjonctions planète ↔ angle (ordre libre, orbe tolérée jusqu’à 7°)
    m1 = regex.search(r"\b(ascendant|mc|milieu du ciel|descendant|fc|fond du ciel|maison\s*4|maison\s*iv)\b.*\bconjonction\b.*\b(soleil|lune|mercure|v[ée]nus|mars|jupiter|saturne|uranus|neptune|pluton)\b", t, regex.I)
    m2 = regex.search(r"\b(soleil|lune|mercure|v[ée]nus|mars|jupiter|saturne|uranus|neptune|pluton)\b.*\bconjonction\b.*\b(ascendant|mc|milieu du ciel|descendant|fc|fond du ciel|maison\s*4|maison\s*iv)\b", t, regex.I)
    if m1 or m2:
        if m1:
            angle_txt, pl_txt = m1.group(1), m1.group(2)
        else:
            pl_txt, angle_txt = m2.group(1), m2.group(2)

        ecart = _parse_orbe(t)
        base_score = 650.0  # plus haut que ta version actuelle

        # bonus selon l’angle
        if angle_txt == "ascendant":
            base_score *= 1.6
        elif angle_txt in ("mc", "milieu du ciel"):
            base_score *= 1.7
        elif angle_txt == "descendant":
            base_score *= 1.4
        elif angle_txt == "fc":
            base_score *= 1.4

        # + bonus lourdes : Saturne/Uranus/Neptune/Pluton
        if pl_txt in ("saturne","uranus","neptune","pluton"):
            base_score *= 1.4

        # tolérance d’orbe étendue à 7° pour les angles (afin de capter p.ex. Asc ⟂ Pluton 6.78°)
        tight_factor = max(0.25, 1.0 - (ecart / 7.0))
        return base_score * tight_factor
    
    # HAUTE PRIORITÉ : Maître d'Ascendant angulaire
    if "maitre d'ascendant" in t and "angulaire" in t:
        return 400.0
    
    # HAUTE PRIORITÉ : Oppositions et carrés serrés avec planètes lourdes
    if any(asp in t for asp in ["opposition", "carré", "carre"]):
        orbe = _parse_orbe(t)
        if orbe <= 2.0:  # Très serré
            # Chercher planètes lourdes
            heavies = ["saturne", "mars", "pluton", "uranus"]
            if any(heavy in t for heavy in heavies):
                return 350.0 * (1.0 - orbe/5.0)
    
    # CONTINUER AVEC L'ANCIEN CODE
    is_mc  = regex.search(r"\b(mc|milieu du ciel)\b", t_no_acc, regex.I) is not None
    is_fc  = regex.search(r"\b(fc|fond du ciel|maison\s*4|maison\s*iv)\b", t_no_acc, regex.I) is not None
    is_asc = regex.search(r"\bascendant\b", t_no_acc, regex.I) is not None
    is_desc= regex.search(r"\bdescendant\b", t_no_acc, regex.I) is not None

    # 🔁 ALIAS “maison angulaire (n)” → angle correspondant
    # 1 → AS, 4 → FC, 7 → DS, 10 → MC
    if not (is_asc or is_desc or is_mc or is_fc):
        m_ang = regex.search(r"maison\s+angulaire\s*\(\s*(\d{1,2})\s*\)", t_no_acc, regex.I)
        if m_ang:
            n = int(m_ang.group(1))
            if n == 1:  is_asc = True
            elif n == 4: is_fc  = True
            elif n == 7: is_desc= True
            elif n == 10:is_mc  = True

    if is_asc or is_mc or is_desc or is_fc:
        for pl in PLANET_WEIGHTS.keys():
            if pl.lower() in t_no_acc:
                angle = "Ascendant" if is_asc else "MC" if is_mc else "Descendant" if is_desc else "FC"
                ecart = _parse_orbe(t)

                # 🛑 Si la ligne contient “maison angulaire (…)", le chiffre entre () est un numéro de maison, pas une orbe
                if regex.search(r"maison\s+angulaire\s*\(\s*(1|4|7|10)\s*\)", t_no_acc, regex.I) and "orbe" not in t_no_acc:
                    ecart = 0.5  # petit défaut raisonnable

                return score_angle_conjunction({"planete": pl, "angle": angle, "ecart": ecart})

    # Aspects planétaires (votre code existant)

    aspect = "Conjonction" if "conjonction" in t_no_acc else \
            "Opposition" if "opposition" in t_no_acc else \
            "Carré" if ("carré" in t_no_acc or "carre" in t_no_acc) else \
            "Trigone" if "trigone" in t_no_acc else \
            "Sextile" if "sextile" in t_no_acc else "Autre"
    
        # repère les deux premières planètes mentionnées (utilise t_no_acc pour être robuste)
    found = [pl for pl in PLANET_WEIGHTS.keys() if pl.lower() in t_no_acc]
    p1, p2 = (found + ["",""])[:2]
    orbe = _parse_orbe(t)

    # Cas spécial "Autre"
    if aspect == "Autre":
        score_final = (_planet_weight(p1) + _planet_weight(p2)) * 40.0
        # (optionnel) debug:
        # if "lune" in t_no_acc and "saturne" in t_no_acc:
        #     print(f"DEBUG SCORE FINAL Lune-Saturne (Autre): {score_final}")
        return score_final  # on retourne ici pour le cas 'Autre'

    # Pour les aspects normaux
    score_final = score_aspect_dict({"p1": p1, "p2": p2, "aspect": aspect, "orbe": orbe})

    # ✅ has_angle élargi (utilisé pour la pénalité “lente+lente”)
    has_angle = regex.search(
        r"\b(ascendant|mc|milieu du ciel|descendant|fc|fond du ciel|fond-du-ciel|maison\s*4|maison\s*iv|maison\s+angulaire\s*\(\s*(?:1|4|7|10)\s*\))\b",
        t_no_acc, regex.I
    ) is not None

    # ⛔ Déclasser "lente + lente" (ex: Jupiter–Saturne) SAUF si angle impliqué
    if (p1 in SLOW_SET and p2 in SLOW_SET) and not has_angle:
        score_final *= 0.55  # pénalité douce

    # ⬇️ appliquer pénalité douce si conjonction dissociée (une seule fois, à la fin)
    if aspect == "Conjonction" and "dissocie" in _strip_accents(t).lower():
        score_final *= 0.85

    return score_final

def trier_points_forts(points_forts: List[str]) -> List[str]:
    return sorted(points_forts, key=score_point_fort_text, reverse=True)

# === Axes majeurs : payload propre (sans Markdown) ===

SECTION_ORDER = [
    "points_forts",
    "infos_complementaires",
    "dignites_chutes",
    "amas",
    "planetes_angulaires",
    "tensions_luminaires",
    "dominances",
    "axes_cardinaux",
]

def _listify_lines_no_md(x) -> List[str]:
    """Transforme un blob éventuel en liste propre, sans titres Markdown ni puces."""
    if not x:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    out = []
    for ln in str(x).replace("\r", "").split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("#"):
            continue           # on vire les titres style "### ..."
        if ln.startswith("- "):
            ln = ln[2:].strip()  # on enlève la puce si présente
        ln = ln.strip("- ").strip()
        if ln:
            out.append(ln)
    return out

def _dedupe_keep_order(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for it in seq:
        k = it.strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out

def _merge_lists_keep_all(*lists: List[str]) -> List[str]:
    """Fusionne plusieurs listes en conservant l'ordre, sans pertes."""
    seen, out = set(), []
    for L in lists:
        for it in (L or []):
            k = (it or "").strip()
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(k)
    return out

def extraire_axes_majeurs_payload(contexte: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Construit un dict {section: [items]} SANS markdown et SANS sections vides.
    À utiliser partout où tu veux un 'axes' propre (Bloc 3, etc.).
    """
    # ✅ CORRECTION : récupérer le markdown complet depuis placements_str
    placements_str = contexte.get("placements_str", "")
    pf_blob = ""
    
    if placements_str:
        # Extraire depuis "### Points forts" jusqu'à "### Spécificités" (ou fin)
        lines = placements_str.splitlines()
        in_points_section = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Début de la zone d'intérêt
            if line_stripped == "### Points forts":
                in_points_section = True
                pf_blob += line + "\n"
                continue
            
            # Fin de la zone d'intérêt
            if in_points_section and line_stripped.startswith("### ") and "points forts" not in line_stripped.lower() and "informations" not in line_stripped.lower():
                break
                
            # Ajouter la ligne si on est dans la zone
            if in_points_section:
                pf_blob += line + "\n"
    
    # Fallback sécurisé sur l'ancienne méthode si rien trouvé
    if not pf_blob.strip():
        pf_blob = _get_points_forts_str(contexte)
    
    print(f"=== DEBUG MARKDOWN COMPLET ===")
    print(f"Blob reçu ({len(pf_blob)} chars):")
    print(pf_blob[:800] if pf_blob else "VIDE")
    print("===============================")
    
    pts_forts = []
    infos_compl = []

    # On sépare les sections du blob "Points forts / Informations complémentaires"
    current = None
    for ln in (pf_blob or "").splitlines():
        l = (ln or "").strip()
        if not l:
            continue
        if l.startswith("### "):
            head = l[4:].strip().lower()
            print(f"Section détectée: '{l}' -> head='{head}'")
            if head.startswith("points forts"):
                current = "pf"
                print("  → Mode: points forts")
            elif "informations" in head and "compl" in head:
                current = "infos"
                print("  → Mode: infos complémentaires")
            else:
                current = None
                print("  → Mode: ignoré")
            continue
        if l.startswith("- "):
            l = l[2:].strip()
        if not l:
            continue
        if current == "pf":
            pts_forts.append(l)
            print(f"  PF ajouté: {l}")
        elif current == "infos":
            infos_compl.append(l)
            print(f"  INFO ajouté: {l}")

    print(f"Résultat: {len(pts_forts)} PF, {len(infos_compl)} infos")
    print("===============================")

    # autres sections éventuelles, si tu en as dans ton contexte
    dignites  = _listify_lines_no_md(contexte.get("dignites") or contexte.get("dignites_chutes"))
    # Amas : fusion de plusieurs origines si présentes
    amas = _merge_lists_keep_all(
        _listify_lines_no_md(contexte.get("amas")),
        _listify_lines_no_md((contexte.get("placements_fusion") or {}).get("amas")),
        _listify_lines_no_md((contexte.get("placements_occ") or {}).get("amas")),
    )
    angulaires = _listify_lines_no_md(contexte.get("planetes_angulaires"))
    tensions   = _listify_lines_no_md(contexte.get("tensions_luminaires"))
    dominances = _listify_lines_no_md(contexte.get("dominances"))
    axes_signs = _listify_lines_no_md(contexte.get("axes_cardinaux"))

    payload = {
        "points_forts":        _dedupe_keep_order(pts_forts),
        "infos_complementaires": _dedupe_keep_order(infos_compl),
        "dignites_chutes":     _dedupe_keep_order(dignites),
        "amas":                _dedupe_keep_order(amas),
        "planetes_angulaires": _dedupe_keep_order(angulaires),
        "tensions_luminaires": _dedupe_keep_order(tensions),
        "dominances":          _dedupe_keep_order(dominances),
        "axes_cardinaux":      _dedupe_keep_order(axes_signs),
    }

    # purge des sections vides + ordre figé
    payload = {k: v for k, v in payload.items() if v}
    payload = {k: payload[k] for k in SECTION_ORDER if k in payload}
    return payload

def axes_payload_items(payload: Dict[str, List[str]]) -> List[str]:
    """Aplatit le payload en une liste d’items (sans titres), pour le prompt LLM."""
    items = []
    for section in SECTION_ORDER:
        if section in payload:
            items.extend(payload[section])
    return items

def axes_payload_to_str(payload: Dict[str, List[str]]) -> str:
    """Option debug : une chaîne de puces (sans titres), lisible humainement."""
    return "\n".join(f"- {it}" for it in axes_payload_items(payload))

# -- PRIORITÉ pour le Bloc 3 -----------------------------------------------

def _calculate_priority_score(item: str) -> int:
    """
    Score de priorité générique : plus élevé = plus important pour le Bloc 3.
    Utilise _parse_orbe pour tolérer 'orbe 1,3' et 'écart 1.3'.
    Neutralise la pénalité 'lente+lente' si un angle est cité.
    """
    t = _strip_accents((item or "").lower())
    score = 0

    # Amas = concentration d'énergie majeure (priorité max)
    if "amas" in t:
        score += 30

    # Maisons angulaires = impact direct
    if "maison angulaire" in t:
        score += 25

    # Dignités problématiques/fortes
    if any(w in t for w in ["chute", "exil"]):
        score += 20
    if any(w in t for w in ["domicile", "exaltation"]):
        score += 18

    # Rétrogrades
    if "retrograde" in t or "rétrograde" in t:  # t est désaccentué, mais on garde les deux
        score += 15

    # Angles (MC/DS surtout)
    if ("mc" in t) or ("milieu du ciel" in t):
        score += 12
    if "descendant" in t:
        score += 10

    # Orbe serrée (via helper robuste)
    try:
        orbe = _parse_orbe(t)  # gère 'orbe', 'écart', '.' et ','
        if orbe <= 1.0:
            score += 15
        elif orbe <= 2.0:
            score += 10
        elif orbe <= 3.0:
            score += 5
    except Exception:
        pass

    # Saturne (hors Soleil/Lune) = structuration
    if "saturne" in t and not any(x in t for x in ["soleil", "lune"]):
        score += 8

    # Duo de lentes : pénalité douce, SAUF si angle cité
    has_angle = any(k in t for k in ["ascendant", "mc", "milieu du ciel", "descendant", "fc", "fond du ciel", "ic"])
    lentes = ["saturne", "uranus", "neptune", "pluton"]
    lentes_in = [p for p in lentes if p in t]
    if (len(lentes_in) >= 2) and not has_angle:
        score -= 5

    return score


def filtrer_items_pour_bloc3(items: list[str], max_items: int = 10) -> list[str]:
    """
    Filtrage générique pour Bloc 3 avec priorisation :
    - Retire Soleil, Lune, Ascendant, Maître d'Ascendant, conj. Asc/IC/FC
    - Garde MC, Descendant, Saturne (hors Soleil/Lune), amas, dignités, maisons angulaires
    - Trie par ordre d'importance pour l'identité
    - Coupe à max_items (par défaut 10)
    """
    out = []
    for s in items or []:
        t = _strip_accents((s or "").lower())

        # ✅ Toujours garder (whitelist)
        if t.startswith("🌟 amas personnel") or t.startswith("amas personnel") or ("amas" in t):
            out.append(s); continue
        if "maison angulaire" in t:
            out.append(s); continue
        if any(w in t for w in ["domicile", "exaltation", "chute", "exil"]):
            out.append(s); continue
        if "saturne" in t and not any(x in t for x in ["soleil", "lune"]):
            out.append(s); continue
        if ("mc" in t) or ("milieu du ciel" in t):
            out.append(s); continue
        if "descendant" in t:
            out.append(s); continue

        # ❌ Déjà traités (Blocs 1 & 2)
        if any(w in t for w in ["soleil", "lune", "ascendant"]):
            continue
        if "maitre d'ascendant" in t or "maître d'ascendant" in t:
            continue

        # ❌ Conjonctions spécifiques (déjà traitées) — on garde MC
        if "conjonction ascendant" in t:
            continue
        if ("conjonction fc" in t) or ("conjonction ic" in t) or ("fond du ciel" in t) or (" ic" in t) or (" fc" in t):
            continue

        # ✅ Le reste passe
        out.append(s)

    # 🎯 Tri par priorité + dédup + coupe
    scored = [(it, _calculate_priority_score(it)) for it in out]
    scored.sort(key=lambda x: x[1], reverse=True)
    prioritized = [it for it, _ in scored]
    prioritized = _dedupe_keep_order(prioritized)

    if max_items and len(prioritized) > max_items:
        prioritized = prioritized[:max_items]

    # Debug optionnel
    print("=== PRIORITÉS BLOC 3 ===")
    for it, sc in scored[:max_items]:
        print(f"{sc:2d} pts: {it}")
    print("========================")

    return prioritized