"""Conclusion seule, puis assemblage local des cinq textes conservés."""

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
from . import bloc_5
from .bloc_1 import nettoyer_parasites
from .plan_partage import reprendre_plan


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2" / "par_blocs" / "bloc_5"
INTRODUCTION_RAPPORT = (
    "Une révolution solaire dessine une ambiance d’année. Plusieurs facteurs peuvent insister "
    "sur les mêmes sujets : ces convergences donnent du poids aux grands enjeux de la lecture. "
    "Tu retrouveras donc certains fils à différents endroits, avec un éclairage sur ta posture, "
    "tes besoins, tes projets ou les moments de l’année."
)


def charger_bloc_4_et_lectures(cas, chemin):
    """Suit les sources explicitement archivées ; ne génère aucun bloc précédent."""
    source = (ROOT / chemin).expanduser().resolve()
    factuel = lire_json(source, "dossier_factuel.json")
    memoires = lire_json(source, "memoire_cumulative.json")
    proprietaires = lire_json(source, "proprietaires_faits_bloc_4.json")
    periodes = lire_json(source, "periodes_bloc_4.json")
    if not all(isinstance(v, dict) for v in (factuel, memoires, proprietaires)) or not isinstance(periodes, list):
        raise ValueError("Bloc 4 incomplet : calculs, mémoires, propriétaires ou périodes absents. Aucun appel lancé.")
    if not all(isinstance(memoires.get(f"bloc_{n}"), dict) for n in range(1, 5)):
        raise ValueError("Les quatre mémoires sont nécessaires. Aucun appel lancé.")
    controler_completude_dossier(factuel)
    lectures, provenance = {}, {}
    courant = source
    for numero in range(4, 0, -1):
        demande = lire_json(courant, "demande.json")
        texte_path = courant / f"bloc_{numero}.md"
        if not isinstance(demande, dict) or not texte_path.is_file():
            raise ValueError(f"Texte ou provenance du bloc {numero} absent. Aucun appel lancé.")
        for champ in ("personne", "lieu_rs", "annee"):
            if demande.get("profil", {}).get(champ) != cas.get(champ):
                raise ValueError(f"Profil différent pour {champ} dans le bloc {numero}. Aucun appel lancé.")
        texte = texte_path.read_text(encoding="utf-8")
        lectures[f"bloc_{numero}"] = texte
        provenance[f"bloc_{numero}"] = {"chemin": str(texte_path), "version": demande.get("mode"),
            "sha256": hashlib.sha256(texte_path.read_bytes()).hexdigest(), "texte_recrit": False}
        if numero > 1:
            precedent = demande.get(f"source_bloc_{numero - 1}")
            if not isinstance(precedent, str) or not precedent:
                raise ValueError(f"Source du bloc {numero - 1} absente. Aucun appel lancé.")
            courant = (ROOT / precedent).expanduser().resolve()
    proprietaires = {cle: n for cle, n in proprietaires.items()
                     if cle in factuel["faits"] and fait_autorise(factuel["faits"][cle])}
    return factuel, memoires, periodes, proprietaires, lectures, provenance, source


def _html_lecture(titre, sections, *, note):
    """Chaque texte est rendu séparément, sans propagation d'une balise Markdown ouverte."""
    import markdown
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(titre)}</title><style>"
            "body{font:18px/1.7 system-ui;max-width:960px;margin:35px auto;padding:0 24px;background:#faf8f4;color:#27252e}"
            "h1,h2,h3{line-height:1.3}aside{padding:16px;background:#fff0d6}"
            "article{margin:36px 0}nav{display:flex;flex-wrap:wrap;gap:16px;margin:20px 0}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:24px 0}summary{cursor:pointer}"
            f"</style><body><aside>{escape(note)}</aside><h1>{escape(titre)}</h1>")
    for identifiant, texte in sections:
        html += f"<article id='{escape(identifiant, quote=True)}'>" + markdown.markdown(
            escape(texte, quote=False), extensions=["extra"]) + "</article>"
    return html + "</body></html>"


def rendre_bloc_5_et_rapport(dossier, lectures, cycle, *, conclusion_complete=False):
    """Exporte la conclusion et concatène les textes ; aucune réécriture des quatre sources."""
    partie = dossier / "bloc_5"
    reponse = lire_json(partie, "reponse.json") or lire_json(partie, "reponse_partielle.json")
    if reponse is None:
        return None
    traite = lire_json(partie, "resultat.json") or {}
    texte = traite.get("texte")
    if not isinstance(texte, str):
        try:
            from ..analyse import parser_json_reponse
            brut = parser_json_reponse(reponse["texte"])
            if isinstance(brut, dict):
                if "synthese_annuelle" in brut:
                    contexte = (lire_json(dossier, "donnees_envoyees_bloc_5.json") or {}).get("informations_personnelles_de_depart", {})
                    texte, _, _ = bloc_5.assembler_conclusion(brut, contexte)
                else:
                    texte = brut.get("texte")
            else:
                texte = None
        except Exception:
            texte = None
    if not isinstance(texte, str):
        texte = reponse["texte"]
    texte, _ = nettoyer_parasites(texte)
    (dossier / "bloc_5.md").write_text(texte, encoding="utf-8")
    diagnostic = traite.get("diagnostic", {})
    note_conclusion = ("Conclusion à relire. Les quatre premières lectures et la réponse brute restent conservées."
                       if conclusion_complete else
                       "Conclusion incomplète — rapport incomplet. Le texte reçu reste consultable ; aucune relance automatique.")
    html = _html_lecture("RS V2 — Conclusion" if conclusion_complete else "RS V2 — Conclusion incomplète",
        [("conclusion", texte)], note=note_conclusion)
    html = html.replace("</body>", "<details><summary>Diagnostic à relire</summary><pre>"
        + escape(json.dumps(diagnostic, ensure_ascii=False, indent=2)) + "</pre></details></body>")
    conclusion_path = dossier / "lecture_bloc_5.html"
    conclusion_path.write_text(html, encoding="utf-8")

    titre = f"Ta Révolution Solaire {cycle['debut_utc'][:4]}–{cycle['fin_utc'][:4]}"
    conclusion_md = "## Ce que cette année met en jeu pour toi\n\n" + texte
    if not conclusion_complete:
        conclusion_md = "**Conclusion incomplète — texte reçu conservé.**\n\n" + conclusion_md
    sections = ([("introduction", INTRODUCTION_RAPPORT)]
                + [(f"bloc_{n}", lectures[f"bloc_{n}"]) for n in range(1, 5)]
                + [("conclusion", conclusion_md)])
    # Le contenu des sources est repris littéralement, même si une correction
    # du moteur a été faite depuis. Cette copie n'est pas une validation client.
    rapport = "# " + titre + "\n\n" + "\n\n".join(t for _, t in sections)
    if not conclusion_complete:
        rapport = "**Rapport incomplet — la conclusion est incomplète.**\n\n" + rapport
    (dossier / "rapport_complet_assemble.md").write_text(rapport, encoding="utf-8")
    note_rapport = ("Rapport complet assemblé, à relire. Les textes conservés sont repris sans réécriture. Aucune validation de livraison."
                    if conclusion_complete else
                    "Conclusion incomplète — rapport incomplet. Les textes reçus sont conservés sans réécriture. Aucune validation de livraison.")
    rapport_html = _html_lecture(titre if conclusion_complete else "Rapport incomplet — " + titre,
        sections, note=note_rapport)
    rapport_path = dossier / "rapport_complet_assemble.html"
    rapport_path.write_text(rapport_html, encoding="utf-8")
    return conclusion_path, rapport_path


def lancer_bloc_5(cas_a_tester, *, source_bloc_4, modele="claude-sonnet-5", apercu=False, sur_dossier=None, plan=None):
    """Un appel maximum pour la conclusion ; assemblage sans autre appel IA."""
    from ..terminal import Tee, JournalTerminal, afficher_requete
    if len(cas_a_tester) != 1:
        raise ValueError("Le bloc 5 exige un profil unique.")
    cas = cas_a_tester[0]
    factuel, memoires, periodes, proprietaires, lectures, provenance, source = charger_bloc_4_et_lectures(cas, source_bloc_4)
    plan = reprendre_plan(source, plan, 4)
    contexte = cas.get("contexte_client", {})
    if not isinstance(contexte, dict):
        raise ValueError("contexte_client doit être un dictionnaire. Aucun appel lancé.")
    arguments = {"memoires": memoires, "periodes": periodes, "proprietaires": proprietaires,
                 "contexte_client": contexte, "genre": cas["personne"].get("genre", ""), "plan": plan}
    prompt, entree, ecartes, suivi_appuis = bloc_5.construire_prompt_bloc_5(factuel, **arguments)
    demande = {"mode": bloc_5.VERSION, "modele": modele,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_bloc_4": str(source), "contexte_client": contexte,
               "empreintes_source": {nom: hashlib.sha256((source / nom).read_bytes()).hexdigest()
                   for nom in ("dossier_factuel.json", "memoire_cumulative.json", "periodes_bloc_4.json", "proprietaires_faits_bloc_4.json")},
               "empreinte_prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}

    class JournalBloc5(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 5 — CONCLUSION PERSONNELLE\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse traitée — conclusion à relire ; aucune validation automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        if plan is not None:
            ecrire_json(dossier, "plan_commun.json", plan)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_5.json", entree)
        ecrire_json(dossier, "memoires_sources_blocs_1_2_3_4.json", memoires)
        ecrire_json(dossier, "elements_memoire_non_transmis.json", ecartes)
        ecrire_json(dossier, "suivi_appuis_memoires.json", suivi_appuis)
        ecrire_json(dossier, "sources_rapport.json", provenance)
        (dossier / "prompt_complet_bloc_5.txt").write_text(prompt, encoding="utf-8")
        # Une modification manuelle d'un texte source peut refaire l'assemblage
        # sans refacturer une conclusion identique. Les anciennes copies restent.
        cle_lectures = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        copies = dossier / "versions_lectures" / cle_lectures
        copies.mkdir(parents=True, exist_ok=True)
        for nom, texte in lectures.items():
            if not (copies / f"{nom}.md").exists():
                (copies / f"{nom}.md").write_text(texte, encoding="utf-8")
        ecrire_json(copies, "sources_rapport.json", provenance)
        sources = [Path(__file__).with_name("plan_partage.py"),
                   Path(__file__).with_name("prompt_plan_partage.txt"), Path(__file__), Path(bloc_5.__file__), bloc_5.PROMPT_PATH, bloc_5.REGLES_PATH,
                   Path(__file__).with_name("style_lecture.txt"), Path(__file__).with_name("bloc_1.py"),
                   Path(__file__).with_name("bloc_4.py"), Path(__file__).with_name("suivi_memoire.py"), Path(__file__).with_name("appuis_memoire.py"),
                   ROOT / "utils/revolution_solaire/v2/filtrage_aspects.py",
                   ROOT / "utils/revolution_solaire/v2/memoire_redaction.py"]
        empreinte = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()[:16]
        snapshots = dossier / "versions_code" / empreinte
        snapshots.mkdir(parents=True, exist_ok=True)
        for path in sources:
            if not (snapshots / path.name).exists():
                shutil.copy2(path, snapshots / path.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("RS V2 — BLOC 5 —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("Bloc 4 source :", source)
                print("Version du bloc 4 source :", provenance["bloc_4"]["version"])
                print("Sorties du bloc 5 :", dossier)
                print("Prompt complet :", dossier / "prompt_complet_bloc_5.txt")
                print("Contexte personnel utilisé :", ", ".join(contexte) or "aucun renseignement")
                print("Mémoires courtes uniquement ; les quatre textes complets ne sont pas envoyés à Claude.")
                print("Suivi des appuis :", json.dumps(suivi_appuis, ensure_ascii=False, indent=2))
                print("Un appel maximum pour la conclusion. Assemblage ensuite sans aucun appel supplémentaire.")
                print("Les textes précédents sont conservés, sans correction rétroactive ni validation de livraison.")
                if apercu:
                    options = options_claude_v2(modele, {"max_tokens": bloc_5.MAX_TOKENS, "temperature": 0.5,
                        "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": bloc_5.schema_bloc_5(plan=plan)})
                    afficher_requete(modele, prompt, options, apercu=True)
                    print("APERÇU GRATUIT TERMINÉ — aucun appel Claude, aucune conclusion générée.")
                    return 0
                journal = JournalBloc5(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                code_retour = 0
                conclusion_complete = False
                try:
                    resultat = _etape_archivee(dossier, "bloc_5", lambda appeler:
                        bloc_5.generer_bloc_5(factuel, appeler=appeler, **arguments), appel, journal=journal)
                    conclusion_complete = isinstance(resultat.get("texte"), str) and bool(resultat["texte"].strip())
                    diagnostic = resultat["diagnostic"]
                    ecrire_json(dossier, "diagnostic_bloc_5.json", diagnostic)
                    ecrire_json(dossier / "bloc_5", "controle.json", {"statut": "a_relire", "validation_humaine": False})
                    ecrire_json(dossier, "etat.json", {"statut": "conclusion_a_relire", "validation_humaine": False})
                    _notifier(journal, "diagnostic_bloc_5", diagnostic=diagnostic)
                    print("\nCONCLUSION TERMINÉE — assemblage local, aucun appel suivant.")
                except KeyboardInterrupt:
                    print("\nARRÊT MANUEL — réponses conservées, aucune relance.")
                    code_retour = 130
                except Exception as exc:
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Aucun appel supplémentaire ; les éléments reçus restent archivés.")
                    code_retour = 1
                finally:
                    try:
                        chemins = rendre_bloc_5_et_rapport(dossier, lectures, factuel["cycle"],
                                                          conclusion_complete=conclusion_complete)
                        if chemins:
                            conclusion, rapport = chemins
                            print("Conclusion :", conclusion)
                            print("Rapport complet assemblé :" if conclusion_complete else "Rapport incomplet :", rapport)
                            print("Markdown :", dossier / "rapport_complet_assemble.md")
                            ecrire_json(dossier, "etat_assemblage.json", {"rapport_complet": conclusion_complete,
                                "validation_humaine": False, "livraison_validee": False,
                                "sources": provenance, "conclusion_complete": conclusion_complete})
                    except Exception as exc:
                        print("Export interrompu :", type(exc).__name__, "—", exc)
                        print("Réponse brute conservée dans", dossier / "bloc_5")
                        code_retour = 1
                    print("Journal :", dossier / "terminal.log")
                return code_retour
