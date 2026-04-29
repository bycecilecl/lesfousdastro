# utils/karmique/chapitres/luminaires_karmiques.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique._slug import slug, house_int
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
from utils.llm_system_prompts import SYSTEM_KARMIQUE


# Orbes (tu ajusteras après)
MOON_ORB_LIMIT = 8.0
SUN_ORB_LIMIT = 8.0

SIGN_RULERS = {
    "Bélier": "Mars",
    "Taureau": "Vénus",
    "Gémeaux": "Mercure",
    "Cancer": "Lune",
    "Lion": "Soleil",
    "Vierge": "Mercure",
    "Balance": "Vénus",
    "Scorpion": "Mars",  # version classique
    "Sagittaire": "Jupiter",
    "Capricorne": "Saturne",
    "Verseau": "Saturne",
    "Poissons": "Jupiter",
}


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _norm_aspect(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    low = s.lower()
    if low in ("carre", "carré"):
        return "Carré"
    if low == "trigone":
        return "Trigone"
    if low == "sextile":
        return "Sextile"
    if low == "opposition":
        return "Opposition"
    if low == "conjonction":
        return "Conjonction"
    return s


def _collect_luminary_aspects(theme: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Récupère les aspects utiles des luminaires à partir de theme["aspects"].
    Ici c'est volontairement simple : on filtre par orbe max.
    """
    aspects = theme.get("aspects") or []

    ALLOWED = {"Conjonction", "Carré", "Opposition", "Trigone", "Sextile"}
    # Karmique : on ne garde que certains corps
    MOON_KARMIC_BODIES = {"Rahu", "Ketu", "Lune Noire", "Saturne", "Pluton", "Neptune", "Uranus"}
    SUN_KARMIC_BODIES  = {"Rahu", "Ketu", "Saturne", "Pluton", "Lune Noire"}
    moon_hits: List[Dict[str, Any]] = []
    sun_hits: List[Dict[str, Any]] = []

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        typ = _norm_aspect(a.get("aspect"))
        orb = a.get("orbe")

        if typ not in ALLOWED:
            continue

        try:
            orbf = float(orb) if orb is not None else None
        except Exception:
            orbf = None
        if orbf is None:
            continue

        # Lune (karmique filtré)
        if p1 == "Lune" or p2 == "Lune":
            other = p2 if p1 == "Lune" else p1

            if other in MOON_KARMIC_BODIES:
                if typ in ("Conjonction", "Opposition", "Carré"):
                    if orbf <= 10:
                        moon_hits.append({"with": other, "type": typ, "orb": round(orbf, 2)})

                elif typ in ("Trigone", "Sextile"):
                    if orbf <= 2:
                        moon_hits.append({"with": other, "type": typ, "orb": round(orbf, 2)})

        # Soleil (karmique filtré)
        if p1 == "Soleil" or p2 == "Soleil":
            other = p2 if p1 == "Soleil" else p1

            if other in SUN_KARMIC_BODIES:
                if typ in ("Conjonction", "Opposition", "Carré"):
                    if orbf <= 10:
                        sun_hits.append({"with": other, "type": typ, "orb": round(orbf, 2)})

                elif typ in ("Trigone", "Sextile"):
                    if orbf <= 2:
                        sun_hits.append({"with": other, "type": typ, "orb": round(orbf, 2)})
    moon_hits.sort(key=lambda x: x.get("orb", 999))
    sun_hits.sort(key=lambda x: x.get("orb", 999))

    moon_hits = moon_hits[:3]
    sun_hits = sun_hits[:2]

    return {"moon_aspects": moon_hits, "sun_aspects": sun_hits}

def _aspect_bdd(astre: str, aspect_type: str, other_body: str) -> str:
    # normaliser type
    typ = slug(aspect_type)  # "Conjonction" -> "conjonction", "Carré" -> "carre", etc.

    # normaliser l'autre corps (noeuds + lune noire)
    other = (other_body or "").strip()

    alias = {
        "Rahu": "noeud_nord",
        "Ketu": "noeud_sud",
        "Noeud Nord": "noeud_nord",
        "Noeud Sud": "noeud_sud",
        "Nœud Nord": "noeud_nord",
        "Nœud Sud": "noeud_sud",
        "Lune Noire": "lune_noire",
        "Lilith": "lune_noire",
    }
    other_slug = alias.get(other, slug(other))

    key = f"{typ}_{other_slug}"
    return get_karmique_interp(astre, "aspect", key) or ""


def build_block_luminaires_karmiques(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Chapitre Luminaires :
    - Lune : signe + maison (CSV)
    - Soleil : maison (CSV) (tu n'as pas encore Soleil/Signe dans ton CSV -> normal)
    - Planète précédente/suivante de la Lune : via global_ctx["context_moon_flow"] si fourni
    - Aspects : pris depuis theme["aspects"]
    """
    planets = theme.get("planetes") or {}
    lune = planets.get("Lune") if isinstance(planets.get("Lune"), dict) else {}
    soleil = planets.get("Soleil") if isinstance(planets.get("Soleil"), dict) else {}

    print("DEBUG LUNE LONG =", lune.get("longitude"))
    print("DEBUG SOLEIL LONG =", soleil.get("longitude"))

    moon_long = lune.get("longitude")
    sun_long = soleil.get("longitude")

    lunation_phase = None
    lunation_angle = None

    if moon_long is not None and sun_long is not None:
        lunation_angle = round((float(moon_long) - float(sun_long)) % 360, 2)

        if lunation_angle < 45:
            lunation_phase = "Nouvelle Lune"
        elif lunation_angle < 90:
            lunation_phase = "Premier croissant"
        elif lunation_angle < 135:
            lunation_phase = "Premier quartier"
        elif lunation_angle < 180:
            lunation_phase = "Gibbeuse croissante"
        elif lunation_angle < 225:
            lunation_phase = "Pleine Lune"
        elif lunation_angle < 270:
            lunation_phase = "Gibbeuse décroissante"
        elif lunation_angle < 315:
            lunation_phase = "Dernier quartier"
        else:
            lunation_phase = "Lune balsamique"

    moon_sign = lune.get("signe")
    moon_ruler = SIGN_RULERS.get(moon_sign)
    moon_ruler_data = planets.get(moon_ruler) if moon_ruler else None
    moon_house = house_int(lune.get("maison"))

    sun_sign = soleil.get("signe")
    sun_house = house_int(soleil.get("maison"))

    if not moon_sign and moon_house is None and sun_house is None:
        return None

    # ---- BDD (CSV) ----
    moon_sign_txt = get_karmique_interp("Lune", "signe", moon_sign) if moon_sign else None
    moon_house_txt = get_karmique_interp("Lune", "maison", str(moon_house)) if moon_house is not None else None
    sun_sign_txt = get_karmique_interp("Soleil", "signe", sun_sign) if sun_sign else None
    sun_house_txt = get_karmique_interp("Soleil", "maison", str(sun_house)) if sun_house is not None else None
    lunation_txt = get_karmique_interp("Lunaison", "phase", lunation_phase) if lunation_phase else None
    print("DEBUG LUNAISON PHASE =", lunation_phase)
    print("DEBUG LUNAISON ANGLE =", lunation_angle)
    print("DEBUG LUNAISON BDD =", repr(lunation_txt[:300] if lunation_txt else None))


    # ---- planète précédente / suivante de la Lune (si global_ctx présent) ----
    prev_next = {}
    if isinstance(global_ctx, dict):
        prev_next = (global_ctx.get("context_moon_flow") or {}) if isinstance(global_ctx.get("context_moon_flow"), dict) else {}

    prev = prev_next.get("prev")
    nextp = prev_next.get("next")

    # BDD : lune,precedente,<planete> (tu l'as dans ton CSV)
    prev_txt = None
    next_txt = None

    if isinstance(prev, dict):
        prev_name = prev.get("name")
        if prev_name:
            prev_txt = get_karmique_interp("lune", "precedente", slug(prev_name))

    if isinstance(nextp, dict):
        next_name = nextp.get("name")
        if next_name:
            next_txt = get_karmique_interp("lune", "suivante", slug(next_name))

    # ---- aspects ----
    asp = _collect_luminary_aspects(theme)
    moon_aspects = asp.get("moon_aspects") or []
    sun_aspects = asp.get("sun_aspects") or []

    # ---- assembler content (facts + BDD) ----
    lines: List[str] = []
    
    # Données Lune
    if moon_sign:
        lines.append(f"POSITION LUNE: {moon_sign} en Maison {moon_house}")
        if moon_sign_txt: lines.append(f"INTERP SIGNE: {moon_sign_txt.strip()}")
        if moon_house_txt: lines.append(f"INTERP MAISON: {moon_house_txt.strip()}")

    # 👇 AJOUT ICI
    if moon_ruler and isinstance(moon_ruler_data, dict):
        ruler_sign = moon_ruler_data.get("signe")
        ruler_house = moon_ruler_data.get("maison")
        lines.append(f"MAITRE LUNE: {moon_ruler} en {ruler_sign} Maison {ruler_house}")

    if lunation_phase:
        lines.append(f"PHASE LUNAISON: {lunation_phase} (écart Soleil-Lune: {lunation_angle}°)")
    if lunation_txt:
        lines.append(f"INTERP LUNAISON: {lunation_txt.strip()}")

    # Planète précédente/suivante
    if isinstance(prev, dict) and prev.get("name"):
        lines.append(f"PLANETE PRECEDENTE LUNE: {prev.get('name')}. {prev_txt.strip() if prev_txt else ''}")
    if isinstance(nextp, dict) and nextp.get("name"):
        lines.append(f"PLANETE SUIVANTE LUNE: {nextp.get('name')}. {next_txt.strip() if next_txt else ''}")

    # Aspects Lune
    for a in moon_aspects:
        txt = _aspect_bdd("lune", a["type"], a["with"])
        lines.append(f"ASPECT LUNE: {a['type']} a {a['with']} (orbe {a['orb']}). {txt}")

    # Données Soleil
    if sun_sign or sun_house is not None:
        lines.append(f"POSITION SOLEIL: {sun_sign} en Maison {sun_house}")
        if sun_sign_txt:
            lines.append(f"INTERP SIGNE SOLEIL: {sun_sign_txt.strip()}")
        if sun_house_txt:
            lines.append(f"INTERP MAISON SOLEIL: {sun_house_txt.strip()}")
        # Aspects Soleil
        for a in sun_aspects:
            txt = _aspect_bdd("soleil", a["type"], a["with"])
            lines.append(f"ASPECT SOLEIL: {a['type']} a {a['with']} (orbe {a['orb']}). {txt}")

    # -------------------------
    # SYNTHÈSE PSYCHOLOGIQUE
    # -------------------------
    profil = []
    # Exemple de logique : Tension luminaire
    dist = None
    if sun_house is not None and moon_house is not None:
        raw_dist = abs(sun_house - moon_house)
        dist = min(raw_dist, 12 - raw_dist)

    if dist in (3, 4, 6):
        profil.append("forte tension entre les besoins profonds et l'identité")
    if moon_house == 4 or moon_house == 12:
        profil.append("mémoire émotionnelle très enfouie et puissante")


    moon_aspect_bodies = {a.get("with") for a in moon_aspects}
    sun_aspect_bodies = {a.get("with") for a in sun_aspects}

    if "Rahu" in moon_aspect_bodies or "Ketu" in moon_aspect_bodies:
        profil.append("tiraillement entre réflexe émotionnel ancien et direction d'évolution")

    if "Rahu" in sun_aspect_bodies or "Ketu" in sun_aspect_bodies:
        profil.append("l'identité consciente peut devenir un levier d'évolution majeur")

    if "Saturne" in moon_aspect_bodies:
        profil.append("vécu émotionnel marqué par la retenue, la peur ou l'auto-contrôle")

    if "Pluton" in moon_aspect_bodies or "Lune Noire" in moon_aspect_bodies:
        profil.append("mémoire émotionnelle intense, parfois défensive ou radicale")

    if "Saturne" in sun_aspect_bodies or "Pluton" in sun_aspect_bodies:
        profil.append("construction identitaire traversée par des enjeux de maîtrise, de pression ou de transformation")

    if moon_ruler and isinstance(moon_ruler_data, dict):
        ruler_house = moon_ruler_data.get("maison")

        if ruler_house in (6, 8, 12):
            profil.append("la sécurité émotionnelle dépend d'une zone de vie instable, exigeante ou inconfortable")

        elif ruler_house in (2, 4):
            profil.append("la mémoire émotionnelle cherche à se stabiliser et à sécuriser ce qui est perçu comme fragile")

        elif ruler_house in (1, 10):
            profil.append("les émotions influencent directement l'identité et la manière de se positionner dans la vie")
    
    synthese = "Dynamique Luminaire : " + " ; ".join(profil) + "." if profil else ""
    
    # On insère la synthèse au début du content
    content = synthese + "\n\n" + "\n".join(lines)
    

    summary = summarize_chapter(
        chapter_title="Luminaires karmiques : mémoire & incarnation",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    print("DEBUG LUMINAIRES SUMMARY BUILT =", summary)

    return {
        "id": "luminaires_karmiques",
        "title": "Luminaires karmiques : mémoire & incarnation",
        "data": {
            "moon_sign": moon_sign,
            "moon_house": moon_house,
            "sun_sign": sun_sign,
            "sun_house": sun_house,
            "prev": prev,
            "next": nextp,
            "moon_aspects": moon_aspects,
            "sun_aspects": sun_aspects,
            "lunation_phase": lunation_phase,
            "lunation_angle": lunation_angle,
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


def interpret_block_luminaires_karmiques_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm,
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Réécrit le chapitre des luminaires en texte client-friendly,
    sans inventer et en restant cohérent avec le fil karmique global.
    """
    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    data = block.get("data") or {}

    moon_sign = data.get("moon_sign")
    moon_house = data.get("moon_house")
    sun_sign = data.get("sun_sign")
    sun_house = data.get("sun_house")
    lunation_phase = data.get("lunation_phase")
    lunation_angle = data.get("lunation_angle")

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    themes_deja_traites = (global_ctx or {}).get("themes_deja_traites", []) or []
    themes_txt = "\n".join([f"- {t}" for t in themes_deja_traites]) if themes_deja_traites else "- aucun pour l’instant"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("luminaires_karmiques", "")

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Tu rédiges le chapitre Luminaires d'une analyse karmique en cours.

**STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Phrases courtes à moyennes. Concret avant abstrait.
- Une phrase = une idée. Pas d'accumulation de subordonnées.
- Interdiction de commencer une phrase par un aspect ("Le sextile à Pluton indique…", "L'opposition à Neptune suggère…"). Les aspects s'insèrent dans une phrase qui parle d'abord du vécu.
- Grain visé :
  "Cette Lune ne cherche pas l'aventure. Elle cherche à ne pas perdre ce qu'elle a construit. Et c'est précisément là que le Soleil la dérange."
  "Il y a une contradiction qui ne se résout pas facilement : le besoin de rester, et la pulsion de creuser plus loin."
  "Ce n'est pas une tension abstraite. Elle se rejoue dans chaque relation, chaque fois qu'il faut choisir entre la sécurité et la vérité."


**OBJECTIF**
Montrer le dialogue entre mémoire émotionnelle (Lune) et construction identitaire (Soleil) :
ce qui est installé, ce qui cherche à émerger, la tension entre les deux.
Prends en compte le maître de la Lune comme point d’ancrage de la mémoire émotionnelle :
c’est lui qui indique où et comment les émotions cherchent à se stabiliser ou se rejouer.
Si une INTERP LUNAISON est présente, tu dois l’exploiter clairement comme une dynamique centrale du dialogue Lune/Soleil, pas comme une simple mention finale.
Prends aussi en compte la phase de lunaison comme rythme du lien entre la Lune et le Soleil :
elle indique si cette dynamique se vit comme un début de cycle, une tension de croissance, une culmination ou une fin de cycle.


**RÈGLES**
- Commence par la mémoire émotionnelle (Lune), puis montre ce que le Soleil vient déranger ou faire émerger.
- Lune et Soleil analysés ensemble, jamais séparément.
- Texte en flux continu, sans titre ni liste.
- S'appuie sur l'axe karmique et les thèmes déjà abordés — aucune répétition.
- 3 paragraphes, ~300 mots.
- Aspects intégrés naturellement, aucune donnée inventée.

**CONTEXTE**
Axe karmique : {axe_central}
Thèmes abordés : {themes_txt}
Contexte global : {theme_brief}

**DONNÉES**
Lune : {moon_sign} (Maison {moon_house})
Soleil : {sun_sign or '—'} (Maison {sun_house})
Phase de lunaison : {lunation_phase or '—'} ({lunation_angle or '—'}°)
Matière brute Lune/Soleil/Lunaison :
{content}

[Analyse en flux continu :]
""".strip()


    
    print("\n" + "=" * 80)
    print("PROMPT LUMINAIRES")
    print("=" * 80)
    print(prompt)
    print("=" * 80 + "\n")

    texte = (call_llm(prompt, system_prompt=SYSTEM_KARMIQUE) or "").strip()

    print("\n" + "-" * 80)
    print("RÉPONSE LLM")
    print("-" * 80)
    print(texte)
    print("-" * 80 + "\n")

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte