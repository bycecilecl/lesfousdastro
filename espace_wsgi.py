"""Point d'entrée Railway : ajoute l'espace personnel à l'application existante."""

from main import app

try:
    from routes.espace_personnel import espace_personnel_bp

    app.register_blueprint(espace_personnel_bp)
except Exception:
    app.logger.exception("Espace personnel indisponible ; application principale conservée")

from services.revolution_solaire_worker import demarrer_relances_rs
demarrer_relances_rs(app)
