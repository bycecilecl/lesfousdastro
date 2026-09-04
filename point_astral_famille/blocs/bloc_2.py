from __future__ import annotations

from textwrap import dedent
from typing import Dict, Any, Optional
import re
import logging

#from utils.llm_client import ask_llm
from point_astral_famille.llm_client import ask_llm
from point_astral_famille.selection_donnees import (
    exclure_aspects_aux_noeuds,
    retrogradation_lente_pertinente,
)
from point_astral_famille.database import (
    formater_interpretation_planete_bdd,
    formater_interpretation_etat_bdd,
    rechercher_interpretation_aspect,
    rechercher_ligne_bdd,
)

from point_astral_famille.configurations_astrologiques import (
    formater_configurations_majeures,
)

logger = logging.getLogger(__name__)


# ============================================================
# BLOC 2 V2 — ÉMOTIONS / FONDATIONS / FAMILLE
# ============================================================
# Partie 1 : Lune (émotions, besoins, sécurité) + Maison IV comme socle intérieur.
# Partie 2 : Famille / foyer / pôle mère / pôle père.
#
# Un seul système de scoring. Pas de fonctions build_* redondantes.
# On collecte des données structurées, on score, on formate, on génère.


# ------------------------------------------------------------
# Constantes
# ------------------------------------------------------------

CANON_ASPECT = {
    "carré": "Carré", "carre": "Carré", "square": "Carré",
    "opposition": "Opposition", "opp": "Opposition",
    "conjonction": "Conjonction", "conj": "Conjonction",
    "conjonction dissociée": "conjonction_dissociee",
    "conjonction dissociee": "conjonction_dissociee",
    "conjonction_dissociee": "conjonction_dissociee",
    "trigone": "Trigone", "trine": "Trigone",
    "sextile": "Sextile",
}

POINT_ALIASES = {
    "mc": "MC", "m.c.": "MC", "milieu du ciel": "MC", "midheaven": "MC",
    "ic": "IC", "f.c.": "IC", "fc": "IC", "fond du ciel": "IC",
    "noeud nord": "Rahu", "nœud nord": "Rahu",
    "noeud sud": "Ketu", "nœud sud": "Ketu",
    "lilith": "Lune Noire",
}

PLANET_ALIASES = {
    "sun": "Soleil", "soleil": "Soleil",
    "moon": "Lune", "lune": "Lune",
    "mercury": "Mercure", "mercure": "Mercure",
    "venus": "Vénus", "vénus": "Vénus",
    "mars": "Mars", "jupiter": "Jupiter",
    "saturn": "Saturne", "saturne": "Saturne",
    "uranus": "Uranus", "neptune": "Neptune",
    "pluto": "Pluton", "pluton": "Pluton",
    "chiron": "Chiron",
}

ASPECTS_DURS = {"Conjonction", "conjonction_dissociee", "Carré", "Opposition"}
ASPECTS_FLUIDES = {"Trigone", "Sextile"}

ORBE_MAX_GENERAL = 8.0
ORBE_MAX_LUNE_NOIRE = 5.0

POINTS_EXCLUS = {
    "Junon", "Cérès", "Pallas", "Vesta",
    "Part de Fortune", "Point d’Illumination", "Vertex",
}

PLANETES_PRINCIPALES = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
    "Chiron", "Lune Noire", "Rahu", "Ketu",
}

MARQUEURS_FAMILIAUX_FORTS = {
    "Lune Noire", "Chiron", "Pluton", "Saturne", "Neptune", "Mars", "Uranus", "Ketu"
}

RULERS = {
    "Bélier": ["Mars"], "Taureau": ["Vénus"], "Gémeaux": ["Mercure"],
    "Cancer": ["Lune"], "Lion": ["Soleil"], "Vierge": ["Mercure"],
    "Balance": ["Vénus"], "Scorpion": ["Pluton", "Mars"], "Sagittaire": ["Jupiter"],
    "Capricorne": ["Saturne"], "Verseau": ["Uranus", "Saturne"], "Poissons": ["Neptune", "Jupiter"],
}

DIGNITES = {
    "Lune": {
        "domicile": ["Cancer"],
        "exaltation": ["Taureau"],
        "chute": ["Scorpion"],
        "exil": ["Capricorne"],
    },
    "Soleil": {
        "domicile": ["Lion"],
        "exaltation": ["Bélier"],
        "chute": ["Balance"],
        "exil": ["Verseau"],
    },
    "Mercure": {
        "domicile": ["Gémeaux", "Vierge"],
        "exaltation": ["Vierge"],
        "chute": ["Poissons"],
        "exil": ["Sagittaire", "Poissons"],
    },
    "Vénus": {
        "domicile": ["Taureau", "Balance"],
        "exaltation": ["Poissons"],
        "chute": ["Vierge"],
        "exil": ["Bélier", "Scorpion"],
    },
    "Mars": {
        "domicile": ["Bélier", "Scorpion"],
        "exaltation": ["Capricorne"],
        "chute": ["Cancer"],
        "exil": ["Taureau", "Balance"],
    },
    "Jupiter": {
        "domicile": ["Sagittaire", "Poissons"],
        "exaltation": ["Cancer"],
        "chute": ["Capricorne"],
        "exil": ["Gémeaux", "Vierge"],
    },
    "Saturne": {
        "domicile": ["Capricorne", "Verseau"],
        "exaltation": ["Balance"],
        "chute": ["Bélier"],
        "exil": ["Cancer", "Lion"],
    },
    "Uranus": {
        "domicile": ["Verseau"],
        "exil": ["Lion"],
    },
    "Neptune": {
        "domicile": ["Poissons"],
        "exil": ["Vierge"],
    },
    "Pluton": {
        "domicile": ["Scorpion"],
        "exil": ["Taureau"],
    },
}


def extraire_resume_developpe(texte):
    match = re.search(
        r"<resume_developpe>\s*(.*?)\s*</resume_developpe>",
        texte,
        re.DOTALL,
    )

    resume = match.group(1).strip() if match else ""

    texte_sans_resume = re.sub(
        r"<resume_developpe>.*?</resume_developpe>",
        "",
        texte,
        flags=re.DOTALL,
    ).strip()

    return texte_sans_resume, resume

# ------------------------------------------------------------
# Helpers métier (autonomes)
# ------------------------------------------------------------
def nom_affichage(planete: str) -> str:
    return {
        "Rahu": "Nœud Nord",
        "Ketu": "Nœud Sud",
    }.get(planete, planete)

def _normalize_aspect(name: str) -> str:
    if not name:
        return ""
    return CANON_ASPECT.get(str(name).strip().lower(), str(name).strip().capitalize())

def marquer_conjonctions_dissociees(aspects: list[dict], planetes: dict) -> list[dict]:
    for a in aspects:
        if a.get("aspect") != "Conjonction":
            continue

        p1 = a.get("planete1")
        p2 = a.get("planete2")

        signe1 = (planetes.get(p1, {}) or {}).get("signe")
        signe2 = (planetes.get(p2, {}) or {}).get("signe")

        if signe1 and signe2 and signe1 != signe2:
            a["aspect"] = "conjonction_dissociee"

    return aspects


def _normalize_body(name: str) -> str:
    if not name:
        return ""
    key = str(name).strip().lower()
    if key in POINT_ALIASES:
        return POINT_ALIASES[key]
    if key in PLANET_ALIASES:
        return PLANET_ALIASES[key]
    return str(name).strip()


def _orbe(a: dict) -> float:
    try:
        return float(str(a.get("orbe", 99)).replace(",", "."))
    except Exception:
        return 99.0


def _is_to(target: str, a: dict) -> bool:
    t = _normalize_body(target)
    return _normalize_body(a.get("planete1")) == t or _normalize_body(a.get("planete2")) == t


def _normalize_aspects(aspects: list[dict]) -> list[dict]:
    out = []
    for raw in aspects or []:
        a = dict(raw)
        if a.get("planete1") is None and a.get("p1") is not None:
            a["planete1"] = a.get("p1")
        if a.get("planete2") is None and a.get("p2") is not None:
            a["planete2"] = a.get("p2")
        a["aspect"] = _normalize_aspect(a.get("aspect"))
        a["planete1"] = _normalize_body(a.get("planete1"))
        a["planete2"] = _normalize_body(a.get("planete2"))
        out.append(a)
    return out


def _exclure_points_mineurs(aspects: list[dict]) -> list[dict]:
    return [
        a for a in aspects
        if a.get("planete1") not in POINTS_EXCLUS and a.get("planete2") not in POINTS_EXCLUS
    ]


def dignite_planete(planete: str, signe: str) -> str:
    data = DIGNITES.get(planete)
    if not data:
        return ""
    for dignite, signes in data.items():
        if signe in signes:
            return dignite
    return ""


def _est_retrograde(theme: dict, planete: str) -> bool:
    d = (theme.get("planetes", {}) or {}).get(planete, {}) or {}
    return bool(d.get("retrograde") or d.get("rx"))


def _est_intercepte(theme: dict, objet: str) -> bool:
    planetes = theme.get("planetes", {}) or {}
    placement = planetes.get(objet, {}) or {}
    if placement.get("intercepte") or placement.get("intercepté"):
        return True
    inter = theme.get("interceptions") or {}
    if isinstance(inter, dict):
        planets_inter = inter.get("planetes") or inter.get("planètes") or []
        if objet in planets_inter:
            return True
        signe_obj = placement.get("signe")
        signes_inter = (
            inter.get("signes") or inter.get("signes_interceptes")
            or inter.get("signes_interceptés") or []
        )
        if signe_obj and signe_obj in signes_inter:
            return True
    return False


def _placement(theme: dict, planete: Optional[str]) -> str:
    if not planete:
        return "N/A"
    obj = (theme.get("planetes", {}) or {}).get(planete, {}) or {}
    extra = []
    if obj.get("retrograde") or obj.get("rx"):
        extra.append("rétrograde")
    if _est_intercepte(theme, planete):
        extra.append("intercepté")
    extra_txt = f" ({', '.join(extra)})" if extra else ""
    return f"{nom_affichage(planete)} en {obj.get('signe', 'N/A')} — Maison {obj.get('maison', 'N/A')}{extra_txt}"


def _placements_compact(planetes: dict) -> str:
    abbrev = {
        "Bélier": "Bé", "Taureau": "Ta", "Gémeaux": "Gé", "Cancer": "Ca",
        "Lion": "Li", "Vierge": "Vi", "Balance": "Ba", "Scorpion": "Sc",
        "Sagittaire": "Sg", "Capricorne": "Cp", "Verseau": "Vr", "Poissons": "Po",
    }
    parts = []
    for p, d in planetes.items():
        if p not in PLANETES_PRINCIPALES:
            continue
        signe = abbrev.get(d.get("signe", ""), d.get("signe", "?"))
        parts.append(f"{p} {signe} M{d.get('maison', '?')}")
    return " | ".join(parts)


def get_maison(theme: dict, num: int) -> dict:
    maisons = theme.get("maisons", {}) or {}
    return maisons.get(num) or maisons.get(str(num)) or maisons.get(f"Maison {num}") or {}


def get_maitres_maison(theme: dict, num: int) -> list[str]:
    signe = get_maison(theme, num).get("signe")
    if not signe:
        return []
    rulers = RULERS.get(signe) or []
    if isinstance(rulers, str):
        rulers = [rulers]
    return [_normalize_body(r) for r in rulers]


def maitres_interceptes_dans_maison(theme: dict, maison_num: int) -> list[str]:
    inter = theme.get("interceptions") or {}
    signes = inter.get("signes") or inter.get("signes_interceptes") or inter.get("signes_interceptés") or []
    maisons_raw = inter.get("maisons") or inter.get("maisons_interceptees") or inter.get("maisons_interceptées") or {}
    maitres = []
    items = maisons_raw.items() if isinstance(maisons_raw, dict) else []
    for signe, maison_txt in items:
        match = re.search(r"\d+", str(maison_txt))
        if not match or int(match.group()) != int(maison_num) or signe not in signes:
            continue
        for maitre in RULERS.get(signe, []):
            if maitre not in maitres:
                maitres.append(maitre)
    return maitres


def planetes_en_maison(theme: dict, num: int) -> list[str]:
    planetes = theme.get("planetes", {}) or {}
    exclus = {"Ascendant", "MC", "IC", "FC", "Descendant"}
    return [p for p, d in planetes.items()
            if str(d.get("maison")) == str(num) and p not in exclus]


def fmt_planetes_en_maison(theme: dict, num: int) -> str:
    planetes = theme.get("planetes", {}) or {}
    items = []
    for p in planetes_en_maison(theme, num):
        d = planetes.get(p, {}) or {}
        flags = []
        if p in MARQUEURS_FAMILIAUX_FORTS:
            flags.append("marqueur familial fort")
        if _est_intercepte(theme, p):
            flags.append("intercepté")
        flag_txt = f" [{', '.join(flags)}]" if flags else ""
        items.append(f"{nom_affichage(p)} en {d.get('signe', 'N/A')}{flag_txt}")
    return ", ".join(items) if items else "Aucune"


def _slug_bdd(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    for a, b in [("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("â", "a"),
                 ("î", "i"), ("ï", "i"), ("ô", "o"), ("ù", "u"), ("û", "u"),
                 ("ç", "c"), ("œ", "oe"), (" ", "_")]:
        s = s.replace(a, b)
    return s


def _extract_nakshatra_lune(contexte: dict) -> str:
    direct = (contexte.get("nakshatra_lune") or "").strip()
    if direct:
        return direct
    for scope in (contexte, (contexte.get("theme") or {}), (contexte.get("data_theme") or {})):
        if not isinstance(scope, dict):
            continue
        for key in ("planetes_vediques", "placements_vediques", "resultats_vediques"):
            ved = scope.get(key) or {}
            if isinstance(ved, dict):
                lune = ved.get("Lune") or ved.get("lune") or {}
                nk = (lune.get("nakshatra") or lune.get("nakshatra_lune") or "").strip()
                if nk:
                    return nk
    placements_str = contexte.get("placements_str", "") or contexte.get("placements", "") or ""
    if placements_str:
        for pattern in (r"Lune\s*[—-]\s*Nakshatra\s*:\s*([\wÀ-ÿ\-]+)",
                        r"Lune.*?Nakshatra.*?:\s*([\wÀ-ÿ\-]+)"):
            match = re.search(pattern, placements_str, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
    return "non précisé ici"


def build_interceptions_famille(theme: dict, aspects: list[dict]) -> str:
    inter = theme.get("interceptions") or {}
    signes = (inter.get("signes") or inter.get("signes_interceptes")
              or inter.get("signes_interceptés") or [])
    maisons_raw = (inter.get("maisons") or inter.get("maisons_interceptees")
                   or inter.get("maisons_interceptées") or {})

    maisons_nums = []
    values = list(maisons_raw.values()) if isinstance(maisons_raw, dict) else maisons_raw
    for m in values:
        match = re.search(r"\d+", str(m))
        if match:
            maisons_nums.append(int(match.group()))
    maisons_nums = sorted(set(maisons_nums))

    maisons_set = set(maisons_nums)
    signes_set = {
        str(signe).strip().casefold()
        for signe in signes
        if signe
    }

    axe_maisons_parentales = {4, 10}.issubset(maisons_set)

    axe_signes_parentaux = {
        "cancer",
        "capricorne",
    }.issubset(signes_set)

    # On retient :
    # - toute interception située sur l’axe des maisons IV/X ;
    # - ou toute interception de l’axe Cancer/Capricorne,
    #   même si elle tombe dans d’autres maisons.
    if not (axe_maisons_parentales or axe_signes_parentaux):
        return "—"

    if axe_maisons_parentales:
        # Exemple : Vierge / Poissons interceptés sur les maisons IV/X
        signes_retenus = []

        if isinstance(maisons_raw, dict):
            for signe, maison_txt in maisons_raw.items():
                match = re.search(r"\d+", str(maison_txt))

                if match and int(match.group()) in {4, 10}:
                    signes_retenus.append(signe)

        maison_key = "4-10"

    else:
        # Exemple : Cancer / Capricorne interceptés sur les maisons I/VII
        signes_retenus = [
            signe
            for signe in signes
            if str(signe).strip().casefold() in {
                "cancer",
                "capricorne",
            }
        ]

        maison_key = "cancer_capricorne"

    s1 = (
        signes_retenus[0]
        if len(signes_retenus) >= 1
        else "signe non précisé"
    )

    s2 = (
        signes_retenus[1]
        if len(signes_retenus) >= 2
        else "signe non précisé"
    )

    ligne_interception = rechercher_ligne_bdd(
        astre="interception",
        donnee="axe",
        valeur=maison_key,
        fichier="LLM_bdd_astro_placements.csv",
    )

    txt = ""

    if ligne_interception:
        txt = (
            str(ligne_interception.get("FAMILLE") or "").strip()
            or str(ligne_interception.get("INTERPRETATION") or "").strip()
        )

    lignes = [f"Interception active sur l’axe parental {maison_key} : {s1} / {s2}"]
    if txt:
        lignes.append(txt.strip())
    return "\n".join(lignes)


# ------------------------------------------------------------
# Scoring unique des aspects
# ------------------------------------------------------------

POIDS_ASPECT = {
    "Conjonction": 3,
    "conjonction_dissociee": 2.5,
    "Opposition": 2,
    "Carré": 2,
    "Trigone": 1,
    "Sextile": 1,
}

# Planètes lourdes : structurent vraiment le récit émotionnel et familial.
POIDS_PLANETE = {
    "Neptune": 3,
    "Pluton": 3,
    "Saturne": 3,
    "Chiron": 2,
    "Uranus": 2,
    "Lune Noire": 3,
    "Mars": 1,
}

ASPECTS_BLOC2_PRIORITAIRES = {
    frozenset(("Lune", "Neptune")),
    frozenset(("Lune", "Saturne")),
    frozenset(("Lune", "Pluton")),
    frozenset(("Lune", "Uranus")),
    frozenset(("Lune", "Chiron")),
    frozenset(("Lune", "Mars")),
    frozenset(("Lune", "Soleil")),
    frozenset(("Lune", "Lune Noire")),

    frozenset(("Soleil", "Neptune")),
    frozenset(("Soleil", "Saturne")),
    frozenset(("Soleil", "Pluton")),
    frozenset(("Soleil", "Uranus")),
    frozenset(("Soleil", "Chiron")),
    frozenset(("Soleil", "Mars")),
    frozenset(("Soleil", "Lune Noire")),

    frozenset(("Saturne", "Neptune")),
    frozenset(("Saturne", "Pluton")),
    frozenset(("Saturne", "Uranus")),
    frozenset(("Saturne", "Chiron")),
    frozenset(("Saturne", "Lune Noire")),
}


def score_aspect(a: dict) -> float:
    """
    Plus le score est haut, plus l'aspect est structurant.
    Combine : type d'aspect + planètes lourdes impliquées + serrage de l'orbe.
    La Lune et le Soleil reçoivent un bonus : un aspect Lune-Soleil prime
    psychologiquement sur un Saturne-Neptune même si les deux sont lourds.
    """
    p1, p2 = a.get("planete1"), a.get("planete2")
    poids = POIDS_ASPECT.get(a.get("aspect"), 0)
    poids += POIDS_PLANETE.get(p1, 0)
    poids += POIDS_PLANETE.get(p2, 0)
    if "Lune" in {p1, p2}:
        poids += 4
    if "Soleil" in {p1, p2}:
        poids += 3
    return poids - (_orbe(a) * 0.3)


def aspects_structurants(
    aspects: list[dict],
    cible: str,
    top: int = 3,
    max_orbe_dur: float = 6.5,
    max_orbe_fluide: float = 5.0,
) -> list[dict]:
    """
    Retourne les aspects les plus structurants impliquant `cible`.

    Par défaut :
    - conjonctions, carrés et oppositions jusqu’à 6,5° ;
    - trigones et sextiles jusqu’à 5°.
    """
    retenus = []

    for a in aspects or []:
        if not _is_to(cible, a):
            continue

        orbe = _orbe(a)
        type_aspect = a.get("aspect")

        implique_lune_noire = (
            "Lune Noire"
            in {
                a.get("planete1"),
                a.get("planete2"),
            }
        )

        if (
            implique_lune_noire
            and orbe > ORBE_MAX_LUNE_NOIRE
        ):
            continue

        if (
            type_aspect in ASPECTS_DURS
            and orbe <= max_orbe_dur
        ):
            retenus.append(a)

        elif (
            type_aspect in ASPECTS_FLUIDES
            and orbe <= max_orbe_fluide
        ):
            retenus.append(a)

    types_conjonction = {
        "Conjonction",
        "conjonction_dissociee",
    }

    conjonctions = [
        aspect
        for aspect in retenus
        if aspect.get("aspect") in types_conjonction
    ]

    autres_aspects = [
        aspect
        for aspect in retenus
        if aspect.get("aspect") not in types_conjonction
    ]

    conjonctions.sort(key=_orbe)
    autres_aspects.sort(key=score_aspect, reverse=True)

    return conjonctions + autres_aspects[:top]

def aspects_prioritaires_famille(
    aspects: list[dict],
    cibles: set[str] | None = None,
    limite: int = 8,
) -> list[dict]:
    """
    Sélectionne les conjonctions et tensions qui structurent le récit
    familial.

    Toute conjonction ou tension impliquant la Lune, le Soleil,
    Saturne ou un maître d’angle parental peut être prioritaire.

    ASPECTS_BLOC2_PRIORITAIRES sert uniquement de bonus et non
    de filtre exclusif.
    """
    if cibles is None:
        cibles = {
            "Lune",
            "Soleil",
            "Saturne",
        }

    retenus = []
    vus = set()

    for aspect in aspects or []:
        type_aspect = aspect.get("aspect")

        if type_aspect not in ASPECTS_DURS:
            continue

        if _orbe(aspect) > 6.5:
            continue

        p1 = aspect.get("planete1")
        p2 = aspect.get("planete2")
        corps = {p1, p2}

        if not corps.intersection(cibles):
            continue

        # Les aspects aux angles décrivent les conséquences identitaires,
        # pas directement le comportement ou la présence d’un parent.
        if corps.intersection(
            {
                "Ascendant",
                "MC",
                "IC",
            }
        ):
            continue

        if (
            "Lune Noire" in corps
            and _orbe(aspect) > ORBE_MAX_LUNE_NOIRE
        ):
            continue

        cle = (
            tuple(sorted(corps)),
            type_aspect,
        )

        if cle in vus:
            continue

        vus.add(cle)
        retenus.append(aspect)

    def cle_priorite(aspect: dict) -> tuple:
        paire = frozenset(
            (
                aspect.get("planete1"),
                aspect.get("planete2"),
            )
        )

        bonus = (
            2
            if paire in ASPECTS_BLOC2_PRIORITAIRES
            else 0
        )

        est_conjonction = aspect.get("aspect") in {
            "Conjonction",
            "conjonction_dissociee",
        }

        return (
            0 if est_conjonction else 1,
            -(score_aspect(aspect) + bonus),
            _orbe(aspect),
        )

    retenus.sort(key=cle_priorite)

    return retenus[:limite]

# ------------------------------------------------------------
# Formatage léger
# ------------------------------------------------------------

def fmt_aspect(a: dict, planetes: dict) -> str:
    p1, p2 = a.get("planete1"), a.get("planete2")
    d1 = planetes.get(p1, {}) or {}
    d2 = planetes.get(p2, {}) or {}
    aspect_affiche = {
        "conjonction_dissociee": "Conjonction dissociée",
    }.get(a.get("aspect"), a.get("aspect"))
    return (
        f"{nom_affichage(p1)} ({d1.get('signe', '?')}, M{d1.get('maison', '?')}) "
        f"{aspect_affiche} "
        f"{nom_affichage(p2)} ({d2.get('signe', '?')}, M{d2.get('maison', '?')}) "
        f"(orbe {a.get('orbe')}°)"
    )


def fmt_aspects(liste: list[dict], planetes: dict) -> str:
    vus = set()
    lignes = []
    for a in liste:
        cle = (
            tuple(sorted([a.get("planete1"), a.get("planete2")])),
            a.get("aspect"),
        )
        if cle in vus:
            continue
        vus.add(cle)
        lignes.append(fmt_aspect(a, planetes))
    return "\n".join(lignes) or "—"

def classer_aspects_famille(
    aspects: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    conjonctions = []
    tensions = []
    fluides = []

    for aspect in aspects or []:
        type_aspect = aspect.get("aspect")

        if type_aspect in {
            "Conjonction",
            "conjonction_dissociee",
        }:
            conjonctions.append(aspect)

        elif type_aspect in {
            "Carré",
            "Opposition",
        }:
            tensions.append(aspect)

        elif type_aspect in ASPECTS_FLUIDES:
            fluides.append(aspect)

    return conjonctions, tensions, fluides

def formater_resultat_bdd(
    type_entree: str,
    cle: str,
    colonne: str,
    texte: str,
) -> str:
    """Sépare clairement chaque définition BDD dans le dossier envoyé au LLM."""
    return (
        "\n"
        "────────────────────────────────────────\n"
        f"{type_entree} : {cle}\n"
        f"BDD : {colonne}\n\n"
        f"{texte.strip()}\n"
        "────────────────────────────────────────"
    )

def bdd_aspects(
    liste: list[dict],
    colonne: str,
    max_blocs: int = 2,
) -> str:
    """
    Interprétations BDD des aspects, limitées aux plus structurants.
    Chaque aspect et sa définition sont clairement séparés.
    """
    blocs = []
    textes_deja_ajoutes = set()

    for a in liste:
        aspect = a.get("aspect")

        if aspect in ASPECTS_FLUIDES:
            aspect_bdd = "Trigone/Sextile"
        elif aspect == "conjonction_dissociee":
            aspect_bdd = "conjonction_dissociee"
        else:
            aspect_bdd = aspect

        planete1 = a.get("planete1")
        planete2 = a.get("planete2")

        # print(
        #     "RECHERCHE :",
        #     planete1,
        #     "|",
        #     aspect_bdd,
        #     "|",
        #     planete2,
        #     "|",
        #     colonne,
        # )

        txt = (
            rechercher_interpretation_aspect(
                planete1,
                aspect_bdd,
                planete2,
                colonne=colonne,
            )
            or rechercher_interpretation_aspect(
                planete2,
                aspect_bdd,
                planete1,
                colonne=colonne,
            )
            or ""
        )

        txt = txt.strip()

        if txt and txt not in textes_deja_ajoutes:
            textes_deja_ajoutes.add(txt)

            cle = f"{planete1} {aspect_bdd} {planete2}"

            blocs.append(
                formater_resultat_bdd(
                    type_entree="ASPECT",
                    cle=cle,
                    colonne=colonne,
                    texte=txt,
                )
            )

            if len(blocs) >= max_blocs:
                break

    return "\n\n".join(blocs)

def bdd_aspects_maitre_angle(
    liste: list[dict],
    type_bdd: str,
    maitre: str,
    colonnes: list[str],
    max_blocs: int = 2,
) -> str:
    """
    Recherche les interprétations fonctionnelles d'un maître d'angle.

    Exemple :
    - la Lune est maître du FDC et carré Saturne ;
    - on cherche : maitre_fdc | carré | saturne
    et non : lune | carré | saturne.
    """
    lignes = []

    for a in liste[:max_blocs]:
        aspect = a.get("aspect")

        if aspect in ASPECTS_FLUIDES:
            aspect_bdd = "Trigone/Sextile"
        elif aspect == "conjonction_dissociee":
            aspect_bdd = "conjonction_dissociee"
        else:
            aspect_bdd = aspect

        planete1 = a.get("planete1")
        planete2 = a.get("planete2")

        if planete1 == maitre:
            autre_planete = planete2
        elif planete2 == maitre:
            autre_planete = planete1
        else:
            continue

        for colonne in colonnes:
            logger.debug(
                "Bloc 2 — recherche BDD maître d'angle : %s %s %s | maître réel=%s | colonne=%s",
                type_bdd,
                aspect_bdd,
                autre_planete,
                maitre,
                colonne,
            )

            txt = rechercher_interpretation_aspect(
                type_bdd,
                aspect_bdd,
                autre_planete,
                colonne=colonne,
            ) or ""

            if txt.strip():
                lignes.append(txt.strip())

    return "\n".join(dict.fromkeys(lignes))

def bdd_maitre_angle(
    d: dict,
    type_bdd: str,
    maitre: str,
    colonnes: list[str],
) -> str:
    theme = d["theme"]
    placement = (theme.get("planetes", {}) or {}).get(maitre, {}) or {}

    signe = placement.get("signe")
    maison = placement.get("maison")

    ligne_signe = None
    morceaux = []

    def ajouter_colonnes(
        ligne: dict | None,
        donnee: str,
        valeur: str,
    ) -> None:
        if not ligne:
            return

        for colonne in colonnes:
            texte = ligne.get(colonne)

            if isinstance(texte, str) and texte.strip():
                morceaux.append(
                    f"[TYPE={type_bdd} | DONNEE={donnee} | "
                    f"VALEUR={valeur} | COLONNE={colonne}]\n"
                    f"{texte.strip()}"
                )

    if signe:
        ligne_signe = rechercher_ligne_bdd(
            astre=type_bdd,
            donnee="signe",
            valeur=signe,
            fichier="LLM_bdd_astro_placements.csv",
        )

        ajouter_colonnes(
            ligne_signe,
            donnee="signe",
            valeur=str(signe),
        )

    if maison:
        ligne_maison = rechercher_ligne_bdd(
            astre=type_bdd,
            donnee="maison",
            valeur=str(maison),
            fichier="LLM_bdd_astro_placements.csv",
        )

        ajouter_colonnes(
            ligne_maison,
            donnee="maison",
            valeur=str(maison),
        )


    return "\n".join(dict.fromkeys(morceaux))

def flags_planete(theme: dict, planete: str, role: str) -> list[str]:
    """Notes interception / rétrogradation pour une planète."""
    out = []
    if _est_retrograde(theme, planete):
        out.append(f"{planete} ({role}) rétrograde : fonction intériorisée ou difficile à lire.")
    if _est_intercepte(theme, planete):
        out.append(f"{planete} ({role}) intercepté : difficile à intégrer ou à poser clairement.")
    return out

def interpretation_etat_maitre_angle(
    theme: dict,
    planete: str,
    maison: int,
    cote: str,
) -> list[str]:
    """
    Interprète l'état rétrograde ou intercepté du maître
    de l'angle représentant le pôle mère ou le pôle père.

    `cote` doit valoir :
    - "mere"
    - "pere"

    Le sens dépend ici du rôle parental attribué à l'angle,
    et non du numéro de maison pris isolément.
    """
    lignes = []

    if cote == "mere":
        parent = "la mère"
        relation = (
            "le lien maternel, le maternage reçu et la manière "
            "dont la sécurité affective a été transmise"
        )

        texte_retrograde = (
            f"{planete}, maître de la Maison {maison} représentant ici "
            f"le pôle mère, est rétrograde : la relation à {parent} a pu "
            "être difficile à comprendre, vécue de manière intérieure, "
            "décalée ou ambivalente. Certains éléments du lien maternel "
            "ont pu demander du temps avant d'être compris ou intégrés."
        )

        texte_interception = (
            f"{planete}, maître de la Maison {maison} représentant ici "
            f"le pôle mère, est intercepté : la relation à {parent} a pu "
            "être compliquée, distante ou difficile à ressentir clairement. "
            f"Les thèmes liés à {relation} ont pu rester difficiles à nommer "
            "ou à intégrer consciemment."
        )

    elif cote == "pere":
        parent = "le père"
        relation = (
            "la reconnaissance, l'encouragement, l'autorité "
            "et la construction du sentiment de légitimité"
        )

        texte_retrograde = (
            f"{planete}, maître de la Maison {maison} représentant ici "
            f"le pôle père, est rétrograde : la relation à {parent} a pu "
            "être difficile à comprendre, vécue de manière intérieure, "
            "décalée ou ambivalente. La reconnaissance ou les repères transmis "
            "ont pu demander du temps avant d'être compris ou intégrés."
        )

        texte_interception = (
            f"{planete}, maître de la Maison {maison} représentant ici "
            f"le pôle père, est intercepté : la relation à {parent} a pu "
            "être compliquée, distante ou difficile à cerner. "
            f"Les thèmes liés à {relation} ont pu être peu accessibles, "
            "peu exprimés ou difficiles à intégrer consciemment."
        )

    else:
        logger.warning(
            "Bloc 2: rôle parental inconnu '%s' pour le maître %s",
            cote,
            planete,
        )
        return lignes
    
    retrogradation_retenue = False

    if _est_retrograde(theme, planete):

        # Uranus / Neptune / Pluton : seulement si la rétrogradation
        # est réellement pertinente pour ce bloc.
        if planete in {"Uranus", "Neptune", "Pluton"}:
            if retrogradation_lente_pertinente(
                theme,
                planete,
                maisons_cibles={4, 10},
                planetes_personnelles={
                    "Lune",
                    "Soleil",
                    "Saturne",
                },
            ):
                lignes.append(texte_retrograde)
                retrogradation_retenue = True
        else:
            lignes.append(texte_retrograde)
            retrogradation_retenue = True

    if _est_intercepte(theme, planete):
        lignes.append(texte_interception)

    return lignes


# ------------------------------------------------------------
# Collecte unique des données
# ------------------------------------------------------------

def collecter_donnees_bloc2(theme: dict, contexte: dict) -> dict:
    """
    Cœur du Bloc 2. Retourne une structure unique et propre.
    Remplace les ~15 fonctions build_* de l'ancien fichier.
    """
    planetes = theme.get("planetes", {}) or {}
    aspects = _normalize_aspects(theme.get("aspects", []))
    aspects = marquer_conjonctions_dissociees(aspects, planetes)
    aspects = _exclure_points_mineurs(aspects)
    aspects = exclure_aspects_aux_noeuds(aspects)
    # print("\n=== ASPECTS NORMALISÉS ===")
    # for a in aspects:
    #     print(
    #         a.get("planete1"),
    #         a.get("aspect"),
    #         a.get("planete2"),
    #         "orbe",
    #         a.get("orbe"),
    #     )

    genre_brut = str(
        contexte.get("genre") or "femme"
    ).strip().casefold()

    genre = (
        "femme"
        if genre_brut in {"femme", "female", "f", "woman"}
        else "homme"
    )

    # Pôles parentaux selon le genre (logique conservée).
    if genre == "femme":
        maison_mere, maison_pere = 4, 10
    else:
        maison_mere, maison_pere = 10, 4

    def maitres(maison: int) -> list[str]:
        m = get_maitres_maison(theme, maison)
        m += [x for x in maitres_interceptes_dans_maison(theme, maison) if x not in m]
        return m
    return {
        "planetes": planetes,
        "aspects": aspects,
        "genre": genre,
        # Partie 1 — émotions / fondations
        "lune": planetes.get("Lune", {}),
        "nakshatra": _extract_nakshatra_lune(contexte),
        "lune_aspects": aspects_structurants(
            aspects,
            "Lune",
            top=4,
            max_orbe_dur=8.0,
        ),
        "maison4_signe": get_maison(theme, 4).get("signe", "N/A"),
        "maison4_planetes": fmt_planetes_en_maison(theme, 4),
        "maison4_planetes_liste": planetes_en_maison(theme, 4),
        "maitres_maison4": maitres(4),
        # Partie 2 — famille
        "maison_mere": maison_mere,
        "maison_pere": maison_pere,
        "maitres_mere": maitres(maison_mere),
        "maitres_pere": maitres(maison_pere),
        "soleil": planetes.get("Soleil", {}),
        "saturne": planetes.get("Saturne", {}),
        "mercure": planetes.get("Mercure", {}),
        "soleil_aspects": aspects_structurants(
            aspects,
            "Soleil",
            top=4,
            max_orbe_dur=8.0,
        ),
        "saturne_aspects": aspects_structurants(aspects, "Saturne", top=4),
        "mercure_aspects": aspects_structurants(aspects, "Mercure", top=4),
        "configurations_majeures": (
            contexte.get("configurations_majeures")
            or []
        ),
        "interceptions": build_interceptions_famille(theme, aspects),
        "base": contexte.get("base_interpretations", {}) or {},
        "theme": theme,
    }

def formater_configurations_ciblees(
    configurations: list[dict],
    corps_cibles: set[str],
) -> str:
    """
    Conserve les configurations qui impliquent au moins
    un des corps astrologiques utiles à la section.
    """
    corps_cibles = {
        corps
        for corps in corps_cibles
        if corps
    }

    configurations_retenues = [
        configuration
        for configuration in configurations
        if corps_cibles.intersection(
            configuration.get("planetes", [])
        )
    ]

    return formater_configurations_majeures(
        configurations_retenues
    )

# ------------------------------------------------------------
# Construction des dossiers (texte injecté au prompt)
# ------------------------------------------------------------

def formater_entree_bdd(
    titre: str,
    texte: str,
) -> str:
    """
    Rend une entrée BDD facilement repérable dans le prompt et les logs.

    Exemple :
    [ENTRÉE BDD]
    ASPECT : Neptune opposition Mars

    DÉFINITION :
    Comportement maternel colérique, impulsif.
    [/ENTRÉE BDD]
    """
    if not texte:
        return ""

    return (
        "\n"
        "────────────────────────────────────────\n"
        "[ENTRÉE BDD]\n"
        f"{titre}\n\n"
        "DÉFINITION :\n"
        f"{texte.strip()}\n"
        "[/ENTRÉE BDD]\n"
        "────────────────────────────────────────"
    )

def dossier_identite(d: dict) -> str:
    planetes = d["planetes"]
    lune = d["lune"]
    signe = lune.get("signe", "N/A")
    maison = lune.get("maison", "N/A")
    dignite = dignite_planete("Lune", signe)
    dignite_txt = f" — dignité : {dignite}" if dignite else ""

    parts = [
        "ÉMOTIONS / BESOINS / SÉCURITÉ INTÉRIEURE",
        f"Lune : {signe} — Maison {maison}{dignite_txt}",
    ]

    if d["lune_aspects"]:
        parts.append("Aspects structurants de la Lune (prioritaires sur le signe) :")
        parts.append(fmt_aspects(d["lune_aspects"], planetes))
        bdd = bdd_aspects(
            d["lune_aspects"],
            colonne="IDENTITE",
            max_blocs=4,
        )
        if bdd:
            parts.append("Interprétation BDD des aspects :")
            parts.append(bdd)

    parts.append(f"Nakshatra lunaire (texture intérieure) : {d['nakshatra']}")

    txt_lune_interception = formater_interpretation_etat_bdd(
        d["base"],
        "Lune",
        "interception",
        colonnes=["IDENTITE"],
    )

    if txt_lune_interception:
        parts.append("BDD Lune interceptée / identité émotionnelle :")
        parts.append(txt_lune_interception)

    bdd_lune = formater_interpretation_planete_bdd(d["base"], "Lune", colonnes=["IDENTITE"]) or ""
    if bdd_lune:
        parts.append("BDD Lune / identité émotionnelle :")
        parts.append(bdd_lune)

    # Maison IV comme socle de sécurité (angle "fondations", pas "mère").
    parts.append(f"\nFondations / socle de sécurité — Maison IV : {d['maison4_signe']}")
    if d["maison4_planetes"] != "Aucune":
        parts.append(f"Planètes en Maison IV : {d['maison4_planetes']}")

    for planete in d["maison4_planetes_liste"]:
        txt = formater_interpretation_planete_bdd(
            d["base"],
            planete,
            colonnes=["IDENTITE"],
        )

        if txt:
            parts.append(f"BDD {planete} en Maison IV / fondations :")
            parts.append(txt)

    # Maître de IV : souvent c'est lui qui raconte les fondations (IV vide mais maître conjoint Pluton).
    for i, m in enumerate(d["maitres_maison4"]):
        role = "principal" if i == 0 else "secondaire"
        parts.append(f"Maître {role} de IV : {_placement(d['theme'], m)}")
        asp = aspects_structurants(d["aspects"], m, top=2)
        if asp:
            parts.append(fmt_aspects(asp, planetes))

    for m in d["maitres_maison4"]:
        bdd_m4 = bdd_maitre_angle(
            d,
            "maitre_fdc",
            m,
            colonnes=["FAMILLE"],
        )

        if bdd_m4:
            parts.append(
                f"BDD maître de IV ({m}) / fondations :"
            )
            parts.append(bdd_m4)

    return "\n\n".join(parts)

def interpretation_planete_parent_avec_fallback(
    base,
    planete: str,
    cote: str,
) -> str:
    """
    Recherche d'abord l'interprétation spécifique au parent :
    - MA_MERE pour le pôle mère
    - MA_PERE pour le pôle père

    Si aucune interprétation n'existe, utilise FAMILLE en secours.
    """
    colonne_parent = "MA_MERE" if cote == "mere" else "MA_PERE"

    texte = formater_interpretation_planete_bdd(
        base,
        planete,
        colonnes=[colonne_parent],
    )

    if texte:
        return texte

    return formater_interpretation_planete_bdd(
        base,
        planete,
        colonnes=["FAMILLE"],
    ) or ""


def entree_bdd(
    type_entree: str,
    cle: str,
    colonne: str,
    texte: str,
) -> str:
    if not texte:
        return ""

    return (
        "\n"
        "────────────────────────────────────────\n"
        f"{type_entree.upper()} : {cle}\n"
        f"BDD : {colonne}\n\n"
        f"{texte.strip()}\n"
        "────────────────────────────────────────\n"
    )

def dossier_pole(d: dict, cote: str) -> str:
    """cote = 'mere' ou 'pere'. Logique unifiée pour les deux pôles."""
    theme = d["theme"]
    planetes = d["planetes"]

    if cote == "mere":
        maison = d["maison_mere"]
        maitres = d["maitres_mere"]
        titre = "PÔLE MÈRE — AU CONDITIONNEL"
        astre, astre_aspects, astre_label = "Lune", d["lune_aspects"], "Lune / maternage reçu"
    else:
        maison = d["maison_pere"]
        maitres = d["maitres_pere"]
        titre = "PÔLE PÈRE / VALIDATION IDENTITAIRE — AU CONDITIONNEL"
        astre, astre_aspects, astre_label = "Soleil", d["soleil_aspects"], "Soleil / validation identitaire"

    signe_angle = get_maison(theme, maison).get("signe", "N/A")
    parts = [titre]

    colonne_parent = (
        "MA_MERE"
        if cote == "mere"
        else "MA_PERE"
    )

    # Significateur parental principal traité avant les maîtres de l'angle
    # Lune pour le maternage reçu / Soleil pour la validation identitaire
    parts.append(f"\n{astre_label} : {_placement(theme, astre)}")

    if astre_aspects:
        conjonctions, tensions, fluides = classer_aspects_famille(
            astre_aspects,
        )

        aspects_principaux = conjonctions + tensions

        if conjonctions:
            parts.append("Conjonctions structurantes :")
            parts.append(fmt_aspects(conjonctions, planetes))

        if tensions:
            parts.append("Aspects de tension structurants :")
            parts.append(fmt_aspects(tensions, planetes))

        if aspects_principaux:
            bdd_principale = bdd_aspects(
                aspects_principaux,
                colonne=colonne_parent,
                max_blocs=3,
            )

            if bdd_principale:
                parts.append(
                    "BDD des aspects structurants :"
                )
                parts.append(bdd_principale)

        if fluides:
            parts.append(
                "Nuance fluide secondaire — ressource ou contrepoids :"
            )
            parts.append(fmt_aspects(fluides[:1], planetes))

            bdd_fluide = bdd_aspects(
                fluides[:1],
                colonne=colonne_parent,
                max_blocs=1,
            )

            if bdd_fluide:
                parts.append(
                    "BDD de la nuance fluide secondaire :"
                )
                parts.append(bdd_fluide)

    # Placement classique de la Lune ou du Soleil
    bdd_astre = formater_interpretation_planete_bdd(
        d["base"],
        astre,
        colonnes=[colonne_parent],
    ) or ""

    if bdd_astre:
        parts.append(bdd_astre)

    
    # Interception éventuelle de la Lune ou du Soleil
    txt_astre_interception = (
        formater_interpretation_etat_bdd(
            d["base"],
            astre,
            "interception",
            colonnes=[colonne_parent],
        )
    )

    if txt_astre_interception:
        parts.append(
            f"BDD {astre} intercepté / rôle parental :"
        )
        parts.append(txt_astre_interception)
        
    # Saturne en plus pour le pôle père
    if cote == "pere":
        sat_dignite = dignite_planete(
            "Saturne",
            d["saturne"].get("signe", ""),
        )
        sat_txt = (
            f" — dignité : {sat_dignite}"
            if sat_dignite
            else ""
        )

        parts.append(
            f"\nSaturne / cadre / autorité : "
            f"{_placement(theme, 'Saturne')}{sat_txt}"
        )

        if d["saturne_aspects"]:
            sat_conjonctions, sat_tensions, sat_fluides = (
                classer_aspects_famille(
                    d["saturne_aspects"],
                )
            )

            sat_principaux = (
                sat_conjonctions
                + sat_tensions
            )

            if sat_conjonctions:
                parts.append(
                    "Conjonctions structurantes de Saturne :"
                )
                parts.append(
                    fmt_aspects(
                        sat_conjonctions,
                        planetes,
                    )
                )

            if sat_tensions:
                parts.append(
                    "Aspects de tension structurants de Saturne :"
                )
                parts.append(
                    fmt_aspects(
                        sat_tensions,
                        planetes,
                    )
                )

            if sat_principaux:
                bdd_sat_principale = bdd_aspects(
                    sat_principaux,
                    colonne="MA_PERE",
                    max_blocs=2,
                )

                if bdd_sat_principale:
                    parts.append(
                        "BDD des aspects structurants de Saturne :"
                    )
                    parts.append(
                        bdd_sat_principale
                    )

            if sat_fluides:
                parts.append(
                    "Nuance fluide secondaire de Saturne :"
                )
                parts.append(
                    fmt_aspects(
                        sat_fluides[:1],
                        planetes,
                    )
                )

                bdd_sat_fluide = bdd_aspects(
                    sat_fluides[:1],
                    colonne="MA_PERE",
                    max_blocs=1,
                )

                if bdd_sat_fluide:
                    parts.append(
                        "BDD de la nuance fluide de Saturne :"
                    )
                    parts.append(
                        bdd_sat_fluide
                    )

        bdd_sat = formater_interpretation_planete_bdd(
            d["base"],
            "Saturne",
            colonnes=["MA_PERE"],
        ) or ""

        if bdd_sat:
            parts.append(bdd_sat)

        for etat_saturne in (
            "retrograde",
            "interception",
        ):
            texte_etat_saturne = (
                formater_interpretation_etat_bdd(
                    d["base"],
                    "Saturne",
                    etat_saturne,
                    colonnes=["MA_PERE"],
                )
            )

            if texte_etat_saturne:
                parts.append(
                    texte_etat_saturne
                )

    parts.append(
        f"Angle utilisé : Maison {maison} en {signe_angle}"
    )

    planetes_angle = fmt_planetes_en_maison(
        theme,
        maison,
    )

    if planetes_angle != "Aucune":
        parts.append(
            f"Planètes dans cet angle : {planetes_angle}"
        )

    for planete in planetes_en_maison(theme, maison):
        txt = interpretation_planete_parent_avec_fallback(
            d["base"],
            planete,
            cote,
        )

        if txt:

            parts.append(
                f"BDD {planete} en Maison {maison} / "
                f"{'pôle maternel' if cote == 'mere' else 'pôle paternel'} :"
            )
            parts.append(txt)


    # Maîtres de l'angle + leurs aspects structurants
    for i, m in enumerate(maitres):
        role = "principal" if i == 0 else "secondaire"
        parts.append(f"Maître {role} : {_placement(theme, m)}")

        type_bdd = "maitre_fdc" if maison == 4 else "maitre_mdc"
        colonne_parent = "MA_MERE" if cote == "mere" else "MA_PERE"

        # Placement du maître : signe + maison
        bdd_placement_maitre = bdd_maitre_angle(
            d,
            type_bdd=type_bdd,
            maitre=m,
            colonnes=[colonne_parent],
        )

        if bdd_placement_maitre:
            parts.append(
                f"BDD {type_bdd} ({m}) / "
                f"{'pôle maternel' if cote == 'mere' else 'pôle paternel'} :"
            )
            parts.append(bdd_placement_maitre)

        # Aspects du maître : indépendants du placement BDD
        asp = aspects_structurants(
            d["aspects"],
            m,
            top=2,
        )

        if asp:
            maitre_conjonctions, maitre_tensions, maitre_fluides = (
                classer_aspects_famille(asp)
            )

            maitre_principaux = (
                maitre_conjonctions
                + maitre_tensions
            )

            if maitre_conjonctions:
                parts.append(
                    "Conjonctions structurantes du maître d’angle :"
                )
                parts.append(
                    fmt_aspects(
                        maitre_conjonctions,
                        planetes,
                    )
                )

            if maitre_tensions:
                parts.append(
                    "Aspects de tension structurants du maître d’angle :"
                )
                parts.append(
                    fmt_aspects(
                        maitre_tensions,
                        planetes,
                    )
                )

            if maitre_principaux:
                bdd_maitre_principale = (
                    bdd_aspects_maitre_angle(
                        maitre_principaux,
                        type_bdd=type_bdd,
                        maitre=m,
                        colonnes=[colonne_parent],
                    )
                )

                if not bdd_maitre_principale:
                    bdd_maitre_principale = (
                        bdd_aspects_maitre_angle(
                            maitre_principaux,
                            type_bdd=type_bdd,
                            maitre=m,
                            colonnes=["FAMILLE"],
                        )
                    )

                if bdd_maitre_principale:
                    parts.append(
                        bdd_maitre_principale
                    )

            if maitre_fluides:
                parts.append(
                    "Nuance fluide secondaire du maître d’angle :"
                )
                parts.append(
                    fmt_aspects(
                        maitre_fluides[:1],
                        planetes,
                    )
                )

        for texte_etat in interpretation_etat_maitre_angle(
            theme,
            m,
            maison,
            cote,
        ):
            parts.append(texte_etat)

    return "\n".join(parts)

def dossier_place_enfant(d: dict) -> str:
    """
    Rassemble les informations liées à Mercure pour décrire
    l’enfant petit dans la dynamique familiale, quel que soit son sexe.

    Mercure représente ici :
    - la manière dont l’enfant observe et comprend son environnement ;
    - sa façon de s’adapter au fonctionnement familial ;
    - la place qu’il prend spontanément ;
    - sa mobilité, sa curiosité et sa manière d’apprendre ;
    - sa façon de se rendre visible, utile, discret ou insaisissable ;
    - sa parole comme une manifestation parmi d’autres.

    Cette section ne décrit pas l’intelligence ou la communication adulte.
"""
    parts = [
        "ENFANT PETIT DANS LA DYNAMIQUE FAMILIALE — AU CONDITIONNEL",
        (
            "Mercure représente ici l’enfant petit, quel que soit son sexe. "
            "Décris la manière dont il observe son environnement, comprend les règles "
            "familiales, s’adapte, apprend et prend spontanément sa place. Montre s’il "
            "cherche à se rendre visible, utile, discret, mobile ou insaisissable selon "
            "son placement et ses aspects. La parole n’est qu’une manifestation parmi "
            "d’autres. Ne fais pas une description générale de l’intelligence ou de "
            "la communication adulte."
        ),
    ]

    # Mercure en signe et en maison
    bdd_mercure = formater_interpretation_planete_bdd(
        d["base"],
        "Mercure",
        colonnes=["FAMILLE"],
    ) or ""

    if bdd_mercure:
        parts.append("BDD Mercure / place de l’enfant :")
        parts.append(bdd_mercure)

    # Aspects structurants de Mercure
    if d["mercure_aspects"]:
        parts.append("Aspects structurants de Mercure :")
        parts.append(
            fmt_aspects(
                d["mercure_aspects"],
                d["planetes"],
            )
        )

        bdd_aspects_mercure = bdd_aspects(
            d["mercure_aspects"],
            colonne="FAMILLE",
            max_blocs=3,
        )

        if bdd_aspects_mercure:
            parts.append("BDD des aspects de Mercure :")
            parts.append(bdd_aspects_mercure)

        # Mercure rétrograde
    txt_mercure_retro = formater_interpretation_etat_bdd(
        d["base"],
        "Mercure",
        "retrograde",
        colonnes=["FAMILLE"],
    )

    if txt_mercure_retro:
        parts.append("BDD Mercure rétrograde / place de l’enfant :")
        parts.append(txt_mercure_retro)

    # Mercure intercepté
    txt_mercure_interception = formater_interpretation_etat_bdd(
        d["base"],
        "Mercure",
        "interception",
        colonnes=["FAMILLE"],
    )

    if txt_mercure_interception:
        parts.append("BDD Mercure intercepté / place de l’enfant :")
        parts.append(txt_mercure_interception)

    # Dignité éventuelle de Mercure
    for etat in ["domicile", "exalté", "exil", "chute"]:
        txt_dignite = formater_interpretation_etat_bdd(
            d["base"],
            "Mercure",
            etat,
            colonnes=["FAMILLE"],
        )

        if txt_dignite:
            parts.append(f"BDD Mercure {etat} / place de l’enfant :")
            parts.append(txt_dignite)


    return "\n\n".join(parts)


# ------------------------------------------------------------
# Prompts système
# ------------------------------------------------------------

SYSTEM_IDENTITE = dedent("""
Tu es une astrologue directe, psychologique, avec humour et une pointe de sarcasme.
Tu parles directement à la personne en la tutoyant.

Tu écris uniquement sur le monde intérieur : émotions, besoins, sécurité affective,
réactions instinctives, mécanismes de protection, vulnérabilités.
La Maison IV est traitée ici comme socle de sécurité intérieure, pas comme la mère.

Hiérarchie absolue :
1. Une configuration majeure impliquant la Lune, une planète de Maison IV
   ou son maître décrit une structure émotionnelle globale. Interprète d’abord
   son fonctionnement d’ensemble, uniquement sous l’angle des émotions,
   des besoins et de la sécurité intérieure.

   Les aspects à la Lune (conjonction > dur > fluide) priment toujours sur
   le signe. Si plusieurs conjonctions forment un même noyau autour de la Lune,
   interprète-les comme une seule structure émotionnelle.

   Une conjonction indiquée comme « dissociée » n'est pas une conjonction
   classique : utilise impérativement l'interprétation « conjonction_dissociee »
   fournie dans la BDD et tiens compte des deux signes différents.

   Lorsqu’un aspect appartient déjà à une configuration ou à un noyau conjoint,
   ne le redéveloppe pas séparément. Utilise-le seulement pour préciser
   la dynamique émotionnelle de l’ensemble.
2. La maison lunaire décrit le terrain d'expression émotionnelle.
3. Le signe nuance le style, sans jamais contredire un aspect fort.
4. Interceptions / rétrogradations = fonction émotionnelle empêchée ou intériorisée.
5. Le nakshatra est une texture complémentaire : une phrase maximum.
   Il ne contredit jamais la Lune tropicale et n’autorise pas à introduire d’autres concepts védiques dans cette section.

Interdictions :
- Ne parle ni de la mère, ni du père, ni de l'enfance comme récit familial.
- N'invente aucun événement.
- Pas de titres, pas de listes, pas de coaching générique.
- Pas de "thème fascinant", "belle invitation à", "cocktail explosif".

Écris 4 à 5 paragraphes continus. Développe concrètement la fonction de chaque
aspect lunaire retenu avant de terminer sur la Maison IV comme socle de sécurité.

IMPORTANT — MÉMOIRE INTERNE
À la toute fin de ta réponse, ajoute exactement ce bloc :

<resume_developpe>
...
</resume_developpe>

Dans cette balise, écris 2 à 3 phrases courtes résumant uniquement ce que tu as réellement développé dans ton analyse.

- le fonctionnement principal décrit ;
- la tension ou le paradoxe principal mis en évidence.

Ne cite aucun élément que tu n’as pas réellement développé dans le texte.
N’ajoute aucun conseil.
""").strip()

SYSTEM_FAMILLE = dedent("""
Tu es astrologue — directe, lucide, psychologique, un peu sarcastique si le contexte s'y prête, mais jamais caricaturale.
Tu parles directement à la personne en la tutoyant. Tu ne parles pas d'elle : tu lui parles.
Tu écris une lecture incarnée, pas un catalogue de placements.

A développer dans le Bloc 2
1. Racines / ambiance familiale : Maison IV, maître de IV, planètes en IV. Ne confonds pas Maison IV et mère.
2. Dynamique familiale : hypothèses au conditionnel, jamais certitudes biographiques.
3. Pôle mère : maître de l'angle mère = comportement général / manière d'être ; Lune = maternage reçu.
4. Pôle père : maître de l'angle père = comportement général / manière d'être ; Soleil = validation identitaire ; Saturne = cadre, autorité ou carence.
5. Lune Noire / Chiron seulement si les données les indiquent.


Hiérarchie absolue :
1. Conjonctions > aspects durs > signes. Un signe seul ne contredit jamais un aspect dur majeur.
Une conjonction indiquée comme « dissociée » doit impérativement être interprétée
à partir de l'entrée BDD « conjonction_dissociee » et des deux signes différents,
et non comme une conjonction classique.
Les aspects fluides sont des nuances ou des ressources secondaires : ils ne construisent jamais à eux seuls le portrait d’un parent et ne contredisent pas les axes prioritaires.
2. Si opposition, conjonction ou carré implique la Lune, le Soleil ou un maître d'angle : cet aspect EST la structure psychologique dominante. Le premier paragraphe part de cette tension, jamais du signe.
3. Interceptions et rétrogradations = fonction empêchée ou intériorisée.
3b. Une interception sur l'axe IV/X ou impliquant les maîtres des pôles parentaux doit être considérée comme un marqueur structurant du récit familial dès le début de l'analyse.
4. Dignités, chutes, exils = nuances de qualité, pas de structure.

Exemple : Soleil Capricorne conjoint Neptune M8 → ne décris pas un père solide. Pars de Neptune M8 : flou, silence, non-dits, validation impossible à saisir.

Interceptions :
- Traiter explicitement si mentionnées.
- Nommer signes interceptés, maisons concernées, maîtres impliqués.
- Expliquer concrètement ce que l'interception bloque, pas juste "difficulté à articuler".

Contraintes absolues :
- Ne pas redévelopper l'identité émotionnelle — elle a déjà été traitée. La Lune intervient ici uniquement comme fonction de maternage reçu.
- Le pôle père doit être traité avec autant de développement que le pôle mère. Ce sont les deux qui construisent l'identité globale.

⚠️⚠️⚠️⚠️⚠️

À partir de l’ensemble des données, construis une lecture familiale croisée.
Ne suis pas l’ordre des dossiers et ne commente pas les placements successivement. 
PAS DE LISTING D'ASPECTS à la suite des uns des autres.
Identifie d’abord la dynamique dominante, puis montre comment les deux parents
et la place de l’enfant participent au même système.

La Lune décrit d’abord le maternage reçu ; le maître de l’angle maternel vient ensuite nuancer la manière d’être de la mère.
Le Soleil et Saturne décrivent d’abord le pôle paternel ; le maître de l’angle paternel vient ensuite nuancer la manière d’être du père.

Les données BDD sont des possibilités à confronter, pas des paragraphes à restituer. Regroupe les indices convergents et écarte les manifestations
qui contredisent le portrait dominant.

Écris 5 à 6 paragraphes continus, entre 850 et 1 050 mots, sans titres,
sans listes et sans Markdown.

  Ne jamais escamoter l'un au profit de l'autre.
- Ne jamais commencer par le signe si un aspect dur majeur implique le Soleil ou un maître d'angle.
- Un maître gouverne depuis sa position réelle, jamais depuis la maison gouvernée.
- Distingue toujours l’empreinte psychique d’un parent de sa présence concrète :
  une figure centrale dans la construction identitaire peut avoir été physiquement absente.
- Les textes BDD proposent plusieurs manifestations possibles, non cumulatives.
  Conserve seulement celles qui forment un portrait cohérent avec les significateurs dominants.
- N'invente aucun placement, aspect, interception, rétrogradation.
- Pas de verdicts biographiques, pas de coaching générique.
- Pas de bullet points dans le texte final.
- AUCUN MARKDOWN 

IMPORTANT — MÉMOIRE INTERNE

À la toute fin de ta réponse, ajoute exactement cette balise :

<resume_developpe>
...
</resume_developpe>

Dans cette balise, écris deux à trois phrases courtes résumant uniquement ce
qui a réellement été développé dans l'analyse :
- le fonctionnement familial principal ;
- la tension ou le paradoxe principal mis en évidence.

Ne cite aucun élément qui n'a pas été développé dans le texte. N'ajoute aucun
conseil, aucune nouvelle interprétation ni aucune formule adressée à la personne.

""").strip()


# ------------------------------------------------------------
# Fonctions principales
# ------------------------------------------------------------

def generer_bloc_2_identite_v2(contexte: Dict[str, Any], max_tokens: int = 1800) -> str:
    theme = contexte.get("theme") or contexte.get("data_theme")
    if not theme:
        return "❌ Contexte invalide."

    d = collecter_donnees_bloc2(theme, contexte)


    corps_emotionnels = {
        "Lune",
        *d["maison4_planetes_liste"],
        *d["maitres_maison4"],
    }

    configurations_identite_str = (
        formater_configurations_ciblees(
            d["configurations_majeures"],
            corps_emotionnels,
        )
    )
    
    genre_txt = (
        "Accords grammaticaux : féminin. Utilise uniquement le féminin classique. "
        "N'utilise jamais l'écriture inclusive : pas de aimé·e, fort·e, né·e, etc."
        if d["genre"] == "femme"
        else
        "Accords grammaticaux : masculin. Utilise uniquement le masculin classique. "
        "N'utilise jamais l'écriture inclusive : pas de aimé·e, fort·e, né·e, etc."
    )
    prompt = dedent(f"""
    {genre_txt}
    Tu analyses uniquement le monde émotionnel et l'identité émotionnelle.

    ## Dossier
    {dossier_identite(d)}

    ## Configurations liées au monde émotionnel
    {configurations_identite_str}

    ## Placements de référence
    {_placements_compact(d["planetes"])}

    Commence par les aspects lunaires s’ils existent, puis articule la maison et le signe tropical. Mentionne le nakshatra en une phrase maximum, uniquement comme texture complémentaire.
    Termine sur la Maison IV comme socle de sécurité intérieure.
    Ne parle jamais du père, de la mère ou de l'enfance.
    
    """).strip()

    #return ask_llm(SYSTEM_IDENTITE + "\n\n" + prompt, max_tokens=max_tokens, temperature=0.85)

    reponse = ask_llm(
        SYSTEM_IDENTITE + "\n\n" + prompt,
        max_tokens=max_tokens,
        temperature=0.85,
    )

    texte, resume = extraire_resume_developpe(reponse)

    contexte["resume_bloc2_identite"] = resume

    return texte


def generer_bloc_2_famille_v2(contexte: Dict[str, Any], max_tokens: int = 2600) -> str:
    theme = contexte.get("theme") or contexte.get("data_theme")
    if not theme:
        return "❌ Contexte invalide."

    d = collecter_donnees_bloc2(theme, contexte)

    cibles_parentales = {
        "Lune",
        "Soleil",
        "Saturne",
        *d["maitres_mere"],
        *d["maitres_pere"],
    }

    aspects_prioritaires = aspects_prioritaires_famille(
        d["aspects"],
        cibles=cibles_parentales,
    )

    priorites_famille_txt = fmt_aspects(
        aspects_prioritaires,
        d["planetes"],
    )

    corps_familiaux = {
        "Lune",
        "Soleil",
        "Saturne",
        "Mercure",
        "MC",
        *d["maitres_mere"],
        *d["maitres_pere"],
        *planetes_en_maison(theme, 4),
        *planetes_en_maison(theme, 10),
    }

    configurations_famille_str = (
        formater_configurations_ciblees(
            d["configurations_majeures"],
            corps_familiaux,
        )
    )

  

    genre_txt = (
        "C'est une femme : formulations au féminin."
        if d["genre"] == "femme"
        else "C'est un homme : formulations au masculin."
    )

    prompt = dedent(f"""
    {genre_txt}

    L'identité émotionnelle a déjà été traitée. Ne pas la redévelopper.

    ## Axes familiaux prioritaires — colonne vertébrale du récit
    {priorites_famille_txt}

    ## Configurations majeures liées aux racines et aux pôles parentaux
    {configurations_famille_str}

    ## Interceptions
    {d["interceptions"]}

    ## Racines / ambiance familiale
    Maison IV : {d["maison4_signe"]}
    Planètes en Maison IV : {d["maison4_planetes"]}

    Règle commune aux deux pôles : le maître de l’angle décrit la manière
    d’être du parent perçue par l’enfant. Sa maison indique ses préoccupations,
    pas nécessairement le rôle concret qu’il remplissait dans la famille.

    ## {dossier_pole(d, "mere")}

    ## {dossier_pole(d, "pere")}

    ## {dossier_place_enfant(d)}

    ## Contexte global du thème — pour relier et vérifier les données, sans commenter chaque placement
    {_placements_compact(d["planetes"])}


    La section « L’enfant petit dans la dynamique familiale » doit s’appuyer
    uniquement sur Mercure : signe, maison, aspects, rétrogradation,
    interception et dignité si présente. Mercure représente ici l’enfant petit
    quel que soit son sexe, et pas seulement sa parole.

    Croise les racines, les deux pôles parentaux et la place de l’enfant
    dans une lecture continue. Le père est développé autant que la mère.
    """).strip()

    prompt_complet = SYSTEM_FAMILLE + "\n\n" + prompt

    with open(
        "prompt_famille_debug.txt",
        "w",
        encoding="utf-8",
    ) as fichier_debug:
        fichier_debug.write(prompt_complet)

    #return ask_llm(SYSTEM_FAMILLE + "\n\n" + prompt, max_tokens=max_tokens, temperature=0.85)
    resultat = ask_llm(
        prompt_complet,
        max_tokens=max_tokens,
        temperature=0.8,
    )

    resultat, resume = extraire_resume_developpe(resultat)

    contexte["resume_bloc2_famille"] = resume
    return resultat
