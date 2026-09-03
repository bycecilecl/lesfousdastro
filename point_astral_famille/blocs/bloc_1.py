from textwrap import dedent
from typing import Dict, List, Optional
import re
import logging

#from utils.llm_client import ask_llm
from point_astral_famille.llm_client import ask_llm
from utils.formatage import formater_positions_planetes
from point_astral_famille.selection_donnees import (
    filtrer_aspects_ascendant,
    filtrer_planetes_maison_occidentale,
    exclure_aspects_aux_noeuds,
    retrogradation_lente_pertinente,
)
from point_astral_famille.poids import filtrer_aspects_par_score
from point_astral_famille.database import (
    formater_interpretation_planete_bdd,
    formater_interpretation_etat_bdd,
    rechercher_interpretation_aspect,
)
from point_astral_famille.calculs_astrologiques import get_maitres_ascendant
from point_astral_famille.configurations_astrologiques import (
    formater_configurations_majeures,
)

logger = logging.getLogger(__name__)


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

def texte_identite_avec_fallback(
    ligne: dict | None,
) -> str:
    """
    Retourne l'interprétation IDENTITE lorsqu'elle est disponible.

    Si IDENTITE est vide ou contient N/A, utilise INTERPRETATION.
    Si aucune des deux colonnes n'est exploitable, retourne une chaîne vide.
    """
    if not ligne:
        return ""

    identite = str(ligne.get("IDENTITE") or "").strip()

    if identite and identite.casefold() not in {"n/a", "na", "n.a."}:
        return identite

    interpretation = str(
        ligne.get("INTERPRETATION") or ""
    ).strip()

    if (
        interpretation
        and interpretation.casefold() not in {"n/a", "na", "n.a."}
    ):
        return interpretation

    return ""

ASPECTS_MAJEURS = {"Conjonction", "Carré", "Opposition", "Trigone", "Sextile"}
ORBE_MAX_ASC = 5.5
ORBE_MAX_KEY = 5.0

POINTS_SECONDAIRES_BLOC1 = {
    "Junon",
    "Juno",
    "Part de Fortune",
    "Point d’Illumination",
    "Point d'Illumination",
    "Point illumination",
    "Rahu",
    "Ketu",
}

def exclure_points_secondaires_bloc1(aspects: list[dict]) -> list[dict]:
    return [
        a for a in aspects
        if a.get("planete1") not in POINTS_SECONDAIRES_BLOC1
        and a.get("planete2") not in POINTS_SECONDAIRES_BLOC1
    ]


def conserver_aspect_chiron(
    aspect: dict,
    maitre_principal: str | None = None,
    second_maitre: str | None = None,
) -> bool:
    """
    Chiron est conservé dans le Bloc 1 uniquement lorsqu'il participe
    directement à la construction de l'identité.

    Conditions :
      - aspect <= 5°
      - Conjonction, Carré ou Opposition uniquement
      - avec Ascendant, Soleil, Lune,
        maître principal ou maître traditionnel.
    """

    p1 = aspect.get("planete1")
    p2 = aspect.get("planete2")

    # Aucun Chiron → on conserve
    if "Chiron" not in (p1, p2):
        return True

    # uniquement aspects majeurs structurants
    if aspect.get("aspect") not in {
        "Conjonction",
        "Carré",
        "Opposition",
    }:
        return False

    try:
        if float(aspect.get("orbe", 99)) > 5:
            return False
    except Exception:
        return False

    autre = p2 if p1 == "Chiron" else p1

    return autre in {
        "Ascendant",
        "Soleil",
        "Lune",
        maitre_principal,
        second_maitre,
    }

def _fmt_aspect(a: Dict) -> str:
    return f"{a['planete1']} {a['aspect']} {a['planete2']} (orbe {a['orbe']}°)"
      

def _is_to(target: str, a: Dict) -> bool:
    return a["planete1"] == target or a["planete2"] == target

def _is_between(p1: str, p2: str, a: Dict) -> bool:
    s = {a["planete1"], a["planete2"]}
    return p1 in s and p2 in s

def _orbe(a: Dict) -> float:
    valeur = a.get("orbe", 99)

    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        logger.warning(
            "Bloc 1 : orbe invalide %r pour l’aspect %s %s %s",
            valeur,
            a.get("planete1"),
            a.get("aspect"),
            a.get("planete2"),
        )
        return 99.0

def _strong(a: Dict, max_orbe: float) -> bool:
    return _orbe(a) <= max_orbe

def _pick(aspects: List[Dict], keep_fn, max_orbe, whitelist=None):
    out = []
    for a in aspects:
        if keep_fn(a) and _strong(a, max_orbe):
            if (whitelist is None) or (a["aspect"] in whitelist):
                out.append(a)
    # trier par orbe croissante
    out.sort(key=_orbe)
    return out

def selectionner_aspects_maitre(
    aspects: List[Dict],
    maitre: str,
    max_autres: int,
) -> List[Dict]:
    """
    Conserve toutes les conjonctions du maître, puis les meilleurs
    autres aspects selon le score psychologique du Bloc 1.
    """
    conjonctions = [
        aspect
        for aspect in aspects
        if aspect.get("aspect") == "Conjonction"
    ]
    conjonctions.sort(key=_orbe)

    autres_aspects = [
        aspect
        for aspect in aspects
        if aspect.get("aspect") != "Conjonction"
    ]

    autres_prioritaires = filtrer_aspects_par_score(
        autres_aspects,
        seuil_min=10,
        maitre_ascendant=maitre,
    )

    return conjonctions + autres_prioritaires[:max_autres]

def planets_in_house(planetes: Dict, house_num: int) -> List[str]:
    out = []
    for nom, obj in planetes.items():
        if nom in ("Ascendant", "MC", "Rahu", "Ketu"):  # adapte si besoin
            continue
        m = obj.get("maison")
        if m == house_num or str(m) == str(house_num):
            out.append(nom)
    return out

def dominante_maison_1(planetes: Dict) -> dict | None:
    """
    Retourne la planète la plus proche de l’Ascendant en Maison I.
    """
    asc = planetes.get("Ascendant")
    if not asc:
        return None

    asc_deg = asc.get("longitude")
    if asc_deg is None:
        return None

    candidates = []

    for nom, obj in planetes.items():

        if nom in ("Ascendant", "MC", "Rahu", "Ketu"):
            continue

        maison = obj.get("maison")

        deg = obj.get("longitude")

        if deg is None:
            continue

        distance = abs(deg - asc_deg)

        if distance > 180:
            distance = 360 - distance

        maison = str(obj.get("maison") or "").strip()

        # On garde :
        # - toutes les planètes en Maison I
        # - les planètes en Maison XII conjointes à l'Ascendant
        if maison != "1":
            if not (maison == "12" and distance <= 5):
                continue

        candidates.append({
            "planete": nom,
            "distance": round(distance, 2),
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["distance"])

    dominante = candidates[0]

    # Une planète de Maison I n’est considérée comme dominante
    # par proximité que si elle se trouve à 10° maximum de l’Ascendant.
    if dominante["distance"] > 10:
        return None

    return dominante


_ROMAN = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12}

def _roman_or_int_to_num(tok: str) -> int | None:
    if not tok: 
        return None
    t = str(tok).strip().upper()
    if t.isdigit():
        try: return int(t)
        except: return None
    return _ROMAN.get(t)


def planets_in_house_from_text(placements_str: str, house_num: int = 1) -> list[str]:
    """
    Fallback ultra simple : détecte les planètes en Maison `house_num` à partir de placements_str.
    Gère :
      - lignes du type "Vénus — Maison I" ou "Vénus en maison 1"
      - "Planètes en Maison I : Vénus, Mars"
    Évite d'inclure les angles (Ascendant/MC/IC/Descendant) et les nœuds.
    """
    if not placements_str:
        return []
    out = set()

    # 1) Lignes individuelles (ex: "Vénus — Maison I" ou "Vénus en maison 1")
    roman = "I" * house_num  # pour 1 -> "I", 2 -> "II", etc. (au cas où)
    pat_line = re.compile(
        rf"^([A-Za-zÉÈÀÂÊÎÔÛÄËÏÖÜÇéèàâêîôûäëïöüç\- ]+?).*?\bmaison\b\s*(?:{roman}|{house_num})\b",
        flags=re.IGNORECASE
    )
    for line in placements_str.splitlines():
        m = pat_line.search(line.strip())
        if m:
            nom = m.group(1).strip(" —:-•")
            nom_low = nom.lower()
            if nom_low not in ("ascendant", "mc", "ic", "descendant", "rahu", "ketu"):
                out.add(nom)

    # 2) Ligne récap (ex: "Planètes en Maison I : Vénus, Mars")
    pat_list = re.compile(
        rf"Planètes?\s+en\s+Maison\s+(?:{roman}|{house_num})\s*[:\-]\s*(.+)",
        flags=re.IGNORECASE
    )
    m2 = pat_list.search(placements_str)
    if m2:
        for p in re.split(r"\s*,\s*", m2.group(1)):
            p = p.strip(" .;:•")
            if p and p.lower() not in ("ascendant", "mc", "ic", "descendant", "rahu", "ketu"):
                out.add(p)

    return sorted(out)

def dignite_planete(planete: str, signe: str) -> str | None:
    dignites = {
        "Soleil": {
            "domicile": ["Lion"],
            "exaltation": ["Bélier"],
            "exil": ["Verseau"],
            "chute": ["Balance"],
        },
        "Lune": {
            "domicile": ["Cancer"],
            "exaltation": ["Taureau"],
            "exil": ["Capricorne"],
            "chute": ["Scorpion"],
        },
        "Mercure": {
            "domicile": ["Gémeaux", "Vierge"],
            "exaltation": ["Vierge"],
            "exil": ["Sagittaire", "Poissons"],
            "chute": ["Poissons"],
        },
        "Vénus": {
            "domicile": ["Taureau", "Balance"],
            "exaltation": ["Poissons"],
            "exil": ["Scorpion", "Bélier"],
            "chute": ["Vierge"],
        },
        "Mars": {
            "domicile": ["Bélier", "Scorpion"],
            "exaltation": ["Capricorne"],
            "exil": ["Balance", "Taureau"],
            "chute": ["Cancer"],
        },
        "Jupiter": {
            "domicile": ["Sagittaire", "Poissons"],
            "exaltation": ["Cancer"],
            "exil": ["Gémeaux", "Vierge"],
            "chute": ["Capricorne"],
        },
        "Saturne": {
            "domicile": ["Capricorne", "Verseau"],
            "exaltation": ["Balance"],
            "exil": ["Cancer", "Lion"],
            "chute": ["Bélier"],
        },
        "Uranus": {
            "domicile": ["Verseau"],
        },
        "Neptune": {
            "domicile": ["Poissons"],
        },
        "Pluton": {
            "domicile": ["Scorpion"],
        },
            }

    if planete not in dignites:
        return None

    for etat, signes in dignites[planete].items():
        if signe in signes:
            return etat

    return None

def planete_est_interceptee(
    theme: dict,
    planete: str | None,
) -> bool:
    """
    Détecte une planète interceptée depuis son placement
    ou depuis la structure globale des interceptions.
    """
    if not planete:
        return False

    placement = (
        theme.get("planetes", {}).get(planete, {})
        or {}
    )

    if (
        placement.get("intercept")
        or placement.get("intercepte")
        or placement.get("intercepté")
    ):
        return True

    interceptions = theme.get("interceptions", {}) or {}

    planetes_interceptees = (
        interceptions.get("planetes")
        or interceptions.get("planètes")
        or []
    )

    if planete in planetes_interceptees:
        return True

    signes_interceptes = (
        interceptions.get("signes")
        or interceptions.get("signes_interceptes")
        or interceptions.get("signes_interceptés")
        or []
    )

    signe_planete = str(
        placement.get("signe") or ""
    ).strip().casefold()

    return bool(
        signe_planete
        and signe_planete
        in {
            str(signe).strip().casefold()
            for signe in signes_interceptes
            if signe
        }
    )

def aspects_entre_planetes_maison1(
    aspects: List[Dict],
    planetes_maison1: List[str],
    max_orbe: float = 5.0,
) -> List[Dict]:
    """
    Détecte les aspects entre planètes présentes en Maison 1.
    Priorité aux conjonctions, carrés et oppositions.
    """
    if not planetes_maison1:
        return []

    planetes_set = set(planetes_maison1)

    aspects_trouves = []

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        aspect = a.get("aspect")

        if p1 in planetes_set and p2 in planetes_set:
            if aspect in {"Conjonction", "Carré", "Opposition"}:
                if _orbe(a) <= max_orbe:
                    aspects_trouves.append(a)

    aspects_trouves.sort(key=_orbe)

    return aspects_trouves

def build_resume_bloc1(theme: Dict, placements_str: str | None = None) -> Dict[str, str]:
    """
    Bloc 1 : Ascendant / Maître d'Ascendant / Maison I / Soleil
    Avec fallback texte pour les planètes en Maison I si le dict 'theme' ne les renseigne pas.
    """
    planetes = theme["planetes"]
    aspects  = theme["aspects"]
    asc = planetes.get("Ascendant", {}) or {}
    asc_sign = asc.get("signe", "N/A")
    asc_deg  = asc.get("degre", "N/A")

    # 1) Conjonctions & aspects vers l’Ascendant
    asc_conj = _pick(aspects, lambda a: _is_to("Ascendant", a), ORBE_MAX_ASC, {"Conjonction"})
    asc_conj = exclure_points_secondaires_bloc1(
        exclure_aspects_aux_noeuds(asc_conj)
    )
    asc_aspects = _pick(aspects, lambda a: _is_to("Ascendant", a), ORBE_MAX_ASC, ASPECTS_MAJEURS)

    # 2) Planètes en Maison I (dict -> puis fallback texte)
    maison1_planetes = planets_in_house(planetes, 1)
    if not maison1_planetes and placements_str:
        maison1_planetes = planets_in_house_from_text(placements_str, 1)

    dominante_1 = dominante_maison_1(planetes)

    # 3) Maître d’Ascendant
    maitre, second_maitre = get_maitres_ascendant(asc_sign)

    asc_conj = [
    aspect for aspect in asc_conj
    if conserver_aspect_chiron(
        aspect,
        maitre_principal=maitre,
        second_maitre=second_maitre,
    )
    ]

    asc_aspects = [
        aspect for aspect in asc_aspects
        if conserver_aspect_chiron(
            aspect,
            maitre_principal=maitre,
            second_maitre=second_maitre,
        )
    ]

    if not maitre:
        logger.warning(
            "Bloc 1: maître d'Ascendant introuvable pour le signe %s",
            asc_sign,
        )
        maitre = "Inconnu"

    maitre_obj = planetes.get(maitre, {}) or {}
    maitre_sign = maitre_obj.get("signe", "N/A")
    maitre_house = maitre_obj.get("maison", "N/A")

    second_maitre_obj = planetes.get(second_maitre, {}) or {} if second_maitre else {}
    second_maitre_sign = second_maitre_obj.get("signe", "N/A")
    second_maitre_house = second_maitre_obj.get("maison", "N/A")

    second_maitre_retro = second_maitre_obj.get(
        "retrograde",
        False,
    )

    # second_maitre_intercept = bool(
    #     second_maitre_obj.get("intercept", False)
    #     or second_maitre_obj.get("intercepte", False)
    #     or second_maitre_obj.get("intercepté", False)
    # )

    second_maitre_intercept = planete_est_interceptee(
        theme,
        second_maitre,
    )

    second_maitre_dignite = (
        dignite_planete(second_maitre, second_maitre_sign)
        if second_maitre
        else None
    )

    etat_second_maitre = []

    if second_maitre_dignite:
        etat_second_maitre.append(second_maitre_dignite)

    if second_maitre_retro:
        etat_second_maitre.append("rétrograde")

    if second_maitre_intercept:
        etat_second_maitre.append("intercepté")

    etat_second_maitre_str = (
        ", ".join(etat_second_maitre)
        if etat_second_maitre
        else "direct"
    )

    maitre_retro = maitre_obj.get("retrograde", False)
    maitre_intercept = planete_est_interceptee(
        theme,
        maitre,
    )
    etat_dignite = dignite_planete(maitre, maitre_sign)

    etat_maitre = []

    if etat_dignite:
        etat_maitre.append(etat_dignite)

    if maitre_retro:
        etat_maitre.append("rétrograde")

    if maitre_intercept:
        etat_maitre.append("intercepté")

    etat_maitre_str = ", ".join(etat_maitre) if etat_maitre else "direct"

    if maitre != "Inconnu":
        aspects_maitre = _pick(
            aspects,
            lambda a: _is_to(maitre, a),
            ORBE_MAX_KEY,
            ASPECTS_MAJEURS,
        )
    else:
        aspects_maitre = []

    if second_maitre:
        aspects_second_maitre = _pick(
            aspects,
            lambda a: _is_to(second_maitre, a),
            ORBE_MAX_KEY,
            ASPECTS_MAJEURS,
        )
    else:
        aspects_second_maitre = []

    # 4) Soleil
    sun = planetes.get("Soleil", {}) or {}
    sun_sign  = sun.get("signe", "N/A")
    sun_house = sun.get("maison", "N/A")

    sun_dignite = dignite_planete("Soleil", sun_sign)

    sun_dignite_str = (
        f" — dignité : {sun_dignite}"
        if sun_dignite
        else ""
    )
    sun_aspects = _pick(
        aspects, lambda a: _is_to("Soleil", a), ORBE_MAX_KEY, ASPECTS_MAJEURS
    )
    sun_aspects = [
        aspect for aspect in sun_aspects
        if conserver_aspect_chiron(
            aspect,
            maitre_principal=maitre,
            second_maitre=second_maitre,
        )
    ]

    # 5) Lune — comparaison Big 3
    lune = planetes.get("Lune", {}) or {}
    lune_sign = lune.get("signe", "N/A")
    lune_house = lune.get("maison", "N/A")

    # Strings
    asc_conj_str       = "\n".join(_fmt_aspect(a) for a in asc_conj) or "—"
    #asc_aspects_str    = "\n".join(_fmt_aspect(a) for a in asc_aspects) or "—"
    asc_aspects_filtrés = filtrer_aspects_ascendant(asc_aspects, orb_max=ORBE_MAX_ASC)
    # Les conjonctions sont déjà présentées dans leur rubrique dédiée.
    asc_aspects_filtrés = [
        aspect
        for aspect in asc_aspects_filtrés
        if str(aspect.get("aspect") or "").strip().casefold()
        != "conjonction"
    ]
    asc_aspects_filtrés = exclure_points_secondaires_bloc1(
        exclure_aspects_aux_noeuds(asc_aspects_filtrés)
    )
    asc_aspects_str     = "\n".join(_fmt_aspect(a) for a in asc_aspects_filtrés) or "—"
    #maison1_str        = ", ".join(maison1_planetes) if maison1_planetes else "Aucune"
    # Nettoyage : enlever K/Rahu/Ketu et normaliser Vénus
    maison1_nettoyees  = filtrer_planetes_maison_occidentale(maison1_planetes)

    # Chiron en Maison I est conservé comme facteur identitaire.
    if (
        "Chiron" in maison1_planetes
        and "Chiron" not in maison1_nettoyees
    ):
        maison1_nettoyees.append("Chiron")

    # Aspects entre planètes de Maison I
    aspects_maison1 = aspects_entre_planetes_maison1(
        aspects,
        maison1_nettoyees,
        max_orbe=5.0,
    )

    aspects_maison1 = [
        aspect for aspect in aspects_maison1
        if conserver_aspect_chiron(
            aspect,
            maitre_principal=maitre,
            second_maitre=second_maitre,
        )
    ]

    aspects_maison1_str = (
        "\n".join(_fmt_aspect(a) for a in aspects_maison1)
        or "—"
    )
    maison1_str        = ", ".join(maison1_nettoyees) if maison1_nettoyees else "Aucune"
    aspects_maitre = exclure_points_secondaires_bloc1(aspects_maitre)
    aspects_maitre = [
        aspect for aspect in aspects_maitre
        if conserver_aspect_chiron(
            aspect,
            maitre_principal=maitre,
            second_maitre=second_maitre,
        )
    ]
    # priorite_aspect = {
    #     "Conjonction": 0,
    #     "Carré": 1,
    #     "Opposition": 2,
    #     "Trigone": 3,
    #     "Sextile": 4,
    # }

    # aspects_maitre = selectionner_aspects_maitre(
    #     aspects_maitre,
    #     maitre=maitre,
    #     max_autres=3,
    # )

    aspects_maitre_str = (
        "\n".join(_fmt_aspect(a) for a in aspects_maitre)
        or "—"
    )

    aspects_second_maitre = exclure_points_secondaires_bloc1(
        aspects_second_maitre
    )

    aspects_second_maitre = [
        aspect for aspect in aspects_second_maitre
        if conserver_aspect_chiron(
            aspect,
            maitre_principal=maitre,
            second_maitre=second_maitre,
        )
    ]

    # aspects_second_maitre = selectionner_aspects_maitre(
    #     aspects_second_maitre,
    #     maitre=second_maitre,
    #     max_autres=2,
    # )

    aspects_second_maitre_str = (
        "\n".join(_fmt_aspect(a) for a in aspects_second_maitre)
        or "—"
    )

    #sun_aspects_str    = "\n".join(_fmt_aspect(a) for a in sun_aspects) or "—"
    sun_aspects_filtrés = exclure_points_secondaires_bloc1(
    exclure_aspects_aux_noeuds(sun_aspects)
    )

    sun_aspects_prioritaires_affichage = [
        a for a in sun_aspects_filtrés
        if a.get("aspect") in {"Conjonction", "Carré", "Opposition"}
    ]

    sun_aspects_secondaires_affichage = [
        a for a in sun_aspects_filtrés
        if a.get("aspect") in {"Trigone", "Sextile"}
    ]

    sun_aspects_filtrés = (
        sun_aspects_prioritaires_affichage
        + sun_aspects_secondaires_affichage[:2]
    )
    sun_aspects_str     = "\n".join(_fmt_aspect(a) for a in sun_aspects_filtrés) or "—"

    if dominante_1:
        dominante_str = (
            f"{dominante_1['planete']} "
            f"(écart Ascendant : {dominante_1['distance']}°)"
        )
    else:
        dominante_str = "Aucune"

    resume = f"""\
    Ascendant : {asc_sign} {asc_deg}° — Maison I
    Conjonctions à l’Ascendant (≤{ORBE_MAX_ASC}°) :
    {asc_conj_str}

    Aspects forts à l’Ascendant (≤{ORBE_MAX_ASC}°) :
    {asc_aspects_str}

    Planètes en Maison I :
    {maison1_str}

    Aspects entre planètes en Maison I :
    {aspects_maison1_str}

    Planète la plus proche de l’Ascendant (Maison I ou XII si conjointe) :
    {dominante_str}

    Maître principal d’Ascendant : {maitre} en {maitre_sign} — Maison {maitre_house} ({etat_maitre_str})
    Aspects forts du maître principal d’Ascendant (≤{ORBE_MAX_KEY}°) :
    {aspects_maitre_str}
    """.strip()

    if second_maitre:
        resume += f"""

    Maître traditionnel complémentaire : {second_maitre} en {second_maitre_sign} — Maison {second_maitre_house} ({etat_second_maitre_str})
    Aspects forts du maître traditionnel complémentaire (≤{ORBE_MAX_KEY}°) :
    {aspects_second_maitre_str}
    """

    resume += f"""

    Soleil : {sun_sign} — Maison {sun_house}{sun_dignite_str}
    Aspects forts du Soleil (≤{ORBE_MAX_KEY}°) :
    {sun_aspects_str}

    Lune : {lune_sign} — Maison {lune_house}
    """

    # Points prioritaires (top 3–5)
    priolist = []
    priolist += [_fmt_aspect(a) for a in asc_conj[:2]]
    #priolist += [_fmt_aspect(a) for a in asc_aspects if a["aspect"] in ASPECTS_DURS][:2]

    aspects_asc_prioritaires = filtrer_aspects_par_score(
        asc_aspects_filtrés,
        seuil_min=11,
        maitre_ascendant=maitre,
    )
    aspects_asc_prioritaires = [
        a for a in aspects_asc_prioritaires
        if a not in asc_conj
    ]
    priolist += [_fmt_aspect(a) for a in aspects_asc_prioritaires[:2]]

    aspects_sun_prioritaires = filtrer_aspects_par_score(
        sun_aspects_filtrés,
        seuil_min=12,
        maitre_ascendant=maitre,
    )

    priolist += [_fmt_aspect(a) for a in aspects_sun_prioritaires[:2]]

    # Aspects entre planètes en Maison I
    priolist += [
        _fmt_aspect(a)
        for a in aspects_maison1[:3]
    ]


    # Aspects du maître d’Ascendant : importants pour l’incarnation de l’identité
    aspects_maitre_prioritaires = filtrer_aspects_par_score(
        aspects_maitre,
        seuil_min=10,
        maitre_ascendant=maitre,
    )

    priolist += [
        _fmt_aspect(a)
        for a in aspects_maitre_prioritaires[:3]
    ]

    if second_maitre:
        aspects_second_maitre_prioritaires = filtrer_aspects_par_score(
            aspects_second_maitre,
            seuil_min=10,
            maitre_ascendant=second_maitre,
        )

        priolist += [
            _fmt_aspect(a)
            for a in aspects_second_maitre_prioritaires[:3]
        ]


  

    points_prioritaires = "\n".join(dict.fromkeys(priolist)) or "—"

    return {
        "resume_bloc1": resume,
        "points_prioritaires_bloc1": points_prioritaires,
        "maitre_principal": maitre,
        "second_maitre": second_maitre,
        "aspects_maison1_filtres": aspects_maison1,
        "aspects_sun_filtres": sun_aspects_filtrés,
        "aspects_maitre_filtres": aspects_maitre,
        "aspects_second_maitre_filtres": aspects_second_maitre,
    }


def generer_bloc_1(contexte: dict, max_tokens: int = 1400) -> str:
    """
    Section 1 : Ascendant & Maître d'Ascendant.
    Branchée sur BDD astrologique + tonalité + genre.
    """

    theme = contexte.get("theme")
    if not theme:
        return "❌ Contexte invalide : 'theme' manquant pour le Bloc 1."

    # ✅ DÉFINIR placements_str AVANT de l'utiliser (et garder une seule version)
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    )
    if (not placements_str or len(placements_str) < 50) and theme.get("planetes"):
        try:
            placements_str = formater_positions_planetes(theme["planetes"])
            logger.info("Bloc 1: placements_str reconstruit depuis theme")
        except Exception:
            logger.exception("Bloc 1: impossible de reconstruire placements_str")

    # 👉 construire le mini-résumé (on passe placements_str pour le fallback texte “Maison I”)
    meta = build_resume_bloc1(theme, placements_str)
    resume_bloc1 = meta["resume_bloc1"]
    priorites_1  = meta["points_prioritaires_bloc1"]
    maitre_asc = meta["maitre_principal"]
    second_maitre = meta["second_maitre"]
    aspects_maitre = meta.get("aspects_maitre_filtres", [])
    aspects_second_maitre = meta.get("aspects_second_maitre_filtres", [])

    aspects_maitre_bdd = selectionner_aspects_maitre(
        aspects_maitre,
        maitre=maitre_asc,
        max_autres=3,
    )

    aspects_second_maitre_bdd = selectionner_aspects_maitre(
        aspects_second_maitre,
        maitre=second_maitre,
        max_autres=2,
    )

    axes_majeurs = contexte.get("axes_majeurs_str", "")
    #rag_snippets = contexte.get("rag_snippets", "") or ""


    # ✅ AJOUT : Récupération des conjonctions À L'ASCENDANT (depuis points forts)
    conj_ascendant_str = (
        contexte.get("conjonctions_ascendant") 
        or contexte.get("conj_ascendant_str")
        or contexte.get("conj_asc_str")
        or ""
    )

    # ✅ AJOUT : Récupération du maître d'Ascendant
    maitre_asc_str = (
        contexte.get("maitre_asc_str") 
        or contexte.get("maitre_ascendant")
        or contexte.get("maitre_asc")
        or ""
    )

    # --- Préférences style & genre (VENANT DE L’ORCHESTRATEUR) ---
    tonalite = (contexte.get("tonalite") or "tu").strip().lower()   # "tu" | "vous"
    g_raw = (contexte.get("genre") or "").strip().lower()
    # tolère f/w/femme ; m/h/homme ; sinon neutre -> on force un label pour l’accord
    if g_raw.startswith(("f", "w")):
        genre_label = "femme"
    elif g_raw.startswith(("m", "h")) or g_raw in ("male", "homme"):
        genre_label = "homme"
    else:
        genre_label = "homme"  # valeur sûre si inconnu (évite le neutre bancal en FR)

    # 👀 DEBUG : loguer ce qu’on reçoit
    logger.debug("Bloc 1: contexte keys=%s", list(contexte.keys()))
    logger.debug("Bloc 1: tonalite=%s | genre=%s", tonalite, genre_label)
    logger.debug("Bloc 1: placements_str chars=%s", len(placements_str))
    logger.debug("Bloc 1: axes_majeurs chars=%s", len(axes_majeurs))

    if not placements_str or len(placements_str) < 50:
        return "❌ Données insuffisantes pour analyser l'Ascendant et son maître."

    # # ---- RAG : récupération + nettoyage + limite taille ----
    # if rag_snippets:
    #     # déduplication de lignes très proches (simple), trimming et cap ~3.5k
    #     lines = []
    #     seen = set()
    #     for ln in rag_snippets.splitlines():
    #         k = ln.strip()
    #         if k and k.lower() not in seen:
    #             seen.add(k.lower())
    #             lines.append(k)
    #     rag_snippets = "\n".join(lines)[:3500]

    # cap tokens pour ce bloc (standard ~4 pages total)
    max_tokens = min(max_tokens, 1500)

    # --- Instruction d’accords de genre pour guider le modèle ---
    if genre_label == "femme":
        genre_txt = "C'est une femme : adapte rigoureusement tes formulations au féminin."
    else:
        genre_txt = "C'est un homme : adapte rigoureusement tes formulations au masculin."

    faits_autorises = (contexte.get("faits_autorises") or "").strip()
    base_interpretations = contexte.get("base_interpretations", {}) or {}
    maitre_asc_bdd = base_interpretations.get("maitre_ascendant", {}) or {}

    # ==========================================================
    # BDD — Bloc 1 (Identité / Ascendant / Soleil)
    # ==========================================================

    bdd_bloc1_lignes = []

    # Maisons / signes utiles au Bloc 1 : Maison 1 + maître de maison 1
    domaines_signes = base_interpretations.get("domaines_signes", {})

    MAISONS_BLOC1 = {"1", "Maison 1"}

    domaines_bloc1_lignes = []

    planetes = theme.get("planetes", {})
    maison1_planetes = planets_in_house(planetes, 1)
    maison1_nettoyees = filtrer_planetes_maison_occidentale(maison1_planetes)

    # Chiron en Maison I est conservé comme facteur identitaire.
    if (
        "Chiron" in maison1_planetes
        and "Chiron" not in maison1_nettoyees
    ):
                maison1_nettoyees.append("Chiron")

    configurations_majeures = (
        contexte.get("configurations_majeures")
        or []
    )

    corps_identitaires_bloc1 = {
        "Ascendant",
        "Soleil",
        maitre_asc,
        second_maitre,
        *maison1_nettoyees,
    }

    corps_identitaires_bloc1.discard(None)
    corps_identitaires_bloc1.discard("")

    configurations_bloc1 = [
        configuration
        for configuration in configurations_majeures
        if corps_identitaires_bloc1.intersection(
            configuration.get("planetes", [])
        )
    ]

    configurations_bloc1_str = (
        formater_configurations_majeures(
            configurations_bloc1
        )
    )

    aspects_maison1 = meta["aspects_maison1_filtres"]

    for m in domaines_signes.get("maisons", []):
        if str(m["maison"]) in MAISONS_BLOC1:
            domaines_bloc1_lignes.append(
                f"{m['maison']} en {m['signe']} : {m['interpretation']}"
            )

    for m in domaines_signes.get("maitres_maisons", []):
        if str(m["maison"]) in MAISONS_BLOC1:
            domaines_bloc1_lignes.append(
                f"Maître de maison {m['maison']} ({m['maitre']}) en {m['signe']} : {m['interpretation']}"
            )

    domaines_bloc1_bdd = "\n".join(domaines_bloc1_lignes).strip()

    if not domaines_bloc1_bdd:
        domaines_bloc1_bdd = "—"


    # Soleil — placement + aspects structurants
    txt_soleil = formater_interpretation_planete_bdd(
        base_interpretations,
        "Soleil",
        colonnes=["IDENTITE"],
    )

    txt_soleil_interception = formater_interpretation_etat_bdd(
        base_interpretations,
        "Soleil",
        "interception",
        colonnes=["IDENTITE"],
    )

   

    sun_aspects_filtrés = meta["aspects_sun_filtres"]

    aspects_sun_prioritaires = filtrer_aspects_par_score(
        sun_aspects_filtrés,
        seuil_min=12,
        maitre_ascendant=maitre_asc,
    )

    lignes_soleil = []

    if txt_soleil:
        lignes_soleil.append(txt_soleil)

    if txt_soleil_interception:
        lignes_soleil.append(txt_soleil_interception)

    for aspect in aspects_sun_prioritaires:
        interpretation_aspect = rechercher_interpretation_aspect(
            aspect["planete1"],
            aspect["aspect"],
            aspect["planete2"],
            colonne="IDENTITE",
        )

        if interpretation_aspect:
            lignes_soleil.append(
                f"{aspect['planete1']} {aspect['aspect']} {aspect['planete2']} : "
                f"{interpretation_aspect}"
            )

    if lignes_soleil:
        bdd_bloc1_lignes.append(
            "Soleil / identité consciente :\n" + "\n\n".join(lignes_soleil)
        )

    # Lune — uniquement comme comparaison avec l’identité
    txt_lune_interception = formater_interpretation_etat_bdd(
        base_interpretations,
        "Lune",
        "interception",
        colonnes=["IDENTITE"],
    )

    if txt_lune_interception:
        bdd_bloc1_lignes.append(
            "Lune interceptée — nuance identitaire uniquement "
            "(ne pas développer toute la vie émotionnelle dans ce bloc) :\n"
            + txt_lune_interception
        )


    # Planètes en Maison I
    for planete_m1 in maison1_nettoyees:
        if planete_m1 == "Soleil":
            continue

        lignes_planete_m1 = []

        # Placement classique : signe + maison
        colonnes_planete_m1 = (
            ["IDENTITE"]
            if planete_m1 == "Chiron"
            else ["INTERPRETATION", "IDENTITE", "GRANDS_AXES"]
        )

        txt_planete_m1 = formater_interpretation_planete_bdd(
            base_interpretations,
            planete_m1,
            colonnes=colonnes_planete_m1,
        )

        if txt_planete_m1:
            lignes_planete_m1.append(txt_planete_m1)

        # État rétrograde éventuel
        # Uranus, Neptune et Pluton ne sont retenus que si leur
        # rétrogradation est suffisamment personnalisée.
        retrograde_pertinente = (
            planete_m1 not in {"Uranus", "Neptune", "Pluton"}
            or retrogradation_lente_pertinente(
                theme,
                planete_m1,
                maisons_cibles={1, 4, 7, 10},
                planetes_personnelles={
                    "Soleil",
                    "Lune",
                    "Mercure",
                    "Vénus",
                    "Mars",
                },
            )
        )

        if retrograde_pertinente:
            txt_planete_m1_retrograde = formater_interpretation_etat_bdd(
                base_interpretations,
                planete_m1,
                "retrograde",
                colonnes=["IDENTITE"],
            )

            if txt_planete_m1_retrograde:
                lignes_planete_m1.append(
                    txt_planete_m1_retrograde
                )

        # Interception éventuelle
        txt_planete_m1_interception = formater_interpretation_etat_bdd(
            base_interpretations,
            planete_m1,
            "interception",
            colonnes=["IDENTITE"],
        )

        if txt_planete_m1_interception:
            lignes_planete_m1.append(txt_planete_m1_interception)

        if lignes_planete_m1:
            bdd_bloc1_lignes.append(
                f"{planete_m1} en Maison I :\n"
                + "\n\n".join(lignes_planete_m1)
            )

    # Maître d’Ascendant — fonction spécifique
    maitre_asc_lignes = []

    if maitre_asc_bdd.get("signe"):
        identite_signe = maitre_asc_bdd["signe"].get("IDENTITE", "").strip()
        if identite_signe:
            maitre_asc_lignes.append(
                f"Maître d’Ascendant en signe : {identite_signe}"
            )

    if maitre_asc_bdd.get("maison"):
        identite_maison = maitre_asc_bdd["maison"].get("IDENTITE", "").strip()
        if identite_maison:
            maitre_asc_lignes.append(
                f"Maître d’Ascendant en maison : {identite_maison}"
            )



    txt_maitre_retrograde = formater_interpretation_etat_bdd(
        base_interpretations,
        maitre_asc,
        "retrograde",
        colonnes=["IDENTITE"],
    )

    if txt_maitre_retrograde:
        maitre_asc_lignes.append(txt_maitre_retrograde)

    txt_maitre_interception = formater_interpretation_etat_bdd(
        base_interpretations,
        maitre_asc,
        "interception",
        colonnes=["IDENTITE"],
    )

    if txt_maitre_interception:
        maitre_asc_lignes.append(txt_maitre_interception)

    # Aspects du maître d’Ascendant
    for aspect in aspects_maitre_bdd:

        autre_planete = (
            aspect["planete2"]
            if aspect["planete1"] == maitre_asc
            else aspect["planete1"]
        )

        interpretation_aspect = rechercher_interpretation_aspect(
            "maitre_asc",
            aspect["aspect"],
            autre_planete,
            colonne="IDENTITE",
        )

        if interpretation_aspect:
            maitre_asc_lignes.append(
                f"Maître d’Ascendant {aspect['aspect']} {autre_planete} : "
                f"{interpretation_aspect}"
            )

    if maitre_asc_lignes:
        bdd_bloc1_lignes.append("\n".join(maitre_asc_lignes))

    # Second maître d’Ascendant éventuel
    if second_maitre:
        second_maitre_lignes = []

        txt_second_maitre_retrograde = formater_interpretation_etat_bdd(
            base_interpretations,
            second_maitre,
            "retrograde",
            colonnes=["IDENTITE"],
        )

        if txt_second_maitre_retrograde:
            second_maitre_lignes.append(txt_second_maitre_retrograde)

        txt_second_maitre_interception = formater_interpretation_etat_bdd(
            base_interpretations,
            second_maitre,
            "interception",
            colonnes=["IDENTITE"],
        )

        if txt_second_maitre_interception:
            second_maitre_lignes.append(txt_second_maitre_interception)

        # Aspects du second maître d’Ascendant
        for aspect in aspects_second_maitre_bdd:

            autre_planete = (
                aspect["planete2"]
                if aspect["planete1"] == second_maitre
                else aspect["planete1"]
            )

            interpretation_aspect = rechercher_interpretation_aspect(
                "maitre_asc",
                aspect["aspect"],
                autre_planete,
                colonne="IDENTITE",
            )

            if interpretation_aspect:
                second_maitre_lignes.append(
                    f"Maître traditionnel complémentaire "
                    f"{aspect['aspect']} {autre_planete} : "
                    f"{interpretation_aspect}"
                )

        if second_maitre_lignes:
            bdd_bloc1_lignes.append(
                f"Maître traditionnel complémentaire ({second_maitre}) :\n"
                + "\n\n".join(second_maitre_lignes)
            )


    # ==========================================================
    # BDD — Aspects structurants Maison I
    # ==========================================================

    for aspect in aspects_maison1:
        interpretation_aspect = rechercher_interpretation_aspect(
            aspect["planete1"],
            aspect["aspect"],
            aspect["planete2"],
            colonne="IDENTITE",
        )

        if interpretation_aspect:
            bdd_bloc1_lignes.append(
                f"{aspect['planete1']} {aspect['aspect']} {aspect['planete2']} : "
                f"{interpretation_aspect}"
            )

    bdd_bloc1 = "\n".join(dict.fromkeys(bdd_bloc1_lignes)).strip()

    if not bdd_bloc1:
        bdd_bloc1 = "—"

    logger.warning(
        "\n========== BDD BLOC 1 ==========\n%s\n===============================",
        bdd_bloc1,
    )


    # ----- PROMPT utilisateur (avec RAG injecté) -----
    prompt = dedent(f"""

Tu es une astrologue expérimentée, à la plume fine, directe, drôle, lucide, sarcastique.
Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
Ton style est vivant mais jamais niais, jamais pompeux. Pas de poésie.. Tu évites les clichés astrologiques.
Tu ne parles pas *de* la personne, tu lui parles *directement*.
Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

Voici les données du thème de {theme['nom']} :
{genre_txt}

# Contexte narratif ciblé (à traiter en premier)
{resume_bloc1}


# Points prioritaires (obligatoires en tête d'analyse)
{priorites_1}

# Configurations majeures impliquant l’identité
{configurations_bloc1_str}

# Interprétations de référence issues de la base astrologique
{bdd_bloc1}

# Données astrologiques COMPLÈTES (référence)
{placements_str}

Section 1 : Identité & Corps

Mission :
Écris un portrait psychologique unique et incarné. Ne produis jamais
une fiche placement par placement.

Hiérarchie astrologique :

1. Les configurations et noyaux conjoints dominants
Une configuration majeure impliquant l’Ascendant, le Soleil, un maître
d’Ascendant ou une planète de Maison I constitue une structure globale
de l’identité. Interprète sa dynamique d’ensemble avant ses aspects séparés.

Toute conjonction serrée impliquant l’Ascendant, le Soleil ou une planète
de Maison I organise le portrait principal. Si plusieurs conjonctions forment
un même noyau, synthétise-les comme une seule structure psychologique.

Lorsqu’un aspect appartient déjà à une configuration ou à un noyau conjoint,
ne répète pas son interprétation séparément. Utilise-le seulement pour préciser
le fonctionnement de l’ensemble.

2. Le maître principal d’Ascendant
L’Ascendant décrit la manière spontanée d’entrer dans le monde, d’habiter
le corps, d’occuper l’espace et de réagir à l’environnement. Il ne constitue
pas un masque artificiel.
Interprète-le toujours avec le signe, la maison et les aspects de son maître.
Le maître d’Ascendant représente la manière globale dont la personne existe
et construit son identité, avant d’exprimer la fonction propre de la planète.

3. Le maître traditionnel complémentaire
Lorsqu’il est fourni, utilise-le comme une nuance réelle du fonctionnement
identitaire, sans lui faire remplacer le maître principal.

4. Le Soleil
Décris l’identité consciente, la volonté, le rapport à soi et la manière
d’affirmer son existence. La maison et les aspects priment sur la dignité.
Une dignité éventuelle nuance la facilité d’expression ; elle ne constitue
jamais un jugement de valeur.

5. Maison I, Maison XII et Chiron
Une planète en Maison I s’exprime directement dans la présence, le corps
et la manière d’être.
Une planète de Maison XII conjointe à l’Ascendant influence fortement
les réactions spontanées, mais peut rester moins consciente ou plus difficile
à reconnaître. Ne confonds jamais ces deux positions.
Si Chiron est en Maison I, traite-le comme un enjeu identitaire important
lié à la légitimité personnelle, au regard extérieur et au droit de prendre
sa place. N’en déduis jamais automatiquement un traumatisme, un rejet,
une vie antérieure ou un problème médical.

6. La Lune
Utilise-la uniquement pour montrer si le monde émotionnel soutient,
nuance ou complique l’identité construite par l’Ascendant et le Soleil.
Ne développe ni ses besoins profonds ni son histoire familiale dans ce bloc.

Méthode d’écriture :
- Croise les indices qui décrivent le même mécanisme.
- Mets en évidence les cohérences, paradoxes, excès et inhibitions.
- Donne des exemples concrets de comportements ou de situations.
- Utilise Persona, Ombre ou individuation seulement si cela éclaire
  concrètement le fonctionnement décrit.
- Parle directement à la personne en « tu ».
- Ton direct, lucide et éventuellement sarcastique, sans flatterie,
  poésie, cliché astrologique ou formule creuse.
- N’invente aucun placement, aspect, comportement ou événement.
- La présence de plusieurs planètes dans le même signe, la même maison ou le
  même noyau conjoint ne signifie pas qu'une planète est « entre », « coincée
  entre » ou « encadrée par » les autres. N'affirme une telle disposition que
  si elle est explicitement fournie dans les données comme une configuration
  calculée ; ne la déduis jamais toi-même des conjonctions.
- N’analyse ni l’enfance, ni les parents, ni les racines familiales.
- Ne donne aucun conseil générique de développement personnel.
- Ne commence pas par « Avec ton Ascendant... ».
- Termine par une transition naturelle vers la Lune et le monde intérieur.
- Aucun titre, aucune liste et aucune syntaxe markdown dans le texte final.

Format :
4–5 paragraphes en français, texte continu, tutoiement. Environ 500 mots.

IMPORTANT — MÉMOIRE INTERNE

À la toute fin de ta réponse, ajoute exactement ce bloc :

<resume_developpe>
...
</resume_developpe>

Dans cette balise, écris 2 à 3 phrases courtes résumant uniquement ce que tu as réellement développé dans ton analyse.

- le fonctionnement identitaire principal décrit ;
- la tension ou le paradoxe central mis en évidence ;

Ne cite aucun élément que tu n’as pas réellement développé dans le texte.
N’ajoute aucun conseil.

    """)

    logger.debug("Bloc 1: prompt chars=%s", len(prompt))

    print("\n===== PROMPT BLOC 1 ENVOYÉ AU LLM =====\n")
    print(prompt)
    print("\n===== FIN PROMPT BLOC 1 =====\n")

    # resultat = ask_llm(
    #     prompt,
    #     #system=system,                
    #     max_tokens=max_tokens,
    #     temperature=0.7,
    # )

    resultat = ask_llm(
        prompt,
        max_tokens=max_tokens,
        temperature=0.7,
    )

    texte, resume = extraire_resume_developpe(resultat)

    contexte["resume_bloc1"] = resume

    resultat = texte

    # DEBUG utile : garder le résultat (on n'affiche plus le prompt)
    logger.debug("Bloc 1: résultat chars=%s", len(resultat or ""))
    logger.debug("Bloc 1: aperçu résultat=%s", (resultat or "")[:1000])

    return resultat
