"""Préparation éditoriale du bloc 3 ; aucune interprétation ni calcul IA."""

from copy import deepcopy
import re


PLANETES = {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}
ANGLES = {"Ascendant", "Descendant", "MC", "FC"}
MAX_MECANISMES_COMPLEMENTAIRES = 3
MAX_APPUIS_PAR_MECANISME = 4


def nettoyer_aides_bloc_3(aides):
    """Nettoie une copie pour le prompt, sans modifier les fiches de la BDD."""
    resultat = deepcopy(aides)
    modifications = []
    for categorie in ("placements", "aspects", "nuances"):
        retenus = []
        for fiche in resultat[categorie]:
            avant = fiche["texte"]
            apres = avant.replace(
                "Le livre évoque des concrétisations parfois tardives, notamment dans les trois derniers mois, mais cette indication de calendrier n'est pas une garantie à appliquer isolément.",
                "Des concrétisations peuvent être tardives, sans garantie de calendrier.")
            apres = re.sub(r"\bLe livre distingue explicitement\s+", "Il faut distinguer clairement ", apres)
            apres = re.sub(r"\bLe livre distingue\s+", "Il faut distinguer ", apres)
            apres = re.sub(r"\bLe livre indique que\s+([a-zà-ÿ])",
                           lambda m: m.group(1).upper(), apres)
            apres = re.sub(r"\bLe livre renforce la vigilance\s+", "Vigilance renforcée ", apres)
            apres = re.sub(r"\bLe reste de la section développe\s+", "Pistes complémentaires : ", apres)
            apres = apres.replace(
                "Vigilance renforcée pour les aspects « difficiles ou stressants », sans nommer dans cette phrase les angles concernés. Cette remarque ne constitue donc pas une distinction explicite entre carré, opposition et conjonction.",
                "Vigilance renforcée pour les aspects difficiles ou stressants, sans généraliser leur effet à tous les aspects.")
            # Une attribution non reconnue n'est pas reconstruite au hasard.
            # Seule sa phrase sort de la copie envoyée ; l'original est archivé.
            paragraphs = []
            for paragraphe in re.split(r"\n\s*\n", apres):
                phrases = re.split(r"(?<=[.!?])\s+", paragraphe)
                phrases = [p for p in phrases if not re.search(r"\blivre\b", p, re.I)]
                if any(p.strip() for p in phrases):
                    paragraphs.append(" ".join(phrases).strip())
            apres = "\n\n".join(paragraphs)
            if apres != avant:
                modifications.append({"categorie": categorie, "faits": fiche.get("faits", [fiche.get("fait")]),
                                      "avant": avant, "apres": apres})
            if apres:
                fiche["texte"] = apres
                retenus.append(fiche)
        resultat[categorie] = retenus
    return resultat, modifications


def acteurs_rs(fait):
    v, categorie = fait["valeur"], fait["type"]
    if categorie == "contact":
        return {v["point_rs"]}
    if fait["source"] != "rs":
        return set()
    if categorie == "aspects":
        return {v["planete1"], v["planete2"]}
    if categorie == "angularites":
        return {v["point"], v["angle"]}
    if categorie == "configurations":
        return set(v["planetes"])
    if categorie in {"positions", "angles"}:
        return {fait["objet"]}
    return set()


def priorite_editoriale(fait):
    """Tri de rédaction, pas un score de dominante ni un nouveau fait astro."""
    v, categorie = fait["valeur"], fait["type"]
    noms = acteurs_rs(fait)
    valeur_orbe = v.get("orbe")
    orbe = valeur_orbe if isinstance(valeur_orbe, (int, float)) else float("inf")
    if categorie in {"aspects", "angularites"} and noms & ANGLES:
        rang = 0 if noms & PLANETES else 5
    elif categorie == "configurations" and len(v["planetes"]) >= 3:
        rang = 1 if v["type"] != "triangle_mineur" else 2
    elif categorie == "contact":
        cible = v["point_natal"]
        rang = 4 if v["point_rs"] in PLANETES and cible in PLANETES | ANGLES else 5
    elif categorie == "aspects":
        rang = 3 if noms <= PLANETES else 5
    else:
        rang = 6
    return rang, orbe


def hierarchiser_complements(faits, parts, deja_traites, dossier):
    """Choisit quelques mécanismes nouveaux et leurs appuis, selon ce thème."""
    references = parts["complements"]
    reserves = {"Soleil", "Lune", *dossier["rs"]["maitrises"]["1"]["maitres"],
                *dossier["rs"]["maitrises"]["10"]["maitres"]}
    # Le maître de la maison d'un luminaire a déjà pu servir à ce rôle.
    for nom in ("Soleil", "Lune"):
        maison = str(dossier["rs"]["positions"][nom]["maison"])
        reserves.update(dossier["rs"]["maitrises"][maison]["maitres"])
    figures_connues = [set(f["fait"]["valeur"]["planetes"]) for f in deja_traites.values()
                       if f["fait"]["source"] == "rs" and f["fait"]["type"] == "configurations"]
    candidats = []
    for cle in references:
        fait = faits[cle]
        if fait["type"] not in {"aspects", "contact", "angularites", "configurations"}:
            continue
        noms = acteurs_rs(fait)
        if fait["source"] == "rs" and fait["type"] == "aspects" and len(noms) == 2 and any(
                noms <= figure for figure in figures_connues):
            continue  # ne recrée pas un mécanisme de figure déjà développé.
        candidats.append(cle)
    candidats.sort(key=lambda cle: (*priorite_editoriale(faits[cle]), cle))
    choix, couverts, figure_choisie = [], set(), False
    for cle in candidats:
        fait = faits[cle]
        noms = acteurs_rs(fait) & PLANETES
        figure = fait["type"] == "configurations" and len(fait["valeur"]["planetes"]) >= 3
        if (figure and figure_choisie) or not noms:
            continue
        nouveaux_roles = noms - reserves
        a_approfondir = nouveaux_roles - couverts
        if choix and not a_approfondir:
            continue
        # Un partenaire déjà développé peut porter le lien principal, mais
        # les appuis suivent les acteurs encore nouveaux de ce mécanisme.
        cibles_appuis = a_approfondir or nouveaux_roles
        appuis = [cle]
        if not figure:
            contacts = int(fait["type"] == "contact")
            for autre in candidats:
                if autre == cle or faits[autre]["type"] == "configurations":
                    continue
                if priorite_editoriale(faits[autre])[0] > 4:
                    continue
                if faits[autre]["type"] == "contact" and contacts >= 1:
                    continue
                if acteurs_rs(faits[autre]) & cibles_appuis and len(appuis) < MAX_APPUIS_PAR_MECANISME:
                    appuis.append(autre)
                    contacts += faits[autre]["type"] == "contact"
        choix.append({"fait_principal": cle, "acteurs_rs": sorted(noms),
                      "acteurs_a_approfondir_rs": sorted(cibles_appuis), "appuis": appuis})
        couverts.update(nouveaux_roles)
        figure_choisie = figure_choisie or figure
        if len(choix) == MAX_MECANISMES_COMPLEMENTAIRES:
            break
    retenus = {cle for groupe in choix for cle in groupe["appuis"]}
    participants = {nom for cle in retenus for nom in acteurs_rs(faits[cle])}
    for nom in participants - reserves:
        cle = f"RS.positions.{nom}"
        if cle in references:
            retenus.add(cle)
        cle = f"SUPERPOSITION.rs_vers_natal.points.{nom}"
        if cle in references:
            retenus.add(cle)
    nouvelle = {**parts, "complements": [cle for cle in references if cle in retenus]}
    return nouvelle, {"mecanismes": choix,
                      "references_secondaires": [cle for cle in references if cle not in retenus],
                      "nature": "Priorité éditoriale selon les faits disponibles, sans validation astrologique."}


def contexte_necessaire(faits, parts, dossier):
    """Positions et cuspides nécessaires aux références développées seulement."""
    retenus = {cle for references in parts.values() for cle in references}
    # Repères courts de continuité : une maison RS de luminaire ne doit pas
    # être confondue avec une projection du MC dans une maison natale.
    for nom in ("Soleil", "Lune"):
        retenus.update({f"RS.positions.{nom}", f"SUPERPOSITION.rs_vers_natal.points.{nom}"})
    noms_rs, noms_natals = set(), set()
    for cle in retenus.intersection(faits):
        fait = faits[cle]
        noms_rs.update(acteurs_rs(fait))
        if fait["source"] == "rs" and fait["type"] == "configurations":
            participants = set(fait["valeur"]["planetes"])
            # Donne les liens calculés de la figure pour en vérifier la forme,
            # sans demander de développer chaque composante séparément.
            retenus.update(ref for ref, f in faits.items() if f["source"] == "rs"
                           and f["type"] == "aspects" and acteurs_rs(f) <= participants)
        if fait["type"] == "contact":
            noms_natals.add(fait["valeur"]["point_natal"])
    for ref, noms in (("RS", noms_rs), ("NATAL", noms_natals)):
        for nom in noms:
            retenus.update({f"{ref}.positions.{nom}", f"{ref}.angles.{nom}"})
            if ref == "RS":
                retenus.add(f"SUPERPOSITION.rs_vers_natal.points.{nom}")
            position = dossier[ref.lower()]["positions"].get(nom)
            if position:
                maison = str(position["maison"])
                retenus.update({f"{ref}.cuspides.{maison}", f"{ref}.maitrises.{maison}"})
                if ref == "RS":
                    retenus.add(f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}")
    return {cle: fait for cle, fait in faits.items() if cle in retenus}
