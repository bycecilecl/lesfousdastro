# utils/karmique/_slug.py
"""Normalisation unique pour matcher la BDD."""
from typing import Any


def slug(s: Any) -> str:
    """
    Normalise un texte pour matcher les clés BDD.
    Ex: "Nœud Sud" → "noeud_sud", "Maison 7" → "7"
    """
    if s is None:
        return ""
    
    s = str(s).strip().lower()
    
    # Accents
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    s = s.replace("à", "a").replace("â", "a").replace("ä", "a")
    s = s.replace("î", "i").replace("ï", "i")
    s = s.replace("ô", "o").replace("ö", "o")
    s = s.replace("ù", "u").replace("û", "u").replace("ü", "u")
    s = s.replace("ç", "c")
    s = s.replace("œ", "oe")
    
    # Caractères spéciaux
    s = s.replace(" ", "_")
    s = s.replace("'", "")
    s = s.replace("'", "")
    
    return s


def house_int(v: Any) -> int | None:
    """
    Convertit une maison en int propre.
    Ex: "7.0" → 7, 7.5 → 7, "invalid" → None
    """
    if v is None:
        return None
    try:
        return int(float(v))
    except Exception:
        return None