"""Calculs, plan commun, cinq blocs conservés, puis PDF ; aucun appel à l'import."""

import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..connaissances import empreinte_connaissances
from ..dossier import VERSION as VERSION_CALCULS, calculer_dossier_factuel_rs, controler_completude_dossier
from ..terminal import Tee
from .execution import lancer_bloc_1
from .execution_bloc_2 import lancer_bloc_2
from .execution_bloc_3 import lancer_bloc_3
from .execution_bloc_4 import lancer_bloc_4
from .execution_bloc_5 import lancer_bloc_5
from .export_pdf import exporter_pdf, verifier_export_pdf
from .execution_plan import lancer_plan
from .plan_partage import bilan_couverture


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/complets"
VERSION = "rs_v2_plan_commun_cinq_blocs_pdf_2"
FONCTIONS = (lancer_bloc_1, lancer_bloc_2, lancer_bloc_3, lancer_bloc_4, lancer_bloc_5)
PARAMETRES_SOURCES = ("source_factuel", "source_bloc_1", "source_bloc_2", "source_bloc_3", "source_bloc_4")


def empreintes_code():
    fichiers = list(Path(__file__).parent.glob("*.py")) + list(Path(__file__).parent.glob("*.txt"))
    fichiers += [ROOT / "utils/revolution_solaire/rapport_pdf.py", ROOT / "utils/revolution_solaire/rapport_html.py",
                 ROOT / "utils/pdf_utils.py"]
    fichiers += list((ROOT / "utils/revolution_solaire/v2").glob("*.py"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(fichiers)}


def preparer_calculs(cas):
    """Dossier indépendant du contexte client, réutilisé à profil et version identiques."""
    demande = {"version_calculs": VERSION_CALCULS, "raffiner_transits": True,
               **{k: cas[k] for k in ("personne", "lieu_rs", "annee")}}
    # Conserver les dépendances de calcul dans l'identité, même sans changement de VERSION.
    demande["code_calculs"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "utils/revolution_solaire").rglob("*.py"))
        if "blocs" not in p.parts and "__pycache__" not in p.parts}
    with verrou_demande(demande, SORTIES / "calculs") as dossier:
        factuel = lire_json(dossier, "dossier_factuel.json")
        if factuel is None:
            print("CALCULS — natal, RS, profection et transits annuels. Aucun appel IA.", flush=True)
            factuel = calculer_dossier_factuel_rs(personne=cas["personne"], lieu_rs=cas["lieu_rs"],
                                                 annee=cas["annee"], raffiner_transits=True)
            ecrire_json(dossier, "dossier_factuel.json", factuel)
        else:
            print("CALCULS ARCHIVÉS — même profil et même code ; aucun recalcul.")
        controle = controler_completude_dossier(factuel)
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "controle.json", controle)
        print("Dossier factuel :", dossier / "dossier_factuel.json")
        return dossier, factuel


def bilan_appels(sources, nouveaux):
    lignes = []
    totaux = {}
    for nom, chemin in sources.items():
        budget = lire_json(chemin, "budget_ia.json") or {}
        usages = {}
        for appel in budget.get("appels", []):
            for cle, valeur in appel.get("usage_tokens", {}).items():
                if isinstance(valeur, int) and not isinstance(valeur, bool):
                    usages[cle] = usages.get(cle, 0) + valeur
                    totaux[cle] = totaux.get(cle, 0) + valeur
        lignes.append({"bloc": nom, "archives": str(chemin), "nouveaux_appels_ce_lancement": nouveaux.get(nom, 0),
                       "tentatives_archivees": len(budget.get("appels", [])) + budget.get("tentatives_anterieures", 0),
                       "tokens_archives": usages})
    return {"blocs": lignes, "nouveaux_appels_ce_lancement": sum(nouveaux.values()),
            "tokens_archives_total": totaux, "plafond_parcours": 6,
            "nature": "Tokens réellement archivés ; une étape reprise en cache ne refacture pas sa réponse."}


def lancer_rapport_complet(cas_a_tester, *, modele="claude-sonnet-5", utiliser_bdd=True, reprendre_bloc_1=None):
    """Une commande : un plan puis cinq blocs, six appels au plus, aucune réécriture finale."""
    if len(cas_a_tester) != 1:
        raise ValueError("Le lanceur complet attend un profil unique.")
    if not isinstance(utiliser_bdd, bool):
        raise ValueError("utiliser_bdd doit être True ou False.")
    cas = cas_a_tester[0]
    if not isinstance(cas.get("contexte_client", {}), dict):
        raise ValueError("contexte_client doit être un dictionnaire.")
    demande = {"version": VERSION, "modele": modele, "profil": cas, "utiliser_bdd": utiliser_bdd,
               "code": empreintes_code(),
               "connaissances": empreinte_connaissances() if utiliser_bdd else None}
    if reprendre_bloc_1 is not None:
        demande["reprendre_bloc_1"] = str((ROOT / reprendre_bloc_1).expanduser().resolve())
    sorties = SORTIES if utiliser_bdd else SORTIES / "sans_bdd"
    with verrou_demande(demande, sorties) as dossier:
        ecrire_json(dossier, "demande.json", demande)
        # Conserver le code complet, y compris l'orchestrateur et l'export PDF.
        snapshots = dossier / "versions_code"
        for relatif in demande["code"]:
            destination = snapshots / relatif
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relatif, destination)
        sources, nouveaux = {}, {}
        source = None
        code_retour = 0
        with (dossier / "terminal.log").open("a", encoding="utf-8") as log:
            with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
                print("RS V2 — RAPPORT COMPLET —", cas["personne"]["nom"], cas["annee"])
                print("Dossier local :", ROOT)
                print("Archives du parcours :", dossier)
                print("Modèle :", modele)
                print("BDD :", "activée" if utiliser_bdd else "DÉSACTIVÉE — comparaison sans fiches d'interprétation")
                if reprendre_bloc_1 is not None:
                    print("Reprise demandée du bloc 1 après erreur réseau ; ancienne tentative conservée :", reprendre_bloc_1)
                print("Calculs → plan commun → Ascendant/profection → Soleil/Lune → MC/compléments → transits → conclusion → PDF")
                print("Au plus six appels Claude : un plan et cinq blocs. Aucune pause, réécriture finale ou relance automatique.")
                try:
                    verifier_export_pdf()
                    print("Export PDF du site disponible ; aucun PDF créé à cette étape.")
                    source, factuel = preparer_calculs(cas)
                    ecrire_json(dossier, "dossier_factuel.json", factuel)
                    capture_plan = {}

                    def recevoir_plan(chemin):
                        capture_plan["chemin"] = chemin
                        sources["plan_initial"] = chemin
                        budget = lire_json(chemin, "budget_ia.json") or {}
                        capture_plan["appels_avant"] = len(budget.get("appels", []))
                        ecrire_json(dossier, "sources_blocs.json", {k: str(v) for k, v in sources.items()})

                    ecrire_json(dossier, "etat.json", {"statut": "en_cours", "etape": "plan_initial", "validation_humaine": False})
                    try:
                        code = lancer_plan([cas], source_factuel=source, modele=modele, sur_dossier=recevoir_plan)
                    finally:
                        if "chemin" in capture_plan:
                            budget = lire_json(capture_plan["chemin"], "budget_ia.json") or {}
                            nouveaux["plan_initial"] = max(0, len(budget.get("appels", [])) - capture_plan["appels_avant"])
                            ecrire_json(dossier, "bilan_appels.json", bilan_appels(sources, nouveaux))
                    if code == 130:
                        raise KeyboardInterrupt
                    if code != 0 or "chemin" not in capture_plan:
                        raise RuntimeError("Le plan n'a pas terminé : les éléments reçus sont conservés, aucun bloc suivant lancé.")
                    plan = lire_json(capture_plan["chemin"], "plan_commun.json")
                    if not isinstance(plan, dict) or not plan.get("fils"):
                        raise RuntimeError("Aucun plan utilisable archivé ; aucun appel de rédaction lancé.")
                    ecrire_json(dossier, "plan_commun.json", plan)
                    suivis = {}
                    for numero, fonction in enumerate(FONCTIONS, 1):
                        nom = f"bloc_{numero}"
                        capture = {}

                        def recevoir_dossier(chemin):
                            capture["chemin"] = chemin
                            sources[nom] = chemin
                            budget = lire_json(chemin, "budget_ia.json") or {}
                            capture["appels_avant"] = len(budget.get("appels", []))
                            ecrire_json(dossier, "sources_blocs.json", {k: str(v) for k, v in sources.items()})

                        print(f"\nPARCOURS COMPLET — BLOC {numero}/5", flush=True)
                        ecrire_json(dossier, "etat.json", {"statut": "en_cours", "bloc": numero, "validation_humaine": False})
                        try:
                            options_bdd = {"utiliser_bdd": False} if not utiliser_bdd and numero <= 3 else {}
                            options_reprise = {"reprendre_apres_erreur": reprendre_bloc_1} if numero == 1 and reprendre_bloc_1 is not None else {}
                            code = fonction([cas], modele=modele, sur_dossier=recevoir_dossier,
                                            plan={**plan, "suivi_blocs_precedents": dict(suivis)},
                                            **options_bdd,
                                            **options_reprise,
                                            **{PARAMETRES_SOURCES[numero - 1]: source})
                        finally:
                            if "chemin" in capture:
                                budget = lire_json(capture["chemin"], "budget_ia.json") or {}
                                nouveaux[nom] = max(0, len(budget.get("appels", [])) - capture["appels_avant"])
                                ecrire_json(dossier, "bilan_appels.json", bilan_appels(sources, nouveaux))
                        if code != 0:
                            code_retour = code
                            if code == 130:
                                raise KeyboardInterrupt
                            raise RuntimeError(f"Le bloc {numero} n'a pas terminé. Sa réponse reste archivée ; aucune suite ni relance automatique.")
                        if "chemin" not in capture:
                            raise RuntimeError("Le bloc n'a pas fourni son dossier de sortie.")
                        source = capture["chemin"]
                        resultat = lire_json(source / nom, "resultat.json") or {}
                        suivis[nom] = resultat.get("fils_servis", [])
                        ecrire_json(dossier, "couverture_plan.json", bilan_couverture(plan, suivis))
                        texte = resultat.get("texte")
                        if not isinstance(texte, str) or not texte.strip():
                            raise RuntimeError(f"Texte du bloc {numero} absent : les résultats reçus sont conservés.")
                    assemblage = lire_json(source, "etat_assemblage.json") or {}
                    if not assemblage.get("conclusion_complete"):
                        raise RuntimeError("Conclusion incomplète ; aucun PDF complet exporté.")
                    for extension in ("md", "html"):
                        shutil.copy2(source / f"rapport_complet_assemble.{extension}", dossier / f"rapport_complet.{extension}")
                    pdf = exporter_pdf(dossier / "rapport_complet.html", dossier / "rapport_rs_v2.pdf",
                                       personne=cas["personne"], lieu_rs=cas["lieu_rs"], annee=cas["annee"])
                    bilan = bilan_appels(sources, nouveaux)
                    couverture = bilan_couverture(plan, suivis)
                    for alerte in couverture["alertes"]:
                        print("À RELIRE —", alerte)
                    print("Couverture du plan :", dossier / "couverture_plan.json")
                    ecrire_json(dossier, "bilan_appels.json", bilan)
                    ecrire_json(dossier, "etat.json", {"statut": "rapport_complet_a_relire", "pdf": str(pdf),
                                                       "validation_humaine": False, "livraison_validee": False})
                    print("\nRAPPORT COMPLET TERMINÉ — à relire.")
                    print("PDF :", pdf)
                    print("HTML :", dossier / "rapport_complet.html")
                    print("Markdown :", dossier / "rapport_complet.md")
                    print("Bilan des appels et tokens :", json.dumps(bilan, ensure_ascii=False, indent=2))
                except KeyboardInterrupt:
                    code_retour = 130
                    ecrire_json(dossier, "etat.json", {"statut": "arret_manuel", "validation_humaine": False})
                    print("\nARRÊT MANUEL — résultats conservés ; aucune relance.")
                except Exception as exc:
                    code_retour = code_retour or 1
                    ecrire_json(dossier, "etat.json", {"statut": "interrompu", "type_erreur": type(exc).__name__,
                                                       "validation_humaine": False})
                    print("\nARRÊT :", type(exc).__name__, "—", exc)
                    print("Les textes et réponses reçus restent dans leurs archives. Aucun appel supplémentaire.")
                finally:
                    print("Journal complet :", dossier / "terminal.log")
        return code_retour
