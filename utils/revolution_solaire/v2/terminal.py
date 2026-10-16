"""Affichage et archivage des essais V2 ; utilisé par le lanceur simple."""

import argparse
import contextlib
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

from utils.revolution_solaire.v2 import analyse
from utils.revolution_solaire.v2.service import (
    AppelAnnuleAvantEnvoi, generer_rapport_rs_v2, options_claude_v2,
)
from .essai_etape2 import preparer_essai_etape2, generer_essai_isole
from .essai_etape3 import preparer_essai_etape3, preparer_essai_etape4, preparer_essai_etape5
from .essai_etape6 import preparer_essai_etape6
from .essai_redaction import preparer_redaction_archivee, generer_redaction_archivee


# ===================== TA CONFIGURATION =====================
GENERER_CLAUDE = False  # ou utilise --generer dans le terminal
MODELE_CLAUDE = "claude-sonnet-5"
APPELS_MAX = 8  # plafond TOTAL par dossier, reprises comprises
CAS_A_TESTER = []
# =================== FIN DE CONFIGURATION ===================

ROOT = Path(__file__).resolve().parents[3]
SORTIES = ROOT / "rapports_test" / "revolution_solaire_v2"
ORDRE = (*analyse.ETAPES, "redaction_corps", "conclusion_contextuelle")


class Tee:
    """Affiche immédiatement et conserve le même texte dans terminal.log."""
    def __init__(self, terminal, fichier):
        self.terminal, self.fichier = terminal, fichier

    def write(self, texte):
        self.terminal.write(texte)
        self.fichier.write(texte)
        self.flush()
        return len(texte)

    def flush(self):
        self.terminal.flush()
        self.fichier.flush()


def afficher_requete(modele, prompt, parametres, *, apercu=False):
    print("\n" + "=" * 78)
    print("APERÇU — AUCUN ENVOI" if apercu else "REQUÊTE CLAUDE — AVANT ENVOI")
    print(f"Modèle : {modele} | Prompt : {len(prompt)} caractères")
    print("PARAMÈTRES API COMPLETS (schéma de sortie compris) :")
    print(json.dumps({"model": modele, **parametres}, ensure_ascii=False, indent=2))
    print("MESSAGES : un message user, affiché ci-dessous. Aucun prompt system ajouté.")
    print("Transport : streaming ; max_retries=0 (aucune relance du SDK).")
    print("DÉBUT DU PROMPT COMPLET")
    print(prompt)
    print("FIN DU PROMPT COMPLET")
    print("=" * 78, flush=True)


class JournalTerminal:
    def __init__(self, *, modele, pas_a_pas=False):
        self.modele, self.pas_a_pas = modele, pas_a_pas
        self.partie = None

    def __call__(self, evenement, **details):
        if evenement == "etape":
            nom = details["nom"]
            self.partie = Path(details["dossier"])
            print(f"\nÉTAPE {ORDRE.index(nom) + 1}/8 : {nom}")
            print(f"Archives : {self.partie}")
        elif evenement == "requete":
            afficher_requete(**details)
            # Copie exacte des arguments applicatifs du SDK, sans clé ni headers.
            requete = {"model": details["modele"], "messages": [
                {"role": "user", "content": details["prompt"]}], **details["parametres"]}
            if self.partie is not None:
                (self.partie / "requete_api.json").write_text(
                    json.dumps(requete, ensure_ascii=False, indent=2), encoding="utf-8")
            if self.pas_a_pas:
                try:
                    choix = input("Entrée = envoyer cet appel ; q = arrêter : ").strip().lower()
                except KeyboardInterrupt:
                    raise AppelAnnuleAvantEnvoi from None
                if choix:
                    raise AppelAnnuleAvantEnvoi
        elif evenement == "envoi":
            print(f"ENVOI CLAUDE : tentative {details['numero']} — {details['modele']}", flush=True)
            print("Attente de la réponse ; aucune relance automatique.", flush=True)
        elif evenement == "reponse":
            print("\nDÉBUT DE LA RÉPONSE BRUTE CLAUDE (avant les contrôles)")
            print(details["texte"])
            print("FIN DE LA RÉPONSE BRUTE CLAUDE")
            print("Arrêt :", details["statut"])
            print("Tokens réels :", json.dumps(details["usage"], ensure_ascii=False))
        elif evenement == "cache":
            print(f"RÉPONSE EN ARCHIVE ({details['source']}) : aucun nouvel appel.")
            original = details["prompt_archive"]
            if original:
                afficher_requete(self.modele, original["prompt"],
                                 options_claude_v2(self.modele, original.get("options", {})), apercu=True)
            print("RÉPONSE ARCHIVÉE :")
            print(details["texte"])
        elif evenement == "calculs":
            print("Calcul local : natal, RS, superpositions, profection et transits annuels…", flush=True)
            print("Dossier :", details["dossier"], flush=True)
        elif evenement == "dossier_factuel":
            print("Contrôle du dossier factuel :", json.dumps(details["controle"], ensure_ascii=False))
            print("Inventaire et dates :", Path(details["dossier"]) / "dossier_factuel.json")
        elif evenement == "controle_valide":
            print(f"CONTRÔLE STRUCTURE / PREUVES / LIENS : validé ({details['nom']})")
        elif evenement == "controle_placements":
            print(f"CONTRÔLE DES PLACEMENTS ({details['nom']}) :")
            print(json.dumps(details["controle"], ensure_ascii=False, indent=2))
        else:
            print(evenement.upper(), json.dumps(details, ensure_ascii=False, indent=2))
        sys.stdout.flush()


class ApercuTermine(Exception):
    pass


def apercu_rs_seule(factuel, modele, dossier):
    def apercu(prompt, **options):
        parametres = options_claude_v2(modele, options)
        afficher_requete(modele, prompt, parametres, apercu=True)
        (dossier / "apercu_rs_seule.json").write_text(json.dumps({
            "model": modele, "messages": [{"role": "user", "content": prompt}],
            **parametres}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ApercuTermine
    try:
        analyse.analyser_rs_seule(factuel, appeler=apercu)
    except ApercuTermine:
        pass
    print("\nLes prompts suivants dépendent des réponses précédentes : ils s'afficheront à leur étape.")


def empreintes_moteur():
    fichiers = sorted((ROOT / "utils/revolution_solaire/v2").glob("*.py"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in fichiers}


def executer(args, session, cas, modele, generer):
    print(f"\nRS V2 — {cas['personne']['nom']} — {cas['annee']}")
    print(f"Dossier local : {ROOT}\nSession : {session}\nJournal : {session / 'terminal.log'}")
    print(f"Modèle : {modele}\nGénération Claude : {'OUI' if generer else 'NON'}")
    print(f"Plafond total du dossier : {args.appels_max} tentatives (reprises comprises)")
    parcours = ORDRE[:ORDRE.index(args.etape) + 1] if generer and args.etape else ORDRE
    print("Parcours : " + " → ".join(parcours))
    journal = JournalTerminal(modele=modele, pas_a_pas=args.pas_a_pas)
    resultat = generer_rapport_rs_v2(
        **cas, stockage_dir=session / "etapes", preparation_seule=not generer,
        autoriser_generation=generer, arreter_apres=args.etape if generer else None,
        modele=modele, limite_appels_ia=args.appels_max, journal=journal)
    if not generer:
        apercu_rs_seule(resultat["donnees"], modele, session)
        print("\nPRÉPARATION TERMINÉE — zéro appel Claude.")
        print(f"Pour générer à partir de ces calculs :\n"
              f'env/bin/python -u -m utils.revolution_solaire.v2.terminal --generer --reprendre "{session}"')
    elif args.etape:
        print(f"\nArrêt demandé après {resultat['etape']}. Résultats : {resultat['dossier']}")
    else:
        print(f"\nRAPPORT ASSEMBLÉ ET CONTRÔLÉ :\n{resultat.dossier_generation}/rapport.html")
        print(f"Texte : {resultat.dossier_generation}/rapport.md")


def main(argv=None, *, cas_a_tester=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--generer", action="store_true", help="Tu déclenches les appels Claude")
    mode.add_argument("--sans-claude", action="store_true", help="Calculs et aperçu du premier prompt uniquement")
    parser.add_argument("--cas", type=int, default=0, help="Index dans CAS_A_TESTER (premier : 0)")
    parser.add_argument("--modele", help="Modèle Claude ; défaut : MODELE_CLAUDE dans ce fichier")
    parser.add_argument("--appels-max", type=int, default=APPELS_MAX, help="Plafond total du dossier (défaut : 8)")
    parser.add_argument("--etape", choices=analyse.ETAPES, help="Arrête le parcours après cette analyse")
    parser.add_argument("--pas-a-pas", action="store_true", help="Attend Entrée après chaque prompt, avant l'envoi")
    parser.add_argument("--reprendre", type=Path, help="Dossier de session existant ; réponses reçues réutilisées")
    args = parser.parse_args(argv)
    if args.appels_max < 0:
        parser.error("--appels-max doit être positif ou nul")
    generer = args.generer or (GENERER_CLAUDE and not args.sans_claude)
    if args.reprendre:
        session = args.reprendre.expanduser().resolve()
        config = json.loads((session / "configuration.json").read_text(encoding="utf-8"))
        cas, modele = config["cas"], config["modele"]
        if args.modele and args.modele != modele:
            parser.error("Une reprise conserve le modèle initial. Lance une nouvelle session pour le changer.")
        if config["empreintes_moteur"] != empreintes_moteur():
            parser.error("Le moteur a changé depuis cet essai. Lance une nouvelle session sans --reprendre.")
    else:
        profils = CAS_A_TESTER if cas_a_tester is None else cas_a_tester
        if not 0 <= args.cas < len(profils):
            parser.error("--cas ne correspond pas à un profil dans CAS_A_TESTER")
        cas, modele = profils[args.cas], args.modele or MODELE_CLAUDE
        session = SORTIES / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
        session.mkdir(parents=True, mode=0o700)
        config = {"cas": cas, "modele": modele, "empreintes_moteur": empreintes_moteur()}
        (session / "configuration.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        sources = session / "sources_moteur"
        sources.mkdir()
        for relatif in config["empreintes_moteur"]:
            shutil.copy2(ROOT / relatif, sources / Path(relatif).name)
    with (session / "terminal.log").open("a", encoding="utf-8") as fichier:
        with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
            try:
                executer(args, session, cas, modele, generer)
            except KeyboardInterrupt:
                print("\nARRÊT MANUEL. Aucune relance. Archives et journal conservés.")
                return 130
            except Exception as exc:
                print(f"\nARRÊT : {type(exc).__name__} — {exc}")
                print("Aucun appel supplémentaire ni réécriture automatique. Consulte les archives ci-dessus.")
                print(f"Journal : {session / 'terminal.log'}")
                return 1
    return 0


def lancer_essai_etape2_terminal(dossier_source, cas, modele):
    """Prépare et lance seulement l'appel 2 ; réutilise les fichiers de l'appel 1."""
    preparation = preparer_essai_etape2(ROOT / dossier_source)
    return lancer_essai_archive_terminal(preparation, cas, modele, "resonances_natales")


def lancer_essai_etape3_terminal(source_rs_seule, source_resonances, cas, modele):
    preparation = preparer_essai_etape3(ROOT / source_rs_seule, ROOT / source_resonances)
    return lancer_essai_archive_terminal(preparation, cas, modele, "contacts_rs_natal")


def lancer_essai_etape4_terminal(source_rs_seule, source_resonances, cas, modele):
    preparation = preparer_essai_etape4(ROOT / source_rs_seule, ROOT / source_resonances)
    return lancer_essai_archive_terminal(preparation, cas, modele, "superpositions_maisons")


def lancer_essai_etape5_terminal(source_rs_seule, source_resonances, cas, modele):
    preparation = preparer_essai_etape5(ROOT / source_rs_seule, ROOT / source_resonances)
    return lancer_essai_archive_terminal(preparation, cas, modele, "profection")


def lancer_essai_etape6_terminal(source_rs_seule, source_resonances, source_profection, cas, modele):
    preparation = preparer_essai_etape6(ROOT / source_rs_seule, ROOT / source_resonances, ROOT / source_profection)
    return lancer_essai_archive_terminal(preparation, cas, modele, "activations_annuelles")


def lancer_essai_archive_terminal(preparation, cas, modele, etape):
    """Terminal d'une seule étape, depuis des calculs et analyses déjà enregistrés."""
    numero = {"resonances_natales": 2, "contacts_rs_natal": 3, "superpositions_maisons": 4,
              "profection": 5, "activations_annuelles": 6}[etape]
    demande_source = preparation["demande_source"]
    for champ in ("personne", "lieu_rs", "annee"):
        if cas.get(champ) != demande_source.get(champ):
            raise ValueError("Le profil du lanceur diffère de l'archive pour " + champ
                             + ". Aucun appel Claude lancé.")
    cle = hashlib.sha256(json.dumps({"sources": preparation["provenance"], "modele": modele,
                                    "prompt": preparation["prompt"]},
                                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    session = SORTIES / (f"etape{numero}_" + cle[:16])
    session.mkdir(parents=True, exist_ok=True, mode=0o700)
    configuration = {"cas": cas, "modele": modele,
                     "source_rs_seule": preparation["provenance"]["dossier_source"],
                     "source_resonances_natales": preparation["provenance"].get("dossier_source_resonances"),
                     "source_profection": preparation["provenance"].get("dossier_source_profection"),
                     "empreintes_moteur": empreintes_moteur(), "mode": f"appel_{numero}_uniquement"}
    (session / "configuration.json").write_text(json.dumps(configuration, ensure_ascii=False, indent=2), encoding="utf-8")
    sources = session / "sources_moteur"
    sources.mkdir(exist_ok=True)
    for relatif in configuration["empreintes_moteur"]:
        shutil.copy2(ROOT / relatif, sources / Path(relatif).name)
    with (session / "terminal.log").open("a", encoding="utf-8") as fichier:
        with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
            print(f"\nRS V2 — {cas['personne']['nom']} — {cas['annee']}")
            print(f"Dossier local : {ROOT}\nSession : {session}\nJournal : {session / 'terminal.log'}")
            print(f"Parcours : {etape} uniquement. Plafond : un nouvel appel Claude.")
            print("Premier appel et calculs réutilisés depuis :", preparation["provenance"]["dossier_source"])
            if numero in {3, 4, 5, 6}:
                print("Deuxième appel réutilisé depuis :", preparation["provenance"]["dossier_source_resonances"])
            if numero == 4:
                print("Appel 3 non transmis : cet essai utilise uniquement les analyses 1 et 2.")
            elif numero == 5:
                print("Appels 3 et 4 non transmis : cet essai utilise uniquement les analyses 1 et 2.")
            elif numero == 6:
                print("Cinquième appel réutilisé depuis :", preparation["provenance"]["dossier_source_profection"])
                print("Appels 3 et 4 non transmis : cet essai utilise uniquement les analyses 1, 2 et 5.")
                print("Fenêtres de transit déjà calculées :", len(preparation["factuel"]["transits"]["evenements"]))
            print("Statuts des résultats précédents conservés :", json.dumps(preparation["statut_historique"], ensure_ascii=False))
            print("Historique transmis : enjeux résumés et références. Lectures complètes conservées dans les archives.")
            print("Cet essai ne valide pas le parcours complet. Aucune relance automatique.")
            try:
                resultat = generer_essai_isole(preparation, etape=etape, modele=modele, stockage_dir=session / "etapes",
                                              journal=JournalTerminal(modele=modele), autoriser_generation=True)
                print(f"\nAPPEL {numero} TERMINÉ — arrêt du parcours. Résultat : {resultat['dossier']}")
                print(f"Lecture : {resultat['dossier']}/lecture_{etape}.html")
            except KeyboardInterrupt:
                print("\nARRÊT MANUEL. Archives conservées ; aucune relance.")
                return 130
            except Exception as exc:
                print(f"\nARRÊT : {type(exc).__name__} — {exc}")
                print("Aucun appel supplémentaire. Les réponses et contrôles reçus restent archivés.")
                print(f"Journal : {session / 'terminal.log'}")
                return 1
    return 0


def lancer_redaction_archivee_terminal(sources_analyses, cas, modele, arreter_apres, dossier_reprise=None):
    """Lancement manuel des dernières étapes ; les six sources sont en lecture seule."""
    preparation = preparer_redaction_archivee({k: ROOT / v for k, v in sources_analyses.items()}, cas)
    empreintes = empreintes_moteur()
    preparation["empreinte_moteur"] = empreintes
    cle = hashlib.sha256(json.dumps({"sources": preparation["provenance"], "cas": cas,
                                    "modele": modele, "empreintes_moteur": empreintes},
                                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    session = SORTIES / ("redaction_7_8_" + cle[:16])
    if dossier_reprise is not None:
        dossier_reprise = (ROOT / dossier_reprise).expanduser().resolve()
        if (dossier_reprise.parent.name != "resultats"
                or dossier_reprise.parent.parent.parent != SORTIES.resolve()):
            raise ValueError("La reprise doit désigner un résultat de rédaction dans rapports_test/revolution_solaire_v2.")
        session = dossier_reprise.parent.parent
    session.mkdir(parents=True, exist_ok=True, mode=0o700)
    configuration = {"cas": cas, "modele": modele, "mode": "brouillon_depuis_six_archives",
                     "sources": preparation["provenance"], "empreintes_moteur": empreintes}
    nom_configuration = "configuration.json" if dossier_reprise is None else "configuration_reprise_" + cle[:16] + ".json"
    (session / nom_configuration).write_text(json.dumps(configuration, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshots = session / "sources_moteur" if dossier_reprise is None else session / "reprises_moteur" / cle[:16]
    snapshots.mkdir(parents=True, exist_ok=True)
    for relatif in empreintes:
        shutil.copy2(ROOT / relatif, snapshots / Path(relatif).name)
    with (session / "terminal.log").open("a", encoding="utf-8") as fichier:
        with contextlib.redirect_stdout(Tee(sys.stdout, fichier)), contextlib.redirect_stderr(Tee(sys.stderr, fichier)):
            print(f"\nRS V2 — {cas['personne']['nom']} — {cas['annee']}")
            print(f"Dossier local : {ROOT}\nSession : {session}\nJournal : {session / 'terminal.log'}")
            print("Parcours : appel 7 seul." if arreter_apres else "Parcours : appels 7 et 8 uniquement. Plafond : deux appels Claude.")
            if dossier_reprise is not None:
                print("REPRISE : réponse de l'appel 7 obligatoire en archive ; aucun nouvel appel 7.")
                print("Le plafond de deux appels inclut l'appel 7 déjà effectué. Seule la conclusion reste à générer.")
            print("Six réponses et calculs réutilisés ; aucune réécriture des archives sources.")
            print("Les consignes de ton sont appliquées au corps et à la conclusion.")
            print("Entrée de rédaction : mémoire courte des tendances, sans les six lectures complètes ni leurs exemples.")
            print("Texte livré : quelques repères, sans aspects énoncés, degrés ou orbes ; quatre grandes périodes au plus.")
            print("Sources provisoires :", json.dumps(preparation["statut_historique"], ensure_ascii=False))
            print("Références archivées reconnues par leurs valeurs calculées :", len(preparation["adaptations_references"]))
            print("Brouillon à relire ; aucune validation de livraison. Aucune pause ni relance automatique.")
            try:
                resultat = generer_redaction_archivee(preparation, cas, modele=modele,
                    stockage_dir=session / "resultats", journal=JournalTerminal(modele=modele),
                    autoriser_generation=True, arreter_apres=arreter_apres, dossier_reprise=dossier_reprise)
                print("\nRÉDACTION TERMINÉE — brouillon à relire.")
                print("Lecture :", Path(resultat["dossier"]) / "rapport_brouillon.html")
                print("Markdown :", Path(resultat["dossier"]) / "rapport_brouillon.md")
            except KeyboardInterrupt:
                print("\nARRÊT MANUEL. Réponses conservées ; aucune relance.")
                return 130
            except Exception as exc:
                print(f"\nARRÊT : {type(exc).__name__} — {exc}")
                print("Aucun appel supplémentaire. Le texte reçu reste consultable si une réponse a été reçue.")
                print("Journal :", session / "terminal.log")
                return 1
    return 0


def afficher_apercu_redaction_rs_v2(cas_a_tester, sources_analyses, *, modele="claude-sonnet-5"):
    """Lancement manuel gratuit : mémoire et prompt 7 uniquement, sans fournisseur IA."""
    from .memoire_redaction import construire_memoire
    from .schemas import schema_corps
    if len(cas_a_tester) != 1:
        raise ValueError("L'aperçu exige un profil unique.")
    cas = cas_a_tester[0]
    preparation = preparer_redaction_archivee({k: ROOT / v for k, v in sources_analyses.items()}, cas)
    prompt, faits = analyse.construire_prompt_corps(preparation["factuel"], preparation["analyses"],
        genre=cas["personne"].get("genre", ""), statut_historique=preparation["statut_historique"])
    cle = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    sortie = SORTIES / ("apercu_redaction_" + cle)
    sortie.mkdir(parents=True, exist_ok=True, mode=0o700)
    (sortie / "prompt_7.txt").write_text(prompt, encoding="utf-8")
    (sortie / "memoire.json").write_text(json.dumps(construire_memoire(preparation["analyses"]),
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    parametres = options_claude_v2(modele, {"max_tokens": 28000, "temperature": 0.5,
                                           "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": schema_corps()})
    with (sortie / "terminal.log").open("w", encoding="utf-8") as fichier:
        with contextlib.redirect_stdout(Tee(sys.stdout, fichier)):
            afficher_requete(modele, prompt, parametres, apercu=True)
            print("APERCU GRATUIT : aucun appel Claude, aucun rapport généré.")
            print("Mémoire :", sortie / "memoire.json")
            print("Prompt :", sortie / "prompt_7.txt")
            print("Faits transmis :", len(faits))
            print("L'appel 8 utilisera le nouveau corps ; il n'est ni construit ni envoyé par cet aperçu.")
    return 0


def lancer_test_rs_v2(cas_a_tester, *, modele="claude-sonnet-5", arreter_apres=None,
                     limite_appels_ia=8, source_rs_seule=None, source_resonances_natales=None,
                     source_profection=None, sources_analyses=None, reprendre_redaction=None):
    """Lance les profils sans pause, jusqu'à l'étape demandée ou au rapport entier."""
    if not cas_a_tester:
        raise ValueError("Renseigne au moins un profil dans CAS_A_TESTER.")
    if sources_analyses is not None:
        plafond = 1 if arreter_apres == "redaction_corps" else 2
        if (len(cas_a_tester) != 1 or arreter_apres not in (None, "redaction_corps")
                or limite_appels_ia != plafond):
            raise ValueError("La rédaction depuis six archives exige un profil et un plafond de " + str(plafond) + ".")
        if any(v is not None for v in (source_rs_seule, source_resonances_natales, source_profection)):
            raise ValueError("Utilise sources_analyses seule pour les appels 7 et 8.")
        return lancer_redaction_archivee_terminal(sources_analyses, cas_a_tester[0], modele, arreter_apres,
                                                  dossier_reprise=reprendre_redaction)
    if reprendre_redaction is not None:
        raise ValueError("Une reprise de rédaction exige sources_analyses.")
    if source_resonances_natales is not None and source_rs_seule is None:
        raise ValueError("L'essai depuis les résonances natales exige également l'archive RS seule.")
    if source_profection is not None and (source_rs_seule is None or source_resonances_natales is None
                                          or arreter_apres != "activations_annuelles"):
        raise ValueError("L'essai avec une archive de profection exige les sources 1 et 2 et l'étape activations_annuelles.")
    if source_rs_seule is not None:
        if arreter_apres in {"superpositions_maisons", "profection", "activations_annuelles"} and source_resonances_natales is None:
            raise ValueError("Cette étape exige les archives des appels 1 et 2.")
        if arreter_apres == "activations_annuelles" and source_profection is None:
            raise ValueError("L'appel 6 exige également l'archive de l'appel 5.")
        etape = (arreter_apres if arreter_apres in {"superpositions_maisons", "profection", "activations_annuelles"}
                 else "contacts_rs_natal" if source_resonances_natales is not None else "resonances_natales")
        if len(cas_a_tester) != 1 or arreter_apres != etape or limite_appels_ia != 1:
            raise ValueError("L'essai depuis une archive exige un profil, l'étape " + etape + " et un plafond de 1.")
        if source_resonances_natales is not None:
            if etape == "activations_annuelles":
                return lancer_essai_etape6_terminal(source_rs_seule, source_resonances_natales, source_profection, cas_a_tester[0], modele)
            if etape == "profection":
                return lancer_essai_etape5_terminal(source_rs_seule, source_resonances_natales, cas_a_tester[0], modele)
            if etape == "superpositions_maisons":
                return lancer_essai_etape4_terminal(source_rs_seule, source_resonances_natales, cas_a_tester[0], modele)
            return lancer_essai_etape3_terminal(source_rs_seule, source_resonances_natales, cas_a_tester[0], modele)
        return lancer_essai_etape2_terminal(source_rs_seule, cas_a_tester[0], modele)
    for numero in range(len(cas_a_tester)):
        options = ["--generer", "--cas", str(numero), "--modele", modele,
                   "--appels-max", str(limite_appels_ia)]
        if arreter_apres is not None:
            options.extend(["--etape", arreter_apres])
        code = main(options, cas_a_tester=cas_a_tester)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
