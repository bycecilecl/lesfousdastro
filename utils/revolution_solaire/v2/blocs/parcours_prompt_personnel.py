"""Six parties : MC/FC/Descendant puis grands enjeux, sans plan IA."""

import contextlib
from functools import partial
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..terminal import Tee
from .execution import ROOT
from .execution_prompt_personnel import MODELE, lancer_essai_prompt_personnel
from .execution_bloc_2_prompt_personnel import lancer_bloc_2_prompt_personnel
from .execution_six_parties import lancer_partie
from .export_pdf import exporter_pdf, verifier_export_pdf
from .parcours_complet import bilan_appels, empreintes_code, preparer_calculs


SORTIES = ROOT / "rapports_test/revolution_solaire_v2/complets/prompts_personnels"
FONCTIONS = (lancer_essai_prompt_personnel, lancer_bloc_2_prompt_personnel,
             partial(lancer_partie, numero=3), partial(lancer_partie, numero=4),
             partial(lancer_partie, numero=5), partial(lancer_partie, numero=6))
PARAMETRES_SOURCES = ("source_factuel", "source_bloc_1", "source_precedente", "source_precedente",
                      "source_precedente", "source_precedente")


def bilan_six_blocs(sources, nouveaux):
    bilan = bilan_appels(sources, nouveaux)
    bilan["plafond_parcours"] = 6
    return bilan


def lancer_rapport_prompts_personnels(cas_a_tester, *, sur_dossier=None, identifiant_execution=None):
    """Une commande : six blocs au plus puis HTML, Markdown et PDF du site."""
    if len(cas_a_tester) != 1:
        raise ValueError("Le lanceur complet attend un profil unique.")
    cas = cas_a_tester[0]
    if not isinstance(cas.get("contexte_client", {}), dict):
        raise ValueError("contexte_client doit être un dictionnaire.")
    demande = {"version": "rs_v2_six_parties_mc_separe_1", "modele": MODELE,
               "profil": cas, "utiliser_bdd": False, "plan_ia": False, "code": empreintes_code()}
    if identifiant_execution:
        demande["identifiant_execution"] = identifiant_execution
    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        ecrire_json(dossier, "demande.json", demande)
        for relatif in demande["code"]:
            destination = dossier / "versions_code" / relatif
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relatif, destination)
        sources, nouveaux = {}, {}
        retour = 0
        with (dossier / "terminal.log").open("a", encoding="utf-8") as log:
            with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
                print("RS V2 — RAPPORT ENTIER EN SIX PARTIES —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("Archives du parcours :", dossier)
                print("Sonnet 5.5 — réflexion adaptative — effort moyen — sans BDD.")
                print("Calculs → Ascendant/profection → Soleil/Lune → MC/FC/Descendant → grands enjeux → périodes → bilan → HTML et PDF.")
                print("Au maximum six appels : aucun plan IA, aucune réécriture finale ni relance automatique.")
                print("Les réponses complètes déjà archivées pour la même demande sont réutilisées sans appel.")
                try:
                    verifier_export_pdf()
                    source, factuel = preparer_calculs(cas)
                    ecrire_json(dossier, "dossier_factuel.json", factuel)
                    for numero, fonction in enumerate(FONCTIONS, 1):
                        nom = f"bloc_{numero}"
                        capture = {}

                        def recevoir_dossier(chemin):
                            capture["chemin"] = Path(chemin)
                            sources[nom] = Path(chemin)
                            budget = lire_json(chemin, "budget_ia.json") or {}
                            capture["appels_avant"] = len(budget.get("appels", []))
                            ecrire_json(dossier, "sources_blocs.json", {k: str(v) for k, v in sources.items()})

                        print(f"\nRAPPORT ENTIER — BLOC {numero}/6", flush=True)
                        ecrire_json(dossier, "etat.json", {"statut": "en_cours", "bloc": numero, "validation_humaine": False})
                        options = {PARAMETRES_SOURCES[numero - 1]: source, "sur_dossier": recevoir_dossier}
                        if numero == 1:
                            options["version_prompt"] = 2
                        try:
                            code = fonction([cas], **options)
                        finally:
                            if "chemin" in capture:
                                budget = lire_json(capture["chemin"], "budget_ia.json") or {}
                                nouveaux[nom] = max(0, len(budget.get("appels", [])) - capture["appels_avant"])
                                ecrire_json(dossier, "bilan_appels.json", bilan_six_blocs(sources, nouveaux))
                        if code == 130:
                            raise KeyboardInterrupt
                        if code != 0 or "chemin" not in capture:
                            raise RuntimeError(f"Le bloc {numero} n'a pas terminé ; ses éléments sont conservés. Aucune relance automatique.")
                        source = capture["chemin"]
                        texte = source / f"bloc_{numero}.md"
                        if not texte.is_file() or not texte.read_text(encoding="utf-8").strip():
                            raise RuntimeError(f"Texte du bloc {numero} absent ; les réponses restent archivées.")
                        shutil.copy2(texte, dossier / texte.name)
                    for extension in ("md", "html"):
                        shutil.copy2(source / f"rapport_complet_assemble.{extension}", dossier / f"rapport_complet.{extension}")
                    pdf = exporter_pdf(dossier / "rapport_complet.html", dossier / "rapport_rs_v2.pdf",
                        personne=cas["personne"], lieu_rs=cas["lieu_rs"], annee=cas["annee"])
                    bilan = bilan_six_blocs(sources, nouveaux)
                    ecrire_json(dossier, "bilan_appels.json", bilan)
                    ecrire_json(dossier, "etat.json", {"statut": "rapport_assemble_a_relire", "pdf": str(pdf),
                        "validation_humaine": False, "livraison_validee": False})
                    print("\nRAPPORT ENTIER ASSEMBLÉ — à relire.")
                    print("PDF avec disclaimer :", pdf)
                    print("HTML :", dossier / "rapport_complet.html")
                    print("Markdown :", dossier / "rapport_complet.md")
                    print("Nouveaux appels pendant ce lancement :", bilan["nouveaux_appels_ce_lancement"])
                    print("Bilan des appels et tokens :", dossier / "bilan_appels.json")
                except KeyboardInterrupt:
                    retour = 130
                    ecrire_json(dossier, "etat.json", {"statut": "arret_manuel", "validation_humaine": False})
                    print("ARRÊT MANUEL — textes et réponses conservés ; aucune relance.")
                except Exception as exc:
                    retour = 1
                    ecrire_json(dossier, "etat.json", {"statut": "interrompu", "type_erreur": type(exc).__name__,
                        "validation_humaine": False})
                    print("ARRÊT :", type(exc).__name__, "—", exc)
                    print("Les textes et réponses restent dans leurs archives. Aucun appel supplémentaire.")
                finally:
                    print("Journal complet :", dossier / "terminal.log")
        return retour
