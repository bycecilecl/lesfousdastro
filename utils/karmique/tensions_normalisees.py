# utils/karmique/tensions_normalisees.py

from typing import Dict, Any, Callable, List
import logging

logger = logging.getLogger(__name__)


PROMPT_NORMALISATION_TENSIONS = """
Tu analyses un thème astrologique karmique.

Identifie les tensions psychologiques majeures présentes dans ce thème.
Retourne-les UNIQUEMENT sous forme de clés normalisées, choisies parmi cette liste :

- surcontrole
- suradaptation
- evitement_emotionnel
- difficulte_limites
- hypervigilance
- fusion
- blessure_trahison
- peur_abandon
- rapport_pouvoir
- illegitimite
- sacrifice_soi
- isolement_choisi
- perfectionnisme

Règles strictes :
- Retourne entre 1 et 5 clés maximum
- Une clé par ligne, aucun autre texte
- Pas d'explication, pas de commentaire
- Si une tension ne correspond à aucune clé, ignore-la

Exemple de sortie attendue :
surcontrole
peur_abandon
illegitimite
""".strip()

VALID_TENSION_KEYS = {
    "surcontrole",
    "suradaptation",
    "evitement_emotionnel",
    "difficulte_limites",
    "hypervigilance",
    "fusion",
    "blessure_trahison",
    "peur_abandon",
    "rapport_pouvoir",
    "illegitimite",
    "sacrifice_soi",
    "isolement_choisi",
    "perfectionnisme",
}


def generer_tensions_normalisees(
    theme_brief: str,
    axe_karmique: str,
    tensions_txt: str,
    call_llm: Callable[[str], str],
) -> List[str]:
    """
    Produit une liste de catégories de tensions normalisées.
    """

    prompt = f"""
{PROMPT_NORMALISATION_TENSIONS}

CONTEXTE :

Résumé du thème :
{theme_brief}

Axe karmique :
{axe_karmique}

Tensions détectées :
{tensions_txt}
""".strip()

    try:
        response = call_llm(prompt)

        lignes = [
            l.strip()
            for l in (response or "").splitlines()
            if l.strip()
        ]

        # Validation stricte des clés
        lignes = [l for l in lignes if l in VALID_TENSION_KEYS]

        # Déduplication propre
        lignes = list(dict.fromkeys(lignes))

        logger.debug(
            "Tensions normalisées générées | total=%s | valeurs=%s",
            len(lignes),
            lignes
        )

        return lignes[:5]

    except Exception:
        logger.exception("Erreur normalisation tensions")
        return []