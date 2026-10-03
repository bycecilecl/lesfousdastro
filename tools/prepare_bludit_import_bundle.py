"""Prepare the one-click, draft-only import plugin for the editing Bludit.

No network call or server mutation occurs. The resulting ZIP is extracted into
the existing Bludit root, adding one plugin without replacing content.
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.import_blog_to_bludit import articles_to_import


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tools" / "bludit_import_plugin"
OUTPUT = ROOT / "preproduction" / "fous-blog-import-brouillons-20261003.zip"


def main() -> None:
    articles = articles_to_import(slug=None, all_articles=True)
    slugs = [article["slug"] for article in articles]
    if len(articles) != 42 or len(set(slugs)) != 42:
        raise RuntimeError("Expected exactly 42 unique articles")
    if any(article["type"] != "draft" or not article["category"] for article in articles):
        raise RuntimeError("Every imported article must be a categorized draft")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        prefix = "bl-plugins/fous-blog-import/"
        archive.write(PLUGIN / "plugin.php", prefix + "plugin.php")
        archive.write(PLUGIN / "metadata.json", prefix + "metadata.json")
        archive.writestr(prefix + "articles.json", json.dumps(articles, ensure_ascii=False))
    print(f"Prepared {len(articles)} drafts: {OUTPUT}")


if __name__ == "__main__":
    main()
