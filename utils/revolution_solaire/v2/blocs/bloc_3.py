"""MC et compléments du thème : un bloc conservé, sans réécriture globale."""

from copy import deepcopy
import json
import re
from pathlib import Path

from ..analyse import parser_json_reponse
from .plan_partage import ajouter_plan_entree, consignes_plan, schema_avec_plan, suivre_fils
from ..connaissances import construire_reperes_rs, reperes_pour_prompt
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from .bloc_1 import (RE_MAISON, ROMAINS_MAISONS, consignes_communes_bloc_1,
                     contient_position, nettoyer_parasites, retirer_note_documentaire, schema_bloc_1,
                     adapter_prompt_sans_bdd, reperes_sans_bdd)
from .repartition import repartir_pour_bloc, repartir_sections_bloc_3
from .preparation_bloc_3 import contexte_necessaire, hierarchiser_complements, nettoyer_aides_bloc_3
from .suivi_memoire import fenetres, motif_point, normaliser_texte, reperer_citation
from .appuis_memoire import copier_mecanisme, verifier_appuis


VERSION = "rs_bloc_3_mc_complements_6_appuis_memoire"
MAX_TOKENS = 6000
PROMPT_PATH = Path(__file__).with_name("prompt_bloc_3.txt")


def selectionner_faits_bloc_3(dossier, proprietaires_precedents):
    """RS restante et contacts directs ; pas de calendrier ni de natal complet."""
    catalogue = dossier["faits"]
    maitres_mc = set(dossier["rs"]["maitrises"]["10"]["maitres"])
    acteurs = (set(dossier["rs"]["positions"]) - {"Soleil", "Lune", "Chiron"}) | maitres_mc | {"MC"}
    retenus = {"RS.angles.MC", "RS.cuspides.10", "RS.maitrises.10",
               "SUPERPOSITION.rs_vers_natal.cuspides.10",
               "RS.positions.Soleil", "RS.positions.Lune",
               "SUPERPOSITION.rs_vers_natal.points.Soleil", "SUPERPOSITION.rs_vers_natal.points.Lune",
               *proprietaires_precedents}
    partenaires_rs, partenaires_natals = set(acteurs), set()
    for cle, fait in catalogue.items():
        if not fait_autorise(fait):
            continue
        v, categorie, source = fait["valeur"], fait["type"], fait["source"]
        if source == "rs":
            if categorie in {"positions", "angles"} and fait["objet"] in acteurs:
                retenus.add(cle)
            elif categorie == "aspects":
                paire = {v["planete1"], v["planete2"]}
                # Les aspects des luminaires ont leur développement au bloc 2.
                # Un luminaire maître du MC peut ici intervenir sous ce rôle.
                if paire & acteurs and (not paire & {"Soleil", "Lune"} or paire & maitres_mc or "MC" in paire):
                    retenus.add(cle)
                    partenaires_rs.update(paire)
            elif categorie == "angularites" and (v["point"] in acteurs or v["angle"] == "MC"):
                retenus.add(cle)
                partenaires_rs.update({v["point"], v["angle"]})
            elif categorie == "configurations" and set(v["planetes"]) & acteurs:
                retenus.add(cle)
                partenaires_rs.update(v["planetes"])
            elif categorie == "interceptions":
                retenus.add(cle)
        elif categorie == "contact" and v["point_rs"] in acteurs:
            retenus.add(cle)
            partenaires_natals.add(v["point_natal"])
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points.") and fait["objet"] in acteurs:
            retenus.add(cle)
    for ref, noms in (("RS", partenaires_rs), ("NATAL", partenaires_natals)):
        for nom in sorted(noms):
            retenus.update({f"{ref}.positions.{nom}", f"{ref}.angles.{nom}"})
            position = dossier[ref.lower()]["positions"].get(nom)
            if position:
                maison = str(position["maison"])
                retenus.update({f"{ref}.cuspides.{maison}", f"{ref}.maitrises.{maison}"})
                if ref == "RS":
                    retenus.add(f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}")
    return {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}


def construire_reperes_calcules_bloc_3(dossier, faits):
    """Copie les positions et projections archivées, sans nouvelle déduction."""
    catalogue = dossier["faits"]
    maitres = list(dossier["rs"]["maitrises"]["10"]["maitres"])
    mc = catalogue["RS.angles.MC"]["valeur"]
    signe_cuspide = catalogue["RS.cuspides.10"]["valeur"]["signe"]
    projection_mc = catalogue["SUPERPOSITION.rs_vers_natal.points.MC"]["valeur"]["maison_cible"]
    projection_cuspide = catalogue["SUPERPOSITION.rs_vers_natal.cuspides.10"]["valeur"]["maison_cible"]
    phrases = [f"Le MC RS est en {mc['signe']} et se projette en maison {projection_mc} natale.",
               f"La cuspide 10 RS tombe en maison {projection_cuspide} natale ; cette projection concerne la cuspide.",
               f"Les maîtres de la cuspide 10 RS sont : {', '.join(maitres)}."]
    if signe_cuspide != mc["signe"]:
        phrases.append(f"Le MC RS est en {mc['signe']}, la cuspide 10 RS en {signe_cuspide} : "
                       "les maîtres listés sont ceux de la cuspide 10 RS, pas du signe du MC.")
    positions = {}
    for nom in maitres:
        position = dossier["rs"]["positions"][nom]
        projection = catalogue[f"SUPERPOSITION.rs_vers_natal.points.{nom}"]["valeur"]["maison_cible"]
        positions[nom] = {"signe": position["signe"], "maison_rs": position["maison"], "projection_natale": projection}
        phrases.append(f"{nom}, maître de la cuspide 10 RS, est en {position['signe']} "
                       f"en maison {position['maison']} de la RS et se projette en maison {projection} natale.")
        maison = str(position["maison"])
        cible_cuspide = catalogue[f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}"]["valeur"]["maison_cible"]
        maitres_maison = list(dossier["rs"]["maitrises"][maison]["maitres"])
        positions[nom].update({"cuspide_maison_rs_projection_natale": cible_cuspide,
                              "maitres_de_sa_maison_rs": maitres_maison})
        phrases.append(f"La cuspide {maison} RS tombe en maison {cible_cuspide} natale ; "
                       f"cette projection est distincte de celle de {nom} RS.")
        if maison != "10":
            phrases.append(f"Les maîtres de la cuspide {maison} RS sont : {', '.join(maitres_maison)}. "
                           "Ce rôle se distingue de celui de maître de la cuspide 10 RS.")
    axe = {}
    for cle, fait in faits.items():
        if fait["source"] != "rs" or fait["type"] != "aspects":
            continue
        v = fait["valeur"]
        if v["planete1"] in {"MC", "FC"} and v["planete2"] not in {"MC", "FC"}:
            angle, point = v["planete1"], v["planete2"]
        elif v["planete2"] in {"MC", "FC"} and v["planete1"] not in {"MC", "FC"}:
            angle, point = v["planete2"], v["planete1"]
        else:
            continue
        axe.setdefault(point, []).append({"reference": cle, "aspect": v["aspect"], "angle_rs": angle})
    for point, liens in axe.items():
        phrases.append(point + " RS : " + " ; ".join(
            lien["aspect"] + " au " + lien["angle_rs"] + " RS" for lien in liens) + ".")
    return {"mc_rs_signe": mc["signe"], "mc_rs_projection_natale": projection_mc,
            "cuspide_10_rs_signe": signe_cuspide, "cuspide_10_rs_projection_natale": projection_cuspide,
            "maitres_cuspide_10_rs": positions, "liens_calcules_axe_mc_fc": axe,
            "phrases_factuelles": phrases}


def preparer_memoires(memoires):
    """Conserve les résumés éditoriaux, sans les paragraphes ni les citations longues."""
    resultat, ecartes = {}, []
    for bloc in ("bloc_1", "bloc_2"):
        source = memoires[bloc]
        mecanismes = []
        for m in source.get("mecanismes", []):
            if not isinstance(m, dict) or not all(isinstance(m.get(k), str) for k in ("sujet", "role", "resume")):
                continue
            mecanismes.append(copier_mecanisme(m))
        references = list(source.get("faits_deja_cites", []))
        references.extend(c["reference"] for c in source.get("faits_cites", [])
                          if isinstance(c, dict) and isinstance(c.get("reference"), str))
        resultat[bloc] = {"mecanismes": mecanismes, "faits_deja_cites": list(dict.fromkeys(references))}
    return resultat, ecartes


def construire_prompt_bloc_3(dossier, *, memoires, proprietaires_precedents, genre="", plan=None, utiliser_bdd=True):
    faits = selectionner_faits_bloc_3(dossier, proprietaires_precedents)
    nouveaux, deja, _ = repartir_pour_bloc(faits, 3, proprietaires_precedents, faits_a_developper=())
    parts = repartir_sections_bloc_3(nouveaux, dossier)
    parts, hierarchie = hierarchiser_complements(nouveaux, parts, deja, dossier)
    nouveaux_envoyes = contexte_necessaire(nouveaux, parts, dossier)
    possedes = {cle for liste in parts.values() for cle in liste}
    _, _, proprietaires = repartir_pour_bloc(faits, 3, proprietaires_precedents, faits_a_developper=possedes)
    documentation = {cle: f for cle, f in nouveaux_envoyes.items() if cle in possedes and f["source"] == "rs"
                     and f["type"] in {"positions", "aspects"}}
    aides = retirer_note_documentaire(construire_reperes_rs(documentation)) if utiliser_bdd else reperes_sans_bdd()
    for fiche in aides["placements"]:
        fiche["texte"] = fiche["texte"].split("\n\nPrécisions de la source", 1)[0].rstrip()
    aides, nettoyage = nettoyer_aides_bloc_3(aides)
    editoriales, ecartes = preparer_memoires(memoires)
    entree = {
        "cycle": {k: dossier["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
        "genre": {"female": "féminin", "male": "masculin"}.get(genre, genre),
        "faits_calcules": {**compacter_faits(nouveaux_envoyes),
                           "REPERES_CALCULES": construire_reperes_calcules_bloc_3(dossier, faits)},
        "repartition_des_faits": parts,
        "references_de_contexte": [cle for cle in nouveaux_envoyes if cle not in possedes],
        "priorites_complementaires": hierarchie["mecanismes"],
        "deja_traites": {cle: {"bloc_proprietaire": f["bloc_proprietaire"],
                                  "fait": compacter_faits({cle: f["fait"]})[cle]} for cle, f in deja.items()},
        "aides_interpretatives_rs": reperes_pour_prompt(aides),
        "memoires_editoriales": editoriales,
    }
    ajouter_plan_entree(entree, plan)
    prompt = consignes_communes_bloc_1() + "\n" + PROMPT_PATH.read_text(encoding="utf-8")
    prompt += consignes_plan(plan)
    prompt = adapter_prompt_sans_bdd(prompt, entree, utiliser_bdd)
    prompt += "\nDONNÉES DU BLOC 3\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    envoyes = {cle: f for cle, f in faits.items() if cle in nouveaux_envoyes or cle in deja}
    preparation = {"nettoyage_aides": nettoyage, "hierarchie_complements": hierarchie,
                   "references_non_envoyees": [cle for cle in faits if cle not in envoyes]}
    return prompt, envoyes, entree, proprietaires, ecartes, preparation


def contradictions_maisons_bloc_3(texte, dossier):
    """Repérage lexical par cadre ; les phrases ambiguës ne sont pas validées."""
    catalogue = dossier["faits"]
    maitres = dossier["rs"]["maitrises"]["10"]["maitres"]
    attendues = {}
    for nom in ("MC", *maitres):
        rs = dossier["rs"]["positions"].get(nom, dossier["rs"]["angles"].get(nom, {}))
        natal = dossier["natal"]["positions"].get(nom, dossier["natal"]["angles"].get(nom, {}))
        maison_rs, maison_natale = rs.get("maison"), natal.get("maison")
        if nom == "MC":
            # Une coïncidence déjà calculée avec la cuspide 10 situe l'angle.
            if rs.get("degre") == dossier["rs"]["cuspides"]["10"]["degre"]:
                maison_rs = 10
            if natal.get("degre") == dossier["natal"]["cuspides"]["10"]["degre"]:
                maison_natale = 10
        attendues[nom] = {"rs": maison_rs, "natal": maison_natale,
                         "projection": catalogue[f"SUPERPOSITION.rs_vers_natal.points.{nom}"]["valeur"]["maison_cible"]}
    autres = (set(dossier["rs"]["positions"]) | set(dossier["rs"]["angles"])) - set(attendues)
    sortie = []
    for phrase, _ in fenetres(texte):
        tokens = [a or b for a, b in RE_MAISON.findall(phrase)]
        numeros = {int(t) if t.isdigit() else ROMAINS_MAISONS[t] for t in tokens}
        sujets = [nom for nom in attendues if re.search(motif_point(nom), phrase)]
        if not numeros or not sujets:
            continue
        if len(numeros) != 1 or len(sujets) != 1 or any(re.search(motif_point(nom), phrase) for nom in autres):
            sortie.append({"phrase": phrase, "statut": "a_relire", "raison": "Plusieurs points ou maisons, association ambiguë."})
            continue
        natal = bool(re.search(r"\bnatal(?:e|s|es)?\b", phrase))
        rs = bool(re.search(r"\brs\b|\brevolution solaire\b", phrase))
        projection = natal and bool(re.search(r"\b(?:projette|projection|retombe|tombe)\b", phrase))
        cadre = "projection" if projection else "rs" if rs and not natal else "natal" if natal and not rs else None
        attendu = attendues[sujets[0]].get(cadre)
        if attendu is None:
            sortie.append({"phrase": phrase, "statut": "a_relire", "raison": "Cadre ou position non identifiable sans ambiguïté."})
        elif attendu not in numeros:
            sortie.append({"phrase": phrase, "statut": "contradiction", "sujet": sujets[0],
                           "cadre": cadre, "maisons_attendues": [attendu]})
    return sortie


def schema_bloc_3(plan=None):
    return schema_bloc_1(plan=plan)


def generer_bloc_3(dossier, *, appeler, memoires, proprietaires_precedents, genre="", plan=None, utiliser_bdd=True):
    prompt, faits, entree, _, ecartes_source, preparation = construire_prompt_bloc_3(
        dossier, memoires=memoires, proprietaires_precedents=proprietaires_precedents,
        genre=genre, plan=plan, utiliser_bdd=utiliser_bdd)
    resultat = parser_json_reponse(appeler(prompt, max_tokens=MAX_TOKENS, temperature=0.5,
        reflexion="disabled", niveau_effort="low", schema_sortie=schema_bloc_3(plan=plan)))
    memoire_brute = deepcopy(resultat.get("memoire"))
    texte = resultat.get("texte")
    parasites = []
    if isinstance(texte, str):
        texte, parasites = nettoyer_parasites(texte)
    corps = texte if isinstance(texte, str) else ""
    alertes = [] if corps.strip() else ["Texte du bloc absent ou vide."]
    maisons = contradictions_maisons_bloc_3(corps, dossier)
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
            continue
        repere, raison = reperer_citation(corps, faits[ref], c.get("extrait"))
        if ref not in attribues and not raison.startswith("Contradiction"):
            repere, raison = False, "À relire : référence déjà traitée ou de contexte, aucun développement attribué au bloc 3."
        statut = ("a_relire" if raison.startswith("À relire") else "repere") if repere else (
            "contradiction" if raison.startswith("Contradiction") else "a_relire")
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
                "maisons_a_relire": maisons,
                "suivi_appuis": suivi_appuis,
                "maisons_incoherentes": [d for d in maisons if d["statut"] == "contradiction"],
                "memoire_source_elements_non_transmis": ecartes_source,
                "preparation_editoriale": {"nombre_aides_nettoyees": len(preparation["nettoyage_aides"]),
                    "mecanismes_complementaires": preparation["hierarchie_complements"]["mecanismes"]},
                "mecanismes_ecartes": ecartes, "parasites_retires": parasites,
                "faits_cites_reperes": [cle for cle in faits if cle in reperes],
                "faits_abordes": [cle for cle in faits if cle in abordes],
                "faits_non_reperes": [cle for cle in faits if cle in attribues and cle not in abordes],
                "suivi_citations": suivi, "citations_a_relire": [d for d in suivi if d["statut"] == "a_relire"],
                "mode_controle": "reperage_lexical_non_validation", "validation_humaine": False}}, plan, 3)
