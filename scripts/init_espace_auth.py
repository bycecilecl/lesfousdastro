"""Crée les tables de l'espace personnel sans modifier les tables existantes.

La commande de démarrage Railway exécute ce script avant Gunicorn. Les
redémarrages suivants ne modifient pas les tables déjà présentes.
"""

import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, text


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.espace_personnel import (  # noqa: E402
    AbonnementEspace, AnalysePersonnelle, CommandeAnalyseEspace,
    CycleLunaire, CycleSolaire, DroitAnalyseAchetee, EmailCycleAbonnement,
    EnjeuPeriode, EntreeJournal, FichierAnalyse, LienConnexionEspace,
    MecanismeExploration, ObservationMecanisme, ProfilAstral,
    SectionAnalyse, SuggestionMecanisme, UtilisateurEspace,
)
from models.bd_comments import BdComment  # noqa: E402


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
                tables=[
                    UtilisateurEspace.__table__,
                    LienConnexionEspace.__table__,
                    ProfilAstral.__table__,
                    AbonnementEspace.__table__,
                    CycleLunaire.__table__,
                    CycleSolaire.__table__,
                    EmailCycleAbonnement.__table__,
                    AnalysePersonnelle.__table__,
                    DroitAnalyseAchetee.__table__,
                    CommandeAnalyseEspace.__table__,
                    SectionAnalyse.__table__,
                    EnjeuPeriode.__table__,
                    SuggestionMecanisme.__table__,
                    MecanismeExploration.__table__,
                    ObservationMecanisme.__table__,
                    EntreeJournal.__table__,
                    FichierAnalyse.__table__,
                    BdComment.__table__,
                ],
                checkfirst=True,
            )
    finally:
        moteur.dispose()
    print("Tables de l'espace personnel vérifiées.")


if __name__ == "__main__":
    main()
