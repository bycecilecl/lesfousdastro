"""Essai du prompt 3 fourni, sans anciennes consignes ni BDD."""

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
from ..schemas import objet
from ..service import _etape_archivee, _fournisseur_borne, options_claude_v2
from ..terminal import JournalTerminal, Tee, afficher_requete
from . import bloc_1, bloc_3
from .execution import ROOT, _source
from .execution_prompt_personnel import MODELE, rendre_essai
from .presentation_faits import compacter_faits


PROMPT_PATH = Path(__file__).with_name("prompt_bloc_3_essai_personnel.txt")
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/essai_prompt_personnel/bloc_3"
CATEGORIES_THEME = {"positions", "angles", "cuspides", "maitrises", "aspects",
                    "angularites", "configurations", "interceptions"}
ORBE_CHIRON_MAX = 3
PLANETES_CHIRON = {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter",
                   "Saturne", "Uranus", "Neptune", "Pluton"}


def selectionner_chiron_bloc_3(catalogue):
    """Exception limitée au bloc 3 : angularité OU conjonction RS calculée."""
    angularites, conjonctions = {}, {}
    for cle, fait in catalogue.items():
        if fait.get("source") != "rs":
            continue
        valeur = fait.get("valeur", {})
        orbe = valeur.get("orbe")
        if not isinstance(orbe, (int, float)) or not 0 <= orbe <= ORBE_CHIRON_MAX:
            continue
        if (fait.get("type") == "angularites" and valeur.get("point") == "Chiron"
                and valeur.get("angle") in {"Ascendant", "Descendant", "MC", "FC"}):
            angularites[cle] = fait
        elif (fait.get("type") == "aspects" and valeur.get("aspect") == "Conjonction"
              and "Chiron" in {valeur.get("planete1"), valeur.get("planete2")}):
            partenaire = {valeur.get("planete1"), valeur.get("planete2")} - {"Chiron"}
            if partenaire & PLANETES_CHIRON:
                conjonctions[cle] = fait
    position = catalogue.get("RS.positions.Chiron")
    if not position or not (angularites or conjonctions):
        return {}
    return {"RS.positions.Chiron": position, **angularites, **conjonctions}


def lancer_bloc_3_prompt_personnel(cas_a_tester, *, source_bloc_2, apercu=False, sur_dossier=None):
    if len(cas_a_tester) != 1:
        raise ValueError("Un seul profil est attendu.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_bloc_2).expanduser().resolve()
    ancienne = lire_json(reference, "demande.json")
    memoires = lire_json(reference, "memoire_cumulative.json")
    if not isinstance(ancienne, dict) or not isinstance(memoires, dict) or not (reference / "bloc_2.md").is_file():
        raise ValueError("Bloc 2 ou mémoire absent. Aucun appel lancé.")
    if not all(isinstance(memoires.get(nom), dict) for nom in ("bloc_1", "bloc_2")):
        raise ValueError("Mémoires des blocs 1 et 2 absentes. Aucun appel lancé.")
    if ancienne.get("profil") != {k: cas[k] for k in ("personne", "lieu_rs", "annee")}:
        raise ValueError("Le profil diffère du bloc 2. Aucun appel lancé.")
    factuel, source = _source(cas, ancienne["source_factuel"])
    # Catalogue compact : thèmes, contacts et projections RS vers natal.
    # Ni calendrier, ni contexte personnel, ni sélection à trois sujets.
    faits = {cle: f for cle, f in factuel["faits"].items() if fait_autorise(f) and (
        (f["source"] in {"rs", "natal"} and f["type"] in CATEGORIES_THEME)
        or f["type"] == "contact" or cle.startswith("SUPERPOSITION.rs_vers_natal."))}
    faits.update(selectionner_chiron_bloc_3(factuel["faits"]))
    cadres, contacts, projections = {"natal": {}, "rs": {}}, {}, {}
    for cle, compact in compacter_faits(faits).items():
        if cle.startswith("CONTACT."):
            contacts[cle] = compact
        elif cle.startswith("SUPERPOSITION."):
            projections[cle] = compact
        else:
            cadre, categorie, nom = cle.split(".", 2)
            cadres[cadre.lower()].setdefault(categorie, {})[nom] = compact
    memoire_texte = json.dumps(memoires, ensure_ascii=False, separators=(",", ":"))
    entree = {**cadres, "aspects_rs_natal": contacts, "memoire": memoire_texte,
              "genre": {"female": "féminin", "male": "masculin"}.get(cas["personne"].get("genre", ""), ""),
              "REPERES_CALCULES": bloc_3.construire_reperes_calcules_bloc_3(factuel, faits),
              "projections_rs_dans_natal": projections}
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    if "RS.positions.Chiron" not in faits:
        prompt = "".join(ligne for ligne in prompt.splitlines(keepends=True)
                         if not ligne.startswith("4. Aborde Chiron RS "))
    for cle in ("natal", "rs", "aspects_rs_natal", "memoire"):
        valeur = entree[cle]
        rendu = valeur if isinstance(valeur, str) else json.dumps(valeur, ensure_ascii=False, separators=(",", ":"))
        prompt = prompt.replace("{" + cle + "}", rendu)
    complement = {k: v for k, v in entree.items() if k not in {"natal", "rs", "aspects_rs_natal", "memoire"}}
    prompt += "\n\nDONNÉES COMPLÉMENTAIRES DU BLOC 3\n" + json.dumps(complement, ensure_ascii=False, separators=(",", ":"))
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=10000)
    options["schema_sortie"] = objet({"texte": {"type": "string"}, "memoire": {"type": "string"}})
    demande = {"mode": "bloc_3_prompt_personnel_1", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), "source_bloc_2": str(reference),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": 10000},
               "utiliser_bdd": False}

    class JournalBloc3(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 3 — ESSAI DU PROMPT PERSONNEL\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée ; contenu à relire, aucune validation astrologique automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_3.json", entree)
        ecrire_json(dossier, "memoires_sources.json", memoires)
        (dossier / "prompt_complet_bloc_3.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for p in (Path(__file__), PROMPT_PATH, Path(bloc_3.__file__),
                  Path(__file__).with_name("execution_prompt_personnel.py"),
                  Path(__file__).with_name("presentation_faits.py")):
            if not (snapshots / p.name).exists():
                shutil.copy2(p, snapshots / p.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("Dossier local :", ROOT)
                print("Bloc 2 conservé :", reference)
                print("Bloc 3 uniquement — un appel maximum, sans BDD, sans anciennes consignes.")
                print("Contacts RS–natal envoyés :", len(contacts))
                print("Mémoires des blocs 1 et 2 conservées ; ce prompt ne crée pas de résumé du bloc 3.")
                print("Prompt complet :", dossier / "prompt_complet_bloc_3.txt")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc3(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    if not isinstance(resultat.get("texte"), str) or not resultat["texte"].strip():
                        raise ValueError("Texte absent ; réponse brute conservée.")
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, "bloc_3", generer, appel, journal=journal)
                    ecrire_json(dossier, "memoire_bloc_3.json", resultat.get("memoire"))
                    ecrire_json(dossier, "memoire_cumulative.json", deepcopy(memoires))
                    ecrire_json(dossier, "diagnostic_bloc_3.json", {
                        "memoire_recue_identique": resultat.get("memoire") == memoire_texte,
                        "nouveau_resume_bloc_3": False})
                    lecture = rendre_essai(dossier, resultat, numero_bloc=3)
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_3_a_relire", "validation_humaine": False})
                    print("\nBLOC 3 TERMINÉ." if sur_dossier is not None else "\nBLOC 3 TERMINÉ — aucun bloc suivant lancé.")
                    print("Lecture :", lecture)
                    print("Mémoire cumulée conservée :", dossier / "memoire_cumulative.json")
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
