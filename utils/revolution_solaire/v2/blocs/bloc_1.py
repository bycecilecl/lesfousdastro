"""Bloc 1 : sélection factuelle, prompt visible et rédaction avec mémoire.

Pas de génération à l'import. Les données sont déjà calculées ; aucune lecture
ancienne n'est recopiée dans ce nouveau parcours.
"""

import json
import re
from copy import deepcopy
from pathlib import Path

from ..analyse import parser_json_reponse
from .plan_partage import ajouter_plan_entree, consignes_plan, schema_avec_plan, suivre_fils
from ..connaissances import construire_reperes_rs, reperes_pour_prompt
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from ..schemas import objet
from .repartition import repartir_pour_bloc, repartir_sections_bloc_1
from .suivi_memoire import fenetres, normaliser_texte, reperer_citation
from .appuis_memoire import verifier_appuis


VERSION = "rs_bloc_1_posture_profection_18_appuis_memoire"
MAX_TOKENS = 6000
PROMPT_PATH = Path(__file__).with_name("prompt_bloc_1.txt")
STYLE_PATH = Path(__file__).with_name("style_lecture.txt")
REGLES_PATH = Path(__file__).with_name("regles.txt")


def reperes_sans_bdd():
    """Structure vide pour le comparatif ; aucune lecture de fiche documentaire."""
    return {"placements": [], "aspects": [], "nuances": [], "faits_sans_fiche": []}


def adapter_prompt_sans_bdd(prompt, entree, utiliser_bdd):
    """Retire uniquement les fiches et leur consigne, sans toucher aux faits ni au style."""
    if not isinstance(utiliser_bdd, bool):
        raise ValueError("utiliser_bdd doit être True ou False.")
    if utiliser_bdd:
        return prompt
    entree.pop("aides_interpretatives_rs", None)
    lignes = prompt.splitlines(keepends=True)
    return "".join(
        "Aucune fiche de BDD n'est fournie pour cette lecture.\n"
        if ligne.startswith("Utilise les fiches de la BDD ") else ligne
        for ligne in lignes
    )


def retirer_note_documentaire(reperes):
    """Retire la note convenue d'une copie ; aucune fiche de BDD n'est modifiée."""
    note = (
        "Le livre renforce la vigilance pour les aspects « difficiles ou stressants », "
        "sans nommer dans cette phrase les angles concernés. Cette remarque ne constitue "
        "donc pas une distinction explicite entre carré, opposition et conjonction."
    )
    resultat = deepcopy(reperes)
    nuances = []
    for fiche in resultat.get("nuances", []):
        fiche["texte"] = fiche["texte"].replace(note, "").strip()
        if fiche["texte"]:
            nuances.append(fiche)
    resultat["nuances"] = nuances
    return resultat


def selectionner_faits_bloc_1(dossier):
    """Ascendant/maîtres, profection et leurs liens natals directs uniquement."""
    catalogue = dossier["faits"]
    maitre_annee = dossier["profection"]["maitre_annee"]["nom"]
    centres = {"Ascendant", maitre_annee}
    centres.update(dossier["rs"]["maitrises"]["1"]["maitres"])
    retenus = {"RS.maitrises.1", "PROFECTION.annuelle"}
    relais_rs, points_natals = set(centres), {maitre_annee}
    for cle, fait in catalogue.items():
        if not fait_autorise(fait):
            continue
        v, categorie = fait["valeur"], fait["type"]
        if fait["source"] == "rs":
            if categorie in {"positions", "angles"} and fait["objet"] in centres:
                retenus.add(cle)
            elif categorie == "aspects" and {v["planete1"], v["planete2"]} & centres:
                retenus.add(cle)
                relais_rs.update({v["planete1"], v["planete2"]})
            elif categorie == "angularites" and (v["point"] in centres or v["angle"] in centres):
                retenus.add(cle)
                relais_rs.update({v["point"], v["angle"]})
            elif categorie == "configurations" and len(set(v["planetes"]) & centres) >= 2:
                retenus.add(cle)
                relais_rs.update(v["planetes"])
        elif cle.startswith("CONTACT.") and v["point_rs"] in centres:
            retenus.add(cle)
            relais_rs.add(v["point_rs"])
            points_natals.add(v["point_natal"])
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points.") and fait["objet"] in centres:
            retenus.add(cle)
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.cuspides.") and str(fait["objet"]) == "1":
            retenus.add(cle)
    for ref, noms in (("RS", relais_rs), ("NATAL", points_natals)):
        for nom in noms:
            retenus.update({f"{ref}.positions.{nom}", f"{ref}.angles.{nom}"})
            position = dossier[ref.lower()]["positions"].get(nom)
            if position:
                maison = str(position["maison"])
                retenus.update({f"{ref}.cuspides.{maison}", f"{ref}.maitrises.{maison}"})
        retenus.add(f"{ref}.interceptions.ensemble")
    for cle, fait in catalogue.items():
        if fait["source"] != "natal" or not fait_autorise(fait):
            continue
        v = fait["valeur"]
        if fait["type"] == "aspects" and {v["planete1"], v["planete2"]} <= points_natals:
            retenus.add(cle)
        elif fait["type"] == "angularites" and v["point"] == maitre_annee:
            retenus.add(cle)
        elif fait["type"] == "configurations" and set(v["planetes"]) <= points_natals:
            retenus.add(cle)
    faits = {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}
    return faits, centres


def consignes_communes_bloc_1():
    """Lit les deux fichiers actifs sans remplacement ni consigne cachée."""
    return REGLES_PATH.read_text(encoding="utf-8") + "\n" + STYLE_PATH.read_text(encoding="utf-8")


def construire_reperes_calcules(dossier):
    """Copie les positions déjà calculées ; aucune nouvelle déduction."""
    profection = dossier["profection"]
    soleil_rs = dossier["rs"]["positions"]["Soleil"]
    reperes = {
        "soleil_rs_maison": soleil_rs["maison"],
        "soleil_natal_maison": dossier["natal"]["positions"]["Soleil"]["maison"],
        "maison_annuelle_profectee": profection["maison_annuelle"],
        "ascendant_profecte_maison_rs": profection["ascendant_profecte"]["maison_rs"],
        "ascendant_profecte_maison_natale": profection["ascendant_profecte"]["maison_natale"],
        "soleil_rs_dignite": soleil_rs.get("dignite_essentielle"),
        "soleil_natal_dignite": dossier["natal"]["positions"]["Soleil"].get("dignite_essentielle"),
        "maitre_annee": profection["maitre_annee"]["nom"],
        "maitres_maison_du_soleil_rs": list(dossier["rs"]["maitrises"][str(soleil_rs["maison"])]["maitres"]),
    }
    reperes["phrases_factuelles"] = [
        f"Le Soleil RS est en maison {reperes['soleil_rs_maison']} de la RS.",
        f"Le Soleil natal est en maison {reperes['soleil_natal_maison']} du thème natal.",
        f"La maison annuelle profectée est la maison {reperes['maison_annuelle_profectee']}.",
        f"L'Ascendant profecté tombe en maison {reperes['ascendant_profecte_maison_rs']} de la RS.",
        f"L'Ascendant profecté tombe en maison {reperes['ascendant_profecte_maison_natale']} du thème natal.",
    ]
    return reperes


def construire_prompt_bloc_1(dossier, *, genre="", proprietaires_precedents=None, plan=None, utiliser_bdd=True):
    faits, centres = selectionner_faits_bloc_1(dossier)
    nouveaux, deja_traites, _ = repartir_pour_bloc(
        faits, 1, proprietaires_precedents, faits_a_developper=())
    reserves = {"Soleil", "Lune", "MC", *dossier["rs"]["maitrises"]["10"]["maitres"]}
    parts = repartir_sections_bloc_1(nouveaux, dossier, reserves=reserves)
    a_developper = {cle for liste in parts.values() for cle in liste}
    _, _, proprietaires = repartir_pour_bloc(
        faits, 1, proprietaires_precedents, faits_a_developper=a_developper)
    # Fiches des seuls faits possédés ; aucune fiche de placement du contexte.
    documentation = {k: f for k, f in nouveaux.items() if k in a_developper
                     and f["source"] == "rs" and f["type"] in {"positions", "aspects"}}
    reperes = retirer_note_documentaire(construire_reperes_rs(documentation)) if utiliser_bdd else reperes_sans_bdd()
    # Seul le condensé est envoyé ; les traductions longues restent dans la BDD.
    for fiche in reperes["placements"]:
        fiche["texte"] = fiche["texte"].split("\n\nPrécisions de la source", 1)[0].rstrip()
    genre_prompt = {"female": "féminin", "male": "masculin"}.get(genre, genre)
    entree = {"cycle": {k: dossier["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
              "genre": genre_prompt, "acteurs_centraux_rs": sorted(centres),
              "faits_calcules": {**compacter_faits(nouveaux),
                                 "REPERES_CALCULES": construire_reperes_calcules(dossier)},
              "repartition_des_faits": parts,
              "references_de_contexte": [cle for cle in nouveaux if cle not in a_developper],
              "deja_traites": deja_traites,
              "aides_interpretatives_rs": reperes_pour_prompt(reperes)}
    ajouter_plan_entree(entree, plan)
    prompt = consignes_communes_bloc_1() + "\n" + PROMPT_PATH.read_text(encoding="utf-8")
    if not deja_traites:
        prompt += "\nPour ce premier bloc, deja_traites est vide.\n"
    prompt += consignes_plan(plan)
    prompt = adapter_prompt_sans_bdd(prompt, entree, utiliser_bdd)
    prompt += "\nDONNÉES DU BLOC 1\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    return prompt, nouveaux, entree, proprietaires


def schema_bloc_1(plan=None):
    return schema_avec_plan(objet({"texte": {"type": "string"}, "memoire": objet({
        "mecanismes": {"type": "array", "items": objet({
            "sujet": {"type": "string"}, "role": {"type": "string"},
            "resume": {"type": "string"},
            "appuis": {"type": "array", "items": {"type": "string"}}})},
        "faits_cites": {"type": "array", "items": objet({
            "reference": {"type": "string"}, "extrait": {"type": "string"}})},
    })}), plan)


ROMAINS_MAISONS = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
                  "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
NUMERO_MAISON = r"(?:\d{1,2}|xii|xi|ix|viii|vii|vi|iv|iii|ii|x|v|i)"
RE_MAISON = re.compile(r"\bmaison\s+(" + NUMERO_MAISON + r")\b|\b("
                      + NUMERO_MAISON + r")\s*(?:e|eme)\s+maison\b", re.I)
RE_PARASITE_IMAGE = re.compile(r"\.(?:i?jpe?g|ipeg|png)\b", re.I)
SUJETS_MAISONS = {
    "soleil": re.compile(r"\bsoleil\b"),
    "asc_profecte": re.compile(r"\basc(?:endant)?\.?\s+profect"),
}


def contient_position(texte):
    """Maisons en chiffres arabes ou romains ; nombres en lettres non couverts."""
    return isinstance(texte, str) and bool(RE_MAISON.search(normaliser_texte(texte)))


def nettoyer_parasites(texte):
    """Retire les suffixes parasites du texte affiché ; brut archivé séparément."""
    parasites = RE_PARASITE_IMAGE.findall(texte)
    return RE_PARASITE_IMAGE.sub("", texte), parasites


def reperer_etats_maitres(texte, dossier):
    """Présence lexicale seulement, sans certification ni relance automatique."""
    reperes = construire_reperes_calcules(dossier)
    maitres = set(dossier["rs"]["maitrises"]["1"]["maitres"])
    maitre_annee = dossier["profection"]["maitre_annee"]["nom"]
    attendus = []
    for nom in sorted(maitres | {maitre_annee}):
        position = dossier["rs"]["positions"].get(nom, {})
        if position.get("retrograde") is True:
            attendus.append((nom, "rétrogradation RS", r"retrograd", "rs"))
    dignite = reperes["soleil_natal_dignite"]
    if "Soleil" in maitres | {maitre_annee} and dignite and dignite != "neutre":
        attendus.append(("Soleil", dignite + " natale, commune au Soleil RS",
                         r"\b" + re.escape(normaliser_texte(dignite)) + r"\b", "natal"))
    suivi = []
    for point, etat, motif, cadre in attendus:
        mentions, implicites, autres_cadres = [], [], []
        nombre_mentions = 0
        for phrase, precedente in fenetres(texte):
            if not re.search(r"\b" + re.escape(normaliser_texte(point)) + r"\b", phrase) or not re.search(motif, phrase):
                continue
            nombre_mentions += len(re.findall(motif, phrase))
            natal = bool(re.search(r"\bnatal(?:e|s|es|ement)?\b|\bnativement\b", phrase))
            rs = bool(re.search(r"\brs\b|\brevolution solaire\b", phrase))
            if cadre == "natal":
                if natal or (not rs and re.search(r"\bnatal(?:e|s|es|ement)?\b|\bnativement\b", precedente)):
                    mentions.append(phrase)
                elif rs:
                    autres_cadres.append(phrase)
                else:
                    implicites.append(phrase)
                continue
            # Un sujet implicite après « Natalement, ce Soleil… » reste natal.
            if natal:
                autres_cadres.append(phrase)
                continue
            if rs:
                mentions.append(phrase)
            elif re.search(r"\bnatal(?:e|s|es|ement)?\b|\bnativement\b", precedente):
                autres_cadres.append(phrase)
                continue
            elif re.search(r"\brs\b|\brevolution solaire\b", precedente):
                mentions.append(phrase)
            else:
                implicites.append(phrase)
        suivi.append({"point": point, "etat_attendu": etat,
                      "cadre_attendu": cadre,
                      "mention_reperee": bool(mentions), "phrases": mentions,
                      "phrases_cadre_implicite": implicites,
                      "phrases_autre_cadre": autres_cadres,
                      "nombre_mentions_lexicales": nombre_mentions,
                      "repetition_a_relire": point == "Soleil" and nombre_mentions > 1,
                      "statut": "repere_lexicalement" if mentions and (point != "Soleil" or nombre_mentions == 1) else "a_relire",
                      "validation": False})
    return suivi


def contradictions_maisons(texte, attendu):
    """Signale les contradictions chiffrées ; aucune relance ni correction.

    soleil / asc_profecte désignent la RS. Leurs variantes _natal sont séparées.
    Sans cadre explicite, seule une maison absente des deux cadres est signalée
    comme contradiction ; une association multiple reste simplement à relire.
    """
    sortie = []
    for phrase in re.split(r"(?<=[.!?])\s+", texte or ""):
        normale = normaliser_texte(phrase)
        tokens = [a or b for a, b in RE_MAISON.findall(normale)]
        numeros = {int(token) if token.isdigit() else ROMAINS_MAISONS[token] for token in tokens}
        if not numeros:
            continue
        sujets = [cle for cle, motif in SUJETS_MAISONS.items() if motif.search(normale)]
        if not sujets:
            continue
        if len(sujets) > 1 or len(numeros) > 1:
            sortie.append((phrase, "À relire : plusieurs sujets ou maisons, association ambiguë"))
            continue
        sujet = sujets[0]
        natal = bool(re.search(r"\bnatal(?:e|s|es|ement)?\b", normale))
        rs = bool(re.search(r"\brs\b|\brevolution\b", normale))
        if natal and rs:
            sortie.append((phrase, "À relire : cadres natal et RS dans la même phrase"))
            continue
        if natal:
            cles = (sujet + "_natal",)
        elif rs:
            cles = (sujet,)
        elif sujet == "asc_profecte" and re.search(r"\b(?:annuelle|profectee)\b", normale):
            cles = ("maison_annuelle",)
        else:
            cles = (sujet, sujet + "_natal")
        possibles = {attendu[cle] for cle in cles if cle in attendu}
        if possibles and not numeros & possibles:
            valeurs = "/".join(str(n) for n in sorted(possibles))
            sortie.append((phrase, sujet + " attendu en maison " + valeurs))
    return sortie


def options_generation_bloc_1(*, plan=None, reflexion="disabled", niveau_effort="low", max_tokens=None):
    """Paramètres explicites du bloc ; les valeurs historiques restent inchangées."""
    if reflexion not in {"disabled", "adaptive"}:
        raise ValueError("Réflexion attendue : disabled ou adaptive.")
    if niveau_effort not in {"low", "medium", "high"}:
        raise ValueError("Niveau d'effort attendu : low, medium ou high.")
    plafond = MAX_TOKENS if max_tokens is None else max_tokens
    if isinstance(plafond, bool) or not isinstance(plafond, int) or plafond <= 0:
        raise ValueError("max_tokens doit être un entier strictement positif.")
    options = {"max_tokens": plafond, "temperature": 0.5, "reflexion": reflexion,
               "niveau_effort": niveau_effort, "schema_sortie": schema_bloc_1(plan=plan)}
    if reflexion == "adaptive":
        options["thinking"] = {"type": "adaptive"}
    return options


def generer_bloc_1(dossier, *, appeler, genre="", maisons_attendues=None, plan=None, utiliser_bdd=True,
                   reflexion="disabled", niveau_effort="low", max_tokens=None):
    attendues = {
        "soleil": dossier["rs"]["positions"]["Soleil"]["maison"],
        "soleil_natal": dossier["natal"]["positions"]["Soleil"]["maison"],
        "asc_profecte": dossier["profection"]["ascendant_profecte"]["maison_rs"],
        "asc_profecte_natal": dossier["profection"]["ascendant_profecte"]["maison_natale"],
        "maison_annuelle": dossier["profection"]["maison_annuelle"],
    }
    if maisons_attendues is not None:
        attendues.update(maisons_attendues)
    prompt, faits, entree, _ = construire_prompt_bloc_1(dossier, genre=genre, plan=plan, utiliser_bdd=utiliser_bdd)
    resultat = parser_json_reponse(appeler(prompt, **options_generation_bloc_1(
        plan=plan, reflexion=reflexion, niveau_effort=niveau_effort, max_tokens=max_tokens)))
    # Les alertes restent consultables, sans arrêter une lecture déjà reçue.
    alertes = []
    texte = resultat.get("texte")
    parasites = []
    if isinstance(texte, str):
        texte, parasites = nettoyer_parasites(texte)
    contradictions = contradictions_maisons(texte if isinstance(texte, str) else "", attendues)
    for phrase, motif in contradictions:
        alertes.append("Maison à relire (" + motif + ") : " + phrase)
    nombre_mots = len(texte.split()) if isinstance(texte, str) else 0
    if not isinstance(texte, str) or not texte.strip():
        alertes.append("Texte du bloc vide ou absent.")
    memoire = resultat.get("memoire")
    memoire_brute = deepcopy(memoire)
    suivi_appuis = []
    mecanismes, citations_retenues, reperes, suivi = [], [], set(), []
    citations_a_relire = []
    ecartes = []
    attribues = {cle for liste in entree["repartition_des_faits"].values() for cle in liste}
    if not isinstance(memoire, dict):
        alertes.append("Mémoire absente ou illisible ; à examiner avant de préparer le bloc 2.")
    else:
        declarations = memoire.get("mecanismes")
        if not isinstance(declarations, list):
            alertes.append("Liste des mécanismes absente ou illisible dans la mémoire.")
            declarations = []
        for mecanisme in declarations:
            if not isinstance(mecanisme, dict) or not all(isinstance(mecanisme.get(k), str) and mecanisme[k].strip()
                                                       for k in ("sujet", "role", "resume")):
                alertes.append("Mécanisme de mémoire incomplet ou illisible.")
                continue
            if any(contient_position(mecanisme[k]) for k in ("sujet", "role", "resume")):
                alertes.append("Mécanisme écarté de la mémoire (contient une maison) : " + mecanisme["sujet"])
                ecartes.append(mecanisme)
                continue
            mecanisme, diagnostic_appuis = verifier_appuis(mecanisme, dossier["faits"], faits)
            mecanismes.append(mecanisme)
            suivi_appuis.append(diagnostic_appuis)
        citations = memoire.get("faits_cites")
        if not isinstance(citations, list):
            alertes.append("Liste des faits cités absente ou illisible dans la mémoire.")
            citations = []
        vus = {}
        for citation in citations:
            if not isinstance(citation, dict):
                alertes.append("Citation de mémoire illisible.")
                continue
            ref, extrait = citation.get("reference"), citation.get("extrait")
            if not isinstance(ref, str) or ref not in faits:
                alertes.append("Référence de mémoire non reconnue : " + str(ref))
                continue
            ecarts_extrait = contradictions_maisons(extrait, attendues) if isinstance(extrait, str) else []
            if any(not motif.startswith("À relire") for _, motif in ecarts_extrait):
                raison = "Extrait écarté de la mémoire : maison chiffrée incohérente."
                alertes.append(ref + " — " + raison)
                suivi.append({"reference": ref, "repere": False, "raison": raison, "extrait": extrait})
                continue
            vus[ref] = vus.get(ref, 0) + 1
            if vus[ref] > 1:
                alertes.append("Fait cité plusieurs fois dans la mémoire : " + ref)
            repere, raison = reperer_citation(texte if isinstance(texte, str) else "", faits[ref], extrait)
            if ref not in attribues:
                repere, raison = False, "À relire : référence de contexte ; aucune propriété de développement attribuée."
            a_relire = raison.startswith("À relire") or (
                not repere and not raison.startswith("Contradiction"))
            statut = "a_relire" if a_relire else "repere" if repere else "contradiction"
            item = {"reference": ref, "repere": repere and not a_relire,
                    "statut": statut, "raison": raison, "extrait": extrait}
            suivi.append(item)
            if a_relire:
                citations_a_relire.append(item)
            elif repere:
                if ref not in reperes:
                    citations_retenues.append({"reference": ref, "extrait": extrait})
                reperes.add(ref)
            else:
                alertes.append(ref + " — " + raison)
    # La réponse brute reste archivée. Cette mémoire de travail ne transmet
    # aucun fait non repéré comme acquis, ni piste libre de redéveloppement.
    if isinstance(texte, str) and texte.strip() and not mecanismes:
        alertes.append("Mémoire sans mécanisme : les blocs suivants ne disposeront pas du résumé de cette lecture.")
    memoire_travail = {"mecanismes": mecanismes, "faits_cites": citations_retenues}
    etats = reperer_etats_maitres(texte if isinstance(texte, str) else "", dossier)
    return suivre_fils({**resultat, "texte": texte, "memoire": memoire_travail, "memoire_brute": memoire_brute,
            "diagnostic": {"alertes": alertes, "nombre_mots": nombre_mots,
            "maisons_attendues": attendues, "contradictions_maisons": contradictions,
            "mecanismes_ecartes": ecartes,
            "suivi_appuis": suivi_appuis,
            "parasites_retires": parasites, "suivi_etats_maitres": etats,
            "citations_a_relire": citations_a_relire,
            "faits_cites_reperes": [cle for cle in faits if cle in reperes],
            "faits_non_reperes": [cle for cle in faits if cle in attribues and cle not in reperes],
            "suivi_citations": suivi, "mode_controle": "reperage_lexical_non_validation",
            "fourchette_mots_visee": [900, 1300], "validation_humaine": False}}, plan, 1)
