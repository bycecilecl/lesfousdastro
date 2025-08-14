# utils/__init__.py
# Objectif : éviter les imports lourds au chargement du package (pas de warning quand on lance un sous-module avec `-m`)
# On expose des proxys "lazy" pour ne charger les modules qu'au premier appel.

from typing import TYPE_CHECKING

__all__ = [
    "extraire_points_forts",
    "calcul_theme",
]

# --- Proxys lazy (ne chargent le module ciblé que quand on appelle la fonction) ---

def extraire_points_forts(*args, **kwargs):
    from .utils_points_forts import extraire_points_forts as _impl
    return _impl(*args, **kwargs)

def calcul_theme(*args, **kwargs):
    from .calcul_theme import calcul_theme as _impl
    return _impl(*args, **kwargs)

# --- Hints pour les analyseurs statiques (facultatif, utile pour l'auto-complétion) ---
if TYPE_CHECKING:
    # Ces imports ne s'exécutent pas à runtime, mais aident l'IDE
    from .utils_points_forts import extraire_points_forts as extraire_points_forts  # type: ignore
    from .calcul_theme import calcul_theme as calcul_theme  # type: ignore