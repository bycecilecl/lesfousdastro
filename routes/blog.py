# routes/blog.py
from pathlib import Path
from flask import Blueprint, render_template, abort, url_for
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
}


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
        "image": page.get("coverImage") or "",
        "image_alt": title,
        "content": page.get("content") or "",
    }


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
