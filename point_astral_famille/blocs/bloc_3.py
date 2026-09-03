# blocs/bloc_3.py
from textwrap import dedent
from typing import Dict, Any
import logging
import re

#from utils.llm_client import ask_llm
from point_astral_famille.llm_client import ask_llm
from point_astral_famille.selection_donnees import _extraire_axes_interceptes
from point_astral_famille.extracteurs import extract_points_forts_from_placements
from point_astral_famille.database import rechercher_interpretation_aspect
from point_astral_famille.configurations_astrologiques import (
    annoter_aspects_appartenant_aux_configurations,
)

logger = logging.getLogger(__name__)

def extraire_resume_developpe(texte):
    match = re.search(
        r"<resume_developpe>\s*(.*?)\s*</resume_developpe>",
        texte,
        re.DOTALL,
    )

    resume = match.group(1).strip() if match else ""

    texte_sans_resume = re.sub(
        r"<resume_developpe>.*?</resume_developpe>",
        "",
        texte,
        flags=re.DOTALL,
    ).strip()

    return texte_sans_resume, resume

POINTS_EXCLUS_BLOC_3 = {
    "Junon",
    "Juno",
    "Part de Fortune",
    "Part de fortune",
    "Point d'illumination",
    "Point illumination",
    "Point d’illumination",
    "Point d’Illumination",
    "Chiron",
}

SYSTEM_PROMPT_BLOC_3 = dedent("""
<role>
Tu es une astrologue expérimentée : cash, lucide, directe, parfois sarcastique.
Tu t'adresses TOUJOURS directement à la personne en "tu".
Tu ne parles jamais d'elle à la troisième personne.
Le genre sert uniquement aux accords grammaticaux.
Tu ne flattes jamais, tu ne fais pas de poésie, pas de coaching.
</role>

<mission>
Ce bloc n'est PAS une fiche par placement. C'est un portrait psychologique unique.
Les données fournies par l'utilisateur sont des preuves, jamais un plan de texte.
Interdiction absolue qu'un paragraphe ne parle que d'un seul élément astrologique
(une planète, un aspect, une dignité, un amas isolé).
</mission>

<regles_absolues>
- N'invente aucun placement, aucun aspect, aucune maison.
- Les placements complets servent uniquement à vérifier les faits astrologiques.
  Ils ne constituent pas des axes d'analyse supplémentaires.
- Construis le portrait uniquement à partir des indices astrologiques principaux
  et des interprétations BDD fournies.
- Ne développe jamais un placement ou un aspect absent des indices principaux,
  même s'il apparaît dans les placements complets.
- N'invente aucun comportement qui ne découle pas clairement des indices fournis.
- Soleil, Lune, Ascendant : jamais analysés pour eux-mêmes, seulement si leur aspect
  figure explicitement dans les indices fournis.
- N'analyse jamais l'enfance, les parents, la famille.
- Aucun coaching, aucun conseil, aucune injonction.
- Écris toujours en "tu". Le texte doit parler À la personne, jamais DE la personne. 
- N’invente jamais d’aspect, de conjonction, d’amas ou de lien entre des planètes.
- Si une configuration n’est pas écrite explicitement dans les indices astrologiques principaux, ne la mentionne pas.
</regles_absolues>

<methode>
1. Lorsqu’une configuration majeure est fournie, interprète-la comme une
   structure psychologique globale avant ses aspects constitutifs. Ne répète
   jamais séparément un aspect déjà expliqué par cette configuration.
   Regroupe ensuite les autres indices qui parlent du même mécanisme psychologique.
2. Dégage 3 à 4 dynamiques maximum.
3. Chaque paragraphe croise au moins deux indices astrologiques quand c'est possible.
4. Chaque paragraphe contient un comportement concret observable.
5. Les placements servent à justifier, jamais à organiser le texte.
6. N'utilise JAMAIS de syntaxe markdown (pas de **gras**, pas de *italique*, pas de #titres). Texte brut uniquement.

</methode>

<style>
Phrases courtes. Ton direct. Pas de poésie. Pas de développement personnel.
Remplace les adjectifs vagues par des situations concrètes.
</style>

<format_de_sortie>
Réponds exclusivement avec les deux blocs suivants, dans cet ordre :

<texte_final>
4 à 5 paragraphes, texte continu, pas de titres, pas de liste, pas de conclusion.
</texte_final>

<resume_developpe>
2 à 3 phrases courtes conformes aux instructions de mémoire interne.
</resume_developpe>
</format_de_sortie>

IMPORTANT — MÉMOIRE INTERNE

À la toute fin de ta réponse, ajoute exactement ce bloc :

<resume_developpe>
...
</resume_developpe>

Dans cette balise, écris 2 à 3 phrases courtes résumant uniquement ce que tu as réellement développé dans ton analyse.

- le fonctionnement principal décrit ;
- la tension ou le paradoxe principal mis en évidence.

Ne cite aucun élément que tu n’as pas réellement développé dans le texte.
N’ajoute aucun conseil.
""")

def _extraire_texte_final(brut: str) -> str:
    """
    Extrait uniquement le contenu situé entre
    <texte_final> ... </texte_final>.
    Si les balises sont absentes, renvoie le texte brut.
    """
    m = re.search(
        r"<texte_final>(.*?)</texte_final>",
        brut or "",
        re.DOTALL | re.IGNORECASE,
    )
    return (m.group(1) if m else brut or "").strip()

def _contient_point_exclu(*noms: str) -> bool:
    """
    Détecte un point exclu même lorsqu'il apparaît dans une phrase complète,
    par exemple : "Chiron en Bélier — Maison 3".
    """
    exclus_normalises = {
        str(point)
        .replace("’", "'")
        .strip()
        .casefold()
        for point in POINTS_EXCLUS_BLOC_3
    }

    for nom in noms:
        texte = (
            str(nom or "")
            .replace("’", "'")
            .strip()
            .casefold()
        )

        if any(point in texte for point in exclus_normalises):
            return True

    return False

def _sanitize(txt: str) -> str:
    return (txt or "").strip()


def _dedupe_lines(text: str) -> str:
    seen = set()
    out = []

    for ln in (text or "").splitlines():
        k = ln.strip().lower()

        if not k:
            continue

        # Une annotation identique peut appartenir à plusieurs aspects.
        # On la déduplique donc avec la ligne précédente,
        # et non uniquement selon son propre texte.
        if k.startswith("[fait partie de "):
            ligne_precedente = (
                out[-1].strip().lower()
                if out
                else ""
            )

            cle_dedoublonnage = (
                ligne_precedente,
                k,
            )
        else:
            cle_dedoublonnage = k

        if cle_dedoublonnage in seen:
            continue

        seen.add(cle_dedoublonnage)
        out.append(ln)

    return "\n".join(out)


def _as_text(lines_or_text) -> str:
    """Normalise points_forts/axes en texte multi-lignes."""
    if not lines_or_text:
        return ""
    if isinstance(lines_or_text, list):
        return "\n".join(str(x).strip() for x in lines_or_text if str(x).strip())
        
    return str(lines_or_text).strip()

def _orbe(a) -> float:
    try:
        return float(str(a.get("orbe", 99)).replace(",", "."))
    except Exception:
        return 99.0

def _plafonner_axes(text: str, max_lignes: int = 12) -> str:
    """
    Limite le nombre de lignes d'indices envoyées au prompt,
    en conservant les annotations [fait partie de...] attachées
    à la ligne qui les précède.
    """
    lignes = (text or "").splitlines()

    resultat = []
    compte_axes = 0

    for ligne in lignes:
        est_annotation = (
            ligne.strip().startswith("[fait partie de ")
        )

        if est_annotation:
            if resultat:
                resultat.append(ligne)
            continue

        if compte_axes >= max_lignes:
            break

        resultat.append(ligne)
        compte_axes += 1

    return "\n".join(resultat)

def _separer_par_categorie(texte: str) -> tuple[list[str], list[str]]:
    """
    Sépare les lignes en deux catégories :
    - aspects astrologiques
    - placements / dignités / maisons angulaires / dominantes...
    """

    ASPECTS = (
        "conjonction",
        "carré",
        "carre",
        "opposition",
        "trigone",
        "sextile",
    )

    aspects = []
    placements = []

    for ligne in texte.splitlines():
        ligne = ligne.strip()

        if not ligne:
            continue

        if any(mot in ligne.lower() for mot in ASPECTS):
            aspects.append(ligne)
        else:
            placements.append(ligne)

    return aspects, placements


def build_aspects_identite_bdd(theme: Dict[str, Any], axes_filtrees: str = "") -> str:
    """
    Récupère les aspects forts utiles au Bloc 3
    et cherche leur interprétation IDENTITE dans la BDD.
    Fallback automatique sur INTERPRETATION via database.py.
    """
    aspects = theme.get("aspects", []) or []
    # axes_items = axes_items or []
    # axes_txt = "\n".join(str(x) for x in axes_items).lower()
    axes_txt = _as_text(axes_filtrees).lower()

    aspects_retenus = []
    seen = set()

    for a in aspects:
        aspect = (a.get("aspect") or "").strip()
        p1 = (a.get("planete1") or a.get("p1") or "").strip()
        p2 = (a.get("planete2") or a.get("p2") or "").strip()

        libelle1 = f"{p1} {aspect} {p2}".lower()
        libelle2 = f"{p2} {aspect} {p1}".lower()

        if libelle1 not in axes_txt and libelle2 not in axes_txt:
            continue

        if aspect not in {"Conjonction", "Carré", "Opposition"}:
            continue

        if _orbe(a) > 5:
            continue

        if not p1 or not p2:
            continue

        if _contient_point_exclu(p1, p2):
            continue
        cle = (frozenset([p1, p2]), aspect)

        if cle in seen:
            continue

        seen.add(cle)

        interpretation = rechercher_interpretation_aspect(
            p1,
            aspect,
            p2,
            colonne="INTERPRETATION",
        )

        if interpretation:
            aspects_retenus.append(
                f"{p1} {aspect} {p2} (orbe {a.get('orbe')}°)\n"
                f"- Interprétation identité : {interpretation}"
            )

    return "\n\n".join(aspects_retenus) or "—"

def generer_bloc_3(contexte: Dict[str, Any], max_tokens: int = 1500) -> str:

    configurations_majeures = (
        contexte.get("configurations_majeures")
        or []
    )

    configurations_majeures_str = (
        contexte.get("configurations_majeures_str")
        or ""
    )

    logger.info(
        "BLOC 3 : %s configuration(s) majeure(s) reçue(s)",
        len(configurations_majeures),
    )

    # print("\n===== DEBUG CONTEXTE BLOC 3 =====")
    # print("Clés disponibles :", sorted(contexte.keys()))
    # print("axes_majeurs_input :", contexte.get("axes_majeurs_input"))
    # print("axes_items :", contexte.get("axes_items"))
    # print("configurations_majeures :", configurations_majeures)
    # print("configurations_majeures_str :", configurations_majeures_str)
    # print("points_forts :", contexte.get("points_forts"))
    # print("points_forts_str :", contexte.get("points_forts_str"))
    # print("amas_signes :", contexte.get("amas_signes"))
    # print("amas_maisons :", contexte.get("amas_maisons"))
    # print("theme keys :", (contexte.get("theme") or {}).keys())
    # print("===== FIN DEBUG CONTEXTE BLOC 3 =====\n")

    # 1) Données de base
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    ).strip()

    # Extraire les points forts du blob de placements

    # Extraire les points forts du blob de placements
    points_forts = extract_points_forts_from_placements(placements_str)
    points_forts = "\n".join(
        ligne for ligne in _as_text(points_forts).splitlines()
        if not _contient_point_exclu(ligne)
    )

    if not points_forts:
        theme = contexte.get("theme") or contexte.get("data_theme") or {}

        points_forts = _as_text(
            contexte.get("points_forts")
            or contexte.get("points_forts_str")
            or theme.get("points_forts")
        )

        points_forts = "\n".join(
            ligne for ligne in _as_text(points_forts).splitlines()
            if not _contient_point_exclu(ligne)
        )
    if not points_forts:
        points_forts = "Non précisé ici"

    #print("points_forts récupérés :", points_forts)

    if not placements_str or len(placements_str) < 50:
        return "❌ Placements manquants — analyse impossible pour le Bloc 3."
    theme = contexte.get("theme") or contexte.get("data_theme") or {}


    # # ✅ Axes filtrés fournis par l’orchestrateur
    # axes_filtrees = (contexte.get("axes_majeurs_input") or "").strip()

    # configurations_majeures = (
    #     contexte.get("configurations_majeures")
    #     or []
    # )

    # # Retirer les points secondaires interdits du Bloc 3
    # axes_filtrees = "\n".join(
    #     ligne
    #     for ligne in axes_filtrees.splitlines()
    #     if not _contient_point_exclu(ligne)
    # )

    # # Annoter les aspects déjà présents dans les axes
    # # lorsqu’ils appartiennent à une configuration majeure.
    # axes_filtrees = annoter_aspects_appartenant_aux_configurations(
    #     axes_filtrees,
    #     configurations_majeures,
    # )

    # # ✅ Conjonctions au MC (optionnel mais recommandé)
    # conj_mc = (contexte.get("conjonctions_mc") or "").strip()

    # # ➕ Axes interceptés (et planètes contenues dans ces signes)
    # axes_int = _extraire_axes_interceptes(contexte)  # {'signes': [...], 'maisons_par_signe': {...}}
    # signes_int = axes_int.get("signes") or []


    # if signes_int:
    #     extra_lines = []

    #     # 1) L'axe lui-même
    #     extra_lines.append(f"Axe intercepté : {', '.join(signes_int)} — thèmes à débloquer / maturer")

    #     # 2) Planètes contenues dans ces signes interceptés
    #     # On prend des placements occidentaux robustes (selon ce que ton orchestrateur fournit)
    #     occ = (
    #         theme.get("planetes")
    #         or contexte.get("planetes")
    #         or contexte.get("placements_occidentaux")
    #         or contexte.get("placements_occ")
    #         or contexte.get("resultats_tropical")
    #         or {}
    #     )
    #     for pl, d in (occ or {}).items():
    #         if _contient_point_exclu(pl):
    #             continue
    #         if not isinstance(d, dict):
    #             continue
    #         signe = d.get("signe")
    #         maison = d.get("maison")
    #         if signe in signes_int:
    #             maison_txt = f"Maison {maison}" if maison is not None else "Maison ?"
    #             extra_lines.append(f"{pl} intercepté en {signe} ({maison_txt}) — potentiel sous-exprimé à intégrer")

    #     # 3) Ajout au bloc d'axes, avec dédup “doux”
    #     if extra_lines:
    #         axes_filtrees = _dedupe_lines(axes_filtrees + "\n" + "\n".join(extra_lines))

    # # Les configurations calculées par le nouveau moteur
    # # complètent les axes déjà filtrés par l’orchestrateur.
    # if configurations_majeures_str:
    #     axes_filtrees = _dedupe_lines(
    #         (
    #             axes_filtrees
    #             + ("\n" if axes_filtrees else "")
    #             + configurations_majeures_str
    #         ).strip()
    #     )

    # ==========================================================
    # Axes reçus de l'orchestrateur
    # ==========================================================

    axes_historiques = (
        contexte.get("axes_majeurs_input")
        or ""
    ).strip()

    configurations_majeures = (
        contexte.get("configurations_majeures")
        or []
    )

    bloc_figures = configurations_majeures_str.strip()

    # Retirer les points secondaires
    axes_historiques = "\n".join(
        ligne
        for ligne in axes_historiques.splitlines()
        if not _contient_point_exclu(ligne)
    )

    # Ajouter les annotations des configurations
    axes_historiques = annoter_aspects_appartenant_aux_configurations(
        axes_historiques,
        configurations_majeures,
    )

    # Séparer les aspects des placements
    aspects_isoles, placements_simples = _separer_par_categorie(
        axes_historiques
    )

    # Assemblage dans l'ordre souhaité
    sections = []

    # if bloc_figures:
    #     sections.append(bloc_figures)

    # if aspects_isoles:
    #     sections.append("\n".join(aspects_isoles))

    # if placements_simples:
    #     sections.append("\n".join(placements_simples))
    sections = []

    # Séparer les conjonctions des autres configurations
    lignes_figures = []
    lignes_conjonctions = []

    for ligne in bloc_figures.splitlines():
        if ligne.lower().startswith("- conjonction"):
            lignes_conjonctions.append(ligne)
        else:
            lignes_figures.append(ligne)

    # 1) Grandes configurations
    if lignes_figures:
        sections.append("\n".join(lignes_figures))

    # 2) Conjonctions importantes
    if lignes_conjonctions:
        sections.append("\n".join(lignes_conjonctions))

    # 3) Aspects isolés
    if aspects_isoles:
        sections.append("\n".join(aspects_isoles))

    # 4) Placements
    if placements_simples:
        sections.append("\n".join(placements_simples))

    axes_filtrees = "\n".join(sections)

    # ✅ Conjonctions au MC (optionnel mais recommandé)
    conj_mc = (contexte.get("conjonctions_mc") or "").strip()

    # Les conjonctions au MC ne sont ajoutées que si elles n’ont
    # pas déjà été retenues dans les axes ou configurations.
    if conj_mc:
        axes_filtrees = _dedupe_lines(
            (
                axes_filtrees
                + ("\n" if axes_filtrees else "")
                + conj_mc
            ).strip()
        )

    axes_filtrees = _plafonner_axes(
        axes_filtrees,
        max_lignes=12,
    )

    if not axes_filtrees:
        return "❌ Aucun axe ni point fort identifiable pour le Bloc 3."
    
    aspects_identite_bdd = build_aspects_identite_bdd(theme, axes_filtrees)

    # print("\n===== ASPECTS IDENTITE BDD =====")
    # print(aspects_identite_bdd)
    # print("===== FIN ASPECTS IDENTITE BDD =====\n")

    # (RAG, tonalité, genre...)
    tonalite = contexte.get("tonalite", "tu")
    genre_label = contexte.get("genre", "femme")

    # rag_snippets = (contexte.get("rag_snippets") or "").strip()
    # if rag_snippets:
    #     lines, seen = [], set()
    #     for ln in rag_snippets.splitlines():
    #         t = ln.strip()
    #         if t and t.lower() not in seen:
    #             seen.add(t.lower()); lines.append(t)
    #     rag_short = "\n".join(lines)[:1500]
    # else:
    #     rag_short = ""

    apercu_bloc_1 = (contexte.get("apercu_bloc_1") or "").strip()
    apercu_bloc_2 = (contexte.get("apercu_bloc_2") or "").strip()

    genre_txt = (
        "Accords grammaticaux : féminin. Adresse-toi toujours à la personne en « tu »."
        if genre_label == "femme"
        else
        "Accords grammaticaux : masculin. Adresse-toi toujours à la personne en « tu »."
    )

    user_prompt = dedent(f"""
    {genre_txt}
    SECTION 3 : LES GRANDS AXES DU THÈME

    # Indices astrologiques principaux
    {axes_filtrees}

    # Interprétations BDD
    {aspects_identite_bdd}

    # Éléments déjà développés dans les sections précédentes

    Bloc 1 — Personnalité et identité :
    {apercu_bloc_1 or "—"}

    Bloc 2 — Monde intérieur et dynamique familiale :
    {apercu_bloc_2 or "—"}

    Consigne :
    Ne répète pas les analyses déjà développées dans les Blocs 1 et 2.
    Tu peux les utiliser uniquement pour créer un lien, montrer une continuité
    ou faire apparaître une dynamique nouvelle.

    # Placements complets — vérification uniquement
    {placements_str}

    """)

    # print("\n===== DEBUG BLOC 3 =====")
    # print("POINTS FORTS =", points_forts)
    # print("AXES FILTRÉS =", axes_filtrees)
    # print("===== FIN DEBUG =====\n")

    #return "DEBUG STOP"

    # try:
    #     #resultat = ask_llm(prompt, max_tokens=max_tokens, temperature=0.65)
    #     resultat_brut = ask_llm(
    #         prompt=user_prompt,
    #         system=SYSTEM_PROMPT_BLOC_3,
    #         max_tokens=max_tokens,
    #         temperature=0.7,
    #     )
    #     resultat = _sanitize(_extraire_texte_final(resultat_brut))
    #     resultat = _sanitize(resultat)
    #     logger.debug("Bloc 3: résultat chars=%s", len(resultat))
    #     if len(resultat) < 80:
    #         raise ValueError("Réponse LLM trop courte")
    # except Exception:
    #     logger.exception("Bloc 3: LLM indisponible ou réponse faible, fallback points_forts")
    #     return points_forts

    # return resultat

    try:
        resultat_brut = ask_llm(
            prompt=user_prompt,
            system=SYSTEM_PROMPT_BLOC_3,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        resultat_sans_resume, resume = extraire_resume_developpe(
            resultat_brut
        )

        resultat = _extraire_texte_final(
            resultat_sans_resume
        )

        contexte["resume_bloc3"] = resume

        resultat = _sanitize(resultat)

        logger.debug("Bloc 3: résultat chars=%s", len(resultat))

        if len(resultat) < 80:
            raise ValueError("Réponse LLM trop courte")

    except Exception:
        logger.exception("Bloc 3: LLM indisponible ou réponse faible, fallback points_forts")
        return points_forts

    return resultat