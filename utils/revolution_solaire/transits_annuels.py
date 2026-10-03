"""Détection factuelle des transits qui activent une révolution solaire."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils.transits.calcul_transits import calculer_positions_transits


ASPECTS_TRANSITS_RS = {
    "conjonction": (0.0, 5.0),
    "sextile": (60.0, 3.0),
    "carré": (90.0, 4.0),
    "trigone": (120.0, 4.0),
    "quinconce": (150.0, 3.0),
    "opposition": (180.0, 5.0),
}
PLANETES_TRANSIT_ANNUELS = {"Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}
CIBLES_NATALES = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton", "Chiron", "Lune Noire", "Part de Fortune",
    "Rahu", "Ketu",
}
POIDS_TRANSIT = {"Pluton": 10, "Neptune": 9, "Saturne": 9, "Uranus": 8, "Jupiter": 5, "Mars": 4}
POIDS_ASPECT = {"conjonction": 10, "opposition": 9, "carré": 9, "quinconce": 7, "trigone": 6, "sextile": 4}


def _ecart(longitude_a: float, longitude_b: float) -> float:
    brut = abs(longitude_a - longitude_b) % 360.0
    return min(brut, 360.0 - brut)


def _longitude(point: dict | float | int | None) -> float | None:
    if isinstance(point, dict):
        point = point.get("longitude", point.get("degre"))
    try:
        return float(point) % 360.0
    except (TypeError, ValueError):
        return None


def _angles(theme: dict) -> dict[str, float]:
    angles = dict(theme.get("angles_deg") or {})
    asc = _longitude(angles.get("Ascendant"))
    mc = _longitude(angles.get("MC"))
    resultat = {}
    if asc is not None:
        resultat["Ascendant"] = asc
        resultat["Descendant"] = (asc + 180.0) % 360.0
    if mc is not None:
        resultat["MC"] = mc
        resultat["FC"] = (mc + 180.0) % 360.0
    return resultat


def _cibles_natales(theme_natal: dict) -> dict[str, float]:
    cibles = {
        nom: longitude
        for nom, point in (theme_natal.get("planetes") or {}).items()
        if nom in CIBLES_NATALES and (longitude := _longitude(point)) is not None
    }
    cibles.update(_angles(theme_natal))
    return cibles


def _cibles_rs(theme_rs: dict, facteurs_directeurs: dict) -> dict[str, float]:
    """Garde les facteurs qui donnent effectivement sa couleur à la RS."""
    noms = {"Ascendant", "MC"}
    for cle in ("soleil_rs", "lune_rs"):
        # Le Soleil RS est identique au Soleil natal : ne pas le dupliquer.
        if cle != "soleil_rs":
            noms.add("Lune")
    for maitre in facteurs_directeurs.get("maitres_ascendant_rs") or []:
        if maitre.get("nom"):
            noms.add(maitre["nom"])
    for figure in facteurs_directeurs.get("figures_majeures") or []:
        noms.update(figure.get("planetes") or [])
    for contexte in facteurs_directeurs.get("planetes_contextuelles") or []:
        if contexte.get("planete"):
            noms.add(contexte["planete"])

    positions = dict(theme_rs.get("planetes") or {})
    positions.update(_angles(theme_rs))
    return {
        nom: longitude
        for nom, point in positions.items()
        if nom in noms and (longitude := _longitude(point)) is not None
    }


def _aspects_du_jour(
    date_utc: datetime,
    cibles: dict[str, float],
    reference: str,
) -> list[dict]:
    positions = calculer_positions_transits(date_utc.replace(tzinfo=None))["positions"]
    resultats = []
    for nom_transit, donnees in positions.items():
        if nom_transit not in PLANETES_TRANSIT_ANNUELS:
            continue
        longitude_transit = _longitude(donnees)
        if longitude_transit is None:
            continue
        for cible, longitude_cible in cibles.items():
            # Une RS est une photographie du ciel du retour : la conjonction
            # d'une planète lente de transit avec elle-même en RS est mécanique,
            # pas un déclencheur annuel à interpréter.
            if reference == "rs" and nom_transit == cible:
                continue
            distance = _ecart(longitude_transit, longitude_cible)
            for aspect, (angle, orbe_max) in ASPECTS_TRANSITS_RS.items():
                orbe = abs(distance - angle)
                if orbe <= orbe_max:
                    resultats.append({
                        "planete_transit": nom_transit,
                        "reference": reference,
                        "cible": cible,
                        "aspect": aspect,
                        "orbe": round(orbe, 3),
                        "date": date_utc,
                        "retrograde": bool(donnees.get("retrograde")),
                    })
    return resultats


def calculer_transits_annuels_rs(
    theme_natal: dict,
    theme_rs: dict,
    facteurs_directeurs: dict,
    debut_utc: datetime,
    fin_utc: datetime,
) -> list[dict]:
    """Retourne les fenêtres de transits annuels vers natal et facteurs RS.

    Le balayage est quotidien : il fournit une première fenêtre datée et le
    passage au plus faible orbe observé. Le raffinage à l'heure sera ajouté au
    moment de construire l'outil de datation détaillé.
    """
    if debut_utc.tzinfo is None or fin_utc.tzinfo is None:
        raise ValueError("Les bornes de période doivent être en UTC.")
    debut = debut_utc.astimezone(timezone.utc)
    fin = fin_utc.astimezone(timezone.utc)
    if fin <= debut:
        raise ValueError("La fin de période doit être postérieure au début.")

    cibles = {
        "natal": _cibles_natales(theme_natal),
        "rs": _cibles_rs(theme_rs, facteurs_directeurs),
    }
    ouvertes: dict[tuple[str, str, str, str], dict] = {}
    fermees: list[dict] = []
    date = debut.replace(hour=12, minute=0, second=0, microsecond=0)
    while date <= fin:
        detectes = []
        for reference, points in cibles.items():
            detectes.extend(_aspects_du_jour(date, points, reference))
        cles_du_jour = set()
        for transit in detectes:
            cle = (transit["planete_transit"], transit["reference"], transit["cible"], transit["aspect"])
            cles_du_jour.add(cle)
            fenetre = ouvertes.get(cle)
            if fenetre is None:
                ouvertes[cle] = {
                    **transit,
                    "debut": transit["date"],
                    "fin": transit["date"],
                    "date_plus_serree": transit["date"],
                    "orbe_plus_serre": transit["orbe"],
                }
                continue
            fenetre["fin"] = transit["date"]
            if transit["orbe"] < fenetre["orbe_plus_serre"]:
                fenetre["orbe_plus_serre"] = transit["orbe"]
                fenetre["date_plus_serree"] = transit["date"]
                fenetre["retrograde"] = transit["retrograde"]
        for cle in set(ouvertes) - cles_du_jour:
            fermees.append(ouvertes.pop(cle))
        date += timedelta(days=1)

    fermees.extend(ouvertes.values())
    resultat = []
    for fenetre in fermees:
        resultat.append({
            "planete_transit": fenetre["planete_transit"],
            "reference": fenetre["reference"],
            "cible": fenetre["cible"],
            "aspect": fenetre["aspect"],
            "debut": fenetre["debut"].date().isoformat(),
            "fin": fenetre["fin"].date().isoformat(),
            "date_plus_serree": fenetre["date_plus_serree"].date().isoformat(),
            "orbe_plus_serre": fenetre["orbe_plus_serre"],
            "retrograde_au_plus_serre": fenetre["retrograde"],
        })
    return sorted(resultat, key=lambda item: (item["date_plus_serree"], item["orbe_plus_serre"]))


def selectionner_transits_directeurs_rs(
    evenements: list[dict],
    facteurs_directeurs: dict,
    *,
    maximum: int = 30,
) -> list[dict]:
    """Hiérarchise les fenêtres annuelles sans supprimer le relevé exhaustif."""
    cibles_rs_majeures = {"Ascendant", "MC", "Lune"}
    for maitre in facteurs_directeurs.get("maitres_ascendant_rs") or []:
        if maitre.get("nom"):
            cibles_rs_majeures.add(maitre["nom"])
    for figure in facteurs_directeurs.get("figures_majeures") or []:
        cibles_rs_majeures.update(figure.get("planetes") or [])

    cibles_natales_majeures = {
        "Ascendant", "Descendant", "MC", "FC", "Soleil", "Lune",
        "Mercure", "Vénus", "Mars",
    }
    selection = []
    for evenement in evenements:
        cible = evenement["cible"]
        reference = evenement["reference"]
        if reference == "rs":
            poids_cible = 10 if cible in cibles_rs_majeures else 4
        else:
            poids_cible = 9 if cible in cibles_natales_majeures else 2

        # Mars sert de déclencheur rapide : ne garder que les contacts vraiment
        # connectés au noyau RS ou aux facteurs personnels du natal.
        if evenement["planete_transit"] == "Mars" and poids_cible < 9:
            continue

        score = (
            POIDS_TRANSIT[evenement["planete_transit"]]
            + POIDS_ASPECT[evenement["aspect"]]
            + poids_cible
            + (3 if evenement["orbe_plus_serre"] <= 1 else 1 if evenement["orbe_plus_serre"] <= 2 else 0)
        )
        selection.append({**evenement, "score_priorite": score})

    return sorted(
        selection,
        key=lambda item: (-item["score_priorite"], item["orbe_plus_serre"], item["date_plus_serree"]),
    )[:maximum]
