"""Interface Amour utilisant Claude 5.5 sans changer le modèle des autres rapports."""
from utils.claude_llm import (
    CLIENT, BlocTronqueError, ask_claude as _ask_claude,
)

MODEL = "claude-sonnet-5-5"


def ask_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = 1200,
    temperature: float = 0.7,
    single_attempt: bool = False,
) -> str:
    return _ask_claude(
        prompt=prompt, system=system, max_tokens=max_tokens,
        temperature=temperature, single_attempt=single_attempt, model=MODEL,
    )
