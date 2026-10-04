# routes/blog.py
from pathlib import Path
from html.parser import HTMLParser
import base64
import binascii
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
import hmac
import os
import secrets
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from flask import Blueprint, render_template, abort, url_for, Response, request, make_response, redirect, session, current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import markdown
import yaml
from services.bludit_blog import published_pages

blog_bp = Blueprint("blog", __name__)

# CATEGORIES_MAP = {
#     "Les Bases": "bases",
#     "Signes astrologiques": "signe",
#     "Planètes": "planete",
#     "Maisons": "maison",
#     "Analyses de thèmes": "analyses",
#     "Astropapote": "astropapote",
#     "Carnets d'astrologue": "carnets",
#     "Astrologie védique": "vedique",
# }

CATEGORIES_MAP = {
    "les bases": "bases",
    "signes astrologiques": "signe",
    "planètes": "planete",
    "maisons": "maison",
    "analyses de thèmes": "analyses",
    "astropapote": "astropapote",
    "carnets d'astrologue": "carnets",
    "astrologie védique": "vedique",
    "astrologie uranienne": "uranienne"
}

BLUDIT_CATEGORIES = {
    "bases": "Les Bases",
    "signe": "Signes astrologiques",
    "planete": "Planètes",
    "maison": "Maisons",
    "analyses": "Analyses de thèmes",
    "astropapote": "Astropapote",
    "carnets": "Carnets d'astrologue",
    "vedique": "Astrologie védique",
    "uranienne": "Astrologie uranienne",
    # Keep recognizing categories created manually in Bludit before import.
    "les-bases": "Les Bases",
    "signes-astrologiques": "Signes astrologiques",
    "planetes": "Planètes",
    "maisons": "Maisons",
    "analyses-de-themes": "Analyses de thèmes",
    "carnets-dastrologue": "Carnets d'astrologue",
    "astrologie-vedique": "Astrologie védique",
    "astrologie-uranienne": "Astrologie uranienne",
}

BD_THEMES = {
    "bases": "Les bases",
    "placements": "Les placements",
    "aspects": "Les aspects",
}


class _ImageSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            source = dict(attrs).get("src", "")
            if source:
                self.sources.append(source)


def bd_image_sources(content: str) -> list[str]:
    parser = _ImageSources()
    parser.feed(content)
    return parser.sources


def bd_image_content(content: str, slug: str) -> tuple[str, list[str]]:
    """Give pasted images real URLs so they can open, zoom and be shared."""
    sources = bd_image_sources(content)
    for index, source in enumerate(sources):
        if source.startswith("data:image/"):
            content = content.replace(source, url_for("blog.bd_embedded_image", slug=slug, index=index))
    return content, sources


BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"


def lire_article_md(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()

    meta = {}
    content = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)

        if len(parts) == 3:
            frontmatter = parts[1].strip()
            content = parts[2].strip()
            meta = yaml.safe_load(frontmatter) or {}

    slug = meta.get("slug") or path.stem

    html_content = markdown.markdown(
        content,
        extensions=["extra", "nl2br"]
    )

    categories = meta.get("categories")

    if not categories:
        categories = [meta.get("category", "")]

    if isinstance(categories, str):
        categories = [categories]

    categories = [
        str(category).strip()
        for category in categories
        if str(category).strip()
    ]

    cats = [
        CATEGORIES_MAP[category.lower()]
        for category in categories
        if category.lower() in CATEGORIES_MAP
    ]

    return {
        "title": meta.get("title", slug),
        "slug": slug,
        "description": meta.get("description", ""),
        "excerpt": meta.get("description", ""),
        "date": meta.get("date", ""),
       "categories": categories,
        "cats": cats,
        "category": categories[0] if categories else "",
        "cat": cats[0] if cats else "signe",
        "tag": meta.get("tag", categories[0] if categories else "Article"),
        "image": meta.get("image", ""),
        "image_alt": meta.get("image_alt", meta.get("title", slug)),
        "content": html_content,
    }


def charger_articles() -> list[dict]:
    articles = []

    if ARTICLES_DIR.exists():
        for path in ARTICLES_DIR.glob("*.md"):
            article = lire_article_md(path)
            articles.append(article)

    # An article imported into Bludit replaces its Markdown version only when
    # explicitly published there. Its /blog/<slug> address stays the same.
    by_slug = {article["slug"]: article for article in articles}
    for page in published_pages():
        article = article_from_bludit(page)
        if article:
            by_slug[article["slug"]] = article

    return sorted(by_slug.values(), key=lambda a: a.get("date", ""), reverse=True)


def article_from_bludit(page: dict) -> dict | None:
    """Adapt a public Bludit page to the existing blog templates."""
    slug = page.get("slug")
    if not isinstance(slug, str) or not slug or "/" in slug or ".." in slug:
        return None
    category_key = str(page.get("category") or "").strip()
    category = BLUDIT_CATEGORIES.get(category_key, category_key)
    cat = CATEGORIES_MAP.get(category.lower())
    if not cat:
        # Bludit's welcome page and unrelated pages must not enter this blog.
        return None
    title = str(page.get("title") or slug)
    description = str(page.get("description") or "")
    date = str(page.get("dateRaw") or page.get("date") or "")[:10]
    content = bludit_content(page)

    return {
        "title": title,
        "slug": slug,
        "description": description,
        "excerpt": description,
        "date": date,
        "categories": [category] if category else [],
        "cats": [cat],
        "category": category,
        "cat": cat,
        "tag": category or "Article",
        "image": bludit_media_url(str(page.get("coverImage") or "")),
        "image_alt": title,
        "content": content,
    }


def bludit_media_url(value: str) -> str:
    origin = os.getenv("BLUDIT_BLOG_URL", "").rstrip("/")
    if origin and value.startswith(origin + "/bl-content/uploads/"):
        return "/blog/media/" + value.split("/bl-content/uploads/", 1)[1]
    if value.startswith("/bl-content/uploads/"):
        return "/blog/media/" + value.split("/bl-content/uploads/", 1)[1]
    return value


def bludit_content(page: dict) -> str:
    content = str(page.get("content") or "")
    origin = os.getenv("BLUDIT_BLOG_URL", "").rstrip("/")
    if origin:
        content = content.replace(origin + "/bl-content/uploads/", "/blog/media/")
    return content.replace('"/bl-content/uploads/', '"/blog/media/')


def bd_from_bludit(page: dict) -> dict | None:
    """Turn a published Bludit page in category BD into a comic page."""
    if (page.get("type") != "published"
            or str(page.get("category") or "").lower() not in {"bd", "bandes-dessinees"}):
        return None
    slug = page.get("slug")
    if not isinstance(slug, str) or not slug or "/" in slug or ".." in slug:
        return None
    tags = page.get("tags") or {}
    if isinstance(tags, dict):
        tag_keys = tags.keys()
    elif isinstance(tags, list):
        tag_keys = tags
    elif isinstance(tags, str):
        # Bludit 3.22's Page::json() returns comma-separated tag names.
        tag_keys = tags.split(",")
    else:
        tag_keys = []
    aliases = {"les-bases": "bases", "les-placements": "placements", "les-aspects": "aspects"}
    normalized_tags = (str(tag).strip().lower() for tag in tag_keys)
    theme = next((aliases.get(tag, tag) for tag in normalized_tags
                  if aliases.get(tag, tag) in BD_THEMES), "")
    content = bludit_content(page)
    cover = bludit_media_url(str(page.get("coverImage") or ""))
    content, image_sources = bd_image_content(content, slug)
    if not cover:
        cover = image_sources[0] if image_sources else ""
        if cover.startswith("data:image/"):
            cover = url_for("blog.bd_embedded_image", slug=slug, index=0)
    return {
        "slug": slug,
        "title": str(page.get("title") or slug),
        "description": str(page.get("description") or ""),
        "date": str(page.get("dateRaw") or page.get("date") or "")[:10],
        "theme": theme,
        "theme_label": BD_THEMES.get(theme, "À découvrir"),
        "cover": cover,
        "has_panel": bool(image_sources),
        "panel_count": len(image_sources),
        "content": content,
    }


def charger_bd() -> list[dict]:
    pages = (bd_from_bludit(page) for page in published_pages())
    return sorted((page for page in pages if page), key=lambda page: page["date"], reverse=True)


@blog_bp.route("/bd/rss.xml")
def bd_rss():
    """Expose one cover image per published comic to Pinterest's RSS import."""
    ET.register_namespace("media", "http://search.yahoo.com/mrss/")
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Les Fous d'Astro — BD"
    ET.SubElement(channel, "link").text = "https://lesfousdastro.fr/bd"
    ET.SubElement(channel, "description").text = "Les BD astrologiques des Fous d'Astro"

    for page in charger_bd():
        if not page["cover"]:
            continue
        link = "https://lesfousdastro.fr/bd/" + quote(page["slug"], safe="")
        image = urljoin("https://lesfousdastro.fr", page["cover"])
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = page["title"]
        ET.SubElement(item, "description").text = page["description"] or page["title"]
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link
        if page["date"]:
            try:
                published = datetime.strptime(page["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
            else:
                ET.SubElement(item, "pubDate").text = format_datetime(published)
        ET.SubElement(item, "{http://search.yahoo.com/mrss/}content", {
            "url": image,
            "medium": "image",
        })

    return Response(ET.tostring(rss, encoding="utf-8", xml_declaration=True),
                    content_type="application/rss+xml; charset=utf-8")


def bd_comments_enabled() -> bool:
    return bool(os.getenv("DATABASE_URL") and current_app.secret_key and
                (os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI")) and
                not current_app.config.get("BD_COMMENTS_DISABLED"))


def _moderation_signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="bd-comment-moderation-v1")


@blog_bp.route("/blog/media/<path:filename>")
def blog_media(filename):
    """Serve Bludit's uploaded images through the public blog domain."""
    if (not filename or "\\" in filename or any(part in (".", "..", "") for part in filename.split("/"))
            or Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}):
        abort(404)
    bludit_origin = os.getenv("BLUDIT_BLOG_URL", "").rstrip("/")
    if not bludit_origin.startswith("https://"):
        abort(404)
    source = bludit_origin + "/bl-content/uploads/" + quote(filename, safe="/")
    try:
        with urlopen(Request(source, headers={"User-Agent": "LesFousDAstroBlog/1.0"}), timeout=5) as upstream:
            content_type = upstream.headers.get_content_type()
            if content_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
                abort(404)
            body = upstream.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                abort(404)
    except OSError:
        abort(404)
    return Response(body, content_type=content_type, headers={"Cache-Control": "public, max-age=86400"})


@blog_bp.route("/bd/<slug>/image/<int:index>")
def bd_embedded_image(slug, index):
    """Serve only image data from an already published BD, never a draft."""
    raw = next((item for item in published_pages() if item.get("slug") == slug
                and item.get("type") == "published"
                and str(item.get("category") or "").lower() in {"bd", "bandes-dessinees"}), None)
    if raw is None:
        abort(404)
    original_sources = bd_image_sources(bludit_content(raw))
    if index >= len(original_sources):
        abort(404)
    source = original_sources[index]
    allowed = {"webp": "image/webp", "png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif"}
    header, marker, encoded = source.partition(",")
    image_type = header.removeprefix("data:image/").removesuffix(";base64").lower()
    if marker != "," or header != f"data:image/{image_type};base64" or image_type not in allowed:
        abort(404)
    if len(encoded) > 11 * 1024 * 1024:
        abort(404)
    try:
        body = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        abort(404)
    if not body or len(body) > 8 * 1024 * 1024:
        abort(404)
    return Response(body, content_type=allowed[image_type], headers={
        "Cache-Control": "public, max-age=300",
        "X-Content-Type-Options": "nosniff",
    })


@blog_bp.route("/bd", strict_slashes=False)
def bd_index():
    theme = request.args.get("theme", "")
    if theme and theme not in BD_THEMES:
        abort(404)
    pages = charger_bd()
    visible_pages = [page for page in pages if page["theme"] == theme] if theme else pages
    response = make_response(render_template(
        "bd/index.html", pages=visible_pages, themes=BD_THEMES, active_theme=theme,
        counts={key: sum(page["theme"] == key for page in pages) for key in BD_THEMES},
    ))
    if not visible_pages:
        response.headers["X-Robots-Tag"] = "noindex"
    return response


@blog_bp.route("/bd/<slug>", strict_slashes=False)
def bd_page(slug):
    pages = charger_bd()
    for index, page in enumerate(pages):
        if page["slug"] == slug:
            comments_enabled = bd_comments_enabled()
            comments = []
            if comments_enabled:
                from models.bd_comments import BdComment
                comments = (BdComment.query.filter_by(bd_slug=slug, status="approved")
                            .order_by(BdComment.created_at.asc()).all())
            if comments_enabled and "bd_comment_csrf" not in session:
                session["bd_comment_csrf"] = secrets.token_urlsafe(32)
            return render_template("bd/page.html", page=page,
                                   newer=pages[index - 1] if index else None,
                                   older=pages[index + 1] if index + 1 < len(pages) else None,
                                   canonical_url=url_for("blog.bd_page", slug=slug, _external=True),
                                   comments=comments, comments_enabled=comments_enabled)
    abort(404)


@blog_bp.route("/bd/<slug>/commenter", methods=["POST"])
def bd_comment_submit(slug):
    if not bd_comments_enabled():
        abort(404)
    from extensions import db
    from models.bd_comments import BdComment
    if not any(page["slug"] == slug for page in charger_bd()):
        abort(404)
    back = url_for("blog.bd_page", slug=slug) + "#commentaires"
    if request.content_length and request.content_length > 4096:
        abort(413)
    if request.form.get("website", ""):
        return redirect(back)
    csrf = session.get("bd_comment_csrf", "")
    if not csrf or not hmac.compare_digest(request.form.get("csrf", ""), csrf):
        abort(400)
    author = " ".join(request.form.get("author", "").split())
    body = request.form.get("body", "").strip()
    if not (2 <= len(author) <= 60 and 10 <= len(body) <= 2000):
        return redirect(url_for("blog.bd_page", slug=slug, commentaire="invalide") + "#commentaires")

    now = datetime.now(timezone.utc)
    ip_digest = hashlib.sha256((str(current_app.secret_key) + ":" +
                                (request.remote_addr or "unknown")).encode()).hexdigest()
    recent = (BdComment.query.filter_by(ip_digest=ip_digest)
              .filter(BdComment.created_at >= now - timedelta(days=1))
              .order_by(BdComment.created_at.desc()).limit(10).all())
    if len(recent) >= 10 or (recent and recent[0].created_at.replace(tzinfo=timezone.utc)
                             > now - timedelta(minutes=2)):
        return redirect(url_for("blog.bd_page", slug=slug, commentaire="patiente") + "#commentaires")

    comment = BdComment(bd_slug=slug, author=author, body=body,
                        status="pending", ip_digest=ip_digest)
    db.session.add(comment)
    db.session.commit()
    session["bd_comment_csrf"] = secrets.token_urlsafe(32)

    from utils.email_sender import envoyer_email_avec_analyse
    token = _moderation_signer().dumps(comment.id)
    review_url = url_for("blog.bd_comment_moderate", token=token, _external=True)
    sent = envoyer_email_avec_analyse(
        destinataire=os.getenv("EMAIL_ADMIN") or os.getenv("EMAIL_ENVOI"),
        sujet=f"[BD] Nouveau commentaire sur {slug}",
        contenu_txt=f"{author} a commenté la BD {slug} :\n\n{body}\n\nModérer : {review_url}",
    )
    if not sent:
        current_app.logger.error("BD comment %s awaiting moderation; notification failed", comment.id)
    return redirect(url_for("blog.bd_page", slug=slug, commentaire="en-attente") + "#commentaires")


@blog_bp.route("/bd/commentaire/moderer/<token>", methods=["GET", "POST"])
def bd_comment_moderate(token):
    if not bd_comments_enabled():
        abort(404)
    from extensions import db
    from models.bd_comments import BdComment
    try:
        comment_id = _moderation_signer().loads(token, max_age=7 * 24 * 3600)
    except (BadSignature, SignatureExpired):
        abort(404)
    comment = db.session.get(BdComment, comment_id)
    if comment is None:
        abort(404)
    if request.method == "POST" and comment.status == "pending":
        decision = request.form.get("decision")
        if decision not in {"approved", "rejected"}:
            abort(400)
        comment.status = decision
        db.session.commit()
        return redirect(url_for("blog.bd_comment_moderate", token=token))
    response = make_response(render_template("bd/moderate.html", comment=comment))
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


LEGACY_ARTICLE_SLUGS = {
    "etude-de-revolution-solaire-de-2020-2021": "revolution-solaire-2020-2021-etude-cas",
    "introduction-a-lastrologie-uranienne": "astrologie-uranienne-introduction",
    "la-lune-la-mere-en-astrologie": "la-lune-la-mere-en-astrologie",
    "les-transneptuniennes-astrologie-uranienne": "planetes-astrologie-uranienne",
}


@blog_bp.route("/etude-de-revolution-solaire-de-2020-2021/", strict_slashes=False)
@blog_bp.route("/introduction-a-lastrologie-uranienne/", strict_slashes=False)
@blog_bp.route("/la-lune-la-mere-en-astrologie/", strict_slashes=False)
@blog_bp.route("/les-transneptuniennes-astrologie-uranienne/", strict_slashes=False)
def legacy_article_redirect():
    slug = LEGACY_ARTICLE_SLUGS[request.path.strip("/")]
    return redirect(url_for("blog.blog_article", slug=slug), code=301)


@blog_bp.route("/blog", strict_slashes=False)
def blog_index():
    articles = charger_articles()
    return render_template("blog/index.html", articles=articles)


@blog_bp.route("/blog/<slug>", strict_slashes=False)
def blog_article(slug):

    articles = charger_articles()

    for article in articles:

        if article["slug"] == slug:

            autres_articles = [
                a for a in articles
                if a["slug"] != slug
            ][:4]

            canonical_url = url_for(
                "blog.blog_article",
                slug=slug,
                _external=True
            )

            return render_template(
                "blog/article.html",
                article=article,
                autres_articles=autres_articles,
                canonical_url=canonical_url,
            )

    abort(404)
