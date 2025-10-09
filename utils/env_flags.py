# utils/env_flags.py
import os

def env_bool(name: str, default="off") -> bool:
    """Lit une variable d'env et la convertit en booléen proprement."""
    return (os.getenv(name, default) or "").strip().lower() in {"1", "true", "on", "yes"}