"""Migration additive des comptes existants, utilisable avant le démarrage web."""
from sqlalchemy import inspect, text


COLONNES_AUTH = {
    "mot_de_passe_hash": "VARCHAR(512)",
    "version_auth": "INTEGER NOT NULL DEFAULT 0",
    "mot_de_passe_modifie_le": "TIMESTAMP WITH TIME ZONE",
}


def ajouter_colonnes_auth(connexion):
    existantes = {c["name"] for c in inspect(connexion).get_columns("utilisateurs_espace")}
    ajoutees = []
    for nom, definition in COLONNES_AUTH.items():
        if nom in existantes:
            continue
        if connexion.dialect.name == "sqlite" and nom == "mot_de_passe_modifie_le":
            definition = "DATETIME"
        # Noms et types statiques du moteur, aucune donnée utilisateur interpolée.
        connexion.execute(text(f"ALTER TABLE utilisateurs_espace ADD COLUMN {nom} {definition}"))
        ajoutees.append(nom)
    return ajoutees
