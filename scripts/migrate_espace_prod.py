"""Migration additive de l'espace personnel PostgreSQL, sans Flask ni moteur.

Sans option : inventaire en lecture seule. --apply : DDL transactionnel.
--check : refuse le démarrage si un élément du schéma est absent.
Aucun INSERT, UPDATE, DELETE, DROP ou transfert de données personnelles.
"""
import argparse
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


COLONNES = {
    "utilisateurs_espace": {
        "mot_de_passe_hash": "VARCHAR(512)",
        "version_auth": "INTEGER NOT NULL DEFAULT 0",
        "mot_de_passe_modifie_le": "TIMESTAMP WITH TIME ZONE",
        "autoriser_journal_mails": "BOOLEAN NOT NULL DEFAULT FALSE",
        "journal_mails_choix_le": "TIMESTAMP WITH TIME ZONE",
        "avatar_personnage": "VARCHAR(20)",
        "est_administratrice": "BOOLEAN NOT NULL DEFAULT FALSE",
    },
    "entrees_journal": {
        "est_periode": "BOOLEAN NOT NULL DEFAULT FALSE",
        "date_fin_periode": "DATE",
    },
    "emails_cycles_abonnement": {
        "cle_creneau": "VARCHAR(10)",
        "date_prevue": "TIMESTAMP WITH TIME ZONE",
        "fin_periode": "TIMESTAMP WITH TIME ZONE",
    },
    "analyses_personnelles": {"cycle_solaire_id": "INTEGER"},
}
NOUVELLES_TABLES = (
    "liens_mot_de_passe_espace", "limites_acces_espace",
    "analyses_lunaisons", "enjeux_annuels", "decodages_observations_mecanisme",
)
INDEX = {
    "uq_espace_administratrice_unique": (
        "utilisateurs_espace", "est_administratrice", "est_administratrice = TRUE",
    ),
    "uq_email_profil_creneau": (
        "emails_cycles_abonnement", "profil_id, cle_creneau", "cle_creneau IS NOT NULL",
    ),
}


def etat(connexion):
    inspection = inspect(connexion)
    tables = set(inspection.get_table_names())
    requises = set(COLONNES) | {"profil_astral", "fichiers_analyses_espace", "observations_mecanisme"}
    if not requises.issubset(tables):
        raise ValueError("La base ne possède pas toutes les tables historiques attendues. Aucune initialisation vide ni modification de données.")
    ajouts = []
    for table, colonnes in COLONNES.items():
        existantes = {c["name"] for c in inspection.get_columns(table)}
        ajouts.extend((table, nom, definition) for nom, definition in colonnes.items() if nom not in existantes)
    index = set()
    for table in {v[0] for v in INDEX.values()}:
        index.update(i["name"] for i in inspection.get_indexes(table))
        index.update(i["name"] for i in inspection.get_unique_constraints(table))
    return ajouts, [t for t in NOUVELLES_TABLES if t not in tables], [n for n in INDEX if n not in index]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise ValueError("DATABASE_URL PostgreSQL est requise. Aucune base locale ouverte ou créée.")
    moteur = create_engine(url, echo=False, hide_parameters=True, pool_pre_ping=True)
    try:
        with moteur.begin() as connexion:
            if not args.apply:
                connexion.execute(text("SET TRANSACTION READ ONLY"))
            else:
                connexion.execute(text("SET LOCAL lock_timeout = '15s'"))
                connexion.execute(text("SET LOCAL statement_timeout = '120s'"))
                connexion.execute(text("SELECT pg_advisory_xact_lock(62101421)"))
            colonnes, tables, index = etat(connexion)
            for table, nom, definition in colonnes:
                print(f"COLONNE : {table}.{nom} {definition}", flush=True)
            for table in tables:
                print(f"TABLE : {table}", flush=True)
            for nom in index:
                print(f"INDEX : {nom}", flush=True)
            if not (colonnes or tables or index):
                print("Schéma de l'espace à jour. Aucune donnée modifiée.", flush=True)
                return
            if args.check:
                raise ValueError("Schéma incomplet. Appliquer la migration additive avant de démarrer cette version.")
            if not args.apply:
                print("Inventaire uniquement. Aucune modification. --apply pour appliquer.", flush=True)
                return
            # Verrou bref : interdit qu'un autre processus modifie simultanément
            # les tables concernées pendant l'ajout de colonnes et d'index.
            connexion.execute(text("LOCK TABLE utilisateurs_espace, entrees_journal, emails_cycles_abonnement, analyses_personnelles IN SHARE ROW EXCLUSIVE MODE"))
            colonnes, tables, index = etat(connexion)
            for table, nom, definition in colonnes:
                connexion.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{nom}" {definition}'))
            # Imports de modèles seuls : aucun import de main, de routes ou d'IA.
            from models.espace_personnel import (
                AnalyseLunaison, DecodageObservationMecanisme, EnjeuAnnuel, LienMotDePasseEspace, LimiteAccesEspace,
            )
            modeles = {m.__tablename__: m.__table__ for m in (
                AnalyseLunaison, DecodageObservationMecanisme, EnjeuAnnuel, LienMotDePasseEspace, LimiteAccesEspace,
            )}
            for table in tables:
                modeles[table].create(bind=connexion, checkfirst=True)
            for nom in index:
                table, champs, filtre = INDEX[nom]
                doublon = connexion.execute(text(
                    f'SELECT 1 FROM "{table}" WHERE {filtre} GROUP BY {champs} HAVING COUNT(*) > 1 LIMIT 1'
                )).first()
                if doublon:
                    raise ValueError(f"Doublons incompatibles avec {nom}. Migration annulée ; aucune suppression automatique.")
                connexion.execute(text(f'CREATE UNIQUE INDEX "{nom}" ON "{table}" ({champs}) WHERE {filtre}'))
            restants = etat(connexion)
            if any(restants):
                raise ValueError("Schéma incomplet après préparation ; transaction annulée.")
        print("Migration validée : structure ajoutée, données existantes conservées. Aucun droit admin attribué.", flush=True)
    finally:
        moteur.dispose()


if __name__ == "__main__":
    try:
        main()
    except ValueError as erreur:
        raise SystemExit(str(erreur))
    except Exception:
        raise SystemExit("Migration interrompue, transaction annulée. Vérifier la connexion et le schéma ; aucune URL ni donnée personnelle affichée.")
