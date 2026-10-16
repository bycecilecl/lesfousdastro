"""Essai manuel de l'appel 2 depuis une réponse RS seule enregistrée.

Ce parcours isolé n'appelle jamais l'étape 1, ne modifie pas sa réponse et ne
valide pas le rapport complet. Le plafond est un appel, sans relance automatique.
"""

from copy import deepcopy
from html import escape
import hashlib
import json
from pathlib import Path

from ..archives_generation import ecrire_json, lire_json, verrou_demande, GenerationAbsente
from . import analyse
from .controle import AnalyseRSInvalide
from .dossier import controler_completude_dossier
from .releve_rs import retablir_references_rs
from .filtrage_aspects import filtrer_historique
from .service import _etape_archivee, _fournisseur_borne, _notifier


def preparer_essai_etape2(dossier_source):
    """Lit l'archive et prépare l'historique ; aucun calcul ni appel Claude."""
    source = Path(dossier_source).expanduser().resolve()
    factuel = lire_json(source, "dossier_factuel.json")
    demande = lire_json(source, "demande.json")
    reponse = lire_json(source / "rs_seule", "reponse.json")
    controle = lire_json(source / "rs_seule", "controle.json")
    if any(valeur is None for valeur in (factuel, demande, reponse, controle)):
        raise ValueError("Archive nécessaire absente : dossier factuel, demande, réponse RS ou contrôle.")
    brut = analyse.parser_json_reponse(reponse["texte"])
    entree_rs = {"etape": "rs_seule", "faits": {
        cle: fait for cle, fait in factuel["faits"].items() if cle.startswith("RS.")}}
    normalise = retablir_references_rs(brut, entree_rs)
    if (not isinstance(normalise.get("ambiance"), str)
            or not normalise["ambiance"].strip() or not isinstance(normalise.get("enjeux"), list)
            or not normalise["enjeux"]):
        raise AnalyseRSInvalide("La réponse enregistrée doit contenir une ambiance et des enjeux lisibles.")
    champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet", "exemples")
    historique = {"ambiance": normalise["ambiance"], "enjeux": []}
    ids = set()
    for enjeu in normalise["enjeux"]:
        if not isinstance(enjeu, dict) or any(champ not in enjeu for champ in champs):
            raise AnalyseRSInvalide("Enjeu RS enregistré incomplet ; aucun nouvel appel autorisé.")
        identifiant = enjeu["id"]
        if (not isinstance(identifiant, str) or not identifiant.startswith("rs_seule-")
                or identifiant in ids):
            raise AnalyseRSInvalide("Identifiants d'enjeux RS ambigus.")
        ids.add(identifiant)
        preuves = enjeu["preuves"]
        exemples = enjeu["exemples"]
        if not isinstance(exemples, list) or any(not isinstance(e, dict) for e in exemples):
            raise AnalyseRSInvalide("Exemples RS enregistrés illisibles.")
        for references in [preuves] + [e.get("preuves") for e in exemples]:
            if (not isinstance(references, list) or not references
                    or any(not isinstance(cle, str) or cle not in entree_rs["faits"] for cle in references)):
                raise AnalyseRSInvalide("Référence RS enregistrée inconnue ; aucun nouvel appel autorisé.")
        historique["enjeux"].append({champ: deepcopy(enjeu[champ]) for champ in champs})
    statut = {"rs_seule": {
        "statut_controle_source": controle.get("statut", "inconnu"),
        "raison_controle_source": controle.get("raison", ""),
        "usage": "Analyse provisoire pour cet essai isolé ; les faits calculés restent la source technique.",
    }}
    analyses = filtrer_historique({"rs_seule": historique}, factuel["faits"])
    entree = analyse.construire_entree_etape("resonances_natales", factuel, analyses,
                                           statut_historique=statut)
    prompt = analyse.construire_prompt_etape("resonances_natales", entree)
    fichiers = ("dossier_factuel.json", "demande.json", "rs_seule/reponse.json", "rs_seule/controle.json")
    provenance = {"dossier_source": str(source), "statut_historique": statut,
                  "empreintes_sources": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest()
                                         for nom in fichiers}}
    return {"factuel": factuel, "demande_source": demande, "analyses": analyses,
            "statut_historique": statut, "provenance": provenance, "prompt": prompt}


def rendre_reponse_isolee(dossier, etape):
    """Affiche la réponse reçue telle quelle, même si son contrôle a bloqué."""
    dossier = Path(dossier)
    numero, titre = {"resonances_natales": (2, "Résonances natales"),
                     "contacts_rs_natal": (3, "Contacts RS–natal"),
                     "superpositions_maisons": (4, "Superpositions des maisons"),
                     "profection": (5, "Profection"),
                     "activations_annuelles": (6, "Transits et périodes annuelles")}[etape]
    reponse = lire_json(dossier / etape, "reponse.json")
    if reponse is None:
        return None
    controle = lire_json(dossier / etape, "controle.json") or {}
    contenu = [f"<h1>Appel {numero} — {titre}</h1>",
               "<aside>Essai isolé : les limites des analyses précédentes restent signalées. Texte de Claude affiché sans réécriture.</aside>",
               "<p>Contrôle de cette étape : " + escape(controle.get("statut", "non terminé")) + "</p>"]
    def paragraphes(texte):
        return "".join("<p>" + escape(p).replace("\n", "<br>") + "</p>"
                       for p in str(texte).split("\n\n") if p.strip())
    try:
        resultat = analyse.parser_json_reponse(reponse["texte"])
        for enjeu in resultat.get("enjeux", []):
            contenu += ["<section><h2>" + escape(enjeu["titre"]) + "</h2>",
                        paragraphes(enjeu["lecture"])]
            for exemple in enjeu.get("exemples", []):
                contenu.append("<blockquote>" + paragraphes(exemple["texte"]) + "</blockquote>")
            contenu.append("</section>")
        contenu.append("<details><summary>Réponse JSON complète et suivi technique</summary><pre>"
                       + escape(reponse["texte"]) + "</pre></details>")
    except (AnalyseRSInvalide, KeyError, TypeError):
        contenu.append("<pre>" + escape(reponse["texte"]) + "</pre>")
    if controle.get("raison"):
        contenu.append("<aside>" + escape(controle["raison"]) + "</aside>")
    page = ('<!doctype html><html lang="fr"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + titre + ' — essai isolé</title><style>'
            'body{font:17px/1.65 system-ui;margin:40px auto;max-width:950px;padding:0 24px;'
            'background:#faf8f4;color:#222}h2{line-height:1.35}section{border-top:1px solid #ddd;'
            'margin-top:30px}aside{background:#fff0d6;padding:18px}pre{white-space:pre-wrap;'
            'overflow-wrap:anywhere;font-size:13px}summary{cursor:pointer}</style>'
            '<body>' + "".join(contenu) + '</body></html>')
    cible = dossier / ("lecture_" + etape + ".html")
    cible.write_text(page, encoding="utf-8")
    return str(cible)


def rendre_reponse_etape2(dossier):
    return rendre_reponse_isolee(dossier, "resonances_natales")


def generer_essai_isole(preparation, *, etape, modele, stockage_dir, journal=None,
                       autoriser_generation=False):
    """Un seul appel de l'étape demandée ; les reprises relisent le cache."""
    fonctions = {"resonances_natales": analyse.analyser_resonances_natales,
                 "contacts_rs_natal": analyse.analyser_contacts_rs_natal,
                 "superpositions_maisons": analyse.analyser_superpositions_maisons,
                 "profection": analyse.integrer_profection,
                 "activations_annuelles": analyse.analyser_activations_annuelles}
    if etape not in fonctions:
        raise ValueError("Cet essai isolé accepte seulement les appels 2 à 6.")
    if not autoriser_generation:
        raise GenerationAbsente("L'essai isolé doit être lancé explicitement par Cécile.")
    factuel = preparation["factuel"]
    controler_completude_dossier(factuel)
    demande = {"mode": "essai_isole_" + etape, "modele": modele,
               "sources": preparation["provenance"],
               "empreinte_prompt": hashlib.sha256(preparation["prompt"].encode("utf-8")).hexdigest()}
    with verrou_demande(demande, Path(stockage_dir)) as dossier:
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "source_historique.json", preparation["provenance"])
        ecrire_json(dossier, "historique_utilise.json", preparation["analyses"])
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
        try:
            resultat = _etape_archivee(
                dossier, etape, lambda appeler: fonctions[etape](
                    factuel, preparation["analyses"], appeler=appeler,
                    statut_historique=preparation["statut_historique"]), appel, journal=journal)
            from ..controle_livraison import controler_placements
            textes = "\n\n".join(e["lecture"] for e in resultat["enjeux"])
            controle = controler_placements(textes, factuel["donnees_controle"])
            ecrire_json(dossier / etape, "controle_lecture.json", controle)
            _notifier(journal, "controle_placements", nom=etape, controle=controle)
            if controle["erreurs"]:
                raison = "Contradiction factuelle dans l'analyse " + etape + "."
                ecrire_json(dossier / etape, "controle.json", {"statut": "bloque", "raison": raison})
                ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "etape": etape})
                raise AnalyseRSInvalide(raison)
            ecrire_json(dossier, "etat.json", {"statut": "essai_isole_termine", "etape": etape,
                                             "parcours_complet_valide": False})
            return {"dossier": str(dossier), "resultat": resultat}
        finally:
            lecture = rendre_reponse_isolee(dossier, etape)
            if lecture:
                _notifier(journal, "lecture_enregistree", chemin=lecture)


def generer_essai_etape2(preparation, *, modele, stockage_dir, journal=None, autoriser_generation=False):
    return generer_essai_isole(preparation, etape="resonances_natales", modele=modele,
                             stockage_dir=stockage_dir, journal=journal,
                             autoriser_generation=autoriser_generation)
