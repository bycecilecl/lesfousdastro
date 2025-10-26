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



# routes/blog.py
from flask import Blueprint, render_template, current_app

blog_bp = Blueprint("blog", __name__)

@blog_bp.route("/blog", strict_slashes=False)
def blog():
    try:
        # ✅ test minimal sans réseau
        articles = [{
            "title": "Test: le blog répond",
            "date": "26 octobre 2025",
            "url": "https://bycecilecl.com",
            "excerpt": "Si tu vois cette carte, la route /blog et le template fonctionnent.",
            "image": "https://bycecilecl.com/wp-content/uploads/default.jpg",
        }]
        return render_template("blog.html", articles=articles)
    except Exception as e:
        current_app.logger.exception("Erreur /blog (stub): %s", e)
        return render_template("blog.html", articles=[])