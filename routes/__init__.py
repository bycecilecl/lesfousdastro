from .checkout import checkout_bp
from .point_astral import point_astral_bp

def register_routes(app):
    app.register_blueprint(checkout_bp)
    app.register_blueprint(point_astral_bp)