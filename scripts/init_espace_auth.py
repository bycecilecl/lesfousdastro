"""Crée uniquement les deux premières tables de l'espace personnel.

La commande de démarrage Railway exécute ce script avant Gunicorn. Les
redémarrages suivants ne modifient pas les tables déjà présentes.
"""

import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, text


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.espace_personnel import LienConnexionEspace, UtilisateurEspace  # noqa: E402


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL est nécessaire avant l'ouverture de l'espace.")
    moteur = create_engine(database_url, pool_pre_ping=True)
    try:
        with moteur.begin() as connexion:
            if moteur.dialect.name == "postgresql":
                connexion.execute(text("SELECT pg_advisory_xact_lock(62101420)"))
            UtilisateurEspace.metadata.create_all(
                bind=connexion,
                tables=[UtilisateurEspace.__table__, LienConnexionEspace.__table__],
                checkfirst=True,
            )
    finally:
        moteur.dispose()
    print("Tables de connexion de l'espace personnel vérifiées.")


if __name__ == "__main__":
    main()
