"""Point d'entrée Railway : ajoute l'espace personnel à l'application existante."""

from main import app

try:
    from routes.espace_personnel import espace_personnel_bp

    app.register_blueprint(espace_personnel_bp)
    from routes.admin_lunaisons import admin_lunaisons_bp
    app.register_blueprint(admin_lunaisons_bp)
    from routes.archives_mails import archives_mails_bp
    app.register_blueprint(archives_mails_bp)
    from routes.communaute import communaute_bp
    app.register_blueprint(communaute_bp)
    from routes.outils_membres import outils_membres_bp
    app.register_blueprint(outils_membres_bp)
except Exception:
    app.logger.exception("Espace personnel indisponible ; application principale conservée")

from services.revolution_solaire_worker import demarrer_relances_rs
demarrer_relances_rs(app)
