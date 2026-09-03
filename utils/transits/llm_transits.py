import logging
from utils.llm_client import ask_llm
from utils.llm_system_prompts import SYSTEM_BASE
from .prompts import construire_prompt_bloc_transits


logger = logging.getLogger(__name__)

class ErreurGenerationTransits(RuntimeError):
    """Le calcul astrologique a réussi, mais le texte LLM est indisponible."""

# def generer_interpretation_llm_transit(
#     transit,
#     interpretation_structuree: str,
# ) -> str:
#     """
#     Génère une interprétation fluide d'un transit via le LLM.
#     Retourne l'interprétation structurée en cas d'échec.
#     """
#     prompt = construire_prompt_transit_brady(transit, interpretation_structuree)

#     try:
#         reponse = interroger_llm(prompt)
#         if not reponse:
#             return interpretation_structuree
#         return reponse.strip()

#     except Exception as e:
#         logger.error(f"Erreur LLM transit ({transit}): {e}", exc_info=True)
#         return interpretation_structuree


def generer_bloc_transits_llm(
    transits: list,
    interpretations_structurees: list[str],
    nom: str = "la personne",
    ascendant: str | None = None,
    dynamiques_periode: dict | None = None,
    genre: str | None = None,
) -> str:
    """
    Génère un bloc complet d'analyse de transits en un seul appel LLM.
    Retourne la concaténation des interprétations structurées en cas d'échec.
    """
    prompt = construire_prompt_bloc_transits(
        transits,
        interpretations_structurees,
        nom=nom,
        ascendant=ascendant,
        dynamiques_periode=dynamiques_periode,
        genre=genre,
    )

    try:
        reponse = ask_llm(
            prompt=prompt,
            system=SYSTEM_BASE,
            max_tokens=1800,
            temperature=0.7,
        )
        if not reponse:
            raise ErreurGenerationTransits(
                "La génération du texte est temporairement indisponible."
            )
        return reponse.strip()

    except ErreurGenerationTransits:
        raise
    except Exception as e:
        logger.error(f"Erreur LLM bloc transits : {e}", exc_info=True)
        raise ErreurGenerationTransits(
            "La génération du texte est temporairement indisponible."
        ) from e
