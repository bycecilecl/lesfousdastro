"""Raccord du gratuit au moteur partagé de configurations, sans appel IA."""

from itertools import combinations
from math import isfinite

from utils import configurations_astrologiques as moteur
from utils.calculs_astrologiques import ORBES_DEFAUT, degre_vers_signe
from utils.analyse_gratuite_formatage import formater_aspects


def preparer_figures_analyse_gratuite(theme):
    """Adapte le contrat de calcul_theme sans modifier le thème ni le moteur.

    Les degrés de calcul_theme sont des longitudes absolues. Les liens sont
    recalculés pour les figures : le filtre des aspects individuels peut
    sinon supprimer un trigone ou un carré admis par le moteur de figures.
    Les seuils et la validation des figures restent ceux du moteur partagé.
    """
    positions = {}
    corps_autorises = (
        moteur.CORPS_CONFIGURATIONS_MAJEURES
        | moteur.POINTS_CONJONCTIONS_IDENTITAIRES
    )
    sources = dict(theme.get("planetes") or {})
    if "Ascendant" not in sources and isinstance(theme.get("ascendant"), dict):
        sources["Ascendant"] = theme["ascendant"]
    for angle in ("Ascendant", "MC"):
        longitude = (theme.get("angles_deg") or {}).get(angle)
        if longitude is not None:
            sources[angle] = {**sources.get(angle, {}), "degre": longitude}

    for nom, fiche in sources.items():
        if nom not in corps_autorises or not isinstance(fiche, dict):
            continue
        valeur = fiche.get("longitude")
        if valeur is None:
            valeur = fiche.get("degre")
        try:
            longitude = float(valeur)
        except (TypeError, ValueError):
            raise ValueError(f"Longitude absente ou invalide pour la figure : {nom}.")
        if not isfinite(longitude) or not 0 <= longitude < 360:
            raise ValueError(f"Longitude hors limites pour la figure : {nom}.")
        signe, degre_signe = degre_vers_signe(longitude)
        positions[nom] = {
            **fiche, "longitude": longitude, "degre": longitude,
            "signe": signe, "degre_dans_signe": degre_signe,
        }
        if nom in {"Ascendant", "MC"}:
            positions[nom]["maison"] = 1 if nom == "Ascendant" else 10

    regles = (
        ("conjonction", 0, moteur.ORBE_CONJONCTION_BLOC),
        ("opposition", 180, max(moteur.ORBE_OPPOSITION_T_CARRE,
                                moteur.ORBE_OPPOSITION_GRAND_CARRE)),
        ("carré", 90, max(moteur.ORBE_CARRE_T_CARRE,
                         moteur.ORBE_CARRE_GRAND_CARRE)),
        ("trigone", 120, moteur.ORBE_GRAND_TRIGONE),
        # Le moteur du diamant utilise les sextiles du calculateur natal.
        ("sextile", 60, ORBES_DEFAUT["sextile"]),
    )
    aspects = []
    for (nom_a, a), (nom_b, b) in combinations(sorted(positions.items()), 2):
        distance = abs((a["longitude"] - b["longitude"] + 180) % 360 - 180)
        for nature, angle, limite in regles:
            orbe = abs(distance - angle)
            if orbe <= limite:
                aspects.append({"planete1": nom_a, "planete2": nom_b,
                                "aspect": nature, "orbe": orbe})

    configurations = moteur.analyser_configurations_majeures(aspects, positions)
    configurations.sort(key=lambda c: (c["type"], tuple(sorted(c["planetes"]))))
    texte = moteur.formater_configurations_majeures(configurations)
    liens = {}
    for configuration in configurations:
        for aspect in configuration.get("aspects_constitutifs") or []:
            cle = (*sorted((aspect["planete1"], aspect["planete2"])), aspect["aspect"])
            liens[cle] = aspect
    if liens:
        texte += "\n\nLiens constitutifs des figures (avec orbes) :\n"
        texte += formater_aspects(list(liens.values()))
    return configurations, texte
