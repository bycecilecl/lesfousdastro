# routes/blog.py
from pathlib import Path
from html.parser import HTMLParser
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Blueprint, render_template, abort, url_for, Response, request, make_response
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


class _FirstImage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.src = ""

    def handle_starttag(self, tag, attrs):
        if tag == "img" and not self.src:
            self.src = dict(attrs).get("src", "")


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
    parser = _FirstImage()
    parser.feed(content)
    if not cover:
        cover = parser.src
    return {
        "slug": slug,
        "title": str(page.get("title") or slug),
        "description": str(page.get("description") or ""),
        "date": str(page.get("dateRaw") or page.get("date") or "")[:10],
        "theme": theme,
        "theme_label": BD_THEMES.get(theme, "À découvrir"),
        "cover": cover,
        "has_panel": bool(parser.src),
        "content": content,
    }


def charger_bd() -> list[dict]:
    pages = (bd_from_bludit(page) for page in published_pages())
    return sorted((page for page in pages if page), key=lambda page: page["date"], reverse=True)


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
            return render_template("bd/page.html", page=page,
                                   newer=pages[index - 1] if index else None,
                                   older=pages[index + 1] if index + 1 < len(pages) else None,
                                   canonical_url=url_for("blog.bd_page", slug=slug, _external=True))
    abort(404)


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
