"""Lancement manuel du seul bloc 3 depuis un bloc 2 explicitement choisi."""

import contextlib
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..connaissances import reperes_documentaires_a_archiver
from ..dossier import controler_completude_dossier
from ..filtrage_aspects import fait_autorise
from ..service import _etape_archivee, _fournisseur_borne, _notifier, options_claude_v2
from . import bloc_3
from .bloc_1 import nettoyer_parasites
from .plan_partage import reprendre_plan
from .suivi_memoire import reperer_configurations_developpees
from .appuis_memoire import cumuler_memoires


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2" / "par_blocs" / "bloc_3"


def charger_bloc_2(cas, chemin):
    """Lit les faits, mémoires et propriétaires ; aucune génération précédente."""
    source = (ROOT / chemin).expanduser().resolve()
    demande = lire_json(source, "demande.json")
    factuel = lire_json(source, "dossier_factuel.json")
    memoires = lire_json(source, "memoire_cumulative.json")
    proprietaires = lire_json(source, "proprietaires_faits_bloc_2.json")
    if not all(isinstance(v, dict) for v in (demande, factuel, memoires, proprietaires)) or not (source / "bloc_2.md").is_file():
        raise ValueError("Bloc 2 incomplet : données, mémoire, propriété ou texte absent. Aucun appel lancé.")
    if not all(isinstance(memoires.get(nom), dict) for nom in ("bloc_1", "bloc_2")):
        raise ValueError("Mémoires des blocs 1 et 2 absentes. Aucun appel lancé.")
    for champ in ("personne", "lieu_rs", "annee"):
        if demande.get("profil", {}).get(champ) != cas.get(champ):
            raise ValueError("Profil différent du bloc 2 pour " + champ + ". Aucun appel lancé.")
    controler_completude_dossier(factuel)
    proprietaires = {cle: n for cle, n in proprietaires.items()
                     if cle in factuel["faits"] and fait_autorise(factuel["faits"][cle])}
    textes = [{"bloc": 2, "source": str(source / "bloc_2.md"),
               "texte": (source / "bloc_2.md").read_text(encoding="utf-8")}]
    chemin_bloc_1 = demande.get("source_bloc_1")
    if isinstance(chemin_bloc_1, str) and chemin_bloc_1:
        texte_1 = (ROOT / chemin_bloc_1).expanduser().resolve() / "bloc_1.md"
        if texte_1.is_file():
            textes.insert(0, {"bloc": 1, "source": str(texte_1),
                              "texte": texte_1.read_text(encoding="utf-8")})
    autorises = {cle: f for cle, f in factuel["faits"].items() if fait_autorise(f)}
    figures = reperer_configurations_developpees(autorises, textes)
    for cle, preuve in figures.items():
        proprietaires.setdefault(cle, preuve["bloc"])
    return factuel, memoires, proprietaires, source, figures


def rendre_bloc_3(dossier):
    """Exporte le texte reçu ; les deux premiers blocs restent intacts."""
    import markdown
    partie = dossier / "bloc_3"
    reponse = lire_json(partie, "reponse.json") or lire_json(partie, "reponse_partielle.json")
    if reponse is None:
        return None
    from ..analyse import parser_json_reponse
    try:
        brut = parser_json_reponse(reponse["texte"])
        texte = brut.get("texte")
        if not isinstance(texte, str):
            texte = reponse["texte"]
        declaree = brut.get("memoire", {})
    except Exception:
        texte, declaree = reponse["texte"], {}
    texte, _ = nettoyer_parasites(texte)
    (dossier / "bloc_3.md").write_text(texte, encoding="utf-8")
    ecrire_json(dossier, "memoire_brute_bloc_3.json", declaree)
    traite = lire_json(partie, "resultat.json") or {}
    memoire = traite.get("memoire", {})
    ecrire_json(dossier, "memoire_bloc_3.json", memoire)
    controle = traite.get("diagnostic", {})
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS V2 — Bloc 3 MC et compléments</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:24px 0}summary{cursor:pointer}"
            "</style><body><aside>Bloc 3 — MC, ses maîtres et compléments, à relire. "
            "Texte reçu conservé ; suffixes parasites retirés de l'affichage. "
            "Les blocs 1 et 2 et la réponse brute restent archivés. Ce bloc n'est pas le rapport complet.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Mémoire du bloc 3</summary><pre>"
            + escape(json.dumps(memoire, ensure_ascii=False, indent=2)) + "</pre></details>"
            + "<details><summary>Diagnostic à relire</summary><pre>"
            + escape(json.dumps(controle, ensure_ascii=False, indent=2)) + "</pre></details></body></html>")
    chemin = dossier / "lecture_bloc_3.html"
    chemin.write_text(html, encoding="utf-8")
    return chemin


def lancer_bloc_3(cas_a_tester, *, source_bloc_2, modele="claude-sonnet-5", apercu=False, sur_dossier=None, plan=None, utiliser_bdd=True):
    """Un seul bloc, un appel maximum, aucune pause ni relance automatique."""
    from ..terminal import Tee, JournalTerminal, afficher_requete
    if len(cas_a_tester) != 1:
        raise ValueError("Le bloc 3 exige un profil unique.")
    cas = cas_a_tester[0]
    factuel, memoires, precedents, source, figures = charger_bloc_2(cas, source_bloc_2)
    plan = reprendre_plan(source, plan, 2)
    arguments = {"memoires": memoires, "proprietaires_precedents": precedents,
                 "genre": cas["personne"].get("genre", ""), "plan": plan,
                 "utiliser_bdd": utiliser_bdd}
    prompt, _, entree, prevus, ecartes, preparation = bloc_3.construire_prompt_bloc_3(factuel, **arguments)
    demande = {"mode": bloc_3.VERSION, "modele": modele,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_bloc_2": str(source),
               "empreinte_figures_deja_developpees": hashlib.sha256(
                   json.dumps(figures, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
               "empreintes_source": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest()
                   for nom in ("dossier_factuel.json", "memoire_cumulative.json", "proprietaires_faits_bloc_2.json", "bloc_2.md")},
               "empreinte_prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
    if not utiliser_bdd:
        demande["utiliser_bdd"] = False

    class JournalBloc3(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 3 — MC, MAÎTRES ET COMPLÉMENTS\nArchives :", self.partie)
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
        ecrire_json(dossier, "donnees_envoyees_bloc_3.json", entree)
        ecrire_json(dossier, "references_documentaires_rs.json",
                    reperes_documentaires_a_archiver(factuel, entree["repartition_des_faits"])
                    if utiliser_bdd else {"bdd_active": False, **bloc_3.reperes_sans_bdd()})
        ecrire_json(dossier, "memoires_sources_blocs_1_2.json", memoires)
        # Extraits justificatifs archivés, pas transmis dans le prompt.
        ecrire_json(dossier, "figures_deja_developpees.json", figures)
        ecrire_json(dossier, "memoires_transmises_blocs_1_2.json", entree["memoires_editoriales"])
        ecrire_json(dossier, "elements_memoire_non_transmis.json", ecartes)
        ecrire_json(dossier, "preparation_editoriale_bloc_3.json", preparation)
        ecrire_json(dossier, "affectations_prevues_bloc_3.json", prevus)
        ecrire_json(dossier, "repartition_des_faits_bloc_3.json", entree["repartition_des_faits"])
        if lire_json(dossier, "proprietaires_faits_bloc_3.json") is None:
            ecrire_json(dossier, "proprietaires_faits_bloc_3.json", precedents)
        (dossier / "prompt_complet_bloc_3.txt").write_text(prompt, encoding="utf-8")
        sources = [Path(__file__).with_name("plan_partage.py"),
                   Path(__file__).with_name("prompt_plan_partage.txt"), Path(__file__), Path(bloc_3.__file__), bloc_3.PROMPT_PATH,
                   Path(__file__).with_name("bloc_1.py"), Path(__file__).with_name("repartition.py"),
                   Path(__file__).with_name("suivi_memoire.py"), Path(__file__).with_name("appuis_memoire.py"), Path(__file__).with_name("regles.txt"),
                   Path(__file__).with_name("preparation_bloc_3.py"),
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
                print("RS V2 — BLOC 3 —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("BDD :", "activée" if utiliser_bdd else "DÉSACTIVÉE — aucune fiche envoyée")
                print("Bloc 2 source :", source)
                print("Sorties du bloc 3 :", dossier)
                print("Prompt complet :", dossier / "prompt_complet_bloc_3.txt")
                print("MC, maîtres et compléments. Un appel maximum ; aucune pause ni relance automatique.")
                print("Mémoires courtes des blocs 1 et 2 ; leurs textes restent archivés, sans réécriture.")
                print("Figures déjà développées :", ", ".join(figures) or "aucune repérée explicitement")
                print("Extraits justificatifs :", dossier / "figures_deja_developpees.json")
                print("Mécanismes complémentaires retenus :", len(entree["priorites_complementaires"]))
                print("Choix des faits et nettoyage des aides :", dossier / "preparation_editoriale_bloc_3.json")
                if apercu:
                    options = options_claude_v2(modele, {"max_tokens": bloc_3.MAX_TOKENS, "temperature": 0.5,
                        "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": bloc_3.schema_bloc_3(plan=plan)})
                    afficher_requete(modele, prompt, options, apercu=True)
                    print("APERÇU GRATUIT TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc3(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                code_retour = 0
                try:
                    resultat = _etape_archivee(dossier, "bloc_3", lambda appeler:
                        bloc_3.generer_bloc_3(factuel, appeler=appeler, **arguments), appel, journal=journal)
                    ecrire_json(dossier, "memoire_brute_bloc_3.json", resultat["memoire_brute"])
                    diagnostic = resultat["diagnostic"]
                    ecrire_json(dossier, "diagnostic_bloc_3.json", diagnostic)
                    ecrire_json(dossier, "proprietaires_faits_bloc_3.json",
                        {**precedents, **{cle: 3 for cle in diagnostic["faits_abordes"] if prevus.get(cle) == 3}})
                    ecrire_json(dossier, "faits_non_reperes_bloc_3.json", diagnostic["faits_non_reperes"])
                    ecrire_json(dossier, "memoire_cumulative.json",
                        cumuler_memoires(memoires, 3, resultat["memoire"]))
                    ecrire_json(dossier / "bloc_3", "controle.json",
                        {"statut": "a_relire", "mode": "reperage_lexical_non_validation", "validation_humaine": False})
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_3_a_relire", "rapport_complet": False, "validation_humaine": False})
                    _notifier(journal, "diagnostic_bloc_3", diagnostic=diagnostic)
                    print("\nBLOC 3 TERMINÉ — aucun bloc suivant lancé.")
                except KeyboardInterrupt:
                    print("\nARRÊT MANUEL — réponses conservées, aucune relance.")
                    code_retour = 130
                except Exception as exc:
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Aucun appel supplémentaire ; les éléments reçus restent archivés.")
                    code_retour = 1
                finally:
                    try:
                        lecture = rendre_bloc_3(dossier)
                        if lecture:
                            print("Lecture :", lecture)
                            print("Markdown :", dossier / "bloc_3.md")
                            print("Mémoire :", dossier / "memoire_bloc_3.json")
                    except Exception as exc:
                        print("Export interrompu :", type(exc).__name__, "—", exc)
                        print("Réponse brute conservée dans", dossier / "bloc_3")
                        code_retour = 1
                    print("Journal :", dossier / "terminal.log")
                return code_retour
