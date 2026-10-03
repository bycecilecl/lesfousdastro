"""Service réutilisable de génération d'une Révolution solaire.

Ce fichier contient le pipeline public. Le lanceur ``test_revolution.py``
reste un outil de comparaison : il n'est jamais importé par l'application.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import os
from .archives_generation import (verrou_demande, ecrire_json, lire_json, texte_archive, GenerationAbsente)

from .controle_livraison import controler_placements, RapportFactuelInvalide

from utils.claude_llm import BlocTronqueError
from utils.claude_llm import ask_claude
from utils.revolution_solaire.calcul_retour_solaire import trouver_retour_solaire
from utils.revolution_solaire.donnees_techniques import extraire_donnees_revolution_solaire
from utils.revolution_solaire.prompt_rapport_complet import construire_prompt_rapport_complet
from utils.revolution_solaire.rapport_html import generer_rapport_html
from utils.revolution_solaire.rapport_technique import generer_rapport_technique
from utils.revolution_solaire.themes_prioritaires import detecter_themes_prioritaires_rs
from utils.revolution_solaire.theme_revolution_solaire import calculer_theme_revolution_solaire
from utils.revolution_solaire.transits_annuels import calculer_transits_annuels_rs
from utils.revolution_solaire.activations_annuelles import (
    selectionner_activations_annuelles, transits_pour_rapport, dater_activations,
)
from utils.revolution_solaire.verification_rapport import verifier_rapport_revolution_solaire


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
) -> RapportRevolutionSolaire:
    """Calcule et rédige une RS complète avec le client Claude partagé.

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
            annee=annee,
            debut_transits=debut_cycle,
            fin_transits=fin_cycle,
            synthese_interne="",
            contexte_client={key: value for key, value in (contexte_client or {}).items() if str(value).strip()},
            releve_technique=releve_technique,
            themes_prioritaires=donnees["themes_prioritaires"],
            activations_calculees=activations_datees,
        )
        ecrire_json(dossier, 'preparation.json', {
            'donnees': donnees, 'transits_directeurs': transits_directeurs,
            'activations_datees': activations_datees,
            'releve_technique': releve_technique, 'debut_cycle': debut_cycle,
            'fin_cycle': fin_cycle, 'prompt': prompt,
            'fournisseur': 'claude',
            'modele': os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5'),
            'parametres': {'max_tokens': 14000, 'temperature': 0.65, 'retries': 1, 'stop_sequences': ['<FIN_RAPPORT>']},
        })
        preparation = lire_json(dossier, 'preparation.json')
    donnees = preparation['donnees']
    transits_directeurs = preparation['transits_directeurs']
    releve_technique = preparation['releve_technique']
    debut_cycle = preparation['debut_cycle']
    fin_cycle = preparation['fin_cycle']
    prompt = preparation['prompt']
    texte_markdown = texte_archive(
        dossier, prompt,
        lambda contenu: ask_claude(
            contenu,
            max_tokens=preparation['parametres']['max_tokens'],
            temperature=preparation['parametres']['temperature'],
            stop_sequences=preparation['parametres']['stop_sequences'],
        ),
        BlocTronqueError,
    )

    controle = _controler_avant_livraison(dossier, texte_markdown, preparation)
    # Le générateur HTML est utilisé comme fonction pure de rendu : son écriture
    # temporaire est évitée ici afin que la route choisisse elle-même l'emplacement.
    from pathlib import Path
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
) -> RapportRevolutionSolaire:
    """Une demande identique réutilise sa sortie ; aucun retry facturé implicite."""
    demande = {
        'personne': personne, 'lieu_rs': lieu_rs, 'annee': annee,
        'contexte_client': {k: v for k, v in (contexte_client or {}).items() if str(v).strip()},
    }
    with verrou_demande(demande, stockage_dir) as dossier:
        resultat = lire_json(dossier, 'rapport.json')
        if resultat is not None:
            controle = _controler_avant_livraison(
                dossier, resultat['texte_markdown'], lire_json(dossier, 'preparation.json'))
            return replace(RapportRevolutionSolaire(**resultat), controle_factualite=controle)
        if not autoriser_generation:
            raise GenerationAbsente('Confirme la génération avant de lancer le rapport.')
        ecrire_json(dossier, 'demande.json', demande)
        rapport = _generer_rapport_revolution_solaire(dossier=dossier, **demande)
        ecrire_json(dossier, 'rapport.json', asdict(rapport))
        return rapport
