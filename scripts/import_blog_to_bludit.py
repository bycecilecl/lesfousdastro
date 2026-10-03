"""Prepare or import existing blog articles as Bludit drafts.

Example (no network, no changes):
    python scripts/import_blog_to_bludit.py --slug astrologie-libre-arbitre

The --apply flag requires BLUDIT_BLOG_URL, BLUDIT_BLOG_API_TOKEN and
BLUDIT_BLOG_AUTH_TOKEN. Imported articles stay drafts until published in
Bludit, while their current Markdown versions remain live on this site.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import markdown
import yaml


ROOT = Path(__file__).resolve().parent.parent
ARTICLE_DIR = ROOT / "data" / "articles"
PUBLIC_URL = "https://lesfousdastro.fr"
CATEGORY_KEYS = {
    "les bases": "bases",
    "signes astrologiques": "signe",
    "planètes": "planete",
    "maisons": "maison",
    "analyses de thèmes": "analyses",
    "astropapote": "astropapote",
    "carnets d'astrologue": "carnets",
    "astrologie védique": "vedique",
    "astrologie uranienne": "uranienne",
}

# The source has a malformed date. Its public page also displays this malformed
# value, so the original day cannot be verified from the current site alone.
# Keep the draft importable and flag it for review before publication.
DATE_TO_REVIEW = {"dominance-elements-theme-astral-feu-terre-air-eau": "2022-06-15"}


def prepare(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Missing YAML front matter: {path.name}")
    meta = yaml.safe_load(match.group(1)) or {}
    slug = str(meta.get("slug") or path.stem).strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError(f"Invalid slug in {path.name}: {slug}")

    raw_date = str(meta.get("date") or "").strip()
    date_needs_review = False
    try:
        date.fromisoformat(raw_date)
    except ValueError as exc:
        if slug not in DATE_TO_REVIEW:
            raise ValueError(f"Invalid date in {path.name}: {raw_date}") from exc
        raw_date = DATE_TO_REVIEW[slug]
        date_needs_review = True

    categories = meta.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    category = str(meta.get("category") or (categories[0] if categories else "")).strip()
    category_key = CATEGORY_KEYS.get(category.lower())
    if category and not category_key:
        raise ValueError(f"Unknown category in {path.name}: {category}")

    html = markdown.markdown(match.group(2).strip(), extensions=["extra", "nl2br"])
    # Images and internal links must also work while previewing on Bludit's
    # separate editing domain. On the public site they keep the same address.
    html = html.replace('src="/static/', f'src="{PUBLIC_URL}/static/')
    html = html.replace('href="/static/', f'href="{PUBLIC_URL}/static/')
    html = html.replace('href="/blog/', f'href="{PUBLIC_URL}/blog/')
    cover = str(meta.get("image") or "").strip()
    if cover.startswith("/"):
        cover = PUBLIC_URL + cover

    return {
        "title": str(meta.get("title") or slug),
        "slug": slug,
        "description": str(meta.get("description") or ""),
        "date": raw_date + " 12:00:00",
        "category": category_key or "",
        "categoryName": category,
        "tags": ", ".join(str(item).strip() for item in categories[1:] if str(item).strip()),
        "dateNeedsReview": date_needs_review,
        "coverImage": cover,
        "content": html,
        "type": "draft",
    }


def articles_to_import(slug: str | None, all_articles: bool) -> list[dict]:
    paths = sorted(ARTICLE_DIR.glob("*.md"))
    if slug:
        selected = []
        for path in paths:
            raw = path.read_text(encoding="utf-8")
            match = re.match(r"\A---\s*\n(.*?)\n---", raw, re.DOTALL)
            if match:
                meta = yaml.safe_load(match.group(1)) or {}
                if str(meta.get("slug") or path.stem) == slug:
                    selected.append(path)
        paths = selected
        if not paths:
            raise ValueError(f"No article with slug: {slug}")
    elif not all_articles:
        raise ValueError("Specify --slug or --all")
    return [prepare(path) for path in paths]


def import_draft(article: dict, base_url: str, api_token: str, auth_token: str) -> str:
    endpoint = base_url.rstrip("/") + "/api/pages"
    check_url = endpoint + "/" + quote(article["slug"]) + "?" + urlencode({"token": api_token})
    try:
        with urlopen(Request(check_url, headers={"Accept": "application/json"}), timeout=10) as response:
            existing = json.load(response)
        if existing.get("status") == "0":
            return "already exists"
    except HTTPError as exc:
        if exc.code != 404:
            raise

    payload = dict(article, token=api_token, authentication=auth_token)
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
    if result.get("status") != "0":
        raise RuntimeError(f"Bludit rejected {article['slug']}: {result.get('message')}")
    return "draft imported"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--slug", help="Import one existing article")
    selection.add_argument("--all", action="store_true", help="Import all articles")
    parser.add_argument("--apply", action="store_true", help="Create drafts in Bludit")
    args = parser.parse_args()

    articles = articles_to_import(args.slug, args.all)
    if not args.apply:
        for article in articles:
            print(f"DRAFT {article['slug']} | {article['date'][:10]} | {article['category']}")
        print(f"{len(articles)} article(s) prepared; nothing sent to Bludit.")
        return

    base_url = os.getenv("BLUDIT_BLOG_URL", "")
    api_token = os.getenv("BLUDIT_BLOG_API_TOKEN", "")
    auth_token = os.getenv("BLUDIT_BLOG_AUTH_TOKEN", "")
    if not all((base_url, api_token, auth_token)):
        raise SystemExit("Bludit URL, API token and auth token are required for --apply.")
    if not base_url.startswith("https://"):
        raise SystemExit("Bludit URL must use HTTPS for --apply.")
    for article in articles:
        print(article["slug"], import_draft(article, base_url, api_token, auth_token))


if __name__ == "__main__":
    main()
