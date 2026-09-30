"""Exporte un brouillon de mail du labo sans l'ajouter au dépôt Git."""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile


CHAMPS_CYCLE = (
    "cle_cycle", "debut_cycle_utc", "fin_cycle_utc", "ville", "fuseau_horaire",
    "latitude", "longitude", "theme_technique", "interpretation", "statut",
)
CHAMPS_EMAIL = (
    "type_email", "objet", "contenu_texte", "contenu_html",
    "declencheur_factuel", "points_abordes", "question_journal", "date_generation",
)


def exporter(source: Path, email: str, cycle: str, type_email: str, sortie: Path) -> None:
    email = email.strip().lower()
    with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as connexion:
        connexion.row_factory = sqlite3.Row
        lignes = connexion.execute(
            """SELECT e.* FROM emails_cycles_abonnement e
               JOIN profil_astral p ON p.id = e.profil_id
               JOIN utilisateurs_espace u ON u.id = p.utilisateur_id
               JOIN cycles_lunaires c ON c.id = e.cycle_lunaire_id
               WHERE lower(u.email) = ? AND c.cle_cycle = ?
                 AND e.type_email = ? AND e.statut = 'brouillon'""",
            (email, cycle, type_email),
        ).fetchall()
        if len(lignes) != 1:
            raise ValueError("Il faut exactement un brouillon correspondant au compte et au cycle.")
        brouillon = lignes[0]
        cycle_lunaire = connexion.execute(
            "SELECT * FROM cycles_lunaires WHERE id = ?", (brouillon["cycle_lunaire_id"],)
        ).fetchone()
    paquet = {
        "version": 1,
        "email": email,
        "cycle": {champ: cycle_lunaire[champ] for champ in CHAMPS_CYCLE},
        "brouillon": {champ: brouillon[champ] for champ in CHAMPS_EMAIL},
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=sortie.parent,
        prefix=".email-", suffix=".tmp", delete=False,
    ) as temporaire:
        os.chmod(temporaire.name, 0o600)
        json.dump(paquet, temporaire, ensure_ascii=False, separators=(",", ":"))
        chemin_temporaire = Path(temporaire.name)
    chemin_temporaire.replace(sortie)
    print(f"Brouillon exporté dans {sortie} ({sortie.stat().st_size} octets).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--type-email", default="boussole_cycle")
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()
    exporter(args.source, args.email, args.cycle, args.type_email, args.sortie)
