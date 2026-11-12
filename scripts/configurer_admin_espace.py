"""Migration et attribution explicite du seul compte administratrice, sans Flask ni IA."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, inspect, text


BASE_LOCALE = Path(__file__).resolve().parents[1] / "instance" / "journal.db"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cible = parser.add_mutually_exclusive_group()
    cible.add_argument("--base", type=Path, help="Base SQLite ; par défaut instance/journal.db.")
    cible.add_argument("--database-url-env", help="Nom de la variable contenant l’URL de la base de production.")
    parser.add_argument("--email", help="Adresse exacte du compte existant à rendre administratrice.")
    parser.add_argument("--retirer", action="store_true", help="Retire le droit au compte indiqué.")
    parser.add_argument("--apply", action="store_true", help="Applique ; sinon inspection uniquement.")
    args = parser.parse_args()
    if args.retirer and not args.email:
        parser.error("--retirer nécessite --email.")
    base = None
    if args.database_url_env:
        url = os.getenv(args.database_url_env, "")
        if not url:
            parser.error("La variable de base demandée est absente.")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
            parser.error("Cette option est réservée à PostgreSQL ; utilise --base pour SQLite.")
        print("Cible : PostgreSQL, URL et identifiants masqués.")
    else:
        base = (args.base or BASE_LOCALE).expanduser().resolve()
        if not base.is_file():
            parser.error("Base SQLite existante requise. Aucun fichier créé.")
        url = "sqlite:///" + str(base)
        print(f"Cible SQLite : {base}")
    moteur = create_engine(url, echo=False, hide_parameters=True)
    try:
        # Valider le compte avant toute mutation ou sauvegarde.
        with moteur.connect() as connexion:
            colonnes = {c["name"] for c in inspect(connexion).get_columns("utilisateurs_espace")}
            if not {"id", "email", "actif", "version_auth", "mot_de_passe_hash"}.issubset(colonnes):
                raise ValueError("Migration des mots de passe requise avant le droit administratrice.")
            compte = None
            if args.email:
                comptes = connexion.execute(text(
                    "SELECT id, actif, mot_de_passe_hash FROM utilisateurs_espace "
                    "WHERE lower(trim(email)) = :email"
                ), {"email": args.email.strip().lower()}).mappings().all()
                if len(comptes) != 1:
                    raise ValueError("L’adresse doit identifier exactement un compte existant.")
                compte = comptes[0]
                if not args.retirer and (compte["actif"] != 1 or not compte["mot_de_passe_hash"]):
                    raise ValueError("Le compte doit être actif et avoir un mot de passe avant attribution.")
                print(f"Compte ciblé : ID {compte['id']} ; action : {'retirer' if args.retirer else 'attribuer'}.")
            print("Champ administratrice : " + ("présent" if "est_administratrice" in colonnes else "à ajouter (non par défaut)"))
        if not args.apply:
            print("Inspection terminée. Aucune modification ; ajoute --apply pour appliquer.")
            return
        if base:
            sauvegarde = base.with_name(base.name + ".backup-admin-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%f"))
            with sqlite3.connect(base) as source, sqlite3.connect(sauvegarde) as destination:
                source.backup(destination)
            print(f"Sauvegarde : {sauvegarde}")
        with moteur.connect() as connexion:
            if connexion.dialect.name == "sqlite":
                connexion.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                connexion.execute(text("LOCK TABLE utilisateurs_espace IN SHARE ROW EXCLUSIVE MODE"))
            try:
                colonnes = {c["name"] for c in inspect(connexion).get_columns("utilisateurs_espace")}
                if "est_administratrice" not in colonnes:
                    connexion.execute(text("ALTER TABLE utilisateurs_espace ADD COLUMN est_administratrice BOOLEAN NOT NULL DEFAULT FALSE"))
                connexion.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_espace_administratrice_unique ON utilisateurs_espace (est_administratrice) WHERE est_administratrice = TRUE"))
                if compte:
                    if not args.retirer:
                        autre = connexion.execute(text("SELECT id FROM utilisateurs_espace WHERE est_administratrice = TRUE AND id <> :id"), {"id": compte["id"]}).first()
                        if autre:
                            raise ValueError("Un autre compte possède déjà le droit. Aucun remplacement automatique.")
                    # Invalide les anciennes sessions, y compris celles du sélecteur DEV.
                    connexion.execute(text(
                        "UPDATE utilisateurs_espace SET est_administratrice = :droit, version_auth = version_auth + 1 "
                        "WHERE id = :id AND est_administratrice <> :droit"
                    ), {"droit": not args.retirer, "id": compte["id"]})
                connexion.commit()
            except Exception:
                connexion.rollback()
                raise
        print("Configuration enregistrée. Après un changement de droit, reconnecte-toi avec ton mot de passe.")
        print("Aucun mot de passe affiché, aucun appel IA ni envoi.")
    finally:
        moteur.dispose()


if __name__ == "__main__":
    try:
        main()
    except ValueError as erreur:
        raise SystemExit(str(erreur))
    except Exception:
        raise SystemExit("Configuration interrompue. Vérifie la connexion et le schéma de la base ; aucune URL ni clé affichée.")
