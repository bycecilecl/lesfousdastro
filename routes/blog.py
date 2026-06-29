# routes/blog.py
from pathlib import Path
from flask import Blueprint, render_template, abort, url_for
import markdown
import yaml

blog_bp = Blueprint("blog", __name__)

CATEGORIES_MAP = {
    "Les Bases": "bases",
    "Signes astrologiques": "signe",
    "Planètes": "planete",
    "Maisons": "maison",
    "Karma": "karma",
    "Astropapote": "astropapote",
    "Carnets d'Astrologue": "carnets",
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

    print("ARTICLE LU :", slug)
    print("LONGUEUR CONTENU MD :", len(content))
    print("DÉBUT CONTENU :", content[:100])
    print("FICHIER :", path)
    print("RAW START :", raw[:300])
    print("CONTENT LENGTH :", len(content))
    print("HTML LENGTH :", len(html_content))

    return {
        "title": meta.get("title", slug),
        "slug": slug,
        "description": meta.get("description", ""),
        "excerpt": meta.get("description", ""),
        "date": meta.get("date", ""),
        "category": meta.get("category", ""),
        "cat": CATEGORIES_MAP.get(meta.get("category", ""), "signe"),
        "tag": meta.get("tag", meta.get("category", "Article")),
        "image": meta.get("image", ""),
        "image_alt": meta.get("image_alt", meta.get("title", slug)),
        "content": html_content,
    }


def charger_articles() -> list[dict]:
    articles = []

    if not ARTICLES_DIR.exists():
        return articles

    for path in ARTICLES_DIR.glob("*.md"):
        article = lire_article_md(path)
        articles.append(article)

    return sorted(articles, key=lambda a: a.get("date", ""), reverse=True)


@blog_bp.route("/blog", strict_slashes=False)
def blog_index():
    articles = charger_articles()
    print("ARTICLES TROUVÉS :", len(articles))
    print([a["slug"] for a in articles])
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