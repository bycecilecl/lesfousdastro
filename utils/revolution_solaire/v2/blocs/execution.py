"""Lancement manuel d'un bloc RS ; une réponse archivée est réutilisée gratuitement."""

import contextlib
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import lire_json, ecrire_json, verrou_demande
from ..dossier import controler_completude_dossier
from ..connaissances import reperes_documentaires_a_archiver
from ..service import _etape_archivee, _fournisseur_borne, _notifier, options_claude_v2
from . import bloc_1
from .presentation_faits import normaliser_prompt_comparaison


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2" / "par_blocs"


def _source(cas, source_factuel):
    source = (ROOT / source_factuel).expanduser().resolve()
    dossier = lire_json(source, "dossier_factuel.json")
    demande = lire_json(source, "demande.json")
    if not isinstance(dossier, dict) or not isinstance(demande, dict):
        raise ValueError("Dossier factuel ou profil source absent. Aucun appel lancé.")
    for champ in ("personne", "lieu_rs", "annee"):
        if cas.get(champ) != demande.get(champ):
            raise ValueError("Profil différent de l'archive pour " + champ + ". Aucun appel lancé.")
    controler_completude_dossier(dossier)
    return dossier, source


def preparer_reprise_bloc_1(demande, chemin):
    """Identité distincte pour un essai manuel après l'erreur réseau désignée.

    Ne déplace, n'efface ni ne réinitialise l'archive précédente ou son budget.
    L'identité reste stable : relancer la même reprise ne donne pas un essai de plus.
    """
    source = (ROOT / chemin).expanduser().resolve()
    precedente = lire_json(source, "demande.json")
    partie = source / "bloc_1"
    etat = lire_json(partie, "appel.json")
    if precedente != demande:
        raise ValueError("La tentative désignée ne correspond pas au même profil, modèle, prompt et dossier factuel. Aucun appel lancé.")
    if not isinstance(etat, dict) or etat.get("statut") != "a_verifier" or etat.get("type_erreur") != "APIConnectionError":
        raise ValueError("Cette reprise exige une tentative arrêtée sur APIConnectionError. Aucun appel lancé.")
    if any((partie / nom).exists() for nom in ("reponse.json", "reponse_partielle.json", "reponse_completee.json", "resultat.json")):
        raise ValueError("Une réponse est déjà archivée : cette reprise réseau ne la remplace pas. Aucun appel lancé.")
    return {"source": str(source), "cause": "APIConnectionError", "nouvelle_tentative_maximum": 1}


def _rendre_bloc_1(dossier):
    """Export de la réponse reçue ; aucun texte client réécrit."""
    import markdown
    partie = Path(dossier) / "bloc_1"
    reponse = lire_json(partie, "reponse.json") or lire_json(partie, "reponse_partielle.json")
    if reponse is None:
        return None
    from ..analyse import parser_json_reponse
    try:
        resultat = parser_json_reponse(reponse["texte"])
        texte = resultat.get("texte")
        if not isinstance(texte, str):
            texte = reponse["texte"]
        memoire = resultat.get("memoire", {})
    except Exception:
        texte, memoire = reponse["texte"], {}
    texte, _ = bloc_1.nettoyer_parasites(texte)
    (Path(dossier) / "bloc_1.md").write_text(texte, encoding="utf-8")
    # Garde la déclaration originale consultable, mais transmet aux blocs
    # suivants la mémoire de travail issue du repérage conservateur.
    ecrire_json(dossier, "memoire_declaree_bloc_1.json", memoire)
    traite = lire_json(partie, "resultat.json")
    if isinstance(traite, dict) and isinstance(traite.get("memoire"), dict):
        memoire = traite["memoire"]
    ecrire_json(dossier, "memoire_bloc_1.json", memoire)
    controle = lire_json(partie, "controle.json") or {}
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS V2 — Bloc 1</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:24px 0}summary{cursor:pointer}"
            "</style><body><aside>Bloc 1 à relire. Texte de Claude conservé, sans réécriture finale. "
            "Les suffixes parasites d'image sont retirés de l'affichage ; la réponse brute reste archivée. "
            "Ce bloc ne constitue pas encore le rapport complet.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Mécanismes déclarés et citations repérées — mémoire à relire</summary><pre>"
            + escape(json.dumps(memoire, ensure_ascii=False, indent=2)) + "</pre></details>"
            + "<details><summary>Suivi technique</summary><pre>"
            + escape(json.dumps(controle, ensure_ascii=False, indent=2)) + "</pre></details></body></html>")
    cible = Path(dossier) / "lecture_bloc_1.html"
    cible.write_text(html, encoding="utf-8")
    return cible


def lancer_bloc_1(cas_a_tester, *, source_factuel, modele="claude-sonnet-5", apercu=False, sur_dossier=None, plan=None,
                  utiliser_bdd=True, reprendre_apres_erreur=None, reflexion="disabled", niveau_effort="low",
                  max_tokens=None, reference_comparaison=None):
    """Un profil et le seul bloc 1. Les blocs 2–4 ne sont jamais appelés ici."""
    from ..terminal import Tee, JournalTerminal, afficher_requete
    if len(cas_a_tester) != 1:
        raise ValueError("Le test du bloc 1 exige un profil unique.")
    cas = cas_a_tester[0]
    factuel, source = _source(cas, source_factuel)
    prompt, faits, entree, proprietaires = bloc_1.construire_prompt_bloc_1(
        factuel, genre=cas["personne"].get("genre", ""), plan=plan, utiliser_bdd=utiliser_bdd)
    demande = {"mode": bloc_1.VERSION, "modele": modele, "profil": {
        k: cas[k] for k in ("personne", "lieu_rs", "annee")}, "source_factuel": str(source),
        "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
        "empreinte_prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
    if not utiliser_bdd:
        demande["utiliser_bdd"] = False
    options = bloc_1.options_generation_bloc_1(
        plan=plan, reflexion=reflexion, niveau_effort=niveau_effort, max_tokens=max_tokens)
    if reflexion != "disabled" or niveau_effort != "low" or options["max_tokens"] != bloc_1.MAX_TOKENS:
        demande["reglages_generation"] = {
            "reflexion": reflexion, "niveau_effort": niveau_effort, "max_tokens": options["max_tokens"]}
    comparaison = None
    if reference_comparaison is not None:
        reference = (ROOT / reference_comparaison).expanduser().resolve()
        ancien = lire_json(reference, "demande.json")
        prompt_reference = reference / "prompt_complet_bloc_1.txt"
        if not isinstance(ancien, dict) or not prompt_reference.is_file() or not (reference / "bloc_1.md").is_file():
            raise ValueError("Bloc de comparaison incomplet. Aucun appel lancé.")
        if (ancien.get("profil") != demande["profil"]
                or ancien.get("empreinte_faits") != demande["empreinte_faits"]
                or normaliser_prompt_comparaison(prompt_reference.read_text(encoding="utf-8"))
                != normaliser_prompt_comparaison(prompt)):
            raise ValueError("Le profil, les faits ou le prompt ont changé depuis le bloc de comparaison. Aucun appel lancé.")
        identique = prompt_reference.read_text(encoding="utf-8") == prompt
        comparaison = {"source": str(reference), "modele_reference": ancien.get("modele"),
                       "prompt_identique": identique, "faits_identiques": True,
                       "correction_affichage": None if identique else "Mention des seules rétrogradations et retrait du rappel redondant propre à Pluton.",
                       "nature": "Comparaison de configurations : modèle et réflexion changent ensemble."}
        demande["reference_comparaison"] = str(reference)
    reprise = preparer_reprise_bloc_1(demande, reprendre_apres_erreur) if reprendre_apres_erreur is not None else None
    if reprise is not None:
        demande["reprise_manuelle"] = reprise

    class JournalBloc(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 1 — POSTURE, MAÎTRES ET PROFECTION")
                print("Archives :", self.partie)
                return
            if evenement == "controle_valide":
                print("Réponse traitée — lecture et mémoire à relire, aucune validation automatique.")
                return
            super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES / "bloc_1") as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        # Un nouvel identifiant de prompt conserve toutes les versions antérieures.
        ecrire_json(dossier, "demande.json", demande)
        if reprise is not None:
            ecrire_json(dossier, "reprise_manuelle.json", reprise)
        if comparaison is not None:
            ecrire_json(dossier, "comparaison.json", comparaison)
        if plan is not None:
            ecrire_json(dossier, "plan_commun.json", plan)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_1.json", entree)
        ecrire_json(dossier, "references_documentaires_rs.json",
                    reperes_documentaires_a_archiver(factuel, entree["repartition_des_faits"])
                    if utiliser_bdd else {"bdd_active": False, **bloc_1.reperes_sans_bdd()})
        ecrire_json(dossier, "affectations_prevues_bloc_1.json", proprietaires)
        # Un aperçu et une affectation prévue ne prouvent aucun développement.
        if lire_json(dossier, "proprietaires_faits_bloc_1.json") is None:
            ecrire_json(dossier, "proprietaires_faits_bloc_1.json", {})
        ecrire_json(dossier, "references_de_contexte_bloc_1.json", entree["references_de_contexte"])
        ecrire_json(dossier, "repartition_des_faits_bloc_1.json", entree["repartition_des_faits"])
        (dossier / "prompt_complet_bloc_1.txt").write_text(prompt, encoding="utf-8")
        empreinte_code = hashlib.sha256((Path(__file__).read_bytes() + Path(bloc_1.__file__).read_bytes()
                                        + bloc_1.PROMPT_PATH.read_bytes()
                                        + bloc_1.STYLE_PATH.read_bytes()
                                        + bloc_1.REGLES_PATH.read_bytes()
                                        + Path(__file__).with_name("plan_partage.py").read_bytes()
                                        + Path(__file__).with_name("prompt_plan_partage.txt").read_bytes()
                                        + Path(__file__).with_name("suivi_memoire.py").read_bytes()
                                        + Path(__file__).with_name("appuis_memoire.py").read_bytes()
                                        + Path(__file__).with_name("presentation_faits.py").read_bytes()
                                        + (ROOT / "utils/revolution_solaire/v2/connaissances.py").read_bytes())).hexdigest()[:16]
        snapshots = dossier / "versions_code" / empreinte_code
        snapshots.mkdir(parents=True, exist_ok=True)
        for fichier in (Path(__file__), Path(bloc_1.__file__), bloc_1.PROMPT_PATH, bloc_1.STYLE_PATH, bloc_1.REGLES_PATH,
                        ROOT / "utils/revolution_solaire/v2/analyse.py",
                        ROOT / "utils/revolution_solaire/v2/memoire_redaction.py",
                        ROOT / "utils/revolution_solaire/v2/connaissances.py",
                        Path(__file__).with_name("repartition.py"), Path(__file__).with_name("suivi_memoire.py"), Path(__file__).with_name("appuis_memoire.py"),
                        Path(__file__).with_name("presentation_faits.py"),
                        Path(__file__).with_name("plan_partage.py"), Path(__file__).with_name("prompt_plan_partage.txt")):
            cible = snapshots / fichier.name
            if not cible.exists():
                shutil.copy2(fichier, cible)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("RS V2 PAR BLOCS —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("BDD :", "activée" if utiliser_bdd else "DÉSACTIVÉE — aucune fiche envoyée")
                print("Modèle :", modele)
                print("Réflexion :", reflexion, "— effort :", niveau_effort, "— plafond de sortie :", options["max_tokens"])
                if comparaison is not None:
                    print("COMPARAISON — mêmes faits, modèle et réflexion modifiés.")
                    if comparaison["correction_affichage"]:
                        print("Correction d'affichage appliquée :", comparaison["correction_affichage"])
                    print("Lecture de référence :", Path(comparaison["source"]) / "lecture_bloc_1.html")
                if reprise is not None:
                    print("REPRISE MANUELLE — un nouvel essai maximum ; aucune relance automatique.")
                    print("Échec précédent conservé :", reprise["source"])
                print("Version du bloc :", dossier)
                print("Prompt complet :", dossier / "prompt_complet_bloc_1.txt")
                print("Données :", dossier / "donnees_envoyees_bloc_1.json")
                print("Un appel maximum pour ce bloc ; le parcours complet enchaîne la suite." if sur_dossier else
                      "Un seul bloc ; un appel maximum. Aucun bloc suivant ni réécriture globale.")
                print("Calculs archivés réutilisés. Aucun texte des anciennes analyses transmis.")
                print("Chaque nouveau prompt a sa propre archive ; une reprise identique relit sa réponse.")
                if apercu:
                    parametres = options_claude_v2(modele, options)
                    afficher_requete(modele, prompt, parametres, apercu=True)
                    print("APERÇU GRATUIT TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                try:
                    resultat = _etape_archivee(dossier, "bloc_1", lambda appeler:
                        bloc_1.generer_bloc_1(factuel, appeler=appeler, genre=cas["personne"].get("genre", ""),
                                             plan=plan, utiliser_bdd=utiliser_bdd, reflexion=reflexion,
                                             niveau_effort=niveau_effort, max_tokens=max_tokens),
                        appel, journal=journal)
                    ecrire_json(dossier, "diagnostic_bloc_1.json", resultat["diagnostic"])
                    reperes = resultat["diagnostic"]["faits_cites_reperes"]
                    ecrire_json(dossier, "proprietaires_faits_bloc_1.json",
                                {cle: 1 for cle in reperes if cle in proprietaires})
                    ecrire_json(dossier, "faits_non_reperes_bloc_1.json", resultat["diagnostic"]["faits_non_reperes"])
                    ecrire_json(Path(dossier) / "bloc_1", "controle.json",
                                {"statut": "a_relire", "mode": "reperage_lexical_non_validation",
                                 "validation_humaine": False})
                    _notifier(journal, "diagnostic_bloc_1", diagnostic=resultat["diagnostic"])
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_1_a_relire", "rapport_complet": False,
                                                       "validation_humaine": False})
                    print("\nBLOC 1 TERMINÉ — retour au parcours complet." if sur_dossier else
                          "\nBLOC 1 TERMINÉ — arrêt prévu après ce seul bloc.")
                    return 0
                except KeyboardInterrupt:
                    print("\nARRÊT MANUEL — réponses conservées, aucune relance.")
                    return 130
                except Exception as exc:
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Aucun appel supplémentaire ; les éléments reçus restent archivés.")
                    return 1
                finally:
                    lecture = _rendre_bloc_1(dossier)
                    if lecture:
                        print("Lecture :", lecture)
                        print("Texte conservé :", dossier / "bloc_1.md")
                        print("Mémoire conservée :", dossier / "memoire_bloc_1.json")
                    print("Journal :", dossier / "terminal.log")
