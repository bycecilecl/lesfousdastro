"""Guard the existing result pages without changing their analysis content."""
from functools import wraps
from flask import has_request_context
from flask import (current_app, request, session, make_response, render_template,
                   template_rendered, abort)
from services.analysis_orders import (owned_order, restore_order, run_job,
                                     JobBusy, JobReview)


def paid_analysis(product):
    def decorate(view):
        @wraps(view)
        def secured(*args, **kwargs):
            order = owned_order(paid=True)
            if product not in order.products:
                abort(403, 'Ce produit ne fait pas partie de ta commande.')
            if request.args.get("debug_snippets"):
                abort(400, "Option de diagnostic indisponible.")
            restore_order(order)
            from config.analysis_sandbox import is_analysis_sandbox
            if is_analysis_sandbox():
                return render_template('debug_sandbox.html', titre='Analyse de test', infos=order.beneficiary)
            def generate(infos):
                # Old per-browser caches must never return another order's PDF.
                for key in list(session):
                    if key.startswith(('last_pdf', 'lock_until', 'last_fingerprint', 'last_generation')):
                        session.pop(key, None)
                session['infos_utilisateur'] = infos
                result = {}
                this_request = request._get_current_object()
                def capture(sender, template, context, **extra):
                    if has_request_context() and request._get_current_object() is this_request and context.get('pdf_url'):
                        result['pdf_url'] = context['pdf_url']
                with template_rendered.connected_to(capture, current_app._get_current_object()):
                    response = make_response(view(*args, **kwargs))
                if response.status_code != 200:
                    raise ValueError('Génération non terminée')
                result.update(html=response.get_data(as_text=True), product_id=product,
                              label=current_app.config.get('PRODUCTS', {}).get(product, {}).get('label', product))
                return result
            try:
                result = run_job(order.id, product, generate)
            except JobBusy:
                return render_template('analyse_suivi.html', en_cours=True), 202, {'Retry-After': '10'}
            except JobReview:
                return render_template('analyse_suivi.html', incident=True), 409
            except Exception:
                current_app.logger.exception('Analyse interrompue, commande %s', order.id)
                return render_template('analyse_suivi.html', incident=True), 503
            if result.get('html'):
                return result['html']
            return render_template('analyse_suivi.html', pdf_url=result['pdf_url'])
        return secured
    return decorate


def install_generation_guards(app):
    @app.before_request
    def block_legacy_generation():
        # These entry points overwrite the beneficiary after payment.
        if request.endpoint in {'analyse_karmique_route', 'analyse_point_astral_route',
                                'analyse_post', 'debug_session', 'checkout_bp.debug_session', 'debug_full'}:
            abort(410, 'Utilise le formulaire de commande puis le suivi de ton paiement.')
