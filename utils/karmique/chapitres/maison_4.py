from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging

logger = logging.getLogger(__name__)

# -------------------------
# Normalisation simple
# -------------------------
def _slug(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    s = s.replace("à", "a").replace("â", "a")
    s = s.replace("î", "i").replace("ï", "i")
    s = s.replace("ô", "o")
    s = s.replace("ù", "u").replace("û", "u").replace("ü", "u")
    s = s.replace("ç", "c")
    s = s.replace("œ", "oe")
    s = s.replace("’", "'")
    s = s.replace(" ", "_")
    return s


def _bdd(astre: str, donnee: str, valeur: Any) -> str:
    if valeur is None:
        return ""
    txt = get_karmique_interp(astre, donnee, str(valeur))
    return txt.strip() if isinstance(txt, str) and txt.strip() else ""


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


# -------------------------
# Rulers (modernes + tradi)
# -------------------------
SIGN_RULERS: Dict[str, List[str]] = {
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


# -------------------------
# Dignités
# -------------------------
DOMICILE = {
    "Mars": ["belier", "scorpion"],
    "Vénus": ["taureau", "balance"],
    "Mercure": ["gemeaux", "vierge"],
    "Lune": ["cancer"],
    "Soleil": ["lion"],
    "Jupiter": ["sagittaire", "poissons"],
    "Saturne": ["capricorne", "verseau"],
    "Uranus": ["verseau"],
    "Neptune": ["poissons"],
    "Pluton": ["scorpion"],
}

EXALTATION = {
    "Soleil": ["belier"],
    "Lune": ["taureau"],
    "Mercure": ["vierge"],
    "Vénus": ["poissons"],
    "Mars": ["capricorne"],
    "Jupiter": ["cancer"],
    "Saturne": ["balance"],
}

OPPOSITE_SIGNS = {
    "belier": "balance",
    "taureau": "scorpion",
    "gemeaux": "sagittaire",
    "cancer": "capricorne",
    "lion": "verseau",
    "vierge": "poissons",
    "balance": "belier",
    "scorpion": "taureau",
    "sagittaire": "gemeaux",
    "capricorne": "cancer",
    "verseau": "lion",
    "poissons": "vierge",
}

PLANET_ALIASES = {
    "Venus": "Vénus",
    "Juno": "Junon",
    "North Node": "Rahu",
    "South Node": "Ketu",
    "Noeud Nord": "Nœud Nord",
    "Noeud Sud": "Nœud Sud",
}


def _canon_planet(name: Any) -> str:
    if not name:
        return ""
    n = str(name).strip()
    return PLANET_ALIASES.get(n, n)


def _dignity(planet: str, sign: str) -> str:
    ps = _slug(sign)
    if planet in DOMICILE and ps in DOMICILE[planet]:
        return "domicile"
    if planet in EXALTATION and ps in EXALTATION[planet]:
        return "exaltation"

    if planet in DOMICILE:
        for d in DOMICILE[planet]:
            if OPPOSITE_SIGNS.get(d) == ps:
                return "exil"

    if planet in EXALTATION:
        for ex in EXALTATION[planet]:
            if OPPOSITE_SIGNS.get(ex) == ps:
                return "chute"

    return "neutre"


# -------------------------
# Aspects dissociés
# -------------------------
SIGN_ORDER = [
    "belier", "taureau", "gemeaux", "cancer", "lion", "vierge",
    "balance", "scorpion", "sagittaire", "capricorne", "verseau", "poissons"
]


def _sign_distance(sign1: str, sign2: str) -> int:
    s1 = _slug(sign1)
    s2 = _slug(sign2)
    if s1 not in SIGN_ORDER or s2 not in SIGN_ORDER:
        return -1
    i1 = SIGN_ORDER.index(s1)
    i2 = SIGN_ORDER.index(s2)
    diff = abs(i1 - i2)
    return min(diff, 12 - diff)


def _is_dissociated_aspect(sign1: Any, sign2: Any, aspect_type: str) -> bool:
    if not sign1 or not sign2:
        return False

    EXPECTED_DISTANCE = {
        "conjonction": 0,
        "conjunction": 0,
        "sextile": 2,
        "carre": 3,
        "square": 3,
        "trigone": 4,
        "trine": 4,
        "opposition": 6,
        "opp": 6,
    }

    t = str(aspect_type).strip().lower()
    expected = EXPECTED_DISTANCE.get(t)
    if expected is None:
        return False

    dist = _sign_distance(sign1, sign2)
    if dist < 0:
        return False

    return dist != expected


# -------------------------
# Helpers thème
# -------------------------
def _get_house_signs(theme: Dict[str, Any], house: int = 4) -> List[str]:
    out: List[str] = []

    houses = theme.get("maisons") or theme.get("houses") or {}

    if isinstance(houses, dict):
        possible_keys = (
            f"Maison {house}",
            f"Maison_{house}",
            f"maison_{house}",
            str(house),
            house,
        )

        for key in possible_keys:
            item = houses.get(key)

            if not isinstance(item, dict):
                continue

            s = item.get("signe") or item.get("sign")

            if s and str(s) not in out:
                out.append(str(s))

            break

    elif isinstance(houses, list):
        for item in houses:
            if not isinstance(item, dict):
                continue
            num = item.get("house") or item.get("maison") or item.get("numero") or item.get("num")
            if num == house:
                s = item.get("signe") or item.get("sign")
                if s and str(s) not in out:
                    out.append(str(s))

    inter = theme.get("interceptions") or {}
    maisons_interceptees = (
        inter.get("maisons_interceptees")
        or inter.get("maisons_interceptées")
        or {}
    )

    if isinstance(maisons_interceptees, dict):
        target = f"Maison {house}"
        for signe, maison_label in maisons_interceptees.items():
            if str(maison_label).strip() == target and str(signe) not in out:
                out.append(str(signe))

    if not out:
        houses_type = type(houses).__name__
        houses_keys = list(houses.keys()) if isinstance(houses, dict) else "non-dict"

        logger.warning(
            "Aucun signe trouvé pour Maison %s | type maisons=%s | clés disponibles=%s",
            house,
            houses_type,
            houses_keys,
        )

    return out


def _get_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    for k in ("aspects", "aspects_majeurs", "aspects_significatifs", "liste_aspects"):
        v = theme.get(k)
        if isinstance(v, list):
            return [a for a in v if isinstance(a, dict)]
    return []


def _planet_pos(theme: Dict[str, Any], planet: str) -> Dict[str, Any]:
    planets = theme.get("planetes") or {}
    if not isinstance(planets, dict):
        return {}

    p = planets.get(planet)
    if isinstance(p, dict):
        return p

    aliases = {
        "Venus": "Vénus",
        "Vénus": "Venus",
    }
    alt = aliases.get(planet)
    if alt:
        p = planets.get(alt)
        if isinstance(p, dict):
            return p

    return {}


def _extract_aspects_for_planet(
    aspects: List[Dict[str, Any]],
    planet: str
) -> List[Dict[str, Any]]:
    out = []
    for a in aspects:
        p1 = a.get("p1") or a.get("planet1") or a.get("A") or a.get("astre1") or a.get("planete1")
        p2 = a.get("p2") or a.get("planet2") or a.get("B") or a.get("astre2") or a.get("planete2")
        if p1 == planet or p2 == planet:
            out.append(a)
    return out


def _aspect_type(a: Dict[str, Any]) -> str:
    t = a.get("type") or a.get("aspect") or a.get("name")
    return str(t).strip().lower() if t else ""


def _other_planet(a: Dict[str, Any], planet: str) -> str:
    p1 = a.get("p1") or a.get("planet1") or a.get("A") or a.get("astre1") or a.get("planete1")
    p2 = a.get("p2") or a.get("planet2") or a.get("B") or a.get("astre2") or a.get("planete2")
    if p1 == planet:
        return str(p2) if p2 else ""
    if p2 == planet:
        return str(p1) if p1 else ""
    return ""


# -------------------------
# Lookup BDD aspects
# -------------------------
def _bdd_master_aspect(aspect: str, other_planet: str) -> str:
    asp = _slug(aspect)
    oth = _slug(other_planet)

    candidates = [
        (asp, oth),
        ("aspect", f"{asp}_{oth}"),
        ("aspect", f"{oth}_{asp}"),
        ("aspect", f"{asp}-{oth}"),
        ("aspect", f"{asp} {oth}"),
    ]

    for donnee, valeur in candidates:
        txt = _bdd("maitre_maison_4", donnee, valeur)
        if txt:
            logger.debug(
                "BDD aspect trouvé | donnee=%s | valeur=%s",
                donnee,
                valeur,
            )
            return txt

    logger.debug(
        "Aucun texte BDD trouvé pour aspect Maison 4 | aspect=%s | planète=%s",
        aspect,
        other_planet,
    )

    return ""


# -------------------------
# Figures / mémoires
# -------------------------
FIGURES_KARMIQUES = {
    "Soleil": "père",
    "Lune": "mère / matrice familiale / climat émotionnel du foyer",
    "Saturne": "père éducateur",
    "Mercure": "amis / enfants / fratrie / jumeau / jumelle",
    "Vénus": "amante / petite amie / amie / amour / soeur",
    "Mars": "amant / petit ami / ami / frère",
    "Jupiter": "guide / mentor",
}

MEMOIRES_LIGNEE = {
    "Uranus": "blessure de rejet",
    "Neptune": "blessure d'abandon / flou transgénérationnel",
    "Pluton": "violence / méfiance / sentiment de danger / manipulation",
}


# -------------------------
# MAIN : block Maison 4
# -------------------------
def build_block_maison_4(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
    debug_mode: bool = False,
) -> Dict[str, Any]:
    signs = _get_house_signs(theme, house=4)
    logger.debug(f"Maison 4 signs détectés : {signs}")

    house_10_signs = _get_house_signs(theme, house=10)
    logger.debug(f"Maison 10 signs détectés : {house_10_signs}")

    signs_slug = [_slug(s) for s in signs if s]
    house_10_slug = [_slug(s) for s in house_10_signs if s]

    intro = _bdd("maison_4", "intro", "base")

    sign_texts = []
    for s in signs_slug:
        t = _bdd("maison_4", "signe", s)
        if t:
            sign_texts.append(t)

    rulers: List[str] = []
    for s in signs_slug:
        rulers += SIGN_RULERS.get(s, [])

    rulers = list(dict.fromkeys(rulers))
    rulers_10: List[str] = []

    for s in house_10_slug:
        rulers_10 += SIGN_RULERS.get(s, [])

    rulers_10 = list(dict.fromkeys(rulers_10))
    rulers_10_details: List[str] = []

    for r10 in rulers_10:
        pos10 = _planet_pos(theme, r10)
        r10_sign = pos10.get("signe") or pos10.get("sign")
        r10_house = pos10.get("maison") or pos10.get("house")

        details = f"{r10}"

        if r10_sign:
            details += f" en {r10_sign}"

        if r10_house:
            details += f" Maison {r10_house}"

        rulers_10_details.append(details)

    aspects = _get_aspects(theme)

    rulers_details: List[Dict[str, Any]] = []
    rulers_aspects_lines: List[str] = []

    for r in rulers:
        pos = _planet_pos(theme, r)
        r_sign = pos.get("signe") or pos.get("sign")
        r_house = pos.get("maison") or pos.get("house")
        r_dign = _dignity(r, r_sign) if r_sign else "neutre"

        rasps = _extract_aspects_for_planet(aspects, r)

        filtered_rasps: List[Dict[str, Any]] = []
        for a in rasps:
            t = _aspect_type(a)
            oth = _other_planet(a, r)
            if not oth:
                continue

            other_pos = _planet_pos(theme, oth)
            other_sign = other_pos.get("signe") or other_pos.get("sign")

            if r_sign and other_sign and _is_dissociated_aspect(r_sign, other_sign, t):
                continue

            filtered_rasps.append(a)

        rasps = filtered_rasps

        HARD_ASPECTS = {"carre", "square", "opposition", "opp"}
        NODE_BODIES = {"Rahu", "Ketu", "Nœud Nord", "Nœud Sud"}

        hard = 0
        node_hard = 0

        for a in rasps:
            t = _aspect_type(a)
            oth = _other_planet(a, r)

            if t not in HARD_ASPECTS:
                continue

            if oth in NODE_BODIES:
                node_hard += 1
            else:
                hard += 1

        if r_dign in ("exil", "chute") or hard >= 2:
            state = "difficile"
        elif r_dign in ("domicile", "exaltation") and hard == 0:
            state = "bon"
        else:
            state = "neutre"

        state_reasons = []
        if r_dign in ("exil", "chute"):
            state_reasons.append(f"dignité faible ({r_dign})")
        if hard >= 2:
            state_reasons.append(f"{hard} aspects durs")
        if node_hard:
            state_reasons.append(f"{node_hard} aspect(s) dur(s) aux Nœuds lunaires")
        if not state_reasons:
            if state == "bon":
                state_reasons.append("bonne tenue astrologique")
            else:
                state_reasons.append("configuration intermédiaire")
        

        rulers_details.append({
            "planet": r,
            "sign": r_sign,
            "house": r_house,
            "dignity": r_dign,
            "hard_aspects_count": hard,
            "node_hard_aspects_count": node_hard,
            "state": state,
            "state_reasons": state_reasons,
        })

        for a in rasps:
            t = _aspect_type(a)
            oth = _other_planet(a, r)
            if not t or not oth:
                continue

            if t not in (
                "conjonction", "conjunction",
                "carre", "square",
                "opposition", "opp",
                "trigone", "trine",
                "sextile",
            ):
                continue

            asp_fr = {
                "conjunction": "conjonction",
                "square": "carre",
                "opp": "opposition",
                "trine": "trigone",
            }.get(t, t)

            txt = _bdd_master_aspect(asp_fr, oth)
            if txt:
                rulers_aspects_lines.append(f"- {r} {asp_fr} {oth} : {txt}")

    planets_in_4: List[str] = []
    planetes = theme.get("planetes") or {}
    if isinstance(planetes, dict):
        for name, p in planetes.items():
            if not isinstance(p, dict):
                continue
            h = p.get("maison") or p.get("house")
            if h == 4:
                planets_in_4.append(name)

    planets_in_4_lines: List[str] = []
    for pl in planets_in_4:
        txt = _bdd(_slug(pl), "maison", "4") or _bdd(pl, "maison", "4")
        if txt:
            planets_in_4_lines.append(f"- {pl} en Maison 4 : {txt}")

    master_house_lines: List[str] = []
    for d in rulers_details:
        h = d.get("house")
        if h is None:
            continue
        mh = _bdd("maitre_maison_4", "maison", str(h))
        if mh:
            master_house_lines.append(f"- Maître en Maison {h} : {mh}")

    master_sign_lines: List[str] = []
    for d in rulers_details:
        s = d.get("sign")
        if not s:
            continue
        ms = _bdd("maitre_maison_4", "signe", _slug(s))
        if ms:
            master_sign_lines.append(f"- Maître en {s} : {ms}")
        else:
            master_sign_lines.append(f"- Maître en {s}")

    master_state_lines: List[str] = []
    for d in rulers_details:
        r = d["planet"]
        dign = d["dignity"]
        state = d["state"]
        reasons = ", ".join(d.get("state_reasons", []))

        master_state_lines.append(
            f"- {r} : {state} — dignité : {dign} ; aspects durs : {d['hard_aspects_count']} ; raison : {reasons}"
        )

    figures_lines: List[str] = []
    memoire_lines: List[str] = []

    for pl in planets_in_4:
        if pl in FIGURES_KARMIQUES:
            role = FIGURES_KARMIQUES[pl]
            figures_lines.append(
                f"- {pl} en Maison 4 peut faire résonner une mémoire liée à la figure suivante : {role}."
            )
        elif pl in MEMOIRES_LIGNEE:
            memoire = MEMOIRES_LIGNEE[pl]
            memoire_lines.append(
                f"- {pl} en Maison 4 indique une mémoire transgénérationnelle liée à : {memoire}."
            )

    profil = []

    for d in rulers_details:
        if d["hard_aspects_count"] >= 2:
            profil.append("insécurité émotionnelle")
        if d.get("node_hard_aspects_count", 0) >= 1:
            profil.append("tension karmique familiale")
        if d.get("house") == 12:
            profil.append("mémoire inconsciente forte")
        if d.get("house") == 8:
            profil.append("passé émotionnel chargé")
        if d.get("house") == 4:
            profil.append("ancrage très familial")

    # On ne prend en compte que les aspects liés :
    # - au maître de Maison 4
    # - aux planètes présentes en Maison 4
    relevant_planets_for_house_4 = set(rulers + planets_in_4)

    for a in aspects:
        p1 = a.get("p1") or a.get("planet1") or a.get("astre1") or a.get("planete1")
        p2 = a.get("p2") or a.get("planet2") or a.get("astre2") or a.get("planete2")

        if not p1 or not p2:
            continue

        if p1 not in relevant_planets_for_house_4 and p2 not in relevant_planets_for_house_4:
            continue

        if "Lune" in (p1, p2):
            profil.append("émotionnel intense")
        if "Saturne" in (p1, p2):
            profil.append("blocage / contrôle")
        if "Pluton" in (p1, p2):
            profil.append("intensité / transformation")

    if "Lune" in planets_in_4:
        profil.append("hyper attachement émotionnel")
    if "Saturne" in planets_in_4:
        profil.append("blocage affectif / rigidité")
    if "Neptune" in planets_in_4:
        profil.append("flou dans les racines")
    if "Pluton" in planets_in_4:
        profil.append("mémoire familiale intense")

    profil = list(set(profil))

    synthese = ""
    if profil:
        synthese = "Le point central de ton socle intérieur est marqué par : " + ", ".join(profil) + "."

    content_debug = _join([
    "### Maison 4 — lecture karmique",
    intro,
    "",
    synthese,
    "",
    "#### Signe(s) de Maison 4",
    *([f"- {s}" for s in signs] if signs else ["- (signe de Maison 4 non disponible)"]),
    *sign_texts,
    "",
    "#### Axe Maison IV / Maison X",
    *([f"- Maison X en {s}" for s in house_10_signs] if house_10_signs else ["- (signe de Maison 10 non disponible)"]),
    *([f"- Maître de Maison X : {r}" for r in rulers_10_details] if rulers_10_details else ["- (maître de Maison 10 non détecté)"]),
    "",
    "#### Maître(s) de la Maison 4",
    *([f"- {r}" for r in rulers] if rulers else ["- (maître non détecté)"]),
    "",
    "#### Placement du/des maître(s)",
    *master_house_lines,
    "",
    "#### Signe du/des maître(s)",
    *(master_sign_lines if master_sign_lines else ["- (signe du maître non disponible)"]),
    "",
    "#### État du/des maître(s)",
    *master_state_lines,
    "",
    "#### Aspects du/des maître(s)",
    *(rulers_aspects_lines if rulers_aspects_lines else ["- (pas d’aspects majeurs interprétés via BDD)"]),
    "",
    "#### Planètes en Maison 4",
    *(planets_in_4_lines if planets_in_4_lines else ["- (aucune planète en Maison 4)"]),
    "",
    "#### Figures karmiques",
    *(figures_lines if figures_lines else ["- (aucune figure karmique explicite détectée)"]),
    "",
    "#### Mémoires de lignée",
    *(memoire_lines if memoire_lines else ["- (aucune mémoire de lignée explicite détectée)"]),
])

    content_llm = _join([
        "Résumé psychologique pré-calculé :",
        synthese, 
        "",
        "Données textuelles de la base de données :",
        intro,
        *sign_texts,
        "",
        "Axe Maison IV / Maison X :",
        f"Maison IV : {', '.join(signs) if signs else 'non disponible'}",
        f"Maison X : {', '.join(house_10_signs) if house_10_signs else 'non disponible'}",
        f"Maître(s) Maison IV : {', '.join(rulers) if rulers else 'non détecté'}",
        f"Maître(s) Maison X : {', '.join(rulers_10_details) if rulers_10_details else 'non détecté'}",
        *master_house_lines,
        *master_sign_lines,
        *rulers_aspects_lines,
        *planets_in_4_lines,
        *figures_lines,
        *memoire_lines
    ])

    summary_source = content_llm or content_debug

    summary = summarize_chapter(
        chapter_title="Maison IV — Racines & mémoire karmique",
        chapter_text=summary_source,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    return {
        "id": "maison_4",
        "title": "Maison IV — Racines & mémoire karmique",
        "data": {
            "house_4_signs": signs,
            "house_4_rulers": rulers,
            "house_10_signs": house_10_signs,
            "house_10_rulers": rulers_10,
            "rulers_details": rulers_details,
            "rulers_aspects_count": len(rulers_aspects_lines),
            "planets_in_house_4": planets_in_4,
        },
        "content": content_debug if debug_mode else content_llm,
        "content_llm": content_llm,
        "text": content_debug if debug_mode else content_llm,
        "summary": summary,
    }


def interpret_block_maison_4_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:

    content = (block.get("content_llm") or "").strip()
    if not content or not call_llm:
        return block.get("content_llm", "")

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []
    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("maison_4", "")
    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n\n".join(memories[-5:]) if memories else "Aucune mémoire précédente"

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Tu écris le chapitre dédié à la Maison 4 d'une analyse karmique déjà en cours.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style incarné, psychologique, dense, focalisé sur les profondeurs de l'inconscient.
- Ton sérieux, avec une légère touche d’ironie possible pour souligner les attachements tenaces.
- L'analyse entre directement dans le vif du sujet : n'introduis pas la personne, n'utilise pas son prénom, assure une continuité fluide avec ce qui précède.

**OBJECTIF DE L'ANALYSE**
Mettre en lumière la cave de la psyché et les racines du thème. Tu dois montrer :
- Le socle intérieur et le climat émotionnel de l'enfance ou du passé lointain.
- Les loyautés invisibles, les schémas de sécurité/insécurité hérités (le "clan", les ancêtres).
- La manière dont ce passé (conscient ou karmique) continue de dicter les réactions présentes.
- Lire la Maison 4 comme la racine invisible de l’axe Maison IV / Maison X : ce qui a été hérité dans l’intime, puis transformé en posture sociale, rapport à l’autorité, ambition, protection ou besoin de reconnaissance.

**RÈGLES STRICTES DE RÉDACTION**
- **Distinction Lunaire :** Ne fais pas un chapitre général sur les humeurs ou la sensibilité, déjà traité ailleurs. Si la Lune apparaît dans les données de Maison 4, traite-la uniquement comme indicateur de matrice familiale, de mémoire émotionnelle héritée, de lien au foyer ou de climat d’enfance.
- **Fusion technique :** Décris cela comme un climat intérieur global. Interdiction absolue de lister ou structurer ton texte par signe, maître ou planètes. Tous les éléments (aspects, astres en maison) doivent s'entrelacer pour tisser une seule ambiance psychologique. Les aspects servent à expliquer, pas à faire un catalogue.
- **Format brut :** Produis un texte en flux continu uniquement. Interdiction d'utiliser des titres, sous-titres, ou listes à puces.
- **Continuité :** Appuie-toi sur l'axe central pour montrer ce qui s’est construit très tôt et influence l'évolution actuelle.
- **Axe IV/X :** Utilise la Maison X comme contrepoint naturel de la Maison IV : elle montre comment la personne tente de sortir, compenser ou prolonger son héritage familial dans le monde. Ne transforme pas ce passage en analyse de carrière.
- Montre comment la posture sociale adulte est souvent une compensation ou une réponse directe au climat familial de départ.
- **Longueur :** Rédige 3 paragraphes denses représentant environ 300 à 350 mots au total.

**CONTEXTE ET DONNÉES**
- Axe karmique central : {axe_central}
- Contexte global : {theme_brief}
**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici les concepts psychologiques abordés dans les derniers chapitres :
{memories_txt}


**CONTENU ET DONNÉES BRUTES**
Données techniques de la Maison 4 : {content}

[Début de l'analyse en flux continu :]
""".strip()

    logger.debug(
        "PROMPT MAISON 4\n%s\n%s\n%s",
        "=" * 80,
        prompt,
        "=" * 80,
    )

    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte