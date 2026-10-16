"""Prépare les faits du futur plan commun, sans IA, texte généré ni écriture disque.

Le score compte des familles de faits, pas une force astrologique. Les maisons
restent séparées du score. Ce module n'est pas branché à la génération des blocs.
"""

from collections import defaultdict
from copy import deepcopy
from itertools import combinations
import unicodedata

from ..filtrage_aspects import fait_autorise
from .filtrage_transits import (
    LENTES, bornes_transit, motif_exclusion_transit, points_transit,
)


VERSION = "preparation_plan_1_faits_et_maisons"
BOUT_AXE = {"Descendant": "Ascendant", "FC": "MC"}
INVERSE = {"conjonction": "opposition", "opposition": "conjonction",
           "trigone": "sextile", "sextile": "trigone", "carre": "carre"}
POINTS_EXCLUS = frozenset({"Chiron", "Rahu", "Ketu", "Part de Fortune"})


def _norm(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


def _pt(cadre, nom):
    return cadre, BOUT_AXE.get(nom, nom)


def cle_contact(cadre1, point1, cadre2, point2, aspect):
    """Reconnaît les descriptions complémentaires ; ne calcule aucun nouvel aspect.

    Chaque extrémité est traitée, y compris pour Descendant RS / FC natal.
    Sans équivalent connu, les noms et l'aspect restent distincts.
    """
    aspect = _norm(aspect)
    if aspect in INVERSE:
        if point1 in BOUT_AXE:
            point1, aspect = BOUT_AXE[point1], INVERSE[aspect]
        if point2 in BOUT_AXE:
            point2, aspect = BOUT_AXE[point2], INVERSE[aspect]
    return frozenset({(cadre1, point1), (cadre2, point2)}), aspect


def _dates_exactes(evenement):
    datation = evenement.get("datation") or {}
    dates = set()
    for passage in datation.get("passages_exacts", []):
        date = passage.get("date_utc") if isinstance(passage, dict) else passage
        if isinstance(date, str) and date:
            dates.add(date)
    for phase in datation.get("phases", []):
        for date in phase.get("passages_exacts", []):
            if isinstance(date, str) and date:
                dates.add(date)
    # Les deux contacts d'un axe peuvent porter les mêmes dates : une seule occurrence.
    for contact in evenement.get("contacts_complementaires_axe", []):
        for passage in contact.get("passages_exacts", []):
            date = passage.get("date_utc") if isinstance(passage, dict) else passage
            if isinstance(date, str) and date:
                dates.add(date)
    return dates


def collecter_faits(dossier, transit_ok=None, *, diagnostic=None):
    """Réunit les doublons en gardant leurs clés ; transit_ok peut ajouter un filtre."""
    diagnostic = diagnostic if diagnostic is not None else []
    catalogue, faits = dossier["faits"], {}

    def ajouter(identite, famille, points, cles, dates=(), evenement=None):
        ligne = faits.setdefault(identite, {"famille": famille, "points": set(),
                                          "cles": set(), "dates": set(), "transits": {}})
        ligne["points"].update(points)
        ligne["cles"].update(cles)
        ligne["dates"].update(dates)
        if evenement is not None:
            for cle in cles:
                ligne["transits"][cle] = {
                    "reference": cle, "planete": evenement["planete_transit"],
                    "cadre_cible": evenement["reference"], "cible": evenement["cible"],
                    "aspect": evenement["aspect"], "fenetre": list(bornes_transit(evenement)),
                }

    # Les aspects absorbés restent attachés à leur configuration pour être retrouvés.
    aspects = defaultdict(set)
    for cle, fait in catalogue.items():
        if fait["source"] == "rs" and fait["type"] == "aspects" and fait_autorise(fait):
            v = fait["valeur"]
            aspects[cle_contact("rs", v["planete1"], "rs", v["planete2"], v["aspect"])].add(cle)
    absorbes = set()
    for cle, fait in catalogue.items():
        if fait["source"] != "rs" or fait["type"] != "configurations" or not fait_autorise(fait):
            continue
        v, signatures = fait["valeur"], set()
        constitutifs = v.get("aspects_constitutifs") or []
        if constitutifs:
            signatures.update(cle_contact("rs", a["planete1"], "rs", a["planete2"], a["aspect"])
                              for a in constitutifs)
        elif _norm(v["type"]) == "conjonction":
            signatures.update(cle_contact("rs", a, "rs", b, "conjonction")
                              for a, b in combinations(v["planetes"], 2))
        else:
            diagnostic.append({"reference": cle, "motif": "Configuration sans liste d'aspects : doublons non retirés."})
        cles_absorbees = set().union(*(aspects[s] for s in signatures)) if signatures else set()
        absorbes.update(cles_absorbees)
        ajouter(("config", v["id"]), "relation_rs", {_pt("rs", p) for p in v["planetes"]},
                {cle, *cles_absorbees})

    for cle, fait in catalogue.items():
        if not fait_autorise(fait):
            continue
        v, categorie = fait["valeur"], fait["type"]
        if fait["source"] == "rs" and categorie == "aspects" and cle not in absorbes:
            identite = cle_contact("rs", v["planete1"], "rs", v["planete2"], v["aspect"])
            ajouter(("asp", *identite), "relation_rs",
                    {_pt("rs", v["planete1"]), _pt("rs", v["planete2"])}, {cle})
        elif categorie == "contact":
            identite = cle_contact("rs", v["point_rs"], "natal", v["point_natal"], v["aspect"])
            ajouter(("contact", *identite), "contact_rs_natal",
                    {_pt("rs", v["point_rs"]), _pt("natal", v["point_natal"])}, {cle})

    eligibles = []
    for cle, fait in catalogue.items():
        if fait["type"] != "transit":
            continue
        motif = motif_exclusion_transit(dossier, fait)
        if motif is None and transit_ok is not None and not transit_ok(cle, fait):
            motif = "Filtre supplémentaire."
        if motif:
            diagnostic.append({"reference": cle, "motif": motif})
        else:
            eligibles.append((cle, fait["valeur"]))
    lentes = [(cle, e) for cle, e in eligibles if e["planete_transit"] in LENTES]
    for cle, e in eligibles:
        if e["planete_transit"] == "Mars":
            debut, fin = bornes_transit(e)
            lies = [r for r, lent in lentes if lent["reference"] == e["reference"]
                    and points_transit(lent) & points_transit(e)
                    and debut <= bornes_transit(lent)[1] and bornes_transit(lent)[0] <= fin]
            if not lies:
                diagnostic.append({"reference": cle, "motif": "Mars sans transit lent simultané sur la même cible et dans le même thème."})
                continue
        identite = cle_contact("transit", e["planete_transit"], e["reference"], e["cible"], e["aspect"])
        ajouter(("transit", *identite), "transit", {_pt(e["reference"], e["cible"])},
                {cle}, _dates_exactes(e), e)

    # Aucun rôle ajouté parce qu'un point est un luminaire ou une planète focale.
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    if "PROFECTION.annuelle" in catalogue and fait_autorise(catalogue["PROFECTION.annuelle"]):
        ajouter(("role", "annee", maitre), "role_annuel", {("rs", maitre), ("natal", maitre)},
                {"PROFECTION.annuelle"})
    for maison in ("1", "10"):
        cle = f"RS.maitrises.{maison}"
        if cle not in catalogue or not fait_autorise(catalogue[cle]):
            diagnostic.append({"reference": cle, "motif": "Rôle non compté : fait calculé absent ou exclu."})
            continue
        for nom in dossier["rs"]["maitrises"][maison]["maitres"]:
            ajouter(("role", maison, nom), "role_annuel", {("rs", nom)}, {cle})
    return faits


def candidats_convergence(dossier, transit_ok=None, *, diagnostic=None):
    points = defaultdict(lambda: {"familles": set(), "faits": 0, "cles": set(),
                                  "liens": defaultdict(int), "transits": []})
    for ligne in collecter_faits(dossier, transit_ok, diagnostic=diagnostic).values():
        for point in ligne["points"]:
            e = points[point]
            e["familles"].add(ligne["famille"])
            e["faits"] += 1
            e["cles"].update(ligne["cles"])
            for autre in ligne["points"] - {point}:
                e["liens"][autre] += 1
            if ligne["famille"] == "transit":
                e["transits"].append({"contacts_calcules": [ligne["transits"][r] for r in sorted(ligne["transits"])],
                                      "passages": len(ligne["dates"]), "dates": sorted(ligne["dates"])})
    resultat = []
    for (cadre, nom), e in points.items():
        liens = sorted(e["liens"], key=lambda q: (-e["liens"][q], q))
        resultat.append({"point": f"{cadre}:{nom}", "score": len(e["familles"]),
                         "familles": sorted(e["familles"]), "faits_independants": e["faits"],
                         "cles": sorted(e["cles"]),
                         "points_lies": [f"{c}:{n}" for c, n in liens],
                         "transits": sorted(e["transits"], key=lambda t: t["contacts_calcules"][0]["reference"]),
                         "aussi_concerne_par": sorted(e["familles"] - {"transit"}) if "transit" in e["familles"] else []})
    return sorted(resultat, key=lambda e: (-e["score"], -e["faits_independants"], e["point"]))


def construire_contexte_maisons(dossier):
    """Copie les maisons calculées, sans les rapprocher ni leur donner de score."""
    contexte = {}
    for cadre in ("rs", "natal"):
        contexte[cadre] = []
        for nom, position in dossier[cadre]["positions"].items():
            cle = f"{cadre.upper()}.positions.{nom}"
            if nom in POINTS_EXCLUS or cle not in dossier["faits"] or not fait_autorise(dossier["faits"][cle]):
                continue
            contexte[cadre].append({"point": nom, "cadre": cadre,
                                    "maison_occupee": position.get("maison"), "reference": cle})
        contexte[cadre].sort(key=lambda e: e["point"])
    annuelle = dossier["profection"]["maison_annuelle"]
    contexte["profection"] = {
        "reference": "PROFECTION.annuelle", "cadre_maison_annuelle": "natal",
        "maison_annuelle": annuelle,
        "signe_ascendant_profecte": dossier["profection"]["ascendant_profecte"]["signe"],
        "maitre_annee": dossier["profection"]["maitre_annee"]["nom"],
        "ascendant_profecte": {k: dossier["profection"]["ascendant_profecte"][k]
                               for k in ("maison_natale", "maison_rs")},
        "maitrise_natale_maison_annuelle": deepcopy(dossier["natal"]["maitrises"][str(annuelle)]),
        "maitrise_rs_maison_meme_numero": deepcopy(dossier["rs"]["maitrises"][str(annuelle)]),
    }
    return contexte


def preparer_donnees_plan(dossier, transit_ok=None):
    """Données locales seulement ; aucun appel IA ni sélection automatique de sujets."""
    diagnostic = []
    return {"version": VERSION,
            "candidats": candidats_convergence(dossier, transit_ok, diagnostic=diagnostic),
            "contexte_maisons": construire_contexte_maisons(dossier),
            "diagnostic": diagnostic,
            "nature": "Nombre de familles de faits ; ne mesure ni force, gravité ni probabilité. Les maisons ne sont pas scorées.",
            "limite_transits": "Préselection avant rédaction, sans les plafonds ni le choix de périodes du bloc 4. Mars reste un déclencheur rattaché à un transit lent."}
