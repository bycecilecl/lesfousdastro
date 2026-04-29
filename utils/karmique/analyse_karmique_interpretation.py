from __future__ import annotations
import logging
from typing import Any, Dict, List, Callable, Optional


from utils.karmique.chapitres.noeuds_lunaires import interpret_block_lunar_nodes_llm
from utils.karmique.chapitres.intro import interpret_intro_karmique
from utils.karmique.chapitres.luminaires_karmiques import interpret_block_luminaires_karmiques_llm
from utils.karmique.chapitres.maison_12 import interpret_block_maison_12_llm
from utils.karmique.chapitres.maison_8 import interpret_block_maison_8_llm
from utils.karmique.chapitres.maison_4 import interpret_block_maison_4_llm
from utils.karmique.chapitres.retrogrades import interpret_block_retrogrades_llm
from utils.karmique.chapitres.lune_noire import interpret_block_lune_noire_llm
from utils.karmique.chapitres.chiron import interpret_block_chiron_llm
from utils.karmique.chapitres.interceptions import interpret_block_interceptions_llm
from utils.karmique.chapitres.axe_portes import interpret_block_axe_portes_llm
from utils.karmique.chapitres.conclusion import interpret_block_synthese_karmique_llm
from utils.karmique.chapitres.chapter_summary import summarize_chapter, summarize_editorial_memory,  extract_psychological_themes
from utils.karmique.chapitres.saturne_pluton import interpret_block_saturne_pluton_llm
from utils.karmique.chapitres.part_fortune import interpret_block_part_fortune_llm
from utils.karmique.chapitres.potentiels_karmiques import interpret_block_potentiels_karmiques_llm
from utils.openai_utils import interroger_llm
from utils.karmique.checkpoint_utils import (
    build_checkpoint_id,
    get_checkpoint_path_for_analysis,
    get_blocks_dir_for_analysis,
    load_checkpoint,
    upsert_block_in_checkpoint,
    save_block_txt,
)
from utils.llm_system_prompts import SYSTEM_KARMIQUE
logger = logging.getLogger(__name__)

def _update_global_memory(global_ctx: Dict[str, Any], block: Dict[str, Any]) -> None:
    bid = block.get("id") or block.get("key")
    final_txt = (block.get("llm_content") or block.get("content") or "").strip()

    if not final_txt:
        return

    global_ctx.setdefault("memoires_contextuelles", [])

    context_memory = block.get("context_memory")
    if context_memory:
        existing_memories = global_ctx.get("memoires_contextuelles", [])
        if context_memory not in existing_memories:
            existing_memories.append(context_memory)
            global_ctx["memoires_contextuelles"] = existing_memories


def interpret_all(
    blocks: List[Dict[str, Any]],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Optional[Callable[..., str]] = None,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Interprète les blocs karmiques avec le LLM
    + met chaque bloc en cache immédiatement
    + réutilise les blocs déjà générés si disponibles.
    """
    out: List[Dict[str, Any]] = []

    if global_ctx is None:
        global_ctx = {}

    global_ctx.setdefault("themes_deja_traites", [])
    global_ctx.setdefault("axe_karmique_central", "")
    global_ctx.setdefault("memoires_contextuelles", [])
    global_ctx["all_blocks_for_conclusion"] = blocks

    checkpoint_id = build_checkpoint_id(
        nom=theme.get("nom", ""),
        date=theme.get("date", ""),
        heure=(global_ctx or {}).get("heure_naissance", ""),
        lieu=(global_ctx or {}).get("lieu_naissance", ""),
    )

    checkpoint_path = get_checkpoint_path_for_analysis(checkpoint_id)
    blocks_dir = get_blocks_dir_for_analysis(checkpoint_id)

    checkpoint = load_checkpoint(checkpoint_path)
    cached_blocks = {}

    for cached in (checkpoint.get("blocks", []) or []):
        cached_bid = cached.get("id") or cached.get("key")
        if cached_bid:
            cached_blocks[cached_bid] = cached

    tonalite = (global_ctx.get("tonalite") or "tu").strip().lower()
    g_raw = (global_ctx.get("genre") or global_ctx.get("sexe") or "").strip().lower()

    if g_raw.startswith(("f", "w")):
        genre_label = "femme"
    elif g_raw.startswith(("m", "h")) or g_raw in ("male", "homme"):
        genre_label = "homme"
    else:
        genre_label = "homme"

    global_ctx["tonalite"] = tonalite
    global_ctx["genre_label"] = genre_label

    if call_llm is None:
        def call_llm(prompt: str) -> str:
            return interroger_llm(prompt, system_prompt=SYSTEM_KARMIQUE)

    for b in blocks:
        bb = dict(b)
        bid = bb.get("id") or bb.get("key")

        if not bid:
            logger.warning("Bloc sans id/key ignoré pour le cache")
            out.append(bb)
            continue

        cached_block = cached_blocks.get(bid)
        if cached_block and (cached_block.get("llm_content") or "").strip():
            logger.debug("Bloc récupéré depuis le cache : %s", bid)
            out.append(cached_block)
            _update_global_memory(global_ctx, cached_block)
            continue

        try:
            if bid == "intro_karmique":
                bb["llm_content"] = interpret_intro_karmique(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "lunar_nodes":
                bb["llm_content"] = interpret_block_lunar_nodes_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "luminaires_karmiques":
                logger.debug(
                    "LUMINAIRES | has_call_llm=%s | content_len=%s",
                    callable(call_llm),
                    len((bb.get("content") or "").strip()),
                )
                bb["llm_content"] = interpret_block_luminaires_karmiques_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )
                logger.debug(
                    "LUMINAIRES | llm_content_len=%s",
                    len((bb.get("llm_content") or "").strip()),
                )

            elif bid == "maison_12":
                bb["llm_content"] = interpret_block_maison_12_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "maison_8":
                logger.debug(
                    "MAISON_8 | content_llm_preview=%r | has_call_llm=%s",
                    bb.get("content_llm", "")[:200],
                    callable(call_llm),
                )
                bb["llm_content"] = interpret_block_maison_8_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )            

            elif bid == "maison_4":
                bb["llm_content"] = interpret_block_maison_4_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "retrogrades":
                bb["llm_content"] = interpret_block_retrogrades_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "lune_noire":
                bb["llm_content"] = interpret_block_lune_noire_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "axe_portes":
                bb["llm_content"] = interpret_block_axe_portes_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "chiron":
                bb["llm_content"] = interpret_block_chiron_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "interceptions":
                bb["llm_content"] = interpret_block_interceptions_llm(
                    bb,
                    theme,
                    score,
                    call_llm=call_llm,
                    global_ctx=global_ctx,
                )

            elif bid == "saturne_pluton":
                bb["llm_content"] = interpret_block_saturne_pluton_llm(
                    bb, theme, score, call_llm, global_ctx
                )

            elif bid == "part_fortune":
                bb["llm_content"] = interpret_block_part_fortune_llm(
                    bb, theme, score, call_llm, global_ctx
                )

            elif bid == "synthese_karmique":
                bb["llm_content"] = interpret_block_synthese_karmique_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            elif bid == "potentiels_karmiques":
                bb["llm_content"] = interpret_block_potentiels_karmiques_llm(
                    bb, theme, score, call_llm=call_llm, global_ctx=global_ctx
                )

            else: 
                bb.pop("llm_content", None)

            final_txt = (bb.get("llm_content") or bb.get("content") or "").strip()

            if final_txt and bid not in ("header", "synthese_karmique"):
                summary = summarize_chapter(
                    chapter_title=bb.get("title", bid),
                    chapter_text=final_txt,
                    call_llm=call_llm,
                )
                bb["summary"] = summary

                themes_used = extract_psychological_themes(
                    chapter_title=bb.get("title", bid),
                    chapter_text=final_txt,
                    call_llm=call_llm,
                )
                bb["themes_used"] = themes_used

                context_memory = summarize_editorial_memory(
                    chapter_title=bb.get("title", bid),
                    chapter_text=final_txt,
                    call_llm=call_llm,
                )
                bb["context_memory"] = context_memory

                existing = global_ctx.get("themes_deja_traites", [])
                for theme_item in themes_used:
                    if theme_item not in existing:
                        existing.append(theme_item)

                global_ctx["themes_deja_traites"] = existing

            upsert_block_in_checkpoint(
                filepath=checkpoint_path,
                block_data=bb,
                error_on_block=None,
                error_message=None,
            )

            save_block_txt(bid, bb.get("llm_content", ""), base_dir=blocks_dir)

            if bid == "maison_8":
                logger.debug(
                    "FINAL BLOCK MAISON_8 | llm_content_preview=%r | content_preview=%r",
                    (bb.get("llm_content") or "")[:500],
                    (bb.get("content") or "")[:500],
                )

            out.append(bb)
            _update_global_memory(global_ctx, bb)

        except Exception as e:
            upsert_block_in_checkpoint(
                filepath=checkpoint_path,
                block_data=bb,
                error_on_block=bid,
                error_message=str(e),
            )
            raise

    return out