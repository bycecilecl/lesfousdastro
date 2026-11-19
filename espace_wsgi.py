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
    from routes.admin_essais_mails import admin_essais_mails_bp
    app.register_blueprint(admin_essais_mails_bp)
    from routes.admin_envois_automatiques import admin_envois_automatiques_bp
    app.register_blueprint(admin_envois_automatiques_bp)
except Exception:
    app.logger.exception("Espace personnel indisponible ; application principale conservée")

from services.mails_evenements_worker import demarrer_mails_evenements
demarrer_mails_evenements(app)

from services.revolution_solaire_worker import demarrer_relances_rs
demarrer_relances_rs(app)
