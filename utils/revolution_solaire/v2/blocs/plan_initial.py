"""Un appel court pour un plan commun fondé sur les calculs, sans contexte client."""

from copy import deepcopy
import json
from pathlib import Path

from ..analyse import parser_json_reponse
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from .convergence import collecter_faits, preparer_donnees_plan


VERSION = "rs_plan_initial_1"
MAX_TOKENS = 2400
PROMPT_PATH = Path(__file__).with_name("prompt_plan_initial.txt")


def _sans_precisions(objet):
    if isinstance(objet, dict):
        return {k: _sans_precisions(v) for k, v in objet.items()
                if k not in {"degre", "orbe", "orbe_deg", "dignite_essentielle"}}
    if isinstance(objet, list):
        return [_sans_precisions(v) for v in objet]
    return objet


def construire_prompt_plan(dossier):
    preparation = preparer_donnees_plan(dossier)
    groupes = collecter_faits(dossier)
    refs = {r for ligne in groupes.values() for r in ligne["cles"]}
    # Vue générale RS et placements natals : pas de texte d'une génération précédente.
    for cle, fait in dossier["faits"].items():
        if (fait["source"] in {"rs", "natal"} and fait["type"] == "positions"
                and fait.get("objet") not in {"Chiron", "Rahu", "Ketu", "Part de Fortune"}):
            refs.add(cle)
        if fait["source"] == "rs" and fait["type"] in {"angles", "maitrises", "interceptions"}:
            refs.add(cle)
    retenus = {cle: f for cle, f in dossier["faits"].items() if cle in refs and fait_autorise(f)}
    fixes = {cle: f for cle, f in retenus.items() if f["type"] != "transit"}
    faits = compacter_faits(fixes)
    for cle, fait in retenus.items():
        if fait["type"] == "transit":
            faits[cle] = {k: fait["valeur"][k] for k in ("planete_transit", "reference", "cible", "aspect")}
    entree = {"cycle": {k: dossier["cycle"][k] for k in ("annee", "age")},
              "classement": [{k: e[k] for k in ("point", "score", "familles")} for e in preparation["candidats"]],
              "groupes_faits": [{"famille": e["famille"], "points": sorted(f"{c}:{n}" for c, n in e["points"]),
                                  "references": sorted(e["cles"]), "passages_exacts": len(e["dates"])}
                                 for e in groupes.values()],
              "contexte_maisons": preparation["contexte_maisons"], "faits_calcules": _sans_precisions(faits)}
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    prompt += "\nDONNÉES DU PLAN\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    return prompt, entree, preparation


def schema_plan():
    def objet(proprietes):
        return {"type": "object", "properties": proprietes, "required": list(proprietes), "additionalProperties": False}
    chaine = {"type": "string"}
    return objet({"fils": {"type": "array", "items": objet({
        "idee": chaine, "explication": chaine, "appuis": {"type": "array", "items": chaine},
        "apports_par_bloc": {"type": "array", "items": objet({"bloc": {"type": "integer", "enum": [1, 2, 3, 4, 5]}, "apport": chaine})}
    })}})


def traiter_plan(resultat, entree):
    """Contrôle des références et de la forme ; aucune validation du sens."""
    alertes, fils = [], []
    declares_fils = resultat.get("fils") if isinstance(resultat, dict) else None
    if not isinstance(declares_fils, list):
        declares_fils = []
        alertes.append("Liste des sujets absente ou illisible dans la réponse reçue.")
    for n, fil in enumerate(declares_fils, 1):
        if not isinstance(fil, dict) or not all(isinstance(fil.get(k), str) and fil[k].strip()
                                              for k in ("idee", "explication")):
            alertes.append(f"Sujet {n} incomplet, conservé dans la réponse brute seulement.")
            continue
        declares = fil.get("appuis", [])
        appuis = list(dict.fromkeys(r for r in declares if isinstance(r, str) and r in entree["faits_calcules"])) if isinstance(declares, list) else []
        if not appuis:
            alertes.append(f"Sujet {n} sans référence calculée reçue ; non transmis.")
            continue
        if not isinstance(declares, list) or len(appuis) != len(declares):
            alertes.append(f"Sujet {n} : références inconnues ou répétées retirées de la copie transmise.")
        declares_apports = fil.get("apports_par_bloc")
        if not isinstance(declares_apports, list):
            declares_apports = []
        apports = [deepcopy(a) for a in declares_apports
                   if isinstance(a, dict) and type(a.get("bloc")) is int and a["bloc"] in range(1, 6)
                   and isinstance(a.get("apport"), str) and a["apport"].strip()]
        fils.append({"id": f"F{len(fils) + 1}", "idee": fil["idee"].strip(),
                     "explication": fil["explication"].strip(), "appuis": appuis, "apports_par_bloc": apports})
    if not 2 <= len(fils) <= 3:
        alertes.append("Le plan reçu ne contient pas deux ou trois sujets utilisables.")
    return {"plan": {"version": VERSION, "fils": fils},
            "diagnostic": {"alertes": alertes, "nature": "Forme et existence des références ; aucune validation de l'interprétation.",
                           "validation_humaine": False}}


def generer_plan(dossier, *, appeler):
    prompt, entree, _ = construire_prompt_plan(dossier)
    brut = parser_json_reponse(appeler(prompt, max_tokens=MAX_TOKENS, temperature=0.5,
        reflexion="disabled", niveau_effort="low", schema_sortie=schema_plan()))
    return traiter_plan(brut, entree)
