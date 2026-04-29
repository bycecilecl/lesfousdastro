# utils/karmique/chapitres/maison_12.py
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
    """Lecture BDD avec fallback et strip."""
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
    "scorpion": ["Mars", "Pluton"],     # tradi + moderne
    "sagittaire": ["Jupiter"],
    "capricorne": ["Saturne"],
    "verseau": ["Saturne", "Uranus"],   # tradi + moderne
    "poissons": ["Jupiter", "Neptune"], # tradi + moderne
}


# -------------------------
# Dignités (simplifié)
# (suffisant pour "bon / difficile")
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
    # modernes souvent non utilisés en exaltation => on laisse vide
}

# Chutes = exaltation opposée ; exils = domicile opposé
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

# -------------------------
# Figures / mémoires (Maison 12)
# -------------------------
MEMOIRES_KARMIQUES_M12 = {
    "Soleil": "effacement de l'ego, identité sacrifiée ou mise en retrait",
    "Lune": "éponges émotionnelles, angoisses prénatales, mémoire de fusion et d'abandon",
    "Mercure": "non-dits, secrets tus, anxiété mentale sourde",
    "Vénus": "amours cachés, sacrifices affectifs, valeurs non reconnues",
    "Mars": "colère refoulée, actions invisibles, autosabotage inconscient",
    "Jupiter": "protecteurs invisibles, fuite dans les dogmes, excès cachés",
    "Saturne": "dette karmique lourde, peurs archaïques, sentiment d'enfermement",
    "Uranus": "rébellion étouffée, rupture soudaine des repères inconscients",
    "Neptune": "dissolution totale, idéalisme sacrificiel, fuite dans l'illusion",
    "Pluton": "traumatismes enfouis, obsessions secrètes, forces de l'ombre agissantes",
}

def _canon_planet(name: Any) -> str:
    if not name:
        return ""
    n = str(name).strip()
    return PLANET_ALIASES.get(n, n)

def _dignity(planet: str, sign: str) -> str:
    """Retourne: domicile / exaltation / exil / chute / neutre"""
    ps = _slug(sign)
    if planet in DOMICILE and ps in DOMICILE[planet]:
        return "domicile"
    if planet in EXALTATION and ps in EXALTATION[planet]:
        return "exaltation"

    # exil = opposé d'un domicile
    if planet in DOMICILE:
        for d in DOMICILE[planet]:
            if OPPOSITE_SIGNS.get(d) == ps:
                return "exil"

    # chute = opposé d'une exaltation
    if planet in EXALTATION:
        for ex in EXALTATION[planet]:
            if OPPOSITE_SIGNS.get(ex) == ps:
                return "chute"

    return "neutre"


def _get_house_signs(theme: Dict[str, Any], house: int = 12) -> List[str]:
    """
    Retourne les signes liés à une maison :
    - signe de cuspide
    - signe(s) intercepté(s) dans cette maison s'il y en a
    """
    out: List[str] = []

    # 1) signe de cuspide via maisons
    houses = theme.get("maisons") or theme.get("houses") or {}

    if isinstance(houses, dict):
        found = False

        for key in (f"Maison {house}", f"Maison_{house}", f"maison_{house}", str(house)):
            if key in houses and isinstance(houses[key], dict):
                s = houses[key].get("signe") or houses[key].get("sign")

                if s and str(s) not in out:
                    out.append(str(s))

                found = True
                break

        if not found and house in houses and isinstance(houses[house], dict):
            s = houses[house].get("signe") or houses[house].get("sign")

            if s and str(s) not in out:
                out.append(str(s))

    elif isinstance(houses, list):
        for item in houses:
            if not isinstance(item, dict):
                continue
            num = item.get("house") or item.get("maison") or item.get("numero") or item.get("num")
            if num == house:
                s = item.get("signe") or item.get("sign")
                if s and str(s) not in out:
                    out.append(str(s))

    # 2) signe(s) intercepté(s) dans cette maison
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

    return out


def _get_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Récupère une liste d'aspects, peu importe la clé."""
    for k in ("aspects", "aspects_majeurs", "aspects_significatifs", "liste_aspects"):
        v = theme.get(k)
        if isinstance(v, list):
            return [a for a in v if isinstance(a, dict)]
    return []


def _planet_pos(theme: Dict[str, Any], planet: str) -> Dict[str, Any]:
    planets = (theme.get("planetes") or {})
    if not isinstance(planets, dict):
        return {}

    # 1) direct
    p = planets.get(planet)
    if isinstance(p, dict):
        return p

    # 2) fallback accents (Vénus <-> Venus)
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
    """
    Filtre les aspects qui touchent `planet`.
    On tolère plein de formats: p1/p2, A/B, planet1/planet2...
    """
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
# BDD lookup aspects (flexible)
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
        txt = _bdd("maitre_maison_12", donnee, valeur)
        if txt:
            logger.debug(
                "BDD aspect Maison 12 trouvé | donnee=%s | valeur=%s",
                donnee,
                valeur,
            )
            return txt

    logger.debug(
        "Aucun texte BDD trouvé pour aspect Maison 12 | aspect=%s | planète=%s",
        aspect,
        other_planet,
    )

    return ""


# -------------------------
# Aspects dissociés (hors signe)
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
# MAIN: block Maison 12
# -------------------------
def build_block_maison_12(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
    debug_mode: bool = False,
) -> Dict[str, Any]:
    """
    Construit le bloc Maison 12 :
    - signe(s) de M12 (intercepté -> 2 signes)
    - maître(s) du signe
    - placement du/des maîtres (signe/maison) + état (dignité + aspects durs)
    - aspects du/des maîtres (BDD)
    - planètes en M12 + interprétation BDD
    """



    signs = _get_house_signs(theme, house=12)  # ex ["Poissons"] ou ["Poissons","Bélier"]
    logger.debug("Maison 12 signs détectés : %s", signs)

    if not signs:
        logger.warning(
            "Aucun signe trouvé pour Maison 12 | clés theme=%s",
            sorted(list(theme.keys())),
        )
    signs_slug = [_slug(s) for s in signs if s]

    # intro M12
    intro = _bdd("maison_12", "intro", "base")

    # signe(s)
    sign_texts = []
    for s in signs_slug:
        t = _bdd("maison_12", "signe", s)
        if t:
            sign_texts.append(t)

    # maîtres
    rulers: List[str] = []
    for s in signs_slug:
        rulers += SIGN_RULERS.get(s, [])
    # unique, conserve l'ordre
    seen = set()
    rulers = [r for r in rulers if not (r in seen or seen.add(r))]

    aspects = _get_aspects(theme)

    rulers_details: List[Dict[str, Any]] = []
    rulers_aspects_lines: List[str] = []

    for r in rulers:
        pos = _planet_pos(theme, r)
        r_sign = pos.get("signe") or pos.get("sign")
        r_house = pos.get("maison") or pos.get("house")
        r_dign = _dignity(r, r_sign) if r_sign else "neutre"

        # aspects du maître
        rasps = _extract_aspects_for_planet(aspects, r)

        filtered_rasps = []

        for a in rasps:
            t = _aspect_type(a)

            other = _canon_planet(_other_planet(a, r))
            other_pos = _planet_pos(theme, other)

            sign_other = other_pos.get("signe") or other_pos.get("sign")

            if _is_dissociated_aspect(r_sign, sign_other, t):
                continue

            filtered_rasps.append(a)

        rasps = filtered_rasps

        # compter durs (carré/opposition) pour “état”
        HARD_ASPECTS = {"carre", "square", "opposition", "opp"}
        NODE_BODIES = {"Rahu", "Ketu", "Nœud Nord", "Nœud Sud"}

        hard = 0
        node_hard = 0

        for a in rasps:
            t = _aspect_type(a)
            oth = _canon_planet(_other_planet(a, r))

            if t not in HARD_ASPECTS:
                continue

            if oth in NODE_BODIES:
                node_hard += 1
            else:
                hard += 1

        # état simplifié
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
            "filtered_aspects": filtered_rasps,
            })

        # rendu aspects via BDD
        for a in rasps:
            t = _aspect_type(a)
            oth = _other_planet(a, r)
            if not t or not oth:
                continue

            # on garde seulement les 5 aspects majeurs connus
            if t not in ("conjonction", "conjunction", "carre", "square", "opposition", "opp", "trigone", "trine", "sextile"):
                continue

            # normalise les noms
            asp_fr = {
                "conjunction": "conjonction",
                "square": "carre",
                "opp": "opposition",
                "trine": "trigone",
            }.get(t, t)

            txt = _bdd_master_aspect(asp_fr, oth)
            if txt:
                rulers_aspects_lines.append(f"- {r} {asp_fr} {oth} : {txt}")

    # Planètes en maison 12
    planets_in_12: List[str] = []
    planetes = theme.get("planetes") or {}
    if isinstance(planetes, dict):
        for name, p in planetes.items():
            if not isinstance(p, dict):
                continue
            h = p.get("maison") or p.get("house")
            if h == 12:
                planets_in_12.append(name)

    planets_in_12_lines: List[str] = []
    for pl in planets_in_12:
        # tu as déjà ce format: ASTRE=soleil DONNEE=maison VALEUR=12
        txt = _bdd(_slug(pl), "maison", "12") or _bdd(pl, "maison", "12")
        if txt:
            planets_in_12_lines.append(f"- {pl} en Maison 12 : {txt}")

    # Placement du maître (BDD “maitre_maison_12 maison <n>”)
    master_house_lines: List[str] = []
    for d in rulers_details:
        h = d.get("house")
        if h is None:
            continue
        mh = _bdd("maitre_maison_12", "maison", str(h))
        if mh:
            master_house_lines.append(f"- Maître en Maison {h} : {mh}")

    # Signe du maître (BDD “maitre_maison_12 signe <signe>”)
    master_sign_lines: List[str] = []
    for d in rulers_details:
        s = d.get("sign")
        if not s:
            continue
        ms = _bdd("maitre_maison_12", "signe", _slug(s))
        if ms:
            master_sign_lines.append(f"- Maître en {s} : {ms}")
        else:
            master_sign_lines.append(f"- Maître en {s}")

    # Etat du maître (phrase courte)
    master_state_lines: List[str] = []
    for d in rulers_details:
        r = d["planet"]
        dign = d["dignity"]
        state = d["state"]
        node_hard = d.get("node_hard_aspects_count", 0)
        reasons = ", ".join(d.get("state_reasons", []))

        master_state_lines.append(
            f"- {r} : {state} — dignité : {dign} ; "
            f"aspects durs : {d['hard_aspects_count']} ; "
            f"aspects durs aux Nœuds : {node_hard} ; "
            f"raison : {reasons}"
        )


    # -------------------------
    # SYNTHÈSE PSYCHOLOGIQUE (NEW)
    # -------------------------

    profil = []

    # 1. Analyse des aspects liés UNIQUEMENT aux maîtres de la Maison 12
    for d in rulers_details:
        if d.get("hard_aspects_count", 0) >= 2:
            profil.append("inconscient très agité")

        r = d["planet"]
        rasps = d.get("filtered_aspects", [])

        for a in rasps:
            oth = _canon_planet(_other_planet(a, r))
            if oth == "Neptune":
                profil.append("confusion / illusion profonde")
            if oth == "Saturne":
                profil.append("blocages inconscients profonds")
            if oth == "Pluton":
                profil.append("forces souterraines puissantes")

    # 2. Analyse des maisons des maîtres
    for d in rulers_details:
        if d.get("house") == 12:
            profil.append("isolement psychique fort")
        if d.get("house") == 8:
            profil.append("karma d'épreuve et de transformation")
        if d.get("house") == 4:
            profil.append("bagage ancestral très lourd")

    # 3. Analyse des mémoires karmiques des planètes présentes EN Maison 12
    memoires_m12_lines: List[str] = []
    for pl in planets_in_12:
        if pl in MEMOIRES_KARMIQUES_M12:
            memoire = MEMOIRES_KARMIQUES_M12[pl]
            profil.append(f"mémoire d'ombre ({pl.lower()})")
            memoires_m12_lines.append(f"- {pl} en Maison 12 : {memoire}.")

    # Nettoyer les doublons
    seen = set()
    profil = [x for x in profil if not (x in seen or seen.add(x))]

    # Créer la phrase de synthèse
    synthese = ""
    if profil:
        synthese = "Le point central de cet angle mort psychologique est marqué par : " + ", ".join(profil) + "."

    # 4. Constitution du contenu final envoyé à l'IA
    content_debug = _join([
        "### Maison 12 — lecture karmique",
        "Résumé psychologique pré-calculé :",
        synthese,
        "",
        "Données textuelles de la base de données :",
        intro,
        "#### Signe(s) de Maison 12",
        *([f"- {s}" for s in signs] if signs else ["- (signe de Maison 12 non disponible)"]),
        *sign_texts,
        "",
        "#### Maître(s) de la Maison 12",
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
        "#### Planètes en Maison 12",
        *(planets_in_12_lines if planets_in_12_lines else ["- (aucune planète en Maison 12)"]),
        "",
        "#### Mémoires karmiques activées",
        *(memoires_m12_lines if memoires_m12_lines else ["- (aucune mémoire planétaire spécifique détectée)"]),
    ])

    content_llm = _join([
        "Résumé psychologique pré-calculé :",
        synthese,
        "",
        "Données textuelles de la base de données :",
        intro,
        *sign_texts,
        *master_house_lines,
        *master_sign_lines,
        *rulers_aspects_lines,
        *planets_in_12_lines,
        *memoires_m12_lines,
    ])

    summary_source = content_llm or content_debug

    summary = summarize_chapter(
        chapter_title="Maison XII — Vie antérieure & karma actif",
        chapter_text=summary_source,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    return {
        "id": "maison_12",
        "title": "Maison XII — Vie antérieure & karma actif",
        "data": {
            "house_12_signs": signs,
            "house_12_rulers": rulers,
            "rulers_details": rulers_details,
            "rulers_aspects_count": len(rulers_aspects_lines),
            "planets_in_house_12": planets_in_12,
        },
        "content": content_debug if debug_mode else content_llm,
        "content_llm": content_llm,
        "text": content_debug if debug_mode else content_llm,
        "summary": summary,
    }


def interpret_block_maison_12_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:

    content = (block.get("content_llm") or "").strip()
    if not content or not call_llm:
        return block.get("content_llm", "") or block.get("content", "")

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []
    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("maison_12", "")

    memories = (global_ctx or {}).get("memoires_contextuelles", [])
     # 🔥 on limite pour éviter surcharge
    memories_txt = "\n".join(memories[-3:]) if memories else "aucune mémoire disponible"
    logger.debug("Maison 12 memories_txt = %s", memories_txt)

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Tu réécris le chapitre dédié à la Maison 12 d'une analyse karmique déjà en cours.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style incarné, psychologique, dense, sans phrases creuses ni développement personnel cliché.
- Évite les formulations trop spirituelles vagues comme "tu es invité à", "transcender", "t'élever", "mission d'âme". Préfère des formulations concrètes : "cela se rejoue quand...", "cela agit par...", "cela se manifeste dans..."
- Ton sérieux, avec une légère touche d’ironie possible pour souligner les mécanismes d'aveuglement.
- L'analyse entre directement dans le vif du sujet : pas d'introduction, pas de prénom, continuité parfaite.

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
Mettre en lumière l'angle mort de la psyché et le bagage karmique enfoui :
- Les schémas inconscients, les fantômes du passé, les mécanismes de refoulement ou d'autosabotage invisible.
- Les zones de repli, d'évitement, de fatigue intérieure, de dissolution de l'ego ou de confusion.
- Focus exclusif : Le courant souterrain et le "flou". Laisse les crises de pouvoir/destruction à la Maison 8 et la direction de vie aux Nœuds Lunaires. Ici, on explore la brume, l'isolement et ce qui échappe au contrôle.

**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici les concepts psychologiques abordés dans les derniers chapitres :
{memories_txt}

**CONSIGNE ANTI-REDONDANCE IMPÉRATIVE**
- INTERDICTION de ré-expliquer les concepts listés ci-dessus.
- Si la Maison 12 s'appuie sur un sentiment déjà évoqué dans la mémoire (ex: l'anxiété), traite-le comme un fait établi et concentre-toi sur la manière dont il *agit en arrière-plan* (répétitions, fuites, sensations de fatalité).
- Chaque phrase doit apporter une information nouvelle sur l'inconscient de l'utilisateur.

**RÈGLES STRICTES DE RÉDACTION**
- **Fusion technique :** Décris cela comme un courant psychique global. Interdiction absolue de lister ou structurer ton texte par signe, maître ou planètes. 
- **Points sensibles :** Si Chiron, la Lune Noire ou la Part de Fortune apparaissent dans les données, mentionne-les très brièvement comme des "colorations" sans les développer.
- **Format brut :** Flux continu uniquement. Zéro titre, zéro liste. Intègre les données astrologiques de manière fluide, sans faire de catalogue technique.
- **Longueur :** 3 paragraphes denses (~300-350 mots).

**CONTEXTE ET DONNÉES TECHNIQUES À TRANSFORMER**
Axe central : {axe_central}
Contexte global : {theme_brief}

Données brutes de la Maison 12 : 
{content}

[Début de l'analyse en flux continu :]
""".strip()
    
    logger.debug(
        "PROMPT MAISON 12\n%s\n%s\n%s",
        "=" * 80,
        prompt,
        "=" * 80,
    )

    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte