"""Raccord des mémoires aux faits reçus ; diagnostics sans blocage ni appel IA."""

from copy import deepcopy
import re

from ..filtrage_aspects import fait_autorise
from .suivi_memoire import normaliser_texte


PLANETES = ("Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton")


def copier_mecanisme(mecanisme, champs=("sujet", "role", "resume")):
    """L'absence d'appuis reste distincte d'une liste vide ou mal formée."""
    copie = {k: deepcopy(mecanisme[k]) for k in champs}
    if "appuis" in mecanisme:
        copie["appuis"] = deepcopy(mecanisme["appuis"])
    return copie


def cumuler_memoires(memoires, numero, nouvelle):
    """Archive les mémoires de travail, pas leurs vues raccourcies pour les prompts."""
    return {**deepcopy(memoires), f"bloc_{numero}": deepcopy(nouvelle)}


def points_du_fait(fait):
    valeur = fait.get("valeur", {})
    points = {valeur.get(k) for k in ("planete1", "planete2", "point_rs", "point_natal",
              "planete_transit", "cible", "point", "angle") if isinstance(valeur.get(k), str)}
    for champ in ("planetes", "maitres"):
        points.update(p for p in valeur.get(champ, []) if isinstance(p, str))
    if fait.get("type") in {"positions", "angles", "points"}:
        points.add(fait.get("objet"))
    return points


def verifier_appuis(mecanisme, catalogue, references_recues=None):
    """Filtre les clés déclarées ; le repérage de noms n'atteste pas leur pertinence."""
    copie = copier_mecanisme(mecanisme)
    suivi = {"sujet": mecanisme["sujet"], "appuis_rejetes": [],
             "planetes_sujet_sans_appui": [], "nature": "Clés et noms seulement ; aucune validation de l'interprétation."}
    if "appuis" not in mecanisme:
        suivi.update(statut="mode_degrade", motif="Ancienne mémoire sans champ appuis.", appuis_valides=[])
        return copie, suivi
    declares = mecanisme["appuis"]
    if not isinstance(declares, list):
        copie["appuis"] = []
        suivi.update(statut="appuis_malformes", motif="Le champ appuis doit être une liste.", appuis_valides=[])
        return copie, suivi
    recues = set(catalogue if references_recues is None else references_recues)
    valides = []
    for cle in declares:
        if not isinstance(cle, str) or cle not in catalogue:
            motif = "Référence absente du catalogue."
        elif cle not in recues:
            motif = "Fait non reçu par ce bloc."
        elif not fait_autorise(catalogue[cle]):
            motif = "Fait exclu de la lecture."
        else:
            if cle not in valides:
                valides.append(cle)
            continue
        suivi["appuis_rejetes"].append({"reference": deepcopy(cle), "motif": motif})
    copie["appuis"] = valides
    points = set().union(*(points_du_fait(catalogue[cle]) for cle in valides)) if valides else set()
    sujet = normaliser_texte(mecanisme["sujet"])
    for planete in PLANETES:
        motif = r"\b" + re.escape(normaliser_texte(planete)) + r"\b"
        if planete == "Lune":
            motif += r"(?! noire)"
        if re.search(motif, sujet) and planete not in points:
            suivi["planetes_sujet_sans_appui"].append(planete)
    suivi.update(statut="appuis_valides" if valides else "sans_appui_valide", appuis_valides=valides)
    return copie, suivi
