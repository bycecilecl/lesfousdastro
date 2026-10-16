"""Lance uniquement Soleil/Lune à partir d'un bloc 1 choisi et archivé."""

import contextlib
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..dossier import controler_completude_dossier
from ..connaissances import reperes_documentaires_a_archiver
from ..filtrage_aspects import fait_autorise
from ..service import _etape_archivee, _fournisseur_borne, _notifier, options_claude_v2
from . import bloc_2
from .bloc_1 import nettoyer_parasites, reperes_sans_bdd
from .plan_partage import reprendre_plan
from .appuis_memoire import cumuler_memoires


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2" / "par_blocs" / "bloc_2"


def charger_bloc_1(cas, chemin):
    """Charge sa version explicite sans générer, recalculer ou modifier la source."""
    source = (ROOT / chemin).expanduser().resolve()
    demande = lire_json(source, "demande.json")
    factuel = lire_json(source, "dossier_factuel.json")
    memoire = lire_json(source, "memoire_bloc_1.json")
    proprietaires = lire_json(source, "proprietaires_faits_bloc_1.json")
    if not all(isinstance(v, dict) for v in (demande, factuel, memoire, proprietaires)) or not (source / "bloc_1.md").is_file():
        raise ValueError("Bloc 1 incomplet : données, mémoire, propriété ou texte absent. Aucun appel lancé.")
    profil = demande.get("profil", demande)
    for champ in ("personne", "lieu_rs", "annee"):
        if profil.get(champ) != cas.get(champ):
            raise ValueError("Profil différent du bloc 1 pour " + champ + ". Aucun appel lancé.")
    controler_completude_dossier(factuel)
    proprietaires = {cle: n for cle, n in proprietaires.items()
                     if cle in factuel["faits"] and fait_autorise(factuel["faits"][cle])}
    return factuel, memoire, proprietaires, (source / "bloc_1.md").read_text(encoding="utf-8"), source


def rendre_bloc_2(dossier):
    """Exporte le texte reçu ; pas de réécriture ni de génération du bloc 1."""
    import markdown
    partie = dossier / "bloc_2"
    reponse = lire_json(partie, "reponse.json") or lire_json(partie, "reponse_partielle.json")
    if reponse is None:
        return None
    from ..analyse import parser_json_reponse
    try:
        brut = parser_json_reponse(reponse["texte"])
        texte = brut.get("texte")
        if not isinstance(texte, str):
            texte = reponse["texte"]
        memoire_declaree = brut.get("memoire", {})
    except Exception:
        texte, memoire_declaree = reponse["texte"], {}
    texte, _ = nettoyer_parasites(texte)
    (dossier / "bloc_2.md").write_text(texte, encoding="utf-8")
    ecrire_json(dossier, "memoire_declaree_bloc_2.json", memoire_declaree)
    ecrire_json(dossier, "memoire_brute_bloc_2.json", memoire_declaree)
    traite = lire_json(partie, "resultat.json") or {}
    memoire = traite.get("memoire", {})
    ecrire_json(dossier, "memoire_bloc_2.json", memoire)
    controle = traite.get("diagnostic", {})
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS V2 — Bloc 2 Soleil et Lune</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:24px 0}summary{cursor:pointer}"
            "</style><body><aside>Bloc 2 — Soleil et Lune, à relire. "
            "Texte reçu conservé ; suffixes parasites retirés de l'affichage. "
            "Le bloc 1 et la réponse brute restent archivés. Ce bloc n'est pas le rapport complet.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Mémoire du bloc 2</summary><pre>"
            + escape(json.dumps(memoire, ensure_ascii=False, indent=2)) + "</pre></details>"
            + "<details><summary>Diagnostic à relire</summary><pre>"
            + escape(json.dumps(controle, ensure_ascii=False, indent=2)) + "</pre></details></body></html>")
    chemin = dossier / "lecture_bloc_2.html"
    chemin.write_text(html, encoding="utf-8")
    return chemin


def lancer_bloc_2(cas_a_tester, *, source_bloc_1, modele="claude-sonnet-5", apercu=False, sur_dossier=None, plan=None, utiliser_bdd=True):
    """Un seul bloc, un appel maximum, aucune relance payante automatique."""
    from ..terminal import Tee, JournalTerminal, afficher_requete
    if len(cas_a_tester) != 1:
        raise ValueError("Le bloc 2 exige un profil unique.")
    cas = cas_a_tester[0]
    factuel, memoire, precedents, texte_1, source = charger_bloc_1(cas, source_bloc_1)
    plan = reprendre_plan(source, plan, 1)
    arguments = {"memoire": memoire, "proprietaires_precedents": precedents,
                 "texte_bloc_1": texte_1, "genre": cas["personne"].get("genre", ""), "plan": plan,
                 "utiliser_bdd": utiliser_bdd}
    prompt, _, entree, prevus, ecartes = bloc_2.construire_prompt_bloc_2(factuel, **arguments)
    demande = {"mode": bloc_2.VERSION, "modele": modele,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_bloc_1": str(source),
               "empreintes_source": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest()
                   for nom in ("dossier_factuel.json", "memoire_bloc_1.json", "proprietaires_faits_bloc_1.json", "bloc_1.md")},
               "empreinte_prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
    if not utiliser_bdd:
        demande["utiliser_bdd"] = False

    class JournalBloc2(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 2 — SOLEIL ET LUNE\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse traitée — texte et mémoire à relire, aucune validation automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        if plan is not None:
            ecrire_json(dossier, "plan_commun.json", plan)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_2.json", entree)
        ecrire_json(dossier, "references_documentaires_rs.json",
                    reperes_documentaires_a_archiver(factuel, entree["repartition_des_faits"])
                    if utiliser_bdd else {"bdd_active": False, **reperes_sans_bdd()})
        ecrire_json(dossier, "memoire_source_bloc_1.json", memoire)
        ecrire_json(dossier, "memoire_transmise_bloc_1.json", entree["memoire_editoriale_bloc_1"])
        ecrire_json(dossier, "elements_memoire_non_transmis.json", ecartes)
        ecrire_json(dossier, "affectations_prevues_bloc_2.json", prevus)
        ecrire_json(dossier, "repartition_des_faits_bloc_2.json", entree["repartition_des_faits"])
        if lire_json(dossier, "proprietaires_faits_bloc_2.json") is None:
            ecrire_json(dossier, "proprietaires_faits_bloc_2.json", precedents)
        (dossier / "prompt_complet_bloc_2.txt").write_text(prompt, encoding="utf-8")
        sources = [Path(__file__).with_name("plan_partage.py"),
                   Path(__file__).with_name("prompt_plan_partage.txt"), Path(__file__), Path(bloc_2.__file__), bloc_2.PROMPT_PATH,
                   Path(__file__).with_name("bloc_1.py"), Path(__file__).with_name("repartition.py"),
                   Path(__file__).with_name("suivi_memoire.py"), Path(__file__).with_name("appuis_memoire.py"), Path(__file__).with_name("regles.txt"),
                   Path(__file__).with_name("style_lecture.txt"),
                   ROOT / "utils/revolution_solaire/v2/filtrage_aspects.py",
                   ROOT / "utils/revolution_solaire/v2/memoire_redaction.py",
                   ROOT / "utils/revolution_solaire/v2/connaissances.py"]
        empreinte = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()[:16]
        snapshots = dossier / "versions_code" / empreinte
        snapshots.mkdir(parents=True, exist_ok=True)
        for path in sources:
            if not (snapshots / path.name).exists():
                shutil.copy2(path, snapshots / path.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("RS V2 — BLOC 2 —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("BDD :", "activée" if utiliser_bdd else "DÉSACTIVÉE — aucune fiche envoyée")
                print("Bloc 1 réutilisé :", source)
                print("Sorties du bloc 2 :", dossier)
                print("Prompt complet :", dossier / "prompt_complet_bloc_2.txt")
                print("Soleil et Lune uniquement. Un appel maximum ; aucune pause ni relance automatique.")
                print("Le bloc 1 n'est ni régénéré ni modifié. Aucun contexte personnel envoyé avant la conclusion.")
                print("Préparation de mémoire :", json.dumps(ecartes, ensure_ascii=False, indent=2))
                if apercu:
                    options = options_claude_v2(modele, {"max_tokens": bloc_2.MAX_TOKENS, "temperature": 0.5,
                        "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": bloc_2.schema_bloc_2(plan=plan)})
                    afficher_requete(modele, prompt, options, apercu=True)
                    print("APERÇU GRATUIT TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc2(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                code_retour = 0
                try:
                    resultat = _etape_archivee(dossier, "bloc_2", lambda appeler:
                        bloc_2.generer_bloc_2(factuel, appeler=appeler, **arguments), appel, journal=journal)
                    ecrire_json(dossier, "memoire_brute_bloc_2.json", resultat["memoire_brute"])
                    diagnostic = resultat["diagnostic"]
                    ecrire_json(dossier, "diagnostic_bloc_2.json", diagnostic)
                    # Propriété éditoriale : inclut les citations partiellement
                    # repérées, dont le statut à relire reste dans la mémoire.
                    reperes = diagnostic["faits_abordes"]
                    ecrire_json(dossier, "proprietaires_faits_bloc_2.json",
                        {**precedents, **{cle: 2 for cle in reperes if prevus.get(cle) == 2}})
                    ecrire_json(dossier, "faits_non_reperes_bloc_2.json", diagnostic["faits_non_reperes"])
                    ecrire_json(dossier, "memoire_cumulative.json",
                        cumuler_memoires({"bloc_1": memoire}, 2, resultat["memoire"]))
                    ecrire_json(dossier / "bloc_2", "controle.json",
                        {"statut": "a_relire", "mode": "reperage_lexical_non_validation", "validation_humaine": False})
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_2_a_relire", "rapport_complet": False, "validation_humaine": False})
                    _notifier(journal, "diagnostic_bloc_2", diagnostic=diagnostic)
                    print("\nBLOC 2 TERMINÉ — aucun bloc suivant lancé.")
                except KeyboardInterrupt:
                    print("\nARRÊT MANUEL — réponses conservées, aucune relance.")
                    code_retour = 130
                except Exception as exc:
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Aucun appel supplémentaire ; les éléments reçus restent archivés.")
                    code_retour = 1
                finally:
                    try:
                        lecture = rendre_bloc_2(dossier)
                        if lecture:
                            print("Lecture :", lecture)
                            print("Markdown :", dossier / "bloc_2.md")
                            print("Mémoire :", dossier / "memoire_bloc_2.json")
                    except Exception as exc:
                        print("Export interrompu :", type(exc).__name__, "—", exc)
                        print("Réponse brute conservée dans", dossier / "bloc_2")
                        code_retour = 1
                    print("Journal :", dossier / "terminal.log")
                return code_retour
