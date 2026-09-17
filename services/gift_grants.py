"""Allocation atomique. Le CSV n'est plus une preuve de paiement."""
from flask import abort
from sqlalchemy.exc import IntegrityError
from config.gift_codes import load_gift_codes, is_code_used
from models.analysis_orders import GiftGrant
from extensions import db
from services.analysis_orders import digest


def allocate(external_order, product):
    rows = load_gift_codes()
    existing = GiftGrant.query.filter_by(external_order=external_order).first()
    if existing:
        if existing.product != product:
            abort(409, 'Commande cadeau déjà attribuée à un autre produit.')
        for row in rows:
            if digest(row['code']) == existing.code_hash:
                return row['code']
        abort(409, 'Code attribué absent du stock.')
    for row in rows:
        if row['product_key'] != product or is_code_used(row):
            continue
        key = digest(row['code'])
        if db.session.get(GiftGrant, key):
            continue
        db.session.add(GiftGrant(code_hash=key, product=product, external_order=external_order))
        try:
            db.session.commit()
            return row['code']
        except IntegrityError:
            db.session.rollback()
            # A concurrent retry of the same sale must return its original code.
            existing = GiftGrant.query.filter_by(external_order=external_order).first()
            if existing:
                return allocate(external_order, product)
    abort(409, 'Aucun code disponible pour ce produit.')
