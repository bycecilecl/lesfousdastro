"""Read published blog articles from the separate Bludit writing space.

The existing Markdown articles remain available while the migration is tested.
Only the read-only Bludit API token is needed by this application.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_log = logging.getLogger(__name__)
_lock = threading.Lock()
_cache: dict[str, object] = {"key": None, "until": 0.0, "last_success": 0.0, "pages": []}


def published_pages() -> list[dict]:
    """Return Bludit's published pages, or an empty list if not configured.

    A short cache avoids an external request on every page view. If the CMS is
    briefly unavailable, the last successful result stays visible for up to
    one hour; the old Markdown articles still provide a fallback otherwise.
    """
    base_url = os.getenv("BLUDIT_BLOG_URL", "").rstrip("/")
    token = os.getenv("BLUDIT_BLOG_API_TOKEN", "")
    if not base_url or not token:
        return []
    if not base_url.startswith("https://"):
        _log.warning("Bludit blog URL must use HTTPS")
        return []

    cache_key = (base_url, token)
    now = time.monotonic()
    with _lock:
        if _cache["key"] == cache_key and now < _cache["until"]:
            return list(_cache["pages"])

        query = urlencode({"token": token, "numberOfItems": -1, "published": "true"})
        request = Request(
            f"{base_url}/api/pages?{query}",
            headers={"Accept": "application/json", "User-Agent": "LesFousDAstroBlog/1.0"},
        )
        try:
            with urlopen(request, timeout=4) as response:
                payload = json.load(response)
            if payload.get("status") != "0" or not isinstance(payload.get("data"), list):
                raise ValueError("unexpected Bludit API response")
            pages = [
                page for page in payload["data"]
                if isinstance(page, dict) and page.get("type") == "published"
            ]
        except (OSError, ValueError, TypeError) as exc:
            _log.warning("Bludit blog unavailable (%s)", type(exc).__name__)
            if _cache["key"] == cache_key and now < _cache["last_success"] + 3600:
                _cache["until"] = now + 60
                return list(_cache["pages"])
            _cache.update({"key": cache_key, "until": now + 60, "last_success": 0.0, "pages": []})
            return []

        _cache.update({"key": cache_key, "until": now + 60, "last_success": now, "pages": pages})
        return list(pages)
