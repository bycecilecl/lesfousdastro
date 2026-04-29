# utils/karmique_score.py

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional

def _norm_aspect_name(x: str) -> str:
    if not x:
        return ""
    x = str(x).strip()
    # normalise sans accent
    if x.lower() == "carre":
        return "Carré"
    if x.lower() == "trigone":
        return "Trigone"
    if x.lower() == "sextile":
        return "Sextile"
    if x.lower() == "opposition":
        return "Opposition"
    if x.lower() == "conjonction":
        return "Conjonction"
    return x


def _delta_deg(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(float(x))
    except Exception:
        return None
    
PERSONAL = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}
CLASSICAL = PERSONAL | {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}
    
def _get_sign_stelliums(resultats: Dict[str, Any]) -> List[Dict[str, Any]]:
    buckets = {}

    for p, info in (resultats or {}).items():
        if p not in CLASSICAL:
            continue
        if not isinstance(info, dict):
            continue

        signe = info.get("signe")
        if not signe:
            continue

        buckets.setdefault(signe, []).append(p)

    out = []
    for signe, planets in buckets.items():
        total = len(planets)
        personal_count = len([p for p in planets if p in PERSONAL])

        # ✅ règle STELLIUM
        if total >= 4 and personal_count >= 3:
            out.append({
                "signe": signe,
                "planetes": sorted(planets),
                "total": total,
                "personal_count": personal_count
            })

    return out

def _sign_ruler(sign: str) -> Optional[str]:
    rulers = {
        "Bélier": "Mars",
        "Taureau": "Vénus",
        "Gémeaux": "Mercure",
        "Cancer": "Lune",
        "Lion": "Soleil",
        "Vierge": "Mercure",
        "Balance": "Vénus",
        "Scorpion": "Mars",
        "Sagittaire": "Jupiter",
        "Capricorne": "Saturne",
        "Verseau": "Saturne",
        "Poissons": "Jupiter",
    }
    return rulers.get(sign)

def _sign_rulers(sign: str) -> List[str]:
    """
    Retourne la liste des maîtres d’un signe :
    - 1 seul pour la majorité
    - 2 pour Scorpion, Verseau, Poissons
    """
    rulers = {
        "Bélier": ["Mars"],
        "Taureau": ["Vénus"],
        "Gémeaux": ["Mercure"],
        "Cancer": ["Lune"],
        "Lion": ["Soleil"],
        "Vierge": ["Mercure"],
        "Balance": ["Vénus"],
        "Scorpion": ["Mars", "Pluton"],
        "Sagittaire": ["Jupiter"],
        "Capricorne": ["Saturne"],
        "Verseau": ["Saturne", "Uranus"],
        "Poissons": ["Jupiter", "Neptune"],
    }
    return rulers.get(sign, [])


def _normalize_aspects(aspects: Any) -> List[Dict[str, Any]]:
    """Normalise la sortie de detecter_aspects() en liste de dicts."""
    if isinstance(aspects, list):
        return [a for a in aspects if isinstance(a, dict)]
    if isinstance(aspects, dict):
        for key in ("aspects", "liste", "data"):
            if key in aspects and isinstance(aspects[key], list):
                return [a for a in aspects[key] if isinstance(a, dict)]
    return []


def _aspect_parts(a: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[float]]:
    """Extrait (p1, p2, type_aspect, orb) depuis ton format réel."""
    p1 = a.get("planete1")
    p2 = a.get("planete2")
    typ = _norm_aspect_name(a.get("aspect"))
    orb = a.get("orbe")

    orb_f = _safe_float(orb)
    if isinstance(typ, str):
        typ = typ.strip()
    if isinstance(p1, str):
        p1 = p1.strip()
    if isinstance(p2, str):
        p2 = p2.strip()

    return p1, p2, typ, orb_f

def _aspects_for_target(aspects: List[Dict[str, Any]], target: str) -> List[Dict[str, Any]]:
    """Retourne les aspects majeurs impliquant `target` (Conj/Carré/Oppo/Trigone/Sextile)."""
    allowed = {"Conjonction", "Carré", "Opposition", "Trigone", "Sextile"}
    out = []
    for a in aspects:
        p1, p2, typ, orb = _aspect_parts(a)
        if not p1 or not p2 or not typ:
            continue
        #typ = _norm_aspect_name(typ)
        if typ not in allowed:
            continue
        if p1 == target or p2 == target:
            other = p2 if p1 == target else p1
            out.append({
                "with": other,
                "type": typ,
                "orb": orb
            })
    # tri par orbe croissant (plus serré = plus important)
    out.sort(key=lambda x: (x["orb"] is None, x["orb"] if x["orb"] is not None else 999))
    return out

def calculer_poids_karmique(theme: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    """
    Calcule le score 'Poids Karmique' en points entiers (barème x2).
    Retourne un dict IA/UI-ready.
    """

    # Barème entier (x2)
    W = {
        "retro_personal": 4,   # Mercure/Vénus/Mars
        "retro_social": 2,     # Jupiter/Saturne

        "house_12": 4,
        "house_8": 3,
        "house_4": 2,
        "stellium_bonus": 4,   # 3+ planètes dans IV/VIII/XII (une fois par maison)

        "node_aspect_personal": 4,  # aspects durs à NN/NS avec planète perso/luminaire
        "node_aspect_heavy": 3,     # aspects durs à NN/NS avec Saturne/Pluton
        "nn_ruler_in_karmic_house": 4,

        "intercept_axis": 6,
        "intercept_planet": 2,

        "satplu_on_angle": 5,
        "sat_plu_hard": 4,

        "anaretic_29": 4,

        # ✅ NOUVEAU : amas en signe
        "stellium_sign_standard": 2,
        "stellium_sign_water": 4,
        "stellium_sign_south_node": 6,


        # --- LUNE karmique (V1) ---
        "moon_water": 2,            # Cancer/Poissons
        "moon_fall_exil": 3,        # Scorpion (chute) / Capricorne (exil)
        "moon_house_4": 2,
        "moon_house_8": 3,
        "moon_house_12": 3,
        "moon_hard": 2,             # carré/opposition (≤5°) avec planète non lourde
        "moon_satplu_hard": 3,      # carré/opposition (≤5°) avec Saturne/Pluton
        "moon_chiron_conj": 2,      # conjonction (≤5°) avec Chiron
        "moon_intercepted": 4,      # Lune interceptée (ou signe intercepté)
    }

    personal = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}
    heavy = {"Saturne", "Pluton"}
    karmic_houses = {4, 8, 12}

    resultats = theme.get("planetes", {}) or {}
    interceptions = theme.get("interceptions", {}) or {}
    aspects = _normalize_aspects(theme.get("aspects"))

    planetes_deg = theme.get("planetes_deg", {}) or {}
    angles_deg = theme.get("angles_deg", {}) or {}

    breakdown = {
        "retrogrades": 0,
        "houses_karmic": 0,
        "nodes": 0,
        "interceptions": 0,
        "saturn_pluto": 0,
        "anaretic_29": 0,
        "amas_signes": 0,
        "moon_karmic": 0,
    }

    total = 0
    top_sources = []

    # A) Rétrogrades
    for p in ("Mercure", "Vénus", "Mars"):
        info = resultats.get(p, {})
        if info.get("retrograde") is True:
            breakdown["retrogrades"] += W["retro_personal"]

    for p in ("Jupiter", "Saturne"):
        info = resultats.get(p, {})
        if info.get("retrograde") is True:
            breakdown["retrogrades"] += W["retro_social"]

    # B) Maisons karmiques IV/VIII/XII + amas
    planets_by_house = {4: [], 8: [], 12: []}
    for p, info in resultats.items():
        if p == "Ascendant":
            continue
        maison = _safe_int(info.get("maison") if isinstance(info, dict) else None)
        if maison in karmic_houses:
            planets_by_house[maison].append(p)
            if maison == 12:
                breakdown["houses_karmic"] += W["house_12"]
            elif maison == 8:
                breakdown["houses_karmic"] += W["house_8"]
            elif maison == 4:
                breakdown["houses_karmic"] += W["house_4"]

    for h in (4, 8, 12):
        if len(planets_by_house[h]) >= 3:
            breakdown["houses_karmic"] += W["stellium_bonus"]

    # C) Nœuds (Rahu/Ketu) - éviter double comptage Rahu+Ketu pour la même planète
    nn = resultats.get("Rahu") or {}
    nn_sign = nn.get("signe")
    nn_ruler = _sign_ruler(nn_sign) if isinstance(nn_sign, str) else None

    # --- Maîtres des Nœuds Lunaires ---
    ns = resultats.get("Ketu") or {}
    ns_sign = ns.get("signe")
    ns_ruler = _sign_ruler(ns_sign) if isinstance(ns_sign, str) else None

    # --- Doubles maîtres des Nœuds (pour l'analyse, pas le score) ---
    nn_rulers = _sign_rulers(nn_sign) if isinstance(nn_sign, str) else []
    ns_rulers = _sign_rulers(ns_sign) if isinstance(ns_sign, str) else []

    # ✅ détails par maître (maison + aspects)
    nn_rulers_details = []
    for r in nn_rulers:
        house = _safe_int((resultats.get(r) or {}).get("maison")) if r in resultats else None
        aspects_r = _aspects_for_target(aspects, r)[:10] if r else []
        nn_rulers_details.append({
            "name": r,
            "house": house,
            "aspects": aspects_r
        })

    ns_rulers_details = []
    for r in ns_rulers:
        house = _safe_int((resultats.get(r) or {}).get("maison")) if r in resultats else None
        aspects_r = _aspects_for_target(aspects, r)[:10] if r else []
        ns_rulers_details.append({
            "name": r,
            "house": house,
            "aspects": aspects_r
        })

    nn_ruler_aspects = _aspects_for_target(aspects, nn_ruler) if nn_ruler else []
    ns_ruler_aspects = _aspects_for_target(aspects, ns_ruler) if ns_ruler else []


    nn_ruler_house = None
    if nn_ruler and nn_ruler in resultats:
        nn_ruler_house = _safe_int(resultats[nn_ruler].get("maison"))

    ns_ruler_house = None
    if ns_ruler and ns_ruler in resultats:
        ns_ruler_house = _safe_int(resultats[ns_ruler].get("maison"))

    if nn_ruler and nn_ruler in resultats:
        ruler_house = _safe_int(resultats[nn_ruler].get("maison"))
        if ruler_house in karmic_houses:
            breakdown["nodes"] += W["nn_ruler_in_karmic_house"]

    hard_aspects = {"Conjonction", "Carré", "Opposition"}

    counted_planets = set()  # ← clé anti-double comptage

    for a in aspects:
        p1, p2, typ, orb = _aspect_parts(a)
        if not p1 or not p2 or not typ:
            continue
        if typ not in hard_aspects:
            continue
        if p1 not in ("Rahu", "Ketu") and p2 not in ("Rahu", "Ketu"):
            continue

        other = p2 if p1 in ("Rahu", "Ketu") else p1

        # si on a déjà compté cette planète via l’autre nœud, on saute
        if other in counted_planets:
            continue

        if other in personal:
            breakdown["nodes"] += W["node_aspect_personal"]
            counted_planets.add(other)
        elif other in heavy:
            breakdown["nodes"] += W["node_aspect_heavy"]
            counted_planets.add(other)

    # D) Interceptions
    axes = interceptions.get("axes_interceptes") or []
    if isinstance(axes, list):
        breakdown["interceptions"] += len(axes) * W["intercept_axis"]

    signes_interceptes = interceptions.get("signes_interceptes") or []
    signes_set = set(signes_interceptes) if isinstance(signes_interceptes, list) else set()

    if signes_set:
        for p, info in resultats.items():
            if p == "Ascendant" or not isinstance(info, dict):
                continue
            if info.get("signe") in signes_set:
                breakdown["interceptions"] += W["intercept_planet"]

    intercepted_rulers = []
    intercepted_rulers_aspects = {}

    if signes_set:
        for s in sorted(signes_set):
            for r in _sign_rulers(s):  # <-- prend 1 ou 2 maîtres selon le signe
                if r and r not in intercepted_rulers:
                    intercepted_rulers.append(r)

        for r in intercepted_rulers:
            intercepted_rulers_aspects[r] = _aspects_for_target(aspects, r)[:10]

    # E) Saturne/Pluton : conjonction angles + aspect dur
    satplu_on_angles = []         # détails conjonctions aux angles
    satplu_hard_aspect = None     # détails aspect dur Saturne/Pluton

    # helper pour lire signe/maison depuis resultats
    def _planet_sig_house(name: str):
        info = resultats.get(name)
        if not isinstance(info, dict):
            return None, None, None
        sign = info.get("signe")
        house = _safe_int(info.get("maison"))
        deg_in_sign = _safe_float(info.get("degre_dans_signe"))
        return sign, house, (round(deg_in_sign, 2) if isinstance(deg_in_sign, (int, float)) else deg_in_sign)

    # 1) conjonctions aux angles (orbe <= 1°)
    for p in ("Saturne", "Pluton"):
        pd = _safe_float(planetes_deg.get(p))
        if pd is None:
            continue

        p_sign, p_house, p_deg_in_sign = _planet_sig_house(p)

        for ang_name, ang_deg in (angles_deg or {}).items():
            ad = _safe_float(ang_deg)
            if ad is None:
                continue

            orb = _delta_deg(pd, ad)

            ANGLE_ORB = 5.0
            if orb <= ANGLE_ORB:
                breakdown["saturn_pluto"] += W["satplu_on_angle"]
                satplu_on_angles.append({
                    "planet": p,
                    "planet_sign": p_sign,
                    "planet_house": p_house,
                    "planet_deg_in_sign": p_deg_in_sign,
                    "angle": ang_name,
                    "orb": round(orb, 2),
                })
                break  # on ne compte qu’un angle max par planète

    # 2) aspect dur Saturne–Pluton (Conj/Carré/Oppo)
    # (hard_aspects est déjà défini plus haut chez toi, donc pas besoin de le redéclarer)
    for a in aspects:
        p1, p2, typ, orb = _aspect_parts(a)
        if not p1 or not p2 or not typ:
            continue

        if {p1, p2} == {"Saturne", "Pluton"} and typ in hard_aspects:
            breakdown["saturn_pluto"] += W["sat_plu_hard"]

            sat_sign, sat_house, sat_deg = _planet_sig_house("Saturne")
            plu_sign, plu_house, plu_deg = _planet_sig_house("Pluton")

            satplu_hard_aspect = {
                "type": typ,
                "orb": round(orb, 2) if isinstance(orb, (int, float)) else orb,
                "saturne": {
                    "sign": sat_sign,
                    "house": sat_house,
                    "deg_in_sign": sat_deg,
                },
                "pluton": {
                    "sign": plu_sign,
                    "house": plu_house,
                    "deg_in_sign": plu_deg,
                },
            }
            break

    # F) 29° anarétique
    for p, info in resultats.items():
        if p == "Ascendant" or not isinstance(info, dict):
            continue
        deg_in_sign = _safe_float(info.get("degre_dans_signe"))
        if deg_in_sign is not None and deg_in_sign >= 29.0:
            breakdown["anaretic_29"] += W["anaretic_29"]

    # G) Amas en signe (3+ planètes)
    amas_signes_data = []
    stelliums_signes = _get_sign_stelliums(resultats)
    signes_eau = {"Cancer", "Scorpion", "Poissons"}

    for st in stelliums_signes:
        signe = st["signe"]
        pls = st["planetes"]

        pts = 0  # ✅ par défaut: dominance, pas karma

        if signe in signes_eau:
            pts = W["stellium_sign_water"]          # ex: 4
        if isinstance(ns_sign, str) and signe == ns_sign:
            pts = W["stellium_sign_south_node"]     # ex: 6 (écrase le reste)

        breakdown["amas_signes"] += pts
        amas_signes_data.append({
            "signe": signe,
            "planetes": pls,
            "score_impact": pts,
            "is_water": signe in signes_eau,
            "is_south_node_sign": bool(isinstance(ns_sign, str) and signe == ns_sign),
        })


    # ============================================================
    # LUNE karmique (V1)
    # ============================================================
    moon_sign = None
    moon_house = None
    moon_intercepted = False
    moon_hard_hits = []

    moon = (resultats or {}).get("Lune")
    if isinstance(moon, dict):
        moon_sign = moon.get("signe")
        if isinstance(moon_sign, str):
            moon_sign = moon_sign.strip()

        moon_house = _safe_int(moon.get("maison"))

        # A) signe
        if moon_sign in ("Scorpion", "Capricorne"):
            breakdown["moon_karmic"] += W["moon_fall_exil"]
        elif moon_sign in ("Cancer", "Poissons"):
            breakdown["moon_karmic"] += W["moon_water"]

        # B) maison karmique
        if moon_house == 4:
            breakdown["moon_karmic"] += W["moon_house_4"]
        elif moon_house == 8:
            breakdown["moon_karmic"] += W["moon_house_8"]
        elif moon_house == 12:
            breakdown["moon_karmic"] += W["moon_house_12"]

        # C) aspects durs (≤5°) : carré/opposition à Lune
        for a in (aspects or []):
            p1, p2, typ, orb = _aspect_parts(a)
            if typ not in ("Carré", "Opposition"):
                continue
            if p1 != "Lune" and p2 != "Lune":
                continue

            other = p2 if p1 == "Lune" else p1
            orbf = _safe_float(orb)
            if orbf is None or orbf > 5.0:
                continue

            pts = W["moon_satplu_hard"] if other in ("Saturne", "Pluton") else W["moon_hard"]
            breakdown["moon_karmic"] += pts

            moon_hard_hits.append({
                "type": typ,
                "with": other,
                "orb": round(orbf, 2),
            })

        # Bonus : conjonction Chiron (≤5°)
        for a in (aspects or []):
            p1, p2, typ, orb = _aspect_parts(a)
            if typ != "Conjonction":
                continue
            if {p1, p2} != {"Lune", "Chiron"}:
                continue

            orbf = _safe_float(orb)
            if orbf is None or orbf > 5.0:
                continue

            breakdown["moon_karmic"] += W["moon_chiron_conj"]

            moon_hard_hits.append({
                "type": "Conjonction",
                "with": "Chiron",
                "orb": round(orbf, 2),
            })

        # D) interception
        inter = interceptions or {}
        signes_interceptes = [str(s).strip() for s in (inter.get("signes_interceptes") or []) if s]
        planetes_interceptees = [str(p).strip() for p in (
            inter.get("planetes_interceptees")
            or inter.get("planetes_interceptées")
            or []
        ) if p]

        if ("Lune" in planetes_interceptees) or (moon_sign and moon_sign in signes_interceptes):
            moon_intercepted = True
            breakdown["moon_karmic"] += W["moon_intercepted"]

    total = sum(breakdown.values())
    top_sources = sorted(
        [k for k, v in breakdown.items() if v > 0],
        key=lambda k: breakdown[k],
        reverse=True
    )[:3]

    if total <= 12:
        level_code, label = "LIGHT", "Voyageur Léger"
    elif total <= 26:
        level_code, label = "MEDIUM", "Bagage Cabine"
    elif total <= 40:
        level_code, label = "HEAVY", "Valise en Soute"
    else:
        level_code, label = "EXTREME", "Expédition Polaire"

    out = {
        "total": total,
        "level_code": level_code,
        "label": label,
        "breakdown": breakdown,
        "top_sources": top_sources,
        "meta": {
            "nn_sign": nn_sign,
            "ns_sign": ns_sign,
            "nn_ruler": nn_ruler,
            "nn_ruler_house": nn_ruler_house,
            "ns_ruler": ns_ruler,
            "ns_ruler_house": ns_ruler_house,
            "nn_ruler_aspects": nn_ruler_aspects[:10],
            "ns_ruler_aspects": ns_ruler_aspects[:10],
            "nn_rulers": nn_rulers,
            "ns_rulers": ns_rulers,
            "nn_rulers_details": nn_rulers_details,
            "ns_rulers_details": ns_rulers_details,
            "intercepted_signs": sorted(list(signes_set)),
            "intercepted_rulers": intercepted_rulers,
            "intercepted_rulers_aspects": intercepted_rulers_aspects,
            "amas_signes": amas_signes_data,
            "satplu_on_angles": satplu_on_angles,
            "satplu_hard_aspect": satplu_hard_aspect,
            "moon_sign": moon_sign,
            "moon_house": moon_house,
            "moon_intercepted": moon_intercepted,
            "moon_hard_hits": moon_hard_hits[:10],
        }
    }

    if debug:
        out["debug"] = {
            "aspects_sample": aspects[:2],
            "interceptions": interceptions,
            "node_aspects_ignored": [
                (a.get("planete1"), a.get("planete2"),
                _norm_aspect_name(a.get("aspect")), a.get("orbe"))
                for a in aspects
                if isinstance(a, dict)
                and _norm_aspect_name(a.get("aspect")) in {"Conjonction", "Carré", "Opposition"}
                and (a.get("planete1") in ("Rahu", "Ketu") or a.get("planete2") in ("Rahu", "Ketu"))
                and (
                    (
                        (a.get("planete1") not in personal | heavy)
                        and (a.get("planete2") not in personal | heavy)
                    )
                )
            ][:10]
        }

    if debug:
        print("DEBUG NODES:", {
            "nn_sign": nn_sign,
            "nn_ruler": nn_ruler,
            "nn_ruler_house": _safe_int(resultats.get(nn_ruler, {}).get("maison")) if nn_ruler else None,
            "node_aspects_hard": [
                (a.get("planete1"), a.get("planete2"), _norm_aspect_name(a.get("aspect")), a.get("orbe"))
                for a in aspects
                if isinstance(a, dict)
                and _norm_aspect_name(a.get("aspect")) in {"Conjonction", "Carré", "Opposition"}
                and (a.get("planete1") in ("Rahu","Ketu") or a.get("planete2") in ("Rahu","Ketu"))
            ][:10]
        })

        print("DEBUG RULERS ASPECTS:", {
            "nn_ruler": nn_ruler,
            "nn_ruler_aspects": nn_ruler_aspects[:5],
            "ns_ruler": ns_ruler,
            "ns_ruler_aspects": ns_ruler_aspects[:5],
        })

        print("DEBUG INTERCEPTIONS RULERS:", {
            "signs": sorted(list(signes_set)),
            "rulers": intercepted_rulers,
            "rulers_aspects_sample": {k: v[:3] for k, v in intercepted_rulers_aspects.items()}
        })

    return out