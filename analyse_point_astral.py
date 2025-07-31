from textwrap import dedent
import base64
import os
from utils.utils_analyse import analyse_gratuite
from utils.utils_points_forts import extraire_points_forts
from utils.utils_formatage import formater_positions_planetes, formater_aspects_significatifs
from utils.rag_utils import interroger_rag
from utils.connect_rag import get_weaviate_client

def analyse_point_astral(data, call_llm, infos_personnelles=None):
    """
    Génère une analyse astrologique complète avec les informations personnelles
    
    Args:
        data: Données astrologiques calculées
        call_llm: Fonction pour appeler le LLM
        infos_personnelles: Dict contenant {
            'nom': str,
            'date_naissance': str,  # Format: "15 août 1990"
            'heure_naissance': str, # Format: "14h30"
            'lieu_naissance': str   # Format: "Paris, France"
        }
    """
    # Données essentielles
    planetes = data.get("planetes", {})
    aspects = data.get("aspects", [])
    lune_vedique = data.get("planetes_vediques", {}).get("Lune", {})
    maisons = data.get("maisons", {})
    maitre_asc = data.get("maitre_ascendant", {})

    # Informations personnelles avec valeurs par défaut
    if infos_personnelles is None:
        infos_personnelles = {
            'nom': 'Analyse Anonyme',
            'date_naissance': 'Date non spécifiée',
            'heure_naissance': 'Heure non spécifiée',
            'lieu_naissance': 'Lieu non spécifié'
        }

    analyse_base = analyse_gratuite(planetes, aspects, lune_vedique)
    points_forts = extraire_points_forts(data)

    # Créer une variable texte des points, mais ne pas l'injecter visuellement
    points_diagnostic = "\n".join(f"- {pt}" for pt in points_forts)

    # Préparer des requêtes RAG à partir des points forts
    questions = [f"Signification astrologique de : {point}" for point in points_forts]

    corpus = []
    for question in questions:
        try:
            réponse = interroger_rag(question)
            corpus.append(f"<div class='rag-item'><strong>{question}</strong><br>{réponse}</div>")
        except Exception as e:
            corpus.append(f"<div class='rag-item error'><strong>{question}</strong><br>❌ Erreur : {e}</div>")

    corpus_rag_html = "\n".join(corpus)

    positions_str = formater_positions_planetes(planetes)
    aspects_str = formater_aspects_significatifs(aspects)

    prompt = dedent(f"""
Tu es un astrologue professionnel de plus de 20 ans, direct, lucide, avec une plume fine, drôle, voire sarcastique et sans fioritures.
Tu t'adresses à la personne en disant "tu", jamais "il/elle". Ton style est clair, incarné, nuancé, sans flatterie, sans fausse poésie.

Cette analyse est pour {infos_personnelles['nom']}, né(e) le {infos_personnelles['date_naissance']} à {infos_personnelles['heure_naissance']} à {infos_personnelles['lieu_naissance']}.

Rédige une analyse astrologique du thème natal à partir des données suivantes.
Commence par une introduction générale (ambiance du thème), puis enchaîne avec une lecture structurée de la personnalité.

⚠️ Tu dois ABSOLUMENT prendre en compte les ASPECTS MAJEURS (conjonction / carré / opposition) aux LUMINAIRES (Soleil ou Lune) avec les planètes suivantes (Mars, Saturne, Uranus, Neptune, Pluton). 
Ces éléments doivent être pris en compte AVANT toute autre interprétation.

<section class="intro">
<h2>Introduction</h2>
- Ambiance générale, tonalité du thème, équilibre ou déséquilibre ressenti
- Mentionne d'emblée les aspects marquants aux luminaires si présents, ainsi que les axes majeurs du thème.
</section>

<section class="trinite">
<h2>Trinité : Ascendant / Soleil / Lune</h2>
<div class="astro-data">
- Ascendant : {planetes.get('Ascendant', {}).get('signe', '?')} {planetes.get('Ascendant', {}).get('degre', '?')}° (Maison 1)
- Maître d'Ascendant : {maitre_asc.get('planete', '?')} en {maitre_asc.get('signe', '?')} (Maison {maitre_asc.get('maison', '?')})
- Soleil : {planetes.get('Soleil', {}).get('signe', '?')} {planetes.get('Soleil', {}).get('degre', '?')}° (Maison {planetes.get('Soleil', {}).get('maison', '?')})
- Lune : {planetes.get('Lune', {}).get('signe', '?')} {planetes.get('Lune', {}).get('degre', '?')}° (Maison {planetes.get('Lune', {}).get('maison', '?')})
- Nakshatra de la Lune : {lune_vedique.get('nakshatra', '?')}
</div>

Analyse les synergies, tensions, contrastes entre ces trois pôles. Intègre les aspects forts aux luminaires. Mentionne les maisons angulaires, conjonctions serrées, et aspects notables.
</section>

<section class="psycho">
<h2>Lecture psychologique approfondie</h2>
<p>Tu dois t'appuyer sur les dynamiques suivantes, mais sans les énumérer textuellement :</p>
<div class="diagnostic-hidden">{points_diagnostic}</div>
<div class="rag-content">
{corpus_rag_html}
</div>
</section>

<section class="aspects">
<h2>Aspects et dynamiques générales</h2>
<div class="aspects-content">
{aspects_str}
</div>
</section>

<section class="positions">
<h2>Positions planétaires</h2>
<div class="positions-content">
{positions_str}
</div>
</section>

<section class="conclusion">
<h2>Conclusion</h2>
- Fais une synthèse lucide et honnête : défis principaux, potentiel d'évolution.
- Termine par une phrase d'encouragement ou de clarification.
</section>

Tu dois utiliser un langage vivant mais jamais cliché. Pas de flatterie. Pas de redite. Pas de fausse poésie.
Utilise des paragraphes en HTML <p>.
""")

    print("\n🔍 Prompt envoyé au LLM :\n")
    print(prompt)
    print("\n🔚 Fin du prompt\n")

    texte_html = call_llm(prompt)

    if "Conclusion" not in texte_html or texte_html.strip().endswith((":", "…", "La")):
        suite_prompt = dedent(f"""
        Le texte ci-dessous est une analyse astrologique bien entamée mais incomplète.
        Continue la rédaction à partir de là, sans recommencer l'introduction, et termine par une conclusion complète et lucide :

        {texte_html}
        """)
        suite = call_llm(suite_prompt)
        texte_html += "\n\n" + suite

    # Encoder le logo en base64 pour l'inclure dans le PDF
    logo_base64 = ""
    logo_path = "static/images/logo_les_fous_dastro.webp"
    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement du logo : {e}")

    # Template HTML simplifié et optimisé pour PDF avec informations personnelles
    full_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <title>Point Astral - {infos_personnelles['nom']}</title>
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
                font-size: 14px;
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

            /* Header avec informations personnelles */
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

            .header .subtitle {{
                font-size: 16px;
                color: #666;
                font-style: italic;
                margin: 0 0 15px 0;
                font-family: Georgia, serif;
            }}

            /* Section des informations personnelles */
            .personal-info {{
                background: linear-gradient(135deg, #f0f8ff, #e6f3ff);
                border: 1px solid #d0e7ff;
                border-radius: 10px;
                padding: 20px;
                margin: 15px 0;
                text-align: center;
                box-shadow: 0 2px 10px rgba(31, 98, 142, 0.1);
            }}

            .personal-info h2 {{
                font-size: 20px;
                color: #1f628e;
                margin: 0 0 15px 0;
                font-weight: bold;
                font-family: Georgia, serif;
            }}

            .birth-details {{
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 15px;
                margin-top: 10px;
            }}

            .birth-detail {{
                flex: 1;
                min-width: 200px;
                background: white;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #e0e8f0;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}

            .birth-detail .label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                font-weight: bold;
                margin-bottom: 5px;
                display: block;
            }}

            .birth-detail .value {{
                font-size: 16px;
                color: #1f628e;
                font-weight: bold;
                font-family: Georgia, serif;
            }}

            /* Sections */
            section {{
                margin-bottom: 20px;
                page-break-inside: avoid;
                width: 100%;
            }}

            h2 {{
                color: #1f628e;
                font-size: 18px;
                font-weight: bold;
                margin: 20px 0 12px 0;
                padding: 10px 15px;
                background: #f0f8ff;
                border-left: 4px solid #1f628e;
                border-radius: 5px;
                font-family: Georgia, serif;
            }}

            h3 {{
                color: #00a8a8;
                font-size: 16px;
                font-weight: bold;
                margin: 15px 0 8px 0;
                font-family: Georgia, serif;
            }}

            p {{
                margin: 10px 0;
                text-align: justify;
                line-height: 1.7;
                font-size: 14px;
            }}

            /* Données astrologiques */
            .astro-data {{
                background: #fafafa;
                border: 1px solid #ddd;
                padding: 15px;
                margin: 12px 0;
                font-family: Georgia, serif;
                font-size: 13px;
                border-radius: 5px;
                white-space: pre-line;
            }}

            /* Éléments RAG */
            .rag-content {{
                margin: 10px 0;
            }}

            .rag-item {{
                background: #f8f9fa;
                border-left: 3px solid #00a8a8;
                margin: 12px 0;
                padding: 12px;
                border-radius: 5px;
            }}

            .rag-item strong {{
                color: #1f628e;
                font-size: 13px;
                display: block;
                margin-bottom: 6px;
                font-family: Georgia, serif;
            }}

            .rag-item.error {{
                border-left-color: #dc3545;
                background: #fff5f5;
            }}

            /* Contenu des aspects et positions */
            .aspects-content,
            .positions-content {{
                background: #fafafa;
                border: 1px solid #ddd;
                padding: 15px;
                margin: 12px 0;
                border-radius: 5px;
                font-size: 13px;
                font-family: Georgia, serif;
            }}

            /* Éléments cachés */
            .diagnostic-hidden {{
                display: none;
            }}

            /* Sections spéciales */
            .intro {{
                background: #f0f8ff;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #e0e8f0;
            }}

            .conclusion {{
                background: #f0f8ff;
                padding: 20px;
                border-radius: 8px;
                border: 2px solid #1f628e;
                margin-top: 25px;
            }}

            /* Footer */
            .footer {{
                margin-top: 30px;
                padding: 15px;
                border-top: 1px solid #ddd;
                text-align: center;
                font-size: 12px;
                color: #666;
                page-break-inside: avoid;
                font-family: Georgia, serif;
            }}

            .footer .copyright {{
                font-weight: bold;
                color: #1f628e;
                margin-bottom: 3px;
            }}

            /* Utilitaires */
            .page-break {{
                page-break-before: always;
            }}

            ul, ol {{
                padding-left: 18px;
                margin: 6px 0;
            }}

            li {{
                margin-bottom: 3px;
            }}

            strong {{
                color: #1f628e;
                font-weight: bold;
            }}

            em {{
                color: #00a8a8;
                font-style: italic;
            }}

            /* Responsive pour l'affichage web */
            @media screen and (max-width: 768px) {{
                body {{
                    font-size: 11px;
                    padding: 10px;
                }}
                
                .header h1 {{
                    font-size: 18px;
                }}
                
                .logo {{
                    width: 50px;
                    height: 50px;
                }}

                .birth-details {{
                    flex-direction: column;
                    gap: 10px;
                }}

                .birth-detail {{
                    min-width: auto;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {f'<img src="data:image/webp;base64,{logo_base64}" alt="Les Fous d\'Astro" class="logo">' if logo_base64 else ''}
                <h1>Point Astral</h1>
                <div class="subtitle">Analyse Astrologique Personnalisée</div>
            </div>

            <div class="personal-info">
                <h2>{infos_personnelles['nom']}</h2>
                <div class="birth-details">
                    <div class="birth-detail">
                        <span class="label">Date de naissance</span>
                        <div class="value">{infos_personnelles['date_naissance']}</div>
                    </div>
                    <div class="birth-detail">
                        <span class="label">Heure de naissance</span>
                        <div class="value">{infos_personnelles['heure_naissance']}</div>
                    </div>
                    <div class="birth-detail">
                        <span class="label">Lieu de naissance</span>
                        <div class="value">{infos_personnelles['lieu_naissance']}</div>
                    </div>
                </div>
            </div>

            <main>
                {texte_html}
            </main>

            <div class="footer">
                <div class="copyright">© Droits réservés - Les Fous d'Astro</div>
                <div>Cette analyse a été générée spécialement pour {infos_personnelles['nom']}</div>
            </div>
        </div>
    </body>
    </html>
    """

    return full_html


# Fonction utilitaire pour sauvegarder le PDF (optionnelle)
def sauvegarder_pdf_point_astral(html_content, nom_fichier="point_astral.pdf"):
    """
    Sauvegarde le contenu HTML en PDF
    Compatible avec plusieurs librairies PDF
    """
    try:
        # Essayer d'abord avec weasyprint
        import weasyprint
        pdf = weasyprint.HTML(string=html_content).write_pdf()
        
        with open(nom_fichier, 'wb') as f:
            f.write(pdf)
            
        print(f"✅ PDF sauvegardé avec WeasyPrint : {nom_fichier}")
        return nom_fichier
        
    except ImportError:
        try:
            # Alternative avec reportlab si weasyprint n'est pas disponible
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
            import tempfile
            
            # Créer un fichier temporaire pour le HTML
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_html = f.name
            
            # Utiliser subprocess pour convertir avec un outil externe
            import subprocess
            result = subprocess.run([
                'python', '-c', 
                f'import weasyprint; weasyprint.HTML(filename="{temp_html}").write_pdf("{nom_fichier}")'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ PDF sauvegardé : {nom_fichier}")
                return nom_fichier
            else:
                print(f"❌ Erreur subprocess : {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde PDF : {e}")
            print("💡 Installez weasyprint avec: pip install weasyprint")
            print("   Ou utilisez une alternative comme: brew install wkhtmltopdf")
            return None


# Exemple d'utilisation
if __name__ == "__main__":
    # Données d'exemple pour tester
    data_exemple = {
        "planetes": {
            "Ascendant": {"signe": "Gémeaux", "degre": 15, "maison": 1},
            "Soleil": {"signe": "Lion", "degre": 22, "maison": 3},
            "Lune": {"signe": "Poissons", "degre": 8, "maison": 10}
        },
        "aspects": [],
        "planetes_vediques": {"Lune": {"nakshatra": "Uttara Bhadrapada"}},
        "maisons": {},
        "maitre_ascendant": {"planete": "Mercure", "signe": "Lion", "maison": 3}
    }
    
    # Informations personnelles d'exemple
    infos_exemple = {
        'nom': 'Sophie Dubois',
        'date_naissance': '15 août 1990',
        'heure_naissance': '14h30',
        'lieu_naissance': 'Paris, France'
    }
    
    def mock_llm(prompt):
        return """
        <section class="intro">
            <h2>Introduction</h2>
            <p>Voici un thème natal riche en contrastes, où l'adaptabilité des Gémeaux se mélange à la créativité du Lion et à la sensibilité des Poissons.</p>
        </section>
        <section class="conclusion">
            <h2>Conclusion</h2>
            <p>Un thème qui demande de jongler entre logique et intuition, avec un potentiel créatif remarquable.</p>
        </section>
        """
    
    # Test de la fonction avec les informations personnelles
    html_result = analyse_point_astral(data_exemple, mock_llm, infos_exemple)
    print("✅ HTML généré avec succès!")
    
    # Test de sauvegarde PDF
    # sauvegarder_pdf_point_astral(html_result, "test_point_astral_sophie.pdf")