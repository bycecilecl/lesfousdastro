from utils.claude_llm import ask_claude


def ask_llm(
    prompt: str,
    system: str = "",
    max_tokens: int = 1200,
    temperature: float = 0.7,
    retries: int = 3,
    min_backoff: float = 1.5,
) -> str:
    """Client Claude réservé au Point Astral Famille."""
    return ask_claude(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )