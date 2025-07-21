from textwrap import dedent
from utils.utils_analyse import analyse_gratuite
from utils.utils_points_forts import extraire_points_forts
from utils.utils_formatage import formater_positions_planetes, formater_aspects_significatifs

def analyse_point_astral(data, call_llm):
    # Données essentielles
    planetes = data.get("planetes", {})
    aspects = data.get("aspects", [])
    lune_vedique = data.get("planetes_vediques", {}).get("Lune", {})
    maisons = data.get("maisons", {})
    maitre_asc = data.get("maitre_ascendant", {})

    # Analyse de base (gratuite)
    analyse_base = analyse_gratuite(planetes, aspects, lune_vedique)

    # Points forts supplémentaires
    points_forts = extraire_points_forts(data)

    # Formater planètes et aspects significatifs
    positions_str = formater_positions_planetes(planetes)
    aspects_str = formater_aspects_significatifs(aspects)  # 👈 ici tu filtres avec orbe ≤ 5°

    # Prompt principal
    prompt = dedent(f"""
    Tu es un astrologue professionnel, direct, lucide, avec une plume fine et sans fioritures.
    Tu t’adresses à la personne en disant "tu", jamais "il/elle". Ton style est clair, incarné, nuancé, sans flatterie.
    
    Rédige une lecture astrologique complète du thème natal à partir des données suivantes.
    Commence par une introduction générale (ambiance du thème), puis enchaîne avec une lecture structurée de la personnalité.

    <h2>Introduction</h2>
    - Ambiance générale, tonalité du thème, équilibre ou déséquilibre ressenti

    <h2>Trinité : Ascendant / Soleil / Lune</h2>
    - Ascendant : {planetes.get('Ascendant', {}).get('signe', '?')} {planetes.get('Ascendant', {}).get('degre', '?')}° (Maison 1)
    - Maître d’Ascendant : {maitre_asc.get('planete', '?')} en {maitre_asc.get('signe', '?')} (Maison {maitre_asc.get('maison', '?')})
    - Soleil : {planetes.get('Soleil', {}).get('signe', '?')} {planetes.get('Soleil', {}).get('degre', '?')}° (Maison {planetes.get('Soleil', {}).get('maison', '?')})
    - Lune : {planetes.get('Lune', {}).get('signe', '?')} {planetes.get('Lune', {}).get('degre', '?')}° (Maison {planetes.get('Lune', {}).get('maison', '?')})
    - Nakshatra de la Lune : {lune_vedique.get('nakshatra', '?')}

    Analyse les synergies, tensions, contrastes entre ces trois pôles. Mentionne les maisons angulaires, conjonctions serrées, et aspects notables.

    <h2>Lecture psychologique approfondie</h2>
    - Décris les tiraillements internes, les ambivalences du thème
    - Intègre les éléments suivants : 
        {chr(10).join(f"- {pt}" for pt in points_forts)}

    <h2>Aspects et dynamiques générales</h2>
    {aspects_str}

    <h2>Positions planétaires</h2>
    {positions_str}

    <h2>Conclusion</h2>
    - Fais une synthèse lucide et honnête : défis principaux, ressources de résilience, potentiel d’évolution.
    - Termine par une phrase d'encouragement ou de clarification.

    Tu dois utiliser un langage vivant mais jamais cliché. Pas de flatterie. Pas de redite. 
    Utilise des paragraphes en HTML <p>.
    """)

    print("\n🔍 Prompt envoyé au LLM :\n")
    print(prompt)
    print("\n🔚 Fin du prompt\n")

    # Appel au LLM
    texte_html = call_llm(prompt)

    # Vérifie si le texte est incomplet ou s’arrête brutalement
    if "Conclusion" not in texte_html or texte_html.strip().endswith((":", "…", "La")):
        suite_prompt = dedent(f"""
        Le texte ci-dessous est une analyse astrologique bien entamée mais incomplète.
        Continue la rédaction à partir de là, sans recommencer l’introduction, et termine par une conclusion complète et lucide :

        {texte_html}
        """)
        suite = call_llm(suite_prompt)
        texte_html += "\n\n" + suite

    # Mise en forme HTML pour PDF
    full_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Georgia, serif; font-size: 14px; line-height: 1.6; color: #2c3e50; padding: 40px;">
    {texte_html}
    </body>
    </html>
    """

    return full_html