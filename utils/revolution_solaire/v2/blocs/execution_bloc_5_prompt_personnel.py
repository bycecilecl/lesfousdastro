"""Conclusion avec le prompt validé, puis assemblage littéral des cinq blocs."""

import contextlib
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import unicodedata

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..analyse import parser_json_reponse
from ..filtrage_aspects import fait_autorise
from ..service import _etape_archivee, _fournisseur_borne, options_claude_v2
from ..terminal import JournalTerminal, Tee, afficher_requete
from . import bloc_1, bloc_4, bloc_5
from .execution import ROOT, _source
from .execution_bloc_5 import INTRODUCTION_RAPPORT, _html_lecture
from .execution_prompt_personnel import MODELE
from .export_pdf import CSS_HIERARCHIE_BLOCS
from .presentation_faits import compacter_faits


PROMPT_PATH = Path(__file__).with_name("prompt_bloc_5_essai_personnel.txt")
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/essai_prompt_personnel/bloc_5"
TITRES_BLOCS = {1: "Cap sur l’année", 2: "Soleil et Lune", 3: "Les autres grands enjeux",
                4: "Les périodes planétaires", 5: "Bilan"}
TITRES_SIX_BLOCS = {1: "Cap sur l’année", 2: "Soleil et Lune", 3: "Ta place, ton foyer et tes relations",
                    4: "Les autres grands enjeux", 5: "Les périodes planétaires", 6: "Bilan"}


def selectionner_conjonctions_noeuds_bloc_5(catalogue):
    """Contacts déjà calculés, Nœud/planète RS–natal, à 3° maximum."""
    noeuds = {"Rahu", "Ketu"}
    planetes = {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter",
                "Saturne", "Uranus", "Neptune", "Pluton"}
    retenus = {}
    for cle, fait in catalogue.items():
        if fait.get("type") != "contact":
            continue
        valeur = fait.get("valeur", {})
        point_rs, point_natal = valeur.get("point_rs"), valeur.get("point_natal")
        if not ((point_rs in noeuds and point_natal in planetes)
                or (point_rs in planetes and point_natal in noeuds)):
            continue
        orbe = valeur.get("orbe")
        if (str(valeur.get("aspect", "")).casefold() != "conjonction"
                or not isinstance(orbe, (int, float)) or not 0 <= orbe <= 3):
            continue
        retenus[cle] = fait
        for cadre, point in (("RS", point_rs), ("NATAL", point_natal)):
            position = f"{cadre}.positions.{point}"
            if position in catalogue:
                retenus[position] = catalogue[position]
    return retenus


def formater_titres_bloc(texte, numero, *, nombre_blocs=5):
    """Change uniquement les lignes de titres, dans la copie destinée à l'assemblage."""
    def normaliser(titre):
        titre = unicodedata.normalize("NFD", titre.lower().replace("’", "'"))
        return "".join(c for c in titre if unicodedata.category(c) != "Mn").strip()

    doublons = {1: {"cap sur ton annee", "cap sur l'annee"},
                2: {"soleil et lune", "soleil - lune", "soleil – lune"},
                3: {"les autres grands enjeux", "direction professionnelle et domaines mis en exergue"},
                4: {"les periodes de ton annee", "les periodes planetaires", "periodes planetaires"},
                5: {"bilan"}}
    titres = TITRES_BLOCS
    if nombre_blocs == 6:
        titres = TITRES_SIX_BLOCS
        doublons = {1: doublons[1], 2: doublons[2],
                    3: {"ta place, ton foyer et tes relations", "mc, fc et descendant", "les angles de l'annee"},
                    4: doublons[3], 5: doublons[4], 6: doublons[5]}
    lignes, cloture_code, mc_renomme = [], None, False
    for ligne in texte.splitlines(keepends=True):
        cloture = re.match(r"^\s*(`{3,}|~{3,})", ligne)
        if cloture:
            marqueur = cloture.group(1)
            if cloture_code is None:
                cloture_code = marqueur
            elif marqueur[0] == cloture_code[0] and len(marqueur) >= len(cloture_code):
                cloture_code = None
            lignes.append(ligne)
            continue
        titre = None if cloture_code else re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", ligne.rstrip("\r\n"))
        if not titre:
            lignes.append(ligne)
            continue
        libelle = titre.group(1)
        cle = normaliser(libelle)
        if cle in doublons[numero]:
            continue
        if numero == 2:
            if re.match(r"^soleil\s*[:–—-]", cle):
                libelle = "Soleil"
            elif re.match(r"^lune\s*[:–—-]", cle):
                libelle = "Lune"
            elif ("comparaison" in cle or "dialogue" in cle) and "soleil" in cle and "lune" in cle:
                libelle = "Leur dialogue"
        elif nombre_blocs == 5 and numero == 3 and not mc_renomme and re.match(r"^(?:ta direction pro\b|le mc\b|le milieu du ciel\b)", cle):
            libelle, mc_renomme = "Le MC et son maître", True
        elif numero == nombre_blocs and cle in {"bilan general", "bilan personnalise"}:
            libelle = "Bilan général" if cle == "bilan general" else "Bilan personnalisé"
        fin = "\r\n" if ligne.endswith("\r\n") else "\n" if ligne.endswith("\n") else ""
        lignes.append("### " + libelle + fin)
    return "## " + titres[numero] + "\n\n" + "".join(lignes)


def charger_lectures(cas, source_bloc_4, *, source_bloc_3=None):
    """Suit la chaîne précise des archives ; aucune recherche par date ni régénération."""
    courant = (ROOT / source_bloc_4).expanduser().resolve()
    lectures, provenance = {}, {}
    for n in range(4, 0, -1):
        demande = lire_json(courant, "demande.json")
        texte = courant / f"bloc_{n}.md"
        if not isinstance(demande, dict) or not texte.is_file():
            raise ValueError(f"Texte ou provenance du bloc {n} absent. Aucun appel lancé.")
        if demande.get("profil") != {k: cas[k] for k in ("personne", "lieu_rs", "annee")}:
            raise ValueError(f"Profil différent dans le bloc {n}. Aucun appel lancé.")
        lectures[f"bloc_{n}"] = texte.read_text(encoding="utf-8")
        provenance[f"bloc_{n}"] = {"chemin": str(texte),
            "sha256": hashlib.sha256(texte.read_bytes()).hexdigest(), "texte_recrit": False}
        if n > 1:
            precedent = demande.get(f"source_bloc_{n - 1}")
            if not isinstance(precedent, str) or not precedent:
                raise ValueError(f"Source du bloc {n - 1} absente. Aucun appel lancé.")
            if n == 4 and source_bloc_3 is not None:
                ancien = lire_json((ROOT / precedent).expanduser().resolve(), "demande.json")
                remplacement = (ROOT / source_bloc_3).expanduser().resolve()
                nouveau = lire_json(remplacement, "demande.json")
                if (not isinstance(ancien, dict) or not isinstance(nouveau, dict)
                        or any(not ancien.get(k) or ancien[k] != nouveau.get(k)
                               for k in ("source_bloc_2", "empreinte_faits"))):
                    raise ValueError("Le nouveau bloc 3 doit reprendre le même bloc 2 et les mêmes calculs. Aucun appel lancé.")
                precedent = str(remplacement)
            courant = (ROOT / precedent).expanduser().resolve()
    return lectures, provenance


def references_memoire(objet, catalogue):
    """Références explicites uniquement ; aucun appui inféré depuis un résumé."""
    if isinstance(objet, str):
        return {objet} if objet in catalogue and fait_autorise(catalogue[objet]) else set()
    if isinstance(objet, dict):
        valeurs = objet.values()
    elif isinstance(objet, list):
        valeurs = objet
    else:
        return set()
    refs = set()
    for valeur in valeurs:
        refs.update(references_memoire(valeur, catalogue))
    return refs


def assembler_rapport(dossier, lectures, conclusion, cycle, *, nombre_blocs=5):
    """Conserve les textes : pas de correction de style ni réécriture finale."""
    titre = f"Ta Révolution Solaire {cycle['debut_utc'][:4]}–{cycle['fin_utc'][:4]}"
    sections = [("introduction", INTRODUCTION_RAPPORT)]
    sections += [(f"bloc_{n}", formater_titres_bloc(lectures[f"bloc_{n}"], n, nombre_blocs=nombre_blocs))
                 for n in range(1, nombre_blocs)]
    sections.append(("conclusion", formater_titres_bloc(conclusion, nombre_blocs, nombre_blocs=nombre_blocs)))
    rapport = "# " + titre + "\n\n" + "\n\n".join(t for _, t in sections)
    (dossier / "rapport_complet_assemble.md").write_text(rapport, encoding="utf-8")
    html = _html_lecture(titre, sections,
        note="Rapport assemblé à relire. Paragraphes conservés ; seule la hiérarchie des titres est harmonisée. Aucune validation de livraison.")
    html = html.replace("</style>", '</style><style id="rs-v2-hierarchie">' + CSS_HIERARCHIE_BLOCS + "</style>", 1)
    (dossier / "rapport_complet_assemble.html").write_text(html, encoding="utf-8")


def lancer_bloc_5_prompt_personnel(cas_a_tester, *, source_bloc_4, apercu=False, sur_dossier=None, source_bloc_3=None):
    if len(cas_a_tester) != 1:
        raise ValueError("Un seul profil est attendu.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_bloc_4).expanduser().resolve()
    ancienne = lire_json(reference, "demande.json")
    memoires = lire_json(reference, "memoire_cumulative.json")
    if not isinstance(ancienne, dict) or not isinstance(memoires, dict):
        raise ValueError("Bloc 4 ou mémoire absent. Aucun appel lancé.")
    contexte = cas.get("contexte_client", {})
    if not isinstance(contexte, dict):
        raise ValueError("contexte_client doit être un dictionnaire.")
    lectures, provenance = charger_lectures(cas, reference, source_bloc_3=source_bloc_3)
    factuel, source = _source(cas, ancienne["source_factuel"])
    catalogue = factuel["faits"]
    refs = {cle for cle, f in catalogue.items() if fait_autorise(f)}
    appuis = references_memoire(memoires, catalogue)
    faits, roles = bloc_5.selectionner_reperes_bloc_5(factuel, refs, appuis_requis=appuis)
    for nom in ("Rahu", "Ketu"):
        cle = f"RS.positions.{nom}"
        if cle in catalogue and fait_autorise(catalogue[cle]):
            faits[cle] = catalogue[cle]
    faits.update(selectionner_conjonctions_noeuds_bloc_5(catalogue))
    entree = bloc_4.purger_donnees_bloc_4({
        "genre": {"female": "féminin", "male": "masculin"}.get(cas["personne"].get("genre", ""), ""),
        "memoire": {k: deepcopy(v) for k, v in memoires.items() if k != "bloc_4"},
        "reperes": {"faits_calcules": compacter_faits(faits), "roles_calcules": roles},
        "periodes": deepcopy(memoires.get("bloc_4", {})),
        "informations_personnelles": deepcopy(contexte),
    })
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    for cle in ("memoire", "reperes", "periodes", "informations_personnelles"):
        prompt = prompt.replace("{" + cle + "}", json.dumps(entree[cle], ensure_ascii=False, separators=(",", ":")))
    prompt += "\n\n" + json.dumps({"genre": entree["genre"]}, ensure_ascii=False, separators=(",", ":"))
    options = bloc_1.options_generation_bloc_1(reflexion="adaptive", niveau_effort="medium", max_tokens=8000)
    # L'objet des informations utilisées est libre dans le prompt de Cécile.
    options.pop("schema_sortie", None)
    demande = {"mode": "bloc_5_prompt_personnel_1", "modele": MODELE,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source), "source_bloc_4": str(reference),
               "contexte_client": deepcopy(contexte),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "reglages": {"reflexion": "adaptive", "niveau_effort": "medium", "max_tokens": 8000},
               "utiliser_bdd": False}
    if source_bloc_3 is not None:
        demande["source_bloc_3_reprise"] = str((ROOT / source_bloc_3).expanduser().resolve())

    class JournalBloc5(JournalTerminal):
        def __call__(self, evenement, **details):
            if evenement == "etape":
                self.partie = Path(details["dossier"])
                print("\nBLOC 5 — BILAN ET SITUATION PERSONNELLE\nArchives :", self.partie)
            elif evenement == "controle_valide":
                print("Réponse enregistrée ; conclusion à relire, aucune validation astrologique automatique.")
            else:
                super().__call__(evenement, **details)

    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", factuel)
        ecrire_json(dossier, "donnees_envoyees_bloc_5.json", entree)
        ecrire_json(dossier, "memoires_sources.json", memoires)
        ecrire_json(dossier, "sources_rapport.json", provenance)
        (dossier / "prompt_complet_bloc_5.txt").write_text(prompt, encoding="utf-8")
        snapshots = dossier / "versions_code"
        snapshots.mkdir(exist_ok=True)
        for p in (Path(__file__), PROMPT_PATH, Path(bloc_5.__file__), Path(bloc_4.__file__),
                  Path(__file__).with_name("presentation_faits.py")):
            if not (snapshots / p.name).exists():
                shutil.copy2(p, snapshots / p.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as fichier:
            with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
                print("Dossier local :", ROOT)
                print("Bloc 5 uniquement — un appel maximum, sans BDD, sans anciennes consignes.")
                print("Les quatre textes sont conservés pour l'assemblage ; seuls les résumés et repères sont envoyés.")
                print("Contexte personnel :", ", ".join(contexte) or "aucun renseignement")
                print("Prompt complet :", dossier / "prompt_complet_bloc_5.txt")
                if apercu:
                    afficher_requete(MODELE, prompt, options_claude_v2(MODELE, options), apercu=True)
                    print("APERÇU TERMINÉ — aucun appel Claude.")
                    return 0
                journal = JournalBloc5(modele=MODELE)
                appel = _fournisseur_borne(dossier, MODELE, 1, journal=journal)

                def generer(appeler):
                    resultat = parser_json_reponse(appeler(prompt, **options))
                    if not isinstance(resultat.get("synthese_annuelle"), str) or not resultat["synthese_annuelle"].strip():
                        raise ValueError("Bilan annuel absent ; réponse brute conservée.")
                    return resultat

                try:
                    resultat = _etape_archivee(dossier, "bloc_5", generer, appel, journal=journal)
                    bilan = resultat["synthese_annuelle"]
                    personnel = resultat.get("mise_en_perspective_personnelle")
                    personnel = personnel if isinstance(personnel, str) else ""
                    texte = "\n\n".join(p for p in (bilan, personnel) if p.strip())
                    (dossier / "bloc_5.md").write_text(texte, encoding="utf-8")
                    ecrire_json(dossier, "conclusion.json", resultat)
                    ecrire_json(dossier, "diagnostic_bloc_5.json", {
                        "mots_bilan": len(bilan.split()), "mots_personnel": len(personnel.split()),
                        "contexte_renseigne": bloc_5.contexte_renseigne(contexte),
                        "partie_personnelle_presente": bool(personnel.strip()), "validation_humaine": False})
                    html = _html_lecture("RS — Bilan de l’année", [("conclusion", texte)],
                        note="Conclusion reçue, à relire ; texte conservé sans réécriture.")
                    (dossier / "lecture_bloc_5.html").write_text(html, encoding="utf-8")
                    assembler_rapport(dossier, lectures, texte, factuel["cycle"])
                    ecrire_json(dossier, "etat.json", {"statut": "bloc_5_et_assemblage_a_relire", "validation_humaine": False})
                    print("\nBLOC 5 TERMINÉ — assemblage sans appel supplémentaire.")
                    if bloc_5.contexte_renseigne(contexte) and not personnel.strip():
                        print("À RELIRE — le bilan personnel demandé est absent du texte reçu.")
                    print("Conclusion :", dossier / "lecture_bloc_5.html")
                    print("Rapport assemblé :", dossier / "rapport_complet_assemble.html")
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
