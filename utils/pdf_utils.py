# utils/pdf_utils.py
import weasyprint
import os
from pathlib import Path

def html_to_pdf(html_content, output_path):
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
            string=html_content,
            base_url=os.getcwd()  # Pour résoudre les chemins relatifs
        )
        
        # Configuration CSS pour WeasyPrint
        css = weasyprint.CSS(string="""
            @page {
                size: A4;
                margin: 20mm;
                @top-center {
                    content: "Point Astral - Les Fous d'Astro";
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
        """)
        
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