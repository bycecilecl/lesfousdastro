# routes/blog.py — version finale filtrée "Astrologie" + fallback RSS + og:image

from flask import Blueprint, render_template, current_app
import re, requests, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from functools import lru_cache
from email.utils import parsedate_to_datetime
from html import unescape

blog_bp = Blueprint("blog", __name__)

# --------- CONFIG ----------
WP_BASE = "https://bycecilecl.com/wp-json/wp/v2"
PER_PAGE = 30
TIMEOUT = 8
RETRIES = 2
ALLOWED_TERM_SLUGS = {"astrologie", "astro"}  # filtrage WordPress
DEFAULT_IMG = "https://lesfousdastro.fr/static/img/blog-placeholder.jpg"  # ton image par défaut

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (compatible; LesFousdAstroBot/1.0; +https://lesfousdastro.fr/blog)",
    "Accept": "application/json",
    "Referer": "https://lesfousdastro.fr/blog",
}
HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (compatible; LesFousdAstroBot/1.0; +https://lesfousdastro.fr/blog)",
    "Accept": "text/html,application/xhtml+xml",
}

# 👉 flux RSS uniquement "astrologie"
FEEDS = [
    "https://bycecilecl.com/category/astrologie/feed/",
    "https://bycecilecl.com/categorie/astrologie/feed/",
]

NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
NS_MEDIA = "{http://search.yahoo.com/mrss/}"


# --------- Utils ----------
def _format_date_fr(date_iso_yyyy_mm_dd: str) -> str:
    try:
        d = datetime.strptime(date_iso_yyyy_mm_dd, "%Y-%m-%d")
        mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{d.day} {mois[d.month]} {d.year}"
    except Exception:
        return date_iso_yyyy_mm_dd


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _find_og_image(url: str) -> str | None:
    """Cherche la balise <meta property='og:image'> sur la page."""
    if not url or url == "#":
        return None
    try:
        r = requests.get(url, headers=HEADERS_HTML, timeout=3)
        r.raise_for_status()
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.I)
        if m:
            return unescape(m.group(1).strip())
    except Exception as e:
        current_app.logger.debug(f"og:image fetch fail for {url}: {e}")
    return None


# --------- API WordPress ----------
def _has_allowed_term_wp(post: dict) -> bool:
    """Filtre sur catégories/tags (slugs autorisés)."""
    emb = post.get("_embedded") or {}
    for group in emb.get("wp:term") or []:
        for term in group or []:
            slug = (term.get("slug") or "").lower()
            if slug in ALLOWED_TERM_SLUGS:
                return True
    return False


def _featured_image_wp(post: dict) -> str | None:
    try:
        media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
        if media and isinstance(media, list):
            return media[0].get("source_url")
    except Exception:
        pass
    return None


def _post_to_article_wp(post: dict) -> dict:
    date_iso = (post.get("date") or "")[:10]
    url = post.get("link") or "#"
    image = _featured_image_wp(post)
    if not image:
        image = _find_og_image(url) or DEFAULT_IMG
    return {
        "title": (post.get("title", {}) or {}).get("rendered", "Sans titre"),
        "date": _format_date_fr(date_iso) if date_iso else "",
        "url": url,
        "excerpt": _strip_html((post.get("excerpt", {}) or {}).get("rendered", "")),
        "image": image,
        "date_iso": date_iso,
    }


@lru_cache(maxsize=1)
def _fetch_wp_api_posts(cache_key: str) -> list[dict]:
    """Tente l’API /wp-json/wp/v2/posts?_embed=1 (avec cache horaire)."""
    params = {"per_page": PER_PAGE, "_embed": "1", "orderby": "date", "order": "desc"}
    last_err = None
    for _ in range(RETRIES):
        try:
            r = requests.get(f"{WP_BASE}/posts", params=params, headers=HEADERS_API, timeout=TIMEOUT)
            if r.status_code >= 400:
                raise requests.HTTPError(f"{r.status_code} for {r.url}")
            return r.json()
        except Exception as e:
            last_err = e
    current_app.logger.warning(f"WP API failed → {last_err}")
    return []


# --------- RSS fallback ----------
def _extract_first_image_from_html(html: str) -> str | None:
    if not html:
        return None
    html = unescape(html)
    for attr in ("data-lazy-src", "data-src", "data-original", "data-orig-file"):
        m = re.search(fr'{attr}=["\']([^"\']+)["\']', html, re.I)
        if m:
            cand = m.group(1).strip()
            if any(ext in cand.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                return cand
    m = re.search(r'srcset=["\']([^"\']+)["\']', html, re.I)
    if m:
        best, wbest = None, -1
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            bits = part.split()
            url = bits[0]
            w = 0
            if len(bits) > 1 and bits[1].endswith("w"):
                try:
                    w = int(bits[1][:-1])
                except:
                    pass
            if any(ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")) and w > wbest:
                best, wbest = url, w
        if best:
            return best
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
    if m:
        cand = m.group(1).strip()
        if any(ext in cand.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return cand
    return None


def _post_to_article_rss(item: ET.Element) -> dict:
    title = _strip_html(item.findtext("title") or "") or "Sans titre"
    link = (item.findtext("link") or "").strip() or "#"
    date_iso = ""
    pub = (item.findtext("pubDate") or "").strip()
    try:
        d = parsedate_to_datetime(pub)
        date_iso = d.strftime("%Y-%m-%d")
    except Exception:
        pass

    img = None
    content = item.findtext(f"{NS_CONTENT}encoded") or ""
    if content:
        img = _extract_first_image_from_html(content)
    if not img:
        desc = item.findtext("description") or ""
        img = _extract_first_image_from_html(desc)
    if not img:
        enc = item.find("enclosure")
        if enc is not None and enc.get("url"):
            url = enc.get("url").strip()
            if any(ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                img = url
    if not img:
        media = item.find(f"{NS_MEDIA}content")
        if media is not None and media.get("url"):
            img = media.get("url").strip()
    if not img:
        img = _find_og_image(link)

    image = img or DEFAULT_IMG
    excerpt_src = content or (item.findtext("description") or "")
    excerpt = _strip_html(excerpt_src)
    if len(excerpt) > 160:
        excerpt = excerpt[:157].rstrip() + "..."

    return {
        "title": title,
        "url": link,
        "date": _format_date_fr(date_iso) if date_iso else "",
        "image": image,
        "excerpt": excerpt,
        "date_iso": date_iso,
    }


def _fetch_rss_posts() -> list[dict]:
    """Lit uniquement les flux RSS Astrologie."""
    for feed in FEEDS:
        try:
            r = requests.get(feed, headers={"User-Agent": HEADERS_API["User-Agent"], "Accept": "application/rss+xml"}, timeout=TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue
            out = [_post_to_article_rss(it) for it in channel.findall("item")]
            if out:
                return out
        except Exception as e:
            current_app.logger.warning(f"RSS failed on {feed}: {e}")
    return []


# --------- Route ----------
@blog_bp.route("/blog", strict_slashes=False)
def blog():
    """Affiche uniquement les articles astrologie."""
    cache_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    articles = []

    # 1) Tente API
    api_posts = _fetch_wp_api_posts(cache_key)
    if api_posts:
        for p in api_posts:
            if _has_allowed_term_wp(p):
                articles.append(_post_to_article_wp(p))

    # 2) Sinon fallback RSS
    if not articles:
        rss_posts = _fetch_rss_posts()
        articles.extend(rss_posts)

    # tri + limite
    articles.sort(key=lambda a: a.get("date_iso", ""), reverse=True)
    for a in articles:
        a.pop("date_iso", None)
    articles = articles[:24]

    if not articles:
        current_app.logger.warning("Blog: aucun article récupéré (API et RSS KO)")

    return render_template("blog.html", articles=articles)