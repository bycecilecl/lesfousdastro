# config/analysis_sandbox.py
import os

def is_analysis_sandbox() -> bool:
    """
    True si on est en mode SANDBOX pour les analyses.
    (On ne lance pas les grosses générations LLM/PDF.)
    """
    return (os.getenv("ANALYSE_SANDBOX") or "").strip().lower() in ("1", "true", "yes", "on")