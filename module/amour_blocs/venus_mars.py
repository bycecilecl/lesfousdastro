from module.amour_bdd import (
    get_from_placements,
    get_from_aspects,
    get_from_etat_planete,
    df_to_snippets,
)
from utils.openai_utils import interroger_llm  # comme dans tes autres modules

def _normaliser_type_aspect(type_brut: str) -> str | None:
    """
    Prend le type d'aspect venant de calcul_theme (ex: 'trigone', 'CONJ', 'Opposition')
    et le mappe sur les valeurs de ta colonne VALEUR dans aspects.csv :
    Conjonction, Carré, Opposition, Trigone, Sextile, Quinconce, Sesqui-carré, etc.
    """
    if not type_brut:
        return None

    t = str(type_brut).lower().replace("é", "e").replace("è", "e").replace("ê", "e")

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

    # fallback : on renvoie capitalisé
    return type_brut.capitalize()


def _extraire_aspects_planete(theme: dict, planete_cible: str) -> list[dict]:
    aspects_theme = theme.get("aspects", []) or theme.get("Aspects", []) or []
    resultat = []

    planete_cible_norm = planete_cible.replace("é", "e").lower()

    for asp in aspects_theme:
        p1 = (
            asp.get("planete_1")
            or asp.get("planète_1")
            or asp.get("p1")
            or asp.get("planete1")
        )
        p2 = (
            asp.get("planete_2")
            or asp.get("planète_2")
            or asp.get("p2")
            or asp.get("planete2")
        )

        if not p1 or not p2:
            continue

        p1_norm = p1.replace("é", "e").lower()
        p2_norm = p2.replace("é", "e").lower()

        if p1_norm == planete_cible_norm or p2_norm == planete_cible_norm:
            resultat.append(asp)

    return resultat

def generer_bloc_venus_mars(theme: dict, call_llm: bool = True) -> str:
    """
    Bloc Vénus/Mars du module Amour.
    Version finale : structure Vénus (toi) + Mars (type d’homme) + passage LLM.
    """

    print("\n\n=== DEBUG ASPECTS DU THÈME ===")
    for asp in theme.get("aspects", []):
        print(asp)
    print("=== FIN DEBUG ===\n\n")

    # Polarités par défaut (plus tard : l’utilisateur pourra choisir)
    polarite_soi = "Femme"
    polarite_partenaire = "Homme"

    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

    venus = planetes.get("Vénus", {}) or planetes.get("Venus", {})
    mars = planetes.get("Mars", {})

    venus_signe = venus.get("signe")
    venus_maison = str(venus.get("maison")) if venus.get("maison") else None

    mars_signe = mars.get("signe")
    mars_maison = str(mars.get("maison")) if mars.get("maison") else None

        # --- SNIPPETS VÉNUS (toi) ---
    df_vs = get_from_placements("Vénus", "Signe", venus_signe, polarite=polarite_soi)
    df_vm = get_from_placements("Vénus", "Maison", venus_maison, polarite=polarite_soi)
    df_ve = get_from_etat_planete("Vénus", venus.get("etat"), polarite=polarite_soi)

    # Aspects de Vénus dans le thème
    aspects_venus = _extraire_aspects_planete(theme, "Vénus")
    snippets_venus_aspects = []

    for asp in aspects_venus:
        p1 = (
            asp.get("planete_1")
            or asp.get("planète_1")
            or asp.get("p1")
            or asp.get("planete1")
        )
        p2 = (
            asp.get("planete_2")
            or asp.get("planète_2")
            or asp.get("p2")
            or asp.get("planete2")
        )
        type_brut = asp.get("type") or asp.get("aspect") or asp.get("nom")

        type_norm = _normaliser_type_aspect(type_brut)

        # on cherche l'autre planète de l'aspect
        autre_planete = p2 if p1 == "Vénus" else p1

        df_va = get_from_aspects(
            planete_1="Vénus",
            valeur=type_norm,
            polarite=polarite_soi,
            bloc="Style",
        )

        if not df_va.empty:
            snippets_venus_aspects.append(df_to_snippets(df_va))

    snippets_venus = "\n".join(filter(None, [
        df_to_snippets(df_vs),
        df_to_snippets(df_vm),
        df_to_snippets(df_ve),
        "\n".join(snippets_venus_aspects)
    ])).strip()

        # --- SNIPPETS MARS (type d’homme) ---
    df_ms = get_from_placements("Mars", "Signe", mars_signe, polarite=polarite_partenaire)
    df_mm = get_from_placements("Mars", "Maison", mars_maison, polarite=polarite_partenaire)
    df_me = get_from_etat_planete("Mars", mars.get("etat"), polarite=polarite_partenaire)

    aspects_mars = _extraire_aspects_planete(theme, "Mars")
    snippets_mars_aspects = []

    for asp in aspects_mars:
        p1 = asp.get("planete_1") or asp.get("planète_1") or asp.get("p1")
        p2 = asp.get("planete_2") or asp.get("planète_2") or asp.get("p2")
        type_brut = asp.get("type") or asp.get("aspect") or asp.get("nom")

        type_norm = _normaliser_type_aspect(type_brut)
        autre_planete = p2 if p1 == "Mars" else p1

        df_ma = get_from_aspects(
            planete_1="Mars",
            valeur=type_norm,
            polarite=polarite_partenaire,
            bloc="Style",
        )

        if not df_ma.empty:
            snippets_mars_aspects.append(df_to_snippets(df_ma))

    snippets_mars = "\n".join(filter(None, [
        df_to_snippets(df_ms),
        df_to_snippets(df_mm),
        df_to_snippets(df_me),
        "\n".join(snippets_mars_aspects)
    ])).strip()

    if not call_llm:
        return f"<pre>SNIPPETS VENUS:\n{snippets_venus}\n\nSNIPPETS MARS:\n{snippets_mars}</pre>"

    # --- PROMPT LLM ---
    prompt = f"""
Tu parles à une femme hétéro.

Voici les informations extraites de sa Vénus (sa façon d’aimer, ses besoins émotionnels, sa sensibilité, ses blessures) :

{snippets_venus}

Voici les informations extraites de son Mars (le type d’homme qui l’attire, ce qui la stimule, ce qu’elle recherche en miroir) :

{snippets_mars}

Rédige un texte structuré, clair, incarné, en 2 à 3 paragraphes pour chaque partie.

Partie 1 — "Ta manière d’aimer"
Partie 2 — "Le type d’homme qui t’attire"

Style : psychologique, direct, profond, sans envolée poétique inutile.
Aucun bullet point. Aucun emoji.
"""

    print("\n" + "*" * 40)
    print("***        PROMPT ENVOYÉ AU LLM       ***")
    print("*" * 40)
    print(prompt)
    print("*" * 40 + "\n")
    
    texte = interroger_llm(prompt)

    return texte