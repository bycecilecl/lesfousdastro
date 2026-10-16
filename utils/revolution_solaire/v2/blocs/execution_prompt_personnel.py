"""Essai isolé du prompt fourni par Cécile ; aucun appel à l'import."""

import contextlib
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..analyse import parser_json_reponse
from ..schemas import objet
from ..service import _etape_archivee, _fournisseur_borne, options_claude_v2
from ..terminal import JournalTerminal, Tee, afficher_requete
from . import bloc_1
from .execution import ROOT, _source


PROMPT_PATH = Path(__file__).with_name("prompt_bloc_1_essai_personnel.txt")
PROMPT_V2_PATH = Path(__file__).with_name("prompt_bloc_1_essai_personnel_v2.txt")
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/essai_prompt_personnel"
MODELE = "claude-sonnet-5-5"


def schema_prompt_personnel():
    texte = {"type": "string"}
    return objet({"texte": texte, "memoire": objet({
        "developpements": {"type": "array", "items": objet({
            "sujet": texte, "role": texte, "resume": texte})},
        "faits_cites": {"type": "array", "items": objet({
            "reference": texte, "extrait": texte})},
        "pistes_a_suivre": {"type": "array", "items": texte},
    })})


def schema_prompt_personnel_v2():
    texte = {"type": "string"}
    liste = {"type": "array", "items": texte}
    return objet({"texte": texte, "memoire": objet({
        "resume": texte,
        "details": objet({"mots_cles": liste, "themes_prioritaires": liste, "deja_developpe": liste}),
    })})


def rendre_essai(dossier, resultat, *, numero_bloc=1):
    """Affiche le texte reçu, sans réécriture ; la réponse brute reste séparée."""
    import markdown
    texte = resultat["texte"]
    (dossier / f"bloc_{numero_bloc}.md").write_text(texte, encoding="utf-8")
    memoire = resultat.get("memoire", {})
    ecrire_json(dossier, "memoire_prompt_personnel.json", memoire)
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS — essai du prompt personnel</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}summary{cursor:pointer}"
            f"</style><body><aside>Essai du prompt fourni — bloc {numero_bloc} uniquement, sans BDD. "
            "Sonnet 5.5, réflexion adaptative, effort moyen. Texte reçu conservé, à relire.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Mémoire reçue</summary><pre>"
            + escape(json.dumps(memoire, ensure_ascii=False, indent=2)) + "</pre></details></body></html>")
    cible = dossier / f"lecture_bloc_{numero_bloc}.html"
    cible.write_text(html, encoding="utf-8")
    return cible


def lancer_essai_prompt_personnel(cas_a_tester, *, source_bloc_1=None, source_factuel=None,
                                apercu=False, version_prompt=1, sur_dossier=None):
    """Un appel au plus. Ni ancien prompt, ni anciennes règles, ni nouveau plan."""
    if len(cas_a_tester) != 1:
        raise ValueError("L'essai attend un seul profil.")
    if isinstance(version_prompt, bool) or version_prompt not in (1, 2):
        raise ValueError("Version du prompt attendue : 1 ou 2.")
    prompt_path = PROMPT_PATH if version_prompt == 1 else PROMPT_V2_PATH
    cas = cas_a_tester[0]
    reference = None
    if source_factuel is not None:
        if source_bloc_1 is not None:
            raise ValueError("Choisis une seule source pour le bloc 1.")
        factuel, source = _source(cas, source_factuel)
    else:
        if source_bloc_1 is None:
            raise ValueError("Source factuelle absente. Aucun appel lancé.")
        reference = (ROOT / source_bloc_1).expanduser().resolve()
        ancienne_demande = lire_json(reference, "demande.json")
        if not isinstance(ancienne_demande, dict) or not ancienne_demande.get("source_factuel"):
            raise ValueError("Source factuelle de référence absente. Aucun appel lancé.")
        factuel, source = _source(cas, ancienne_demande["source_factuel"])
    # Réutiliser la sélection des faits ; le prompt habituel construit par cette
    # fonction est écarté. Aucun ancien texte ni plan interprétatif n'est envoyé.
    _, faits, entree, _ = bloc_1.construire_prompt_bloc_1(
        factuel, genre=cas["personne"].get("genre", ""), utiliser_bdd=False)
    entree["deja_traites"] = []
    if version_prompt == 2:
        for cadre in ("natal", "rs"):
            entree[cadre] = {}
            for cle in list(entree["faits_calcules"]):
                if cle.startswith(cadre.upper() + "."):
                    _, categorie, nom = cle.split(".", 2)
                    entree[cadre].setdefault(categorie, {})[nom] = entree["faits_calcules"].pop(cle)
    consigne = prompt_path.read_text(encoding="utf-8")
    prompt = consigne
    if version_prompt == 2:
        for cadre in ("natal", "rs"):
            prompt = prompt.replace("{" + cadre + "}", json.dumps(entree[cadre], ensure_ascii=False, separators=(",", ":")))
    # La version 1 renvoie à la voix choisie. La version 2 définit elle-même
    # son ton : aucun style supplémentaire ne lui est ajouté.
    if version_prompt == 1:
        voix = bloc_1.STYLE_PATH.read_text(encoding="utf-8").split("\n\n", 1)[0]
        prompt += "\n\nVOIX DEMANDÉE\n" + voix
    complement = {k: v for k, v in entree.items() if version_prompt != 2 or k not in {"natal", "rs"}}
    prompt += "\n\nDONNÉES DU BLOC 1\n" + json.dumps(complement, ensure_ascii=False, separators=(",", ":"))
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=10000)
    options["schema_sortie"] = schema_prompt_personnel() if version_prompt == 1 else schema_prompt_personnel_v2()
    demande = {"mode": f"essai_prompt_personnel_{version_prompt}", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), "source_bloc_1": str(reference) if reference else None,
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": 10000},
               "utiliser_bdd": False}

    class JournalEssai(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nESSAI DU PROMPT PERSONNEL — BLOC 1\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée ; aucune validation de la justesse astrologique.")
            else:
                super().__call__(evenement, **details)

    sorties = SORTIES if version_prompt == 1 else SORTIES / "v2"
    with verrou_demande(demande, sorties) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_1.json", entree)
        (dossier / "prompt_fourni.txt").write_text(consigne, encoding="utf-8")
        (dossier / "prompt_complet_bloc_1.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for fichier in (Path(__file__), prompt_path, Path(bloc_1.__file__),
                        Path(__file__).with_name("presentation_faits.py"), bloc_1.STYLE_PATH,
                        Path(__file__).with_name("repartition.py")):
            if not (snapshots / fichier.name).exists():
                shutil.copy2(fichier, snapshots / fichier.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("Dossier local :", ROOT)
                print("Prompt personnel :", prompt_path, "— version", version_prompt)
                print("Essai séparé — un bloc, un appel maximum, sans BDD et sans nouveau plan.")
                print("Ajouts au prompt fourni : voix choisie et données calculées uniquement." if version_prompt == 1 else
                      "Ajouts au prompt fourni : données calculées uniquement. Ton défini par ton prompt, sans ancien style.")
                if version_prompt == 2:
                    print("Mémoire : resume et details (mots_cles, themes_prioritaires, deja_developpe).")
                print("Modèle :", MODELE, "— réflexion adaptative — effort moyen — 10000 tokens maximum.")
                print("Prompt complet :", dossier / "prompt_complet_bloc_1.txt")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalEssai(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    if not isinstance(resultat.get("texte"), str) or not resultat["texte"].strip():
                        raise ValueError("Texte absent ; réponse brute conservée.")
                    memoire = resultat.get("memoire", {})
                    references = [c.get("reference") for c in memoire.get("faits_cites", []) if isinstance(c, dict)]
                    diagnostic = {"nombre_mots": len(resultat["texte"].split()),
                                  "references_inconnues": [r for r in references if not isinstance(r, str) or r not in faits],
                                  "nature": "Structure et existence des références seulement ; interprétation à relire.",
                                  "validation_humaine": False}
                    resultat["diagnostic"] = diagnostic
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, "bloc_1", generer, appel, journal=journal)
                    ecrire_json(dossier, "diagnostic_bloc_1.json", resultat["diagnostic"])
                    lecture = rendre_essai(dossier, resultat)
                    ecrire_json(dossier, "etat.json", {"statut": "essai_a_relire", "validation_humaine": False})
                    print("\nBLOC 1 TERMINÉ." if sur_dossier is not None else "\nESSAI TERMINÉ — aucun bloc suivant lancé.")
                    print("Lecture :", lecture)
                    print("Markdown :", dossier / "bloc_1.md")
                    print("Diagnostic :", json.dumps(resultat["diagnostic"], ensure_ascii=False, indent=2))
                    return 0
                except KeyboardInterrupt:
                    print("ARRÊT MANUEL — éléments reçus conservés, aucune relance.")
                    return 130
                except Exception as exc:
                    print("ARRÊT :", type(exc).__name__, "—", exc)
                    print("Réponse brute conservée si reçue. Aucun appel supplémentaire.")
                    return 1
                finally:
                    print("Budget et tokens :", dossier / "budget_ia.json")
                    print("Journal :", dossier / "terminal.log")
