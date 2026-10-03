"""Prepare the one-click, draft-only import plugin for the editing Bludit.

No network call or server mutation occurs. The resulting ZIP is extracted into
the existing Bludit root, adding one plugin without replacing content.
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from scripts.import_blog_to_bludit import articles_to_import


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tools" / "bludit_import_plugin"
OUTPUT = ROOT / "preproduction" / "fous-blog-import-brouillons-20261003.zip"


def add(archive: ZipFile, name: str, data: bytes, directory: bool = False) -> None:
    entry = ZipInfo(name)
    entry.create_system = 3
    entry.external_attr = (0o40755 if directory else 0o100644) << 16
    entry.compress_type = ZIP_DEFLATED
    archive.writestr(entry, data)


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
        add(archive, prefix, b"", directory=True)
        add(archive, prefix + "languages/", b"", directory=True)
        add(archive, prefix + "plugin.php", (PLUGIN / "plugin.php").read_bytes())
        add(archive, prefix + "metadata.json", (PLUGIN / "metadata.json").read_bytes())
        for language in ("fr_FR.json", "en.json"):
            add(archive, prefix + "languages/" + language, (PLUGIN / "languages" / language).read_bytes())
        payload = json.dumps(articles, ensure_ascii=False)
        php = "<?php defined('BLUDIT') or die('Bludit CMS.');\nreturn json_decode(<<<'FOUS_ARTICLES_JSON'\n" + payload + "\nFOUS_ARTICLES_JSON, true);\n"
        add(archive, prefix + "articles.php", php.encode("utf-8"))
    print(f"Prepared {len(articles)} drafts: {OUTPUT}")


if __name__ == "__main__":
    main()
