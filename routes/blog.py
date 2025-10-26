# routes/blog.py — VERSION FINALE (corrections ChatGPT intégrées)

from flask import Blueprint, render_template, current_app
import re, requests, xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape

blog_bp = Blueprint("blog", __name__)

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

def _extract_first_image(html_content: str) -> str | None:
    """Extrait la première image d'un contenu HTML."""
    if not html_content:
        return None
    
    # Cherche les balises img avec src
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if img_match:
        url = img_match.group(1)
        # Vérifie que c'est une vraie image (pas un emoji ou icon)
        if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
            return url
    
    return None

def _rss_fetch_articles(limit: int = 24) -> list[dict]:
    """
    Essaie les flux RSS et retourne les articles formatés.
    Tri par date ISO (YYYY-MM-DD) pour un ordre correct.
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
                    # TITRE - nettoyé
                    raw_title = it.findtext("title") or ""
                    title = _strip_html(raw_title).strip() or "Sans titre"
                    
                    # URL
                    link = (it.findtext("link") or "").strip() or "#"
                    
                    # DATE
                    pub = (it.findtext("pubDate") or "").strip()
                    date_iso = ""
                    try:
                        d = parsedate_to_datetime(pub)
                        date_iso = d.strftime("%Y-%m-%d")
                    except:
                        pass
                    
                    # IMAGE - cherche dans plusieurs endroits
                    img = None
                    
                    # 1) content:encoded
                    content_encoded = it.findtext(f"{NS_CONTENT}encoded") or ""
                    if content_encoded:
                        img = _extract_first_image(content_encoded)
                    
                    # 2) description
                    if not img:
                        description = it.findtext("description") or ""
                        img = _extract_first_image(description)
                    
                    # 3) enclosure
                    if not img:
                        enclosure = it.find("enclosure")
                        if enclosure is not None:
                            enc_url = enclosure.get("url", "")
                            if any(ext in enc_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                img = enc_url
                    
                    # 4) media:content
                    if not img:
                        media_content = it.find(f"{NS_MEDIA}content")
                        if media_content is not None:
                            img = media_content.get("url")
                    
                    # 4bis) media:thumbnail (ajout ChatGPT)
                    if not img:
                        media_thumb = it.find(f"{NS_MEDIA}thumbnail")
                        if media_thumb is not None:
                            img = media_thumb.get("url")
                    
                    # Image par défaut si rien trouvé + décode l'URL (correction ChatGPT)
                    if not img:
                        img = DEFAULT_IMG
                    else:
                        img = unescape(img).strip()  # <= Évite les &amp; qui cassent les URLs
                    
                    # EXCERPT - nettoyé
                    raw_desc = content_encoded or (it.findtext("description") or "")
                    excerpt = _strip_html(raw_desc)
                    if len(excerpt) > 160:
                        excerpt = excerpt[:157].rstrip() + "..."
                    
                    # ✅ Garde date_iso pour le tri (correction ChatGPT)
                    out.append({
                        "title": title,
                        "url": link,
                        "date_iso": date_iso,  # Clé technique pour le tri
                        "date": _format_date_fr(date_iso) if date_iso else "",
                        "excerpt": excerpt,
                        "image": img,
                    })
                    
                except Exception as e:
                    current_app.logger.warning(f"⚠️ Erreur sur un item : {e}")
                    continue

            if out:
                # ✅ Tri par date ISO (YYYY-MM-DD) - correction ChatGPT
                out.sort(key=lambda a: a.get("date_iso", ""), reverse=True)
                
                # ✅ Retire la clé technique avant d'envoyer au template
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