"""Préparation d'étapes isolées depuis les appels 1 et 2 archivés, sans génération."""

from copy import deepcopy
import hashlib
from pathlib import Path

from ..archives_generation import lire_json
from . import analyse
from .controle import AnalyseRSInvalide
from .essai_etape2 import preparer_essai_etape2
from .filtrage_aspects import fait_autorise, filtrer_historique
from .releve_rs import references_prompt


def preparer_essai_etape3(source_rs_seule, source_resonances, *, etape="contacts_rs_natal"):
    """Réutilise les textes, retire leurs suivis techniques, conserve leurs limites."""
    if etape not in {"contacts_rs_natal", "superpositions_maisons", "profection"}:
        raise ValueError("Étape isolée non prise en charge depuis ces deux archives.")
    preparation = preparer_essai_etape2(source_rs_seule)
    source = Path(source_resonances).expanduser().resolve()
    factuel_2 = lire_json(source, "dossier_factuel.json")
    resultat = lire_json(source / "resonances_natales", "resultat.json")
    controle = lire_json(source / "resonances_natales", "controle.json")
    placements = lire_json(source / "resonances_natales", "controle_lecture.json")
    demande_2 = lire_json(source, "demande.json")
    prompt_2 = lire_json(source / "resonances_natales", "prompt.json")
    if any(v is None for v in (factuel_2, resultat, controle, placements, demande_2, prompt_2)):
        raise ValueError("Archive de l'appel 2 incomplète : aucun nouvel appel lancé.")
    if factuel_2 != preparation["factuel"]:
        raise ValueError("Les deux archives ne correspondent pas au même dossier astrologique.")
    if demande_2.get("sources", {}).get("dossier_source") != preparation["provenance"]["dossier_source"]:
        raise ValueError("L'appel 2 ne provient pas de la première archive choisie.")
    if controle.get("statut") != "valide" or placements.get("erreurs"):
        raise AnalyseRSInvalide("L'appel 2 choisi n'a pas passé ses contrôles : aucun nouvel appel lancé.")
    champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet", "exemples")
    historique = {"enjeux": []}
    ids = set()
    if not isinstance(resultat.get("enjeux"), list):
        raise AnalyseRSInvalide("Enjeux de l'appel 2 illisibles.")
    for enjeu in resultat["enjeux"]:
        if not isinstance(enjeu, dict) or any(champ not in enjeu for champ in champs):
            raise AnalyseRSInvalide("Enjeu de l'appel 2 incomplet.")
        identifiant = enjeu["id"]
        if (not isinstance(identifiant, str) or not identifiant.startswith("resonances_natales-")
                or identifiant in ids):
            raise AnalyseRSInvalide("Identifiants d'enjeux de l'appel 2 ambigus.")
        ids.add(identifiant)
        exemples = enjeu["exemples"]
        if not isinstance(exemples, list) or any(not isinstance(e, dict) for e in exemples):
            raise AnalyseRSInvalide("Exemples de l'appel 2 illisibles.")
        for references in [enjeu["preuves"]] + [e.get("preuves") for e in exemples]:
            if (not isinstance(references, list) or not references or
                    any(not isinstance(cle, str) or cle not in factuel_2["faits"] for cle in references)):
                raise AnalyseRSInvalide("Référence de l'appel 2 inconnue : aucun nouvel appel lancé.")
        historique["enjeux"].append({champ: deepcopy(enjeu[champ]) for champ in champs})
    preparation["analyses"]["resonances_natales"] = historique
    preparation["analyses"] = filtrer_historique(preparation["analyses"], factuel_2["faits"])
    faits_themes = {cle: fait for cle, fait in factuel_2["faits"].items()
                    if fait.get("source") in {"natal", "rs"}}
    libelles = references_prompt({"etape": "resonances_natales", "faits": faits_themes})
    anciens_aspects = [cle for cle, fait in faits_themes.items()
                      if not fait_autorise(fait) and libelles[cle] in prompt_2["prompt"]]
    preparation["statut_historique"]["resonances_natales"] = {
        "statut_controle_source": controle["statut"],
        "statut_placements_source": placements.get("statut", "inconnu"),
        "nombre_aspects_exclus_presents_dans_prompt_source": len(anciens_aspects),
        "limite": ("Cette analyse a reçu des aspects désormais exclus ; ses lectures restent inchangées."
                   if anciens_aspects else "Cette analyse reste une interprétation, pas une source de faits."),
    }
    preparation["provenance"]["dossier_source_resonances"] = str(source)
    noms = ("dossier_factuel.json", "demande.json", "resonances_natales/resultat.json",
            "resonances_natales/reponse.json", "resonances_natales/controle.json",
            "resonances_natales/controle_lecture.json", "resonances_natales/prompt.json")
    preparation["provenance"]["empreintes_sources_resonances"] = {
        nom: hashlib.sha256((source / nom).read_bytes()).hexdigest() for nom in noms}
    if etape == "superpositions_maisons":
        preparation["provenance"]["analyses_omises"] = ["contacts_rs_natal"]
        preparation["provenance"]["raison_omission"] = "Essai de l'appel 4 depuis les appels 1 et 2 uniquement."
    elif etape == "profection":
        preparation["provenance"]["analyses_omises"] = ["contacts_rs_natal", "superpositions_maisons"]
        preparation["provenance"]["raison_omission"] = "Essai de l'appel 5 depuis les appels 1 et 2 uniquement."
    entree = analyse.construire_entree_etape(etape, preparation["factuel"],
                                           preparation["analyses"],
                                           statut_historique=preparation["statut_historique"])
    if etape == "profection":
        # L'archive du nouvel essai reflète l'historique réellement sélectionné.
        # Les textes complets restent dans les fichiers sources des appels 1 et 2.
        preparation["analyses"] = entree["analyses_precedentes"]
    preparation["prompt"] = analyse.construire_prompt_etape(etape, entree)
    return preparation


def preparer_essai_etape4(source_rs_seule, source_resonances):
    """Prépare les superpositions depuis les appels 1 et 2 ; ne lit pas l'appel 3."""
    return preparer_essai_etape3(source_rs_seule, source_resonances, etape="superpositions_maisons")


def preparer_essai_etape5(source_rs_seule, source_resonances):
    """Prépare la profection depuis les appels 1 et 2 ; ne lit pas les appels 3 et 4."""
    return preparer_essai_etape3(source_rs_seule, source_resonances, etape="profection")
