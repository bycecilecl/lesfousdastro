# routes/blog.py — VERSION FINALE (corrections ChatGPT intégrées)

from flask import Blueprint, render_template, current_app
import re, requests, xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin, urlparse
from html import unescape

blog_bp = Blueprint("blog", __name__)

def _normalize_url(url: str, base: str) -> str:
    """Décode &amp;, gère //, relatives -> absolues."""
    if not url:
        return url
    url = unescape(url.strip())
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(base, url)
    return url

# --- Config / constantes ---
DEFAULT_IMG = "https://lesfousdastro.fr/static/img/blog-placeholder.jpg"  # À créer !
FEEDS = [
    "https://bycecilecl.com/category/astrologie/feed/",
    "https://bycecilecl.com/feed/",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/rss+xml, application/xml;q=0.9,*/*;q=0.8",
}

# Namespaces XML (déclarés une seule fois)
NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
NS_MEDIA = "{http://search.yahoo.com/mrss/}"

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
    """Enlève TOUS les tags HTML et nettoie le texte."""
    if not text:
        return ""
    
    # Décode les entités HTML (&nbsp;, &amp;, etc.)
    text = unescape(text)
    
    # Enlève tous les tags HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Nettoie les espaces
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def _extract_first_image(html_content: str, base_page_url: str) -> str | None:
    """
    Cherche une image exploitable dans cet ordre :
    - data-lazy-src / data-src / data-original / data-orig-file
    - srcset (on prend la plus large)
    - src standard
    Retourne une URL normalisée (absolue).
    """
    if not html_content:
        return None

    html_content = unescape(html_content)

    # a) attributs lazy-load courants
    for attr in ("data-lazy-src", "data-src", "data-original", "data-orig-file"):
        m = re.search(fr'{attr}=["\']([^"\']+)["\']', html_content, re.I)
        if m:
            cand = _normalize_url(m.group(1), base_page_url)
            if any(ext in cand.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                return cand

    # b) srcset → prendre l’URL avec la plus grande largeur
    m = re.search(r'srcset=["\']([^"\']+)["\']', html_content, re.I)
    if m:
        srcset = m.group(1)
        best_url, best_w = None, -1
        # srcset: "url1 300w, url2 768w, url3 1024w"
        for part in srcset.split(","):
            part = part.strip()
            if not part:
                continue
            pieces = part.split()
            url_part = pieces[0]
            width = 0
            if len(pieces) > 1 and pieces[1].lower().endswith("w"):
                try:
                    width = int(pieces[1][:-1])
                except:
                    width = 0
            cand = _normalize_url(url_part, base_page_url)
            if any(ext in cand.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                if width > best_w:
                    best_url, best_w = cand, width
        if best_url:
            return best_url

    # c) src standard
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.I)
    if m:
        cand = _normalize_url(m.group(1), base_page_url)
        if any(ext in cand.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return cand

    return None

def _rss_fetch_articles(limit: int = 24) -> list[dict]:
    """
    Essaie les flux RSS et retourne les articles formatés.
    Tri par date ISO (YYYY-MM-DD) pour un ordre correct.
    Passe l'URL de base au parseur d'images pour gérer lazy-load, srcset et URLs relatives.
    """
    for feed_url in FEEDS:
        try:
            current_app.logger.info(f"📡 Tentative RSS : {feed_url}")

            r = requests.get(feed_url, headers=HEADERS, timeout=10)
            r.raise_for_status()

            # Parse le XML
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue

            items = channel.findall("item")
            current_app.logger.info(f"✅ Trouvé {len(items)} articles dans {feed_url}")

            out: list[dict] = []

            for it in items:
                try:
                    # TITRE
                    raw_title = it.findtext("title") or ""
                    title = _strip_html(raw_title).strip() or "Sans titre"

                    # URL de l'article (avec normalisation)
                    raw_link = (it.findtext("link") or "").strip()
                    link = _normalize_url(raw_link, "https://bycecilecl.com/") if raw_link else "#"

                    # log pour vérifier
                    current_app.logger.info(f"🔗 Lien brut trouvé : {raw_link}")
                    current_app.logger.info(f"🔗 Lien normalisé : {link}")

                    # base pour les images
                    base_for_images = link or "https://bycecilecl.com/"

                    # DATE -> ISO
                    pub = (it.findtext("pubDate") or "").strip()
                    date_iso = ""
                    try:
                        d = parsedate_to_datetime(pub)
                        date_iso = d.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                    # ---- IMAGE : on essaie plusieurs sources ----
                    img = None

                    # 1) content:encoded (souvent la meilleure source)
                    content_encoded = it.findtext(f"{NS_CONTENT}encoded") or ""
                    if content_encoded:
                        img = _extract_first_image(content_encoded, base_for_images)

                    # 2) description (parfois l'image est là)
                    if not img:
                        description = it.findtext("description") or ""
                        img = _extract_first_image(description, base_for_images)

                    # 3) enclosure (WordPress/Jerpack peuvent déposer une image ici)
                    if not img:
                        enclosure = it.find("enclosure")
                        if enclosure is not None and enclosure.get("url"):
                            enc_url = _normalize_url(enclosure.get("url"), base_for_images)
                            if any(ext in enc_url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                                img = enc_url

                    # 4) media:content
                    if not img:
                        media_content = it.find(f"{NS_MEDIA}content")
                        if media_content is not None and media_content.get("url"):
                            img = _normalize_url(media_content.get("url"), base_for_images)

                    # 4bis) media:thumbnail
                    if not img:
                        media_thumb = it.find(f"{NS_MEDIA}thumbnail")
                        if media_thumb is not None and media_thumb.get("url"):
                            img = _normalize_url(media_thumb.get("url"), base_for_images)

                    # fallback + nettoyage final
                    if not img:
                        img = DEFAULT_IMG
                    else:
                        img = unescape(img).strip()

                    # EXCERPT
                    raw_desc = content_encoded or (it.findtext("description") or "")
                    excerpt = _strip_html(raw_desc)
                    if len(excerpt) > 160:
                        excerpt = excerpt[:157].rstrip() + "..."

                    # Empile
                    out.append({
                        "title": title,
                        "url": link,
                        "date_iso": date_iso,  # clé technique pour le tri
                        "date": _format_date_fr(date_iso) if date_iso else "",
                        "excerpt": excerpt,
                        "image": img,
                    })

                except Exception as e:
                    current_app.logger.warning(f"⚠️ Erreur sur un item : {e}")
                    continue

            if out:
                # Tri sur la vraie date (ISO), puis on enlève la clé technique
                out.sort(key=lambda a: a.get("date_iso", ""), reverse=True)
                for a in out:
                    a.pop("date_iso", None)
                current_app.logger.info(f"✅ {len(out)} articles extraits et triés")
                return out[:limit]

        except Exception as e:
            current_app.logger.warning(f"⚠️ Erreur RSS sur {feed_url}: {e}")
            continue

    current_app.logger.error("❌ Aucun flux RSS n'a fonctionné")
    return []

@blog_bp.route("/blog", strict_slashes=False)
def blog():
    """Route principale du blog"""
    try:
        articles = _rss_fetch_articles(limit=24)
        
        if not articles:
            current_app.logger.warning("⚠️ Aucun article récupéré")
        else:
            current_app.logger.info(f"✅ {len(articles)} articles envoyés au template")
        
        return render_template("blog.html", articles=articles)
        
    except Exception as e:
        current_app.logger.exception(f"❌ Erreur critique /blog: {e}")
        return render_template("blog.html", articles=[])