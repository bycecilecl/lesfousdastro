"""Figures simultanées du ciel collectif, sans thème natal."""

from datetime import date
from itertools import combinations

from utils.ciel_collectif import (
    PLANETES, _aspect, _positions,
)

ORBES_FIGURES = {"conjonction": 8, "sextile": 4, "carré": 7, "trigone": 5, "opposition": 8}


def _figures(aspects: list[dict]) -> list[dict]:
    """Figures simultanées, sur les seuls aspects non dissociés du jour."""
    par_paire = {frozenset((a["premiere"], a["seconde"])): a["aspect"] for a in aspects}
    figures = []
    noms = list(PLANETES)
    grands_carres = []
    for groupe in combinations(noms, 4):
        paires = [(frozenset(p), par_paire.get(frozenset(p))) for p in combinations(groupe, 2)]
        oppositions = [paire for paire, aspect in paires if aspect == "opposition"]
        carres = [paire for paire, aspect in paires if aspect == "carré"]
        if len(oppositions) == 2 and len(carres) == 4 and not (oppositions[0] & oppositions[1]):
            grands_carres.append(frozenset(groupe))
            figures.append({"nom": "Grand carré", "planetes": groupe,
                            "detail": " · ".join(groupe)})
    grands_trigones = []
    for trio in combinations(noms, 3):
        paires = [(frozenset(p), par_paire.get(frozenset(p))) for p in combinations(trio, 2)]
        oppositions = [paire for paire, aspect in paires if aspect == "opposition"]
        carres = [paire for paire, aspect in paires if aspect == "carré"]
        trigones = [paire for paire, aspect in paires if aspect == "trigone"]
        if len(oppositions) == 1 and len(carres) == 2 and not any(
            set(trio) <= grand_carre for grand_carre in grands_carres
        ):
            foyer = next(nom for nom in trio if nom not in oppositions[0])
            figures.append({"nom": "T-carré", "planetes": trio,
                            "detail": f"{', '.join(sorted(oppositions[0]))} en opposition · {foyer} au sommet"})
        elif len(trigones) == 3:
            grands_trigones.append(trio)
    diamants = set()
    for trio in grands_trigones:
        for pointe in (nom for nom in noms if nom not in trio):
            for sommet in trio:
                autres = [nom for nom in trio if nom != sommet]
                if (par_paire.get(frozenset((pointe, sommet))) == "opposition"
                        and all(par_paire.get(frozenset((pointe, autre))) == "sextile" for autre in autres)):
                    groupe = frozenset((*trio, pointe))
                    if groupe not in diamants:
                        diamants.add(groupe)
                        figures.append({"nom": "Diamant (cerf-volant)",
                                        "planetes": tuple((*trio, pointe)),
                                        "detail": f"Grand trigone {' · '.join(trio)} · pointe {pointe}"})
    for trio in grands_trigones:
        if not any(set(trio) <= diamant for diamant in diamants):
            figures.append({"nom": "Grand trigone", "planetes": trio,
                            "detail": " · ".join(trio)})
    return figures


def figures_ciel_collectif(jour: date) -> list[dict]:
    """Détecte les figures construites par des aspects présents le même jour."""
    positions = _positions(jour)
    aspects = []
    for premiere, seconde in combinations(PLANETES, 2):
        resultat = _aspect(positions[premiere][0], positions[seconde][0])
        if resultat is None or resultat[1] > ORBES_FIGURES[resultat[0]]:
            continue
        aspects.append({"premiere": premiere, "seconde": seconde, "aspect": resultat[0]})
    return _figures(aspects)
