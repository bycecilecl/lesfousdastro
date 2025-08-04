from .checkout import checkout_bp
from .point_astral import point_astral_bp
from .analyse_gratuite import gratuite_bp

def register_routes(app):
    app.register_blueprint(checkout_bp)
    app.register_blueprint(gratuite_bp)
    app.register_blueprint(point_astral_bp)