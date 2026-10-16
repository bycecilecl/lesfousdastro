"""Lanceur du bloc transits depuis une version du bloc 3 choisie explicitement."""

import contextlib
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..dossier import controler_completude_dossier
from ..filtrage_aspects import fait_autorise
from ..service import _etape_archivee, _fournisseur_borne, _notifier, options_claude_v2
from . import bloc_4
from .bloc_1 import nettoyer_parasites
from .plan_partage import reprendre_plan
from .appuis_memoire import cumuler_memoires


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2" / "par_blocs" / "bloc_4"


def charger_bloc_3(cas, chemin):
    """Charge les calculs et les mémoires ; ne rejoue aucun des trois blocs."""
    source = (ROOT / chemin).expanduser().resolve()
    demande = lire_json(source, "demande.json")
    factuel = lire_json(source, "dossier_factuel.json")
    memoires = lire_json(source, "memoire_cumulative.json")
    proprietaires = lire_json(source, "proprietaires_faits_bloc_3.json")
    if not all(isinstance(v, dict) for v in (demande, factuel, memoires, proprietaires)) or not (source / "bloc_3.md").is_file():
        raise ValueError("Bloc 3 incomplet : calculs, mémoire, propriété ou texte absent. Aucun appel lancé.")
    if not all(isinstance(memoires.get(nom), dict) for nom in ("bloc_1", "bloc_2", "bloc_3")):
        raise ValueError("Les trois mémoires sont nécessaires. Aucun appel lancé.")
    for champ in ("personne", "lieu_rs", "annee"):
        if demande.get("profil", {}).get(champ) != cas.get(champ):
            raise ValueError("Profil différent du bloc 3 pour " + champ + ". Aucun appel lancé.")
    controler_completude_dossier(factuel)
    proprietaires = {cle: n for cle, n in proprietaires.items()
                     if cle in factuel["faits"] and fait_autorise(factuel["faits"][cle])}
    return factuel, memoires, proprietaires, source


def rendre_bloc_4(dossier):
    """Affiche le texte reçu ; les trois premières lectures restent intactes."""
    import markdown
    partie = dossier / "bloc_4"
    reponse = lire_json(partie, "reponse.json") or lire_json(partie, "reponse_partielle.json")
    if reponse is None:
        return None
    from ..analyse import parser_json_reponse
    traite = lire_json(partie, "resultat.json") or {}
    try:
        brut = parser_json_reponse(reponse["texte"])
        texte = traite.get("texte")
        if not isinstance(texte, str) and isinstance(brut.get("texte"), str):
            texte = brut["texte"]
        if not isinstance(texte, str) and isinstance(brut.get("periodes"), list):
            entree = lire_json(dossier, "donnees_envoyees_bloc_4.json") or {}
            texte, _, _, _ = bloc_4.assembler_periodes_bloc_4(brut["periodes"], entree["reperes_calendrier"])
        if not isinstance(texte, str):
            texte = reponse["texte"]
        declaree = brut.get("memoire", {})
    except Exception:
        texte, declaree = reponse["texte"], {}
    texte, _ = nettoyer_parasites(texte)
    (dossier / "bloc_4.md").write_text(texte, encoding="utf-8")
    ecrire_json(dossier, "memoire_brute_bloc_4.json", declaree)
    memoire = traite.get("memoire", {})
    ecrire_json(dossier, "memoire_bloc_4.json", memoire)
    controle = traite.get("diagnostic", {})
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS V2 — Bloc 4 Transits annuels</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:24px 0}summary{cursor:pointer}"
            "</style><body><aside>Bloc 4 — les transits annuels, à relire. Texte reçu conservé ; "
            "les trois premières lectures et la réponse brute restent archivées. Ce bloc n'est pas le rapport complet.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Mémoire du bloc 4</summary><pre>"
            + escape(json.dumps(memoire, ensure_ascii=False, indent=2)) + "</pre></details>"
            + "<details><summary>Diagnostic à relire</summary><pre>"
            + escape(json.dumps(controle, ensure_ascii=False, indent=2)) + "</pre></details></body></html>")
    chemin = dossier / "lecture_bloc_4.html"
    chemin.write_text(html, encoding="utf-8")
    return chemin


def lancer_bloc_4(cas_a_tester, *, source_bloc_3, modele="claude-sonnet-5", apercu=False, sur_dossier=None, plan=None):
    """Un appel maximum, sans pause, sans nouvel appel aux blocs précédents."""
    from ..terminal import Tee, JournalTerminal, afficher_requete
    if len(cas_a_tester) != 1:
        raise ValueError("Le bloc 4 exige un profil unique.")
    cas = cas_a_tester[0]
    factuel, memoires, precedents, source = charger_bloc_3(cas, source_bloc_3)
    plan = reprendre_plan(source, plan, 3)
    arguments = {"memoires": memoires, "proprietaires_precedents": precedents,
                 "genre": cas["personne"].get("genre", ""), "plan": plan}
    prompt, transits, entree, audit = bloc_4.construire_prompt_bloc_4(factuel, **arguments)
    demande = {"mode": bloc_4.VERSION, "modele": modele,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_bloc_3": str(source),
               "empreintes_source": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest()
                   for nom in ("dossier_factuel.json", "memoire_cumulative.json", "proprietaires_faits_bloc_3.json")},
               "empreinte_prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}

    class JournalBloc4(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 4 — TRANSITS ANNUELS\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse traitée — périodes, texte et mémoire à relire ; aucune validation automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        if plan is not None:
            ecrire_json(dossier, "plan_commun.json", plan)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_4.json", entree)
        ecrire_json(dossier, "selection_transits_bloc_4.json", audit)
        ecrire_json(dossier, "reperes_calendrier_bloc_4.json", entree["reperes_calendrier"])
        ecrire_json(dossier, "memoires_sources_blocs_1_2_3.json", memoires)
        ecrire_json(dossier, "memoires_transmises_blocs_1_2_3.json", entree["rappel_sujets_et_roles"])
        if lire_json(dossier, "proprietaires_faits_bloc_4.json") is None:
            ecrire_json(dossier, "proprietaires_faits_bloc_4.json", precedents)
        (dossier / "prompt_complet_bloc_4.txt").write_text(prompt, encoding="utf-8")
        sources = [Path(__file__).with_name("plan_partage.py"),
                   Path(__file__).with_name("prompt_plan_partage.txt"), Path(__file__), Path(bloc_4.__file__), bloc_4.PROMPT_PATH,
                   Path(__file__).with_name("filtrage_transits.py"),
                   Path(__file__).with_name("calendrier_bloc_4.py"),
                   Path(__file__).with_name("bloc_1.py"), Path(__file__).with_name("suivi_memoire.py"), Path(__file__).with_name("appuis_memoire.py"),
                   bloc_4.REGLES_PATH, Path(__file__).with_name("style_lecture.txt"),
                   ROOT / "utils/revolution_solaire/v2/filtrage_aspects.py",
                   ROOT / "utils/revolution_solaire/v2/memoire_redaction.py",
                   ROOT / "utils/revolution_solaire/v2/releve_transits.py"]
        empreinte = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()[:16]
        snapshots = dossier / "versions_code" / empreinte
        snapshots.mkdir(parents=True, exist_ok=True)
        for path in sources:
            if not (snapshots / path.name).exists():
                shutil.copy2(path, snapshots / path.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("RS V2 — BLOC 4 —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("Bloc 3 source :", source)
                print("Sorties du bloc 4 :", dossier)
                print("Prompt complet :", dossier / "prompt_complet_bloc_4.txt")
                print("Un appel maximum ; cinq périodes significatives au plus. Aucune pause ni relance automatique.")
                print("Calculs archivés réutilisés ; aucun recalcul ni appel aux blocs précédents.")
                print("Fenêtres calculées :", audit["fenetres_calculees"])
                print("Familles lentes retenues :", audit["familles_lentes_retenues"])
                print("Familles RS/natal :", audit["familles_par_cadre"])
                print("Fenêtres transmises :", audit["fenetres_transmises"])
                print("Déclencheurs Mars :", audit["declencheurs_mars_retenus"])
                print("Sélection et motifs d'exclusion :", dossier / "selection_transits_bloc_4.json")
                print("Les plages et les passages repères seront affichés par le moteur depuis les jours calculés.")
                if apercu:
                    options = options_claude_v2(modele, {"max_tokens": bloc_4.MAX_TOKENS, "temperature": 0.5,
                        "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": bloc_4.schema_bloc_4(entree["reperes_calendrier"], plan=plan)})
                    afficher_requete(modele, prompt, options, apercu=True)
                    print("APERÇU GRATUIT TERMINÉ — aucun appel Claude.")
                    return 0
                if not transits:
                    print("Aucun transit sélectionné : consulte le fichier de sélection. Aucun appel Claude.")
                    return 1
                journal = JournalBloc4(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                code_retour = 0
                try:
                    resultat = _etape_archivee(dossier, "bloc_4", lambda appeler:
                        bloc_4.generer_bloc_4(factuel, appeler=appeler, **arguments), appel, journal=journal)
                    diagnostic = resultat["diagnostic"]
                    ecrire_json(dossier, "memoire_brute_bloc_4.json", resultat["memoire_brute"])
                    ecrire_json(dossier, "diagnostic_bloc_4.json", diagnostic)
                    ecrire_json(dossier, "periodes_bloc_4.json", resultat.get("periodes", []))
                    ecrire_json(dossier, "periodes_brutes_bloc_4.json", resultat.get("periodes_brutes", []))
                    ecrire_json(dossier, "proprietaires_faits_bloc_4.json",
                        {**precedents, **{cle: 4 for cle in diagnostic["transits_utilises"]}})
                    ecrire_json(dossier, "memoire_cumulative.json",
                        cumuler_memoires(memoires, 4, resultat["memoire"]))
                    ecrire_json(dossier / "bloc_4", "controle.json",
                        {"statut": "a_relire", "mode": diagnostic["mode_controle"], "validation_humaine": False})
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_4_a_relire", "rapport_complet": False, "validation_humaine": False})
                    _notifier(journal, "diagnostic_bloc_4", diagnostic=diagnostic)
                    print("\nBLOC 4 TERMINÉ — retour au parcours complet." if sur_dossier else
                          "\nBLOC 4 TERMINÉ — aucune conclusion lancée.")
                except KeyboardInterrupt:
                    print("\nARRÊT MANUEL — réponses conservées, aucune relance.")
                    code_retour = 130
                except Exception as exc:
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Aucun appel supplémentaire ; les éléments reçus restent archivés.")
                    code_retour = 1
                finally:
                    try:
                        lecture = rendre_bloc_4(dossier)
                        if lecture:
                            print("Lecture :", lecture)
                            print("Markdown :", dossier / "bloc_4.md")
                            print("Mémoire :", dossier / "memoire_bloc_4.json")
                    except Exception as exc:
                        print("Export interrompu :", type(exc).__name__, "—", exc)
                        print("Réponse brute conservée dans", dossier / "bloc_4")
                        code_retour = 1
                    print("Journal :", dossier / "terminal.log")
                return code_retour
