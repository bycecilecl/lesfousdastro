from __future__ import annotations

from typing import List, Dict, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


def build_conclusion_from_summaries(
    blocks: List[Dict[str, Any]],
    call_llm: Optional[Callable[[str], str]] = None,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Génère la conclusion karmique finale à partir des summaries des chapitres.

    Retourne toujours :
    - long_conclusion
    """

    global_ctx = global_ctx or {}

    axe_central = (global_ctx.get("axe_karmique_central") or "").strip()
    theme_brief = (global_ctx.get("theme_brief") or "").strip()

    summaries = []
    included_titles = []
    excluded_titles = []

    for b in blocks:
        title = b.get("title") or b.get("id") or "Bloc sans titre"
        summary = (b.get("summary") or "").strip()

        if summary:
            if len(summary) > 800:
                logger.warning(
                    "CONCLUSION summary très long tronqué | title=%s | length=%s",
                    title,
                    len(summary),
                )
                summary = summary[:800]

            summaries.append(f"{title} : {summary}")
            included_titles.append(title)
        else:
            excluded_titles.append(title)

    logger.debug("CONCLUSION summaries retenus : %s", included_titles)
    logger.debug("CONCLUSION summaries absents/écartés : %s", excluded_titles)

    if not summaries:
        logger.warning("CONCLUSION impossible : aucun summary disponible.")
        return {
            "long_conclusion": "",
        }

    combined = "\n\n".join(summaries)

    contexte_global = ""

    if axe_central:
        contexte_global += f"\nAxe karmique central déjà identifié :\n{axe_central}\n"

    if theme_brief:
        contexte_global += f"\nRésumé global du thème :\n{theme_brief}\n"
    if not contexte_global.strip():
        contexte_global = "\nContexte global non disponible : la conclusion doit s'appuyer uniquement sur les summaries.\n"

    long_prompt = f"""
Tu rédiges l'épilogue final d'une analyse karmique.

C'est le moment de la synthèse finale : pas un résumé scolaire, mais une mise en perspective claire, profonde et utile.

{contexte_global}

Éléments extraits des chapitres précédents :
{combined}

OBJECTIF PSYCHOLOGIQUE :
- Ne résume pas les chapitres un par un.
- Dégage le fil rouge global du parcours intérieur de cette personne.
- Identifie la dynamique centrale : ce qu'elle répète, ce qu'elle protège, ce qu'elle évite, ce qu'elle cherche à transformer.
- Explique ce que la personne croit gagner en restant dans son ancien fonctionnement : sécurité, contrôle, loyauté, évitement, maîtrise, protection émotionnelle.
- Montre ce qu'elle risque à rester figée dans cette mécanique.
- Ouvre ensuite vers une voie de libération concrète, mature et incarnée.
- Le ton doit être celui d'un mentor lucide : direct, profond, sans complaisance, mais profondément empathique.

RÈGLES DE RÉDACTION STRICTES :
- AMNÉSIE ASTROLOGIQUE ABSOLUE : il est strictement interdit de mentionner des planètes, des signes, des maisons, des Nœuds ou des aspects.
- Traduis toute l'astrologie en psychologie, en comportements, en états intérieurs et en choix de vie.
- Texte en flux continu, dense et immersif.
- Environ 300 à 400 mots.
- Ne dis pas : "comme vu dans les chapitres précédents".
- Ne fais pas de liste.
- Ne termine pas par une morale.
- Termine sur une question ouverte, responsabilisante, tournée vers l'avenir et l'action.
IMPORTANT :
La question finale doit être SPECIFIQUE à cette personne.
Elle doit reprendre la contradiction centrale ou l’axe principal identifié.
Elle ne doit jamais être générique.

Axe central identifié :
{axe_central}

Conclusion psychologique finale :
""".strip()
    
    logger.debug(
        "CONCLUSION prompt final | length=%s | preview=%r",
        len(long_prompt),
        long_prompt[:1200],
    )

    long_conclusion = ""

    if call_llm:
        try:
            long_conclusion = (call_llm(long_prompt) or "").strip()
        except Exception as e:
            logger.exception("Erreur génération conclusion karmique : %r", e)

    return {
        "long_conclusion": long_conclusion,
    }


def interpret_block_synthese_karmique_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Optional[Callable[[str], str]] = None,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Génère la conclusion finale du rapport karmique à partir des summaries
    déjà présents dans les blocs.
    """

    if not call_llm:
        logger.warning("Conclusion karmique non générée : call_llm absent.")
        return ""

    global_ctx = global_ctx or {}

    blocks_for_conclusion = global_ctx.get("all_blocks_for_conclusion") or []

    logger.debug(
        "CONCLUSION blocks ids reçus : %s",
        [b.get("id") for b in blocks_for_conclusion]
    )

    for b in blocks_for_conclusion:
        logger.debug(
            "CONCLUSION summary check | id=%s | title=%s | has_summary=%s",
            b.get("id"),
            b.get("title"),
            bool((b.get("summary") or "").strip())
        )

    if not blocks_for_conclusion:
        logger.warning(
            "Conclusion karmique non générée : all_blocks_for_conclusion vide."
        )
        return ""

    conclusion = build_conclusion_from_summaries(
        blocks_for_conclusion,
        call_llm=call_llm,
        global_ctx=global_ctx,
    )

    return (conclusion.get("long_conclusion") or "").strip()