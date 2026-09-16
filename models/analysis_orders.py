"""Commandes automatisées, distinctes des consultations manuelles."""
import uuid
from datetime import datetime, timezone
from extensions import db


class AnalysisOrder(db.Model):
    __tablename__ = 'analysis_orders'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_hash = db.Column(db.String(64), nullable=False)
    provider = db.Column(db.String(16), nullable=False)
    provider_id = db.Column(db.String(255), unique=True)
    payment_id = db.Column(db.String(255), unique=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='EUR')
    sandbox = db.Column(db.Boolean, nullable=False, default=False)
    items = db.Column(db.JSON, nullable=False)
    products = db.Column(db.JSON, nullable=False)
    beneficiary = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))


class AnalysisJob(db.Model):
    __tablename__ = 'analysis_jobs'
    __table_args__ = (db.UniqueConstraint('order_id', 'product'),)
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(36), db.ForeignKey('analysis_orders.id'), nullable=False)
    product = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    result = db.Column(db.JSON)
    started_at = db.Column(db.DateTime(timezone=True))


class GiftGrant(db.Model):
    __tablename__ = 'gift_grants'
    code_hash = db.Column(db.String(64), primary_key=True)
    # The printable code remains in the existing CSV, never in logs.
    product = db.Column(db.String(80), nullable=False)
    external_order = db.Column(db.String(255), unique=True, nullable=False)
    redeemed_order = db.Column(db.String(36), db.ForeignKey('analysis_orders.id'), unique=True)
