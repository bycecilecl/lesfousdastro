"""Plan commun et couverture déclarée ; aucune interprétation ou génération IA."""

from copy import deepcopy
import json
from pathlib import Path


CONSIGNES_PATH = Path(__file__).with_name("prompt_plan_partage.txt")


def reprendre_plan(source, plan, precedent):
    """Une reprise isolée garde le plan archivé, sans refaire l'appel de préparation."""
    if plan is not None:
        return plan
    chemin = Path(source) / "plan_commun.json"
    if not chemin.is_file():
        return None
    plan = json.loads(chemin.read_text(encoding="utf-8"))
    resultat = Path(source) / f"bloc_{precedent}" / "resultat.json"
    if resultat.is_file():
        traite = json.loads(resultat.read_text(encoding="utf-8"))
        plan.setdefault("suivi_blocs_precedents", {})[f"bloc_{precedent}"] = traite.get("fils_servis", [])
    return plan


def ajouter_plan_entree(entree, plan):
    if plan is None:
        return
    entree["plan_commun"] = deepcopy(plan)


def consignes_plan(plan):
    return "\n" + CONSIGNES_PATH.read_text(encoding="utf-8") if plan is not None else ""


def schema_avec_plan(schema, plan):
    if plan is None:
        return schema
    schema = deepcopy(schema)
    schema["properties"]["fils_servis"] = {
        "type": "array", "items": {"type": "string", "enum": [f["id"] for f in plan["fils"]]}}
    schema["required"].append("fils_servis")
    return schema


def suivre_fils(resultat, plan, numero):
    """Une déclaration manquante ou inconnue produit une alerte, jamais une relance."""
    if plan is None:
        return resultat
    sortie = deepcopy(resultat)
    connus = {f["id"] for f in plan["fils"]}
    declares = sortie.get("fils_servis")
    valides = list(dict.fromkeys(r for r in declares if isinstance(r, str) and r in connus)) if isinstance(declares, list) else []
    inconnus = [r for r in declares if not isinstance(r, str) or r not in connus] if isinstance(declares, list) else []
    alertes = []
    if not valides:
        alertes.append(f"Bloc {numero} : aucun sujet du plan déclaré abordé ; vérifier la lecture.")
    if inconnus:
        alertes.append(f"Bloc {numero} : identifiants de sujets inconnus dans le suivi.")
    sortie["fils_servis_declares"] = deepcopy(declares)
    sortie["fils_servis"] = valides
    diagnostic = sortie.setdefault("diagnostic", {})
    diagnostic.setdefault("alertes", []).extend(alertes)
    diagnostic["suivi_plan"] = {"bloc": numero, "fils_servis": valides, "inconnus": inconnus,
                                "nature": "Déclaration du modèle, pas une validation de l'interprétation."}
    return sortie


def bilan_couverture(plan, suivis):
    par_fil = {f["id"]: [bloc for bloc, ids in suivis.items() if f["id"] in ids] for f in plan["fils"]}
    absents = [identifiant for identifiant, blocs in par_fil.items() if not blocs]
    return {"par_fil": par_fil, "fils_sans_bloc": absents,
            "alertes": ["Sujet du plan non déclaré abordé : " + r for r in absents],
            "nature": "Couverture déclarée ; aucune validation du sens ni relance automatique."}
