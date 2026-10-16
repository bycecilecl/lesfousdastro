"""Conclusion contextuelle : mémoires courtes et faits calculés, un appel maximum."""

from copy import deepcopy
import json
from pathlib import Path
import re

from ..analyse import parser_json_reponse
from .plan_partage import ajouter_plan_entree, consignes_plan, schema_avec_plan, suivre_fils
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from .bloc_1 import STYLE_PATH, nettoyer_parasites
from .bloc_4 import ANGLES, roles_par_cadre, structure_cible, purger_donnees_bloc_4, nature_bornes_fenetre
from .suivi_memoire import normaliser_texte
from .appuis_memoire import copier_mecanisme, verifier_appuis


VERSION = "rs_bloc_5_conclusion_5_activations_sans_plafond"
MAX_TOKENS = 4000
MAX_APPUIS = 10
PROMPT_PATH = Path(__file__).with_name("prompt_bloc_5.txt")
REGLES_PATH = Path(__file__).with_name("regles_bloc_5.txt")


def preparer_memoires_bloc_5(memoires, faits_catalogue):
    """Garde les mécanismes et leur interprétation, pas les paragraphes ou scènes."""
    resultat, ecartes, appuis_requis, suivi = {}, [], [], []
    for numero in range(1, 5):
        bloc = f"bloc_{numero}"
        mecanismes = []
        source = memoires[bloc]
        for m in source.get("mecanismes", []):
            if not isinstance(m, dict) or not all(isinstance(m.get(k), str) for k in ("sujet", "role", "resume")):
                continue
            contenu = normaliser_texte(" ".join(m[k] for k in ("sujet", "role", "resume")))
            if re.search(r"\b(?:chiron|rahu|ketu|noeuds?|part de fortune|point de fortune)\b", contenu):
                ecartes.append({"bloc": bloc, "mecanisme": deepcopy(m), "motif": "Point exclu de la conclusion."})
                continue
            # Corriger seulement la copie transmise ; l'archive source reste intacte.
            mecanisme = copier_mecanisme(m)
            if (normaliser_texte(mecanisme["sujet"]).startswith("interception ")
                    and normaliser_texte(mecanisme["role"]) == "maitres de l'ascendant"):
                mecanisme["role"] = "interception des signes"
            mecanisme["resume"] = mecanisme["resume"].replace(
                "avec une tension image du mot qui sort plus vite que la réflexion",
                "avec une parole qui peut sortir plus vite que la réflexion")
            mecanisme, diagnostic = verifier_appuis(mecanisme, faits_catalogue)
            suivi.append({"bloc": bloc, **diagnostic})
            if "appuis" in mecanisme and not mecanisme["appuis"]:
                ecartes.append({"bloc": bloc, "mecanisme": deepcopy(m),
                                "motif": "Appuis déclarés vides, mal formés ou sans fait autorisé disponible."})
                continue
            appuis_requis.extend(mecanisme.get("appuis", []))
            mecanismes.append(mecanisme)
        resultat[bloc] = {"mecanismes": mecanismes,
                          "nature": "Interprétations conservées ; aucune autorité sur les faits techniques."}
    return resultat, ecartes, list(dict.fromkeys(appuis_requis)), suivi


def selectionner_reperes_bloc_5(dossier, proprietaires, appuis_requis=()):
    """Repères directeurs et quelques appuis du rapport, sans inventaire complet."""
    catalogue = dossier["faits"]
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    centres = {"Soleil", "Lune", "Ascendant", "MC", maitre,
               *dossier["rs"]["maitrises"]["1"]["maitres"],
               *dossier["rs"]["maitrises"]["10"]["maitres"]}
    roles, _, _ = roles_par_cadre(dossier)
    refs = {"PROFECTION.annuelle", "RS.maitrises.1", "RS.maitrises.10",
            f"NATAL.positions.{maitre}"}
    refs.update(f"RS.positions.{nom}" for nom in centres)
    refs.update(f"RS.angles.{nom}" for nom in centres)
    # Le maître de la maison occupée par un luminaire reste distinct du luminaire.
    for nom in ("Soleil", "Lune"):
        refs.add(f"RS.maitrises.{dossier['rs']['positions'][nom]['maison']}")
    candidats = []
    for cle in proprietaires:
        f = catalogue.get(cle)
        if f is None or not fait_autorise(f):
            continue
        v, categorie = f["valeur"], f["type"]
        if f["source"] == "rs" and categorie == "configurations" and len(v.get("planetes", [])) >= 3:
            rang = 0
        elif f["source"] == "rs" and categorie == "aspects":
            noms = {v["planete1"], v["planete2"]}
            if not noms & centres:
                continue
            rang = 1 if {"Soleil", "Lune"} <= noms else 2 if noms & {"Soleil", "Lune"} else 3
        elif categorie == "contact" and v["point_rs"] in centres:
            rang = 4 if v["point_rs"] in ANGLES else 5
        else:
            continue
        candidats.append((rang, cle))
    candidats.sort()
    refs.update(cle for cle in appuis_requis if cle in catalogue and fait_autorise(catalogue[cle]))
    complements = [(rang, cle) for rang, cle in candidats if cle not in refs]
    refs.update(cle for _, cle in complements[:MAX_APPUIS])
    retenus = {k: f for k, f in catalogue.items() if k in refs and fait_autorise(f)}
    roles_directeurs = {nom: structure_cible(nom, "rs", dossier, roles["rs"].get(nom, []))
                       for nom in sorted(centres) if nom in roles["rs"]}
    roles_directeurs["maitre_annee_natal"] = structure_cible(maitre, "natal", dossier, roles["natal"].get(maitre, []))
    return retenus, roles_directeurs


def construire_prompt_bloc_5(dossier, *, memoires, periodes, proprietaires, contexte_client=None, genre="", plan=None):
    editoriales, ecartes, appuis_requis, suivi_appuis = preparer_memoires_bloc_5(memoires, dossier["faits"])
    faits, roles = selectionner_reperes_bloc_5(dossier, proprietaires, appuis_requis)
    moments = []
    for p in periodes if isinstance(periodes, list) else []:
        if not isinstance(p, dict):
            continue
        refs = p.get("transits", [])
        if not isinstance(refs, list):
            refs = []
        # Les périodes proviennent du calendrier significatif du bloc 4 :
        # conserver chacune de leurs activations, pas seulement les deux premières.
        refs = dict.fromkeys(r for r in refs if isinstance(r, str))
        transits = [(r, dossier["faits"][r]["valeur"]) for r in refs
                    if r in dossier["faits"] and dossier["faits"][r]["type"] == "transit"]
        maitre = dossier["profection"]["maitre_annee"]["nom"]
        transits.sort(key=lambda x: (x[1]["cible"] != maitre, x[1]["planete_transit"] == "Mars", x[0]))
        moments.append({"plage_de_lecture": [p.get("debut"), p.get("fin")],
                        "activations_retenues": [{"reference_calcul": r, "planete_mobile": e["planete_transit"],
                            "cible": e["cible"], "cadre_cible": e["reference"], "aspect": e["aspect"],
                            "nature_bornes_fenetre": nature_bornes_fenetre(e)} for r, e in transits]})
    contexte = deepcopy(contexte_client) if isinstance(contexte_client, dict) else {}
    entree = {"cycle": {"debut": dossier["cycle"]["debut_utc"][:10],
                         "fin": dossier["cycle"]["fin_utc"][:10], "annee": dossier["cycle"]["annee"]},
              "genre": {"female": "féminin", "male": "masculin"}.get(genre, genre),
              "memoires_des_enjeux": editoriales,
              "reperes_calcules": compacter_faits(faits), "roles_calcules": roles,
              "moments_de_l_annee": moments, "informations_personnelles_de_depart": contexte}
    entree = purger_donnees_bloc_4(entree)
    ajouter_plan_entree(entree, plan)
    prompt = REGLES_PATH.read_text(encoding="utf-8") + "\n" + STYLE_PATH.read_text(encoding="utf-8")
    prompt += "\n" + PROMPT_PATH.read_text(encoding="utf-8")
    prompt += consignes_plan(plan)
    prompt += "\nDONNÉES DU BLOC 5\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    return prompt, entree, ecartes, suivi_appuis


def schema_bloc_5(plan=None):
    chaine = {"type": "string"}
    enjeu = {"type": "object", "properties": {"enjeu": chaine, "texte": chaine},
             "required": ["enjeu", "texte"], "additionalProperties": False}
    return schema_avec_plan({"type": "object", "properties": {
            "synthese_annuelle": {"type": "array", "items": enjeu},
            "mise_en_perspective_personnelle": chaine,
            "informations_personnelles_utilisees": {"type": "array", "items": chaine}},
            "required": ["synthese_annuelle", "mise_en_perspective_personnelle", "informations_personnelles_utilisees"],
            "additionalProperties": False}, plan)


def contexte_renseigne(contexte):
    return any(bool(v) and (not isinstance(v, str) or normaliser_texte(v) not in {"", "ras"})
               for v in contexte.values())


def assembler_conclusion(resultat, contexte):
    """Bilan d'abord, contexte ensuite ; aucun paragraphe réécrit ou complété localement."""
    alertes, synthese, titres = [], [], []
    declares = resultat.get("synthese_annuelle")
    if isinstance(declares, list):
        for numero, enjeu in enumerate(declares, 1):
            if not isinstance(enjeu, dict) or not isinstance(enjeu.get("texte"), str) or not enjeu["texte"].strip():
                alertes.append(f"Enjeu annuel {numero} sans développement écrit.")
                continue
            synthese.append(enjeu["texte"].strip())
            titre = enjeu.get("enjeu")
            if not isinstance(titre, str) or not titre.strip():
                alertes.append(f"Enjeu annuel {numero} sans intitulé interne.")
            else:
                titres.append(titre)
        if not 2 <= len(synthese) <= 3:
            alertes.append("Le bilan annuel doit développer deux ou trois enjeux, pas seulement les déclarer.")
    else:
        alertes.append("Bilan annuel structuré absent ; ancien format ou réponse à relire.")
        # Les anciennes réponses restent consultables, sans interpréter leur contenu.
        if isinstance(resultat.get("texte"), str) and resultat["texte"].strip():
            synthese.append(resultat["texte"].strip())
    personnel = resultat.get("mise_en_perspective_personnelle")
    if not isinstance(personnel, str):
        personnel = ""
    personnel = personnel.strip()
    if contexte_renseigne(contexte):
        if not personnel:
            alertes.append("Contexte personnel renseigné, mais mise en perspective personnelle absente.")
    else:
        # Le bilan annuel tient seul ; aucune phrase client sur le manque de contexte.
        personnel = ""
    bilan = "\n\n".join(synthese)
    texte = "\n\n".join(t for t in (bilan, personnel) if t)
    mots = len(texte.split())
    if not texte:
        alertes.append("Conclusion absente ou vide.")
    elif mots < 350:
        alertes.append(f"Conclusion trop courte pour le bilan demandé : {mots} mots.")
    elif mots > 600:
        alertes.append(f"Conclusion longue pour une page : {mots} mots ; vérifier le rendu PDF.")
    return texte, titres, {"alertes": alertes, "nombre_enjeux_developpes": len(synthese),
                          "nombre_mots_synthese": len(bilan.split()),
                          "nombre_mots_contexte": len(personnel.split()),
                          "nombre_mots": mots, "fourchette_mots_visee": [400, 550]}


def generer_bloc_5(dossier, *, appeler, memoires, periodes, proprietaires, contexte_client=None, genre="", plan=None):
    prompt, entree, ecartes, suivi_appuis = construire_prompt_bloc_5(dossier, memoires=memoires,
        periodes=periodes, proprietaires=proprietaires, contexte_client=contexte_client, genre=genre, plan=plan)
    resultat = parser_json_reponse(appeler(prompt, max_tokens=MAX_TOKENS, temperature=0.5,
        reflexion="disabled", niveau_effort="low", schema_sortie=schema_bloc_5(plan=plan)))
    contexte = entree["informations_personnelles_de_depart"]
    texte, enjeux, diagnostic_structure = assembler_conclusion(resultat, contexte)
    parasites = []
    if isinstance(texte, str):
        texte, parasites = nettoyer_parasites(texte)
    corps = texte if isinstance(texte, str) else ""
    alertes = list(diagnostic_structure["alertes"])
    memoires_vides = [nom for nom, memoire in entree["memoires_des_enjeux"].items()
                     if not memoire["mecanismes"]]
    for nom in memoires_vides:
        alertes.append(f"Mémoire {nom} sans mécanisme transmis : ses interprétations ne sont pas résumées pour la conclusion.")
    informations = resultat.get("informations_personnelles_utilisees", [])
    if not isinstance(informations, list):
        informations = []
        alertes.append("Suivi du contexte personnel illisible.")
    inconnues = [c for c in informations if not isinstance(c, str) or c not in contexte]
    if inconnues:
        alertes.append("Des clés du contexte déclarées utilisées ne sont pas dans les informations de départ.")
    return suivre_fils({**resultat, "texte": texte, "enjeux_retenus": enjeux,
            "diagnostic": {**diagnostic_structure, "alertes": alertes, "nombre_mots": len(corps.split()),
                "memoires_vides": memoires_vides,
                "informations_personnelles_disponibles": list(contexte),
                "informations_personnelles_declarees_utilisees": informations,
                "elements_memoire_non_transmis": ecartes, "parasites_retires": parasites,
                "suivi_appuis": suivi_appuis,
                "nature": "Structure et déclaration du contexte seulement ; pas une validation du contenu.",
                "validation_humaine": False}}, plan, 5)
