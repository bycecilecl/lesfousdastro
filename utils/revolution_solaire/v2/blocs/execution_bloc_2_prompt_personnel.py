"""Bloc 2 avec le prompt fourni ; mémoire précédente conservée sans réécriture."""

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
from . import bloc_1, bloc_2
from .execution import ROOT, _source
from .execution_prompt_personnel import MODELE, rendre_essai, schema_prompt_personnel_v2
from .presentation_faits import compacter_faits
from .repartition import repartir_sections_bloc_2


PROMPT_PATH = Path(__file__).with_name("prompt_bloc_2_essai_personnel.txt")
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/essai_prompt_personnel/bloc_2"


def lancer_bloc_2_prompt_personnel(cas_a_tester, *, source_bloc_1, apercu=False, sur_dossier=None):
    if len(cas_a_tester) != 1:
        raise ValueError("Un seul profil est attendu.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_bloc_1).expanduser().resolve()
    ancienne = lire_json(reference, "demande.json")
    memoire_1 = lire_json(reference, "memoire_prompt_personnel.json")
    if not isinstance(ancienne, dict) or not isinstance(memoire_1, dict) or not (reference / "bloc_1.md").is_file():
        raise ValueError("Bloc 1 ou mémoire absent. Aucun appel lancé.")
    if ancienne.get("profil") != {k: cas[k] for k in ("personne", "lieu_rs", "annee")}:
        raise ValueError("Le profil diffère du bloc 1. Aucun appel lancé.")
    factuel, source = _source(cas, ancienne["source_factuel"])
    faits = bloc_2.selectionner_faits_bloc_2(factuel)
    # Contacts des luminaires dans les deux sens : luminaire RS vers le natal,
    # ou autre point RS vers un luminaire natal. Aucun nouvel aspect calculé.
    for cle, fait in factuel["faits"].items():
        if fait.get("type") != "contact" or not fait_autorise(fait):
            continue
        v = fait["valeur"]
        if not {v["point_rs"], v["point_natal"]} & {"Soleil", "Lune"}:
            continue
        faits[cle] = fait
        for cadre, nom in (("RS", v["point_rs"]), ("NATAL", v["point_natal"])):
            for categorie in ("positions", "angles"):
                ref = f"{cadre}.{categorie}.{nom}"
                position = factuel["faits"].get(ref)
                if position is not None and fait_autorise(position):
                    faits[ref] = position
    # Situation natale et projection des maîtres des maisons des luminaires,
    # uniquement depuis les faits déjà calculés du dossier.
    for luminaire in ("Soleil", "Lune"):
        maison = str(factuel["rs"]["positions"][luminaire]["maison"])
        for maitre in factuel["rs"]["maitrises"][maison]["maitres"]:
            for cle in (f"RS.positions.{maitre}", f"NATAL.positions.{maitre}",
                        f"SUPERPOSITION.rs_vers_natal.points.{maitre}"):
                f = factuel["faits"].get(cle)
                if f is not None and fait_autorise(f):
                    faits[cle] = f
    compacts = compacter_faits(faits)
    cadres = {"natal": {}, "rs": {}}
    for cle in list(compacts):
        for cadre in cadres:
            if cle.startswith(cadre.upper() + "."):
                _, categorie, nom = cle.split(".", 2)
                cadres[cadre].setdefault(categorie, {})[nom] = compacts.pop(cle)
                break
    compacts["REPERES_CALCULES"] = bloc_2.construire_reperes_calcules_bloc_2(factuel)
    parts = repartir_sections_bloc_2(faits, factuel)
    for cle, fait in faits.items():
        if fait["type"] == "contact" and fait["valeur"]["point_rs"] not in {"Soleil", "Lune"}:
            section = {"Soleil": "soleil", "Lune": "lune"}[fait["valeur"]["point_natal"]]
            parts[section].append(cle)
    memoires = {"bloc_1": deepcopy(memoire_1)}
    entree = {"cycle": {k: factuel["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
              "genre": {"female": "féminin", "male": "masculin"}.get(cas["personne"].get("genre", ""), ""),
              **cadres, "memoire": memoires, "faits_calcules": compacts,
              "repartition_des_faits": parts}
    consigne = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = consigne
    for cle in ("natal", "rs", "memoire"):
        prompt = prompt.replace("{" + cle + "}", json.dumps(entree[cle], ensure_ascii=False, separators=(",", ":")))
    complement = {k: v for k, v in entree.items() if k not in {"natal", "rs", "memoire"}}
    prompt += "\n\nDONNÉES COMPLÉMENTAIRES DU BLOC 2\n" + json.dumps(complement, ensure_ascii=False, separators=(",", ":"))
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=10000)
    options["schema_sortie"] = schema_prompt_personnel_v2()
    demande = {"mode": "bloc_2_prompt_personnel_1", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), "source_bloc_1": str(reference),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": 10000},
               "utiliser_bdd": False}

    class JournalBloc2(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 2 — ESSAI DU PROMPT PERSONNEL\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée ; contenu à relire, aucune validation astrologique automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_2.json", entree)
        ecrire_json(dossier, "memoire_source_bloc_1.json", memoire_1)
        (dossier / "prompt_complet_bloc_2.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for p in (Path(__file__), PROMPT_PATH, Path(bloc_2.__file__),
                  Path(__file__).with_name("execution_prompt_personnel.py"),
                  Path(__file__).with_name("presentation_faits.py"), Path(__file__).with_name("repartition.py")):
            if not (snapshots / p.name).exists():
                shutil.copy2(p, snapshots / p.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("Dossier local :", ROOT)
                print("Bloc 1 conservé :", reference)
                print("Bloc 2 uniquement — un appel maximum, sans BDD, sans anciennes consignes.")
                print("Mémoire du bloc 1 conservée ; nouveau résumé du bloc 2 ajouté séparément.")
                print("Prompt complet :", dossier / "prompt_complet_bloc_2.txt")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc2(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    if not isinstance(resultat.get("texte"), str) or not resultat["texte"].strip():
                        raise ValueError("Texte absent ; réponse brute conservée.")
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, "bloc_2", generer, appel, journal=journal)
                    ecrire_json(dossier, "memoire_bloc_2.json", resultat["memoire"])
                    ecrire_json(dossier, "memoire_cumulative.json", {**memoires, "bloc_2": resultat["memoire"]})
                    lecture = rendre_essai(dossier, resultat, numero_bloc=2)
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_2_a_relire", "validation_humaine": False})
                    print("\nBLOC 2 TERMINÉ." if sur_dossier is not None else "\nBLOC 2 TERMINÉ — aucun bloc suivant lancé.")
                    print("Lecture :", lecture)
                    print("Mémoire cumulée :", dossier / "memoire_cumulative.json")
                    return 0
                except KeyboardInterrupt:
                    print("ARRÊT MANUEL — éléments reçus conservés ; aucune relance.")
                    return 130
                except Exception as exc:
                    print("ARRÊT :", type(exc).__name__, "—", exc)
                    print("Réponse brute conservée si reçue. Aucun appel supplémentaire.")
                    return 1
                finally:
                    print("Budget et tokens :", dossier / "budget_ia.json")
                    print("Journal :", dossier / "terminal.log")
