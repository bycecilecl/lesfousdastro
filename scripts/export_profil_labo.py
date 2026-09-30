"""Exporte un profil du labo vers un JSON privé, sans l'ajouter au dépôt Git.

Exemple :
    python scripts/export_profil_labo.py --source /chemin/journal.db \
        --email personne@example.com --sortie /private/tmp/profil.json
"""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile


CHAMPS = (
    "prenom", "date_naissance", "heure_naissance", "ville_naissance",
    "fuseau_horaire", "latitude", "longitude", "ville_cycles",
    "fuseau_cycles", "latitude_cycles", "longitude_cycles", "theme_natal",
    "situation_foyer", "situation_amour", "situation_travail",
    "situation_enfants", "situation_sante", "preoccupation_actuelle",
)


def exporter(source: Path, email: str, sortie: Path) -> None:
    email = email.strip().lower()
    with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as connexion:
        connexion.row_factory = sqlite3.Row
        ligne = connexion.execute(
            """SELECT p.* FROM profil_astral p
               JOIN utilisateurs_espace u ON u.id = p.utilisateur_id
               WHERE lower(u.email) = ?""",
            (email,),
        ).fetchone()
        abonnement = connexion.execute(
            """SELECT a.formule, a.statut, a.date_debut, a.date_fin, a.source
               FROM abonnements_espace a JOIN utilisateurs_espace u ON u.id = a.utilisateur_id
               WHERE lower(u.email) = ?""",
            (email,),
        ).fetchone()
    if ligne is None:
        raise ValueError("Aucun profil lié à cette adresse dans le labo.")
    profil = {champ: ligne[champ] for champ in CHAMPS}
    if not isinstance(json.loads(profil["theme_natal"] or "null"), dict):
        raise ValueError("Le thème natal du labo est absent ou invalide.")
    contenu = json.dumps(
        {
            "version": 2, "email": email, "profil": profil,
            "abonnement": dict(abonnement) if abonnement is not None else None,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=sortie.parent,
        prefix=".profil-", suffix=".tmp", delete=False,
    ) as temporaire:
        os.chmod(temporaire.name, 0o600)
        temporaire.write(contenu)
        chemin_temporaire = Path(temporaire.name)
    chemin_temporaire.replace(sortie)
    print(f"Profil exporté dans {sortie} ({sortie.stat().st_size} octets).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()
    exporter(args.source, args.email, args.sortie)
