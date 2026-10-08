"""Extraction factuelle des éléments d'un thème de révolution solaire.

Ce module ne contient aucune interprétation. Les orbes restent des paramètres
visibles afin que la méthode de RS puisse évoluer sans toucher aux calculs.
"""

from __future__ import annotations

from collections import defaultdict

from .calculs_astrologiques_rs import get_maison_planete, get_maitres_ascendant
from utils.configurations_astrologiques import analyser_configurations_majeures
from .portrait_natal import extraire_portrait_natal_rs
from .profections import calculer_profection_annuelle
from .selection import selectionner_facteurs_directeurs_rs


POINTS_RS = (
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton", "Chiron", "Lune Noire",
    "Part de Fortune", "Rahu", "Ketu",
)
ANGLES = ("Ascendant", "MC", "Descendant", "FC")
# Les angles sont lus séparément comme activations d'axe. Ils ne créent pas
# à eux seuls un T-carré, un grand trigone ou un grand carré.
POINTS_FIGURES_RS = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton",
}
ASPECTS = (
    ("conjonction", 0), ("sextile", 60), ("carré", 90),
    ("trigone", 120), ("quinconce", 150), ("opposition", 180),
)


def _ecart(longitude_a: float, longitude_b: float) -> float:
    """Distance minimale entre deux longitudes, de 0 à 180 degrés."""
    brut = abs(longitude_a - longitude_b) % 360
    return min(brut, 360 - brut)


def _point(theme: dict, nom: str) -> dict | None:
    if nom == "Ascendant":
        donnees = (theme.get("planetes") or {}).get(nom)
        if donnees:
            return dict(donnees)
    if nom in ANGLES:
        longitude = (theme.get("angles_deg") or {}).get(nom)
        if longitude is None:
            return None
        return {"degre": float(longitude)}
    donnees = (theme.get("planetes") or {}).get(nom)
    return dict(donnees) if donnees else None


def _cuspides(theme: dict) -> list[float]:
    maisons = theme.get("maisons") or {}
    try:
        return [float(maisons[f"Maison {numero}"]["degre"]) for numero in range(1, 13)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Les cuspides du thème natal sont incomplètes.") from exc


def _maisons_interceptees_par_maitre(theme: dict) -> dict[str, list[dict]]:
    """Associe chaque maître aux maisons portées par des signes interceptés."""
    maisons = (theme.get("interceptions") or {}).get("maisons_interceptées") or {}
    resultat: dict[str, list[dict]] = defaultdict(list)
    for signe, maison_libelle in maisons.items():
        try:
            maison = int(str(maison_libelle).split()[-1])
        except (ValueError, IndexError):
            continue
        for maitre in get_maitres_ascendant(signe):
            entree = {"signe": signe, "maison": maison}
            if entree not in resultat[maitre]:
                resultat[maitre].append(entree)
    return dict(resultat)


def _aspects_rs_natal(
    theme_rs: dict,
    theme_natal: dict,
    orbe: float,
    orbe_angles: float,
) -> list[dict]:
    resultat = []
    for nom_rs in (*POINTS_RS, *ANGLES):
        # Le Soleil RS revient nécessairement à sa longitude natale. Tous ses
        # aspects au natal sont donc reproduits chaque année : ils relèvent du
        # thème natal, non de la dynamique spécifique de la RS.
        if nom_rs == "Soleil":
            continue
        point_rs = _point(theme_rs, nom_rs)
        if not point_rs:
            continue
        for nom_natal in (*POINTS_RS, *ANGLES):
            point_natal = _point(theme_natal, nom_natal)
            if not point_natal:
                continue
            distance = _ecart(float(point_rs["degre"]), float(point_natal["degre"]))
            for nom_aspect, angle in ASPECTS:
                ecart = abs(distance - angle)
                seuil = orbe_angles if nom_rs in ANGLES and nom_natal in ANGLES else orbe
                if ecart <= seuil:
                    resultat.append({
                        "point_rs": nom_rs,
                        "point_natal": nom_natal,
                        "aspect": nom_aspect,
                        "orbe": round(ecart, 2),
                    })
                    break
    return sorted(resultat, key=lambda aspect: aspect["orbe"])


def extraire_donnees_revolution_solaire(
    theme_natal: dict,
    theme_rs: dict,
    *,
    orbe_rs_natal: float = 6.0,
    orbe_rs_natal_angles: float = 6.0,
    orbe_angularite: float = 8.0,
    age_profection: int | None = None,
) -> dict:
    """Retourne les données techniques utiles à une future interprétation.

    Les orbes de 6° (contacts RS-natal), 6° (contacts angle à angle entre RS
    et natal) et 8° (angularité RS) sont des valeurs de méthode explicites.
    """
    if min(orbe_rs_natal, orbe_rs_natal_angles, orbe_angularite) < 0:
        raise ValueError("Les orbes doivent être positifs.")

    cuspides_natales = _cuspides(theme_natal)
    placements_rs = {}
    # Les placements natals sont conservés séparément des superpositions RS →
    # natal. Leurs maisons ne doivent jamais être déduites de la position RS.
    placements_natals_verifies = {
        nom: dict(point)
        for nom in POINTS_RS
        if (point := _point(theme_natal, nom))
    }
    maisons_occupees = defaultdict(list)
    angularites = []
    maisons_gouvernees_rs = theme_rs.get("house_rulers_map") or {}
    maisons_gouvernees_natales = theme_natal.get("house_rulers_map") or {}
    interceptions_rs = theme_rs.get("interceptions") or {}
    interceptions_natales = theme_natal.get("interceptions") or {}
    maisons_interceptees_rs = _maisons_interceptees_par_maitre(theme_rs)
    maisons_interceptees_natales = _maisons_interceptees_par_maitre(theme_natal)
    signes_interceptes_rs = interceptions_rs.get("maisons_interceptées") or {}
    signes_interceptes_natals = interceptions_natales.get("maisons_interceptées") or {}

    for nom in POINTS_RS:
        donnees = _point(theme_rs, nom)
        if not donnees:
            continue
        copie = dict(donnees)
        copie["maison_natale"] = get_maison_planete(float(copie["degre"]), cuspides_natales)
        # Une planète ne se lit pas seulement là où elle se trouve : elle porte
        # aussi les maisons dont les cuspides tombent dans ses signes.
        copie["maisons_gouvernees_rs"] = list(maisons_gouvernees_rs.get(nom, []))
        copie["maisons_gouvernees_natales"] = list(maisons_gouvernees_natales.get(nom, []))
        copie["maisons_gouvernees_interceptees_rs"] = list(maisons_interceptees_rs.get(nom, []))
        copie["maisons_gouvernees_interceptees_natales"] = list(maisons_interceptees_natales.get(nom, []))
        copie["signe_intercepte_rs"] = signes_interceptes_rs.get(copie.get("signe"))
        copie["signe_intercepte_natal"] = signes_interceptes_natals.get(copie.get("signe"))
        placements_rs[nom] = copie
        maisons_occupees[copie.get("maison")].append(nom)

        for angle in ANGLES:
            angle_rs = _point(theme_rs, angle)
            if not angle_rs:
                continue
            distance = _ecart(float(copie["degre"]), float(angle_rs["degre"]))
            if distance <= orbe_angularite:
                angularites.append({"point": nom, "angle": angle, "orbe": round(distance, 2)})

    maitre = dict(theme_rs.get("maitre_ascendant") or {})
    nom_maitre = maitre.get("nom")
    if nom_maitre in placements_rs:
        maitre["maison_natale"] = placements_rs[nom_maitre]["maison_natale"]

    signe_ascendant_rs = (theme_rs.get("maisons") or {}).get("Maison 1", {}).get("signe")
    maitres_ascendant_rs = []
    if signe_ascendant_rs:
        for nom in get_maitres_ascendant(signe_ascendant_rs):
            if not nom:
                continue
            fiche = _point(theme_rs, nom)
            if fiche:
                fiche["nom"] = nom
                fiche["maison_natale"] = placements_rs.get(nom, {}).get("maison_natale")
                fiche["maisons_gouvernees_rs"] = list(maisons_gouvernees_rs.get(nom, []))
                fiche["maisons_gouvernees_natales"] = list(maisons_gouvernees_natales.get(nom, []))
                fiche["maisons_gouvernees_interceptees_rs"] = list(maisons_interceptees_rs.get(nom, []))
                fiche["maisons_gouvernees_interceptees_natales"] = list(maisons_interceptees_natales.get(nom, []))
                maitres_ascendant_rs.append(fiche)

    points_autorises = set(POINTS_RS) | set(ANGLES)
    aspects_rs = [
        aspect for aspect in (theme_rs.get("aspects_avec_angles") or [])
        if (
            aspect.get("planete1") in points_autorises
            and aspect.get("planete2") in points_autorises
        )
    ]
    aspects_figures_rs = [
        aspect for aspect in aspects_rs
        if (
            aspect.get("planete1") in POINTS_FIGURES_RS
            and aspect.get("planete2") in POINTS_FIGURES_RS
        )
    ]
    positions_figures_rs = {
        nom: point for nom, point in (theme_rs.get("planetes") or {}).items()
        if nom in POINTS_FIGURES_RS
    }
    configurations_majeures_rs = analyser_configurations_majeures(
        aspects_figures_rs,
        positions_figures_rs,
    )
    profection = (
        calculer_profection_annuelle(theme_natal, theme_rs, age=age_profection)
        if age_profection is not None
        else None
    )
    resultat = {
        "parametres": {
            "orbe_rs_natal": orbe_rs_natal,
            "orbe_rs_natal_angles": orbe_rs_natal_angles,
            "orbe_angularite": orbe_angularite,
            "lune_noire": "moyenne",
        },
        "ascendant_rs": _point(theme_rs, "Ascendant"),
        "portrait_natal": extraire_portrait_natal_rs(theme_natal),
        "maitre_ascendant_rs": maitre,
        "maitres_ascendant_rs": maitres_ascendant_rs,
        "maisons_gouvernees_rs": dict(maisons_gouvernees_rs),
        "maisons_gouvernees_natales": dict(maisons_gouvernees_natales),
        "interceptions_rs": dict(interceptions_rs),
        "interceptions_natales": dict(interceptions_natales),
        "placements_rs": placements_rs,
        "placements_natals_verifies": placements_natals_verifies,
        "maisons_rs_occupees": dict(sorted(maisons_occupees.items())),
        "points_angulaires_rs": sorted(angularites, key=lambda item: item["orbe"]),
        "aspects_internes_rs": aspects_rs,
        "configurations_majeures_rs": configurations_majeures_rs,
        "profection_annuelle": profection,
        "aspects_rs_natal": _aspects_rs_natal(
            theme_rs, theme_natal, orbe_rs_natal, orbe_rs_natal_angles
        ),
    }
    resultat["facteurs_directeurs_rs"] = selectionner_facteurs_directeurs_rs(resultat)
    return resultat
