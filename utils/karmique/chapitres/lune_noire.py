from typing import Dict, Any, Optional, List
from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging

logger = logging.getLogger(__name__)

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
        return "carre"
    if low == "conjonction":
        return "conjonction"
    if low == "opposition":
        return "opposition"
    if low == "trigone":
        return "trigone"
    if low == "sextile":
        return "sextile"
    return _slug(x)


def _collect_lune_noire_aspects(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    aspects = theme.get("aspects") or []
    out: List[Dict[str, Any]] = []

    ASPECT_PRIORITY = {
        "conjonction": 5,
        "carre": 4,
        "opposition": 4,
        "trigone": 2,
        "sextile": 1,
    }

    PLANET_PRIORITY = {
        "Saturne": 5,
        "Pluton": 5,
        "Lune": 4,
        "Soleil": 4,
        "Mars": 4,
        "Neptune": 3,
        "Uranus": 3,
        "Mercure": 2,
        "Vénus": 2,
        "Jupiter": 2,
        "Rahu": 4,
        "Ketu": 4,
        "Nœud Nord": 4,
        "Nœud Sud": 4,
        "Noeud Nord": 4,
        "Noeud Sud": 4,
    }

    ALLOWED = {
        "Soleil", "Lune", "Mercure", "Vénus", "Mars",
        "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton",
        "Rahu", "Ketu", "Nœud Nord", "Nœud Sud", "Noeud Nord", "Noeud Sud"
    }

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
    }

    for a in aspects:
        p1 = a.get("planete1")
        p2 = a.get("planete2")
        asp = _norm_aspect_name(a.get("aspect"))
        orb = a.get("orbe")

        other = None
        if p1 == "Lune Noire" and p2 in ALLOWED:
            other = p2
        elif p2 == "Lune Noire" and p1 in ALLOWED:
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

        retrograde = False

        try:
            retrograde = bool(
                (theme.get("planetes", {})
                    .get(other, {})
                    .get("retrograde", False))
            )
        except Exception:
            retrograde = False

        impact_score = (
            ASPECT_PRIORITY.get(asp, 1)
            * PLANET_PRIORITY.get(other, 1)
        )

        out.append({
            "with": other,
            "aspect": asp,
            "orb": orb,
            "bdd_key": f"aspect_{other_key}",
            "impact_score": impact_score,
            "retrograde": retrograde,
        })

    out.sort(
        key=lambda x: (
            -x.get("impact_score", 0),
            x.get("orb", 999) if x.get("orb") is not None else 999
        )
    )
    return out


def build_block_lune_noire(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    planetes = theme.get("planetes", {}) or {}
    ln = planetes.get("Lune Noire")

    if not isinstance(ln, dict):
        return None

    signe = ln.get("signe")
    maison = ln.get("maison")

    if not signe and maison is None:
        return None

    txt_signe = get_karmique_interp("lune_noire", "Signe", signe) if signe else ""
    txt_maison = get_karmique_interp("lune_noire", "Maison", str(maison)) if maison is not None else ""

    aspects_ln = _collect_lune_noire_aspects(theme)

    aspects_lines = []
    for a in aspects_ln:
        interp = get_karmique_interp("lune_noire", a["bdd_key"], a["aspect"])
        logger.debug(
            "LN BDD CALL | key=%s | aspect=%s",
            a["bdd_key"],
            a["aspect"]
        )

        logger.debug(
            "LN INTERP | %s",
            interp
        )

        if interp:
            orb_txt = f" (orbe {a['orb']}°)" if a.get("orb") is not None else ""
            aspects_lines.append(f"**{a['aspect'].capitalize()} avec {a['with']}**{orb_txt}")
            aspects_lines.append(interp.strip())
            aspects_lines.append("")

    parts = []

    if txt_signe:
        parts.append(f"### Lune Noire en {signe}\n{txt_signe}")

    if txt_maison:
        parts.append(f"### Lune Noire en Maison {maison}\n{txt_maison}")

    if aspects_lines:
        parts.append("### Aspects de la Lune Noire\n" + "\n".join(aspects_lines).strip())

    content = "\n\n".join([p for p in parts if p]).strip()

    fn = global_ctx.get("call_llm") if isinstance(global_ctx, dict) else None
    call_llm_safe = fn if callable(fn) else None

    summary = summarize_chapter(
        chapter_title="Lune Noire : la mémoire interdite",
        chapter_text=content,
        call_llm=call_llm_safe,
    )

    return {
        "id": "lune_noire",
        "title": "Lune Noire : la mémoire interdite",
        "data": {
            "signe": signe,
            "maison": maison,
            "aspects": aspects_ln,
        },
        "content": content,
        "text": content,
        "summary": summary,
    }


def interpret_block_lune_noire_llm(
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

    aspects_txt = "\n".join(
        f"{a['aspect'].capitalize()} avec {a['with']}"
        + (" rétrograde" if a.get("retrograde") else "")
        + (f" (orbe {a['orb']}°)" if a.get("orb") is not None else "")
        for a in data.get("aspects", [])
    )

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()
    karmic_ctx = (global_ctx or {}).get("karmic_context", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()
    
    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("lune_noire", "")
    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n\n".join(memories[-7:]) if memories else "Aucune mémoire précédente"

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Ta mission : rédiger le chapitre "Lune Noire" d'une analyse profonde.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style incarné, dense, analytique. Ton sérieux, avec une pointe d'ironie ou de tranchant : tu n'hésites pas à pointer du doigt ce qui dérange, le tabou, l'inavouable.
- Aucun cliché de développement personnel, pas de complaisance.
- Pas d'introduction, pas de prénom. Entre directement dans le vif du sujet par une transition fluide avec ce qui précède.

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
IMPORTANT : cette analyse repose sur la Lune Noire Moyenne (point symbolique stabilisé), et non sur la Lune Noire Vraie. Interprète-la comme une dynamique psychique profonde, constante et structurelle.
Mettre en lumière la zone d'intransigeance absolue et le vertige intérieur :
- Le point de tension : ce qui attire (fascination) et révulse simultanément.
- Les réactions excessives, la radicalité, la compulsion ou le rejet catégorique.
- L'illusion d'un vide ou d'un manque que rien ne semble pouvoir combler, poussant à une exigence inhumaine.
- Focus exclusif : Concentre-toi sur le concept de "l'absolu", de la "transgression" et du "vide". Laisse les crises de transformation à la Maison 8 et la blessure à guérir à Chiron. Ici, on ne guérit pas la Lune Noire, on apprend à vivre avec son exigence radicale.

**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici ce qui a déjà été traité et l'angle utilisé :
{memories_txt}

**CONSIGNE ANTI-REDONDANCE IMPÉRATIVE**
- INTERDICTION de ré-expliquer les concepts listés ci-dessus.
- Si la Lune Noire touche à une peur déjà évoquée dans la mémoire, montre comment elle la rend *radicale*, *obsessionnelle* ou *taboue*, plutôt que de réexpliquer la peur elle-même.
- Varie ton vocabulaire : utilise des termes comme intransigeance, gouffre, fascination, absolu, vide, transgression, rejet, aimant, zone interdite, nœud aveugle. Évite les mots "blessure", "transformation" et "ombre", sauf si le terme est réellement nécessaire.

**RÈGLES STRICTES DE RÉDACTION**
- **Unité de lecture :** Fusionne le signe et la maison en un seul noyau psychologique.
- **Intégration technique organique :** Tisse les aspects ({aspects_txt}) directement dans le récit pour expliquer *comment* cette radicalité se manifeste (ex: "La tension de [Planète] vient exacerber ce rejet de..."). Aucune énumération stérile.
- **Format brut :** Texte en flux continu uniquement. Zéro titre, zéro liste.
- **Longueur :** Exactement 3 paragraphes denses (~300 à 350 mots au total).

**DONNÉES TECHNIQUES À TRANSFORMER EN PSYCHOLOGIE**
Axe central : {axe_central}
Contexte global : {theme_brief}
Contexte karmique spécifique : {karmic_ctx}

Éléments techniques de la Lune Noire :
- Signe : {signe}
- Maison : {maison}
- Aspects spécifiques : {aspects_txt}
- Données brutes BDD : {content}

[Début de l'analyse en flux continu :]
""".strip()


    logger.debug("=" * 80)
    logger.debug("PROMPT CHAPITRE LUNE NOIRE")
    logger.debug("=" * 80)
    logger.debug(prompt)
    logger.debug("=" * 80)

    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte