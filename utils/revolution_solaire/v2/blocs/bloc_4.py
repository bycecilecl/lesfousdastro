"""Transits annuels depuis les calculs archivés ; un seul appel de rédaction."""

from copy import deepcopy
import json
from pathlib import Path

from ..analyse import parser_json_reponse
from .plan_partage import ajouter_plan_entree, consignes_plan, schema_avec_plan, suivre_fils
from ..filtrage_aspects import fait_autorise
from .presentation_faits import compacter_faits
from ..releve_transits import transit_compact
from .bloc_1 import STYLE_PATH, contient_position, nettoyer_parasites
from .suivi_memoire import normaliser_texte
from .calendrier_bloc_4 import assembler_periodes_bloc_4, construire_reperes_calendrier
from .appuis_memoire import copier_mecanisme, verifier_appuis
from .filtrage_transits import (
    ANGLES, CIBLES_EXCLUES, LENTES, PERSONNELLES,
    bornes_transit, motif_exclusion_transit, points_transit,
)


VERSION = "rs_bloc_4_transits_6_maisons_rs"
MAX_TOKENS = 6000
MAX_FAMILLES_LENTES = 12
MAX_DECLENCHEURS_MARS = 4
MAX_PERIODES = 5
MAISONS_CLES_NATALES = frozenset({"1", "2", "4", "7", "10"})
PROMPT_PATH = Path(__file__).with_name("prompt_bloc_4.txt")
REGLES_PATH = Path(__file__).with_name("regles_bloc_4.txt")
CHAMPS_NON_TRANSMIS = frozenset({"orbe", "orbe_deg", "degre", "dignite_essentielle"})


def purger_donnees_bloc_4(objet):
    """Copie destinée au prompt seulement ; précisions brutes conservées en archive."""
    if isinstance(objet, dict):
        return {k: purger_donnees_bloc_4(v) for k, v in objet.items() if k not in CHAMPS_NON_TRANSMIS}
    if isinstance(objet, list):
        return [purger_donnees_bloc_4(v) for v in objet]
    return objet


def consignes_bloc_4():
    """Règles propres aux transits et style commun, sans remplacement de texte caché."""
    return REGLES_PATH.read_text(encoding="utf-8") + "\n" + STYLE_PATH.read_text(encoding="utf-8")


def roles_par_cadre(dossier):
    """Maîtrises et maisons copiées du thème de la cible, pas de l'autre thème."""
    fixes = {"Soleil": ["luminaire"], "Lune": ["luminaire"],
             "Ascendant": ["axe Ascendant–Descendant"], "Descendant": ["axe Ascendant–Descendant"],
             "MC": ["axe MC–FC"], "FC": ["axe MC–FC"]}
    rs, natal = deepcopy(fixes), deepcopy(fixes)
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    for roles in (rs, natal):
        roles.setdefault(maitre, []).append("planète maître de l'année de profection")
    for maison, role in (("1", "maître de l'Ascendant RS"), ("10", "maître de la cuspide 10 RS")):
        for nom in dossier["rs"]["maitrises"][maison]["maitres"]:
            rs.setdefault(nom, []).append(role)
    cles, maitres_asc_natal = set(), set(dossier["natal"]["maitrises"]["1"]["maitres"])
    annuelle = str(dossier["profection"]["maison_annuelle"])
    for maison, maitrise in dossier["natal"]["maitrises"].items():
        for nom in maitrise["maitres"]:
            natal.setdefault(nom, []).append(f"maître de la cuspide {maison} natale ({maitrise['signe']})")
            if str(maison) in MAISONS_CLES_NATALES | {annuelle}:
                cles.add(nom)
    for cadre, roles in (("rs", rs), ("natal", natal)):
        for nom, p in dossier[cadre]["positions"].items():
            if nom in roles and "maison" in p:
                roles[nom].append(f"occupe la maison {p['maison']} {'RS' if cadre == 'rs' else 'natale'}")
    return {"rs": rs, "natal": natal}, cles, maitres_asc_natal


def appuis_annuels_rs(dossier):
    """Repères calculés : maisons regroupées, luminaires, maîtres et figures RS.

    Deux planètes dans une maison suffisent à la retenir. Les Nœuds et points
    secondaires ne comptent pas dans ce regroupement. Aucun thème de vie ni
    événement n'est déduit ici : les références expliquent seulement la sélection.
    """
    catalogue = dossier["faits"]
    positions = {nom: p for nom, p in dossier["rs"]["positions"].items()
                 if nom in PERSONNELLES | LENTES and p.get("maison") is not None}
    occupants = {}
    for nom, p in positions.items():
        occupants.setdefault(str(p["maison"]), set()).add(nom)
    centres = {"Soleil", "Lune", dossier["profection"]["maitre_annee"]["nom"]}
    for maison in ("1", "10"):
        centres.update(dossier["rs"]["maitrises"][maison]["maitres"])
    maisons = {maison for maison, noms in occupants.items() if len(noms) >= 2}
    maisons.update(str(positions[n]["maison"]) for n in centres if n in positions)
    resultat = {}

    def ajouter(nom, *references):
        resultat.setdefault(nom, set()).update(
            r for r in references if r in catalogue and fait_autorise(catalogue[r]))

    for maison in sorted(maisons, key=int):
        maitrise = dossier["rs"]["maitrises"][maison]
        noms = occupants.get(maison, set()) | set(maitrise["maitres"])
        for nom in noms:
            ajouter(nom, f"RS.positions.{nom}", f"RS.maitrises.{maison}")
    for maison in ("1", "10"):
        for nom in dossier["rs"]["maitrises"][maison]["maitres"]:
            ajouter(nom, f"RS.positions.{nom}", f"RS.maitrises.{maison}")
    for cle, fait in catalogue.items():
        if fait["source"] == "rs" and fait["type"] == "configurations" and fait_autorise(fait):
            noms = set(fait["valeur"].get("planetes", [])) & (PERSONNELLES | LENTES)
            if len(noms) >= 3:
                for nom in noms:
                    ajouter(nom, cle, f"RS.positions.{nom}")
    return {nom: sorted(refs) for nom, refs in sorted(resultat.items()) if refs}


def structure_cible(nom, cadre, dossier, roles):
    """Sépare occupation, maîtrises et rôles annuels, à partir des calculs existants.

    Les listes utilisées pour classer les candidats restent inchangées ; cette
    structure concerne uniquement la description des cibles envoyée à l'IA.
    """
    position = dossier[cadre]["positions"].get(nom, {})
    gouvernees = [{"maison": int(maison), "signe_cuspide": m["signe"]}
                 for maison, m in dossier[cadre]["maitrises"].items() if nom in m["maitres"]]
    gouvernees.sort(key=lambda m: m["maison"])
    fonctions = {"luminaire", "axe Ascendant–Descendant", "axe MC–FC"}
    annuels = {"planète maître de l'année de profection", "maître de l'Ascendant RS",
               "maître de la cuspide 10 RS"}
    return {"cadre": cadre, "fonctions": [r for r in roles if r in fonctions],
            "maison_occupee": position.get("maison"), "maisons_gouvernees": gouvernees,
            "roles_annuels": [r for r in roles if r in annuels]}


def nature_bornes_fenetre(evenement):
    """Une borne du cycle n'est pas une sortie d'orbe ni une fin de transit."""
    d = evenement.get("datation") or {}
    debut = ("borne_du_cycle" if d.get("entree_coupee_par_cycle") else
             "entree_d_orbe_calculee" if d.get("entree_utc") else "borne_de_detection")
    fin = ("borne_du_cycle" if d.get("sortie_coupee_par_cycle") else
           "sortie_d_orbe_calculee" if d.get("sortie_utc") else "borne_de_detection")
    resultat = {"debut": debut, "fin": fin}
    if fin == "borne_du_cycle":
        resultat["portee_fin"] = "Fin du cycle étudié ; la fin réelle du transit n'est pas établie par cette date."
    elif fin == "sortie_d_orbe_calculee":
        resultat["portee_fin"] = "Sortie de cette fenêtre d'orbe ; une reprise ultérieure reste possible."
    else:
        resultat["portee_fin"] = "Fin de la fenêtre de détection ; pas une fin exacte de transit garantie."
    return resultat


def ponts_rs_natal_cible(evenement, appuis):
    """Ponts de la cible natale vers les enjeux RS, sans identité d'aspect prétendue."""
    if evenement["reference"] != "natal":
        return []
    noms = _points(evenement)
    candidats = [(cle, f) for cle, f in appuis.items()
                  if f["type"] == "contact" and f["valeur"]["point_natal"] in noms]
    candidats.sort(key=lambda item: (item[1]["valeur"]["point_rs"] not in ANGLES | {"Soleil", "Lune"},
                                     item[1]["valeur"].get("orbe", 999), item[0]))
    return [cle for cle, _ in candidats[:2]]


def _jour(valeur):
    return valeur.split("T", 1)[0] if isinstance(valeur, str) else None


def _bornes(evenement):
    return bornes_transit(evenement)


def _points(evenement):
    return points_transit(evenement)


def _participants(fait):
    """Identités avec leur cadre, sans assimiler une planète RS à sa natale."""
    v, source, categorie = fait["valeur"], fait["source"], fait["type"]
    if categorie == "contact":
        return {("rs", v["point_rs"]), ("natal", v["point_natal"])}
    if source not in {"rs", "natal"}:
        return set()
    if categorie == "aspects":
        noms = {v["planete1"], v["planete2"]}
    elif categorie == "configurations":
        noms = set(v["planetes"])
    elif categorie == "angularites":
        noms = {v["point"], v["angle"]}
    else:
        return set()
    return {(source, nom) for nom in noms}


def _exact(evenement):
    d = evenement.get("datation") or {}
    return bool(d.get("passages_exacts") or
                any(p.get("passages_exacts") for p in d.get("phases", [])))


def _orbe(evenement):
    d = evenement.get("datation") or {}
    return d.get("orbe_minimum", evenement.get("orbe_plus_serre", 999))


def _rappel_bref(evenement):
    d = evenement.get("datation") or {}
    return not _exact(evenement) and bool(d.get("entree_coupee_par_cycle") or d.get("sortie_coupee_par_cycle"))


def liens_calcules_transit(evenement, catalogue, appuis):
    """Même planète RS et même cible ; liens natals conservés sous un cadre séparé.

    Un partage du MC seul ne transforme pas Vénus–MC en lien Uranus–MC.
    Le type d'aspect peut différer entre RS et transit : cette différence reste
    visible dans les faits. Une continuation exige en plus le même aspect.
    """
    noms = _points(evenement)
    cible_rs = evenement["reference"] == "rs" or evenement.get("alias_cible_rs") == "Soleil"
    cibles_rs = noms if evenement["reference"] == "rs" else {"Soleil"} if cible_rs else set()
    liens_rs = []
    for cle, f in catalogue.items():
        if f["source"] != "rs" or f["type"] != "aspects" or not fait_autorise(f):
            continue
        v = f["valeur"]
        a, b = v["planete1"], v["planete2"]
        if ((a == evenement["planete_transit"] and b in cibles_rs) or
                (b == evenement["planete_transit"] and a in cibles_rs)):
            liens_rs.append(cle)
    liens_nataux = []
    if evenement["reference"] == "natal":
        for cle, f in appuis.items():
            v = f["valeur"]
            if f["source"] == "natal" and _participants(f) & {("natal", n) for n in noms}:
                liens_nataux.append(cle)
            elif (f["type"] == "contact" and v["point_rs"] == evenement["planete_transit"]
                  and v["point_natal"] in noms):
                liens_nataux.append(cle)
    return liens_rs, liens_nataux[:2]


def continuite_ouverture(evenement, catalogue, liens_rs, liens_nataux):
    """Associe uniquement des triplets déjà calculés, sans déduire de nouvel aspect."""
    if not (evenement.get("datation") or {}).get("entree_coupee_par_cycle"):
        return None
    # Les deux extrémités d'un axe peuvent porter des aspects complémentaires.
    contacts = [(evenement["cible"], evenement["aspect"])]
    contacts.extend((nom, aspect) for nom, aspect in evenement.get("axe_angles", {}).items())
    contacts.extend((c["cible"], c["aspect"]) for c in evenement.get("contacts_complementaires_axe", []))
    correspondances_rs, correspondances_natales = [], []
    for cle in liens_rs:
        v = catalogue[cle]["valeur"]
        autre = v["planete2"] if v["planete1"] == evenement["planete_transit"] else v["planete1"]
        if any(autre == nom and normaliser_texte(v["aspect"]) == normaliser_texte(aspect) for nom, aspect in contacts):
            correspondances_rs.append(cle)
    for cle in liens_nataux:
        f = catalogue[cle]
        if f["type"] != "contact":
            continue
        v = f["valeur"]
        if any(v["point_natal"] == nom and normaliser_texte(v["aspect"]) == normaliser_texte(aspect) for nom, aspect in contacts):
            correspondances_natales.append(cle)
    if correspondances_rs:
        return {"cadre": "aspect_interne_rs", "references": correspondances_rs}
    if correspondances_natales:
        return {"cadre": "contact_rs_natal", "references": correspondances_natales}
    return {"cadre": "transit_present_a_l_ouverture", "references": []}


def preparer_memoires_bloc_4(memoires, catalogue):
    """Sujets et rôles seulement pour cet appel ; résumés bruts conservés en archive."""
    resultat, ecartes = {}, []
    for bloc in ("bloc_1", "bloc_2", "bloc_3"):
        source = memoires[bloc]
        mecanismes = []
        for m in source.get("mecanismes", []):
            if not isinstance(m, dict) or not all(isinstance(m.get(k), str) for k in ("sujet", "role")):
                continue
            contenu = normaliser_texte(" ".join(m[k] for k in ("sujet", "role")))
            if "part de fortune" in contenu or "point de fortune" in contenu:
                ecartes.append({"bloc": bloc, "mecanisme": deepcopy(m), "motif": "Part de Fortune exclue."})
                continue
            mecanismes.append(copier_mecanisme(m, champs=("sujet", "role")))
        refs = list(source.get("faits_deja_cites", []))
        refs.extend(c["reference"] for c in source.get("faits_cites", [])
                    if isinstance(c, dict) and isinstance(c.get("reference"), str))
        refs = [r for r in dict.fromkeys(refs) if r in catalogue and fait_autorise(catalogue[r])]
        resultat[bloc] = {"mecanismes": mecanismes, "faits_deja_cites": refs}
    return resultat, ecartes


def selectionner_transits_bloc_4(dossier, proprietaires_precedents):
    """Hiérarchie éditoriale explicite, sans calcul de dates ou d'aspects nouveaux.

    Une famille conserve chaque fenêtre séparément. Sa réunion n'implique pas
    que le transit reste actif entre ses passages. Le classement sert à limiter
    l'entrée du modèle ; il ne mesure ni gravité ni probabilité d'événement.
    """
    catalogue = dossier["faits"]
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    roles_cadres, cles_natales, maitres_asc_natal = roles_par_cadre(dossier)
    annuels_rs = appuis_annuels_rs(dossier)
    appuis = {k: catalogue[k] for k in proprietaires_precedents
              if k in catalogue and fait_autorise(catalogue[k]) and _participants(catalogue[k])}
    familles, mars, ecartes = {}, [], []
    for cle, fait in catalogue.items():
        if fait["type"] != "transit":
            continue
        motif = motif_exclusion_transit(dossier, fait)
        if motif:
            ecartes.append({"reference": cle, "motif": motif})
            continue
        e = fait["valeur"]
        noms = _points(e)
        debut, fin = _bornes(e)
        liens_rs, liens_nataux = liens_calcules_transit(e, catalogue, appuis)
        ponts = ponts_rs_natal_cible(e, appuis)
        appuis_annuels = sorted({r for nom in noms for r in annuels_rs.get(nom, [])}) if e["reference"] == "rs" else []
        lies = list(dict.fromkeys(liens_rs + liens_nataux + ponts + appuis_annuels))
        roles = roles_cadres[e["reference"]]
        directeurs = sorted(noms & roles.keys())
        if not directeurs and not lies and not noms & PERSONNELLES:
            ecartes.append({"reference": cle, "motif": "Pas de lien aux facteurs directeurs ni aux faits déjà développés."})
            continue
        entree = {"reference": cle, "evenement": e, "bornes": (debut, fin),
                  "appuis": lies, "liens_rs": liens_rs, "liens_nataux": liens_nataux,
                  "appuis_annuels_rs": appuis_annuels,
                  "ponts_rs_natal": ponts,
                  "roles": {n: roles.get(n, []) for n in sorted(noms)}}
        if e["planete_transit"] == "Mars":
            mars.append(entree)
            continue
        axe = e.get("axe_angles") or e.get("axe_noeuds")
        identite = tuple(sorted(axe)) if axe else (e["cible"], e["aspect"])
        identite = (e["planete_transit"], e["reference"], *identite)
        familles.setdefault(identite, []).append(entree)

    def priorite(lignes):
        noms = set().union(*(_points(l["evenement"]) for l in lignes))
        cadre = lignes[0]["evenement"]["reference"]
        roles = roles_cadres[cadre]
        prioritaires = {"Soleil", "Lune", "Ascendant", "Descendant", "MC", "FC"}
        if cadre == "natal":
            prioritaires |= maitres_asc_natal
        rang = (0 if maitre in noms else 1 if noms & prioritaires
                else 2 if noms & (cles_natales if cadre == "natal" else roles.keys())
                or any(l["ponts_rs_natal"] for l in lignes) else 3)
        return (rang, not any(_exact(l["evenement"]) for l in lignes),
                round(min(_orbe(l["evenement"]) for l in lignes), 1), lignes[0]["reference"])

    eligibles = []
    for lignes in familles.values():
        lignes.sort(key=lambda l: l["bornes"])
        if not any(_exact(l["evenement"]) for l in lignes) and min(_orbe(l["evenement"]) for l in lignes) > 2:
            ecartes.extend({"reference": l["reference"], "motif": "Famille sans passage exact archivé et minimum supérieur à 2°."} for l in lignes)
        else:
            eligibles.append(lignes)
    eligibles.sort(key=priorite)
    # Deux listes indépendantes. À importance comparable, alterner les cadres
    # évite l'éviction du natal ; aucun quota fixe ni présence forcée par période.
    # Le plafond limite les compléments, jamais les facteurs annuels identifiés.
    prioritaires = [l for l in eligibles if priorite(l)[0] <= 1
                    or any(f["appuis_annuels_rs"] for f in l)]
    refs_prioritaires = {f["reference"] for l in prioritaires for f in l}
    listes = {cadre: [l for l in eligibles if l[0]["evenement"]["reference"] == cadre
                     and l[0]["reference"] not in refs_prioritaires]
              for cadre in ("rs", "natal")}
    retenues = list(prioritaires)
    compte = {cadre: sum(l[0]["evenement"]["reference"] == cadre for l in retenues)
              for cadre in ("rs", "natal")}
    while len(retenues) < MAX_FAMILLES_LENTES and any(listes.values()):
        cadre = min((c for c in listes if listes[c]),
                    key=lambda c: (*priorite(listes[c][0])[:3], compte[c], listes[c][0][0]["bornes"]))
        retenues.append(listes[cadre].pop(0))
        compte[cadre] += 1
    retenues.sort(key=priorite)
    choisies = {l["reference"] for lignes in retenues for l in lignes}
    ecartes.extend({"reference": l["reference"], "motif": "Complément secondaire au-delà du budget de familles ; facteurs annuels conservés."}
                  for lignes in eligibles for l in lignes if l["reference"] not in choisies)
    lignes_lentes = [l for lignes in retenues for l in lignes]

    declencheurs = []
    for m in mars:
        rencontres = [l["reference"] for l in lignes_lentes
                      if m["evenement"]["reference"] == l["evenement"]["reference"]
                      and _points(m["evenement"]) & _points(l["evenement"])
                      and m["bornes"][0] <= l["bornes"][1] and l["bornes"][0] <= m["bornes"][1]]
        if rencontres:
            declencheurs.append({**m, "active_avec": rencontres})
        else:
            ecartes.append({"reference": m["reference"], "motif": "Mars sans fenêtre lente simultanée sur la même cible et dans le même cadre."})
    declencheurs.sort(key=lambda l: (not _exact(l["evenement"]), _orbe(l["evenement"]), l["reference"]))
    ecartes.extend({"reference": l["reference"], "motif": "Au-delà des quatre déclencheurs Mars."}
                  for l in declencheurs[MAX_DECLENCHEURS_MARS:])
    declencheurs = declencheurs[:MAX_DECLENCHEURS_MARS]
    selection = lignes_lentes + declencheurs
    contexte = {"PROFECTION.annuelle", "RS.maitrises.1", "RS.maitrises.10"}
    for l in selection:
        cadre = l["evenement"]["reference"]
        cibles = _points(l["evenement"])
        for maison, m in dossier[cadre]["maitrises"].items():
            if cibles & set(m["maitres"]):
                contexte.add(f"{cadre.upper()}.maitrises.{maison}")
    for l in selection:
        contexte.update(l["appuis"])
        e = l["evenement"]
        for nom in _points(e):
            contexte.update({f"{e['reference'].upper()}.positions.{nom}", f"{e['reference'].upper()}.angles.{nom}"})
        if e.get("alias_cible_rs") == "Soleil":
            contexte.add("RS.positions.Soleil")
    faits_contexte = {k: f for k, f in catalogue.items() if k in contexte and fait_autorise(f)}

    def compact(l):
        e = l["evenement"]
        resultat = {"reference": l["reference"], "fait": transit_compact(e),
                    "roles_cible": {n: structure_cible(n, e["reference"], dossier, roles)
                                    for n, roles in l["roles"].items()},
                    "nature_bornes_fenetre": nature_bornes_fenetre(e),
                    "liens_rs_associes": l["liens_rs"],
                    "liens_nataux_associes": l["liens_nataux"],
                    "appuis_annuels_rs": l["appuis_annuels_rs"],
                    "ponts_rs_natal_cible": l["ponts_rs_natal"],
                    "usage": "rappel_bref" if _rappel_bref(e) else "periode_possible"}
        continuite = continuite_ouverture(e, catalogue, l["liens_rs"], l["liens_nataux"])
        if continuite:
            resultat["continuite_ouverture"] = continuite
        return resultat

    calendrier = [{"famille": i, "fenetres": [compact(l) for l in lignes]}
                  for i, lignes in enumerate(retenues, 1)]
    declencheurs_compacts = [{**compact(l), "transits_lents_associes": l["active_avec"]} for l in declencheurs]
    faits_transits = {l["reference"]: catalogue[l["reference"]] for l in selection}
    audit = {"fenetres_calculees": sum(f["type"] == "transit" for f in catalogue.values()),
             "familles_lentes_retenues": len(retenues), "fenetres_transmises": len(selection),
             "declencheurs_mars_retenus": len(declencheurs), "ecartes": ecartes,
             "facteurs_annuels_rs": annuels_rs,
             "familles_prioritaires_hors_plafond": len(prioritaires),
             "familles_par_cadre": compte,
             "nature": "Sélection éditoriale, pas une mesure de gravité ; aucun nouveau calcul astrologique."}
    return faits_transits, faits_contexte, calendrier, declencheurs_compacts, audit


def construire_prompt_bloc_4(dossier, *, memoires, proprietaires_precedents, genre="", plan=None):
    transits, contexte, calendrier, mars, audit = selectionner_transits_bloc_4(dossier, proprietaires_precedents)
    editoriales, ecartes = preparer_memoires_bloc_4(memoires, dossier["faits"])
    entree = {
        "cycle": {k: dossier["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
        "genre": {"female": "féminin", "male": "masculin"}.get(genre, genre),
        "faits_calcules_de_contexte": compacter_faits(contexte),
        "calendrier_selectionne": calendrier, "declencheurs_mars": mars,
        "repartition_des_faits": {"transits": list(transits)},
        "rappel_sujets_et_roles": editoriales,
        "reperes_calendrier": construire_reperes_calendrier(transits, dossier["cycle"]),
        "precision": "Dates au jour UTC ; les fenêtres de détection et les passages exacts sont distincts. Le Soleil RS est un alias du Soleil natal lorsqu'il est signalé.",
    }
    entree = purger_donnees_bloc_4(entree)
    ajouter_plan_entree(entree, plan)
    prompt = consignes_bloc_4() + "\n" + PROMPT_PATH.read_text(encoding="utf-8")
    prompt += consignes_plan(plan)
    prompt += "\nDONNÉES DU BLOC 4\n" + json.dumps(entree, ensure_ascii=False, separators=(",", ":"))
    audit["elements_memoire_non_transmis"] = ecartes
    return prompt, transits, entree, audit


def schema_bloc_4(reperes=None, plan=None):
    def objet(proprietes):
        return {"type": "object", "properties": proprietes, "required": list(proprietes), "additionalProperties": False}
    chaine = {"type": "string"}
    liste_refs = {"type": "array", "items": chaine}
    jour = {"type": "string", **({"enum": list(reperes["jours"])} if reperes and reperes["jours"] else {})}
    return schema_avec_plan(objet({
        "periodes": {"type": "array", "items": objet({
            "titre": chaine, "repere_debut": jour, "repere_fin": jour, "transits": liste_refs,
            "reperes_exacts": liste_refs, "texte": chaine})},
        "memoire": objet({
            "mecanismes": {"type": "array", "items": objet({"sujet": chaine, "role": chaine, "resume": chaine,
                                                           "appuis": liste_refs})},
            "faits_cites": {"type": "array", "items": objet({"reference": chaine, "extrait": chaine})},
        }),
    }), plan)


def generer_bloc_4(dossier, *, appeler, memoires, proprietaires_precedents, genre="", plan=None):
    prompt, transits, entree, audit = construire_prompt_bloc_4(
        dossier, memoires=memoires, proprietaires_precedents=proprietaires_precedents, genre=genre, plan=plan)
    if not transits:
        raise ValueError("Aucun transit retenu : consulte la sélection avant tout appel Claude.")
    resultat = parser_json_reponse(appeler(prompt, max_tokens=MAX_TOKENS, temperature=0.5,
        reflexion="disabled", niveau_effort="low", schema_sortie=schema_bloc_4(entree["reperes_calendrier"], plan=plan)))
    memoire_brute = deepcopy(resultat.get("memoire"))
    periodes_brutes = deepcopy(resultat.get("periodes"))
    texte, periodes, alertes, parasites = assembler_periodes_bloc_4(periodes_brutes, entree["reperes_calendrier"])
    corps = texte
    if not corps.strip():
        alertes.append("Texte du bloc absent ou vide.")
    controle_periodes, utilises = [], set()
    if not 1 <= len(periodes) <= MAX_PERIODES:
        alertes.append("Le calendrier doit comporter une à cinq périodes significatives.")
    for p in periodes:
        if not isinstance(p, dict):
            alertes.append("Période illisible.")
            continue
        refs = p.get("transits", [])
        if not isinstance(refs, list):
            refs = []
        connues = [r for r in refs if isinstance(r, str) and r in transits]
        inconnues = [r for r in refs if not isinstance(r, str) or r not in transits]
        motifs = []
        if inconnues or not connues:
            motifs.append("Références de transit inconnues ou absentes.")
        cadre = sorted({transits[r]["valeur"]["reference"] for r in connues})
        if not p["texte"].strip():
            motifs.append("Texte de période absent ou vide.")
        hors_plage = []
        if p["dates_valides"]:
            for r in connues:
                debut, fin = _bornes(transits[r]["valeur"])
                if fin < p["debut"] or debut > p["fin"]:
                    hors_plage.append(r)
        if hors_plage:
            motifs.append("Transits sans fenêtre commune avec la plage : " + ", ".join(hors_plage))
        if connues and all(_rappel_bref(transits[r]["valeur"]) for r in connues):
            motifs.append("Période fondée uniquement sur des fenêtres coupées sans passage exact : rappels brefs attendus.")
        utilises.update(connues)
        controle_periodes.append({"titre": p.get("titre"), "transits": connues,
                                 "plage_de_lecture": [p["debut"], p["fin"]], "cadres": cadre,
                                 "a_relire": motifs})
        alertes.extend(motifs)
    declaree = resultat.get("memoire")
    if not isinstance(declaree, dict):
        declaree = {}
        alertes.append("Mémoire absente ou illisible.")
    mecanismes, ecartes = [], []
    suivi_appuis = []
    references_recues = set(transits) | set(entree["faits_calcules_de_contexte"])
    declarations = declaree.get("mecanismes", [])
    for m in declarations if isinstance(declarations, list) else []:
        if not isinstance(m, dict) or not all(isinstance(m.get(k), str) and m[k].strip() for k in ("sujet", "role", "resume")):
            alertes.append("Mécanisme de mémoire incomplet.")
        elif any(contient_position(m[k]) for k in ("sujet", "role", "resume")):
            ecartes.append(m)
        else:
            mecanisme, diagnostic_appuis = verifier_appuis(m, dossier["faits"], references_recues)
            mecanismes.append(mecanisme)
            suivi_appuis.append(diagnostic_appuis)
    citations, suivi = [], []
    declarations = declaree.get("faits_cites", [])
    for c in declarations if isinstance(declarations, list) else []:
        if not isinstance(c, dict) or not isinstance(c.get("reference"), str) or c["reference"] not in transits:
            alertes.append("Référence de mémoire absente du calendrier transmis.")
            continue
        extrait = c.get("extrait")
        present = isinstance(extrait, str) and bool(extrait.strip()) and normaliser_texte(extrait) in normaliser_texte(corps)
        statut = "extrait_repere" if present else "a_relire"
        suivi.append({"reference": c["reference"], "statut": statut,
                      "raison": "Repérage littéral seulement ; ni aspect ni date certifiés."})
        citations.append({"reference": c["reference"], "extrait": extrait, "statut": statut})
    if corps.strip() and not mecanismes:
        alertes.append("Mémoire sans mécanisme : les blocs suivants ne disposeront pas du résumé de cette lecture.")
    return suivre_fils({**resultat, "texte": texte, "periodes": periodes, "periodes_brutes": periodes_brutes,
            "memoire_brute": memoire_brute,
            "memoire": {"mecanismes": mecanismes, "faits_cites": citations,
                        "periodes": deepcopy(periodes)},
            "diagnostic": {"alertes": alertes, "nombre_mots": len(corps.split()),
                "nombre_periodes": len(periodes), "controle_periodes": controle_periodes,
                "selection": {k: v for k, v in audit.items() if k != "ecartes"},
                "transits_utilises": [r for r in transits if r in utilises],
                "transits_non_utilises": [r for r in transits if r not in utilises],
                "suivi_citations": suivi, "mecanismes_ecartes": ecartes, "parasites_retires": parasites,
                "suivi_appuis": suivi_appuis,
                "mode_controle": "reperage_non_bloquant_non_validation", "validation_humaine": False}}, plan, 4)
