# security_headers.py
import os
from flask import request

def _is_production() -> bool:
    # Mets FLASK_ENV=production ou APP_ENV=production en prod
    return (os.getenv("FLASK_ENV") == "production") or (os.getenv("APP_ENV") == "production")

def add_security_headers(app):
    """
    Ajoute des en-têtes de sécurité à TOUTES les réponses.
    - HSTS uniquement si la requête est HTTPS (prod)
    - CSP raisonnable (PayPal, OpenAI, Google Maps si tu en uses)
    """
    @app.after_request
    def _set_headers(resp):
        # X-Frame-Options / Anti-clickjacking
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # X-Content-Type-Options / Anti-MIME sniffing
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Referrer-Policy
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Permissions-Policy (ex-Feature-Policy)
        # Coupe tout par défaut; rouvre si tu as besoin de geolocation, camera, etc.
        resp.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # HSTS : seulement en prod ET en HTTPS réel (ProxyFix aide request.is_secure)
        if _is_production() and request.is_secure:
            # ajoute includeSubDomains si tout ton sous-domaine est en HTTPS
            resp.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content-Security-Policy (CSP)
        # Ajuste selon tes vrais besoins (CDN, scripts externes, etc.).
        # NB: commence strict, desserre si une ressource légitime est bloquée.
                # Content-Security-Policy (CSP)
        # En local: CSP large (inclut PayPal sandbox). En prod: CSP plus serrée.
        if not _is_production():
           csp_parts = [
                "default-src 'self'",
                # JS : Paypal + Google + Maps + StatCounter
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.paypal.com https://www.sandbox.paypal.com https://*.paypal.com https://*.paypalobjects.com https://www.gstatic.com https://www.google.com https://maps.googleapis.com https://www.statcounter.com https://challenges.cloudflare.com",
                # XHR / beacons : OpenAI, Maps, PayPal, StatCounter
                "connect-src 'self' https://api.openai.com https://maps.googleapis.com https://www.paypal.com https://www.sandbox.paypal.com https://*.paypal.com https://*.paypalobjects.com https://api-m.paypal.com https://api-m.sandbox.paypal.com https://statcounter.com https://*.statcounter.com",
                # iframes autorisés
                "frame-src 'self' https://www.paypal.com https://www.sandbox.paypal.com https://*.paypal.com https://statcounter.com https://*.statcounter.com https://challenges.cloudflare.com",
                # Images : self + data + PayPal + StatCounter (pixel)
                "img-src 'self' data: https://www.paypal.com https://www.sandbox.paypal.com https://*.paypal.com https://*.paypalobjects.com https://c.statcounter.com",
                # Styles / Fonts
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' data: https://fonts.gstatic.com",
                "object-src 'none'",
                "frame-ancestors 'self'",
            ]
        else:
            csp_parts = [
                "default-src 'self'",
                # JS : PayPal + StatCounter
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.paypal.com https://*.paypal.com https://*.paypalobjects.com https://www.statcounter.com https://challenges.cloudflare.com",
                # XHR / beacons : PayPal + StatCounter
                "connect-src 'self' https://www.paypal.com https://*.paypal.com https://*.paypalobjects.com https://api-m.paypal.com https://statcounter.com https://*.statcounter.com",
                # iframes autorisés
                "frame-src 'self' https://www.paypal.com https://*.paypal.com https://statcounter.com https://*.statcounter.com https://challenges.cloudflare.com",
                # Images : self + data + PayPal + StatCounter (pixel)
                "img-src 'self' data: https://www.paypal.com https://*.paypal.com https://*.paypalobjects.com https://c.statcounter.com",
                # Styles / Fonts
                "style-src 'self' 'unsafe-inline'",
                "font-src 'self' data:",
                "object-src 'none'",
                "frame-ancestors 'self'",
            ]

        # ⚠️ Ici on écrase la CSP pour être sûr d’appliquer celle-ci
        resp.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        return resp