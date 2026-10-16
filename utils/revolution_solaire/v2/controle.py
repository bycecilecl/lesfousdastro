"""Contrôles bloquants de structure, références et facteurs prioritaires.

Ils ne prouvent pas la justesse de toute interprétation astrologique ni la
couverture sémantique du texte : cette limite est conservée dans les diagnostics.
"""

import re
import unicodedata

from ..archives_generation import GenerationARevoir
from .controle_superpositions import controler_superpositions, decrire_contradictions


class AnalyseRSInvalide(GenerationARevoir):
    """Résultat sauvegardé ; pas de nouvelle facturation automatique."""


def _exiger(condition, message):
    if not condition:
        raise AnalyseRSInvalide(message)


def _texte(valeur):
    return isinstance(valeur, str) and bool(valeur.strip())


def _ids(valeur, autorises, *, vide=True):
    return (isinstance(valeur, list) and (vide or bool(valeur))
            and all(isinstance(item, str) and item in autorises for item in valeur)
            and len(valeur) == len(set(valeur)))


def controler_assertions_rs_seule(resultat, faits):
    """Repère des assertions groupées que le contrôleur historique ignore.

    Applicable seulement à une lecture RS isolée : aucune carte implicite
    n'est choisie dans une comparaison natale/RS. Ne réécrit aucun texte.
    """
    positions = {fait["objet"]: fait["valeur"] for cle, fait in faits.items()
                 if cle.startswith("RS.positions.")}
    if not positions:
        return {"erreurs": [], "portee": "assertions groupées de la RS seule"}

    def normaliser(texte):
        texte = unicodedata.normalize("NFD", texte.lower().replace("œ", "oe"))
        return "".join(c for c in texte if unicodedata.category(c) != "Mn")

    noms = {normaliser(n): n for n in positions}
    motif_nom = "|".join(re.escape(n) for n in sorted(noms, key=len, reverse=True))
    groupe = rf"(?P<p1>{motif_nom})(?:\s+rs)?\s+et\s+(?P<p2>{motif_nom})(?:\s+rs)?"
    conjonction = re.compile(rf"\b{groupe}\s+(?:sont\s+)?conjoint(?:s|es|e)?\b")
    maison = re.compile(rf"\b{groupe}\s+(?P<description>[^.!?;\n]{{0,100}}?)\bmaison\s+(?P<n>\d+|[ivx]+)\b")
    aspects = {frozenset((v["planete1"], v["planete2"]))
               for cle, fait in faits.items() if cle.startswith("RS.aspects.")
               for v in [fait["valeur"]] if normaliser(v.get("aspect", "")) == "conjonction"}
    romains = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
               "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
    textes = [resultat.get("ambiance", "")]
    for enjeu in resultat.get("enjeux", []):
        textes.extend((enjeu.get("titre", ""), enjeu.get("lecture", "")))
    erreurs, deja = [], set()
    for texte in textes:
        for phrase in re.split(r"(?<=[.!?;])\s+|\n", texte):
            normalise = normaliser(phrase)
            if re.search(r"\b(?:pas|jamais|si|pourrait|serait|pourraient|seraient)\b", normalise):
                continue
            for match in conjonction.finditer(normalise):
                paire = frozenset((noms[match["p1"]], noms[match["p2"]]))
                cle = ("conjonction_absente", tuple(sorted(paire)))
                if paire not in aspects and cle not in deja:
                    erreurs.append({"code": cle[0], "points": list(sorted(paire)), "extrait": phrase})
                    deja.add(cle)
            for match in maison.finditer(normalise):
                # Une reprise du sujet ou deux maisons distinctes ne sont
                # pas un placement commun : ne pas inventer une contradiction.
                suite = normalise[match.end():]
                if ("respectivement" in normalise
                        or re.search(rf"\b(?:{motif_nom})\b", match["description"])
                        or re.match(r"\s*(?:et|/|,)\s*(?:en\s+)?(?:maison\s+)?(?:\d+|[ivx]+)\b", suite)):
                    continue
                annonce = int(match["n"]) if match["n"].isdigit() else romains.get(match["n"])
                for nom in (noms[match["p1"]], noms[match["p2"]]):
                    attendu = positions[nom].get("maison")
                    cle = ("maison_groupee_contradictoire", nom, annonce)
                    if annonce is not None and attendu is not None and annonce != attendu and cle not in deja:
                        erreurs.append({"code": cle[0], "point": nom, "annonce": annonce,
                                        "attendu": attendu, "extrait": phrase})
                        deja.add(cle)
    return {"erreurs": erreurs, "portee": "conjonctions et maisons attribuées explicitement à deux points RS"}


def faits_incontournables(etape, faits):
    """Socle et facteurs serrés qui ne peuvent pas être simplement écartés."""
    socle = {"RS.angles.Ascendant", "RS.angles.MC", "RS.positions.Soleil", "RS.positions.Lune",
             "RS.maitrises.1", "RS.maitrises.10", "PROFECTION.annuelle"}
    resultat = {cle for cle in faits if cle in socle}
    planetes = {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}
    for cle, fait in faits.items():
        valeur = fait.get("valeur") or {}
        if etape == "rs_seule":
            if cle.startswith("RS.configurations.") and valeur.get("type") in {
                "stellium", "t_carre", "grand_trigone", "grand_carre", "diamant",
            }:
                resultat.add(cle)
            if cle.startswith("RS.angularites.") and valeur.get("point") in planetes and valeur.get("orbe", 99) <= 3:
                resultat.add(cle)
            if cle.startswith("RS.aspects.") and valeur.get("aspect", "").lower() in {"carre", "carré", "opposition"}:
                membres = {valeur.get("planete1"), valeur.get("planete2")}
                if membres & {"Soleil", "Lune"} and membres & {"Saturne", "Uranus", "Neptune", "Pluton"} and valeur.get("orbe", 99) <= 6:
                    resultat.add(cle)
        if etape == "contacts_rs_natal" and cle.startswith("CONTACT."):
            angles = {"Ascendant", "Descendant", "MC", "FC"}
            seuil = 4 if valeur.get("point_rs") in angles and valeur.get("point_natal") in angles else 2.5
            if valeur.get("aspect", "").lower() == "conjonction" and valeur.get("orbe", 99) <= seuil:
                resultat.add(cle)
    return resultat


def controler_etape(etape, resultat, entree):
    faits = entree["faits"]
    precedents = {e["id"] for a in entree["analyses_precedentes"].values() for e in a["enjeux"]}
    enjeux = resultat.get("enjeux")
    _exiger(isinstance(enjeux, list), "Enjeux manquants.")
    ids_courants = {e.get("id") for e in enjeux if isinstance(e, dict) and isinstance(e.get("id"), str)}
    index = {}
    for enjeu in enjeux:
        _exiger(isinstance(enjeu, dict), "Enjeu invalide.")
        identifiant = enjeu.get("id")
        _exiger(_texte(identifiant) and identifiant.startswith(etape + "-") and identifiant not in index,
                "Identifiant d'enjeu absent, dupliqué ou hors étape.")
        _exiger(_texte(enjeu.get("titre")) and _texte(enjeu.get("lecture")), "Lecture/titre manquant.")
        _exiger(enjeu.get("importance") in {"majeur", "secondaire"}, "Importance invalide.")
        _exiger(enjeu.get("effet") in {"initial", "confirme", "amplifie", "nuance", "contredit", "distinct"},
                "Effet invalide.")
        preuves = enjeu.get("preuves")
        inconnues = [p for p in preuves if not isinstance(p, str) or p not in faits] if isinstance(preuves, list) else ["liste de preuves manquante"]
        _exiger(_ids(preuves, faits, vide=False),
                f"Preuve inconnue, absente ou dupliquée dans {identifiant} : {inconnues or preuves!r}.")
        for exemple in enjeu.get("exemples", []):
            _exiger(isinstance(exemple, dict) and _texte(exemple.get("texte")), "Exemple vide ou invalide.")
            _exiger(_ids(exemple.get("preuves"), enjeu["preuves"], vide=False), "Exemple sans preuve de son enjeu.")
            # L'exemple illustre un enjeu déjà expliqué : sa référence précise
            # peut pointer le déclencheur, tandis que l'enjeu apporte les autres
            # indices. Le paragraphe reste le contexte du scénario.
            _exiger(len(set(enjeu["preuves"])) >= 2, "Exemple concret sans enjeu étayé par plusieurs faits.")
        _exiger(_ids(enjeu.get("liens"), (precedents | ids_courants) - {identifiant}), "Lien vers un enjeu inconnu ou vers lui-même.")
        if enjeu["importance"] == "majeur":
            _exiger(len(enjeu["preuves"]) >= 2, "Un enjeu majeur exige plusieurs faits distincts.")
            if "exemples" in enjeu:
                _exiger(len(enjeu["exemples"]) >= 2, "Un enjeu majeur exige deux exemples concrets.")
        if etape == "activations_annuelles":
            transits = {cle for cle in faits if cle.startswith("TRANSIT.")}
            _exiger(_ids(enjeu.get("periodes"), transits, vide=False), "Période non calculée.")
            _exiger(set(enjeu["periodes"]) <= set(enjeu["preuves"]), "Période absente des preuves.")
        elif enjeu.get("periodes"):
            raise AnalyseRSInvalide("Une étape non temporelle annonce des périodes.")
        index[identifiant] = enjeu
    if etape == "rs_seule":
        _exiger(_texte(resultat.get("ambiance")) and bool(enjeux), "Ambiance RS absente.")
        assertions = controler_assertions_rs_seule(resultat, faits)
        _exiger(not assertions["erreurs"],
                "Contradictions dans la RS seule : " + "; ".join(
                    e["code"] + " — " + e["extrait"] for e in assertions["erreurs"]))
    if etape == "superpositions_maisons":
        projections = controler_superpositions(resultat, faits)
        if projections["erreurs"]:
            erreur = AnalyseRSInvalide("Contradictions de superpositions :\n" + decrire_contradictions(projections))
            erreur.diagnostic_superpositions = projections
            raise erreur
    references = {p for enjeu in enjeux for p in enjeu["preuves"]}
    references_precedentes = {p for a in entree["analyses_precedentes"].values()
                             for e in a["enjeux"] for p in e["preuves"] if p in faits}
    prioritaires = set(entree.get("faits_incontournables", []))
    manquants = prioritaires - references - references_precedentes
    _exiger(not manquants, "Facteurs prioritaires sans référence : " + ", ".join(sorted(manquants)))
    return {"statut": "valide", "faits_references": len(references), "enjeux": len(enjeux),
            "portee": "références, liens et facteurs prioritaires ; pas une certification sémantique"}


def controler_analyse_rs(dossier, analyses):
    from .analyse import ETAPES, construire_entree_etape
    controles, precedentes = {}, {}
    _exiger(set(analyses) == set(ETAPES), "Une étape d'analyse obligatoire est absente.")
    for etape in ETAPES:
        controles[etape] = controler_etape(etape, analyses[etape], construire_entree_etape(etape, dossier, precedentes))
        precedentes[etape] = analyses[etape]
    return {"statut": "valide", "etapes": controles}


def controler_redaction(resultat, dossier, analyses, *, exiger_majeurs=True, couverture_bloquante=True,
                       faits_autorises=None):
    enjeux = {e["id"]: e for a in analyses.values() for e in a["enjeux"]}
    preuves_transmises = {p for e in enjeux.values() for p in e["preuves"]}
    if faits_autorises is not None:
        preuves_transmises = set(faits_autorises)
        _exiger(preuves_transmises <= set(dossier["faits"]), "Faits de rédaction inconnus du calculateur.")
    sections = resultat.get("sections")
    _exiger(isinstance(sections, list) and bool(sections), "Rapport vide ou non structuré.")
    couverts, classements, avertissements = set(), [], []

    def verifier_couverture(condition, raison):
        if condition:
            return
        if couverture_bloquante:
            _exiger(False, raison)
        avertissements.append(raison)
    for section in sections:
        _exiger(isinstance(section, dict) and _texte(section.get("titre")) and _texte(section.get("texte")),
                "Section vide ou invalide.")
        _exiger(_ids(section.get("enjeux"), enjeux, vide=False), "Section sans enjeu calculé dans l'analyse.")
        _exiger(_ids(section.get("preuves"), dossier["faits"], vide=False), "Section sans preuve connue.")
        autorisees = {p for cle in section["enjeux"] for p in enjeux[cle]["preuves"]}
        _exiger(set(section["preuves"]) <= preuves_transmises,
                "La rédaction introduit une preuve absente des données transmises.")
        autres_preuves = sorted(set(section["preuves"]) - autorisees)
        if autres_preuves:
            classements.append({"section": section["titre"], "enjeux_declares": section["enjeux"],
                                "preuves_autres_enjeux": autres_preuves,
                                "bloquant": False})
        couverts.update(section["enjeux"])
    if exiger_majeurs:
        majeurs = {cle for cle, e in enjeux.items() if e["importance"] == "majeur"}
        verifier_couverture(majeurs <= couverts,
                            "La rédaction omet des enjeux majeurs : " + ", ".join(sorted(majeurs - couverts)))
        # Les anciennes archives sans rôles restent lisibles ; les nouvelles
        # sorties structurées doivent rendre profection et périodes visibles.
        if any("role" in section for section in sections):
            roles = {section.get("role") for section in sections}
            verifier_couverture("ambiance" in roles, "Aucune section étiquetée ambiance dans le corps.")
            verifier_couverture("profection" in roles, "Aucune section étiquetée profection dans le corps.")
            if analyses.get("activations_annuelles", {}).get("enjeux"):
                verifier_couverture("periode" in roles, "Aucune section étiquetée période de transit dans le corps.")
            verifier_couverture(sum(s.get("role") == "periode" for s in sections) <= 4,
                                "Plus de quatre grandes périodes dans le corps.")
            for section in sections:
                if section.get("role") == "profection":
                    _exiger("PROFECTION.annuelle" in section["preuves"], "Profection non sourcée.")
                if section.get("role") == "periode":
                    _exiger(any(cle.startswith("TRANSIT.") for cle in section["preuves"]), "Période sans transit calculé.")
    return {"statut": "valide", "enjeux_couverts": sorted(couverts),
            "portee": "couverture déclarée et preuves connues dans les analyses transmises",
            "classements_non_bloquants": classements,
            "avertissements_couverture": avertissements,
            "couverture_complete": not avertissements}


def controler_rapport_final_rs(texte, dossier, analyses, corps, conclusion):
    from ..controle_livraison import controler_placements
    from .memoire_redaction import faits_pour_redaction
    controler_analyse_rs(dossier, analyses)
    controle_corps = controler_redaction(corps, dossier, analyses, couverture_bloquante=False,
                                        faits_autorises=faits_pour_redaction(dossier, analyses))
    controler_redaction({"sections": [{"titre": "Conclusion", **conclusion}]}, dossier, analyses,
                       exiger_majeurs=False, faits_autorises=faits_pour_redaction(dossier, analyses, corps))
    resultat = controler_placements(texte, dossier["donnees_controle"])
    resultat["bloquant"] = True
    resultat["avertissements_redaction"] = controle_corps["avertissements_couverture"]
    # Le contrôleur historique ne couvre pas les projections natal → RS.
    resultat["limites"] = ["Contrôle textuel heuristique, pas certification de chaque phrase.",
                           "Les superpositions inverses et dates sont contrôlées par leurs références structurées."]
    _exiger(not resultat["erreurs"], f"{len(resultat['erreurs'])} contradiction(s) factuelle(s) dans le rapport.")
    return resultat
