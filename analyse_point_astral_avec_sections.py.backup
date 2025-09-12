import re
import os
import base64
from utils.rag_utils_optimized import generer_corpus_rag_optimise


# ────────────────────────────────────────────────
# FONCTION : transformer_en_sections
# Objectif : Transforme un texte brut ou markdown généré par le LLM
# en sections HTML bien structurées avec titres et paragraphes.
# Étapes :
#   1. Détecte différents formats de titres via regex (plusieurs patterns testés).
#   2. Si aucun titre n’est trouvé → renvoie le texte brut dans une <div>.
#   3. Si titres trouvés → découpe le texte en sections (intro + sections numérotées).
#   4. Convertit chaque section en HTML (<h2> pour le titre, <p> pour le contenu).
#   5. Ajoute une classe CSS spéciale "conclusion" si le titre contient "synthèse",
#      "conclusion" ou "conseils".
#   6. Retourne le HTML final prêt à être injecté dans le template.
# Logs : pattern détecté, nombre de sections créées, extraits du texte pour debug.
# ────────────────────────────────────────────────

def transformer_en_sections(texte_brut):
    """
    Transforme le texte markdown du LLM en sections HTML bien structurées
    """
    
    print(f"🔍 DEBUT transformer_en_sections")
    print(f"🔍 Texte reçu (premiers 200 chars): {texte_brut[:200]}")
    
    # 1. Essayer plusieurs patterns de titres dans l'ordre de priorité
    patterns = [
        r'^(\d+)\.\s*\*\*(.+?)\*\*',        # 1. **Titre** (format actuel du LLM)
        r'\*\*(\d+)\.\s*(.+?)\*\*',         # **1. Titre** (format original)
        r'^(\d+)\.\s*(.+?)(?=\n\n|\n[A-Z]|\n\d+\.|\Z)',  # 1. Titre (suivi de paragraphe)
        r'###\s*(\d+)\.\s*(.+?)(?=\n)',     # ### 1. Titre
        r'##\s*(\d+)\.\s*(.+?)(?=\n)',      # ## 1. Titre
    ]
    
    parties = None
    pattern_utilisé = None
    
    for i, pattern in enumerate(patterns):
        # Test avec flags multiline pour détecter les débuts de ligne
        test_parties = re.split(pattern, texte_brut, flags=re.MULTILINE)
        if len(test_parties) > 3:  # Au moins 1 section trouvée (3 parties min: avant + num + titre + contenu)
            parties = test_parties
            pattern_utilisé = pattern
            print(f"🔍 ✅ Pattern {i+1} utilisé: {pattern}")
            print(f"🔍 Nombre de parties trouvées: {len(parties)}")
            break
    
    if parties is None or len(parties) <= 1:
        print(f"🔍 ❌ Aucun pattern trouvé")
        print(f"🔍 Premier extrait pour debug: {texte_brut[:500]}")
        # Retourner le texte brut dans une div simple
        return f'<div class="contenu-brut">{texte_brut.replace(chr(10), "<br>")}</div>'
    
    # 2. Construire les sections HTML
    sections_html = []
    
    i = 0
    while i < len(parties):
        if i == 0 and parties[i].strip():
            # Contenu avant le premier titre
            intro = parties[i].strip()
            if intro:
                sections_html.append(f'<div class="introduction">{intro.replace(chr(10), "<br>")}</div>')
        elif i + 2 < len(parties) and parties[i].isdigit():
            # On a un titre numéroté
            numero = parties[i]
            titre = parties[i + 1].strip()
            contenu = parties[i + 2].strip() if i + 2 < len(parties) else ""
            
            print(f"🔍 Section trouvée - {numero}: {titre[:50]}...")
            
            # Nettoyer le contenu - préserver les paragraphes
            contenu_paragraphes = contenu.split('\n\n')
            contenu_html = ""
            for para in contenu_paragraphes:
                if para.strip():
                    contenu_html += f"<p>{para.strip().replace(chr(10), ' ')}</p>"
            
            # Déterminer la classe CSS selon le titre
            classe_section = "conclusion" if any(word in titre.lower() for word in ["synthèse", "conclusion", "conseils"]) else "section"
            
            section_html = f'''
            <section class="{classe_section}">
                <h2>{numero}. {titre}</h2>
                <div class="section-content">
                    {contenu_html}
                </div>
            </section>
            '''
            sections_html.append(section_html)
            
            i += 2  # Sauter titre et contenu
        
        i += 1
    
    result = '\n'.join(sections_html)
    print(f"🔍 ✅ {len(sections_html)} sections créées")
    return result


# ────────────────────────────────────────────────
# FONCTION : analyse_point_astral_avec_sections
# Objectif : Générer une analyse « Point Astral » avec mise en page en sections HTML
# Étapes :
#   1. Construction de la chaîne des placements planétaires avec build_resume_fusion().
#   2. Tentative de chargement du corpus RAG (limité à 8000 caractères).
#   3. Génération du texte brut via le LLM (fonction generer_analyse_airops_style()).
#   4. Transformation du texte brut en HTML structuré par sections (transformer_en_sections()).
#   5. Insertion des infos personnelles et du logo dans un template HTML complet.
#   6. Retourne le HTML final prêt à être affiché ou converti en PDF.
# Logs : étapes, longueurs des chaînes générées, erreurs éventuelles.
# ────────────────────────────────────────────────

def analyse_point_astral_avec_sections(data, call_llm, infos_personnelles=None):
    """
    Version modifiée qui applique le post-traitement pour les belles sections
    """
    print(f"\n{'='*60}")
    print(f"🎬 DÉBUT ANALYSE POINT ASTRAL (avec sections)")
    print(f"👤 Nom: {(infos_personnelles or {}).get('nom', 'Anonyme')}")
    print(f"{'='*60}")
    
    # 1) Construction des placements
    print(f"🔧 Étape 1: Construction des placements...")
    from utils.placements_fusion import build_resume_fusion
    placements_str = build_resume_fusion(data)
    print(f"✅ Placements construits: {len(placements_str)} caractères")

    # 2) RAG optionnel
    print(f"🔧 Étape 2: Tentative chargement RAG...")
    rag_snippets = None
    try:
        # UTILISER LA FONCTION DÉJÀ IMPORTÉE
        rag_snippets = generer_corpus_rag_optimise(data)
        if rag_snippets and len(rag_snippets) > 8000:
            rag_snippets = rag_snippets[:8000]
        print(f"✅ RAG chargé: {len(rag_snippets) if rag_snippets else 0} caractères")
    except Exception as e:
        print(f"⚠️ RAG indisponible: {e}")
        import traceback
        traceback.print_exc()

    # 3) Génération LLM
    print(f"🔧 Étape 3: Génération LLM...")
    print("🚨 DEBUG - Vérification des points forts avant LLM:")
    axes_str = data.get("axes_majeurs_str", "")
    print(f"Contenu axes_majeurs_str (premiers 500 chars):\n{axes_str[:500]}")

    try:
        from utils.openai_utils import generer_analyse_airops_style
        texte_brut = generer_analyse_airops_style(
            placements_str=placements_str,
            call_llm=call_llm,
            rag_snippets=rag_snippets,
            points_forts=data.get("axes_majeurs_str"),
            gender=data.get('gender')
        )
        print(f"✅ Texte brut généré: {len(texte_brut)} caractères")
        
        # 4) POST-TRAITEMENT : Transformer en sections HTML
        print(f"🔧 Étape 4: Transformation en sections HTML...")
        texte_structure = transformer_en_sections(texte_brut)
        print(f"✅ Sections HTML créées: {len(texte_structure)} caractères")
        
    except Exception as e:
        print(f"❌ Erreur génération LLM: {e}")
        import traceback
        traceback.print_exc()
        texte_structure = "<p>Impossible de générer l'analyse pour le moment.</p>"

     # 5) Logo (inchangé)
    logo_base64 = ""
    logo_path = "static/images/logo_les_fous_dastro.webp"
    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement du logo : {e}")

    # 5) Construction du HTML final avec votre CSS original
    nom = (infos_personnelles or {}).get("nom", "Analyse Anonyme")
    date_n = (infos_personnelles or {}).get("date_naissance", "—")
    heure_n = (infos_personnelles or {}).get("heure_naissance", "—")
    lieu_n = (infos_personnelles or {}).get("lieu_naissance", "—")

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <title>Point Astral - {nom}</title>
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: Georgia, serif;
                font-size: 16px;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background: #f5f5f5;
            }}
            .container {{
                width: 100%;
                max-width: none;
                margin: 0;
                padding: 30px;
                background: white;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                min-height: 100vh;
            }}
            .header {{
                text-align: center;
                margin-bottom: 25px;
                padding: 20px 0;
                border-bottom: 2px solid #1f628e;
                page-break-inside: avoid;
            }}
            .logo {{
                width: 60px;
                height: 60px;
                margin: 0 auto 10px auto;
                display: block;
                border-radius: 50%;
                border: 2px solid #1f628e;
            }}
            .header h1 {{
                font-size: 26px;
                color: #1f628e;
                margin: 10px 0 6px 0;
                font-weight: bold;
                font-family: Georgia, serif;
            }}
            .personal-info {{
                background: linear-gradient(135deg, #f0f8ff, #e6f3ff);
                border: 1px solid #d0e7ff;
                border-radius: 10px;
                padding: 20px;
                margin: 15px 0;
                text-align: center;
                box-shadow: 0 2px 10px rgba(31, 98, 142, 0.1);
            }}
            
            /* SECTIONS PRINCIPALES */
            section {{
                margin-bottom: 25px;
                page-break-inside: avoid;
                width: 100%;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            
            section h2 {{
                color: #1f628e;
                font-size: 20px;
                font-weight: bold;
                margin: 0;
                padding: 15px 20px;
                background: linear-gradient(135deg, #f0f8ff, #e6f3ff);
                border-left: 5px solid #1f628e;
                font-family: Georgia, serif;
                border-bottom: 1px solid #e0e7ff;
            }}
            
            .section-content {{
                padding: 20px;
            }}
            
            .section-content p {{
                margin: 15px 0;
                text-align: justify;
                line-height: 1.7;
                font-size: 16px;
            }}
            
            .section-content p:first-child {{
                margin-top: 0;
            }}
            
            .section-content p:last-child {{
                margin-bottom: 0;
            }}
            
            /* SECTION CONCLUSION */
            .conclusion {{
                background: linear-gradient(135deg, #f0f8ff, #e6f3ff);
                border: 2px solid #1f628e;
                margin-top: 30px;
            }}
            
            .conclusion h2 {{
                background: #1f628e;
                color: white;
                border-left: none;
                border-bottom: none;
            }}
            
            /* INTRODUCTION */
            .introduction {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 25px;
                border-left: 4px solid #1f628e;
            }}
            
            footer {{
                margin-top: 30px;
                padding: 15px;
                border-top: 1px solid #ddd;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {f'<img src="data:image/webp;base64,{logo_base64}" alt="Logo" class="logo">' if logo_base64 else ''}
                <h1>Point Astral</h1>
                <div class="personal-info">
                    <p><strong>Nom :</strong> {nom}</p>
                    <p><strong>Date/Heure :</strong> {date_n} — {heure_n}</p>
                    <p><strong>Lieu :</strong> {lieu_n}</p>
                </div>
            </div>
            <main>
                {texte_structure}
            </main>
            <footer>
                <p>© Les Fous d'Astro – Document généré automatiquement</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    print(f"✅ HTML final avec sections: {len(html)} caractères")
    print(f"🎬 FIN ANALYSE POINT ASTRAL")
    
    return html