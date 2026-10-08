"""Accords grammaticaux connus pour les rapports de révolution solaire."""

from __future__ import annotations

import re


def genre_grammatical(valeur: str | None) -> str:
    normalise = str(valeur or "").strip().lower()
    if normalise in {"male", "homme", "masculin"}:
        return "masculin"
    if normalise in {"female", "femme", "féminin", "feminin"}:
        return "féminin"
    return "non précisé"


def accorder_formes_inclusives(texte: str, genre: str | None) -> str:
    """Résout les formes à point médian usuelles quand le genre est connu."""
    accord = genre_grammatical(genre)
    if accord == "non précisé":
        return texte

    def remplacer(match: re.Match) -> str:
        base, pluriel = match.group("base"), bool(match.group("pluriel"))
        return base + ("e" if accord == "féminin" else "") + ("s" if pluriel else "")

    return re.sub(
        r"(?P<base>\b[^\W\d_]+)[·.]e(?P<pluriel>[·.]?s)?\b",
        remplacer,
        texte,
        flags=re.UNICODE,
    )
