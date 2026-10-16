"""Nouvelle RS V2 : dossier factuel, analyses séparées et contrôles bloquants.

Ce paquet n'est pas branché sur le parcours de vente historique.
"""

from .dossier import calculer_dossier_factuel_rs

__all__ = ["calculer_dossier_factuel_rs"]
