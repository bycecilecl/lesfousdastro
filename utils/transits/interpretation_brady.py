# utils/transits/interpretation_brady.py
from .synthese_brady import THEMES_MAISONS
from .transits_bdd import (
    chercher_interpretation_aspect,
    chercher_interpretation_maison,
)
import logging
logger = logging.getLogger(__name__)

SENS_PLANETES_TRANSIT = {
    "Jupiter":  "amplifie, ouvre et pousse à élargir",
    "Saturne":  "structure, limite et oblige à regarder la réalité en face",
    "Uranus":   "réveille, fracture et libère ce qui était figé",
    "Neptune":  "floute, sensibilise et dissout les anciens repères",
    "Pluton":   "intensifie, transforme et met à nu ce qui opère en profondeur",
    "Mars":     "active, accélère et met sous pression",
    "Chiron": "réactive une zone sensible et oblige à changer de rapport à la vulnérabilité",
}

SENS_PLANETES_NATALES = {
    "Soleil":    "l'identité, la confiance et la direction personnelle",
    "Lune":      "le monde émotionnel, les besoins profonds et la sécurité intérieure",
    "Mercure":   "la pensée, la communication et la manière de comprendre",
    "Vénus":     "l'affectif, les valeurs et la manière d'aimer",
    "Mars":      "l'action, l'affirmation et le désir",
    "Jupiter":   "la foi, l'expansion et les croyances",
    "Saturne":   "les limites, la structure et la peur",
    "Uranus":    "le besoin de liberté, d'indépendance et de rupture",
    "Neptune":   "l'idéal, la confusion et la sensibilité profonde",
    "Pluton":    "l'intensité, la transformation et les instincts de fond",
    "Nœud Nord": "la direction évolutive et le chemin de croissance",
    "Chiron": "une zone sensible ancienne où la vulnérabilité demande une autre posture",
}

VERBES_ASPECTS = {
    "conjonction": "se fond dans",
    "opposition":  "affronte directement",
    "carré":       "bouscule et met en friction",
    "trigone":     "soutient et fluidifie",
    "sextile":     "ouvre doucement vers",
}

TONALITES_ASPECTS = {
    "conjonction": "fusion intense — pas de distance possible entre les deux énergies",
    "opposition":  "tension entre deux pôles qui se révèlent l'un l'autre",
    "carré":       "friction nécessaire — quelque chose doit bouger ou changer",
    "trigone":     "énergie fluide — une ouverture naturelle se présente",
    "sextile":     "opportunité douce — à saisir consciemment",
}

def _formatter_maisons_activees(maisons: list[int]) -> str:
    parties = []
    for m in maisons[:4]:
        theme = THEMES_MAISONS.get(m)
        if theme:
            parties.append(f"maison {m} ({theme})")
    return ", ".join(parties) if parties else "zones non identifiées"


def _ordonner_maisons_brady(contexte: dict) -> list[int]:
    """
    Ordre Brady :
    1. maison transitée (où est la planète en transit maintenant)
    2. maison natale de la planète touchée
    3. maisons gouvernées par la planète natale
    4. maison natale de la planète en transit
    5. maisons gouvernées par la planète en transit
    """
    vues = []
    ordre = [
        "maison_transit",
        "maison_natale_planete",
        "maisons_gouvernees_natale",
        "maison_natale_transit",
        "maisons_gouvernees_transit",
    ]
    for cle in ordre:
        val = contexte.get(cle)
        if isinstance(val, list):
            for m in val:
                if m and m not in vues:
                    vues.append(m)
        elif val and val not in vues:
            vues.append(val)
    return vues


def interpreter_transit_brady(transit) -> str:
    planete_t = transit.planete_transit
    planete_n = transit.planete_natale
    aspect = transit.aspect
    ctx = transit.contexte or {}

    interpretation_aspect = chercher_interpretation_aspect(
        planete_t,
        aspect,
        planete_n,
    )

    logger.info(
        "BDD ASPECT | %s %s %s => %s",
        planete_t,
        aspect,
        planete_n,
        "OK" if interpretation_aspect else "AUCUNE ENTREE",
    )

    interpretation_maison = chercher_interpretation_maison(
        planete_t,
        ctx.get("maison_transit"),
    )

    logger.info(
        "BDD MAISON | %s maison %s => %s",
        planete_t,
        ctx.get("maison_transit"),
        "OK" if interpretation_maison else "AUCUNE ENTREE",
    )
    

    sens_t   = SENS_PLANETES_TRANSIT.get(planete_t, "active et transforme")
    sens_n   = SENS_PLANETES_NATALES.get(planete_n, f"la fonction {planete_n}")
    verbe    = VERBES_ASPECTS.get(aspect, "entre en relation avec")
    tonalite = TONALITES_ASPECTS.get(aspect, "")
    maisons  = _ordonner_maisons_brady(ctx)
    champs   = _formatter_maisons_activees(maisons)

    bloc_interpretations = " ".join(
        filter(
            None,
            [
                interpretation_aspect,
                interpretation_maison,
            ]
        )
    )


    return (
        f"{planete_t} {verbe} {sens_n}. "
        f"{tonalite.capitalize()}. "
        f"{bloc_interpretations} "
        f"Ici, {planete_t.lower()} {sens_t}. "
        f"Champs activés (lecture Brady) : {champs}."
    )
