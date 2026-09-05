# blocs/bloc_3.py
from utils.llm_client import ask_llm
from textwrap import dedent
from typing import Dict, Any
from utils.selection_donnees import filtrer_items_pour_bloc3, _extraire_axes_interceptes

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

def _sanitize(txt: str) -> str:
    return (txt or "").strip()


def _dedupe_lines(text: str) -> str:
    seen, out = set(), []
    for ln in (text or "").splitlines():
        k = ln.strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(ln)
    return "\n".join(out)

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

def _fallback_dev_axes_from_items(items):
    if not items:
        return ("Aucun axe majeur détecté automatiquement. "
                "Le thème semble équilibré sans concentrer l'énergie autour d'une seule dynamique.")
    return "\n".join(f"- {it}" for it in items[:8])

def _fallback_dev_axes(axes_input: str) -> str:
    # (conservé pour compat, mais on préférera _fallback_dev_axes_from_items)
    axes_input = _sanitize(axes_input)
    if not axes_input:
        return ("Aucun axe majeur détecté automatiquement. "
                "Le thème semble équilibré sans concentrer l'énergie autour d'une seule dynamique.")
    lignes = [l.strip("- ").strip() for l in axes_input.splitlines() if l.strip()]
    out = []
    for l in lignes[:8]:
        out.append(f"- {l}")
    return "\n".join(out)

def _as_text(lines_or_text) -> str:
    """Normalise points_forts/axes en texte multi-lignes."""
    if not lines_or_text:
        return ""
    if isinstance(lines_or_text, list):
        return "\n".join(str(x).strip() for x in lines_or_text if str(x).strip())
    return str(lines_or_text).strip()

def generer_bloc_3(contexte: Dict[str, Any], max_tokens: int = 1800) -> str:
    ctx: Dict[str, Any] = contexte

    # 1) Données de base
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    ).strip()

    placements_str = _filtrer_lignes_points_secondaires(placements_str)

    # Extraire les points forts du blob de placements
    points_forts = _extract_points_forts_from_placements(placements_str)
    if not points_forts:
        points_forts_fallback = _as_text(contexte.get("points_forts") or contexte.get("points_forts_str"))
        points_forts = points_forts_fallback or "Non précisé ici"

    if not placements_str or not points_forts:
        return "❌ Données insuffisantes pour analyser les points forts."

    # ✅ Axes filtrés fournis par l’orchestrateur
    axes_filtrees = (
        contexte.get("axes_majeurs_input")
        or ""
    ).strip()

    axes_filtrees = _filtrer_lignes_points_secondaires(axes_filtrees)

    # ✅ Conjonctions au MC (optionnel mais recommandé)
    conj_mc = (
        contexte.get("conjonctions_mc")
        or ""
    ).strip()

    conj_mc = _filtrer_lignes_points_secondaires(conj_mc)

    # ➕ Axes interceptés (et planètes contenues dans ces signes)
    axes_int = _extraire_axes_interceptes(contexte)  # {'signes': [...], 'maisons_par_signe': {...}}
    signes_int = axes_int.get("signes") or []
    maisons_int = axes_int.get("maisons_par_signe") or {}

    if signes_int:
        extra_lines = []

        # 1) L'axe lui-même
        extra_lines.append(f"Axe intercepté : {', '.join(signes_int)} — thèmes à débloquer / maturer")

        # 2) Planètes contenues dans ces signes interceptés
        # On prend des placements occidentaux robustes (selon ce que ton orchestrateur fournit)
        occ = (contexte.get("planetes")
               or contexte.get("placements_occidentaux")
               or contexte.get("placements_occ")
               or contexte.get("resultats_tropical")
               or {})

        for pl, d in (occ or {}).items():
            if not isinstance(d, dict):
                continue
            signe = d.get("signe")
            maison = d.get("maison")
            if signe in signes_int:
                maison_txt = f"Maison {maison}" if maison is not None else "Maison ?"
                extra_lines.append(f"{pl} intercepté en {signe} ({maison_txt}) — potentiel sous-exprimé à intégrer")

        # 3) Ajout au bloc d'axes, avec dédup “doux”
        if extra_lines:
            axes_filtrees = _dedupe_lines(axes_filtrees + "\n" + "\n".join(extra_lines))

    # 🔁 Fallback : si axes_filtrees est vide, retombe sur les points_forts extraits
    if not axes_filtrees:
        axes_filtrees = points_forts

    # ➕ Ajoute les conjonctions MC si dispo (sans doublons)
    if conj_mc:
        axes_filtrees = _dedupe_lines(axes_filtrees + ("\n" if axes_filtrees else "") + conj_mc)


    # (RAG, tonalité, genre...)
    tonalite = contexte.get("tonalite", "tu")
    genre_label = contexte.get("genre", "femme")

    rag_snippets = (contexte.get("rag_snippets") or "").strip()
    if rag_snippets:
        lines, seen = [], set()
        for ln in rag_snippets.splitlines():
            t = ln.strip()
            if t and t.lower() not in seen:
                seen.add(t.lower()); lines.append(t)
        rag_short = "\n".join(lines)[:2500]
    else:
        rag_short = ""

    apercu_bloc_1 = (contexte.get("apercu_bloc_1") or "").strip()
    apercu_bloc_2 = (contexte.get("apercu_bloc_2") or "").strip()

    genre_txt = "C'est une femme : adapte rigoureusement tes formulations au féminin." \
                if genre_label == "femme" else \
                "C'est un homme : adapte rigoureusement tes formulations au masculin."

    prompt = dedent(f"""
    {genre_txt}

    SECTION 3 : LES AXES FORTS DU THEME

    Tu es une astrologue expérimentée, plein d'humour, à la plume fine, directe, drôle, lucide, sarcastique.
    Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
    Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
    Ton style est vivant mais jamais niais, jamais pompeux. Pas de poésie. Tu évites les clichés astrologiques.
    Tu ne parles pas *de* la personne, tu lui parles *directement*.

    # Axes à traiter (déjà filtrés pour éviter les redites avec les Blocs 1 & 2)

    {axes_filtrees}

    # Contexte global (référence)
 
    {placements_str}

    # Contexte documentaire (si utile)

    {rag_short}
 

    Instruction :
    Instructions :
    - N’analyse PAS : Ascendant, Maître d’Ascendant, Soleil, Lune, enfance, parents (ces points sont traités ailleurs).
    - Ta mission : dégager 2 à 3 tensions maîtresses + 1 à 2 ressources structurantes à partir des axes filtrés ci-dessus. 
    - Articule-les clairement, sans passer par un listing item par item.
    - Chaque phrase doit apporter une idée précise (évite le remplissage ou les généralités).
    - Style attendu : cash, profond, sarcastique si besoin. Pas de poésie, pas de phrases toutes faites.
    - Tu peux utiliser des repères jungiens (Persona/Ombre, Anima-Animus, individuation) UNIQUEMENT si c’est pertinent et bien intégré.
    - Exemples concrets exigés : illustre les dynamiques par des images de vie réelle (relations, comportements, choix…).
    - Pas de conclusion, pas de résumé final.
    - INTERDIT : coaching générique (« écris un journal », « explore tes émotions », « pose des limites »). Pas de conseils hors analyse.
    - Toute recommandation doit être reliée explicitement à un placement cité (ex: « car NN en Capricorne M7… "car Lune en IV"»).
    - Si une idée n’est pas justifiée par les placements fournis, ne l’écris pas.
    - ⚠️ N'INVENTE AUCUN PLACEMENT. Tout ce que tu cites doit se trouver dans la liste des placements.
    - N’utilise pas de pronom possessif devant les planètes (évite : “ton Mars”, “ta Vénus”, “ta Saturne”).

    Format : 4–5 paragraphes en français, texte continu, tutoiement.
    """).strip()

    print(prompt)

    try:
        resultat = ask_llm(prompt, max_tokens=max_tokens, temperature=0.4)
        resultat = _sanitize(resultat)
        if len(resultat) < 80:
            raise ValueError("Réponse LLM trop courte")
    except Exception as e:
        print(f"⚠️ BLOC3 — LLM indisponible ou réponse faible ({e}), fallback.")
        return points_forts

    return resultat
