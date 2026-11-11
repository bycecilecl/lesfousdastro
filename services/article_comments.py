"""Moderated blog comments using the existing persistent BD comment table.

The opaque article namespace prevents collisions with comic slugs and fits
the existing column without a schema migration. Moderation uses a separate
signing salt and checks the namespace again before any status change.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from flask import abort, current_app, make_response, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def comments_enabled() -> bool:
    return bool(os.getenv("DATABASE_URL") and current_app.secret_key
                and (os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI"))
                and not current_app.config.get("BLOG_COMMENTS_DISABLED")
                and not current_app.config.get("BD_COMMENTS_DISABLED"))


def article_scope(slug: str) -> str:
    return "blog:" + hashlib.sha256(slug.encode("utf-8")).hexdigest()


def moderation_signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="blog-comment-moderation-v1")


def comments_context(slug: str) -> dict:
    context = {"article_comments": [], "article_comments_enabled": False,
               "article_comments_unavailable": False}
    if not comments_enabled():
        return context
    from extensions import db
    from models.bd_comments import BdComment
    from sqlalchemy.exc import SQLAlchemyError
    try:
        comments = (BdComment.query.filter_by(bd_slug=article_scope(slug), status="approved")
                    .order_by(BdComment.created_at.asc()).all())
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Blog comments temporarily unavailable")
        context["article_comments_unavailable"] = True
        return context
    if "blog_comment_csrf" not in session:
        session["blog_comment_csrf"] = secrets.token_urlsafe(32)
    context.update(article_comments=comments, article_comments_enabled=True)
    return context


def _back(slug: str, notice: str):
    return redirect(url_for("blog.blog_article", slug=slug, commentaire=notice) + "#commentaires", code=303)


def submit_comment(slug: str, article: dict):
    if not comments_enabled():
        abort(404)
    if request.content_length and request.content_length > 32768:
        return "Ton message est trop volumineux. Limite-le à 2 000 caractères.", 413
    if request.form.get("website", ""):
        return _back(slug, "en-attente")
    csrf = session.get("blog_comment_csrf", "")
    if not csrf or not hmac.compare_digest(request.form.get("csrf", ""), csrf):
        return _back(slug, "expire")
    author = " ".join(request.form.get("author", "").split())
    body = request.form.get("body", "").strip()
    if not (2 <= len(author) <= 60 and 10 <= len(body) <= 2000):
        return _back(slug, "invalide")

    from extensions import db
    from models.bd_comments import BdComment
    from sqlalchemy.exc import SQLAlchemyError
    now = datetime.now(timezone.utc)
    ip_digest = hashlib.sha256((str(current_app.secret_key) + ":" +
                                (request.remote_addr or "unknown")).encode()).hexdigest()
    try:
        # Shared limits with the existing BD comments prevent cross-page spam.
        recent = (BdComment.query.filter_by(ip_digest=ip_digest)
                  .filter(BdComment.created_at >= now - timedelta(days=1))
                  .order_by(BdComment.created_at.desc()).limit(10).all())
        if len(recent) >= 10 or (recent and recent[0].created_at.replace(tzinfo=timezone.utc)
                                 > now - timedelta(minutes=2)):
            return _back(slug, "patiente")
        comment = BdComment(bd_slug=article_scope(slug), author=author, body=body,
                            status="pending", ip_digest=ip_digest)
        db.session.add(comment)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Blog comment could not be stored")
        return _back(slug, "indisponible")
    session["blog_comment_csrf"] = secrets.token_urlsafe(32)

    token = moderation_signer().dumps({"id": comment.id, "slug": slug})
    review_url = url_for("blog.blog_comment_moderate", token=token, _external=True)
    try:
        from utils.email_sender import envoyer_email_avec_analyse
        sent = envoyer_email_avec_analyse(
            destinataire=os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI"),
            sujet=f"[Blog] Nouveau commentaire sur {article['title']}",
            contenu_txt=(f"Article : {article['title']}\n\n{author} :\n{body}\n\n"
                         f"Modérer ce commentaire : {review_url}\n\n"
                         "Le commentaire ne sera visible qu’après validation."),
        )
    except Exception:
        sent = False
    if not sent:
        current_app.logger.error("Blog comment %s is saved pending moderation; notification failed", comment.id)
    return _back(slug, "en-attente")


def moderate_comment(token: str):
    if not comments_enabled():
        abort(404)
    try:
        payload = moderation_signer().loads(token, max_age=7 * 24 * 3600)
    except (BadSignature, SignatureExpired):
        abort(404)
    if (not isinstance(payload, dict) or not isinstance(payload.get("id"), int)
            or not isinstance(payload.get("slug"), str)):
        abort(404)
    from extensions import db
    from models.bd_comments import BdComment
    comment = db.session.get(BdComment, payload["id"])
    if comment is None or comment.bd_slug != article_scope(payload["slug"]):
        abort(404)
    if "blog_moderation_csrf" not in session:
        session["blog_moderation_csrf"] = secrets.token_urlsafe(32)
    if request.method == "POST":
        csrf = session.get("blog_moderation_csrf", "")
        if not csrf or not hmac.compare_digest(request.form.get("csrf", ""), csrf):
            abort(400)
        decision = request.form.get("decision")
        if decision not in {"approved", "rejected"}:
            abort(400)
        if comment.status == "pending":
            comment.status = decision
            db.session.commit()
        return redirect(url_for("blog.blog_comment_moderate", token=token), code=303)
    response = make_response(render_template("blog/moderate-comment.html", comment=comment,
                                            article_slug=payload["slug"]))
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
