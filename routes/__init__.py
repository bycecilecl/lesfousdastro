from .checkout import checkout_bp
from .point_astral_blocs import point_astral_blocs_bp  # <-- le SEUL import du BP blocs


def register_routes(app):
    app.register_blueprint(checkout_bp)

    # Garde-fou : n’enregistre pas deux fois si reload/debug ou import double
    if "point_astral_blocs" not in app.blueprints:
        app.register_blueprint(point_astral_blocs_bp)


    