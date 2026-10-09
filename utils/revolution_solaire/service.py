"""Service réutilisable de génération d'une Révolution solaire.

Ce fichier contient le pipeline public. Le lanceur ``test_revolution.py``
reste un outil de comparaison : il n'est jamais importé par l'application.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import os
from pathlib import Path
from .archives_generation import (verrou_demande, ecrire_json, lire_json, texte_archive, GenerationAbsente)

from .controle_livraison import controler_placements, corriger_references_maitrises, corriger_fausses_maitrises_points, RapportFactuelInvalide
from .accords import accorder_formes_inclusives

from utils.claude_llm import BlocTronqueError, ask_claude
from utils.revolution_solaire.calcul_retour_solaire import trouver_retour_solaire
from utils.revolution_solaire.donnees_techniques import extraire_donnees_revolution_solaire
from utils.revolution_solaire.prompt_rapport_complet import construire_prompt_rapport_complet
from utils.revolution_solaire.corrections_faits_rs import corriger_contacts_et_roles
from utils.revolution_solaire.prompt_synthese_contextuelle import construire_prompt_synthese_contextuelle, assembler_rapport
from utils.revolution_solaire.rapport_html import generer_rapport_html
from utils.revolution_solaire.rapport_technique import generer_rapport_technique
from utils.revolution_solaire.themes_prioritaires import detecter_themes_prioritaires_rs
from utils.revolution_solaire.theme_revolution_solaire import calculer_theme_revolution_solaire
from utils.revolution_solaire.transits_annuels import calculer_transits_annuels_rs
from utils.revolution_solaire.activations_annuelles import (
    selectionner_activations_annuelles, transits_pour_rapport, dater_activations,
)
from utils.revolution_solaire.verification_rapport import verifier_rapport_revolution_solaire


def _rediger_avec_claude(prompt: str, parametres: dict) -> str:
    """Conserve le moteur Claude du test local sans changer les autres analyses."""
    return ask_claude(
        prompt,
        max_tokens=parametres['max_tokens'],
        temperature=parametres['temperature'],
        stop_sequences=parametres['stop_sequences'],
        single_attempt=True,
    )


@dataclass(frozen=True)
class RapportRevolutionSolaire:
    texte_markdown: str
    html: str
    releve_technique: str
    controle_factualite: str
    debut_cycle: str
    fin_cycle: str
    identifiant_generation: str = ""


def _controler_avant_livraison(dossier, texte, preparation):
    if not preparation or not isinstance(preparation.get('donnees'), dict):
        ecrire_json(dossier, 'controle.json', {'statut': 'faits_indisponibles'})
        raise RapportFactuelInvalide(
            'Le rapport est conservé, mais ses données de contrôle sont indisponibles. '
            'Vérification manuelle nécessaire ; aucun nouvel appel IA lancé.')
    controle = verifier_rapport_revolution_solaire(
        texte, preparation['donnees'], preparation.get('transits_directeurs'))
    resultat = controler_placements(texte, preparation['donnees'])
    resultat['texte'] = controle
    ecrire_json(dossier, 'controle.json', resultat)
    if resultat['erreurs']:
        raise RapportFactuelInvalide(
            f"{len(resultat['erreurs'])} contradiction(s) de placement détectée(s). "
            'La réponse est sauvegardée ; livraison suspendue pour correction. '
            'Aucun nouvel appel IA lancé automatiquement.')
    return controle


def _generer_rapport_revolution_solaire(
    *,
    dossier,
    personne: dict,
    lieu_rs: dict,
    annee: int,
    contexte_client: dict | None = None,
    preparation_seule: bool = False,
) -> RapportRevolutionSolaire:
    """Calcule une RS et rédige séparément son corps et sa synthèse.

    Les données factuelles restent calculées localement. Claude reçoit le
    contrat astrologique et rédige uniquement la lecture cliente.
    """
    preparation = lire_json(dossier, 'preparation.json')
    if preparation is None:
        calcul = calculer_theme_revolution_solaire(
            personne["nom"], personne, lieu_rs, annee,
        )
        donnees = extraire_donnees_revolution_solaire(
            calcul["theme_natal"],
            calcul["theme_revolution_solaire"],
            age_profection=calcul["age_au_retour"],
        )
        prochain_retour = trouver_retour_solaire(calcul["naissance_locale"], annee + 1)
        transits = calculer_transits_annuels_rs(
            calcul["theme_natal"],
            calcul["theme_revolution_solaire"],
            donnees["facteurs_directeurs_rs"],
            calcul["retour"]["retour_utc"],
            prochain_retour["retour_utc"],
        )
        activations = selectionner_activations_annuelles(
            transits, donnees["facteurs_directeurs_rs"],
            theme_natal=calcul["theme_natal"], theme_rs=calcul["theme_revolution_solaire"],
        )
        transits_directeurs = transits_pour_rapport(
            transits, donnees["facteurs_directeurs_rs"], activations,
            theme_natal=calcul["theme_natal"], theme_rs=calcul["theme_revolution_solaire"],
        )
        activations_datees = dater_activations(
            activations, calcul["theme_natal"], calcul["theme_revolution_solaire"],
            donnees["facteurs_directeurs_rs"], calcul["retour"]["retour_utc"],
            prochain_retour["retour_utc"],
        )
        donnees["themes_prioritaires"] = detecter_themes_prioritaires_rs(donnees)
        releve_technique = generer_rapport_technique(donnees, calcul["retour_local"])
        debut_cycle = calcul["retour"]["retour_utc"].date().isoformat()
        fin_cycle = prochain_retour["retour_utc"].date().isoformat()
        prompt = construire_prompt_rapport_complet(
            donnees,
            transits_directeurs,
            nom=personne["nom"],
            genre=personne.get('genre', ''),
            annee=annee,
            debut_transits=debut_cycle,
            fin_transits=fin_cycle,
            synthese_interne="",
            releve_technique=releve_technique,
            themes_prioritaires=donnees["themes_prioritaires"],
            activations_calculees=activations_datees,
        )
        ecrire_json(dossier, 'preparation.json', {
            'mode_redaction': 'corps_neutre_puis_synthese',
            'contexte_client': {key: value for key, value in (contexte_client or {}).items() if str(value).strip()},
            'donnees': donnees, 'transits_directeurs': transits_directeurs,
            'activations_datees': activations_datees,
            'releve_technique': releve_technique, 'debut_cycle': debut_cycle,
            'fin_cycle': fin_cycle, 'prompt': prompt,
            'fournisseur': 'claude',
            'modele': os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5'),
            'parametres': {'max_tokens': 14000, 'temperature': 0.65, 'retries': 1, 'stop_sequences': ['<FIN_RAPPORT>']},
        })
        preparation = lire_json(dossier, 'preparation.json')
    if preparation_seule:
        return preparation
    donnees = preparation['donnees']
    transits_directeurs = preparation['transits_directeurs']
    releve_technique = preparation['releve_technique']
    debut_cycle = preparation['debut_cycle']
    fin_cycle = preparation['fin_cycle']
    prompt = preparation['prompt']
    if preparation.get('mode_redaction') == 'corps_neutre_puis_synthese':
        dossier_corps = Path(dossier) / 'corps_neutre'
        dossier_corps.mkdir(exist_ok=True, mode=0o700)
        corps = texte_archive(
            dossier_corps, prompt,
            lambda contenu: _rediger_avec_claude(contenu, preparation['parametres']),
            BlocTronqueError,
        )
        corps, corrections_points, erreurs_points = corriger_fausses_maitrises_points(corps, donnees)
        if corrections_points:
            ecrire_json(dossier, 'corrections_points_corps.json', corrections_points)
        if erreurs_points:
            ecrire_json(dossier, 'erreurs_points_corps.json', erreurs_points)
            raise RapportFactuelInvalide('Une maîtrise impossible reste dans le corps du rapport.')
        corps = accorder_formes_inclusives(corps, personne.get('genre'))
        corps, corrections_faits = corriger_contacts_et_roles(corps, donnees)
        if corrections_faits:
            ecrire_json(dossier, 'corrections_faits_corps.json', corrections_faits)
        controle_corps = controler_placements(corps, donnees)
        if controle_corps['erreurs']:
            corps, corrections = corriger_references_maitrises(
                corps, donnees, controle_corps['erreurs'])
            if corrections:
                ecrire_json(dossier, 'corrections_corps.json', corrections)
        controle_corps = controler_placements(corps, donnees)
        if controle_corps['erreurs']:
            ecrire_json(dossier, 'controle_corps.json', controle_corps)
            raise RapportFactuelInvalide(
                f"{len(controle_corps['erreurs'])} contradiction(s) dans le corps du rapport. "
                "La synthèse n'a pas été lancée ; le texte reçu est conservé.")
        dossier_synthese = Path(dossier) / 'synthese_contextuelle'
        dossier_synthese.mkdir(exist_ok=True, mode=0o700)
        prompt_synthese = construire_prompt_synthese_contextuelle(
            corps, preparation.get('contexte_client'), personne.get('genre', ''))
        ecrire_json(dossier_synthese, 'preparation.json', {'prompt': prompt_synthese})
        synthese = texte_archive(
            dossier_synthese, prompt_synthese,
            lambda contenu: _rediger_avec_claude(contenu, {
                'max_tokens': 1600, 'temperature': 0.6,
                'stop_sequences': ['<FIN_SYNTHESE>'],
            }),
            BlocTronqueError,
        )
        texte_markdown = assembler_rapport(corps, synthese)
        texte_markdown, corrections_points, erreurs_points = corriger_fausses_maitrises_points(
            texte_markdown, donnees)
        if corrections_points:
            ecrire_json(dossier, 'corrections_points_rapport.json', corrections_points)
        if erreurs_points:
            ecrire_json(dossier, 'erreurs_points_rapport.json', erreurs_points)
            raise RapportFactuelInvalide('Une maîtrise impossible reste dans la synthèse du rapport.')
        texte_markdown = accorder_formes_inclusives(texte_markdown, personne.get('genre'))
        texte_markdown, corrections_faits = corriger_contacts_et_roles(texte_markdown, donnees)
        if corrections_faits:
            ecrire_json(dossier, 'corrections_faits_rapport.json', corrections_faits)
    else:
        # Les générations déjà préparées gardent leur prompt et leur réponse.
        texte_markdown = texte_archive(
            dossier, prompt,
            lambda contenu: _rediger_avec_claude(contenu, preparation['parametres']),
            BlocTronqueError,
        )

    premier_controle = controler_placements(texte_markdown, donnees)
    if premier_controle['erreurs']:
        texte_corrige, corrections = corriger_references_maitrises(
            texte_markdown, donnees, premier_controle['erreurs'])
        if corrections:
            ecrire_json(dossier, 'corrections_factuelles.json', corrections)
            texte_markdown = texte_corrige

    controle = _controler_avant_livraison(dossier, texte_markdown, preparation)
    # Le générateur HTML est utilisé comme fonction pure de rendu : son écriture
    # temporaire est évitée ici afin que la route choisisse elle-même l'emplacement.
    import tempfile

    with tempfile.TemporaryDirectory() as dossier_html:
        chemin = generer_rapport_html(
            texte_markdown,
            Path(dossier_html) / "rapport.html",
            nom=personne["nom"],
            annee=annee,
        )
        html = chemin.read_text(encoding="utf-8")

    return RapportRevolutionSolaire(
        texte_markdown=texte_markdown,
        html=html,
        releve_technique=releve_technique,
        controle_factualite=controle,
        debut_cycle=debut_cycle,
        fin_cycle=fin_cycle,
        identifiant_generation=dossier.name,
    )


def generer_rapport_revolution_solaire(
    *, personne: dict, lieu_rs: dict, annee: int,
    contexte_client: dict | None = None, stockage_dir=None,
    autoriser_generation: bool = True,
    identifiant_execution: str | None = None,
) -> RapportRevolutionSolaire:
    """Une demande identique réutilise sa sortie ; aucun retry facturé implicite."""
    demande = {
        'personne': personne, 'lieu_rs': lieu_rs, 'annee': annee,
        'contexte_client': {k: v for k, v in (contexte_client or {}).items() if str(v).strip()},
    }
    # Une exécution explicite peut comparer les mêmes données sans écraser
    # l'ancien rapport. Cet identifiant n'entre jamais dans le prompt.
    demande_archive = dict(demande)
    if identifiant_execution:
        demande_archive['identifiant_execution'] = identifiant_execution
    with verrou_demande(demande_archive, stockage_dir) as dossier:
        resultat = lire_json(dossier, 'rapport.json')
        if resultat is not None:
            controle = _controler_avant_livraison(
                dossier, resultat['texte_markdown'], lire_json(dossier, 'preparation.json'))
            return replace(RapportRevolutionSolaire(**resultat), controle_factualite=controle)
        if not autoriser_generation:
            raise GenerationAbsente('Confirme la génération avant de lancer le rapport.')
        ecrire_json(dossier, 'demande.json', demande_archive)
        rapport = _generer_rapport_revolution_solaire(dossier=dossier, **demande)
        ecrire_json(dossier, 'rapport.json', asdict(rapport))
        return rapport


def generer_rapport_revolution_solaire_v2(
    *, personne, lieu_rs, annee, contexte_client=None, stockage_dir=None,
    autoriser_generation=True, identifiant_execution=None, moteur_enjeux=False,
):
    """Parcours complet V2 : calculs directs, rédaction séquentielle et cache."""
    from .version_archive_enjeux import generer_version_2, VERSION
    demande = {'personne': personne, 'lieu_rs': lieu_rs, 'annee': annee,
               'contexte_client': {k:v for k,v in (contexte_client or {}).items() if str(v).strip()},
               'moteur': VERSION}
    if identifiant_execution:
        demande['identifiant_execution'] = identifiant_execution
    with verrou_demande(demande, stockage_dir) as dossier:
        resultat = lire_json(dossier, 'rapport.json')
        if resultat is not None:
            return RapportRevolutionSolaire(**resultat)
        if not autoriser_generation:
            raise GenerationAbsente('Confirme la génération avant de lancer le rapport.')
        ecrire_json(dossier, 'demande.json', demande)
        preparation = _generer_rapport_revolution_solaire(
            dossier=dossier, personne=personne, lieu_rs=lieu_rs, annee=annee,
            contexte_client=contexte_client, preparation_seule=True)
        sortie = generer_version_2(dossier, dossier.parent.parent / 'generations_rs_v2')
        resultat_v2 = lire_json(sortie, 'rapport.json')
        controle = verifier_rapport_revolution_solaire(
            resultat_v2['texte_markdown'], preparation['donnees'], preparation.get('transits_directeurs'))
        diagnostic = controler_placements(resultat_v2['texte_markdown'], preparation['donnees'])
        diagnostic.update(bloquant=False, texte=controle)
        if diagnostic['erreurs']:
            diagnostic['statut'] = 'avertissements_non_bloquants'
        ecrire_json(dossier, 'controle.json', diagnostic)
        rapport = RapportRevolutionSolaire(
            texte_markdown=resultat_v2['texte_markdown'], html=resultat_v2['html'],
            releve_technique=preparation['releve_technique'], controle_factualite=controle,
            debut_cycle=preparation['debut_cycle'], fin_cycle=preparation['fin_cycle'],
            identifiant_generation=dossier.name)
        ecrire_json(dossier, 'rapport.json', asdict(rapport))
        return rapport
