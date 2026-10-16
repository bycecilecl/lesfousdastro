"""Angles puis grands enjeux ; six parties conservées, sans appel à l'import."""

import contextlib
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..analyse import parser_json_reponse
from ..filtrage_aspects import fait_autorise
from ..service import _etape_archivee, _fournisseur_borne, options_claude_v2
from ..terminal import JournalTerminal, Tee, afficher_requete
from . import bloc_1, bloc_4, bloc_5
from .execution import ROOT, _source
from .execution_bloc_3_prompt_personnel import CATEGORIES_THEME, selectionner_chiron_bloc_3
from .execution_bloc_5_prompt_personnel import (
    assembler_rapport, references_memoire, selectionner_conjonctions_noeuds_bloc_5,
)
from .execution_prompt_personnel import MODELE, rendre_essai, schema_prompt_personnel_v2

from .presentation_faits import compacter_faits


PARTIES = {
    3: ("mc", "MC, FC ET DESCENDANT", "prompt_bloc_3_mc.txt"),
    4: ("grands_enjeux", "LES AUTRES GRANDS ENJEUX", "prompt_bloc_4_grands_enjeux.txt"),
    5: ("periodes", "LES PÉRIODES DE L’ANNÉE", "prompt_bloc_5_periodes.txt"),
    6: ("bilan", "BILAN ET SITUATION PERSONNELLE", "prompt_bloc_6_bilan.txt"),
}
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/six_parties"
ANGLES_BLOC_3 = {"MC": "10", "FC": "4", "Descendant": "7"}


def selectionner_faits_angles(dossier):
    """MC, FC, Descendant et leurs maîtres, avec le contexte RS et natal calculé."""
    catalogue = dossier["faits"]
    maisons = set(ANGLES_BLOC_3.values())
    maitres = {nom for maison in maisons for nom in dossier["rs"]["maitrises"][maison]["maitres"]}
    centres = maitres | set(ANGLES_BLOC_3)
    faits = {}
    for cle, fait in catalogue.items():
        if not fait_autorise(fait):
            continue
        v, categorie, cadre = fait["valeur"], fait["type"], fait["source"]
        acteurs = {v.get(k) for k in ("planete1", "planete2", "point", "angle")}
        acteurs.update(v.get("planetes", []))
        retenir = (
            cadre in {"rs", "natal"} and (
                categorie in {"positions", "angles"} and fait.get("objet") in centres
                or categorie in {"aspects", "angularites", "configurations"} and bool(acteurs & centres)
            )
            or categorie == "contact" and v.get("point_rs") in centres
            or cle.startswith("SUPERPOSITION.rs_vers_natal.points.") and fait.get("objet") in centres
            or cadre in {"rs", "natal"} and categorie in {"cuspides", "maitrises"} and str(fait.get("objet")) in maisons
            or cle in {f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}" for maison in maisons}
        )
        if retenir:
            faits[cle] = fait
    # Positions des partenaires d'aspect : du contexte, pas de nouveaux aspects.
    for fait in list(faits.values()):
        v, cadre = fait["valeur"], fait["source"]
        if fait["type"] == "contact":
            points = (("rs", v["point_rs"]), ("natal", v["point_natal"]))
        elif cadre in {"rs", "natal"}:
            noms = {v.get(k) for k in ("planete1", "planete2", "point", "angle")}
            noms.update(v.get("planetes", []))
            points = [(cadre, nom) for nom in noms if isinstance(nom, str)]
        else:
            points = []
        for cadre_point, nom in sorted(points):
            for categorie in ("positions", "angles"):
                cle = f"{cadre_point.upper()}.{categorie}.{nom}"
                if cle in catalogue and fait_autorise(catalogue[cle]):
                    faits[cle] = catalogue[cle]
    for fait in list(faits.values()):
        maison = fait["valeur"].get("maison")
        if fait["type"] != "positions" or maison is None:
            continue
        cadre = fait["source"].upper()
        for cle in (f"{cadre}.cuspides.{maison}", f"{cadre}.maitrises.{maison}"):
            if cle in catalogue and fait_autorise(catalogue[cle]):
                faits[cle] = catalogue[cle]
        if cadre == "RS":
            cle = f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}"
            if cle in catalogue:
                faits[cle] = catalogue[cle]
    return faits


def reperes_angles(faits):
    """Regroupe les repères existants par angle, sans confondre angle et cuspide."""
    compacts = compacter_faits(faits)
    reperes = {}
    for angle, maison in ANGLES_BLOC_3.items():
        references = (f"RS.angles.{angle}", f"RS.cuspides.{maison}", f"RS.maitrises.{maison}",
                      f"SUPERPOSITION.rs_vers_natal.points.{angle}",
                      f"SUPERPOSITION.rs_vers_natal.cuspides.{maison}")
        reperes[angle] = {"maison_rs": int(maison),
                         "faits": {cle: compacts[cle] for cle in references if cle in compacts}}
    return reperes


def selectionner_faits_enjeux(dossier):
    faits = {cle: f for cle, f in dossier["faits"].items() if fait_autorise(f) and (
        f["source"] in {"rs", "natal"} and f["type"] in CATEGORIES_THEME
        or f["type"] == "contact" or cle.startswith("SUPERPOSITION.rs_vers_natal."))}
    faits.update(selectionner_chiron_bloc_3(dossier["faits"]))
    return faits


def construire_entree(numero, dossier, memoires, cas):
    if numero in {3, 4}:
        faits = selectionner_faits_angles(dossier) if numero == 3 else selectionner_faits_enjeux(dossier)
        cadres, contacts, projections = {"natal": {}, "rs": {}}, {}, {}
        for cle, compact in compacter_faits(faits).items():
            if cle.startswith("CONTACT."):
                contacts[cle] = compact
            elif cle.startswith("SUPERPOSITION."):
                projections[cle] = compact
            else:
                cadre, categorie, nom = cle.split(".", 2)
                cadres[cadre.lower()].setdefault(categorie, {})[nom] = compact
        contexte = {"projections_rs_dans_natal": projections}
        if numero == 3:
            contexte["REPERES_CALCULES"] = reperes_angles(faits)
        entree = {**cadres, "aspects_rs_natal": contacts, "contexte": contexte, "memoire": deepcopy(memoires)}
        return entree, {"references_envoyees": list(faits)}, "RS.positions.Chiron" in faits
    if numero == 5:
        refs = {cle for cle, fait in dossier["faits"].items() if fait_autorise(fait)}
        _, contexte, calendrier, mars, audit = bloc_4.selectionner_transits_bloc_4(dossier, refs)
        entree = bloc_4.purger_donnees_bloc_4({
            "cycle": {k: dossier["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
            "transits": {"familles": calendrier, "declencheurs_mars": mars},
            "contexte": compacter_faits(contexte), "memoire": deepcopy(memoires),
        })
        return entree, audit, False
    catalogue = dossier["faits"]
    refs = {cle for cle, fait in catalogue.items() if fait_autorise(fait)}
    appuis = references_memoire(memoires, catalogue)
    faits, roles = bloc_5.selectionner_reperes_bloc_5(dossier, refs, appuis_requis=appuis)
    for nom in ("Rahu", "Ketu"):
        cle = f"RS.positions.{nom}"
        if cle in catalogue and fait_autorise(catalogue[cle]):
            faits[cle] = catalogue[cle]
    faits.update(selectionner_conjonctions_noeuds_bloc_5(catalogue))
    entree = bloc_4.purger_donnees_bloc_4({
        "memoire": {k: deepcopy(v) for k, v in memoires.items() if k != "bloc_5"},
        "reperes": {"faits_calcules": compacter_faits(faits), "roles_calcules": roles},
        "periodes": deepcopy(memoires.get("bloc_5", {})),
        "informations_personnelles": deepcopy(cas.get("contexte_client", {})),
    })
    return entree, {"references_envoyees": list(faits)}, False


def charger_precedents(cas, reference, numero):
    """Suit uniquement la chaîne des six parties, sans toucher aux anciennes archives."""
    lectures, provenance = {}, {}
    for n in range(numero - 1, 0, -1):
        demande = lire_json(reference, "demande.json")
        texte = reference / f"bloc_{n}.md"
        if (not isinstance(demande, dict) or not texte.is_file()
                or demande.get("profil") != {k: cas[k] for k in ("personne", "lieu_rs", "annee")}):
            raise ValueError(f"Archive du bloc {n} absente ou profil différent. Aucun appel lancé.")
        if n >= 3 and demande.get("mode") != f"rs_six_parties_{n}_{PARTIES[n][0]}":
            raise ValueError(f"Le bloc {n} ne provient pas du parcours à six parties. Aucun appel lancé.")
        lectures[f"bloc_{n}"] = texte.read_text(encoding="utf-8")
        provenance[f"bloc_{n}"] = {"chemin": str(texte), "sha256": hashlib.sha256(texte.read_bytes()).hexdigest()}
        if n > 1:
            chemin = demande.get(f"source_bloc_{n - 1}")
            if not isinstance(chemin, str) or not chemin:
                raise ValueError(f"Source du bloc {n - 1} absente. Aucun appel lancé.")
            reference = (ROOT / chemin).expanduser().resolve()
    return lectures, provenance


def lancer_periodes_et_bilan(source_rapport, *, apercu=False):
    """Reprend un rapport à six parties : quatre textes conservés, deux appels au plus."""
    return reprendre_fin_rapport(source_rapport, premier_bloc=5, apercu=apercu)


def reprendre_fin_rapport(source_rapport, *, premier_bloc=3, apercu=False):
    """Reprend les archives exactes du profil, sans régénérer les parties antérieures."""
    from .export_pdf import exporter_pdf, verifier_export_pdf

    if premier_bloc not in {3, 5}:
        raise ValueError("La reprise commence au bloc 3 ou au bloc 5.")
    reference = (ROOT / source_rapport).expanduser().resolve()
    demande = lire_json(reference, "demande.json") or {}
    sources = lire_json(reference, "sources_blocs.json") or {}
    precedent = f"bloc_{premier_bloc - 1}"
    if demande.get("version") != "rs_v2_six_parties_mc_separe_1" or precedent not in sources:
        raise ValueError("Un rapport complet à six parties est attendu. Aucun appel lancé.")
    cas = demande["profil"]
    source = (ROOT / sources[precedent]).resolve()
    charger_precedents(cas, source, premier_bloc)
    if not apercu:
        verifier_export_pdf()
    print(f"REPRISE — blocs {premier_bloc} à 6 ; les {premier_bloc - 1} premières parties restent identiques.")
    print("Profil et informations personnelles repris du rapport :", reference)
    for numero in range(premier_bloc, 7):
        capture = {}
        code = lancer_partie([cas], numero=numero, source_precedente=source, apercu=apercu,
                             sur_dossier=lambda p: capture.update(chemin=Path(p)))
        if code != 0 or apercu:
            return code
        source = capture["chemin"]
    pdf = exporter_pdf(source / "rapport_complet_assemble.html", source / "rapport_rs_v2.pdf",
                       personne=cas["personne"], lieu_rs=cas["lieu_rs"], annee=cas["annee"])
    print(f"\nREPRISE TERMINÉE — rapport entier à relire ; {7 - premier_bloc} appels maximum, aucune relance automatique.")
    print("Rapport HTML :", source / "rapport_complet_assemble.html")
    print("PDF :", pdf)
    return 0


def lancer_partie(cas_a_tester, *, numero, source_precedente, apercu=False, sur_dossier=None):
    if len(cas_a_tester) != 1 or numero not in PARTIES:
        raise ValueError("Un profil et une partie de 3 à 6 sont attendus.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_precedente).expanduser().resolve()
    lectures, provenance = charger_precedents(cas, reference, numero)
    ancienne = lire_json(reference, "demande.json")
    memoires = lire_json(reference, "memoire_cumulative.json")
    if (not isinstance(memoires, dict)
            or not all(isinstance(memoires.get(f"bloc_{n}"), dict) for n in range(1, numero))):
        raise ValueError("Mémoires précédentes absentes. Aucun appel lancé.")
    factuel, source = _source(cas, ancienne["source_factuel"])
    entree, audit, chiron = construire_entree(numero, factuel, memoires, cas)
    if numero == 6:
        # Les dates restent calculées : le bilan ne dépend pas uniquement du résumé IA.
        donnees_periodes = lire_json(reference, "donnees_envoyees_bloc_5.json") or {}
        transits = donnees_periodes.get("transits", {})
        fenetres = [f for famille in transits.get("familles", []) for f in famille["fenetres"]]
        fenetres.extend(transits.get("declencheurs_mars", []))
        entree["periodes"] = {"lecture": entree["periodes"], "transits_calcules": [
            {k: f[k] for k in ("reference", "fait", "roles_cible", "usage") if k in f}
            for f in fenetres]}
    entree["genre"] = {"female": "féminin", "male": "masculin"}.get(cas["personne"].get("genre", ""), "")
    prompt_path = Path(__file__).with_name(PARTIES[numero][2])
    prompt = prompt_path.read_text(encoding="utf-8")
    if numero == 4 and not chiron:
        prompt = "".join(l for l in prompt.splitlines(keepends=True) if not l.startswith("Aborde Chiron RS "))
    for cle, valeur in entree.items():
        prompt = prompt.replace("{" + cle + "}", json.dumps(valeur, ensure_ascii=False, separators=(",", ":")))
    prompt += "\n\n" + json.dumps({"genre": entree["genre"]}, ensure_ascii=False, separators=(",", ":"))
    max_tokens = 8000 if numero == 6 else 10000
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=max_tokens)
    if numero in {3, 4}:
        options["schema_sortie"] = schema_prompt_personnel_v2()
    else:
        options.pop("schema_sortie", None)
    nom = f"bloc_{numero}"
    demande = {"mode": f"rs_six_parties_{numero}_{PARTIES[numero][0]}", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), f"source_bloc_{numero - 1}": str(reference),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": max_tokens},
               "utiliser_bdd": False}
    if numero == 6:
        demande["contexte_client"] = deepcopy(cas.get("contexte_client", {}))

    class JournalPartie(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print(f"\nBLOC {numero} — {PARTIES[numero][1]}\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée, à relire ; aucune validation astrologique automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES / nom) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        for fichier, contenu in (("demande.json", demande), ("dossier_factuel.json", factuel),
                                 (f"donnees_envoyees_{nom}.json", entree), ("memoires_sources.json", memoires),
                                 ("sources_rapport.json", provenance), ("selection_faits.json", audit)):
            ecrire_json(dossier, fichier, contenu)
        (dossier / f"prompt_complet_{nom}.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for fichier in (Path(__file__), prompt_path, Path(bloc_4.__file__),
                        Path(__file__).with_name("filtrage_transits.py")):
            if not (snapshots / fichier.name).exists():
                shutil.copy2(fichier, snapshots / fichier.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as log:
            with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
                print(f"BLOC {numero}/6 — {PARTIES[numero][1]}")
                print("Dossier local :", ROOT)
                print("Un appel maximum ; aucune relance automatique. BDD désactivée.")
                print("Prompt complet :", dossier / f"prompt_complet_{nom}.txt")
                print("Données :", dossier / f"donnees_envoyees_{nom}.json")
                if numero == 5:
                    print("Sélection des transits :", audit["familles_lentes_retenues"], "familles lentes,",
                          audit["fenetres_transmises"], "fenêtres transmises ; facteurs annuels conservés hors plafond.")
                    print("Détail des sélections et exclusions :", dossier / "selection_faits.json")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalPartie(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    cle = "synthese_annuelle" if numero == 6 else "texte"
                    if not isinstance(resultat.get(cle), str) or not resultat[cle].strip():
                        raise ValueError("Texte absent ; réponse brute conservée.")
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, nom, generer, appel, journal=journal)
                    cumulative = deepcopy(memoires)
                    if numero == 6:
                        personnel = resultat.get("mise_en_perspective_personnelle", "")
                        personnel = personnel if isinstance(personnel, str) else ""
                        texte = "\n\n".join(p for p in (resultat["synthese_annuelle"], personnel) if p.strip())
                        ecrire_json(dossier, "conclusion.json", resultat)
                        rendu = {"texte": texte, "memoire": {}}
                    else:
                        rendu = resultat
                        memoire = resultat.get("memoire")
                        if isinstance(memoire, dict):
                            cumulative[nom] = deepcopy(memoire)
                        ecrire_json(dossier, f"memoire_{nom}.json", memoire)
                    ecrire_json(dossier, "memoire_cumulative.json", cumulative)
                    lecture = rendre_essai(dossier, rendu, numero_bloc=numero)
                    if numero == 6:
                        assembler_rapport(dossier, lectures, rendu["texte"], factuel["cycle"], nombre_blocs=6)
                    diagnostic = {
                        "nombre_mots": len(rendu["texte"].split()),
                        "memoire_objet_json": isinstance(resultat.get("memoire"), dict) if numero != 6 else None,
                        "validation_humaine": False}
                    if numero == 6:
                        diagnostic.update({
                            "mots_bilan": len(resultat["synthese_annuelle"].split()),
                            "mots_personnel": len(personnel.split()),
                            "contexte_renseigne": bloc_5.contexte_renseigne(cas.get("contexte_client", {})),
                            "partie_personnelle_presente": bool(personnel.strip()),
                        })
                        if diagnostic["contexte_renseigne"] and not personnel.strip():
                            print("À RELIRE — le bilan personnel demandé est absent du texte reçu.")
                    elif not isinstance(resultat.get("memoire"), dict):
                        print("À RELIRE — mémoire absente ou invalide ; texte et réponse brute conservés.")
                    ecrire_json(dossier, f"diagnostic_{nom}.json", diagnostic)
                    ecrire_json(dossier, "etat.json", {"statut": nom + "_a_relire", "validation_humaine": False})
                    print(f"\nBLOC {numero} TERMINÉ — texte à relire.")
                    print("Lecture :", lecture)
                    if numero == 6:
                        print("Rapport assemblé :", dossier / "rapport_complet_assemble.html")
                    return 0
                except KeyboardInterrupt:
                    print("ARRÊT MANUEL — éléments reçus conservés ; aucune relance.")
                    return 130
                except Exception as exc:
                    print("ARRÊT :", type(exc).__name__, "—", exc)
                    print("Réponses conservées. Aucun appel supplémentaire.")
                    return 1
                finally:
                    print("Budget et tokens :", dossier / "budget_ia.json")
                    print("Journal :", dossier / "terminal.log")
