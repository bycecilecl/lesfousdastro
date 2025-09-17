import os

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

def rag_enabled() -> bool:
    # Par défaut OFF si la variable n’existe pas
    return _env_bool("ENABLE_RAG", False)
