# # routes/blog.py
# from flask import Blueprint, render_template, current_app

# # ✅ le Blueprint doit exister dès l'import
# blog_bp = Blueprint("blog", __name__)

# @blog_bp.route("/blog", strict_slashes=False)
# def blog():
#     try:
#         # ⬇️ imports et réseau ici, pas au top (évite de casser l'import)
#         import requests, re
#         from datetime import datetime, timezone
#         from functools import lru_cache

#         WP_BASE = "https://bycecilecl.com/wp-json/wp/v2"
#         ALLOWED_TERM_SLUGS = {"astrologie", "astro"}
#         PER_PAGE, TIMEOUT, RETRIES = 30, 10, 2

#         def format_date_fr(s: str) -> str:
#             from datetime import datetime
#             try:
#                 d = datetime.strptime(s, "%Y-%m-%d")
#                 mois = ["","janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
#                 return f"{d.day} {mois[d.month]} {d.year}"
#             except Exception:
#                 return s

#         def _clean_excerpt(html: str, max_len: int = 150) -> str:
#             txt = re.sub(r"<.*?>", "", html or "").replace("&nbsp;"," ").replace("[&hellip;]","…").strip()
#             return (txt[:max_len] + "...") if len(txt) > max_len else txt

#         def _featured_image(post: dict):
#             try:
#                 media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
#                 if media and isinstance(media, list):
#                     return media[0].get("source_url")
#             except Exception:
#                 pass
#             return None

#         def _has_allowed_term(post: dict) -> bool:
#             emb = post.get("_embedded") or {}
#             for group in (emb.get("wp:term") or []):
#                 for term in (group or []):
#                     if (term.get("slug") or "").lower() in ALLOWED_TERM_SLUGS:
#                         return True
#             return False

#         def _post_to_article(p: dict) -> dict:
#             date_iso = (p.get("date") or "")[:10]
#             return {
#                 "title": (p.get("title", {}) or {}).get("rendered", "Sans titre"),
#                 "date": format_date_fr(date_iso),
#                 "url": p.get("link") or "#",
#                 "excerpt": _clean_excerpt((p.get("excerpt", {}) or {}).get("rendered", "")),
#                 "image": _featured_image(p) or "https://bycecilecl.com/wp-content/uploads/default.jpg",
#             }

#         @lru_cache(maxsize=1)
#         def _fetch_posts_with_embed(cache_hour_key: str):
#             headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://lesfousdastro.fr/blog"}
#             params = {"per_page": PER_PAGE, "_embed": "1", "orderby": "date", "order": "desc"}
#             last_err = None
#             for _ in range(RETRIES):
#                 try:
#                     r = requests.get(f"{WP_BASE}/posts", params=params, headers=headers, timeout=TIMEOUT)
#                     r.raise_for_status()
#                     return r.json()
#                 except Exception as e:
#                     last_err = e
#                     continue
#             current_app.logger.warning("WP posts embed error: %s", last_err)
#             return []

#         cache_hour_key = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d-%H")
#         posts = [p for p in _fetch_posts_with_embed(cache_hour_key) if _has_allowed_term(p)]
#         articles = [_post_to_article(p) for p in posts]
#         return render_template("blog.html", articles=articles)

#     except Exception as e:
#         current_app.logger.exception("Erreur /blog: %s", e)
#         return render_template("blog.html", articles=[])



from flask import Blueprint, render_template, current_app
import re, requests, xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

blog_bp = Blueprint("blog", __name__)

def _format_date_fr(date_iso: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d")
        mois = ["","janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
        return f"{d.day} {mois[d.month]} {d.year}"
    except Exception:
        return date_iso

def _rss_fetch_articles() -> list[dict]:
    FEEDS = [
        "https://bycecilecl.com/category/astrologie/feed/",
        "https://bycecilecl.com/categorie/astrologie/feed/",
        "https://bycecilecl.com/feed/",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/rss+xml, application/xml;q=0.9,*/*;q=0.8",
    }
    for url in FEEDS:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
            out = []
            for it in items:
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                pub  = (it.findtext("pubDate") or "").strip()

                # date → ISO
                date_iso = ""
                try:
                    d = parsedate_to_datetime(pub)  # ex: Sun, 26 Oct 2025 09:12:00 +0000
                    date_iso = d.strftime("%Y-%m-%d")
                except Exception:
                    pass

                # image
                img = None
                ns_media = "{http://search.yahoo.com/mrss/}"
                media_content = it.find(f"{ns_media}content")
                if media_content is not None and media_content.get("url"):
                    img = media_content.get("url")
                if not img:
                    enc = it.find("enclosure")
                    if enc is not None and enc.get("url"):
                        img = enc.get("url")
                if not img:
                    raw_html = (it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or "")
                    m = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', raw_html, re.I)
                    if m:
                        img = m.group(1)

                out.append({
                    "title": title or "Sans titre",
                    "url": link or "#",
                    "date": _format_date_fr(date_iso) if date_iso else "",
                    "excerpt": "",  # l’extrait RSS est rarement propre → on laisse vide
                    "image": img or "https://bycecilecl.com/wp-content/uploads/default.jpg",
                })
            if out:
                return out
        except Exception as e:
            current_app.logger.warning("RSS error on %s: %s", url, e)
    return []

@blog_bp.route("/blog", strict_slashes=False)
def blog():
    try:
        articles = _rss_fetch_articles()
        # option: limiter à 24
        articles = articles[:24]
        return render_template("blog.html", articles=articles)
    except Exception as e:
        current_app.logger.exception("Erreur /blog (rss): %s", e)
        return render_template("blog.html", articles=[])