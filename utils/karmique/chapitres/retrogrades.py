# utils/karmique/chapitres/retrogrades.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable

from utils.karmique.planete_retro_bdd import get_retro_interp
from utils.karmique.chapitres.chapter_summary import summarize_chapter
from utils.karmique.chapitres.intro_chapitres import CHAPTER_INTROS
import logging
logger = logging.getLogger(__name__)


def _slug(s: Any) -> str:
    """Normalisation basique pour matcher la BDD (signe en minuscules, sans accents)."""
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
    return s


def _house_int(value: Any) -> Optional[int]:
    """Normalise une maison astrologique en entier simple : 1, 2, 3, etc."""
    if value is None:
        return None

    try:
        return int(str(value).strip().replace("Maison", "").replace("maison", "").strip())
    except (TypeError, ValueError):
        return None


def _join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


SLOW_PLANETS = {"Uranus", "Neptune", "Pluton"}
PERSONAL_PLANETS = {"Mercure", "Vénus", "Mars"}
SENSITIVE_HOUSES = {1, 4, 7, 8, 12}


SIGN_RULERS = {
    "Bélier": "Mars",
    "Taureau": "Vénus",
    "Gémeaux": "Mercure",
    "Cancer": "Lune",
    "Lion": "Soleil",
    "Vierge": "Mercure",
    "Balance": "Vénus",
    "Scorpion": "Mars",  # maîtrise traditionnelle, volontaire ici
    "Sagittaire": "Jupiter",
    "Capricorne": "Saturne",
    "Verseau": "Saturne",  # maîtrise traditionnelle
    "Poissons": "Jupiter",  # maîtrise traditionnelle
}

KNOWN_RETRO_PLANETS = {
    "Mercure", "Vénus", "Mars",
    "Jupiter", "Saturne",
    "Uranus", "Neptune", "Pluton",
}


def _compute_impact_level(name: str, maison: Any) -> str:
    """
    Pondération astrologique :
    - fort : planète personnelle OU maison karmiquement sensible
    - moyen : Jupiter / Saturne hors maisons sensibles
    - fond : lentes générationnelles hors zones sensibles
    """

    maison_int = _house_int(maison)

    if name in PERSONAL_PLANETS:
        return "fort"

    if maison_int in SENSITIVE_HOUSES:
        return "fort"

    if name in {"Jupiter", "Saturne"}:
        return "moyen"

    return "fond"


def _collect_retrogrades(theme: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Retourne [{name, signe, maison, is_slow}, ...] pour chaque planète rétrograde."""
    planets = theme.get("planetes") or {}
    if not isinstance(planets, dict):
        return []

    out: List[Dict[str, Any]] = []
    for name, p in planets.items():
        name = str(name)
        if name not in KNOWN_RETRO_PLANETS:
            continue
        if not isinstance(p, dict):
            continue
        if p.get("retrograde") is True:
            out.append({
                "name": name,
                "signe": p.get("signe"),
                "maison": p.get("maison"),
                "is_slow": str(name) in SLOW_PLANETS,
                "is_personal": name in PERSONAL_PLANETS,
                "impact_level": _compute_impact_level(name, p.get("maison")),
                "governed_houses": _get_governed_houses(theme, name),
            })

    impact_order = {
        "fort": 0,
        "moyen": 1,
        "fond": 2,
    }

    out.sort(
        key=lambda x: (
            impact_order.get(x.get("impact_level", "moyen"), 1),
            x["is_slow"],
            x["name"],
        )
    )

    return out


def _build_retro_axis(retro: List[Dict[str, Any]]) -> str:
    """
    Détecte un axe psychologique commun aux rétrogrades
    pour éviter que le LLM invente une cohérence artificielle.
    """

    maisons = []

    for r in retro:
        m = _house_int(r.get("maison"))
        if m:
            maisons.append(m)

    themes = []

    if any(m in {1, 7} for m in maisons):
        themes.append("identité, relation et miroir de l’autre")

    if any(m in {2, 8} for m in maisons):
        themes.append("héritage karmique des ressources, attachements, pertes et deuils accumulés")

    if any(m in {3, 9} for m in maisons):
        themes.append("communication, pensée et vision intérieure")

    if any(m in {4, 10} for m in maisons):
        themes.append("héritage familial, légitimité et place sociale")

    if any(m in {6, 12} for m in maisons):
        themes.append("service, fatigue psychique et intériorisation")

    if not themes:
        return "aucun axe dominant clair"

    return " / ".join(themes)

def _get_governed_houses(theme: Dict[str, Any], planet_name: str) -> List[int]:
    """
    Retourne les maisons gouvernées par une planète
    selon le signe sur la cuspide des maisons.
    """

    maisons = theme.get("maisons") or {}
    if not isinstance(maisons, dict):
        return []

    governed = []

    for maison_num, maison_data in maisons.items():

        if not isinstance(maison_data, dict):
            continue

        signe = maison_data.get("signe")
        if not signe:
            continue

        ruler = SIGN_RULERS.get(str(signe))

        if ruler == planet_name:
            try:
                maison_index = int(
                    str(maison_num)
                    .replace("maison_", "")
                    .replace("Maison_", "")
                    .replace("maison", "")
                    .replace("Maison", "")
                    .strip()
                )
                governed.append(maison_index)
            except (ValueError, TypeError):
                pass

    return sorted(governed)

def _render_planet_retro(r: Dict[str, Any]) -> List[str]:
    """Rendu complet d'une planète rétrograde (signification + maison + signe)."""
    lines: List[str] = []

    pl = r["name"]
    signe = r.get("signe")
    maison = _house_int(r.get("maison"))
    is_slow = bool(r.get("is_slow"))
    impact_level = r.get("impact_level", "moyen")
    governed_houses = r.get("governed_houses", [])


    extra = []
    if signe:
        extra.append(str(signe))
    if maison is not None:
        extra.append(f"Maison {maison}")

    marker = " (générationnel)" if is_slow else ""
    extra_txt = f" ({' — '.join(extra)})" if extra else ""

    lines.append(f"### {pl} rétrograde{marker}{extra_txt}")
    lines.append(f"[META: impact={impact_level}]")
    if governed_houses:
        lines.append(f"[META: maisons_gouvernees={', '.join(map(str, governed_houses))}]")
    lines.append("")

    # 1) SIGNIFICATION
    signif = get_retro_interp(pl, "signification", "")
    if signif.get("vie_actuelle"):
        lines.append("#### Signification karmique")
        lines.append(signif["vie_actuelle"].strip())
        lines.append("")

    # 2) MAISON
    if maison is not None:
        maison_data = get_retro_interp(pl, "Maison", str(maison))
        if maison_data.get("vie_actuelle") or maison_data.get("vie_anterieure"):
            lines.append(f"#### En Maison {maison}")

            if maison_data.get("vie_actuelle"):
                lines.append("**Vie actuelle :**")
                lines.append(maison_data["vie_actuelle"].strip())
                lines.append("")

            if maison_data.get("vie_anterieure"):
                lines.append("**Vie antérieure :**")
                lines.append(maison_data["vie_anterieure"].strip())
                lines.append("")

    # 3) SIGNE
    if signe:
        signe_data = get_retro_interp(pl, "Signe", _slug(signe))
        if signe_data.get("vie_actuelle") or signe_data.get("vie_anterieure"):
            lines.append(f"#### En {signe}")

            if signe_data.get("vie_actuelle"):
                lines.append("**Vie actuelle :**")
                lines.append(signe_data["vie_actuelle"].strip())
                lines.append("")

            if signe_data.get("vie_anterieure"):
                lines.append("**Vie antérieure :**")
                lines.append(signe_data["vie_anterieure"].strip())
                lines.append("")

    return lines


def build_block_retrogrades(
    theme: Dict[str, Any],
    score: Dict[str, Any],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Bloc Planètes rétrogrades (karmique) :
    - Signification globale par planète
    - Maison + Signe (vie actuelle / vie antérieure)
    - Séparation personnelles vs lentes
    """
    retro = _collect_retrogrades(theme)

    # Pas de rétrogrades -> pas de bloc (le Engine doit skip)
    if not retro:
        return None

    intro = (
        "Les planètes rétrogrades signalent une énergie intériorisée, "
        "un apprentissage qui demande retour sur soi, révision et maturation. "
        "En karmique, elles pointent des mémoires anciennes à conscientiser "
        "pour éviter de les rejouer en pilote automatique."
    )

    personal = [r for r in retro if r.get("is_personal")]
    slow = [r for r in retro if r.get("is_slow")]
    social = [
        r for r in retro
        if r["name"] in {"Jupiter", "Saturne"}
    ]
    axe_commun = _build_retro_axis(retro)
    priority_planets = [r["name"] for r in retro if r.get("impact_level") == "fort"]

    lines: List[str] = []

    if personal:
        lines.append("## Planètes personnelles rétrogrades")
        lines.append("")
        lines.append(
            "Ces rétrogrades sont plus rares et signalent un karma personnel actif "
            "(lecture plus directe et plus intime)."
        )
        lines.append("")
        for r in personal:
            lines.extend(_render_planet_retro(r))
            lines.append("---")
            lines.append("")

    if social:
        lines.append("## Planètes sociales rétrogrades")
        lines.append("")
        lines.append(
            "Ces rétrogrades concernent la manière de construire sa place, "
            "sa légitimité, son rapport aux règles, à l’expansion et au temps long."
        )
        lines.append("")

        for r in social:
            lines.extend(_render_planet_retro(r))
            lines.append("---")
            lines.append("")

    if slow:
        lines.append("## Planètes lentes rétrogrades (générationnel)")
        lines.append("")
        lines.append(
            "Ces rétrogrades sont fréquentes : elles colorent une génération entière. "
            "L'impact personnel dépend surtout de la maison et des aspects."
        )
        lines.append("")
        for r in slow:
            lines.extend(_render_planet_retro(r))
            lines.append("---")
            lines.append("")

    # -------------------------
    # SYNTHÈSE PSYCHOLOGIQUE
    # -------------------------
    profil = []

    if len(personal) >= 2:
        profil.append("plusieurs fonctions personnelles en révision intérieure")
    elif len(personal) == 1:
        profil.append(f"un accent intime sur {personal[0]['name']} rétrograde")

    if len(social) > 0:
        profil.append("une révision du rapport à la légitimité, au temps long et à la construction sociale")

    if len(slow) >= 3:
        profil.append("un profond sentiment de décalage avec sa génération")
    elif len(slow) > 0 and len(personal) == 0:
        profil.append("un karma principalement collectif ou de fond, sans blocage personnel majeur")

    synthese = ""
    if profil:
        synthese = "Résumé de la dynamique rétrograde : Cette configuration indique " + " et ".join(profil) + "."
    
    content_parts = [
        "# Planètes rétrogrades — lecture karmique",
        "",
    ]

    if synthese:
        content_parts.extend([
            "Résumé psychologique pré-calculé :",
            synthese,
            "",
        ])

    content_parts.extend([
        intro,
        "",
        *lines,
    ])

    content = _join(content_parts)

    # 🔥 DEBUG : vérifie ce qui est construit
    logger.debug("build_block_retrogrades: content_len=%s", len(content))
    logger.debug("build_block_retrogrades preview: %s", content[:200])
    
    summary = summarize_chapter(
        chapter_title="Rétrogrades : mémoires en révision",
        chapter_text=content,
        call_llm=(global_ctx or {}).get("call_llm"),
    )
    return {
        "id": "retrogrades",
        "title": "Planètes rétrogrades — ce qui demande maturation",
        "data": {
            "retrogrades": retro,
            "retrogrades_count": len(retro),
            "personal_count": len(personal),
            "slow_count": len(slow),
            "axe_commun": axe_commun,
            "priority_planets": priority_planets,
            "social_count": len(social),
        },
        "content": content,
        "text": content,
        "summary": summary,

    }


def interpret_block_retrogrades_llm(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Callable[[str], str],
    global_ctx: Optional[Dict[str, Any]] = None,
) -> str:

    content = (block.get("content") or "").strip()
    if not content or not call_llm:
        return block.get("content", "")

    theme_brief = (global_ctx or {}).get("theme_brief", "").strip()

    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()

    retro_data = block.get("data") or {}
    retro_count = retro_data.get("retrogrades_count", 0)
    personal_count = retro_data.get("personal_count", 0)
    social_count = retro_data.get("social_count", 0)
    strong_count = personal_count + social_count
    axe_commun = retro_data.get("axe_commun", "")
    priority_planets = retro_data.get("priority_planets", [])
    priority_txt = ", ".join(priority_planets) if priority_planets else "aucune priorité particulière"  

    if personal_count >= 2:
        longueur_txt = "4 paragraphes denses (~400 à 500 mots)"
    elif retro_count >= 4 or strong_count >= 2:
        longueur_txt = "3 paragraphes riches (~350 à 450 mots)"
    else:
        longueur_txt = "2 à 3 paragraphes (~250 à 350 mots)"

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"

    intro_txt = CHAPTER_INTROS.get("retrogrades", "")
    memories = (global_ctx or {}).get("memoires_contextuelles", [])
    memories_txt = "\n".join(memories[-8:]) if memories else "aucune mémoire disponible"
    logger.debug("memories_txt = %s", memories_txt)

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Ta mission : rédiger le chapitre "Rétrogradations"  d'une analyse profonde.

**TON ET STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Style incarné, psychologique, dense, analytique.
- Ton sérieux, avec une légère touche d’ironie possible pour souligner les répétitions, les retards ou le côté "pilote automatique" de la personne.
- Pas d'introduction, pas de prénom. Entre directement dans le vif du sujet par une transition fluide avec ce qui précède.

**OBJECTIF DU CHAPITRE (TERRITOIRE EXCLUSIF)**
Mettre en lumière le décalage de rythme et la maturation intérieure :
- L'énergie psychique qui tourne en circuit fermé, qui est intériorisée, retenue, ou vécue en décalage.
- La frustration d'un "timing" qui semble toujours inadéquat entre l'intention et l'action.
- Le processus de décantation : comment cette apparente lenteur est en réalité une révision karmique nécessaire.
- La répétition compulsive : certaines expériences semblent rejouées plusieurs fois jusqu'à prise de conscience.
- Focus exclusif : Concentre-toi sur le concept de *temps*, de *révision*, de *répétition* et d'*intériorisation*. Laisse les blocages profonds aux Interceptions. Si une rétrogradation tombe en Maison 12, traite-la uniquement sous l’angle du rythme intérieur : retrait prolongé, cycles d’isolement, maturation lente, temps de décantation. N’entre pas dans l’inconscient flou ou les mémoires invisibles déjà traitées ailleurs.
**MÉMOIRE DE RÉDACTION (CE QUI A DÉJÀ ÉTÉ DIT)**
Voici ce qui a déjà été traité et l'angle utilisé :
{memories_txt}

**CONSIGNE ANTI-REDONDANCE IMPÉRATIVE**
- INTERDICTION de ré-expliquer les concepts listés ci-dessus.
- Si une planète rétrograde gouverne un domaine déjà évoqué dans la mémoire, montre comment elle impose une *lenteur*, une *rumination* ou une *réévaluation* constante sur ce sujet, plutôt que de réexpliquer le problème.
- Varie ton vocabulaire : utilise des termes comme décalage, à contretemps, décantation, rumination, maturation lente, révision, circuit fermé, incubation. Évite le mot "blocage" (réservé aux interceptions).

**RÈGLES STRICTES DE RÉDACTION**
- **Fusion narrative absolue :** Ne rédige jamais un paragraphe par planète. Interdiction de commencer un paragraphe par le nom d’une planète ou par une formule du type "Mars rétrograde...", "Jupiter rétrograde...", "Saturne rétrograde...". Les planètes doivent être fondues dans une seule lecture psychologique continue, comme des forces qui se répondent dans un même mécanisme intérieur.
- **Interdiction de structure scolaire :** Ne fais pas "d'abord Mars, puis Jupiter, enfin Saturne". Construis une progression psychologique : tension intérieure → répétition → maturation → issue possible.
- **Hiérarchie de l'impact :** Développe en priorité les planètes listées comme prioritaires. Donne plus de poids psychologique aux planètes personnelles (Mercure, Vénus, Mars). Pour les planètes lentes, reste synthétique sauf si elles sont en maison sensible ou indiquées comme prioritaires.
- **Planètes sociales :** Jupiter et Saturne occupent un niveau intermédiaire. Développe-les si elles sont en maison sensible ou présentes dans les planètes prioritaires ; sinon, une phrase suffit.
- **Maisons gouvernées :** Si une planète rétrograde gouverne une ou plusieurs maisons, utilise ces maisons comme le territoire profond concerné. La maison où se trouve la planète montre où la tension se manifeste ; les maisons gouvernées montrent quels domaines de vie sont entraînés dans la révision karmique.
- **Format brut :** Texte en flux continu uniquement. Zéro titre, zéro liste.
- **Longueur :** {longueur_txt}.

**DONNÉES TECHNIQUES À TRANSFORMER EN PSYCHOLOGIE**
Axe central : {axe_central}
Contexte global : {theme_brief}

Axe psychologique commun détecté :
{axe_commun}

Planètes à développer en priorité :
{priority_txt}

Important :
Les lignes [META: maisons_gouvernees=...] indiquent les maisons gouvernées par la planète rétrograde. Utilise-les pour comprendre le fond du sujet, sans les citer mécaniquement.

Données techniques des rétrogradations : 
{content}

[Début de l'analyse en flux continu :]
""".strip()


    logger.debug("=" * 80)
    logger.debug("PROMPT FINAL ENVOYÉ AU LLM")
    logger.debug("=" * 80)
    logger.debug(prompt)
    logger.debug("=" * 80)

    texte = (call_llm(prompt) or "").strip()

    if intro_txt:
        return f"{intro_txt}\n\n{texte}".strip()

    return texte