"""Prompt du chapitre des points symboliques complémentaires de la RS."""

from __future__ import annotations

import json

from .presentation import traduire_pour_affichage


POINTS_SYMBOLIQUES = ("Rahu", "Ketu", "Lune Noire", "Part de Fortune")


def extraire_points_symboliques(donnees: dict) -> dict:
    """Prépare les seuls faits complémentaires utiles à la rédaction."""
    placements = donnees.get("placements_rs") or {}
    return {
        "placements_rs": {
            nom: placements.get(nom) for nom in POINTS_SYMBOLIQUES if placements.get(nom)
        },
        "aspects_internes_rs": [
            aspect for aspect in donnees.get("aspects_internes_rs") or []
            if (
                {aspect.get("planete1"), aspect.get("planete2")} & set(POINTS_SYMBOLIQUES)
                and float(aspect.get("orbe", 999)) <= 3.0
            )
        ],
        "aspects_rs_natal": [
            aspect for aspect in donnees.get("aspects_rs_natal") or []
            if (
                {aspect.get("point_rs"), aspect.get("point_natal")} & set(POINTS_SYMBOLIQUES)
                and float(aspect.get("orbe", 999)) <= 3.0
            )
        ],
    }


def construire_prompt_points_symboliques(donnees: dict) -> str:
    """Construit le prompt sans élever ces points au rang de facteurs directeurs."""
    points = traduire_pour_affichage(extraire_points_symboliques(donnees))
    return f"""Tu rédiges exclusivement le chapitre complémentaire d'une révolution solaire, en français et au tutoiement.

Titre unique et obligatoire :
## Points symboliques complémentaires

Les données JSON sont la seule source astrologique autorisée.

RÈGLES DE LECTURE
- Lis le Nœud Nord, le Nœud Sud, la Lune Noire et la Part de Fortune comme des confirmations ou nuances. Ils ne passent jamais avant l'Ascendant RS, ses maîtres, le Soleil, la Lune, une figure majeure ou le maître de l'année.
- Relie-les aux dynamiques déjà installées, sans réécrire les chapitres précédents ni inventer un nouveau thème.
- Ne cite un aspect ou une maison que s'il figure explicitement dans les données.
- Le Soleil RS–natal n'est jamais interprété.
- Formule des manifestations concrètes et plausibles. Prends position, mais ne présente pas un fait précis comme garanti et ne pose aucun diagnostic.
- Ne mentionne ni transit, ni diviseur, ni participant, ni dates précises.

VOIX
- Tutoiement direct, texte vivant, incarné et agréable à lire.
- Une ou deux pointes d'humour sec sont bienvenues si elles servent le propos.
- Longueur cible : 500 à 650 mots.

DONNÉES
{json.dumps(points, ensure_ascii=False, indent=2)}
"""
