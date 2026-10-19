from utils.report_presentation import report_text_to_html
# utils/rendu_point_astral.py - FIX FINAL

import re

def transformer_en_sections(texte_brut: str) -> str:
    """Sépare les modules sans confondre ## et les sous-titres ###."""
    parties = re.split(r"(?m)^##(?!#)[ \t]+([^\n]+)\n?", texte_brut)
    sections = []
    if parties[0].strip():
        sections.append('<div class="introduction">' + report_text_to_html(parties[0]) + '</div>')
    for i in range(1, len(parties), 2):
        titre = parties[i].strip()
        contenu = parties[i + 1]
        classe = determiner_classe_section(titre)
        sections.append(
            f'<section class="{classe}"><h2>{titre}</h2>'
            + '<div class="section-content">' + report_text_to_html(contenu)
            + '</div></section>'
        )
    return "\n".join(sections)


def fallback_simple(texte_brut: str) -> str:
    """
    Fallback simple qui divise manuellement par '## Bloc'
    """
    print("🔧 Fallback simple")
    
    # Diviser manuellement
    parties = texte_brut.split('## Bloc')
    sections_html = []
    
    for i, partie in enumerate(parties):
        if not partie.strip():
            continue
            
        # Première partie peut être une intro
        if i == 0 and '–' not in partie:
            if len(partie.strip()) > 20:
                sections_html.append(f'<div class="introduction">{nettoyer_contenu_html(partie)}</div>')
            continue
        
        # Reconstituer le titre
        if '–' in partie:
            ligne_titre = partie.split('\n')[0].strip()
            contenu = '\n'.join(partie.split('\n')[1:]).strip()
            
            # Extraire numéro et titre
            if ' –' in ligne_titre:
                numero_titre, reste_titre = ligne_titre.split(' –', 1)
                numero = numero_titre.strip()
                titre = reste_titre.strip()
                
                if numero.isdigit() and len(contenu) > 50:
                    contenu_html = nettoyer_contenu_html(contenu)
                    classe = determiner_classe_section(titre)
                    
                    section_html = f'''
<section class="{classe}">
    <h2>Bloc {numero} – {titre}</h2>
    <div class="section-content">
        {contenu_html}
    </div>
</section>'''
                    sections_html.append((int(numero), section_html))
    
    # Trier et nettoyer
    sections_html.sort(key=lambda x: x[0])
    sections_html = [html for _, html in sections_html]
    
    return '\n'.join(sections_html) if sections_html else f'<div class="contenu-brut">{texte_brut}</div>'


def determiner_classe_section(titre: str) -> str:
    """Détermine la classe CSS selon le titre"""
    titre_lower = titre.lower()
    
    if any(k in titre_lower for k in ["synthèse", "conclusion", "axes", "vision"]):
        return "conclusion"
    elif any(k in titre_lower for k in ["tension", "défi", "conflit"]):
        return "section tensions"
    elif any(k in titre_lower for k in ["atout", "force", "talent"]):
        return "section atouts"
    else:
        return "section"


def nettoyer_contenu_html(contenu: str) -> str:
    return report_text_to_html(contenu)
