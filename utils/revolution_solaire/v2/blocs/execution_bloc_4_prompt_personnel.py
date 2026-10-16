"""Bloc 4 avec le prompt validé : grandes périodes en mois, sans anciennes consignes."""

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
from . import bloc_1, bloc_4
from .execution import ROOT, _source
from .execution_prompt_personnel import MODELE, rendre_essai
from .presentation_faits import compacter_faits


PROMPT_PATH = Path(__file__).with_name("prompt_bloc_4_essai_personnel.txt")
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/essai_prompt_personnel/bloc_4"


def lancer_bloc_4_prompt_personnel(cas_a_tester, *, source_bloc_3, apercu=False, sur_dossier=None):
    if len(cas_a_tester) != 1:
        raise ValueError("Un seul profil est attendu.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_bloc_3).expanduser().resolve()
    ancienne = lire_json(reference, "demande.json")
    memoires = lire_json(reference, "memoire_cumulative.json")
    if not isinstance(ancienne, dict) or not isinstance(memoires, dict) or not (reference / "bloc_3.md").is_file():
        raise ValueError("Bloc 3 ou mémoire absent. Aucun appel lancé.")
    if ancienne.get("profil") != {k: cas[k] for k in ("personne", "lieu_rs", "annee")}:
        raise ValueError("Le profil diffère du bloc 3. Aucun appel lancé.")
    factuel, source = _source(cas, ancienne["source_factuel"])
    # La nouvelle mémoire ne déclare pas de propriétaires de faits. Le catalogue
    # autorisé fournit des liens calculés, sans prétendre qu'ils ont été rédigés.
    references_contexte = {cle for cle, fait in factuel["faits"].items() if fait_autorise(fait)}
    transits, contexte, calendrier, mars, audit = bloc_4.selectionner_transits_bloc_4(
        factuel, references_contexte)
    entree = bloc_4.purger_donnees_bloc_4({
        "genre": {"female": "féminin", "male": "masculin"}.get(cas["personne"].get("genre", ""), ""),
        "cycle": {k: factuel["cycle"][k] for k in ("debut_utc", "fin_utc", "annee", "age")},
        "transits": {"familles": calendrier, "declencheurs_mars": mars},
        "contexte": compacter_faits(contexte),
        "memoire": deepcopy(memoires),
    })
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    for cle in ("cycle", "transits", "contexte", "memoire"):
        prompt = prompt.replace("{" + cle + "}", json.dumps(entree[cle], ensure_ascii=False, separators=(",", ":")))
    prompt += "\n\n" + json.dumps({"genre": entree["genre"]}, ensure_ascii=False, separators=(",", ":"))
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=10000)
    # Le prompt autorise une mémoire JSON libre : ne pas imposer le schéma de
    # l'ancien bloc 4 ni celui des mémoires des autres essais.
    options.pop("schema_sortie", None)
    demande = {"mode": "bloc_4_prompt_personnel_1", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), "source_bloc_3": str(reference),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": 10000},
               "utiliser_bdd": False}

    class JournalBloc4(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 4 — GRANDES PÉRIODES DE L’ANNÉE\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée ; contenu à relire, aucune validation astrologique automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_4.json", entree)
        ecrire_json(dossier, "memoires_sources.json", memoires)
        ecrire_json(dossier, "selection_transits_bloc_4.json", audit)
        (dossier / "prompt_complet_bloc_4.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for p in (Path(__file__), PROMPT_PATH, Path(bloc_4.__file__),
                  Path(__file__).with_name("execution_prompt_personnel.py"),
                  Path(__file__).with_name("filtrage_transits.py"),
                  Path(__file__).with_name("presentation_faits.py"),
                  Path(__file__).parents[1] / "releve_transits.py"):
            if not (snapshots / p.name).exists():
                shutil.copy2(p, snapshots / p.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("Dossier local :", ROOT)
                print("Bloc 3 conservé :", reference)
                print("Bloc 4 uniquement — un appel maximum, sans BDD, sans anciennes consignes.")
                print("Le texte demandé présente de grandes périodes par mois et années, sans jours précis.")
                print("Fenêtres de transit envoyées :", len(transits))
                print("Mémoires disponibles :", ", ".join(memoires))
                print("Prompt complet :", dossier / "prompt_complet_bloc_4.txt")
                print("Données :", dossier / "donnees_envoyees_bloc_4.json")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc4(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    if not isinstance(resultat.get("texte"), str) or not resultat["texte"].strip():
                        raise ValueError("Texte absent ; réponse brute conservée.")
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, "bloc_4", generer, appel, journal=journal)
                    memoire_4 = resultat.get("memoire")
                    ecrire_json(dossier, "memoire_bloc_4.json", memoire_4)
                    cumulative = deepcopy(memoires)
                    if isinstance(memoire_4, dict):
                        cumulative["bloc_4"] = memoire_4
                    ecrire_json(dossier, "memoire_cumulative.json", cumulative)
                    ecrire_json(dossier, "diagnostic_bloc_4.json", {
                        "nombre_mots": len(resultat["texte"].split()),
                        "memoire_objet_json": isinstance(memoire_4, dict),
                        "validation_humaine": False})
                    lecture = rendre_essai(dossier, resultat, numero_bloc=4)
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_4_a_relire", "validation_humaine": False})
                    print("\nBLOC 4 TERMINÉ." if sur_dossier is not None else "\nBLOC 4 TERMINÉ — aucun bloc suivant lancé.")
                    if not isinstance(memoire_4, dict):
                        print("À relire : la mémoire reçue n'est pas un objet JSON ; le texte est conservé.")
                    print("Lecture :", lecture)
                    print("Markdown :", dossier / "bloc_4.md")
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
