"""Emplacement des journaux privés de l'espace, séparé des assets publics."""
import os
from pathlib import Path
from flask import current_app


def racine_privee_espace():
    valeur = os.getenv("ESPACE_DOSSIER_PRIVE")
    chemin = Path(valeur) if valeur else Path(current_app.instance_path)
    if not chemin.is_absolute():
        raise ValueError("ESPACE_DOSSIER_PRIVE doit être un chemin absolu hors du dossier static.")
    chemin = chemin.resolve()
    public = Path(current_app.static_folder).resolve()
    if chemin == public or public in chemin.parents:
        raise ValueError("Le stockage privé de l'espace ne peut pas être dans static.")
    return chemin
