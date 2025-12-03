# module/amour_blocs/soleil_lune.py

from module.amour_bdd import (
    get_from_placements,
    get_from_aspects,
    df_to_snippets,
)
from utils.openai_utils import interroger_llm


def _normaliser_type_aspect(type_brut: str) -> str | None:
    if not type_brut:
        return None

    t = str(type_brut).lower()
    t = (
        t.replace("é", "e")
         .replace("è", "e")
         .replace("ê", "e")
    )

    if "conj" in t:
        return "Conjonction"
    if "carre" in t and "semi" not in t and "sesqui" not in t:
        return "Carré"
    if "opp" in t:
        return "Opposition"
    if "trig" in t:
        return "Trigone"
    if "sext" in t and "semi" not in t:
        return "Sextile"
    if "quin" in t:
        return "Quinconce"
    if "sesqui" in t:
        return "Sesqui-carré"
    if "semi-carre" in t or ("carre" in t and "semi" in t):
        return "Semi-carré"
    if "semi-sext" in t:
        return "Semi-sextile"

    return type_brut.capitalize()


def _extraire_aspects(theme: dict, planete: str):
    """
    Récupère tous les aspects du thème qui impliquent une planète donnée.
    Gère planete_1 / planete1 / planète_1 / p1, idem pour la 2.
    """
    aspects_theme = theme.get("aspects", []) or theme.get("Aspects", []) or []
    resultat = []
    for asp in aspects_theme:
        p1 = (
            asp.get("planete_1")
            or asp.get("planete1")
            or asp.get("planète_1")
            or asp.get("p1")
        )
        p2 = (
            asp.get("planete_2")
            or asp.get("planete2")
            or asp.get("planète_2")
            or asp.get("p2")
        )
        if p1 == planete or p2 == planete:
            resultat.append(asp)
    return resultat


def generer_bloc_soleil_lune(theme: dict, call_llm: bool = True) -> str:
    """
    Bloc Soleil / Lune :
    - placements du Soleil (image de l’homme / figure masculine intérieure)
    - placements de la Lune (manière de vivre l’intimité, le foyer, le quotidien)
    - aspect Soleil/Lune (modèle intérieur du couple)
    - aspects du Soleil avec les autres planètes (type d’homme qui t’attire, via Soleil–Pluton, Soleil–Neptune, etc.)
    """

    polarite = "Femme"  # plus tard : paramétrable

    planetes = theme.get("planetes", {}) or theme.get("planètes", {})
    soleil = planetes.get("Soleil", {})
    lune = planetes.get("Lune", {})

    soleil_signe = soleil.get("signe")
    soleil_maison = str(soleil.get("maison")) if soleil.get("maison") else None

    lune_signe = lune.get("signe")
    lune_maison = str(lune.get("maison")) if lune.get("maison") else None

    # --- PLACEMENTS SOLEIL (Femme : image de l’homme / figure masculine intérieure) ---
    df_ss = get_from_placements("Soleil", "Signe", soleil_signe, polarite=polarite)
    df_sm = get_from_placements("Soleil", "Maison", soleil_maison, polarite=polarite)

    # --- PLACEMENTS LUNE (Femme : manière de vivre l’intimité, le foyer, le couple au quotidien) ---
    df_ls = get_from_placements("Lune", "Signe", lune_signe, polarite=polarite)
    df_lm = get_from_placements("Lune", "Maison", lune_maison, polarite=polarite)

    # --- ASPECT SOLEIL/LUNE : lien entre archétype masculin et féminin en toi ---
    aspect_sl = None
    for asp in theme.get("aspects", []) or theme.get("Aspects", []) or []:
        p1 = (
            asp.get("planete_1")
            or asp.get("planete1")
            or asp.get("planète_1")
            or asp.get("p1")
        )
        p2 = (
            asp.get("planete_2")
            or asp.get("planete2")
            or asp.get("planète_2")
            or asp.get("p2")
        )
        if {p1, p2} == {"Soleil", "Lune"}:
            aspect_sl = asp
            break

    df_aspect_sl = None
    if aspect_sl:
        type_norm = _normaliser_type_aspect(
            aspect_sl.get("aspect") or aspect_sl.get("type") or aspect_sl.get("nom")
        )
        if type_norm:
            df_aspect_sl = get_from_aspects(
                planete_1="Soleil",
                planete_2="Lune",
                valeur=type_norm,
                bloc="Style",
                polarite=polarite,
            )

        # --- ASPECTS DU SOLEIL AVEC LES AUTRES PLANÈTES (type d’homme) ---

    aspects_soleil = _extraire_aspects(theme, "Soleil")

    # Priorité des planètes (0 = le plus important)
    PRIORITE_PLANETE = {
        "Pluton": 0,
        "Saturne": 1,
        "Neptune": 2,
        "Uranus": 3,
        "Jupiter": 4,
        "Mars": 5,
        "Vénus": 6,
        "Venus": 6,
        "Mercure": 7,
    }

    # Priorité des aspects
    PRIORITE_ASPECT = {
        "Conjonction": 0,
        "Opposition": 1,
        "Carré": 2,
        "Carre": 2,
        "Trigone": 3,
        "Sextile": 4,
    }

    # On stocke (clé_de_tri, df) pour trier après
    aspects_tries = []

    for asp in aspects_soleil:
        p1 = (
            asp.get("planete_1")
            or asp.get("planete1")
            or asp.get("planète_1")
            or asp.get("p1")
        )
        p2 = (
            asp.get("planete_2")
            or asp.get("planete2")
            or asp.get("planète_2")
            or asp.get("p2")
        )
        if not p1 or not p2:
            continue

        # On saute le Soleil/Lune, déjà traité avant
        if {p1, p2} == {"Soleil", "Lune"}:
            continue

        autre_planete = p2 if p1 == "Soleil" else p1

        type_brut = (
            asp.get("aspect")
            or asp.get("type")
            or asp.get("nom")
        )
        type_norm = _normaliser_type_aspect(type_brut)
        if not type_norm:
            continue

        df_sa = get_from_aspects(
            planete_1="Soleil",
            planete_2=autre_planete,
            valeur=type_norm,
            bloc="Partenaire",
            polarite=polarite,
        )

        if df_sa.empty:
            continue

        # Récupération de l'orbe pour affiner la priorité (plus c'est serré, mieux c'est)
        try:
            orbe = float(asp.get("orbe", 99))
        except (TypeError, ValueError):
            orbe = 99.0

        key = (
            PRIORITE_PLANETE.get(autre_planete, 99),
            PRIORITE_ASPECT.get(type_norm, 99),
            orbe,
        )

        aspects_tries.append((key, df_sa))

    # On trie par importance
    aspects_tries.sort(key=lambda x: x[0])

    # On limite le nombre d'aspects pris en compte (par ex. top 2 ou 3)
    MAX_ASPECTS = 3
    snippets_soleil_autres = [
        df_to_snippets(df_sa) for _, df_sa in aspects_tries[:MAX_ASPECTS]
    ]

    snippets_soleil_autres_txt = "\n".join(
        s for s in snippets_soleil_autres if s
    ).strip()

    # --- CONCAT SNIPPETS BRUTS ---
    snippets_couple = "\n".join(
        s for s in [
            df_to_snippets(df_ss),
            df_to_snippets(df_sm),
            df_to_snippets(df_ls),
            df_to_snippets(df_lm),
            df_to_snippets(df_aspect_sl) if df_aspect_sl is not None else "",
        ] if s
    ).strip()

    if not call_llm:
        return (
            "<pre>"
            "SNIPPETS SOLEIL/LUNE (modèle intérieur du couple):\n"
            f"{snippets_couple}\n\n"
            "SNIPPETS SOLEIL_AUTRES (type d’homme via aspects du Soleil):\n"
            f"{snippets_soleil_autres_txt}"
            "</pre>"
        )

    # --- PROMPT LLM ---
    prompt = f"""
Tu parles à une femme hétéro.

On travaille ici le DUO SOLEIL / LUNE de son thème natal.

Soleil/Lune = son modèle intérieur du couple :
- comment elle vit l'engagement,
- le quotidien à deux,
- ce qu'elle rejoue de son couple parental (et de son vécu affectif).

Les aspects du Soleil aux autres planètes = coloration du type d’homme qui l’attire,
et de ce qu'elle projette sur la figure masculine (Soleil–Pluton, Soleil–Neptune, etc.).

Voici les informations issues de la base de données :

[Modèle intérieur du couple - Soleil/Lune]
{snippets_couple}

[Type d'homme qui t'attire - Aspects du Soleil]
{snippets_soleil_autres_txt}

Rédige un texte structuré en deux parties :

Partie 1 — "Ton modèle intérieur du couple"
Explique comment elle vit l'engagement, le quotidien, les projections liées au couple parental,
et ce que cela crée comme dynamiques (fusion, tension, besoin de sécurité, idéalisation, etc.).

Partie 2 — "Le type d’homme que tu investis dans le long terme"
Décris le type d’homme qu’elle attire ou idéalise pour une relation engagée,
en intégrant surtout les aspects du Soleil aux autres planètes (Pluton, Neptune, Saturne, etc.)
et ce que cela raconte de ses attentes, de ses peurs et de ses schémas.

Style : psychologique, direct, profond, concret.
Pas de blabla spirituel fumeux, pas d’envolée poétique.
Aucun bullet point. Aucun emoji.
Parle-lui en "tu".
"""
    
    print("\n" + "*" * 40)
    print("***        PROMPT ENVOYÉ AU LLM       ***")
    print("*" * 40)
    print(prompt)
    print("*" * 40 + "\n")

    
    texte = interroger_llm(prompt)
    return texte