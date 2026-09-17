"""Migration additive indépendante du graphe Alembic historique incomplet.

DATABASE_URL=... python scripts/init_analysis_orders.py
Ne modifie que les trois nouvelles tables; exécution répétable.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from extensions import db
from models.analysis_orders import AnalysisOrder, AnalysisJob, GiftGrant


def migrate(uri):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    db.init_app(app)
    with app.app_context(), db.engine.begin() as connection:
        for model in (AnalysisOrder, AnalysisJob, GiftGrant):
            model.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    uri = os.environ.get('DATABASE_URL')
    if not uri:
        raise SystemExit('DATABASE_URL doit être configurée dans cet environnement.')
    migrate(uri)
    print('Tables des commandes, analyses et cadeaux disponibles.')
