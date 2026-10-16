"""Mémoire locale de tendances et faits compacts ; aucune génération IA.

Les tendances sont des pistes d'interprétation, jamais des faits astrologiques.
Les anciennes archives fournissent des mots-clés et, si possible, de courts
extraits non techniques. Ce procédé n'est pas un résumé sémantique complet.
"""

from copy import deepcopy
import re
import unicodedata

from .filtrage_aspects import fait_autorise
from .releve_rs import degres_minutes, profection_compacte
from .releve_transits import transit_compact


VOCABULAIRE = {
    "affirmation personnelle": ("identit", "affirm", "confiance"),
    "argent et valeur personnelle": ("argent", "financ", "valeur", "ressource"),
    "liens et engagements": ("relation", "engagement", "attachement", "affect"),
    "autonomie et changement": ("libert", "rupture", "independance", "changement"),
    "vocation et reconnaissance": ("vocation", "profession", "reconnaissance"),
    "projets et réseaux": ("collectif", "reseau", "projet", "amitie"),
    "sécurité émotionnelle": ("securite", "emotion", "inquietude", "besoin"),
    "foyer et création": ("foyer", "logement", "creati", "plaisir"),
    "limites et responsabilités": ("limite", "responsabil", "contraint", "structur"),
    "convictions et direction": ("conviction", "sens", "direction", "ideal"),
}
TECHNIQUE = re.compile(
    r"soleil|lune|mercure|venus|mars|jupiter|saturne|uranus|neptune|pluton|chiron|"
    r"rahu|ketu|fortune|ascendant|descendant|\bmc\b|\bfc\b|\brs\b|natal|"
    r"maison|maitr|cuspide|orbe|conjonct|sextile|trigone|opposit|quinconce|"
    r"carre|figure|intercept|dignite|exalt|\bchute\b|\bexil\b|contact\."
)


def _normalise(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


def construire_memoire(analyses):
    tendances = []
    for etape, precedente in analyses.items():
        for enjeu in precedente["enjeux"]:
            contenu = _normalise(enjeu["titre"] + " " + enjeu["lecture"])
            themes = [theme for theme, termes in VOCABULAIRE.items()
                      if any(terme in contenu for terme in termes)]
            phrases = re.split(r"(?<=[.!?])\s+|\n+", enjeu["lecture"])
            extraits = [p.strip() for p in phrases
                        if p.strip() and len(p) <= 400 and not TECHNIQUE.search(_normalise(p))
                        and not re.search(r"\d|[°′]", p)]
            tendance = {"id": enjeu["id"], "origine": etape,
                        "importance": enjeu["importance"], "themes_abordes": themes,
                        "apport": enjeu["effet"], "liens": deepcopy(enjeu["liens"]),
                        "preuves": deepcopy(enjeu["preuves"])}
            if extraits:
                tendance["extraits_interpretatifs"] = extraits[:2]
            if enjeu.get("periodes"):
                tendance["fenetres_a_rehierarchiser"] = deepcopy(enjeu["periodes"])
            tendances.append(tendance)
    return {"tendances": tendances,
            "nature": "Mots-clés et extraits de pistes interprétatives ; ni texte à recopier ni source technique."}


def faits_pour_redaction(dossier, analyses, corps=None):
    catalogue = dossier["faits"]
    retenus = ({p for a in analyses.values() for e in a["enjeux"] for p in e["preuves"]}
               if corps is None else {p for s in corps["sections"] for p in s["preuves"]})
    retenus.update({"RS.angles.Ascendant", "RS.angles.MC", "RS.positions.Soleil",
                    "RS.positions.Lune", "RS.maitrises.1", "RS.maitrises.10", "PROFECTION.annuelle"})
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    retenus.update({f"NATAL.positions.{maitre}", f"RS.positions.{maitre}"})
    participants = set()
    for cle in list(retenus):
        fait = catalogue.get(cle)
        if fait is None:
            continue
        v = fait["valeur"]
        if cle.startswith("CONTACT."):
            participants.update({("RS", v["point_rs"]), ("NATAL", v["point_natal"])})
        elif cle.startswith("TRANSIT."):
            participants.add((v["reference"].upper(), v["cible"]))
        elif fait["source"] in {"natal", "rs"}:
            ref = fait["source"].upper()
            if fait["type"] == "aspects":
                participants.update({(ref, v["planete1"]), (ref, v["planete2"])})
            elif fait["type"] == "configurations":
                participants.update((ref, nom) for nom in v["planetes"])
            elif fait["type"] == "maitrises":
                participants.update((ref, nom) for nom in v["maitres"])
            elif fait["type"] == "angularites":
                participants.update({(ref, v["point"]), (ref, v["angle"])})
    for ref, nom in participants:
        retenus.update({f"{ref}.positions.{nom}", f"{ref}.angles.{nom}"})
    return {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}


def compacter_faits(faits):
    resultat = {}
    for cle, fait in faits.items():
        v, categorie = fait["valeur"], fait["type"]
        if cle.startswith("TRANSIT."):
            compact = transit_compact(v)
        elif cle.startswith("CONTACT."):
            compact = {k: v[k] for k in ("point_rs", "aspect", "point_natal")}
            compact["orbe"] = degres_minutes(v["orbe"])
        elif cle.startswith("PROFECTION."):
            compact = profection_compacte(v)
        elif cle.startswith("SUPERPOSITION."):
            compact = {"maison_arrivee": v["maison_cible"]}
        elif categorie in {"positions", "angles", "cuspides"}:
            compact = {"signe": v["signe"], "degre": degres_minutes(v["degre_dans_signe"])}
            for k in ("maison", "retrograde", "dignite_essentielle"):
                if k in v:
                    compact[k] = v[k]
        elif categorie == "aspects":
            compact = {k: v[k] for k in ("planete1", "aspect", "planete2")}
            compact["orbe"] = degres_minutes(v["orbe"])
        elif categorie == "angularites":
            compact = {"point": v["point"], "angle": v["angle"], "orbe": degres_minutes(v["orbe"])}
        elif categorie == "configurations":
            compact = {k: deepcopy(v[k]) for k in
                       ("type", "planetes", "planete_focale", "planetes_en_opposition") if k in v}
        else:
            compact = deepcopy(v)
        resultat[cle] = compact
    return resultat
