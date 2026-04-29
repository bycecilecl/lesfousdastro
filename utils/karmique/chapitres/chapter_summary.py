# utils/karmique/chapitres/chapter_summary.py

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_MEMORY_MARKERS = [
    "THÈMES TRAITÉS",
    "ANGLE UTILISÉ",
    "CE QUI A ÉTÉ MIS EN AVANT",
    "À NE PAS RÉPÉTER",
    "ANGLE À PRIVILÉGIER ENSUITE",
]

_SUMMARY_FALLBACK_LENGTH = 280


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------
 
def _call_safe(
    call_llm: Callable[[str], str],
    prompt: str,
    context: str = "",
) -> str:
    """Appelle le LLM avec gestion d'erreur centralisée."""
    try:
        return (call_llm(prompt) or "").strip()
    except Exception:
        logger.exception("Erreur LLM — contexte : %s", context)
        return ""
 
 
def _extract_json_list(raw: str) -> Optional[List[str]]:
    """
    Extrait une liste JSON depuis une réponse LLM potentiellement bruitée.
    Cherche le premier '[' et le dernier ']' pour absorber le texte parasite
    avant/après sans être trompé par des crochets imbriqués.
    """
    start = raw.find("[")
    end = raw.rfind("]")
 
    if start == -1 or end == -1 or end <= start:
        return None
 
    try:
        items = json.loads(raw[start : end + 1])
        if isinstance(items, list):
            return items
    except json.JSONDecodeError:
        logger.debug("_extract_json_list : JSON invalide dans la réponse LLM.")
 
    return None
 
 
def _validate_memory_format(text: str) -> bool:
    """
    Vérifie que la mémoire éditoriale contient les marqueurs attendus.
    Validation souple sur mots-clés (pas libellés exacts) pour absorber
    les légères variations de formulation du LLM.
    """
    return all(marker in text for marker in _MEMORY_MARKERS)
 
 
def _truncate_text(text: str, max_len: int = _SUMMARY_FALLBACK_LENGTH) -> str:
    """Tronque proprement sans couper un mot."""
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."
 
 
# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------
 
def extract_psychological_themes(
    chapter_title: str,
    chapter_text: str,
    call_llm: Optional[Callable[[str], str]] = None,
) -> List[str]:
    """
    Extrait 3 à 5 thèmes psychologiques courts d'un chapitre.
    Retourne une liste vide si le LLM est absent ou si la réponse est inexploitable.
    """
    if not chapter_text or not call_llm:
        return []
 
    prompt = f"""
Tu lis un chapitre d'analyse karmique.
 
Ta mission :
extraire uniquement 3 à 5 thèmes psychologiques majeurs déjà abordés dans ce texte.
 
Règles strictes :
- Réponds UNIQUEMENT en JSON.
- Format attendu : ["thème 1", "thème 2", "thème 3"]
- Chaque thème doit être court : 2 à 6 mots maximum.
- Pas de phrase complète.
- Pas de jargon astrologique.
- Pas de ponctuation finale.
- Pas de doublons.
- Les thèmes doivent être psychologiques, concrets et réutilisables pour éviter les redondances dans les chapitres suivants.
 
Titre du chapitre :
{chapter_title}
 
Texte :
{chapter_text}
""".strip()
 
    raw = _call_safe(call_llm, prompt, context=f"extract_themes | {chapter_title}")
 
    if not raw:
        return []
 
    items = _extract_json_list(raw)
 
    if not items:
        logger.warning(
            "extract_psychological_themes : réponse non parseable pour '%s'. raw=%r",
            chapter_title,
            raw[:200],
        )
        return []
 
    cleaned: List[str] = []
    for x in items:
        if isinstance(x, str):
            x = x.strip().lower()
            if x and x not in cleaned:
                cleaned.append(x)
 
    result = cleaned[:5]
    logger.debug("extract_psychological_themes | '%s' → %s", chapter_title, result)
    return result
 
 
def summarize_chapter(
    chapter_title: str,
    chapter_text: str,
    call_llm: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Résume un chapitre karmique en 2 à 3 phrases maximum.
    Fallback sur version tronquée si le LLM est absent ou échoue.
    """
    clean_text = (chapter_text or "").strip()
 
    if not clean_text:
        return ""
 
    def _fallback() -> str:
        short = clean_text.replace("\n", " ").strip()
        return _truncate_text(short)
 
    if not call_llm:
        return _fallback()
 
    prompt = f"""
Tu résumes le chapitre suivant d'une analyse karmique.
 
Titre : {chapter_title}
 
Texte :
{clean_text}
 
Consignes :
- Ne fais pas un résumé vague applicable à tout le monde — reste ancré dans ce texte précis.
- Résume en 2 ou 3 phrases maximum.
- Garde uniquement l'idée centrale.
- Ton clair, direct, incarné.
- Pas de jargon inutile.
- Pas de répétition décorative.
- Pas de liste.
- Tutoiement.
""".strip()
 
    result = _call_safe(call_llm, prompt, context=f"summarize_chapter | {chapter_title}")
 
    if result:
        logger.debug("summarize_chapter | '%s' → %r", chapter_title, result[:120])
        return result
 
    logger.warning(
        "summarize_chapter : LLM vide/échec pour '%s', fallback tronqué utilisé.",
        chapter_title,
    )
    return _fallback()
 
 
def summarize_editorial_memory(
    chapter_title: str,
    chapter_text: str,
    call_llm: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Génère une mémoire contextuelle structurée pour éviter les redondances
    dans les chapitres suivants.
 
    Valide que le retour LLM respecte le format attendu (validation souple).
    Retourne une string vide si le format est invalide.
    """
    clean_text = (chapter_text or "").strip()
 
    if not clean_text or not call_llm:
        return ""
 
    prompt = f"""
Tu lis un chapitre d'analyse psychologique/karmique déjà rédigé.
 
Ta mission : produire une mémoire de contexte courte mais vraiment utile, pour empêcher les chapitres suivants de radoter et pour orienter leur angle.
 
Règles strictes :
- Zéro jargon astrologique.
- Pas de blabla.
- Style clair, compact, exploitable par un autre rédacteur.
- Va au fond des choses : ne reste pas à des mots trop vagues.
- Le but est d'aider le chapitre suivant à se différencier.
 
Renvoie UNIQUEMENT ce format strict (sans rien avant ni après) :
 
- THÈMES TRAITÉS : [3 à 6 thèmes psychologiques vraiment précis]
- ANGLE UTILISÉ : [1 phrase courte expliquant le prisme dominant du chapitre]
- CE QUI A ÉTÉ MIS EN AVANT : [1 phrase courte sur ce que le texte a surtout insisté]
- À NE PAS RÉPÉTER : [3 à 6 idées déjà suffisamment développées]
- ANGLE À PRIVILÉGIER ENSUITE : [1 phrase courte indiquant le meilleur angle complémentaire pour les chapitres suivants]
 
Titre du chapitre :
{chapter_title}
 
Texte :
{clean_text}
""".strip()
 
    result = _call_safe(call_llm, prompt, context=f"summarize_editorial_memory | {chapter_title}")
 
    if not result:
        return ""
 
    if not _validate_memory_format(result):
        logger.warning(
            "summarize_editorial_memory : format invalide pour '%s'. "
            "Marqueurs manquants. Mémoire écartée. raw=%r",
            chapter_title,
            result[:300],
        )
        return ""
 
    logger.debug("summarize_editorial_memory | '%s' → OK", chapter_title)
    return result