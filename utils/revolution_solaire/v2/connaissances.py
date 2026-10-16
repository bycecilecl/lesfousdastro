"""Sélection documentaire RS, sans calcul astrologique ni appel IA.

Les bibliothèques restent sur disque. Seules les fiches correspondant aux
faits RS déjà calculés peuvent alimenter le premier prompt.
"""

import hashlib
import json
import unicodedata
from pathlib import Path


BDD = Path(__file__).resolve().parent / "bdd"
FICHIERS = ("rs_connaissances_fr.json", "rs_aspects_differencies_fr.json",
            "rs_placements_condenses_riches_fr_v2.json")
VERSION_SELECTION = "selection_rs_3_placements_condenses_v2"


def normaliser(nom):
    return "".join(c for c in unicodedata.normalize("NFD", str(nom).lower())
                   if unicodedata.category(c) != "Mn").strip()


def charger_bases():
    return tuple(json.loads((BDD / nom).read_text(encoding="utf-8")) for nom in FICHIERS)


def empreinte_connaissances():
    """Empêche de réutiliser une analyse antérieure à ces connaissances."""
    empreinte = hashlib.sha256(VERSION_SELECTION.encode("utf-8"))
    for nom in FICHIERS:
        empreinte.update(nom.encode("utf-8"))
        empreinte.update((BDD / nom).read_bytes())
    return empreinte.hexdigest()


def index_unique(fiches, cle):
    index = {}
    for fiche in fiches:
        identifiant = cle(fiche)
        if identifiant in index:
            raise ValueError("Fiches documentaires RS ambiguës : " + str(identifiant))
        index[identifiant] = fiche
    return index


def cle_aspect(planete_1, planete_2, aspect):
    return (*sorted((normaliser(planete_1), normaliser(planete_2))), normaliser(aspect))


def selectionner_fiches_rs(faits):
    """Associe les placements/aspects calculés à leurs fiches, dans les deux sens.

    Une absence documentaire ne supprime jamais un fait du thème. Les fiches
    restent des interprétations ; elles ne rejoignent pas le catalogue de faits.
    """
    placements, aspects, condenses = charger_bases()
    index_placements = index_unique(
        (f for f in placements["sections"] if f.get("type") == "placement_maison"
         and f.get("cadre_1") == "rs" and f.get("cadre_2") is None),
        lambda f: (normaliser(f["planete_1"]), f["maison"]))
    if condenses.get("cadre") != "revolution_solaire":
        raise ValueError("La base de placements condensés doit concerner la RS.")
    index_condenses = index_unique(condenses["placements"],
                                  lambda f: (normaliser(f["planete"]), f["maison"]))
    if index_condenses.keys() != index_placements.keys():
        raise ValueError("Les placements condensés ne couvrent pas les mêmes planètes et maisons que la source.")
    for cle, fiche in index_placements.items():
        texte = index_condenses[cle].get("interpretation")
        if not isinstance(texte, str) or not texte.strip():
            raise ValueError("Interprétation condensée vide : " + str(cle))
        # Garde les références documentaires d'origine, mais utilise uniquement
        # le condensé fourni. Aucun retour silencieux aux longs textes.
        index_placements[cle] = {**fiche, "interpretation_fr": texte}
    index_aspects = index_unique(
        (f for f in aspects["aspects"] if f.get("cadre_1") == f.get("cadre_2") == "rs"),
        lambda f: cle_aspect(f["planete_1"], f["planete_2"], f["aspect"]))
    index_nuances = index_unique(aspects["nuances_source"], lambda f: f["id"])
    selection = {"placements": [], "aspects": [], "nuances": [], "non_couverts": []}
    nuances = {}
    for reference, fait in faits.items():
        if not reference.startswith("RS.") or fait.get("source") != "rs":
            continue
        valeur = fait["valeur"]
        if fait["type"] == "positions":
            fiche = index_placements.get((normaliser(fait["objet"]), valeur["maison"]))
            categorie = "placements"
        elif fait["type"] == "aspects":
            fiche = index_aspects.get(cle_aspect(valeur["planete1"], valeur["planete2"], valeur["aspect"]))
            categorie = "aspects"
        else:
            continue
        if fiche is None:
            selection["non_couverts"].append(reference)
            continue
        selection[categorie].append({"fait": reference, "fiche": fiche})
        if categorie == "aspects":
            for identifiant in dict.fromkeys(fiche.get("nuances_typees_ids", [])
                                            + fiche.get("nuances_generales_ids", [])):
                if identifiant not in index_nuances:
                    raise ValueError("Nuance documentaire RS absente : " + identifiant)
                nuance = nuances.setdefault(identifiant, {"faits": [], "fiche": index_nuances[identifiant]})
                nuance["faits"].append(reference)
    selection["nuances"] = list(nuances.values())
    return selection


def texte_fr(fiche):
    """Reprend le texte français de la BDD, sans résumé ni réécriture."""
    texte = fiche.get("interpretation_fr") or fiche.get("traduction_fr")
    if not isinstance(texte, str) or not texte.strip():
        raise ValueError("Texte français absent de la fiche : " + fiche["id"])
    return texte


def pages_pdf(fiche, *, paire=False):
    prefixe = "page_pdf_paire_" if paire else "page_pdf_"
    return [fiche[prefixe + "debut"], fiche[prefixe + "fin"]]


def construire_reperes_rs(faits):
    """Ne transporte ni texte anglais, ni catalogue complet, ni métadonnées inutiles."""
    selection = selectionner_fiches_rs(faits)
    reperes = {
        "provenance": {
            "placements": "Condensés fournis dans rs_placements_condenses_riches_fr_v2.json ; références Mary Shea associées par planète et maison, pas des citations intégrales",
            "aspects": "Compléments éditoriaux IA ou reformulations de source, selon origine ; à relire",
        },
        "placements": [], "aspects": [], "nuances": [],
        # Ce suivi reste dans l'archive locale ; il n'est pas envoyé au modèle.
        "faits_sans_fiche": selection["non_couverts"],
    }
    for element in selection["placements"]:
        fiche = element["fiche"]
        reperes["placements"].append({
            "fait": element["fait"], "fiche": fiche["id"],
            "texte": texte_fr(fiche), "pages_pdf": pages_pdf(fiche),
        })
    for element in selection["aspects"]:
        fiche = element["fiche"]
        reperes["aspects"].append({
            "fait": element["fait"], "fiche": fiche["id"],
            "texte": texte_fr(fiche), "origine": fiche["origine_interpretation"],
            "source_paire": fiche["source_paire_id"],
            "source_aspect": fiche["source_regle_aspect_id"],
            "pages_pdf": pages_pdf(fiche, paire=True),
        })
    for element in selection["nuances"]:
        fiche = element["fiche"]
        reperes["nuances"].append({
            "faits": element["faits"], "fiche": fiche["id"],
            "texte": fiche["texte_fr"], "conditions": fiche["conditions"],
            "nature": fiche["nature"], "source": fiche["source_section_id"],
            "pages_pdf": pages_pdf(fiche),
        })
    return reperes


def reperes_pour_prompt(reperes):
    """Interprétations et liens aux faits, sans références bibliographiques.

    Les textes restent inchangés. La provenance et les identifiants de fiches
    sont conservés séparément dans les archives, pas dans l'entrée du modèle.
    """
    champs = {
        "placements": ("fait", "texte"),
        "aspects": ("fait", "texte"),
        "nuances": ("faits", "texte", "conditions"),
    }
    return {
        categorie: [{cle: element[cle] for cle in autorises if cle in element}
                    for element in reperes[categorie]]
        for categorie, autorises in champs.items()
    }


def reperes_documentaires_a_archiver(dossier, repartition):
    """Sélection documentaire complète des faits attribués au bloc."""
    attribues = {cle for liste in repartition.values() for cle in liste}
    documentation = {
        cle: fait for cle, fait in dossier["faits"].items()
        if cle in attribues and fait["source"] == "rs"
        and fait["type"] in {"positions", "aspects"}
    }
    return construire_reperes_rs(documentation)


def formater_reperes_rs(reperes, references):
    """Un objet par ligne ; les preuves continuent à référencer les faits du relevé."""
    lignes = ["REPÈRES INTERPRÉTATIFS DE LA BDD — RS"]
    lignes.append(json.dumps({"provenance": reperes["provenance"]}, ensure_ascii=False))
    for categorie in ("placements", "aspects", "nuances"):
        lignes.append(categorie.upper())
        for element in reperes[categorie]:
            element = dict(element)
            if "fait" in element:
                element["fait"] = references[element["fait"]]
            if "faits" in element:
                element["faits"] = [references[cle] for cle in element["faits"]]
            lignes.append(json.dumps(element, ensure_ascii=False))
    return "\n".join(lignes)
