"""Accès temporaire à la maintenance, conservé dans le navigateur."""
import hmac
from flask import after_this_request, request


def autoriser_acces_maintenance(secret):
    if not secret:
        return False
    token = (
        request.args.get('maint_token')
        or request.headers.get('X-MAINT-TOKEN')
        or request.cookies.get('maint_token')
        or ''
    )
    if not hmac.compare_digest(token.encode(), secret.encode()):
        return False
    if request.args.get('maint_token') or request.headers.get('X-MAINT-TOKEN'):
        @after_this_request
        def memoriser_acces(response):
            response.set_cookie(
                'maint_token', secret, max_age=8 * 60 * 60,
                httponly=True, secure=request.is_secure, samesite='Lax', path='/',
            )
            return response
    return True
