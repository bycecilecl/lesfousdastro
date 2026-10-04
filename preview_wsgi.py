"""Isolated blog preview for the Railway ``blog-test`` environment.

This process loads only the blog and its public Markdown fallbacks. It never
imports the storefront, payment routes, account system, or database startup.
"""

from flask import Flask, abort, redirect, url_for as flask_url_for

from routes.blog import blog_bp


app = Flask(__name__)
app.register_blueprint(blog_bp)


def preview_url_for(endpoint, **values):
    """Keep links outside the blog inert in the isolated preview."""
    if endpoint == "static" or endpoint.startswith("blog."):
        return flask_url_for(endpoint, **values)
    return "#"


app.jinja_env.globals["url_for"] = preview_url_for


@app.context_processor
def preview_context():
    return {"blog_preview": True}


@app.after_request
def disable_indexing(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Content-Security-Policy"] = (
        "script-src 'self' 'unsafe-inline'; connect-src 'self'"
    )
    return response


@app.route("/")
def home():
    return redirect(flask_url_for("blog.blog_index"))


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/<path:unused>", methods=["GET", "POST"])
def unavailable(unused):
    abort(404)
