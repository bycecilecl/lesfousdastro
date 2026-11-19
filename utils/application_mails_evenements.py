"""Application minimale du programme de mails, sans serveur ni autre moteur démarré."""
import os
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]


def creer_application():
    from dotenv import load_dotenv
    from flask import Flask
    from extensions import db

    load_dotenv(RACINE / ".env", override=False)
    railway = any(os.getenv(c) for c in ("RAILWAY_ENVIRONMENT_ID", "RAILWAY_SERVICE_ID"))
    if railway:
        uri = os.getenv("DATABASE_URL", "")
        if not uri.startswith(("postgres://", "postgresql://", "postgresql+psycopg")):
            raise ValueError("Le programme Railway exige la base PostgreSQL partagée avec l’espace abonné.")
        uri = uri.replace("postgres://", "postgresql://", 1)
    else:
        base = RACINE / "instance" / "journal.db"
        if not base.is_file():
            raise ValueError("Base locale du journal introuvable ; aucune base vide ne sera créée.")
        uri = "sqlite:///" + str(base)
    application = Flask("mails_evenements", root_path=str(RACINE),
                        instance_path=str(RACINE / "instance"), static_folder="static")
    application.config.update(SQLALCHEMY_DATABASE_URI=uri,
                              SQLALCHEMY_BINDS={"journal": uri},
                              SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(application)
    # Déclarations seules : aucun import de main, serveur, worker RS ou client IA.
    from models import espace_personnel  # noqa: F401
    return application
