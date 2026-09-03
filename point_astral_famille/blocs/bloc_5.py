# blocs/bloc_5.py
from textwrap import dedent
import logging

#from utils.llm_client import ask_llm
from point_astral_famille.llm_client import ask_llm
from point_astral_famille.selection_donnees import (
    extraire_noeuds_pour_bloc5,
)
from point_astral_famille.extracteurs import extract_points_forts_from_placements


logger = logging.getLogger(__name__)

def _nettoyer_placements_bloc5(placements_str: str) -> str:
    """
    Retire du Bloc 5 les points astrologiques qui ne doivent pas
    participer à la synthèse globale.
    """
    exclusions = (
        "point d’illumination",
        "point d'illumination",
        "junon",
        "juno",
    )

    lignes_conservees = []

    for ligne in placements_str.splitlines():
        ligne_normalisee = ligne.lower().strip()

        if any(
            exclusion in ligne_normalisee
            for exclusion in exclusions
        ):
            continue

        lignes_conservees.append(ligne)

    return "\n".join(lignes_conservees).strip()


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

def _formater_memoires_precedentes(
    memoires_precedentes: dict,
) -> str:
    """
    Regroupe les résumés réellement développés
    dans les Blocs 1, 2 et 3 pour les transmettre au Bloc 5.
    """
    if not memoires_precedentes:
        return ""

    sections = []

    noms_blocs = {
        "bloc_1": "Personnalité et identité",
        "bloc_2_identite": "Monde émotionnel et sécurité intérieure",
        "bloc_2_famille": "Racines et dynamique familiale",
        "bloc_3": "Axes majeurs",
    }

    for cle_bloc in (
        "bloc_1",
        "bloc_2_identite",
        "bloc_2_famille",
        "bloc_3",
    ):
        resume = memoires_precedentes.get(cle_bloc)

        if not resume:
            continue

        resume = str(resume).strip()

        if not resume:
            continue

        titre = noms_blocs.get(cle_bloc, cle_bloc)

        sections.append(
            f"### {titre}\n{resume}"
        )

    return "\n\n".join(sections).strip()

def _formater_aspects_bloc5(theme: dict) -> str:
    """
    Récupère les aspects déjà calculés dans le thème
    et retire les points secondaires inutiles à la synthèse.
    """
    aspects = theme.get("aspects") or []

    if not aspects:
        return "Aucun aspect majeur disponible."

    exclusions = (
        "point d’illumination",
        "point d'illumination",
        "part de fortune",
        "vertex",
        "junon",
        "chiron",
        "lune noire",
        "lilith",
    )

    lignes = []

    for aspect in aspects:
        if isinstance(aspect, dict):
            planete1 = (
                aspect.get("planete1")
                or aspect.get("p1")
                or ""
            )
            nom_aspect = aspect.get("aspect") or ""
            planete2 = (
                aspect.get("planete2")
                or aspect.get("p2")
                or ""
            )
            orbe = aspect.get("orbe")

            if not planete1 or not nom_aspect or not planete2:
                continue

            texte = f"{planete1} {nom_aspect} {planete2}"

            if orbe not in (None, ""):
                texte += f" (orbe {orbe}°)"
        else:
            texte = str(aspect).strip()

        if not texte:
            continue

        texte_normalise = texte.lower()

        if any(
            exclusion in texte_normalise
            for exclusion in exclusions
        ):
            continue

        lignes.append(f"- {texte}")
   

    if not lignes:
        return "Aucun aspect majeur disponible."

    return "\n".join(lignes)

def generer_bloc_5(
    contexte: dict,
    memoires_precedentes: dict | None = None,
    max_tokens: int = 1300,
) -> str:
    """
    Bloc 5 – Synthèse globale.
    Condense le thème en 2–3 axes directeurs + direction de vie.
    """
    memoires_precedentes = memoires_precedentes or {}

    memoire_bloc_1 = memoires_precedentes.get("bloc_1", "")
    memoire_bloc_2_identite = memoires_precedentes.get(
        "bloc_2_identite",
        "",
    )
    memoire_bloc_2_famille = memoires_precedentes.get(
        "bloc_2_famille",
        "",
    )
    memoire_bloc_3 = memoires_precedentes.get("bloc_3", "")

    logger.debug(
        (
            "Bloc 5: mémoires reçues — "
            "B1=%s | B2 identité=%s | B2 famille=%s | B3=%s"
        ),
        bool(memoire_bloc_1),
        bool(memoire_bloc_2_identite),
        bool(memoire_bloc_2_famille),
        bool(memoire_bloc_3),
    )

    memoires_txt = _formater_memoires_precedentes(
        memoires_precedentes
    )

    logger.debug(
        "Bloc 5: mémoire structurée formatée=%s caractères",
        len(memoires_txt),
    )


    # 1) Données de base (même socle que les autres blocs)
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    ).strip()

    placements_str = _nettoyer_placements_bloc5(
        placements_str
    )

    if len(placements_str) < 50:
        return "❌ Données insuffisantes pour produire la synthèse."

    # CORRECTION: Extraire les points forts directement de placements_str
    points_forts = extract_points_forts_from_placements(placements_str)
    
    # Fallback si pas de points forts extraits
    if not points_forts:
        axes_majeurs_fallback = (contexte.get("axes_majeurs_str") or "").strip()
        if axes_majeurs_fallback:
            points_forts = axes_majeurs_fallback
        else:
            points_forts = "Non précisé ici"

    if isinstance(points_forts, (list, tuple)):
        points_forts = "\n".join(
            str(point).strip()
            for point in points_forts
            if str(point).strip()
        )
    else:
        points_forts = str(points_forts or "").strip()

    if not points_forts:
        points_forts = "Non précisé ici"

    logger.debug("Bloc 5: points_forts chars=%s", len(points_forts))

    genre_label  = contexte.get("genre", "femme")

    genre_brut = str(
        contexte.get("genre") or "femme"
    ).strip().casefold()

    genre_label = (
        "femme"
        if genre_brut in {"femme", "female", "f", "woman"}
        else "homme"
    )

    # # 2) RAG (digest déjà préparé par l'orchestrateur ; sinon compacte un peu)
    # rag_snippets = (contexte.get("rag_snippets") or "").strip()

    # if rag_snippets:
    #     lines, seen = [], set()

    #     for ln in rag_snippets.splitlines():
    #         t = ln.strip()
    #         if not t:
    #             continue

    #         k = t.lower()
    #         if k not in seen:
    #             seen.add(k)
    #             lines.append(t)

    #     rag_lines = []
    #     taille = 0

    #     for ligne in lines:
    #         cout = len(ligne) + 1  # + saut de ligne

    #         if taille + cout > 2500:
    #             break

    #         rag_lines.append(ligne)
    #         taille += cout

    #     rag_short = "\n".join(rag_lines)

    # else:
    #     rag_short = ""

    # Construire le thème à partir du contexte
    # theme = contexte.get("theme")
    # conjonctions = analyser_conjonctions(theme)
    # stelliums = analyser_stelliums(theme)
    # configurations = analyser_configurations_majeures(theme)

    # configurations_txt = formater_configurations_majeures(
    #     conjonctions,
    #     stelliums,
    #     configurations,
    # )
    # if not theme:
    #     return "❌ Thème astrologique indisponible."

    # Construire le thème à partir du contexte
    theme = contexte.get("theme")

    if not theme:
        return "❌ Thème astrologique indisponible."

    configurations_txt = (
        contexte.get("configurations_majeures_str")
        or "Aucune configuration majeure détectée."
    ).strip()

    #aspects_txt = _formater_aspects_bloc5(theme)
    
    # base_interpretations = charger_base_theme(theme)
    # # logger.warning(
    # #     "DEBUG INTERCEPTION BLOC 5 — Soleil placement=%s | interceptions=%s | base Soleil=%s",
    # #     theme.get("planetes", {}).get("Soleil"),
    # #     theme.get("interceptions"),
    # #     base_interpretations.get("Soleil"),
    # # )
    # planetes_synthese = [
    #     "Soleil",
    #     "Lune",
    #     "Mercure",
    #     "Vénus",
    #     "Mars",
    #     "Jupiter",
    #     "Saturne",
    #     "Uranus",
    #     "Neptune",
    #     "Pluton",
    # ]

    # morceaux = []

    # for p in planetes_synthese:

    #     txt = formater_interpretation_planete_bdd(
    #         base_interpretations,
    #         p,
    #         colonnes=["INTERPRETATION"],
    #     )

    #     if txt:
    #         morceaux.append(txt)

    #     txt = formater_interpretation_etat_bdd(
    #         base_interpretations,
    #         p,
    #         "interception",
    #         colonnes=["INTERPRETATION"],
    #     )

    #     if txt:
    #         morceaux.append(txt)

    #     retrograde_pertinente = (
    #         p not in {"Uranus", "Neptune", "Pluton"}
    #         or retrogradation_lente_pertinente(
    #             theme,
    #             p,
    #             maisons_cibles={1, 4, 7, 10},
    #             planetes_personnelles={
    #                 "Soleil",
    #                 "Lune",
    #                 "Mercure",
    #                 "Vénus",
    #                 "Mars",
    #             },
    #         )
    #     )

    #     if retrograde_pertinente:
    #         txt = formater_interpretation_etat_bdd(
    #             base_interpretations,
    #             p,
    #             "retrograde",
    #             colonnes=["INTERPRETATION"],
    #         )

    #         if txt:
    #             morceaux.append(txt)

    # bdd_bloc = "\n\n".join(morceaux).strip()

    # if not bdd_bloc:
    #     bdd_bloc = "Aucune donnée BDD disponible."

    logger.debug("Bloc 5: keys theme=%s", list(theme.keys())[:12])

    noeuds_txt = _section_noeuds_lunaires_for_prompt(theme, max_orbe=5.0)
    logger.debug("Bloc 5: noeuds_txt chars=%s", len(noeuds_txt))

    
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
    Tu ne parles pas *de* la personne, tu lui parles *directement* en la tutoyant. 

    {genre_txt}

    Section 5 : Synthèse

    <analyses_precedentes>
    {memoires_txt}
    </analyses_precedentes>

    <indices_de_verification>
    <configurations_majeures>
    {configurations_txt}
    </configurations_majeures>

    <points_forts_du_theme>
    {points_forts}
    </points_forts_du_theme>

    <noeuds_lunaires>
    {noeuds_txt}
    </noeuds_lunaires>
    </indices_de_verification>

Les analyses détaillées ont déjà été réalisées. Elles sont résumées dans
<analyses_precedentes>. Relie les mécanismes déjà développés sans résumer les
sections l'une après l'autre et sans produire une nouvelle analyse astrologique.
Commence directement par le texte, sans écrire de titre.

Organise impérativement le texte autour de cette progression :

1. Identifie une seule contradiction centrale qui organise le fonctionnement
   de la personne. Ne présente pas une liste de fils rouges.

2. Montre comment cette contradiction relie son identité, son fonctionnement
   émotionnel, son histoire familiale et ses dynamiques majeures, sans reprendre
   séparément chaque section du rapport.

3. Décris le mécanisme psychologique principal qui en découle, ce qu'il cherche
   à protéger et les tensions qu'il peut produire aujourd'hui.

4. Montre la ressource réelle déjà présente dans le thème qui nuance ou soutient
   ce fonctionnement. Ne produis pas une liste de qualités.

5. Intègre les Nœuds lunaires comme direction d'évolution, sans refaire une
   analyse karmique, puis termine par une conclusion qui rassemble l'essentiel
   du portrait psychologique.

Les configurations et points forts servent uniquement à vérifier et hiérarchiser
ce mécanisme. Ils ne doivent jamais devenir de nouveaux paragraphes d’analyse.

Règles générales:

- Écris entre 600 et 800 mots, en 4 ou 5 paragraphes continus.
- Ne parcours jamais les blocs précédents dans leur ordre.
- Ne résume pas séparément l’identité, les émotions, la famille et les axes.
- Utilise au maximum quatre références astrologiques explicites dans tout
  le texte. Ne mentionne jamais les orbes.
- Ne répète aucune interprétation de placement déjà développée.
- Ne décris pas à nouveau la personnalité supposée des parents. Utilise
  uniquement les mécanismes psychologiques déjà établis dans les analyses.
- Une idée doit être soutenue par les analyses précédentes. Les configurations
  et les points forts servent uniquement à la vérifier et à la hiérarchiser,
  jamais à créer un nouvel axe.
- Évoque les Nœuds lunaires en utilisant les termes Nœud Nord (Rahu)
        et Nœud Sud (Ketu). Présente-les comme une direction d’évolution :
        les automatismes ou acquis symbolisés par Ketu et les qualités que Rahu
        invite progressivement à développer. Fais le lien avec le mécanisme central
mis en évidence
- Les repères de psychologie jungienne sont autorisés uniquement s’ils
  éclairent directement la boucle centrale. Pas de jargon décoratif.
- Ne transforme pas la conclusion en mode d'emploi, en programme d'action ou
  en séance de coaching. Ne termine pas par une série de questions.
- Si l’Analyse Karmique est pertinente, évoque-la en une seule phrase, sans
  formulation publicitaire.
- Pas de titres, pas de listes et aucune syntaxe markdown dans le texte final.
- Parle directement à la personne en la tutoyant, avec lucidité, sans flatterie.

    """)

    logger.debug(
        "Bloc 5: placements=%s chars | prompt=%s chars",
        len(placements_str),
        len(prompt),
    )

    logger.info("========== DEBUG BLOC 5 : DÉBUT ==========")

    logger.info(
        "Bloc 5 mémoires : B1=%s caractères | B2 identité=%s | B2 famille=%s | B3=%s",
        len(memoire_bloc_1),
        len(memoire_bloc_2_identite),
        len(memoire_bloc_2_famille),
        len(memoire_bloc_3),
    )

    logger.info(
        "Bloc 5 données : placements=%s caractères | points_forts=%s",
        len(placements_str),
        len(points_forts),
    )

    logger.debug(
        "\n===== BLOC 5 — MÉMOIRE BLOC 1 =====\n%s",
        memoire_bloc_1 or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — MÉMOIRE BLOC 2 IDENTITÉ =====\n%s",
        memoire_bloc_2_identite or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — MÉMOIRE BLOC 2 FAMILLE =====\n%s",
        memoire_bloc_2_famille or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — MÉMOIRE BLOC 3 =====\n%s",
        memoire_bloc_3 or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — POINTS FORTS =====\n%s",
        points_forts or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — PLACEMENTS NETTOYÉS =====\n%s",
        placements_str or "[VIDE]",
    )

    logger.debug(
        "\n===== BLOC 5 — PROMPT COMPLET ENVOYÉ AU LLM =====\n%s",
        prompt,
    )

    logger.debug("========== DEBUG BLOC 5 : ENVOI LLM ==========")

    try:
        resultat = ask_llm(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.60,
        )

        if not resultat or len(resultat.strip()) < 80:
            raise ValueError("Réponse LLM trop courte")

        resultat = resultat.strip()

        logger.debug(
            "\n===== BLOC 5 — RÉPONSE DU LLM =====\n%s",
            resultat,
        )

        logger.info("========== DEBUG BLOC 5 : FIN ==========")

        return resultat

    except Exception:
        logger.exception("Bloc 5 : erreur LLM")

        return (
            "Synthèse indisponible pour le moment.\n\n"
            f"Principaux axes identifiés :\n{points_forts}"
        )
