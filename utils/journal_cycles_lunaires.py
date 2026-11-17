"""Traces privées par tentative de RL, sans appel IA à l'import."""
from datetime import datetime, timezone
import json
import os
import re
from uuid import uuid4

from utils.stockage_espace import racine_privee_espace


FICHIERS = {"requete.json", "reponse_brute.json", "usage.json", "controles.json", "erreur.json"}
FORMAT_EXECUTION = r"\d{8}T\d{6}-[a-f0-9]{12}"


def dossier_cycle(cycle_id):
    return racine_privee_espace() / "generations_cycles_lunaires" / str(int(cycle_id))


def nouvelle_tentative(cycle_id):
    execution = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
    # Les appels web fournissent l'id ; les anciens lanceurs ont aussi leurs traces.
    racine = dossier_cycle(cycle_id) if cycle_id is not None else (
        racine_privee_espace() / "generations_cycles_lunaires" / "sans-cycle"
    )
    dossier = racine / execution
    dossier.mkdir(parents=True, mode=0o700)
    return dossier


def ecrire_trace(dossier, nom, valeur):
    if nom not in FICHIERS:
        raise ValueError("Fichier de trace inconnu.")
    descripteur = os.open(dossier / nom, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
        fichier.write(json.dumps(valeur, ensure_ascii=False, indent=2, default=str))


def journaux_interpretation(cycle_id):
    racine = dossier_cycle(cycle_id)
    if not racine.is_dir():
        return []
    return [
        {"id": dossier.name, "fichiers": sorted(nom for nom in FICHIERS if (dossier / nom).is_file())}
        for dossier in sorted(racine.iterdir(), reverse=True)
        if dossier.is_dir() and re.fullmatch(FORMAT_EXECUTION, dossier.name)
    ]
