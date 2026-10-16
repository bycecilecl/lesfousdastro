"""Adaptateur Astro-form du parcours à six blocs, sans import de profil de test."""

from dataclasses import asdict
from pathlib import Path
import re
import shutil

from ...archives_generation import (
    GenerationAbsente, GenerationARevoir, ecrire_json, lire_json, verrou_demande,
)
from ...service import RapportRevolutionSolaire
from .execution import ROOT
from .execution_prompt_personnel import MODELE
from .export_pdf import ajouter_disclaimer_rs
from .parcours_complet import empreintes_code
from .parcours_prompt_personnel import lancer_rapport_prompts_personnels


VERSION = "rs_astro_form_six_parties_mc_separe_1"


def generer_rapport_formulaire(
    *, personne, lieu_rs, annee, contexte_client=None, stockage_dir=None,
    autoriser_generation=True, identifiant_execution=None,
):
    """Le POST confirmé lance le parcours ; le GET ne lit que le rapport archivé.

    Les calculs, prompts, réponses et PDF viennent du même parcours que les
    lanceurs manuels. Les fichiers de test et leurs profils ne sont pas importés.
    """
    if contexte_client is not None and not isinstance(contexte_client, dict):
        raise ValueError("Le contexte personnel doit être un dictionnaire.")
    contexte = {k: v for k, v in (contexte_client or {}).items() if str(v).strip()}
    cas = {"personne": personne, "lieu_rs": lieu_rs, "annee": annee, "contexte_client": contexte}
    demande = {"moteur": VERSION, "modele": MODELE, **cas, "code": empreintes_code()}
    if identifiant_execution:
        demande["identifiant_execution"] = identifiant_execution
    racine = Path(stockage_dir) if stockage_dir is not None else ROOT / "instance/generations_rs"
    with verrou_demande(demande, racine) as dossier:
        resultat = lire_json(dossier, "rapport.json")
        if isinstance(resultat, dict):
            print("ASTRO-FORM — rapport à six blocs déjà archivé ; aucun appel IA.")
            return RapportRevolutionSolaire(**resultat)
        if not autoriser_generation:
            etat = lire_json(dossier, "etat.json")
            if etat:
                raise GenerationARevoir(
                    "Le rapport n'est pas terminé. Les éléments reçus sont conservés ; "
                    "consulter cette page ne relance aucun appel IA."
                )
            raise GenerationAbsente("Confirme la génération avant de lancer le rapport.")
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "etat.json", {"statut": "en_cours", "moteur": VERSION})
        capture = {}

        def recevoir_parcours(chemin):
            capture["chemin"] = Path(chemin)
            ecrire_json(dossier, "source_parcours.json", {"chemin": str(chemin)})

        print("ASTRO-FORM — moteur à six blocs —", personne["nom"], annee)
        print("Archives du formulaire :", dossier)
        try:
            code = lancer_rapport_prompts_personnels(
                [cas], sur_dossier=recevoir_parcours, identifiant_execution=identifiant_execution)
            if code != 0 or "chemin" not in capture:
                raise GenerationARevoir(
                    "La génération s'est interrompue. Les textes et réponses reçus restent "
                    "archivés ; aucune relance automatique n'a été effectuée."
                )
            source = capture["chemin"]
            for nom in ("rapport_complet.md", "rapport_complet.html", "rapport_rs_v2.pdf"):
                fichier = source / nom
                if not fichier.is_file() or not fichier.stat().st_size:
                    raise GenerationARevoir(
                        "Le rapport n'est pas complet. Les textes reçus sont conservés ; aucun appel supplémentaire."
                    )
            factuel = lire_json(source, "dossier_factuel.json")
            texte = (source / "rapport_complet.md").read_text(encoding="utf-8")
            html = (source / "rapport_complet.html").read_text(encoding="utf-8")
            # Le bandeau d'archive n'appartient pas au rapport affiché au client.
            html = re.sub(r"<aside\b[^>]*>.*?</aside>", "", html, count=1, flags=re.I | re.S)
            html = ajouter_disclaimer_rs(html, personne=personne, annee=annee)
            shutil.copy2(source / "rapport_rs_v2.pdf", dossier / "rapport.pdf")
            (dossier / "rapport.md").write_text(texte, encoding="utf-8")
            (dossier / "rapport.html").write_text(html, encoding="utf-8")
            rapport = RapportRevolutionSolaire(
                texte_markdown=texte, html=html, releve_technique="",
                controle_factualite="Rapport à six blocs conservé ; aucune réécriture ni validation humaine automatique.",
                debut_cycle=factuel["cycle"]["debut_utc"][:10],
                fin_cycle=factuel["cycle"]["fin_utc"][:10],
                identifiant_generation=dossier.name,
            )
            ecrire_json(dossier, "rapport.json", asdict(rapport))
            ecrire_json(dossier, "etat.json", {"statut": "termine", "moteur": VERSION})
            print("ASTRO-FORM — rapport et PDF disponibles ; aucune réécriture supplémentaire.")
            return rapport
        except BaseException as exc:
            ecrire_json(dossier, "etat.json", {"statut": "interrompu", "type_erreur": type(exc).__name__, "moteur": VERSION})
            raise
