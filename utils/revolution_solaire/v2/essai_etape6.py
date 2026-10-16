"""Prépare les transits depuis les archives 1, 2 et 5, sans génération."""

from copy import deepcopy
import hashlib
from pathlib import Path

from ..archives_generation import lire_json
from . import analyse
from .controle import AnalyseRSInvalide
from .essai_etape3 import preparer_essai_etape3
from .filtrage_aspects import filtrer_historique


def preparer_essai_etape6(source_rs_seule, source_resonances, source_profection):
    preparation = preparer_essai_etape3(source_rs_seule, source_resonances)
    source = Path(source_profection).expanduser().resolve()
    fichiers = ("dossier_factuel.json", "demande.json", "profection/resultat.json",
                "profection/reponse.json", "profection/controle.json", "profection/controle_lecture.json")
    contenus = {nom: lire_json(source, nom) for nom in fichiers}
    if any(valeur is None for valeur in contenus.values()):
        raise ValueError("Archive de profection incomplète : aucun nouvel appel lancé.")
    if contenus["dossier_factuel.json"] != preparation["factuel"]:
        raise ValueError("La profection ne correspond pas au même dossier astrologique.")
    sources = contenus["demande.json"].get("sources", {})
    for cle in ("dossier_source", "dossier_source_resonances"):
        if sources.get(cle) != preparation["provenance"][cle]:
            raise ValueError("La profection ne provient pas des deux archives choisies.")
    controle = contenus["profection/controle.json"]
    placements = contenus["profection/controle_lecture.json"]
    if controle.get("statut") != "valide" or placements.get("erreurs"):
        raise AnalyseRSInvalide("La profection choisie n'a pas passé ses contrôles techniques.")
    resultat = contenus["profection/resultat.json"]
    champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet", "exemples")
    if not isinstance(resultat.get("enjeux"), list):
        raise AnalyseRSInvalide("Enjeux de profection illisibles.")
    historique, ids = {"enjeux": []}, set()
    for enjeu in resultat["enjeux"]:
        if not isinstance(enjeu, dict) or any(champ not in enjeu for champ in champs):
            raise AnalyseRSInvalide("Enjeu de profection incomplet.")
        identifiant = enjeu["id"]
        if not isinstance(identifiant, str) or not identifiant.startswith("profection-") or identifiant in ids:
            raise AnalyseRSInvalide("Identifiants de profection ambigus.")
        ids.add(identifiant)
        exemples = enjeu["exemples"]
        if not isinstance(exemples, list) or any(not isinstance(e, dict) for e in exemples):
            raise AnalyseRSInvalide("Exemples de profection illisibles.")
        for references in [enjeu["preuves"]] + [e.get("preuves") for e in exemples]:
            if (not isinstance(references, list) or not references or
                    any(not isinstance(cle, str) or cle not in preparation["factuel"]["faits"] for cle in references)):
                raise AnalyseRSInvalide("Référence de profection inconnue.")
        historique["enjeux"].append({champ: deepcopy(enjeu[champ]) for champ in champs})
    preparation["analyses"]["profection"] = historique
    preparation["analyses"] = filtrer_historique(preparation["analyses"], preparation["factuel"]["faits"])
    preparation["statut_historique"]["profection"] = {
        "statut_controle_source": controle["statut"],
        "statut_placements_source": placements.get("statut", "inconnu"),
        "limite": "Contrôles techniques passés ; la lecture reste une interprétation, pas une source de faits.",
    }
    preparation["provenance"].update({
        "dossier_source_profection": str(source),
        "empreintes_sources_profection": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest() for nom in fichiers},
        "analyses_omises": ["contacts_rs_natal", "superpositions_maisons"],
        "raison_omission": "Essai de l'appel 6 depuis les appels 1, 2 et 5 uniquement.",
    })
    entree = analyse.construire_entree_etape("activations_annuelles", preparation["factuel"],
                                           preparation["analyses"], statut_historique=preparation["statut_historique"])
    preparation["analyses"] = entree["analyses_precedentes"]
    preparation["prompt"] = analyse.construire_prompt_etape("activations_annuelles", entree)
    return preparation
