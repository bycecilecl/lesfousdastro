# utils/pdf_utils.py
import weasyprint
import os
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser


ACCOMPANIMENT_URL = "https://lesfousdastro.fr/prestations#accompagnement"
ACCOMPANIMENT_OFFER = f"""
<aside class="accompaniment-offer" id="accompaniment-offer">
    <h2>Tu veux aller plus loin ?</h2>
    <p>Ce rapport t'offre des pistes de réflexion. Si tu souhaites les relier à ton vécu et explorer ce qui se répète pour toi, je propose un accompagnement individuel avec ton thème astral comme support.</p>
    <p><a href="{ACCOMPANIMENT_URL}">Découvrir l'accompagnement</a><br><span>{ACCOMPANIMENT_URL}</span></p>
</aside>
"""


class _ClosingTagLocator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.body_end = None
        self.html_end = None

    def handle_endtag(self, tag):
        if tag == "body":
            self.body_end = self.getpos()
        elif tag == "html":
            self.html_end = self.getpos()


def append_accompaniment_offer(html_content):
    if 'id="accompaniment-offer"' in html_content:
        return html_content

    parser = _ClosingTagLocator()
    parser.feed(html_content)
    position = parser.body_end or parser.html_end
    if position is None:
        return html_content + ACCOMPANIMENT_OFFER

    line, column = position
    lines = html_content.splitlines(keepends=True)
    offset = sum(len(part) for part in lines[:line - 1]) + column
    return html_content[:offset] + ACCOMPANIMENT_OFFER + html_content[offset:]

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : html_to_pdf(html_content, output_path)
# Rôle : Convertit un contenu HTML en PDF et écrit le fichier sur disque
#        en utilisant WeasyPrint.
# Entrées :
#   - html_content (str) : HTML complet (inline CSS ok)
#   - output_path (str)  : chemin du PDF de sortie (dossiers créés si besoin)
# Dépendances :
#   - weasyprint
#   - chemins relatifs résolus via base_url=os.getcwd()
# Sortie :
#   - True si succès, False si erreur (et log console).
# Où c’est utilisé :
#   - routes/point_astral.py → génération du PDF final du Point Astral
#   - main.py → route /telecharger_point_astral/<nom_fichier>
# Remarques :
#   - Gère un CSS minimal (@page, body, section/break-inside).
#   - Idéal quand on génère d’abord un HTML propre puis on le “print” en PDF.
# ─────────────────────────────────────────────────────────────────────────────

def html_to_pdf(html_content, output_path, page_header="Point Astral - Les Fous d'Astro", include_accompaniment_offer=True):
    """
    Convertit du HTML en PDF en utilisant WeasyPrint
    Compatible avec votre code existant
    """
    try:
        # Créer le dossier de sortie si nécessaire
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Créer le document HTML avec WeasyPrint
        html_doc = weasyprint.HTML(
            string=append_accompaniment_offer(html_content) if include_accompaniment_offer else html_content,
            base_url=os.getcwd()  # Pour résoudre les chemins relatifs
        )
        
        # Le titre courant est personnalisable par rapport. La valeur par défaut
        # conserve le rendu historique des appels existants.
        safe_page_header = str(page_header).replace('\\', '\\\\').replace('"', '\\"')

        # Configuration CSS pour WeasyPrint
        css_text = """
            @page {
                size: A4;
                margin: 20mm;
                @top-center {
                    content: "__PAGE_HEADER__";
                    font-size: 10px;
                    color: #1f628e;
                }
                @bottom-center {
                    content: "© Droits réservés - Les Fous d'Astro";
                    font-size: 10px;
                    color: #666;
                }
            }
            
            body {
                font-family: 'DejaVu Sans', 'Arial', sans-serif;
                font-size: 11px;
                line-height: 1.6;
                color: #2c3e50;
            }
            
            .page-break {
                page-break-before: always;
            }
            
            section {
                break-inside: avoid;
            }

            .encadre-note {
                background: #f7f3ec;
                border-left: 4px solid #b98b5f;
                padding: 16px 20px;
                margin: 20px 20px 24px;
                border-radius: 8px;
                font-size: 0.95em;
                page-break-inside: avoid;
            }

            .encadre-note p {
                margin: 0 0 10px 0;
                line-height: 1.6;
                text-align: left;
                padding: 0;
            }

            .encadre-note p:last-child {
                margin-bottom: 0;
            }

            .encadre-titre {
                font-weight: 700;
                font-size: 1.05em;
                color: #144a6b;
                margin-bottom: 10px !important;
            }

            .accompaniment-offer {
                margin: 28px 0 0;
                padding: 18px 20px;
                border: 1px solid #b7d9d7;
                border-left: 4px solid #00a8a8;
                background: #f2f9f8;
                break-inside: avoid;
                page-break-inside: avoid;
            }

            .accompaniment-offer h2 {
                margin: 0 0 8px;
                color: #144a6b;
                font-size: 15px;
            }

            .accompaniment-offer p {
                margin: 0 0 10px;
                line-height: 1.5;
            }

            .accompaniment-offer p:last-child {
                margin-bottom: 0;
            }

            .accompaniment-offer a {
                color: #126f7b;
                font-weight: 700;
                text-decoration: underline;
            }

            .accompaniment-offer span {
                color: #4a5a61;
                font-size: 9px;
            }
        """
        css = weasyprint.CSS(string=css_text.replace("__PAGE_HEADER__", safe_page_header))
        
        # Générer le PDF
        pdf_bytes = html_doc.write_pdf(stylesheets=[css])
        
        # Écrire le fichier
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
            
        print(f"✅ PDF généré avec succès : {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération du PDF : {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# UTIL : html_to_pdf_bytes(html_content)
# Rôle : Convertit un contenu HTML en PDF et renvoie les bytes (sans écrire
#        sur disque). Utile pour un envoi direct (email, stream HTTP).
# Entrées :
#   - html_content (str) : HTML complet (inline CSS ok)
# Dépendances :
#   - weasyprint
# Sortie :
#   - bytes du PDF si succès, None si erreur (et log console).
# Où c’est utilisé :
#   - (Optionnel) À brancher si tu veux attacher un PDF en mémoire dans un mail
#     sans créer de fichier temporaire.
# Remarques :
#   - CSS minimal appliqué ; ajoute un CSS plus riche si besoin.
# ─────────────────────────────────────────────────────────────────────────────

def html_to_pdf_bytes(html_content):
    """
    Convertit du HTML en PDF et retourne les bytes directement
    """
    try:
        html_doc = weasyprint.HTML(string=html_content, base_url=os.getcwd())
        
        css = weasyprint.CSS(string="""
            @page { size: A4; margin: 20mm; }
            body { font-family: 'DejaVu Sans', 'Arial', sans-serif; font-size: 11px; }
        """)
        
        return html_doc.write_pdf(stylesheets=[css])
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération du PDF : {e}")
        return None
