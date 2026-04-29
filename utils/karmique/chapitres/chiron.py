from typing import Dict, Any, Optional, List
from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging

logger = logging.getLogger(__name__)


# -------------------------
# Blessures Karmiques de Chiron
# -------------------------
CHIRON_WOUNDS_KEY = {
    "Soleil": "blessure d'ego, identité étouffée ou dévalorisée",
    "Lune": "blessure de carence maternelle, insécurité émotionnelle profonde",
    "Mercure": "blessure d'intellect, difficulté à se faire entendre ou comprendre",
    "Vénus": "blessure affective, sentiment inconscient de ne pas mériter l'amour",
    "Mars": "blessure d'affirmation, colère refoulée ou sentiment d'impuissance",
    "Jupiter": "blessure de légitimité sociale ou de foi, sentiment d'injustice",
    "Saturne": "blessure de structure, manque de reconnaissance, peur de l'échec",
    "Uranus": "blessure de différence, sentiment profond d'être un alien ou un paria",
    "Neptune": "blessure de fusion ou d'abandon, déception face à la dureté du monde",
    "Pluton": "blessure de trahison ou d'abus de pouvoir, instinct de survie crispé",
    "Rahu": "blessure liée à l'évolution, peur panique de faire le grand saut",
    "Ketu": "blessure du passé qui empêche de lâcher prise",
    "Lune Noire": "blessure du vide, rejet viscéral et exigence de pureté impossible"
}

ALLOWED = {
    "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
    "Rahu", "Ketu", "Nœud Nord", "Nœud Sud", "Noeud Nord", "Noeud Sud",
    "Lune Noire",
    "Ascendant", "ASC",
    "MC", "Milieu du Ciel",
    "Descendant", "DSC",
    "FC", "Fond du Ciel", "IC"
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
    s = s.replace(" ", "_")
    s = s.replace("’", "'")
    return s


def _norm_aspect_name(x: str) -> str:
    if not x:
        return ""
    low = str(x).strip().lower()
    if low in ("carre", "carré"):
        return "carré"
    if low == "conjonction":
        return "conjonction"
    if low == "opposition":
        return "opposition"
    if low == "trigone":
        return "trigone"
    if low == "sextile":
        return "sextile"
    return _slug(x)

SIGN_RULERS = {
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

def _collect_chiron_rulers(theme: Dict[str, Any], chiron_sign: str) -> List[Dict[str, Any]]:
    planetes = theme.get("planetes", {}) or {}
    rulers = SIGN_RULERS.get(_slug(chiron_sign), [])
    out: List[Dict[str, Any]] = []

    for r in rulers:
        p = planetes.get(r)
        if not isinstance(p, dict):
            continue

        r_slug = _slug(r)
        signe = p.get("signe")
        maison = p.get("maison")

        out.append({
            "name": r,
            "bdd_prefix": f"chiron_m_{r_slug}",
            "signe": signe,
            "maison": maison,
        })

    return out


def _collect_chiron_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    out: List[Dict[str, Any]] = []



    label_map = {
        "Rahu": "noeud_nord",
        "Nœud Nord": "noeud_nord",
        "Noeud Nord": "noeud_nord",
        "Ketu": "noeud_sud",
        "Nœud Sud": "noeud_sud",
        "Noeud Sud": "noeud_sud",
        "Soleil": "soleil",
        "Lune": "lune",
        "Mercure": "mercure",
        "Vénus": "venus",
        "Mars": "mars",
        "Jupiter": "jupiter",
        "Saturne": "saturne",
        "Uranus": "uranus",
        "Neptune": "neptune",
        "Pluton": "pluton",
        "Lune Noire": "lune_noire",
        "Ascendant": "asc",
        "ASC": "asc",
        "MC": "mc",
        "Milieu du Ciel": "mc",
        "Descendant": "dsc",
        "DSC": "dsc",
        "FC": "fc",
        "Fond du Ciel": "fc",
        "IC": "fc", 
            }

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        asp = _norm_aspect_name(a.get("aspect"))
        orb = a.get("orbe")

        other = None
        if p1 == "Chiron" and p2 in ALLOWED:
            other = p2
        elif p2 == "Chiron" and p1 in ALLOWED:
            other = p1

        if not other:
            continue

        try:
            orb = round(float(orb), 2) if orb is not None else None
        except Exception:
            orb = None

        other_key = label_map.get(other)
        if not other_key:
            continue

        bdd_key = f"{asp}_{other_key}"

        out.append({
            "with": other,
            "aspect": asp,
            "orb": orb,
            "bdd_key": bdd_key,
        })

    out.sort(key=lambda x: x.get("orb", 999) if x.get("orb") is not None else 999)
    return out

def _collect_chiron_angles(theme: Dict[str, Any], orb_limit: float = 5.0) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    out: List[Dict[str, Any]] = []

    angle_labels = {
        "Ascendant": "Ascendant",
        "ASC": "Ascendant",
        "MC": "MC",
        "Milieu du Ciel": "MC",
        "Descendant": "Descendant",
        "DSC": "Descendant",
        "FC": "FC",
        "Fond du Ciel": "FC",
        "IC": "FC",
    }

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        asp = _norm_aspect_name(a.get("aspect"))
        orb = a.get("orbe")

        if asp != "conjonction":
            continue

        other = None
        if p1 == "Chiron" and p2 in angle_labels:
            other = angle_labels[p2]
        elif p2 == "Chiron" and p1 in angle_labels:
            other = angle_labels[p1]

        if not other:
            continue

        try:
            orb = round(float(orb), 2) if orb is not None else None
        except Exception:
            orb = None

        if orb is not None and orb > orb_limit:
            continue

        out.append({
            "angle": other,
            "aspect": asp,
            "orb": orb,
        })

    out.sort(key=lambda x: x.get("orb", 999) if x.get("orb") is not None else 999)
    return out

def build_block_chiron(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    planetes = theme.get("planetes", {}) or {}
    chiron = planetes.get("Chiron")

    if not isinstance(chiron, dict):
        return None

    signe = chiron.get("signe")
    maison = chiron.get("maison")

    if not signe and maison is None:
        return None

    txt_signe = get_karmique_interp("chiron", "Signe", signe) if signe else ""
    txt_maison = get_karmique_interp("chiron", "Maison", str(maison)) if maison is not None else ""

    rulers_details = _collect_chiron_rulers(theme, signe) if signe else []

    aspects_chiron = _collect_chiron_aspects(theme)
    logger.debug("CHIRON ASPECTS RAW: %s", aspects_chiron)
    angles_chiron = _collect_chiron_angles(theme)

    for a in aspects_chiron:
        interp = get_karmique_interp("chiron", "aspect", a["bdd_key"])
        logger.debug("CHIRON BDD KEY: %s -> %s", a["bdd_key"], bool(interp))

    aspects_lines = []
    for a in aspects_chiron:
        interp = get_karmique_interp("chiron", "aspect", a["bdd_key"])
        if interp:
            orb_txt = f" (orbe {a['orb']}°)" if a.get("orb") is not None else ""
            aspects_lines.append(f"**{a['aspect'].capitalize()} avec {a['with']}**{orb_txt}")
            aspects_lines.append(interp.strip())
            aspects_lines.append("")


    rulers_lines = []
    for r in rulers_details:
        prefix = r["bdd_prefix"]
        r_name = r["name"]
        r_sign = r.get("signe")
        r_house = r.get("maison")
        is_transsat = r_name in {"Uranus", "Neptune", "Pluton"}

        if r_sign or r_house is not None:
            extra = []
            if r_sign:
                extra.append(str(r_sign))
            if r_house is not None:
                extra.append(f"Maison {r_house}")
            rulers_lines.append(f"**{r_name}** ({' — '.join(extra)})")
            rulers_lines.append("")

        if r_sign and not is_transsat:
            txt_r_sign = get_karmique_interp(prefix, "signe", _slug(r_sign))
            if txt_r_sign:
                rulers_lines.append(f"**En {r_sign} :**")
                rulers_lines.append(txt_r_sign.strip())
                rulers_lines.append("")

        if r_house is not None:
            logger.debug("CHIRON RULER HOUSE LOOKUP: %s maison %s", prefix, str(r_house))
            txt_r_house = get_karmique_interp(prefix, "maison", str(r_house))
            logger.debug("CHIRON RULER HOUSE TXT: %s", txt_r_house)
            if txt_r_house:
                rulers_lines.append(f"**En Maison {r_house} :**")
                rulers_lines.append(txt_r_house.strip())
                rulers_lines.append("")

    # -------------------------
    # SYNTHÈSE PSYCHOLOGIQUE (NEW)
    # -------------------------
    profil = []

    # 1. Analyse par les aspects (Quelle énergie fait mal ?)
    for a in aspects_chiron:
        other = a.get("with")
        orb = a.get("orb")

        if orb is not None and orb > 5:
            continue

        if other in CHIRON_WOUNDS_KEY:
            profil.append(CHIRON_WOUNDS_KEY[other])

    # 2. Analyse par les éléments de la Maison (Dans quel domaine ça fait mal ?)
    if str(maison) in ("1", "5", "9"):
        profil.append("blessure liée à l'identité, l'expression de soi et la place à prendre")
    elif str(maison) in ("2", "6", "10"):
        profil.append("blessure liée à la légitimité, la matière et la réussite concrète")
    elif str(maison) in ("3", "7", "11"):
        profil.append("blessure liée au lien, à la communication et au regard de l'autre")
    elif str(maison) in ("4", "8", "12"):
        profil.append("blessure enfouie, karmique, viscérale et souvent transgénérationnelle")

    for angle in angles_chiron:
        angle_name = angle.get("angle")

        if angle_name == "Ascendant":
            profil.append("blessure visible dans l'identité, le corps, la posture et la manière d'exister")
        elif angle_name == "MC":
            profil.append("blessure liée à la place sociale, à la vocation, à l'exposition et au sentiment de légitimité")
        elif angle_name == "Descendant":
            profil.append("blessure rejouée dans le lien, les projections relationnelles et le face-à-face avec l'autre")
        elif angle_name == "FC":
            profil.append("blessure racinaire, familiale, intime, liée au socle intérieur et au sentiment d'appartenance")

    # Nettoyage des doublons (tout en gardant l'ordre)
    profil_unique = list(dict.fromkeys(profil))
    
    synthese = ""
    if profil_unique:
        synthese = "Noyau de la blessure pré-calculé : " + " ; ".join(profil_unique) + "."

    # -------------------------
    # CONSTITUTION DU CONTENU
    # -------------------------
    parts = []
    
    parts.append("### Chiron — lecture karmique")
    parts.append("Résumé psychologique :")
    parts.append(synthese if synthese else "(aucune synthèse pré-calculée)")

    if angles_chiron:
        angle_lines = []
        for angle in angles_chiron:
            orb_txt = f" avec un orbe de {angle['orb']}°" if angle.get("orb") is not None else ""
            angle_lines.append(f"- Chiron conjoint {angle['angle']}{orb_txt}")

        parts.append("Angles touchés par Chiron :\n" + "\n".join(angle_lines))

    if txt_signe:
        parts.append(f"#### Chiron en {signe}\n{txt_signe}")

    if txt_maison:
        parts.append(f"#### Chiron en Maison {maison}\n{txt_maison}")

    if aspects_lines:
        parts.append("#### Aspects de Chiron\n" + "\n".join(aspects_lines).strip())
    
    if rulers_lines:
        parts.append("#### Maître(s) de Chiron (les mécanismes de défense)\n" + "\n".join(rulers_lines).strip())

    content = "\n\n".join([p for p in parts if p]).strip()
    
    summary = summarize_chapter(
        chapter_title="Chiron : la blessure initiatique",
        chapter_text=content,
        call_llm=global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None,
    )

    return {
        "id": "chiron",
        "title": "Chiron : la blessure initiatique",
        "data": {
            "signe": signe,
            "maison": maison,
            "aspects": aspects_chiron,
            "angles": angles_chiron,
            "rulers_details": rulers_details,
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


def interpret_block_chiron_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm=None,
    global_ctx: Dict[str, Any] | None = None,
) -> str:

    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    data = block.get("data", {}) or {}
    signe = data.get("signe")
    maison = data.get("maison")

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    karmic_ctx = (global_ctx or {}).get("karmic_context", "").strip()

    intro_txt = CHAPTER_INTROS.get("chiron", "")
    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n\n".join(memories[-8:]) if memories else "Aucune mémoire précédente"

    

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Ta mission : rédiger le chapitre "Chiron" (la blessure fondamentale et la surcompensation) d'une analyse profonde.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style incarné, psychologique, dense, sans phrases creuses.
- Ton sérieux, avec une légère touche d’ironie possible pour souligner les stratégies d'évitement ou les "béquilles" de l'ego.
- Pas d'introduction, pas de prénom. Entre directement dans le vif du sujet par une transition fluide avec ce qui précède.

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
Mettre en lumière le "talon d'Achille" et la stratégie d'adaptation :
- La zone de vulnérabilité consciente : la plaie à vif, le sentiment d'insuffisance, de honte ou de décalage inné.
- La "béquille" psychologique : les mécanismes de défense (surcompensation, syndrome de l'imposteur, évitement ou projection) mis en place pour masquer la douleur.
- Focus exclusif : Concentre-toi sur la *vulnérabilité* et la *compensation*. Laisse le vertige absolu à la Lune Noire, l'énergie bloquée aux Interceptions et les crises actives à la Maison 8. Ici, on parle d'une hyper-sensibilité avec laquelle il faut apprendre à vivre lucidement.

**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici ce qui a déjà été traité et l'angle utilisé :
{memories_txt}

**CONSIGNE ANTI-REDONDANCE IMPÉRATIVE**
- INTERDICTION de ré-expliquer les fragilités listées ci-dessus.
- Si Chiron touche à une peur déjà abordée dans la mémoire, montre comment la personne a construit une *armure* ou une *stratégie de surcompensation* autour, plutôt que de réexpliquer la peur elle-même.
- Varie ton vocabulaire : utilise des termes comme plaie à vif, talon d'Achille, béquille, surcompensation, évitement, hypersensibilité, lucidité douloureuse. Évite "transformation", "blocage", "vide" et "guérison".

**RÈGLES STRICTES DE RÉDACTION**
- **Refus de la guérison magique :** Écarte impérativement toute notion de "guérison" simpliste ou de développement personnel positif. Décris plutôt comment cette blessure s’intègre, se rejoue en boucle, et devient à terme un point d'hyper-lucidité (on apprend à "boiter avec grâce").
- **Intégration technique organique :** Intègre le maître de Chiron et ses aspects de manière fluide pour montrer comment ils intensifient ou déplacent la dynamique de la blessure (ex: "Le carré de [Planète] vient irriter cette zone en..."). Aucune analyse technique isolée.
- **Format brut :** Texte en flux continu uniquement. Zéro titre, zéro liste.
- **Longueur :** Exactement 3 paragraphes denses (~300 à 350 mots au total).

**DONNÉES TECHNIQUES À TRANSFORMER EN PSYCHOLOGIE**
Axe central : {axe_central}
Contexte global : {theme_brief}
Contexte karmique spécifique : {karmic_ctx}

Éléments techniques de Chiron :
- Signe : {signe}
- Maison : {maison}
- Données brutes BDD : {content}

[Début de l'analyse en flux continu :]
""".strip()

    print("\n" + "=" * 100)
    print("PROMPT CHIRON")
    print("=" * 100)
    print(prompt)
    print("=" * 100 + "\n")

    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte
