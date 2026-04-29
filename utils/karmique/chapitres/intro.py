# utils/karmique/intro.py

from __future__ import annotations
from typing import Any, Dict, List, Callable, Optional
import logging
from utils.karmique.karmique_bdd import get_karmique_interp
from utils.karmique.karmique_anaretic import (
    get_anaretic_interp,
    get_anaretic_sign_interp
)
logger = logging.getLogger(__name__)


def _bdd(astre: str, donnee: str, valeur: Any) -> str:
    if valeur is None:
        return ""
    txt = get_karmique_interp(astre, donnee, str(valeur))
    return txt.strip() if isinstance(txt, str) and txt.strip() else ""


def _safe_join(lines: List[str]) -> str:
    return "\n".join([x for x in lines if isinstance(x, str) and x.strip()]).strip()


def _intro_base_text() -> str:
    return _safe_join([
        "Cette analyse karmique met en lumière les mémoires et automatismes qui influencent tes réactions et tes répétitions de vie.",
        "Elle ne prédit pas : elle éclaire. Le but, c’est de reprendre la main sur ce qui se rejoue en pilote automatique.",
        "",
        "On va commencer par une vue d’ensemble (score, dominante, axe des Nœuds), puis dérouler une analyse détaillée point par point."
    ])


def _score_tagline(label: str) -> str:
    label = (label or "").strip()
    if not label:
        return ""

    mapping = {
        "Valise en Soute": "Ça parle d’un bagage déjà bien rempli : l’enjeu, c’est de trier ce qui sert encore… et ce qui te plombe inutilement.",
        "Expédition Polaire": "Ici, c’est du karma ‘haut niveau’ : ça demande courage, lucidité, et capacité à avancer même sans confort émotionnel.",
        "Valise Cabine": "Bagage visible et gérable : l’évolution passe surtout par des choix conscients et réguliers, pas par des révolutions dramatiques.",
    }
    if label not in mapping:
        logger.warning("Label de score karmique non reconnu dans intro : %s", label)

    return mapping.get(label, "Le score donne une idée de l’intensité du travail intérieur demandé : ni fatalité, ni étiquette — juste un niveau de “matière” à transformer.")

def interpret_intro_karmique(
    block: Dict[str, Any],
    theme: Dict[str, Any],
    score: Dict[str, Any],
    call_llm: Optional[Callable[..., str]] = None,
    global_ctx: Optional[Dict[str, Any]] = None,   # ✅ pour le contexte global plus tard
) -> str:
    """
    Intro = cadre + grandes lignes.
    PAS de Lune ici (elle a son bloc).
    """

    genre_label = (global_ctx or {}).get("genre_label", "homme")
    genre_txt = "une femme" if genre_label == "femme" else "un homme"
    axe_central = (global_ctx or {}).get("axe_karmique_central", "").strip()


    data = block.get("data", {}) or {}
    meta = score.get("meta", {}) or {}

    total = score.get("total")
    label = score.get("label", "—")

    elements = meta.get("dominant_elements") or data.get("dominant_elements") or []
    cuspides = data.get("cuspides", []) or []
    points_29 = data.get("points_29", []) or []

    nn_sign = meta.get("nn_sign")
    ns_sign = meta.get("ns_sign")
    nn_house = meta.get("nn_house")
    ns_house = meta.get("ns_house")

    lines = []
    lines.append(f"Score karmique : {total if total is not None else '—'} — {label}")
    tag = _score_tagline(label)
    if tag:
        lines.append(tag)
    lines.append("")

    if elements:
        dom_txt = " / ".join(elements)
        lines.append(f"Dominante(s) élémentaire(s) : {dom_txt}")
        bdd_dom = _bdd("Karmique", "dominante_elements", elements[0])
        if bdd_dom:
            lines.append(bdd_dom)
        lines.append("")

    if cuspides:
        shown = [c for c in cuspides if c.get("name") in ("Ascendant", "Soleil")][:2]
        if shown:
            lines.append("Entre-deux signes (Ascendant / Soleil) :")
            for c in shown:
                name = c.get("name")
                deg = c.get("deg")
                cur = c.get("current_sign")
                other = c.get("other_sign")
                pos = c.get("position")
                if not (name and cur and other and pos):
                    continue
                direction = f"passage vers {other}" if pos == "fin" else f"héritage de {other}"
                lines.append(f"- {name} ({deg}°) en {cur} : {direction}.")
            lines.append("")

    if nn_sign and ns_sign:
        left = f"{ns_sign}" + (f" (Maison {ns_house})" if ns_house is not None else "")
        right = f"{nn_sign}" + (f" (Maison {nn_house})" if nn_house is not None else "")
        lines.append(f"Axe des Nœuds Lunaires : passage de {left} vers {right}.")
        lines.append("")

    if points_29:
        lines.append("Points sensibles :")

        for p in points_29:
            nom = p.get("name")
            deg = p.get("deg")
            signe = p.get("signe")
            maison = p.get("maison")

            txt = f"- {nom} à {deg}°"
            if signe:
                txt += f" en {signe}"
            if maison is not None:
                txt += f" (Maison {maison})"

            # 🔥 interprétation planète
            interp_planete = get_anaretic_interp(nom)

            # 🔥 interprétation signe
            interp_signe = get_anaretic_sign_interp(signe)

            # 🔥 combinaison intelligente
            parts = []
            if interp_planete:
                parts.append(interp_planete)
            if interp_signe:
                parts.append(interp_signe)

            if parts:
                txt += " : " + ", ".join(parts)

            lines.append(txt)

        lines.append("")

    facts = _safe_join(lines)

    if not call_llm:
        return block.get("content") or facts

    # ✅ Contexte global (si tu l'as)
    # ctx_json = ""
    # if isinstance(global_ctx, dict) and global_ctx:
    #     ctx_json = _safe_join([
    #         "Contexte global (JSON) :",
    #         str(global_ctx)
    #     ])

    ctx_lines = []

    if isinstance(global_ctx, dict):

        # 🧠 Résumé global du thème (si tu l’as)
        theme_brief = (global_ctx.get("theme_brief") or "").strip()
        if theme_brief:
            ctx_lines.append(f"Résumé global du thème : {theme_brief}")

        # 🔮 Contexte karmique global (si tu l’as)
        karmic_context = (global_ctx.get("karmic_context") or "").strip()
        if karmic_context:
            ctx_lines.append(f"Contexte karmique : {karmic_context}")

    ctx_text = _safe_join(ctx_lines)

    prompt = f"""
Tu es astrologue karmique à l'approche psychologique Jungienne, directe avec une pointe de mordant.
Tu rédiges l'introduction d'une analyse karmique complète.

**STYLE**
- Tutoiement direct {genre_txt}.
- Adresse toi directement à la personne
- INTERDIT : "Dans le thème de (prénom)...Le soleil pousse (Prénom)"
- Phrases courtes à moyennes. Concret avant abstrait. Pas de métaphore décorative.
- Une phrase = une idée.
- Grain visé :
  "Il y a une configuration dans ton thème qui revient partout. Pas un défaut. Une logique."
  "Ce thème ne parle pas de destin. Il parle de ce que tu rejoues sans t'en rendre compte."

**OBJECTIF**
Poser l'ambiance karmique globale et l'axe central — sans tout révéler.
Introduire les tensions principales pour donner envie de lire la suite.
Ne pas résoudre, ne pas expliquer : poser.

**RÈGLES**
- Ne mentionne jamais la Lune ni les besoins de sécurité lunaire.
- Aucun inventaire de planètes. Tout doit être narratif.
- Si un degré 29° est présent dans les données, traite-le comme un point de bascule.
- Flux continu, 2-3 paragraphes courts, 200-250 mots.
- Dernière phrase : une transition sobre vers la suite — pas de "plongeons ensemble".

**DONNÉES**
Axe karmique : {axe_central}
Contexte global : {ctx_text}
Faits et extraits base de données : {facts}

[Introduction en flux continu :]
""".strip()
    
    logger.debug(
        "INTRO KARMIQUE facts envoyés au LLM | length=%s | preview=%r",
        len(facts),
        facts[:1200],
    )

    logger.debug(
        "INTRO KARMIQUE prompt final | length=%s | preview=%r",
        len(prompt),
        prompt[:1800],
    )

    txt = (call_llm(prompt) or "").strip()
    return txt if txt else facts