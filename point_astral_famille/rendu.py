# utils/rendu_point_astral.py - FIX FINAL

import re

def transformer_en_sections(texte_brut: str) -> str:
    print("Début transformer_en_sections (fix final)")
    
    # Nouveau pattern pour vos titres actuels
    pattern = r'##\s*([^\n]+)'
    
    try:
        # Diviser par les sections ##
        sections = re.split(pattern, texte_brut)
        
        # Supprimer la première partie vide
        if sections and not sections[0].strip():
            sections = sections[1:]
        
        sections_html = []
        
        # Traiter par paires (titre, contenu)
        for i in range(0, len(sections), 2):
            if i + 1 < len(sections):
                titre = sections[i].strip()
                contenu = sections[i + 1].strip()
                
                if len(contenu) > 50:
                    contenu_html = nettoyer_contenu_html(contenu)
                    classe = determiner_classe_section(titre)
                    
                    section_html = f'''
                        <section class="{classe}">
                            <h2>{titre}</h2>
                            <div class="section-content">
                                {contenu_html}
                            </div>
                        </section>'''
                    sections_html.append(section_html)
        
        return '\n'.join(sections_html)
        
    except Exception as e:
        print(f"Erreur: {e}")
        return fallback_simple(texte_brut)


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
    if not contenu:
        return "<p>Contenu en cours...</p>"

    contenu = re.sub(r'\n\s*---\s*\n', '\n\n', contenu)
    paragraphes = re.split(r'\n\s*\n', contenu.strip())
    contenu_html = ""

    BLOC_TAGS = (
        "<div",
        "<table",
        "<ul",
        "<ol",
        "<blockquote",
        "<section",
    )

    for para in paragraphes:
        para_strip = para.strip()

        # Les blocs HTML déjà construits passent tels quels.
        if para_strip.startswith(BLOC_TAGS):
            contenu_html += para_strip + "\n"
            continue

        para_clean = para_strip.replace('\n', ' ')
        para_clean = re.sub(r'^\d+\.\s*', '', para_clean)

        if para_clean and len(para_clean) > 20:
            contenu_html += f"<p>{para_clean}</p>\n"

    return contenu_html if contenu_html else f"<p>{contenu}</p>"