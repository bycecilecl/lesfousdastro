"""Offline integration tests: actual Flask requests + SQL database, fake providers/IA."""
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from flask import Flask, session, render_template_string
from werkzeug.exceptions import HTTPException
from extensions import db
from models.analysis_orders import AnalysisOrder, AnalysisJob, GiftGrant
from services.analysis_orders import *
from services.generation_access import paid_analysis, install_generation_guards

INFO = dict(nom='Test', email='test@example.invalid', date_naissance='1990-01-01',
            heure_naissance='12:00', lieu_naissance='Paris', lat='48.85', lon='2.35', tzid='Europe/Paris')


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'templates'))
    app.config.update(TESTING=True, SECRET_KEY='offline-test-only',
                      SQLALCHEMY_DATABASE_URI='sqlite:///' + str(tmp_path / 'test.db'))
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.calls = []
    @app.route('/buy/<product>')
    def buy(product):
        order = create_order('stripe', [{'key': product}], INFO)
        bind_provider(order, 'cs_' + order.id)
        return {'id': order.id}
    @app.route('/pay')
    def pay():
        order = owned_order()
        confirm_stripe(order, stripe_data(order))
        return 'ok'
    @app.route('/generate')
    @paid_analysis('flash_astral')
    def generate():
        app.calls.append(dict(session['infos_utilisateur']))
        return render_template_string('<a href="{{ pdf_url }}">PDF</a>', pdf_url='https://example.invalid/test.pdf')
    @app.route('/legacy', endpoint='analyse_point_astral_route')
    def legacy():
        raise AssertionError('legacy reached')
    install_generation_guards(app)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def stripe_data(order, **changes):
    data = dict(id=order.provider_id.split(':', 1)[1], mode='payment', payment_status='paid',
                client_reference_id=order.id, metadata={'order_id': order.id},
                amount_total=order.amount_cents, currency='eur', livemode=True,
                payment_intent='pi_' + order.id)
    return dict(data, **changes)


def test_unpaid_wrong_product_qa_and_legacy(app):
    c = app.test_client()
    assert c.get('/generate?qa=1', headers={'X-QA': '1'}).status_code == 403
    assert c.get('/legacy').status_code == 410
    c.get('/buy/flash_astral')
    assert c.get('/generate').status_code == 403
    c.get('/buy/forces_defis'); c.get('/pay')
    assert c.get('/generate').status_code == 403
    assert app.calls == []


def test_paid_replay_and_beneficiary_binding(app):
    c = app.test_client(); c.get('/buy/flash_astral'); c.get('/pay')
    with c.session_transaction() as s:
        s['infos_utilisateur'] = dict(INFO, nom='Other person')
    first = c.get('/generate')
    assert first.status_code == 200
    c.get('/pay')
    assert c.get('/generate').data == first.data
    assert app.calls == [INFO]
    stranger = app.test_client()
    with c.session_transaction() as source, stranger.session_transaction() as dest:
        dest['analysis_order_id'] = source['analysis_order_id']
    assert stranger.get('/generate').status_code == 403


@pytest.mark.parametrize('changes', [dict(amount_total=1), dict(currency='usd'),
    dict(payment_status='unpaid'), dict(client_reference_id='other'), dict(livemode=False),
    dict(metadata={'order_id':'other'}), dict(mode='subscription')])
def test_stripe_mismatch(app, changes):
    with app.test_request_context():
        order = create_order('stripe', [{'key':'flash_astral'}], INFO)
        bind_provider(order, 'cs_test')
        with pytest.raises(HTTPException):
            confirm_stripe(order, stripe_data(order, **changes))
        assert order.status == 'pending'


@pytest.mark.parametrize('items', [[{'key':'missing'}], [{'key':'flash_astral','quantity':-1}],
    [{'key':'flash_astral','quantity':2}], [{'key':'pack_essence'}, {'key':'flash_astral'}],
    [{'key':'flash_transits'}, {'key':'forces_defis'}]])
def test_bad_catalog(app, items):
    with app.test_request_context(), pytest.raises(HTTPException):
        create_order('stripe', items, INFO)


def test_pack_price_and_unique_payment(app):
    with app.test_request_context():
        first = create_order('stripe', [{'key':'pack_essence', 'price_cents':1}], INFO)
        assert first.amount_cents == PRODUCTS['pack_essence']['price_cents']
        assert set(first.products) == set(PRODUCTS['pack_essence']['included_products'])
        bind_provider(first, 'cs_first'); confirm_stripe(first, stripe_data(first, payment_intent='same'))
        second = create_order('stripe', [{'key':'flash_astral'}], INFO)
        with pytest.raises(HTTPException):
            bind_provider(second, 'cs_first')
        bind_provider(second, 'cs_second')
        with pytest.raises(HTTPException):
            confirm_stripe(second, stripe_data(second, payment_intent='same'))


def test_concurrent_execution_and_retry(app):
    with app.test_request_context():
        order = create_order('stripe', [{'key':'flash_astral'}], INFO)
        mark_paid(order, 'pi_concurrent'); oid = order.id
    started, release = threading.Event(), threading.Event()
    calls = []
    def generate(info):
        calls.append(info); started.set(); assert release.wait(5)
        return {'pdf_url':'https://example.invalid/result.pdf'}
    def worker():
        with app.app_context():
            return run_job(oid, 'flash_astral', generate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        assert started.wait(5)
        with app.app_context(), pytest.raises(JobBusy):
            run_job(oid, 'flash_astral', generate)
        release.set(); result = first.result(timeout=5)
    with app.app_context():
        assert run_job(oid, 'flash_astral', generate) == result
    assert len(calls) == 1


def test_failure_never_restarts_uncertain_work(app):
    with app.test_request_context():
        order = create_order('stripe', [{'key':'flash_astral'}], INFO)
        mark_paid(order, 'pi_failure')
        with pytest.raises(ValueError):
            run_job(order.id, 'flash_astral', lambda _: None)
        with pytest.raises(JobReview):
            run_job(order.id, 'flash_astral', lambda _: pytest.fail('restarted'))


def test_gift_invalid_consumed_and_payment_binding(app):
    with app.test_request_context():
        with pytest.raises(HTTPException):
            redeem_gift('UNKNOWN', INFO)
        db.session.add(GiftGrant(code_hash=digest('GIFT'), product='flash_astral', external_order='woo-1'))
        db.session.commit()
        order = redeem_gift('GIFT', INFO)
        assert order.status == 'paid' and order.products == ['flash_astral']
        assert order.beneficiary == INFO
        with pytest.raises(HTTPException):
            redeem_gift('GIFT', dict(INFO, nom='Other'))


def paypal_data(order):
    return {'id': 'PAYPAL123', 'status':'COMPLETED', 'purchase_units':[{
        'custom_id':order.id, 'payments':{'captures':[{'id':'CAP123', 'status':'COMPLETED',
        'amount':{'currency_code':'EUR','value':f'{order.amount_cents / 100:.2f}'}}]}}]}


@pytest.mark.parametrize('case', ['valid','amount','currency','pending','wrong_order','empty'])
def test_paypal_confirmation(app, case):
    with app.test_request_context():
        order = create_order('paypal', [{'key':'flash_astral'}], INFO)
        bind_provider(order, 'PAYPAL123'); data = paypal_data(order)
        cap = data['purchase_units'][0]['payments']['captures'][0]
        if case == 'amount': cap['amount']['value'] = '0.01'
        if case == 'currency': cap['amount']['currency_code'] = 'USD'
        if case == 'pending': cap['status'] = 'PENDING'
        if case == 'wrong_order': data['purchase_units'][0]['custom_id'] = 'other'
        if case == 'empty': data['purchase_units'] = []
        if case == 'valid':
            confirm_paypal(order, data); confirm_paypal(order, data)
            assert order.status == 'paid'
        else:
            with pytest.raises(HTTPException): confirm_paypal(order, data)
            assert order.status == 'pending'


def test_pack_and_solo_share_job(app):
    c = app.test_client(); c.get('/buy/pack_essence'); c.get('/pay')
    with c.session_transaction() as s: oid = s['analysis_order_id']
    with app.app_context():
        run_job(oid, 'flash_astral', lambda _: {'pdf_url':'https://example.invalid/pack.pdf'})
    response = c.get('/generate')
    assert response.status_code == 200 and b'pack.pdf' in response.data
    assert app.calls == []


def test_gift_allocation_replay_and_concurrency(app, monkeypatch):
    from services import gift_grants
    monkeypatch.setattr(gift_grants, 'load_gift_codes', lambda: [
        {'code':'A', 'product_key':'flash_astral', 'used_at':''},
        {'code':'B', 'product_key':'flash_astral', 'used_at':''}])
    def worker():
        with app.app_context(): return gift_grants.allocate('sale-1', 'flash_astral')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert results[0] == results[1]
    with app.app_context():
        assert GiftGrant.query.count() == 1
        with pytest.raises(HTTPException): gift_grants.allocate('sale-1', 'forces_defis')


def test_migration_repeatable(tmp_path):
    from scripts.init_analysis_orders import migrate
    uri = 'sqlite:///' + str(tmp_path / 'migration.db')
    migrate(uri); migrate(uri)


def test_actual_paypal_routes(app, monkeypatch):
    import importlib.util
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('isolated_paypal', Path(__file__).resolve().parents[1] / 'routes/paypal.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    app.register_blueprint(module.payments_bp)
    monkeypatch.setattr(module, 'get_paypal_token', lambda: ('offline', 'https://example.invalid'))
    calls, created = [], {}
    def post(url, **kwargs):
        calls.append(url)
        if url.endswith('/capture'):
            order = db.session.get(AnalysisOrder, created['id'])
            result = paypal_data(order)
        else:
            created['id'] = kwargs['json']['purchase_units'][0]['custom_id']
            result = {'id':'PAYPAL123'}
        return SimpleNamespace(status_code=201, json=lambda: result, raise_for_status=lambda: None)
    monkeypatch.setattr(module.requests, 'post', post)
    c = app.test_client()
    info = dict(nom='Test', email=INFO['email'], birthDate=INFO['date_naissance'],
                birthTime=INFO['heure_naissance'], birthPlace='Paris', lat='48.85', lon='2.35', tzid='Europe/Paris')
    assert c.post('/payments/create-order?qa=1', json={'items':[{'key':'flash_astral'}], 'userInfo':info}).status_code == 201
    assert c.post('/payments/capture-order', json={'orderID':'OTHER'}).status_code == 403
    assert len(calls) == 1
    for _ in range(2):
        response = c.post('/payments/capture-order', json={'orderID':'PAYPAL123', 'userInfo':dict(info, nom='Attacker')})
        assert response.status_code == 200
    assert len(calls) == 2
    with app.app_context():
        order = db.session.get(AnalysisOrder, created['id'])
        assert order.beneficiary['nom'] == 'Test' and order.status == 'paid'


def test_actual_gift_api_fails_closed(app, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location('isolated_gift', Path(__file__).resolve().parents[1] / 'routes/gift_api.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'API_TOKEN', '')
    app.register_blueprint(module.gift_api_bp)
    assert app.test_client().post('/api/gift/allocate', json={'product_key':'flash_astral'}).status_code == 401


def test_actual_stripe_checkout_and_return(app, monkeypatch):
    # Compile the unmodified route functions, excluding heavyweight IA imports.
    import ast, json, uuid, stripe
    import flask
    from datetime import datetime
    from types import SimpleNamespace
    source = Path(__file__).resolve().parents[1] / 'routes/checkout.py'
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'checkout', 'paiement_effectue'}]
    for node in functions: node.decorator_list = []
    namespace = dict(globals(), **{name:getattr(flask, name) for name in
        ('request','session','redirect','url_for','render_template','abort','current_app')},
        json=json, uuid=uuid, stripe=stripe, datetime=datetime, PAYMENTS_SANDBOX=False)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    app.add_url_rule('/checkout', 'checkout_bp.checkout', namespace['checkout'], methods=['POST'])
    app.add_url_rule('/success', 'checkout_bp.paiement_effectue', namespace['paiement_effectue'])
    app.add_url_rule('/process', 'checkout_bp.traiter_analyses', lambda:'ok')
    app.add_url_rule('/', 'main.index', lambda:'ok')
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id='cs_created', url='https://example.invalid/checkout')
    monkeypatch.setattr(stripe.checkout.Session, 'create', create)
    def retrieve(sid):
        order = owned_order()
        return stripe.StripeObject.construct_from(stripe_data(order), None)
    monkeypatch.setattr(stripe.checkout.Session, 'retrieve', retrieve)
    c = app.test_client()
    response = c.post('/checkout', data=dict(INFO, items=json.dumps([{'key':'pack_essence','price':0.01}])))
    assert response.status_code == 303
    assert captured['line_items'][0]['price_data']['unit_amount'] == PRODUCTS['pack_essence']['price_cents']
    with c.session_transaction() as s:
        oid = s['analysis_order_id']; s['infos_utilisateur'] = dict(INFO, nom='Changed')
    assert captured['client_reference_id'] == oid and captured['metadata']['order_id'] == oid
    assert c.get('/success?session_id=cs_created').status_code == 302
    assert c.get('/success?session_id=cs_created').status_code == 302
    with c.session_transaction() as s: assert s['infos_utilisateur']['nom'] == INFO['nom']
    stranger = app.test_client()
    assert stranger.get('/success?session_id=cs_created').status_code == 403


def test_all_paid_entrypoints_have_guard():
    import ast
    expected = {
        'routes/point_astral_blocs.py': 'point_astral_blocs_complet',
        'point_astral_famille/routes.py': 'point_astral_famille_complet',
        'routes/forces_defis_module.py': 'forces_defis_complet',
        'routes/profil_amoureux_module.py': 'profil_amoureux_complet',
        'routes/analyse_karmique.py': 'analyse_karmique_complete',
        'routes/transits.py': 'transits_complet',
    }
    root = Path(__file__).resolve().parents[1]
    for file, function in expected.items():
        tree = ast.parse((root / file).read_text())
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
        assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                   and d.func.id == 'paid_analysis' for d in route.decorator_list)
