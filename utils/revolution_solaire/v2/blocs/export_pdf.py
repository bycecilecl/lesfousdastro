"""Export local RS V2 avec le même habillage et convertisseur que le site."""

from pathlib import Path
import re
from tempfile import TemporaryDirectory

from ...rapport_pdf import LOGO, habiller_rapport_pdf
from ...rapport_html import generer_rapport_html


CSS_HIERARCHIE_BLOCS = """
article h2 { font-size: 22px; line-height: 1.3; font-weight: 700;
    color: #1f4166; margin: 42px 0 22px; padding-bottom: 9px;
    border-bottom: 2px solid #3498db; break-after: avoid; }
article h3, article h4 { font-size: 18px; line-height: 1.35; font-weight: 700;
    color: #1f628e; margin: 24px 0 10px; padding: 0;
    border: 0; break-after: avoid; }
"""


def verifier_export_pdf():
    """Charge les dépendances avant tout appel IA, sans créer de PDF."""
    from utils.pdf_utils import html_to_pdf
    if not LOGO.is_file():
        raise FileNotFoundError("Logo PDF absent : " + str(LOGO))
    return html_to_pdf


def ajouter_disclaimer_rs(html, *, personne, annee):
    """Réutilise le disclaimer du rendu RS du site, sans dupliquer son texte."""
    motif = r'<div class="disclaimer">.*?</div>'
    if re.search(motif, html, flags=re.I | re.S):
        return html
    # Le rendu vide sert uniquement à récupérer le texte commun du site.
    # Aucun calcul astrologique ni appel IA n'intervient dans ce rendu HTML.
    with TemporaryDirectory() as temporaire:
        modele = generer_rapport_html("", Path(temporaire) / "disclaimer.html",
                                      nom=personne.get("nom", ""), annee=annee).read_text(encoding="utf-8")
    disclaimer = re.search(motif, modele, flags=re.I | re.S)
    if disclaimer is None:
        raise ValueError("Le disclaimer du rapport RS du site est introuvable ; le texte du rapport reste conservé.")
    return re.sub(r"(<body\b[^>]*>)", lambda m: m.group(0) + disclaimer.group(0), html, count=1, flags=re.I)


def exporter_pdf(rapport_html, destination, *, personne, lieu_rs, annee):
    convertir = verifier_export_pdf()
    destination = Path(destination)
    # Retirer seulement le bandeau de travail de l'assemblage, pas le texte client.
    html = Path(rapport_html).read_text(encoding="utf-8")
    html = re.sub(r"<aside\b[^>]*>.*?</aside>", "", html, count=1, flags=re.I | re.S)
    html = ajouter_disclaimer_rs(html, personne=personne, annee=annee)
    html_pdf = habiller_rapport_pdf(html, personne=personne, lieu_rs=lieu_rs, annee=annee)
    if 'id="rs-v2-hierarchie"' in html:
        html_pdf = html_pdf.replace("</style>", CSS_HIERARCHIE_BLOCS + "\n</style>", 1)
    # Le bilan commence sur sa propre page. Le contenu n'est ni réduit ni tronqué.
    html_pdf = html_pdf.replace("</style>", "@media print { article#conclusion { break-before: page; } }\n</style>", 1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / "rapport_pdf.html").write_text(html_pdf, encoding="utf-8")
    temporaire = destination.with_name(destination.stem + ".en_cours.pdf")
    if not convertir(html_pdf, str(temporaire), page_header="Révolution Solaire - Les Fous d'Astro") or not temporaire.exists() or not temporaire.stat().st_size:
        temporaire.unlink(missing_ok=True)
        raise RuntimeError("Le texte est conservé, mais le PDF n'a pas pu être créé. Une reprise identique réutilisera les réponses archivées.")
    temporaire.replace(destination)
    return destination
