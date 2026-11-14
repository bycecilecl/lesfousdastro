"""Rendu et recadrage des cartes, uniquement sur action d’upload de l’administratrice."""
from io import BytesIO
import math
from threading import Lock
import warnings

from PIL import Image, ImageOps

VERROU_PDF = Lock()
COTE_MAX = 3200


def image_de_travail(contenu, page=1):
    """Image orientée et proportionnelle, commune à l’aperçu et à l’enregistrement."""
    if contenu.startswith(b"%PDF-"):
        try:
            import pypdfium2 as pdfium
            with VERROU_PDF:
                pdf = pdfium.PdfDocument(contenu)
                try:
                    pages = len(pdf)
                    if not 1 <= pages <= 100 or not 1 <= page <= pages:
                        raise ValueError("Choisis une page disponible du PDF.")
                    feuille = pdf.get_page(page - 1)
                    try:
                        largeur, hauteur = feuille.get_size()
                        if not all(math.isfinite(v) and v > 0 for v in (largeur, hauteur)):
                            raise ValueError("Cette page PDF n’a pas de dimensions valides.")
                        echelle = min(3.0, COTE_MAX / max(largeur, hauteur))
                        bitmap = feuille.render(scale=echelle)
                        try:
                            image = bitmap.to_pil().copy()
                        finally:
                            bitmap.close()
                    finally:
                        feuille.close()
                finally:
                    pdf.close()
        except ValueError:
            raise
        except Exception:
            raise ValueError("Le PDF n’a pas pu être converti en image. Essaie avec une image PNG ou JPG.") from None
    else:
        pages = 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(contenu)) as source:
                    if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > 40_000_000:
                        raise ValueError()
                    source.thumbnail((COTE_MAX, COTE_MAX), Image.Resampling.LANCZOS)
                    image = ImageOps.exif_transpose(source).copy()
        except Exception:
            raise ValueError("Cette image ne peut pas être préparée. Choisis un PNG, JPG ou WebP lisible.") from None
    # Fond blanc pour les transparences ; aucune déformation de la carte.
    if image.mode in {"RGBA", "LA", "P"}:
        avec_alpha = image.convert("RGBA")
        fond = Image.new("RGBA", image.size, "white")
        fond.alpha_composite(avec_alpha)
        image = fond.convert("RGB")
    else:
        image = image.convert("RGB")
    image.thumbnail((COTE_MAX, COTE_MAX), Image.Resampling.LANCZOS)
    return image, pages


def webp(image, *, apercu=False):
    copie = image.copy()
    if apercu:
        copie.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    sortie = BytesIO()
    # Les lignes fines et les petits degrés restent nets ; pas de perte JPEG.
    copie.save(sortie, format="WEBP", lossless=True, quality=100, method=4)
    return sortie.getvalue()


def recadrer(image, valeurs):
    if valeurs in (None, ""):
        return image
    import json
    try:
        rectangle = json.loads(valeurs)
        if not isinstance(rectangle, list) or len(rectangle) != 4:
            raise ValueError()
        x, y, largeur, hauteur = map(float, rectangle)
        if not all(math.isfinite(v) for v in (x, y, largeur, hauteur)):
            raise ValueError()
        if min(x, y) < 0 or min(largeur, hauteur) <= 0 or x + largeur > 1.000001 or y + hauteur > 1.000001:
            raise ValueError()
        gauche, haut = round(x * image.width), round(y * image.height)
        droite = min(image.width, round((x + largeur) * image.width))
        bas = min(image.height, round((y + hauteur) * image.height))
        if droite - gauche < 32 or bas - haut < 32:
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Le recadrage est trop petit ou sort de l’image. Sélectionne à nouveau la zone à conserver.") from None
    return image.crop((gauche, haut, droite, bas))
