"""Orchestrateur V2 indépendant du service de vente : reprise étape par étape."""

from dataclasses import asdict, dataclass
from html import escape
import os
import re
import json
from pathlib import Path
import tempfile

from ..archives_generation import (
    GenerationAbsente, GenerationARevoir, ecrire_json, lire_json, texte_archive, verrou_demande,
    identifiant_demande,
)
from . import analyse
from .controle import AnalyseRSInvalide, controler_analyse_rs, controler_rapport_final_rs
from .dossier import VERSION, calculer_dossier_factuel_rs, controler_completude_dossier
from .budget import BudgetAppelsIA
from .connaissances import empreinte_connaissances
from .filtrage_aspects import VERSION_FILTRE_ASPECTS


@dataclass(frozen=True)
class RapportRSV2:
    texte_markdown: str
    html: str
    debut_cycle: str
    fin_cycle: str
    identifiant_generation: str
    dossier_generation: str
    version: str = VERSION


class ReponseTronquee(RuntimeError):
    def __init__(self, texte_partiel):
        self.texte_partiel = texte_partiel
        super().__init__("Réponse V2 tronquée, conservée sans relance automatique.")


class RequeteAPIRefusee(GenerationARevoir):
    """Refus HTTP 400 connu : aucune génération reçue, paramètres à corriger."""


class AppelAnnuleAvantEnvoi(KeyboardInterrupt):
    """Arrêt demandé pendant l'affichage du prompt, avant toute requête."""


def options_claude_v2(modele, options):
    """Les Claude 5 refusent les anciennes températures non par défaut."""
    resultat = dict(options)
    schema = resultat.pop("schema_sortie", None)
    effort = resultat.pop("niveau_effort", "medium")
    reflexion = resultat.pop("reflexion", None)
    configuration = {}
    if schema is not None:
        configuration["format"] = {"type": "json_schema", "schema": schema}
    if re.match(r"^claude-[a-z]+-5(?:-|$)", modele):
        resultat.pop("temperature", None)
        configuration["effort"] = effort
    if reflexion == "disabled" and modele.startswith("claude-sonnet-5"):
        resultat["thinking"] = {"type": "between_tools" if modele.startswith("claude-sonnet-5-5") else "disabled"}
    if configuration:
        resultat["extra_body"] = {"output_config": configuration}
    return resultat


def _notifier(journal, evenement, **details):
    if journal is not None:
        journal(evenement, **details)


def _appel_claude(prompt, *, modele=None, budget=None, journal=None, **options):
    if budget is None:
        raise GenerationAbsente("Appel Claude interdit sans plafond explicite et journal de dépenses.")
    budget.verifier_disponible()
    modele_explicite = modele is not None
    # Le lanceur impose un modèle explicite ; la compatibilité du service
    # historique conserve son modèle par défaut.
    if modele is not None:
        parametres = options_claude_v2(modele, options)
        _notifier(journal, "requete", modele=modele, prompt=prompt, parametres=parametres)
    # Import tardif : calculer/préparer une V2 ne nécessite aucune clé IA.
    from utils.claude_llm import CLIENT, MODEL
    from anthropic import BadRequestError
    modele = modele or MODEL
    parametres = options_claude_v2(modele, options)
    if not modele_explicite:
        _notifier(journal, "requete", modele=modele, prompt=prompt, parametres=parametres)
    numero = budget.reserver(modele, prompt, parametres.get("max_tokens"))
    _notifier(journal, "envoi", numero=numero + 1, modele=modele)
    # Le streaming évite les longues requêtes non streamées ; les blocs de
    # réflexion des nouveaux modèles ne sont jamais confondus avec du texte.
    try:
        with CLIENT.with_options(max_retries=0).messages.stream(
            model=modele, messages=[{"role": "user", "content": prompt}], **parametres,
        ) as flux:
            reponse = flux.get_final_message()
    except BadRequestError as exc:
        budget.terminer(numero, statut="refuse_api")
        corps = exc.body if isinstance(exc.body, dict) else {}
        details = corps.get("error", corps)
        raison = details.get("message", "Paramètres API refusés.") if isinstance(details, dict) else "Paramètres API refusés."
        _notifier(journal, "refus_api", raison=raison)
        raise RequeteAPIRefusee(raison) from exc
    except Exception as exc:
        budget.terminer(numero, statut="resultat_incertain")
        _notifier(journal, "erreur_reseau", type_erreur=type(exc).__name__)
        raise
    usage = reponse.usage.model_dump(mode="json")
    budget.terminer(numero, statut=reponse.stop_reason, usage=usage)
    texte = "".join(bloc.text for bloc in reponse.content if getattr(bloc, "type", None) == "text")
    _notifier(journal, "reponse", texte=texte, usage=usage, statut=reponse.stop_reason)
    if reponse.stop_reason == "max_tokens":
        raise ReponseTronquee(texte)
    if reponse.stop_reason not in {"end_turn", "stop_sequence"}:
        raise GenerationARevoir("Réponse Claude non terminée : " + str(reponse.stop_reason))
    if not texte.strip():
        raise GenerationARevoir("Réponse Claude sans texte exploitable.")
    return texte


def _fournisseur_borne(dossier, modele, limite, journal=None):
    budget = BudgetAppelsIA(dossier, limite)

    def appeler(prompt, **options):
        return _appel_claude(prompt, modele=modele, budget=budget, journal=journal, **options)

    appeler.budget = budget
    return appeler


def _etape_archivee(dossier, nom, fonction, appel, journal=None):
    """Archive la réponse brute avant son parsing ; ne réessaie pas une erreur IA."""
    partie = Path(dossier) / nom
    partie.mkdir(exist_ok=True, mode=0o700)
    _notifier(journal, "etape", nom=nom, dossier=str(partie))

    def appeler(prompt, **options):
        completee = lire_json(partie, "reponse_completee.json")
        if completee is not None:
            _notifier(journal, "cache", prompt_archive=lire_json(partie, "prompt.json"),
                      texte=completee["texte"], source="reponse_completee.json")
            return completee["texte"]
        dossier_appel = partie
        refus = lire_json(partie, "refus_api.json")
        if refus and refus.get("code_http") == 400 and lire_json(partie, "reponse.json") is None:
            precedente = lire_json(partie, "prompt.json")
            if precedente == {"prompt": prompt, "options": options}:
                raise RequeteAPIRefusee("Requête déjà refusée : corrige ses paramètres avant un nouvel appel.")
            # Un HTTP 400 diagnostiqué n'est pas un résultat réseau incertain.
            # Les nouveaux paramètres ont leur propre archive ; aucun retry
            # n'est fait pour une réponse reçue, tronquée ou un échec réseau.
            cle = identifiant_demande({"prompt": prompt, "options": options})
            dossier_appel = partie / ("correction_requete_" + cle[:16])
            dossier_appel.mkdir(exist_ok=True, mode=0o700)
        reponse_archivee = lire_json(dossier_appel, "reponse.json")
        if reponse_archivee is not None:
            _notifier(journal, "cache", prompt_archive=lire_json(dossier_appel, "prompt.json"),
                      texte=reponse_archivee["texte"], source="reponse.json")
        else:
            ecrire_json(dossier_appel, "prompt.json", {"prompt": prompt, "options": options})
        if (lire_json(dossier_appel, "reponse.json") is None
                and lire_json(dossier_appel, "appel.json") is None
                and getattr(appel, "budget", None) is not None):
            appel.budget.verifier_disponible()
        try:
            return texte_archive(dossier_appel, prompt, lambda contenu: appel(contenu, **options), ReponseTronquee)
        except AppelAnnuleAvantEnvoi:
            # L'arrêt a précédé la réservation du budget et le réseau.
            # Conserver sa trace sans interdire une reprise de cette étape.
            (dossier_appel / "appel.json").replace(dossier_appel / "annulation_avant_envoi.json")
            ecrire_json(dossier, "etat.json", {"statut": "arret_manuel_avant_envoi", "etape": nom})
            raise
        except RequeteAPIRefusee as exc:
            ecrire_json(dossier_appel, "refus_api.json", {"code_http": 400, "raison": str(exc),
                                                        "statut": "refuse_avant_generation"})
            raise

    # Les fonctions réexécutent leurs contrôles, mais l'appel est servi depuis
    # l'archive ; une reprise après échec HTML ne facture aucune nouvelle IA.
    ecrire_json(dossier, "etat.json", {"statut": "en_cours", "etape": nom})
    try:
        resultat = fonction(appeler)
    except GenerationARevoir as exc:
        diagnostic = getattr(exc, "diagnostic_superpositions", None)
        if diagnostic is not None:
            ecrire_json(partie, "controle_superpositions.json", diagnostic)
            _notifier(journal, "controle_superpositions", nom=nom, controle=diagnostic)
        ecrire_json(partie, "controle.json", {"statut": "bloque", "raison": str(exc)})
        ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "etape": nom})
        _notifier(journal, "controle_bloque", nom=nom, raison=str(exc))
        raise
    except Exception as exc:
        ecrire_json(dossier, "etat.json", {"statut": "interrompu", "etape": nom,
                                           "type_erreur": type(exc).__name__})
        _notifier(journal, "interruption", nom=nom, type_erreur=type(exc).__name__)
        raise
    ecrire_json(partie, "resultat.json", resultat)
    ecrire_json(partie, "controle.json", {"statut": "valide"})
    _notifier(journal, "controle_valide", nom=nom)
    return resultat


def completer_premiere_analyse_tronquee(dossier_generation, *, autoriser_generation=False, appeler=None,
                                      limite_appels_ia=0):
    """Ancien complément de grille désactivé ; les fragments archivés restent conservés."""
    raise GenerationARevoir(
        "L'ancien complément de suivi est désactivé dans la version sans grille. "
        "Le fragment reste archivé ; aucun appel Claude n'est lancé.")


def assembler_rapport_rs(corps, conclusion, annee):
    """Les titres sont ajoutés par le programme, pas générés à plusieurs endroits."""
    parties = [f"# Ta révolution solaire {annee}"]
    for section in corps["sections"]:
        titre = " ".join(section["titre"].splitlines())
        parties.append(f"## {titre}\n\n{section['texte'].strip()}")
    parties.append("## Ce que cette année te demande vraiment\n\n" + conclusion["texte"].strip())
    return "\n\n".join(parties)


def generer_rapport_rs_v2(
    *, personne, lieu_rs, annee, contexte_client=None, stockage_dir=None,
    preparation_seule=False, autoriser_generation=False, appeler=None,
    raffiner_transits=True, identifiant_execution=None, arreter_apres=None, modele=None,
    limite_appels_ia=0, journal=None,
):
    """Calcule, analyse en six étapes, contrôle, rédige et rend un rapport V2.

    Par défaut les appels payants sont désactivés. ``preparation_seule=True``
    retourne le dossier factuel et son emplacement sans importer de client IA.
    Ce moteur n'est pas branché au paiement ou à la livraison automatique.
    """
    if arreter_apres is not None and arreter_apres not in analyse.ETAPES:
        raise ValueError("Étape d'arrêt V2 inconnue.")
    if modele is not None and (not isinstance(modele, str) or not modele.startswith("claude-") or modele.strip() != modele):
        raise ValueError("Identifiant de modèle Claude invalide.")
    if contexte_client is not None and (
        not isinstance(contexte_client, dict)
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in contexte_client.items())
    ):
        raise ValueError("Le contexte doit être un dictionnaire de textes.")
    demande = {
        "version": VERSION, "personne": personne, "lieu_rs": lieu_rs, "annee": annee,
        "connaissances_rs": empreinte_connaissances(),
        "filtre_aspects_internes": VERSION_FILTRE_ASPECTS,
        "version_analyses": analyse.VERSION_ANALYSES,
        "contexte_client": contexte_client or {}, "raffiner_transits": raffiner_transits,
        "modele": modele or (os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5") if appeler is None else "appel_injecte"),
    }
    if identifiant_execution:
        demande["identifiant_execution"] = identifiant_execution
    racine = Path(stockage_dir) if stockage_dir is not None else Path(__file__).resolve().parents[3] / "instance" / "rs_v2_sequentielle"
    with verrou_demande(demande, racine) as dossier:
        ecrire_json(dossier, "demande.json", demande)
        dossier_factuel = lire_json(dossier, "dossier_factuel.json")
        if dossier_factuel is None:
            if not preparation_seule and not autoriser_generation:
                raise GenerationAbsente("Prépare les calculs ou active explicitement la génération V2.")
            ecrire_json(dossier, "etat.json", {"statut": "en_cours", "etape": "calculs"})
            _notifier(journal, "calculs", dossier=str(dossier))
            dossier_factuel = calculer_dossier_factuel_rs(
                personne=personne, lieu_rs=lieu_rs, annee=annee, raffiner_transits=raffiner_transits)
            ecrire_json(dossier, "dossier_factuel.json", dossier_factuel)
        controle_dossier = controler_completude_dossier(dossier_factuel)
        ecrire_json(dossier, "controle_dossier.json", controle_dossier)
        _notifier(journal, "dossier_factuel", dossier=str(dossier), controle=controle_dossier)
        entree_rs = analyse.construire_entree_etape("rs_seule", dossier_factuel, {})
        ecrire_json(dossier, "reperes_interpretatifs_rs.json", entree_rs["reperes_interpretatifs"])
        if preparation_seule:
            if (lire_json(dossier, "etat.json") or {}).get("etape") == "calculs":
                ecrire_json(dossier, "etat.json", {"statut": "prepare", "etape": "calculs"})
            return {"dossier": str(dossier), "donnees": dossier_factuel, "controle": controle_dossier}

        cache = lire_json(dossier, "rapport.json")
        if cache is not None and arreter_apres is None:
            _controler_archives(dossier, dossier_factuel, cache["texte_markdown"])
            _notifier(journal, "rapport_cache", dossier=str(dossier))
            return RapportRSV2(**cache)
        if not autoriser_generation:
            raise GenerationAbsente("La génération IA V2 n'est pas activée.")
        appel = appeler or _fournisseur_borne(dossier, demande["modele"], limite_appels_ia, journal=journal)
        fonctions = {
            "rs_seule": analyse.analyser_rs_seule,
            "resonances_natales": analyse.analyser_resonances_natales,
            "contacts_rs_natal": analyse.analyser_contacts_rs_natal,
            "superpositions_maisons": analyse.analyser_superpositions_maisons,
            "profection": analyse.integrer_profection,
            "activations_annuelles": analyse.analyser_activations_annuelles,
        }
        analyses = {}
        for nom in analyse.ETAPES:
            fonction = fonctions[nom]
            resultat = _etape_archivee(
                dossier, nom,
                lambda appeler, nom=nom, fonction=fonction: (
                    fonction(dossier_factuel, appeler=appeler) if nom == "rs_seule"
                    else fonction(dossier_factuel, analyses, appeler=appeler)),
                appel,
                journal=journal,
            )
            from ..controle_livraison import controler_placements
            textes = "\n\n".join(e["lecture"] for e in resultat["enjeux"])
            if nom == "rs_seule":
                textes = resultat["ambiance"] + "\n\n" + textes
            controle_lecture = controler_placements(textes, dossier_factuel["donnees_controle"])
            ecrire_json(dossier / nom, "controle_lecture.json", controle_lecture)
            _notifier(journal, "controle_placements", nom=nom, controle=controle_lecture)
            if controle_lecture["erreurs"]:
                ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "etape": nom})
                raise AnalyseRSInvalide("Contradiction factuelle dans l'analyse " + nom + ".")
            analyses[nom] = resultat
            if nom == arreter_apres:
                partiel = {"dossier": str(dossier), "etape": nom, "resultat": resultat,
                           "analyses": analyses}
                ecrire_json(dossier, "analyse_partielle.json", partiel)
                if cache is None:
                    ecrire_json(dossier, "etat.json", {"statut": "etape_terminee", "etape": nom})
                else:
                    ecrire_json(dossier, "etat.json", {"statut": "termine", "etape": "rapport"})
                return partiel
        ecrire_json(dossier, "analyse.json", analyses)
        ecrire_json(dossier, "controle_analyse.json", controler_analyse_rs(dossier_factuel, analyses))
        _notifier(journal, "analyses_validees")
        corps = _etape_archivee(
            dossier, "redaction_corps",
            lambda appeler: analyse.rediger_corps_rapport_rs(
                dossier_factuel, analyses, appeler=appeler, genre=personne.get("genre", "")), appel, journal=journal)
        # Contrôle du corps avant de payer la conclusion.
        texte_corps = "\n\n".join(s["texte"] for s in corps["sections"])
        from ..controle_livraison import controler_placements
        controle_corps = controler_placements(texte_corps, dossier_factuel["donnees_controle"])
        ecrire_json(dossier, "controle_corps.json", controle_corps)
        _notifier(journal, "controle_placements", nom="redaction_corps", controle=controle_corps)
        if controle_corps["erreurs"]:
            ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "etape": "controle_corps"})
            raise AnalyseRSInvalide("Contradiction factuelle dans le corps ; conclusion non lancée.")
        conclusion = _etape_archivee(
            dossier, "conclusion_contextuelle",
            lambda appeler: analyse.rediger_conclusion_contextuelle(
                dossier_factuel, analyses, corps, contexte_client,
                appeler=appeler, genre=personne.get("genre", "")), appel, journal=journal)
        texte = assembler_rapport_rs(corps, conclusion, annee)
        _controler_archives(dossier, dossier_factuel, texte)
        from ..rapport_html import generer_rapport_html
        with tempfile.TemporaryDirectory() as temporaire:
            chemin = generer_rapport_html(
                escape(texte, quote=False), Path(temporaire) / "rapport.html",
                nom=escape(personne["nom"]), annee=annee)
            html = chemin.read_text(encoding="utf-8")
        rapport = RapportRSV2(
            texte_markdown=texte, html=html,
            debut_cycle=dossier_factuel["cycle"]["debut_utc"],
            fin_cycle=dossier_factuel["cycle"]["fin_utc"],
            identifiant_generation=dossier.name, dossier_generation=str(dossier))
        ecrire_json(dossier, "rapport.json", asdict(rapport))
        (dossier / "rapport.md").write_text(texte, encoding="utf-8")
        (dossier / "rapport.html").write_text(html, encoding="utf-8")
        ecrire_json(dossier, "etat.json", {"statut": "termine", "etape": "rapport"})
        _notifier(journal, "rapport_termine", dossier=str(dossier))
        return rapport


def _controler_archives(dossier, factuel, texte):
    analyses = {nom: lire_json(Path(dossier) / nom, "resultat.json") for nom in analyse.ETAPES}
    if any(resultat is None for resultat in analyses.values()):
        raise AnalyseRSInvalide("Archives d'analyse absentes : rapport non livrable.")
    corps = lire_json(Path(dossier) / "redaction_corps", "resultat.json")
    conclusion = lire_json(Path(dossier) / "conclusion_contextuelle", "resultat.json")
    if corps is None or conclusion is None:
        raise AnalyseRSInvalide("Archives de rédaction absentes : rapport non livrable.")
    if texte != assembler_rapport_rs(corps, conclusion, factuel["cycle"]["annee"]):
        raise AnalyseRSInvalide("Le rapport ne correspond pas aux étapes archivées.")
    try:
        controle = controler_rapport_final_rs(texte, factuel, analyses, corps, conclusion)
    except AnalyseRSInvalide as exc:
        ecrire_json(dossier, "controle_final.json", {"statut": "bloque", "raison": str(exc), "bloquant": True})
        ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "etape": "controle_final"})
        raise
    ecrire_json(dossier, "controle_final.json", controle)
