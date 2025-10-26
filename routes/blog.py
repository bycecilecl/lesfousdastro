# routes/blog.py
from flask import Blueprint, render_template
import requests
import re
from datetime import datetime, timezone
from functools import lru_cache

blog_bp = Blueprint("blog", __name__)

# --- CONFIG ---
WP_BASE = "https://bycecilecl.com/wp-json/wp/v2"
# Slugs (catégories ET/OU tags) à garder. Mets ici tes vrais slugs WordPress.
ALLOWED_TERM_SLUGS = {"astrologie", "astro"}
PER_PAGE = 30
TIMEOUT = 10
RETRIES = 2

# --- Utilitaires ---

def format_date_fr(date_iso_yyyy_mm_dd: str) -> str:
    """Transforme '2025-06-29' -> '29 juin 2025' (sans dépendance externe)."""
    try:
        d = datetime.strptime(date_iso_yyyy_mm_dd, "%Y-%m-%d")
        mois_fr = [
            "", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"
        ]
        return f"{d.day} {mois_fr[d.month]} {d.year}"
    except Exception:
        return date_iso_yyyy_mm_dd

def _clean_excerpt(html: str, max_len: int = 150) -> str:
    """Nettoie l’extrait HTML WordPress en texte court lisible."""
    txt = re.sub(r"<.*?>", "", html or "")
    txt = (txt.replace("&nbsp;", " ")
              .replace("[&hellip;]", "…")
              .replace("\xa0", " ")
              .strip())
    return (txt[:max_len] + "...") if len(txt) > max_len else txt

def _featured_image(post: dict) -> str | None:
    try:
        media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
        if media and isinstance(media, list):
            return media[0].get("source_url")
    except Exception:
        pass
    return None

def _has_allowed_term(post: dict) -> bool:
    """
    True si le post a au moins un tag/catégorie dont le slug ∈ ALLOWED_TERM_SLUGS.
    On lit _embedded['wp:term'] (grâce à _embed=true).
    """
    emb = post.get("_embedded") or {}
    terms_groups = emb.get("wp:term") or []
    for group in terms_groups:
        for term in group or []:
            slug = (term.get("slug") or "").lower()
            if slug in ALLOWED_TERM_SLUGS:
                return True
    return False

def _post_to_article(post: dict) -> dict:
    date_iso = (post.get("date") or "")[:10]
    return {
        "title": (post.get("title", {}) or {}).get("rendered", "Sans titre"),
        "date": format_date_fr(date_iso),  # ✅ français
        "url": post.get("link") or "#",
        "excerpt": _clean_excerpt((post.get("excerpt", {}) or {}).get("rendered", "")),
        "image": _featured_image(post) or "https://bycecilecl.com/wp-content/uploads/default.jpg",
    }

# --- Récupération (avec cache horaire) ---

@lru_cache(maxsize=1)
def _fetch_posts_with_embed(cache_hour_key: str) -> list[dict]:
    """
    Récupère les posts avec _embed=1. User-Agent 'navigateur' et Referer
    pour éviter certains 403 ; + 1 retry léger.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://lesfousdastro.fr/blog",
    }
    params = {"per_page": PER_PAGE, "_embed": "1", "orderby": "date", "order": "desc"}

    last_err = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(f"{WP_BASE}/posts", params=params, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            # petit retry (réseau lent / micro-coupure)
            continue

    print("⚠️ WP posts embed error:", last_err)
    return []

# --- Route ---

@blog_bp.route("/blog", strict_slashes=False)
def blog():
    # ✅ corrige la dépréciation de utcnow()
    cache_hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")

    all_posts = _fetch_posts_with_embed(cache_hour_key)

    # 🔎 filtre sur les slugs autorisés (catégories/tags)
    posts = [p for p in all_posts if _has_allowed_term(p)]

    # transforme pour le template
    articles = [_post_to_article(p) for p in posts]

    # Option : limiter l’affichage
    # articles = articles[:18]

    return render_template("blog.html", articles=articles)