"""Bloc Soleil/Lune : faits sélectionnés, mémoire courte, un seul appel manuel."""

import json
import re
from copy import deepcopy
from pathlib import Path

from ..analyse import parser_json_reponse
from .plan_partage import ajouter_plan_entree, consignes_plan, schema_avec_plan, suivre_fils
from ..connaissances import construire_reperes_rs, reperes_pour_prompt
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from .bloc_1 import (
    ROMAINS_MAISONS, RE_MAISON, consignes_communes_bloc_1, contient_position,
    nettoyer_parasites, retirer_note_documentaire, schema_bloc_1,
    adapter_prompt_sans_bdd, reperes_sans_bdd,
)
from .repartition import repartir_pour_bloc, repartir_sections_bloc_2
from .suivi_memoire import fenetres, normaliser_texte, reperer_citation
from .appuis_memoire import copier_mecanisme, verifier_appuis


VERSION = "rs_bloc_2_soleil_lune_5_appuis_memoire"
MAX_TOKENS = 6000
PROMPT_PATH = Path(__file__).with_name("prompt_bloc_2.txt")
AUTRES_POINTS = re.compile(r"\b(?:mercure|venus|mars|jupiter|saturne|uranus|neptune|pluton|chiron|rahu|ketu|mc|fc|ascendant|descendant|milieu du ciel|fond du ciel|part de fortune|lune noire)\b")


def selectionner_faits_bloc_2(dossier):
    """Luminaires RS, contacts de leur côté RS, positions de leurs partenaires."""
    catalogue = dossier["faits"]
    luminaires = {"Soleil", "Lune"}
    retenus = {f"{ref}.positions.{nom}" for ref in ("RS", "NATAL") for nom in luminaires}
    relais_rs, cibles_natales = set(luminaires), set(luminaires)
    for cle, fait in catalogue.items():
        if not fait_autorise(fait):
            continue
        v, categorie = fait["valeur"], fait["type"]
        if fait["source"] == "rs":
            if categorie == "aspects" and {v["planete1"], v["planete2"]} & luminaires:
                retenus.add(cle)
                relais_rs.update({v["planete1"], v["planete2"]})
            elif categorie == "angularites" and v["point"] in luminaires:
                retenus.add(cle)
                relais_rs.add(v["angle"])
            elif categorie == "configurations" and set(v["planetes"]) & luminaires:
                retenus.add(cle)
                relais_rs.update(v["planetes"])
        elif categorie == "contact" and v["point_rs"] in luminaires:
            retenus.add(cle)
            cibles_natales.add(v["point_natal"])
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points.") and fait["objet"] in luminaires:
            retenus.add(cle)
        elif fait["source"] == "natal" and categorie == "aspects" and {v["planete1"], v["planete2"]} & luminaires:
            # Résonance contextuelle, jamais un portrait natal développé ici.
            retenus.add(cle)
            cibles_natales.update({v["planete1"], v["planete2"]})
    for ref, noms in (("RS", relais_rs), ("NATAL", cibles_natales)):
        for nom in sorted(noms):
            retenus.update({f"{ref}.positions.{nom}", f"{ref}.angles.{nom}"})
            position = dossier[ref.lower()]["positions"].get(nom)
            if position:
                maison = str(position["maison"])
                retenus.update({f"{ref}.cuspides.{maison}", f"{ref}.maitrises.{maison}"})
    # Les maîtres des maisons des luminaires sont des références, pas un
    # nouveau portrait de leurs maîtres déjà étudiés au bloc précédent.
    for nom in sorted(luminaires):
        maison = str(dossier["rs"]["positions"][nom]["maison"])
        retenus.add(f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}")
        for maitre in dossier["rs"]["maitrises"][maison]["maitres"]:
            retenus.add(f"RS.positions.{maitre}")
    interceptes = dossier["rs"]["interceptions"].get("signes_interceptes", [])
    if any(dossier["rs"]["positions"][nom]["signe"] in interceptes for nom in luminaires):
        retenus.add("RS.interceptions.ensemble")
    return {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}


def construire_reperes_calcules_bloc_2(dossier):
    """Formate les résultats archivés, sans recalcul ni valeur de profil en dur."""
    catalogue = dossier["faits"]
    maitre_annee = dossier["profection"]["maitre_annee"]["nom"]
    reperes = {
        "luminaires_rs": {}, "cuspides_rs": {},
        "maitre_profection": maitre_annee,
        "phrases_factuelles": [],
    }
    for nom in ("Soleil", "Lune"):
        maison = catalogue[f"RS.positions.{nom}"]["valeur"]["maison"]
        projection = catalogue[f"SUPERPOSITION.rs_vers_natal.points.{nom}"]["valeur"]["maison_cible"]
        reperes["luminaires_rs"][nom] = {"maison_rs": maison, "maison_natale_de_projection": projection}
        article = "Le" if nom == "Soleil" else "La"
        reperes["phrases_factuelles"].append(
            f"{article} {nom} RS est en maison {maison} de la RS et se projette en maison {projection} natale.")
        if str(maison) in reperes["cuspides_rs"]:
            continue
        cible = catalogue[f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}"]["valeur"]["maison_cible"]
        maitres = list(catalogue[f"RS.maitrises.{maison}"]["valeur"]["maitres"])
        reperes["cuspides_rs"][str(maison)] = {"maison_natale_de_projection": cible, "maitres_rs": maitres}
        reperes["phrases_factuelles"].append(
            f"La cuspide {maison} RS tombe en maison {cible} natale ; cette projection concerne la cuspide.")
        sujet = "Le maître" if len(maitres) == 1 else "Les maîtres"
        verbe = "est" if len(maitres) == 1 else "sont"
        reperes["phrases_factuelles"].append(
            f"{sujet} de la cuspide {maison} RS {verbe} {' et '.join(maitres)} ; "
            f"le maître de la profection est {maitre_annee}. "
            "Ces rôles sont distincts, même lorsqu'une même planète les porte.")
    return reperes


def preparer_memoire_bloc_1(memoire, dossier, texte_bloc_1):
    """Mémoire éditoriale seulement ; aucune lecture ni position recalculée."""
    mecanismes, ecartes = [], []
    for m in memoire.get("mecanismes", []):
        if not isinstance(m, dict) or not all(isinstance(m.get(k), str) for k in ("sujet", "role", "resume")):
            continue
        contenu = normaliser_texte(" ".join(m[k] for k in ("sujet", "role", "resume")))
        if any(contient_position(m[k]) for k in ("sujet", "role", "resume")) or re.search(r"\b(?:chiron|rahu|ketu|noeuds)\b", contenu):
            ecartes.append({"mecanisme": m, "motif": "Position ou point exclu de la mémoire transmise."})
            continue
        mecanismes.append(copier_mecanisme(m))
    references = [c["reference"] for c in memoire.get("faits_cites", [])
                  if isinstance(c, dict) and isinstance(c.get("reference"), str)
                  and c["reference"] in dossier["faits"] and fait_autorise(dossier["faits"][c["reference"]])]
    dignite = dossier["natal"]["positions"]["Soleil"].get("dignite_essentielle")
    deja = bool(dignite and any(re.search(r"\bsoleil\b", phrase) and
                re.search(r"\b" + re.escape(normaliser_texte(dignite)) + r"\b", phrase)
                for phrase, _ in fenetres(texte_bloc_1)))
    return {"mecanismes": mecanismes, "faits_deja_cites": list(dict.fromkeys(references)),
            "dignite_solaire_deja_mentionnee": deja,
            "nature": "Suivi éditorial du bloc conservé, pas une source de faits ni une validation."}, ecartes


def construire_prompt_bloc_2(dossier, *, memoire, proprietaires_precedents, texte_bloc_1, genre="", plan=None, utiliser_bdd=True):
    faits = selectionner_faits_bloc_2(dossier)
    nouveaux, deja_traites, _ = repartir_pour_bloc(faits, 2, proprietaires_precedents, faits_a_developper=())
    parts = repartir_sections_bloc_2(nouveaux, dossier)
    possedes = {cle for liste in parts.values() for cle in liste}
    _, _, proprietaires = repartir_pour_bloc(faits, 2, proprietaires_precedents, faits_a_developper=possedes)
    documentation = {cle: f for cle, f in nouveaux.items() if cle in possedes and f["source"] == "rs"
                     and f["type"] in {"positions", "aspects"}}
    aides = retirer_note_documentaire(construire_reperes_rs(documentation)) if utiliser_bdd else reperes_sans_bdd()
    for fiche in aides["placements"]:
        fiche["texte"] = fiche["texte"].split("\n\nPrécisions de la source", 1)[0].rstrip()
    editoriale, ecartes = preparer_memoire_bloc_1(memoire, dossier, texte_bloc_1)
    entree = {
        "cycle": {k: dossier["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
        "genre": {"female": "féminin", "male": "masculin"}.get(genre, genre),
        "faits_calcules": {**compacter_faits(nouveaux),
                           "REPERES_CALCULES": construire_reperes_calcules_bloc_2(dossier)},
        "repartition_des_faits": parts,
        "references_de_contexte": [cle for cle in nouveaux if cle not in possedes],
        "deja_traites": {cle: {"bloc_proprietaire": f["bloc_proprietaire"],
                                  "fait": compacter_faits({cle: f["fait"]})[cle]}
                         for cle, f in deja_traites.items()},
        "aides_interpretatives_rs": reperes_pour_prompt(aides),
        "memoire_editoriale_bloc_1": editoriale,
    }
    ajouter_plan_entree(entree, plan)
    prompt = consignes_communes_bloc_1() + "\n" + PROMPT_PATH.read_text(encoding="utf-8")
    prompt += consignes_plan(plan)
    prompt = adapter_prompt_sans_bdd(prompt, entree, utiliser_bdd)
    prompt += "\nDONNÉES DU BLOC 2\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    return prompt, faits, entree, proprietaires, ecartes


def schema_bloc_2(plan=None):
    return schema_bloc_1(plan=plan)


def contradictions_maisons_luminaires(texte, dossier):
    """Diagnostic lexical, sans arrêt ni correction du texte."""
    sortie = []
    for phrase, _ in fenetres(texte):
        tokens = [a or b for a, b in RE_MAISON.findall(phrase)]
        numeros = {int(t) if t.isdigit() else ROMAINS_MAISONS[t] for t in tokens}
        sujets = [nom for nom in ("Soleil", "Lune") if re.search(r"\b" + nom.lower() + r"\b", phrase)]
        if not numeros or not sujets:
            continue
        if AUTRES_POINTS.search(phrase):
            sortie.append({"phrase": phrase, "statut": "a_relire", "raison": "Autre point nommé dans la phrase."})
            continue
        natal = bool(re.search(r"\bnatal(?:e|s|es|ement)?\b|\bnativement\b", phrase))
        rs = bool(re.search(r"\brs\b|\brevolution solaire\b", phrase))
        if len(numeros) != 1 or len(sujets) != 1 or natal and rs:
            sortie.append({"phrase": phrase, "statut": "a_relire", "raison": "Association de sujets, cadres ou maisons ambiguë."})
            continue
        cadres = ("natal",) if natal else ("rs",) if rs else ("rs", "natal")
        attendues = {dossier[c]["positions"][sujets[0]]["maison"] for c in cadres}
        if not numeros & attendues:
            sortie.append({"phrase": phrase, "statut": "contradiction", "maisons_attendues": sorted(attendues)})
    return sortie


def generer_bloc_2(dossier, *, appeler, memoire, proprietaires_precedents, texte_bloc_1, genre="", plan=None, utiliser_bdd=True):
    prompt, faits, entree, _, ecartes_source = construire_prompt_bloc_2(
        dossier, memoire=memoire, proprietaires_precedents=proprietaires_precedents,
        texte_bloc_1=texte_bloc_1, genre=genre, plan=plan, utiliser_bdd=utiliser_bdd)
    resultat = parser_json_reponse(appeler(prompt, max_tokens=MAX_TOKENS, temperature=0.5,
        reflexion="disabled", niveau_effort="low", schema_sortie=schema_bloc_2(plan=plan)))
    # Copie avant toute sélection. La réponse complète est déjà archivée par
    # _etape_archivee avant ce parsing ; ce champ conserve aussi la déclaration.
    memoire_brute = deepcopy(resultat.get("memoire"))
    texte = resultat.get("texte")
    parasites = []
    if isinstance(texte, str):
        texte, parasites = nettoyer_parasites(texte)
    corps = texte if isinstance(texte, str) else ""
    alertes = [] if corps.strip() else ["Texte du bloc absent ou vide."]
    maisons = contradictions_maisons_luminaires(corps, dossier)
    alertes.extend("Maison incohérente : " + d["phrase"] for d in maisons if d["statut"] == "contradiction")
    declaree = resultat.get("memoire")
    if not isinstance(declaree, dict):
        alertes.append("Mémoire absente ou illisible.")
        declaree = {}
    mecanismes, ecartes, citations, suivi, reperes, abordes = [], [], [], [], set(), set()
    suivi_appuis = []
    declarations = declaree.get("mecanismes", [])
    for m in declarations if isinstance(declarations, list) else []:
        if not isinstance(m, dict) or not all(isinstance(m.get(k), str) and m[k].strip() for k in ("sujet", "role", "resume")):
            alertes.append("Mécanisme incomplet dans la mémoire.")
        elif any(contient_position(m[k]) for k in ("sujet", "role", "resume")):
            ecartes.append(m)
        else:
            mecanisme, diagnostic_appuis = verifier_appuis(m, dossier["faits"], faits)
            mecanismes.append(mecanisme)
            suivi_appuis.append(diagnostic_appuis)
    attribues = {cle for liste in entree["repartition_des_faits"].values() for cle in liste}
    declarations = declaree.get("faits_cites", [])
    for c in declarations if isinstance(declarations, list) else []:
        if not isinstance(c, dict) or not isinstance(c.get("reference"), str) or c["reference"] not in faits:
            alertes.append("Référence de mémoire illisible ou inconnue.")
            continue
        ref = c["reference"]
        if faits[ref]["type"] not in {"aspects", "contact"}:
            # Hors périmètre du repérage, sans bruit dans les citations à relire.
            # La déclaration reste dans memoire_brute et dans reponse.json.
            continue
        repere, raison = reperer_citation(corps, faits[ref], c.get("extrait"))
        # Une référence de contexte ne devient pas un développement possédé,
        # mais ce classement ne doit pas masquer une contradiction détectée.
        if ref not in attribues and not raison.startswith("Contradiction"):
            repere, raison = False, "À relire : référence déjà traitée ou de contexte, aucun développement attribué au bloc 2."
        if repere:
            statut = "a_relire" if raison.startswith("À relire") else "repere"
        elif raison.startswith("Contradiction"):
            statut = "contradiction"
        else:
            statut = "a_relire"
        suivi.append({"reference": ref, "statut": statut, "raison": raison})
        if repere:
            if ref not in abordes:
                citations.append({"reference": ref, "extrait": c.get("extrait"), "statut": statut})
            abordes.add(ref)
            if statut == "repere":
                reperes.add(ref)
        elif statut == "contradiction":
            alertes.append(ref + " — " + raison)
    if corps.strip() and not mecanismes:
        alertes.append("Mémoire sans mécanisme : les blocs suivants ne disposeront pas du résumé de cette lecture.")
    return suivre_fils({**resultat, "texte": texte, "memoire_brute": memoire_brute,
            "memoire": {"mecanismes": mecanismes, "faits_cites": citations},
            "diagnostic": {"alertes": alertes, "nombre_mots": len(corps.split()),
                "maisons_a_relire": maisons, "mecanismes_ecartes": ecartes,
                "suivi_appuis": suivi_appuis,
                "memoire_source_elements_non_transmis": ecartes_source, "parasites_retires": parasites,
                "faits_cites_reperes": [cle for cle in faits if cle in reperes],
                "faits_abordes": [cle for cle in faits if cle in abordes],
                "faits_non_reperes": [cle for cle in faits if cle in attribues and cle not in abordes],
                "suivi_citations": suivi, "citations_a_relire": [d for d in suivi if d["statut"] == "a_relire"],
                "mode_controle": "reperage_lexical_non_validation", "validation_humaine": False}}, plan, 2)
