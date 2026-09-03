PLANETES_NIVEAU_1 = {
    "Soleil", "Lune", "Ascendant", "MC",
    "Saturne", "Pluton", "Uranus", "Mars"
}

PLANETES_NIVEAU_2 = {
    "Mercure", "Vénus", "Jupiter", "Neptune", "Chiron", "Lune Noire"
}

PLANETES_NIVEAU_3 = {
    "Junon", "Part de Fortune", "Point d’Illumination", "Rahu", "Ketu"
}

ASPECTS_PRIORITAIRES = {"Conjonction", "Carré", "Opposition"}
ASPECTS_SECONDAIRES = {"Trigone", "Sextile"}


def score_aspect(aspect: dict, maitre_ascendant: str | None = None) -> int:
    p1 = aspect.get("planete1") or aspect.get("p1")
    p2 = aspect.get("planete2") or aspect.get("p2")
    type_aspect = aspect.get("aspect")

    score = 0

    for p in (p1, p2):
        if p == maitre_ascendant:
            score += 6
        elif p in PLANETES_NIVEAU_1:
            score += 5
        elif p in PLANETES_NIVEAU_2:
            score += 3
        elif p in PLANETES_NIVEAU_3:
            score += 1

    if type_aspect in ASPECTS_PRIORITAIRES:
        score += 5
    elif type_aspect in ASPECTS_SECONDAIRES:
        score += 2

    try:
        orbe = float(str(aspect.get("orbe", 99)).replace(",", "."))
        score += max(0, round(5 - orbe))
    except Exception:
        pass

    # --- Pondération spéciale Lune Noire ---
    if "Lune Noire" in (p1, p2):

        if type_aspect == "Conjonction":
            score += 6

        elif type_aspect in {"Carré", "Opposition"}:
            score += 4

        elif type_aspect == "Trigone":
            score += 1

        elif type_aspect == "Sextile":
            score -= 2

    return score


def filtrer_aspects_par_score(
    aspects: list[dict],
    seuil_min: int = 10,
    maitre_ascendant: str | None = None,
) -> list[dict]:
    """
    Retourne les aspects dont le score psychologique est suffisant,
    triés du plus important au moins important.
    """
    aspects_scores = [
        (aspect, score_aspect(aspect, maitre_ascendant=maitre_ascendant))
        for aspect in aspects
    ]

    aspects_scores = [
        (aspect, score)
        for aspect, score in aspects_scores
        if score >= seuil_min
    ]

    aspects_scores.sort(key=lambda item: item[1], reverse=True)

    return [aspect for aspect, score in aspects_scores]