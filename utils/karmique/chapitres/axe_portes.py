from __future__ import annotations
from typing import Any, Dict, Optional, Callable, List

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS

import logging
logger = logging.getLogger(__name__)


# -------------------------
# Symbolique de l'Axe des Portes
# -------------------------
PORTE_INVISIBLE_KEY = {
    "1": "Mémoire d'identité, difficulté à sortir d'un vieux 'Moi' archaïque.",
    "2": "Attachements matériels ou sensoriels très anciens, peur de manquer.",
    "3": "Schémas de pensée bloqués, vieux réflexes de communication.",
    "4": "Loyautés familiales ou claniques invisibles et pesantes.",
    "5": "Mémoire de pouvoir personnel ou créatif mal utilisé ou refoulé.",
    "6": "Réflexes de servitude ou de perfectionnisme hérités.",
    "7": "Dépendances relationnelles karmiques, peur de la solitude.",
    "8": "Traumatismes enfouis, mémoires de crises ou de pertes non résolues.",
    "9": "Vieilles croyances dogmatiques, soif d'ailleurs inassouvie.",
    "10": "Poids des responsabilités sociales passées, peur de l'échec.",
    "11": "Idéaux collectifs déçus, mémoires de marginalité.",
    "12": "Sacrifices inconscients, sentiment de flou ou de dissolution globale."
}

def _slug(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    s = s.replace("à", "a").replace("â", "a")
    s = s.replace("î", "i").replace("ï", "i")
    s = s.replace("ô", "o")
    s = s.replace("ù", "u").replace("û", "u").replace("ü", "u")
    s = s.replace("ç", "c")
    s = s.replace("œ", "oe")
    s = s.replace("’", "'")
    s = s.replace(" ", "_")
    return s


def _bdd(astre: str, donnee: str, valeur: Any) -> str:
    if valeur is None:
        return ""
    txt = get_karmique_interp(astre, donnee, str(valeur))
    return txt.strip() if isinstance(txt, str) and txt.strip() else ""


def build_block_axe_portes(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    axe = theme.get("axe_des_portes") or {}
    if not isinstance(axe, dict) or not axe:
        return None

    chiron = (theme.get("planetes") or {}).get("Chiron") or {}

    maison_invisible = axe.get("porte_invisible_maison")
    maison_visible = axe.get("porte_visible_maison")
    signe_invisible = axe.get("porte_invisible_signe")
    signe_visible = axe.get("porte_visible_signe")

    texte_bdd = _bdd("axe_des_portes", "maison", maison_invisible)

    # Maître de la porte invisible
    sign_rulers = {
        "belier": ["Mars"],
        "taureau": ["Vénus"],
        "gemeaux": ["Mercure"],
        "cancer": ["Lune"],
        "lion": ["Soleil"],
        "vierge": ["Mercure"],
        "balance": ["Vénus"],
        "scorpion": ["Mars", "Pluton"],
        "sagittaire": ["Jupiter"],
        "capricorne": ["Saturne"],
        "verseau": ["Saturne", "Uranus"],
        "poissons": ["Jupiter", "Neptune"],
    }

    signe_invisible_slug = _slug(signe_invisible)
    rulers = sign_rulers.get(signe_invisible_slug, [])

    aspects = theme.get("aspects") or []
    planetes = theme.get("planetes") or {}

    def _norm_aspect_name(x: Any) -> str:
        if not x:
            return ""
        x = str(x).strip().lower()
        if x in ("carre", "carré"):
            return "Carré"
        if x == "opposition":
            return "Opposition"
        if x == "conjonction":
            return "Conjonction"
        if x == "trigone":
            return "Trigone"
        if x == "sextile":
            return "Sextile"
        return str(x).capitalize()

    def _collect_planet_aspects(planet_name: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for a in aspects:
            p1 = a.get("planete1")
            p2 = a.get("planete2")

            if p1 == planet_name:
                other = p2
            elif p2 == planet_name:
                other = p1
            else:
                continue

            out.append({
                "type": _norm_aspect_name(a.get("aspect")),
                "with": other,
                "orb": a.get("orbe"),
            })
        return out

    rulers_details: List[Dict[str, Any]] = []
    ruler_lines: List[str] = []

    for r in rulers:
        pos = planetes.get(r) if isinstance(planetes.get(r), dict) else {}
        if not pos:
            continue

        r_sign = pos.get("signe")
        r_house = pos.get("maison")
        r_aspects = _collect_planet_aspects(r)

        rulers_details.append({
            "name": r,
            "signe": r_sign,
            "maison": r_house,
            "aspects": r_aspects,
        })

        ruler_lines.append(f"- {r} en {r_sign} — Maison {r_house}")
        if r_aspects:
            for a in r_aspects[:5]:
                orb = a.get("orb")
                orb_txt = f"{float(orb):.2f}" if isinstance(orb, (int, float)) else str(orb)
                ruler_lines.append(f"  - {a['type']} avec {a['with']} (orbe {orb_txt}°)")

    logger.debug("AXE PORTES maison_invisible = %s", maison_invisible)
    logger.debug("AXE PORTES maison_visible = %s", maison_visible)
    logger.debug("AXE PORTES signe_invisible = %s", signe_invisible)
    logger.debug("DEBUG AXE PORTES bdd_found = %s", bool(texte_bdd))
    logger.debug("DEBUG AXE PORTES texte_bdd = %s", texte_bdd[:500] if texte_bdd else "NONE")
    logger.debug("DEBUG AXE PORTES rulers = %s", rulers)
    logger.debug("DEBUG AXE PORTES rulers_details = %s", rulers_details)

    # -------------------------
    # SYNTHÈSE PSYCHOLOGIQUE (NEW)
    # -------------------------
    profil = []

    # Mémoire principale de la porte invisible
    memoire_invisible = PORTE_INVISIBLE_KEY.get(str(maison_invisible))
    if memoire_invisible:
        profil.append(f"La porte invisible indique une {memoire_invisible}")

    # Sens général du mouvement invisible -> visible
    if maison_invisible and maison_visible:
        profil.append(
            f"L'énergie semble devoir passer de la Maison {maison_invisible}, zone de rétention inconsciente, "
            f"vers la Maison {maison_visible}, zone de manifestation plus visible."
        )

    # Analyse des maîtres de la porte invisible
    for d in rulers_details:
        nom_maitre = d.get("name")
        maison_maitre = d.get("maison")
        signe_maitre = d.get("signe")
        aspects_maitre = d.get("aspects") or []

        if nom_maitre and maison_maitre:
            profil.append(
                f"Le maître de la porte invisible, {nom_maitre}, se trouve en {signe_maitre} Maison {maison_maitre}, "
                f"ce qui précise la manière dont cette énergie cherche à circuler."
            )

        for a in aspects_maitre:
            cible = a.get("with")
            aspect_type = a.get("type")

            if cible == "Saturne":
                profil.append(
                    f"{nom_maitre} en {aspect_type} à Saturne indique un passage ralenti, contrôlé ou chargé d'une peur de mal faire."
                )
            elif cible == "Pluton":
                profil.append(
                    f"{nom_maitre} en {aspect_type} à Pluton donne une intensité forte au passage, avec une tendance à retenir avant de libérer."
                )
            elif cible == "Neptune":
                profil.append(
                    f"{nom_maitre} en {aspect_type} à Neptune peut rendre le passage flou, poreux ou difficile à nommer clairement."
                )
            elif cible == "Uranus":
                profil.append(
                    f"{nom_maitre} en {aspect_type} à Uranus peut créer des ouvertures brusques, des déclics ou des ruptures dans le flux."
                )

    synthese = " ".join(profil).strip()
    logger.debug("AXE PORTES synthese = %s", synthese)

    # 4. Constitution du contenu final enrichi
    content = "\n".join([
        "### Axe des portes — lecture karmique",
        "Résumé de la dynamique pré-calculé :",
        synthese,
        "",
        f"Porte invisible : {signe_invisible} (Maison {maison_invisible})",
        f"Porte visible : {signe_visible} (Maison {maison_visible})",
        "",
        "#### Interprétation de base (BDD)",
        texte_bdd if texte_bdd else "(aucune donnée BDD)",
        "",
        "#### Analyse du Maître de la porte (ce qui réactive le passé)",
        *(ruler_lines if ruler_lines else ["- (maître non détecté)"]),
        "",
        "#### Chiron (Le point de friction de cet axe)",
        f"- En {chiron.get('signe', '—')} (Maison {chiron.get('maison', '—')}) à {chiron.get('degre_dans_signe', '—')}°",
    ]).strip()

    summary = summarize_chapter(
        chapter_title="Axe des portes — visible, invisible et blessure karmique",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    return {
        "id": "axe_portes",
        "title": "Axe des portes — visible, invisible et blessure karmique",
        "data": {
            "axe_des_portes": axe,
            "chiron": chiron,
            "porte_invisible_maison": maison_invisible,
            "porte_visible_maison": maison_visible,
            "porte_invisible_signe": signe_invisible,
            "porte_visible_signe": signe_visible,
            "rulers": rulers,
            "rulers_details": rulers_details,
            "bdd_found": bool(texte_bdd),
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


def interpret_block_axe_portes_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:

    # 🔹 1. Récupérer le contenu
    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return ""

    # 🔹 2. Contexte global
    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()

    # 🔹 3. Intro fixe du chapitre (IMPORTANT)
    intro_txt = CHAPTER_INTROS.get("axe_portes", "")

    # 🔹 4. Variables narratif
    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []

    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "femme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"
    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n\n".join(memories[-7:]) if memories else "Aucune mémoire précédente"


    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Ta mission : rédiger le chapitre "Axe des Portes" d'une analyse profonde.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style direct, incarné, psychologique. Évite les envolées lyriques, reste dans l'analyse de la mécanique de l'âme.
- Pas d'introduction, pas de prénom. Entre directement dans le vif du sujet par une transition fluide avec ce qui précède.

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
Expliquer la dynamique de "sas" psychique et de passage :
- La Porte Invisible représente un lieu de distorsion ancienne, difficilement visible, qui agit comme une faille psychique répétitive.
- La Porte Visible ne doit jamais être décrite comme un objectif volontaire ou une mission.
Elle représente une zone où l'énergie cesse d'être bloquée lorsque le passage intérieur devient possible.
Chiron (traité au chapitre suivant) agit comme le mécanisme de franchissement entre ces deux pôles 
- Focus exclusif : Concentre-toi sur le concept de *flux*, de *sas*, d'*émergence* et de *pont*. Laisse la "direction de vie" aux Nœuds Lunaires et la blessure profonde à Chiron. Ici, on décrit une valve de décompression énergétique.

**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici ce qui a déjà été traité et l'angle utilisé :
{memories_txt}

**CONSIGNE ANTI-REDONDANCE IMPÉRATIVE**
- INTERDICTION de ré-expliquer les concepts listés ci-dessus.
- Si la Porte Invisible résonne avec un problème déjà évoqué dans la mémoire, montre comment il agit comme un "aimant" silencieux, et comment la Porte Visible permet enfin de l'exprimer ou de le purger.
- Varie ton vocabulaire : utilise des mots comme sas, aimant inconscient, émergence, canal, point de bascule, manifestation, pont, écoulement. Évite "chemin de vie", "mission" et "transformation".

**RÈGLES STRICTES DE RÉDACTION**
- **Mouvement fluide (Intégration organique) :** Ne fais pas une description statique. Décris un processus d'évolution de l'invisible vers le visible en intégrant le "Maître de la Porte" comme la force qui pousse ce flux. Aucune énumération technique.
- **Le rôle de Chiron (Transition obligatoire) :** Mentionne Chiron uniquement comme le point de friction ou de sensibilité qui *oblige* à ouvrir ce passage. Termine IMPÉRATIVEMENT ton texte par une transition fluide qui annonce la blessure fondamentale (puisque le chapitre suivant sera dédié à Chiron).
- **Format brut :** Texte en flux continu uniquement. Zéro titre, zéro liste.
- **Longueur :** Exactement 3 paragraphes denses (~300 à 350 mots au total).

**DONNÉES TECHNIQUES À TRANSFORMER EN PSYCHOLOGIE**
Axe central : {axe_central}
Contexte global : {theme_brief}

Données brutes de l'Axe des Portes : 
{content}

[Début du chapitre "Axe des Portes" en flux continu :]
""".strip()

    texte = (call_llm(prompt) or "").strip()

    # 🔥 ICI on force l’intro visible
    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte