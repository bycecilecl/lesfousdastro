# utils/transits/detecteurs.py
from .config import (
    ASPECTS_TRANSITS,
    ORBES_TRANSITS,
    POIDS_CIBLES_NATALES,
    POIDS_ASPECTS,
    PLANETES_EXCLUES,
    POIDS_PLANETES_TRANSIT,
    POIDS_PLANETES_NATALES,
)
from .modeles import TransitActif
from .maisons import trouver_maison
from utils.astro_constants import (
    MAPPING_ANGLES,
    NOMS_AFFICHAGE_ANGLES,
)
import logging


ANGLES_NATAUX = {"ascendant", "descendant", "milieu_du_ciel", "fond_du_ciel"}

logger = logging.getLogger(__name__)

def ecart_a_laspect(delta: float, angle_aspect: float) -> float:
    """
    Retourne l'orbe : écart entre la distance réelle
    et l'angle théorique de l'aspect.
    """
    return abs(delta - angle_aspect)

def trouver_conjonctions_natales(
    planete: str,
    natal_et_angles: dict,
    orbe_max: float = 5.0,
) -> list[str]:
    """
    Cherche si la planète/point natal touché appartient à une conjonction natale.
    Exemple : Pluton conjoint Soleil, Lune Noire ou Ascendant.
    """

    if planete not in natal_et_angles:
        return []

    pos_ref = natal_et_angles[planete].get("longitude")
    if pos_ref is None:
        return []

    associees = []

    for autre, data in natal_et_angles.items():
        if autre == planete:
            continue
        if autre in PLANETES_EXCLUES:
            continue
        pos_autre = data.get("longitude")
        if pos_autre is None:
            continue

        diff = abs(pos_ref - pos_autre)
        if diff > 180:
            diff = 360 - diff

        if diff <= orbe_max:
            associees.append(NOMS_AFFICHAGE_ANGLES.get(autre, autre))

    return associees

def calculer_importance(
    planete_natale: str,
    aspect: str,
    orbe: float,
    maitre_ascendant: str | None = None,
) -> int:
    """
    Score astrologique simple du transit.
    """

    score = 0

    # poids de la planète touchée
    score += POIDS_CIBLES_NATALES.get(planete_natale, 1)

    # poids de l’aspect
    score += POIDS_ASPECTS.get(aspect, 1)

    # bonus orbe serré
    if orbe <= 1:
        score += 3
    elif orbe <= 2:
        score += 2
    elif orbe <= 3:
        score += 1

    # bonus si le transit touche le maître d’Ascendant
    if maitre_ascendant and planete_natale == maitre_ascendant:
        score += 9

    return score


def detecter_aspects(
    transits: dict,
    natal: dict,
    cuspides: list[float],
    house_rulers_map: dict,
    maitre_ascendant: str | None = None,
    angles_deg: dict | None = None,
) -> list[TransitActif]:
    """
    Détecte les aspects entre les planètes en transit et les planètes natales,
    puis enrichit chaque aspect avec le contexte maison façon Brady.
    """

    aspects_detectes = []

    natal_et_angles = dict(natal)

    if angles_deg:
        angles_complets = dict(angles_deg)

        if "Ascendant" in angles_complets and "Descendant" not in angles_complets:
            angles_complets["Descendant"] = (angles_complets["Ascendant"] + 180) % 360

        if "MC" in angles_complets and "FC" not in angles_complets:
            angles_complets["FC"] = (angles_complets["MC"] + 180) % 360

        for cle_angle, nom_bdd in MAPPING_ANGLES.items():
            lon_angle = angles_complets.get(cle_angle)

            if lon_angle is not None:
                natal_et_angles[nom_bdd] = {
                    "longitude": lon_angle,
                    "maison": None,
                    "type": "angle",
                }

    for nom_transit, data_t in transits.items():
        if nom_transit in PLANETES_EXCLUES:
            continue
        lon_t = data_t.get("longitude")
        if lon_t is None:
            continue

        vitesse_transit = data_t.get("vitesse", 1.0)

        # Maison où se trouve actuellement la planète en transit
        maison_courante = trouver_maison(lon_t, cuspides)

        # Données natales de la planète transitante
        # Exemple : Uranus transitant → Uranus natal dans le thème
        planete_transit_natale = natal.get(nom_transit, {})
        maison_natale_transit = planete_transit_natale.get("maison")

        # Maisons gouvernées par la planète transitante
        maisons_gouvernees_transit = house_rulers_map.get(nom_transit, [])

        for nom_nat, data_n in natal_et_angles.items():
            if nom_nat in PLANETES_EXCLUES:
                continue
            lon_n = data_n.get("longitude")
            if lon_n is None:
                continue

            delta = abs(lon_t - lon_n)
            if delta > 180:
                delta = 360 - delta

            for aspect_nom, angle in ASPECTS_TRANSITS.items():
                orbe_max = ORBES_TRANSITS[aspect_nom]
                orbe = ecart_a_laspect(delta, angle)

                if orbe <= orbe_max:
                    nom_nat_affichage = NOMS_AFFICHAGE_ANGLES.get(nom_nat, nom_nat)
                    importance = calculer_importance(
                        planete_natale=NOMS_AFFICHAGE_ANGLES.get(nom_nat, nom_nat),
                        aspect=aspect_nom,
                        orbe=orbe,
                        maitre_ascendant=maitre_ascendant,
                    )

                    # ─────────────────────────────────────────────────────
                    # Score narratif astrologique (climat réel)
                    # ─────────────────────────────────────────────────────

                    poids_transit_lent = POIDS_PLANETES_TRANSIT.get(nom_transit, 0)
                    poids_planete_natale = POIDS_PLANETES_NATALES.get(nom_nat_affichage, 0)

                    importance += poids_transit_lent
                    importance += poids_planete_natale

                    if nom_nat in ANGLES_NATAUX:
                        importance += 12

                    contexte = {
                        "maison_transit": maison_courante,
                        "maison_natale_transit": maison_natale_transit,
                        "maison_natale_planete": data_n.get("maison"),
                        "maisons_gouvernees_transit": maisons_gouvernees_transit,
                        "maisons_gouvernees_natale": house_rulers_map.get(nom_nat_affichage, []),
                    }

                    if nom_nat in ANGLES_NATAUX:
                        logger.info(
                            "ANGLE DETECTE | %s %s %s | orbe=%s | importance=%s",
                            nom_transit,
                            aspect_nom,
                            nom_nat,
                            round(orbe, 2),
                            importance,
                        )


                    conjonctions_associees = trouver_conjonctions_natales(
                        planete=nom_nat,
                        natal_et_angles=natal_et_angles,
                        orbe_max=8.0,
                    )

                    if conjonctions_associees:
                        logger.info(
                            "CONJONCTIONS ASSOCIEES | %s touché par %s %s | associees=%s",
                            nom_nat_affichage,
                            nom_transit,
                            aspect_nom,
                            conjonctions_associees,
                        )

                    aspects_detectes.append(
                        TransitActif(
                            planete_transit=nom_transit,
                            planete_natale=nom_nat_affichage,
                            aspect=aspect_nom,
                            orbe=round(orbe, 2),
                            importance=importance,
                            application=vitesse_transit > 0,
                            contexte=contexte,
                            conjonctions_associees=conjonctions_associees,
                        )
                    )

    return sorted(
        aspects_detectes,
        key=lambda a: (-a.importance, a.orbe)
    )




# if __name__ == "__main__":
#     transits = {
#         "Saturne": {"longitude": 90.0, "vitesse": 0.05},
#     }

#     natal = {
#         "Soleil": {"longitude": 0.0},
#         "Lune": {"longitude": 92.0},
#     }

#     aspects = detecter_aspects(transits, natal)

#     for a in aspects:
#         print(a)
