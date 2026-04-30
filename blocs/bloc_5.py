# blocs/bloc_5.py
from utils.llm_client import ask_llm
from textwrap import dedent
from utils.selection_donnees import extraire_noeuds_pour_bloc5

POINT_ASTRAL_EXCLUS = {
    "Junon",
    "Chiron",
    #"Lune Noire",
    "Part de Fortune",
    "Cérès",
    "Pallas",
    "Vesta",
}

def _filtrer_lignes_points_secondaires(text: str) -> str:
    if not text:
        return ""

    lignes = []
    for line in text.splitlines():
        if any(point.lower() in line.lower() for point in POINT_ASTRAL_EXCLUS):
            continue
        lignes.append(line)

    return "\n".join(lignes)

def _extract_points_forts_from_placements(placements_str: str) -> str:
    """
    Extrait la section ### Points forts du texte placements_str
    """
    if not placements_str:
        return ""
    
    lines = placements_str.split('\n')
    points_forts_lines = []
    in_points_forts_section = False
    
    for line in lines:
        line = line.strip()
        
        # Début de la section Points forts
        if line == "### Points forts":
            in_points_forts_section = True
            continue
        
        # Fin de la section (nouvelle section ###)
        if line.startswith("### ") and in_points_forts_section:
            break
            
        # Collecter les lignes de la section Points forts
        if in_points_forts_section and line:
            # Nettoyer les tirets en début de ligne
            clean_line = line.lstrip("- ").strip()
            if clean_line:
                points_forts_lines.append(clean_line)
    
    return "\n".join(points_forts_lines)


def _section_noeuds_lunaires_for_prompt(theme: dict, max_orbe: float = 5.0) -> str:
    pkg = extraire_noeuds_pour_bloc5(theme, max_orbe=max_orbe)
    lines = ["### Nœuds lunaires"]
    plc = pkg.get("placements", {})
    asp = pkg.get("aspects_list", [])

    # Placements
    if plc:
        lines.append("- Placements :")
        for nom in ("Nœud Nord", "Nœud Sud"):
            if nom in plc:
                lines.append(f"  • {nom} : {plc[nom]}")
    else:
        lines.append("- Placements : (indispo)")

    # Aspects
    lines.append("- Aspects (≤5°) :")
    if asp:
        for a in asp:
            lines.append(f"  • {a}")
    else:
        lines.append("  • Aucun aspect notable")

    return "\n".join(lines)

def generer_bloc_5(contexte: dict, max_tokens: int = 1200) -> str:
    print("[BLOC5] version=2025-09-12A")
    """
    Bloc 5 – Axes & Synthèse
    Objectif : condenser le thème en 2–3 axes directeurs + trajectoire d'intégration
               (priorités, leviers, pièges à éviter), avec un ton clair et incarné.
    """
    # 1) Données de base (même socle que les autres blocs)
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    ).strip()
    placements_str = _filtrer_lignes_points_secondaires(placements_str)
    if len(placements_str) < 50:
        return "❌ Données insuffisantes pour produire la synthèse."

    # CORRECTION: Extraire les points forts directement de placements_str
    points_forts = _extract_points_forts_from_placements(placements_str)
    points_forts = _filtrer_lignes_points_secondaires(points_forts)
    
    # Fallback si pas de points forts extraits
    if not points_forts:
        axes_majeurs_fallback = _filtrer_lignes_points_secondaires(
            (contexte.get("axes_majeurs_str") or "").strip()
        )
        if axes_majeurs_fallback:
            points_forts = axes_majeurs_fallback
        else:
            points_forts = "Non précisé ici"

    print(f"Points forts extraits pour bloc 5 (synthèse):\n{points_forts}")

    tonalite     = contexte.get("tonalite", "tu")
    genre_label  = contexte.get("genre", "femme")

    # 2) RAG (digest déjà préparé par l'orchestrateur ; sinon compacte un peu)
    rag_snippets = (contexte.get("rag_snippets") or "").strip()
    if rag_snippets:
        lines, seen = [], set()
        for ln in rag_snippets.splitlines():
            t = ln.strip()
            if not t:
                continue
            k = t.lower()
            if k not in seen:
                seen.add(k); lines.append(t)
        rag_short = "\n".join(lines)[:2500]
    else:
        rag_short = ""

    LONGUEUR_MIN, LONGUEUR_MAX = 250, 400  # mots

    # 3) Continuité (optionnel) — aperçu des blocs précédents si passés par l'orchestrateur
    # apercu_bloc_1 = (contexte.get("apercu_bloc_1") or "").strip()
    # apercu_bloc_2 = (contexte.get("apercu_bloc_2") or "").strip()
    # apercu_bloc_3 = (contexte.get("apercu_bloc_3") or "").strip()

    # Construire le thème à partir du contexte
    theme = contexte.get("theme") or contexte
    print("[BLOC5] keys theme:", list(theme.keys())[:12])

    noeuds_txt = _section_noeuds_lunaires_for_prompt(theme, max_orbe=5.0)
    print("[BLOC5] noeuds_txt:\n", noeuds_txt)

    
    # Accords de genre
    if genre_label == "femme":
        genre_txt = "C'est une femme : adapte rigoureusement tes formulations au féminin."
    else:
        genre_txt = "C'est un homme : adapte rigoureusement tes formulations au masculin."


    prompt = dedent(f"""

    Tu es une astrologue expérimentée, plein d'humour, à la plume fine, directe, drôle, lucide, sarcastique.
    Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
    Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
    Ton style est vivant mais jamais niais,  jamais pompeux. Pas de poésie. Tu évites les clichés astrologiques.
    Tu ne parles pas *de* la personne, tu lui parles *directement*.

    {genre_txt}

    Section 5 : Synthèse

    Noeuds Lunaires : 
    {noeuds_txt}

    Données astrologiques :
    {placements_str}


    Références (RAG) — pense-bête, ne pas copier tel quel :
    {rag_short}


    
    Mission: produire une synthèse en 2/3 pragraphes du thème dans sa globalité, à partir des éléments fournis uniquement. 

    Règles générales:
    - Prends en compte toutes les planètes entre elles (Ascendant, Soleil, Lune, Mercure, Mars, Jupiter, Saturne, Uranus, Neptune, Pluton )
    - Evoque les noeuds lunaires (en terme de Noeud Nord (Rahu) et Noeud Sud (Ketu)) et la direction de vie. 
        Où la personne est-elle censée aller ? Qu'est-elle censée dépasser ? Fais le lien avec son thème.
    - Contrainte de contenu: n'utilise QUE les éléments fournis dans <placements>.
    - Parle vrai, cash, pas besoin de brosser dans le sens du poil. Pas de "Ton thème est un véritable patchwork, un cocktail explosif, fascinant etc). Pas de phrases bateaux, poétiques. Sois aussi profond que drôle et sarcastique !
    - Repère les tensions internes (les dissonances, les contradictions).
    - Appuie-toi sur des repères de psychologie jungienne (Persona / Ombre, Anima-Animus, processus d’individuation, fonctions psychologiques) pour proposer 3 à 5 axes d’intégration concrets adaptés au profil, avec des gestes simples du quotidien (conduites, rituels, communication, créativité). Évite tout jargon non expliqué et toute formulation pseudo-médicale.
    - Pas de coaching générique à l'eau de rose "écris un journal, explore tes zones d'ombre, tes émotions sans jugement", ça n'aide en rien.
    - ⚠️ N'INVENTE AUCUN PLACEMENT. Tout ce que tu cites DOIT SE TROUVER dans la liste des placements. Vérifie chaque placement dont tu parles. 
    - N’utilise pas de pronom possessif devant les planètes (évite : “ton Mars”, “ta Vénus”, “ta Saturne”).
    - Si une idée n’est pas justifiée par les placements fournis, ne l’écris pas.
    - Interdit d’énoncer des actions génériques (« fais un journal », « pratique la gratitude », « écris/peins ») si elles ne sont pas justifiées par <noeuds_lunaires> ou <points_forts>.
    - Toute recommandation doit être reliée explicitement à un placement cité (ex: « car NN en Capricorne M7… "car Lune en IV"»).
    - Si une idée n’est pas justifiée par les placements fournis, ne l’écris pas.
    - Structure: 1 ou 2 grands paragraphes continus, sans titres ni listes. 
    - Conclus par 2/3 questions pertinentes.

    - Utilise le tutoiement.
    """)

    print("=== PROMPT BLOC 5 ===")
    print(prompt)
    print("=== FIN PROMPT ===")

    return ask_llm(
        prompt,
        max_tokens=max_tokens,
        temperature=0.9,
    )