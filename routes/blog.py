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

# routes/blog.py — À coller tel quel (REMPLACE ton implémentation RSS actuelle)

from flask import Blueprint, render_template, current_app
import re, requests, xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

blog_bp = Blueprint("blog", __name__)

# --- Config / constantes ---
DEFAULT_IMG = "https://lesfousdastro.fr/static/img/blog-placeholder.jpg"
FEEDS = [
    "https://bycecilecl.com/category/astrologie/feed/",
    "https://bycecilecl.com/categorie/astrologie/feed/",
    "https://bycecilecl.com/feed/",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/rss+xml, application/xml;q=0.9,*/*;q=0.8",
}
# Namespaces courants
NS_MEDIA = "{http://search.yahoo.com/mrss/}"
NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"

def _format_date_fr(date_iso: str) -> str:
    """Transforme 'YYYY-MM-DD' -> '29 juin 2025'."""
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d")
        mois = ["","janvier","février","mars","avril","mai","juin","juillet",
                "août","septembre","octobre","novembre","décembre"]
        return f"{d.day} {mois[d.month]} {d.year}"
    except Exception:
        return date_iso

def _strip_html(text: str) -> str:
    """Enlève les balises pour fabriquer un petit extrait lisible."""
    txt = re.sub(r"<.*?>", "", text or "")
    txt = txt.replace("&nbsp;", " ").replace("\xa0", " ").strip()
    return txt

def _extract_image_from_item(it: ET.Element) -> str | None:
    """
    Essaie dans l'ordre :
      1) <media:content> (plus grande surface si plusieurs)
      2) <media:thumbnail>
      3) <enclosure url="...">
      4) 1ère <img src="..."> dans <content:encoded>
      5) 1ère <img src="..."> dans <description>
      6) None
    Compatible Jetpack i*.wp.com avec query-string (fit=..., ssl=1, etc.).
    """
    # 1) media:content — on prend l'image avec la plus grande surface
    try:
        media_contents = it.findall(f"{NS_MEDIA}content")
        best_url, best_area = None, -1
        for mc in media_contents:
            url = mc.get("url")
            medium = (mc.get("medium") or "").lower()
            w = int(mc.get("width") or 0)
            h = int(mc.get("height") or 0)
            area = w * h
            if url and (medium in ("", "image")):
                if area > best_area:
                    best_url, best_area = url, area
        if best_url:
            return best_url
    except Exception:
        pass

    # 2) media:thumbnail
    try:
        thumb = it.find(f"{NS_MEDIA}thumbnail")
        if thumb is not None and thumb.get("url"):
            return thumb.get("url")
    except Exception:
        pass

    # 3) enclosure
    try:
        enc = it.find("enclosure")
        if enc is not None and enc.get("url"):
            return enc.get("url")
    except Exception:
        pass

    # 4) content:encoded — première balise <img ... src="...">
    try:
        raw_html = (it.findtext(f"{NS_CONTENT}encoded") or "")
        m = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']', raw_html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass

    # 5) description — idem
    try:
        desc = (it.findtext("description") or "")
        m = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']', desc, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass

    # 6) rien trouvé
    return None

def _rss_fetch_articles(limit: int = 24) -> list[dict]:
    """
    Essaie les flux spécialisés 'astrologie' puis le flux global.
    Retourne une liste déjà prête pour le template: title, url, date, excerpt, image.
    """
    for url in FEEDS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
            out: list[dict] = []

            for it in items:
                title = (it.findtext("title") or "").strip() or "Sans titre"
                link  = (it.findtext("link") or "").strip() or "#"
                pub   = (it.findtext("pubDate") or "").strip()

                # pubDate -> YYYY-MM-DD
                date_iso = ""
                try:
                    d = parsedate_to_datetime(pub)  # ex: Sun, 26 Oct 2025 09:12:00 +0000
                    date_iso = d.strftime("%Y-%m-%d")
                except Exception:
                    pass

                # image robuste
                img = _extract_image_from_item(it) or DEFAULT_IMG

                # petit extrait lisible depuis description/content
                raw_desc = (it.findtext("description") or "") \
                           or (it.findtext(f"{NS_CONTENT}encoded") or "")
                excerpt = _strip_html(raw_desc)
                if len(excerpt) > 160:
                    excerpt = excerpt[:157].rstrip() + "..."

                out.append({
                    "title": title,
                    "url": link,
                    "date": _format_date_fr(date_iso) if date_iso else "",
                    "excerpt": excerpt,
                    "image": img,
                })

            if out:
                # tri par date (si dispo), décroissant, puis limite
                out.sort(key=lambda a: a.get("date", ""), reverse=True)
                return out[:limit]

        except Exception as e:
            current_app.logger.warning("RSS error on %s: %s", url, e)

    return []

@blog_bp.route("/blog", strict_slashes=False)
def blog():
    try:
        articles = _rss_fetch_articles(limit=24)
        return render_template("blog.html", articles=articles)
    except Exception as e:
        current_app.logger.exception("Erreur /blog (rss): %s", e)
        # on affiche la page avec liste vide (pas de 500)
        return render_template("blog.html", articles=[])