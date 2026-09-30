"""Noms affichés dans les rapports de révolution solaire."""

from __future__ import annotations


NOMS_AFFICHAGE = {
    "Rahu": "Nœud Nord",
    "Ketu": "Nœud Sud",
}


def nom_affiche(nom: str) -> str:
    """Traduit un identifiant astrologique interne pour les lectrices."""
    return NOMS_AFFICHAGE.get(nom, nom)


def traduire_pour_affichage(valeur):
    """Traduit récursivement les noms internes dans un contexte de prompt."""
    if isinstance(valeur, str):
        return nom_affiche(valeur)
    if isinstance(valeur, list):
        return [traduire_pour_affichage(item) for item in valeur]
    if isinstance(valeur, dict):
        return {
            nom_affiche(cle) if isinstance(cle, str) else cle: traduire_pour_affichage(item)
            for cle, item in valeur.items()
        }
    return valeur
