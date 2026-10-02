import json
import sqlite3
import uuid
from pathlib import Path
import pytest
from flask import Flask
from extensions import db
import importlib.util
spec = importlib.util.spec_from_file_location('conversion_under_test', Path(__file__).resolve().parents[1] / 'routes/conversion.py')
conversion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conversion)
conversion_bp, clean = conversion.conversion_bp, conversion.clean
from services.analysis_orders import create_order, bind_provider, confirm_stripe, owned_order
from scripts.conversion_report import report

INFO = dict(nom='SecretName', email='private@example.invalid', date_naissance='1990-01-01',
    heure_naissance='12:00', lieu_naissance='Paris', lat='48.85', lon='2.35', tzid='Europe/Paris')

@pytest.fixture
def app(tmp_path):
    app=Flask(__name__)
    app.config.update(TESTING=True,SECRET_KEY='test',SQLALCHEMY_DATABASE_URI='sqlite://',
                      CONVERSION_DB=str(tmp_path/'conversion.db'))
    db.init_app(app)
    app.register_blueprint(conversion_bp)
    with app.app_context():
        db.create_all()
    @app.get('/order')
    def order():
        order=create_order('stripe',[{'key':'flash_astral'}],INFO)
        bind_provider(order,'cs_test')
        return {'id':order.id}
    @app.get('/pay')
    def pay():
        order=owned_order()
        confirm_stripe(order,dict(id='cs_test',mode='payment',payment_status='paid',
            client_reference_id=order.id,metadata={'order_id':order.id},amount_total=2500,
            currency='eur',livemode=True,payment_intent='pi_test'))
        return ''
    return app


def test_allowlist_and_feedback():
    sid=str(uuid.uuid4())
    _,event,payload=clean(dict(event='paid_offer_click',session_id=sid,product='flash_astral',
        price=1,email='secret',source='private@example.invalid',campaign='1990-01-01',error_type='secret'))
    assert payload == {'product':'flash_astral','price':25}
    _,_,payload=clean(dict(event='offer_feedback',session_id=sid,reason='price',device='mobile',product='flash_astral'))
    assert payload == {'reason':'price','offered_product':'flash_astral'}
    with pytest.raises(ValueError):
        clean(dict(event='purchase',session_id=sid))
    with pytest.raises(ValueError):
        clean(dict(event='offer_feedback',session_id=sid,reason='My email'))


def test_verified_purchase_deduplicated_without_personal_data(app):
    client=app.test_client();sid=str(uuid.uuid4())
    assert client.post('/api/conversion/purchase',json={'session_id':sid}).status_code == 403
    order=client.get('/order').json
    assert client.post('/api/conversion/purchase',json={'session_id':sid}).status_code == 403
    client.get('/pay')
    for _ in range(2):
        result=client.post('/api/conversion/purchase',json={'session_id':sid})
        assert result.json['transaction_id'] == order['id']
        assert result.json['value'] == 25
    stranger=app.test_client()
    assert stranger.post('/api/conversion/purchase',json={'session_id':sid}).status_code == 403
    with sqlite3.connect(app.config['CONVERSION_DB']) as conn:
        rows=conn.execute('SELECT * FROM events').fetchall()
        assert len(rows)==1
        assert 'SecretName' not in str(rows) and 'private@' not in str(rows)
    html=report(app.config['CONVERSION_DB'],'2020-01-01','2030-01-01')
    assert '1 commande(s)' in html and 'SecretName' not in html


def test_ingestion_feedback_once_and_fake_purchase_rejected(app):
    client=app.test_client();sid=str(uuid.uuid4())
    for _ in range(2):
        assert client.post('/api/conversion/events',json=dict(event='offer_feedback',session_id=sid,reason='price')).status_code==204
    assert client.post('/api/conversion/events',json=dict(event='purchase',session_id=sid)).status_code==400
    assert client.post('/api/conversion/events',json=[]).status_code==400
    with sqlite3.connect(app.config['CONVERSION_DB']) as conn:
        assert conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]==1
