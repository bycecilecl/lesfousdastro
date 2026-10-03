import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
import logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

raw_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
CLEAN_API_KEY = raw_key.replace("\r", "").replace("\n", "").strip()

if not CLEAN_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY manquant. Vérifie ton .env à la racine.\n"
        f"Chemin lu : {DOTENV_PATH}"
    )

CLIENT = Anthropic(api_key=CLEAN_API_KEY)
logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

class BlocTronqueError(RuntimeError):
    def __init__(self, texte_partiel: str):
        self.texte_partiel = texte_partiel
        super().__init__(
            "Réponse Claude toujours tronquée après une seconde tentative."
        )

def ask_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = 1200,
    temperature: float = 0.7,
    single_attempt: bool = False,
    stop_sequences: list[str] | None = None,
) -> str:
    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    if system:
        kwargs["system"] = [
            {"type": "text", "text": system}
        ]

    if stop_sequences:
        kwargs["stop_sequences"] = stop_sequences

    client = CLIENT.with_options(max_retries=0) if single_attempt else CLIENT
    resp = client.messages.create(**kwargs)
    logger.info("Claude stop_reason=%s", resp.stop_reason)
    logger.info("Claude input_tokens=%s", resp.usage.input_tokens)
    logger.info("Claude output_tokens=%s", resp.usage.output_tokens)

    if single_attempt and resp.stop_reason == "max_tokens":
        raise BlocTronqueError(resp.content[0].text.strip())
    if single_attempt and resp.stop_reason not in {"end_turn", "stop_sequence"}:
        raise RuntimeError("Réponse Claude non terminée : aucun rapport à livrer.")

    if resp.stop_reason == "max_tokens":
        retry_max_tokens = int(max_tokens * 1.5)

        logger.warning(
            "Claude tronqué à %s tokens → nouvelle tentative avec %s tokens",
            max_tokens,
            retry_max_tokens,
        )

        kwargs["max_tokens"] = retry_max_tokens
        resp = CLIENT.messages.create(**kwargs)

        logger.info("Claude RETRY stop_reason=%s", resp.stop_reason)
        logger.info("Claude RETRY input_tokens=%s", resp.usage.input_tokens)
        logger.info("Claude RETRY output_tokens=%s", resp.usage.output_tokens)

        if resp.stop_reason == "max_tokens":
            logger.error(
                "Claude toujours tronqué après retry (%s tokens).",
                retry_max_tokens,
            )
            raise BlocTronqueError(
                resp.content[0].text.strip()
            )

    return resp.content[0].text.strip()
