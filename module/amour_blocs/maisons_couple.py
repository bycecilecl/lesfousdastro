# module/amour_blocs/maisons_couple.py

import unicodedata


from module.amour_bdd import (
    get_from_maisons_amour,
    get_from_maitre_en_maison,
    df_to_snippets,
)
from utils.openai_utils import interroger_llm

# ─────────────────────────────────────────
# 1. Maîtres par signe (tropical) – avec double maître
# ─────────────────────────────────────────

MAITRES_PAR_SIGNE = {
    "belier": ["Mars"],
    "taureau": ["Vénus"],
    "gemeaux": ["Mercure"],
    "gémeaux": ["Mercure"],  # au cas où
    "cancer": ["Lune"],
    "lion": ["Soleil"],
    "vierge": ["Mercure"],
    "balance": ["Vénus"],
    "scorpion": ["Pluton", "Mars"],
    "sagittaire": ["Jupiter"],
    "capricorne": ["Saturne"],
    "verseau": ["Uranus", "Saturne"],
    "poissons": ["Neptune", "Jupiter"],
}


def _normalize_signe(signe: str | None) -> str | None:
    """
    Normalise un nom de signe : minuscules + accents retirés.
    Exemple : 'Bélier' -> 'belier', 'Gémeaux' -> 'gemeaux'
    """
    if not isinstance(signe, str):
        return None
    nfkd = unicodedata.normalize("NFKD", signe)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.lower().strip()


# def _get_signe_maison(theme: dict, numero: int) -> str | None:
#     """
#     Récupère le signe de la maison N dans theme["maisons"]["Maison N"]["signe"].
#     """
#     maisons = theme.get("maisons") or {}
#     key = f"Maison {numero}"
#     data = maisons.get(key) or {}
#     signe = data.get("signe")
#     if isinstance(signe, str) and signe.strip():
#         return signe.strip()
#     return None

def _get_signe_maison(theme: dict, numero: int) -> str | None:
    maisons = theme.get("maisons") or {}
    key = f"Maison {numero}"
    data = maisons.get(key) or {}
    signe = data.get("signe")
    if isinstance(signe, str) and signe.strip():
        return signe.strip()
    return None


def _get_maitres_pour_signe(signe: str | None) -> list[str]:
    """
    Retourne la liste des maîtres (un ou deux) pour un signe donné,
    après normalisation (accents retirés).
    """
    s_norm = _normalize_signe(signe)
    if not s_norm:
        return []
    maitres = MAITRES_PAR_SIGNE.get(s_norm)
    if maitres is None:
        return []
    return maitres if isinstance(maitres, (list, tuple)) else [maitres]


# ─────────────────────────────────────────
# 2. Bloc Maison 5 : Maison 5 + maître(s) de Maison 5
# ─────────────────────────────────────────

# def generer_bloc_maisons_amour(theme: dict, call_llm: bool = True) -> str:
#     """
#     Maison 5 (amour, désir, séduction, enfants, créativité) + maître(s) de 5.
#     """
#     polarite = "Femme"   # plus tard : à rendre dynamique (femme/homme)

#     planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

#     # 1) Maison V : signe
#     signe_5 = _get_signe_maison(theme, 5)
#     maitres_5 = _get_maitres_pour_signe(signe_5)

#     snippets_maison5 = []
#     snippets_maitre_5 = []

#     # (optionnel) Interprétation "Maison 5 en Verseau / Poissons / etc." via maisons_amour.csv
#     if signe_5:
#         df_m5 = get_from_maisons_amour(
#             type_donnee="Maison_5",
#             valeur=signe_5,     # signe tel qu'affiché ("Verseau", "Lion"...)
#             bloc="Style",
#             polarite=polarite,
#         )
#         if not df_m5.empty:
#             snippets_maison5.append(df_to_snippets(df_m5))

#     # 2) Maître(s) de 5 en maison X
#     for maitre in maitres_5:
#         donnees_maitre = planetes.get(maitre, {}) or {}
#         maison_maitre_5 = donnees_maitre.get("maison")

#         print(
#             f"[AMOUR] DEBUG Maison 5 : signe={signe_5} | maîtres={maitres_5} | "
#             f"détails={maitre} en maison {maison_maitre_5}"
#         )

#         if maison_maitre_5 is None:
#             continue

#         brut = str(maison_maitre_5).strip()
#         if brut.isdigit():
#             valeur_maitre_5 = f"Maison_{brut}"
#         else:
#             valeur_maitre_5 = brut

#         print(f"[AMOUR] DEBUG valeur_maitre_5 pour maître {maitre} envoyée au CSV : {valeur_maitre_5}")

#         df_maitre_5 = get_from_maitre_en_maison(
#             type_donnee="maitre_maison_5",
#             valeur=valeur_maitre_5,
#             bloc="Style",       # Maison 5 = bloc Style
#             polarite=polarite,
#         )
#         if not df_maitre_5.empty:
#             snippets_maitre_5.append(df_to_snippets(df_maitre_5))

#     # --- Concat maison 5 + maître(s) de 5 ---
#     snippets_bruts = "\n".join(
#         s for s in [*snippets_maison5, *snippets_maitre_5] if s
#     ).strip()

#     if not call_llm:
#         return (
#             "<pre>SNIPPETS MAISON 5 / MAITRE(S) MAISON 5:\n"
#             + snippets_bruts
#             + "</pre>"
#         )

#     if not snippets_bruts:
#         return ""

#     prompt = f"""
# On travaille ici la Maison 5 et son ou ses maîtres (amour, désir, enfants, créativité).

# Voici les informations extraites de la base de données :

# {snippets_bruts}

# Rédige un texte clair, psychologique et incarné sur :
# - ta façon de vivre l'amour et la séduction (Maison 5),
# - la manière dont l'amour s'enracine dans ta vie concrète via le ou les maîtres de la Maison 5.

# Pas de bullet points. Pas d'emoji.
# Parle en "tu".
# """
#     texte = interroger_llm(prompt)
#     return texte



# ─────────────────────────────────────────
# 3. Bloc Maison 5
# ─────────────────────────────────────────

def generer_bloc_maisons_amour(theme: dict, call_llm: bool = True) -> str:
    """
    Maison 5 : 
    - signe de la maison 5
    - planète(s) en maison 5
    - maître(s) de maison 5 en maison X (avec contexte : signe + état du maître)
    """
    polarite = "Femme"
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

    # ── 1) Signe de la Maison 5
    signe_5 = _get_signe_maison(theme, 5)
    signe_5_norm = _normalize_signe(signe_5) if isinstance(signe_5, str) else None
    maitres_5 = MAITRES_PAR_SIGNE.get(signe_5_norm, []) if signe_5_norm else []

    print(f"[AMOUR] DEBUG Maison 5 : signe={signe_5} | maîtres={maitres_5}")

    snippets = []

    # ── A) Signe de la Maison 5 (Style)
    if signe_5:
        df_m5_signe = get_from_maisons_amour(
            maison="Maison 5",
            type_donnee="Signe",
            valeur=signe_5,
            bloc="Style",
            polarite=polarite,
        )
        if not df_m5_signe.empty:
            snippets.append(
                f"=== MAISON 5 EN {signe_5.upper()} ===\n" + df_to_snippets(df_m5_signe)
            )

    # ── B) Planètes en Maison 5 (Style)
    for nom_planete, infos in planetes.items():
        if infos.get("maison") == 5:
            df_planete_5 = get_from_maisons_amour(
                maison="Maison 5",
                type_donnee="Planète",
                valeur=nom_planete,
                bloc="Style",
                polarite=polarite,
            )
            if not df_planete_5.empty:
                snippets.append(
                    f"=== PLANÈTE {nom_planete.upper()} EN MAISON 5 ===\n"
                    + df_to_snippets(df_planete_5)
                )

    # ── C) Maître(s) de la Maison 5 (maitre_en_maison.csv)
    valeurs_deja_vues = set()
    for nom_maitre in maitres_5:
        infos_m = planetes.get(nom_maitre, {}) or {}
        maison_maitre = infos_m.get("maison")
        signe_maitre = infos_m.get("signe")
        etat_maitre = infos_m.get("etat")

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()
        valeur_maitre_5 = f"Maison_{brut}" if brut.isdigit() else brut

        if valeur_maitre_5 in valeurs_deja_vues:
            continue
        valeurs_deja_vues.add(valeur_maitre_5)

        df_maitre_5 = get_from_maitre_en_maison(
            type_donnee="maitre_maison_5",
            valeur=valeur_maitre_5,
            bloc="Style",
            polarite=polarite,
        )
        if not df_maitre_5.empty:
            # Contexte : signe + état (ex : "Saturne en Balance, chute")
            contexte = f"{nom_maitre} en {signe_maitre}" if signe_maitre else nom_maitre
            if etat_maitre:
                contexte += f", {etat_maitre}"

            snippets.append(
                f"=== MAÎTRE DE 5 ({contexte.upper()}) EN MAISON {maison_maitre} ===\n"
                + df_to_snippets(df_maitre_5)
            )

    snippets_bruts = "\n".join(s for s in snippets if s).strip()

    if not call_llm:
        return (
            "<pre>SNIPPETS MAISON 5 / MAITRE(S) MAISON 5:\n"
            + (snippets_bruts or "(rien)")
            + "</pre>"
        )

    if not snippets_bruts:
        return ""

    prompt = f"""
On travaille ici la Maison 5 (amour, désir, séduction, créativité) et son ou ses maîtres.

Voici les informations extraites de la base de données :

{snippets_bruts}

Rédige un texte clair, psychologique et incarné sur :
- ta façon de vivre l'amour, la séduction et le plaisir (Maison 5),
- la manière dont tout cela s'enracine dans ta vie concrète via le maître de la Maison 5,
- en regroupant naturellement ce qui vient du signe, des planètes en Maison 5 et du ou des maîtres.

IMPORTANT : Tiens compte du signe et de l'état du maître (dignité, chute, exil) pour nuancer ton analyse.
Un maître en chute ou exil modifie l'expression de la maison.

Pas de bullet points. Pas d'emoji.
Parle en "tu".
"""
    texte = interroger_llm(prompt)
    return texte


# ─────────────────────────────────────────
# 3. Bloc Maison 7 
# ─────────────────────────────────────────

def generer_bloc_maison7_couple(theme: dict, call_llm: bool = True) -> str:
    """
    Maison 7 :
    - signe de la maison 7
    - planète(s) en maison 7
    - maître(s) de maison 7 en maison X
    """
    polarite = "Femme"
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

    signe_7 = _get_signe_maison(theme, 7)
    signe_7_norm = _normalize_signe(signe_7) if isinstance(signe_7, str) else None
    maitres_7 = MAITRES_PAR_SIGNE.get(signe_7_norm, []) if signe_7_norm else []

    print(f"[AMOUR] DEBUG Maison 7 : signe={signe_7} | maîtres={maitres_7}")

    snippets = []

    # ── A) Signe de la Maison 7 (Partenaire)
    if signe_7:
        df_m7_signe = get_from_maisons_amour(
            type_donnee="Maison 7",
            valeur=signe_7,
            bloc="Partenaire",
            polarite=polarite,
        )
        if not df_m7_signe.empty:
            snippets.append(
                f"=== MAISON 7 EN {signe_7.upper()} ===\n" + df_to_snippets(df_m7_signe)
            )

    # ── B) Planètes en Maison 7 (Partenaire)
    for nom_planete, infos in planetes.items():
        if infos.get("maison") == 7:
            df_planete_7 = get_from_maisons_amour(
                type_donnee="Maison 7",
                valeur=nom_planete,
                bloc="Partenaire",
                polarite=polarite,
            )
            if not df_planete_7.empty:
                snippets.append(
                    f"=== PLANÈTE {nom_planete.upper()} EN MAISON 7 ===\n"
                    + df_to_snippets(df_planete_7)
                )

    # ── C) Maître(s) de la Maison 7
    valeurs_deja_vues = set()
    for nom_maitre in maitres_7:
        infos_m = planetes.get(nom_maitre, {}) or {}
        maison_maitre = infos_m.get("maison")
        signe_maitre = infos_m.get("signe")
        etat_maitre = infos_m.get("etat")

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()
        valeur_maitre_7 = f"Maison_{brut}" if brut.isdigit() else brut

        if valeur_maitre_7 in valeurs_deja_vues:
            continue
        valeurs_deja_vues.add(valeur_maitre_7)

        df_maitre_7 = get_from_maitre_en_maison(
            type_donnee="maitre_maison_7",
            valeur=valeur_maitre_7,
            bloc="Partenaire",
            polarite=polarite,
        )

        if not df_maitre_7.empty:
            contexte = f"{nom_maitre} en {signe_maitre}" if signe_maitre else nom_maitre
            if etat_maitre:
                contexte += f", {etat_maitre}"

            snippets.append(
                f"=== MAÎTRE DE 7 ({contexte.upper()}) EN MAISON {maison_maitre} ===\n"
                + df_to_snippets(df_maitre_7)
            )

    snippets_bruts = "\n".join(s for s in snippets if s).strip()

    if not call_llm:
        return (
            "<pre>SNIPPETS MAISON 7 / MAITRE(S) MAISON 7:\n"
            + (snippets_bruts or "(rien)")
            + "</pre>"
        )

    if not snippets_bruts:
        return ""

    prompt = f"""
On travaille ici la Maison 7 (couple officiel, engagement, partenariat) et son ou ses maîtres.

Voici les informations extraites de la base de données :

{snippets_bruts}

Rédige un texte clair, psychologique et incarné sur :
- ta façon de vivre le couple et l'engagement (Maison 7),
- le type de partenaire que tu attires ou avec qui tu t'engages,
- en tenant compte à la fois du signe de ta Maison 7, des planètes en Maison 7 et des maîtres de la Maison 7.

IMPORTANT : Tiens compte du signe et de l'état du maître (dignité, chute, exil) pour nuancer ton analyse.

Pas de bullet points. Pas d'emoji.
Parle en "tu".
"""
    texte = interroger_llm(prompt)
    return texte


# ─────────────────────────────────────────
# 3. Bloc Maison 8
# ─────────────────────────────────────────

# def generer_bloc_maison8_intimite(theme: dict, call_llm: bool = True) -> str:
#     """
#     Maison 8 :
#     - signe de la maison 8
#     - planète(s) en maison 8
#     - maître(s) de maison 8 en maison X
#     """
#     polarite = "Femme"
#     planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

#     signe_8 = _get_signe_maison(theme, 8)
#     signe_8_norm = _normalize_signe(signe_8) if isinstance(signe_8, str) else None
#     maitres_8 = MAITRES_PAR_SIGNE.get(signe_8_norm, []) if signe_8_norm else []

#     print(f"[AMOUR] DEBUG Maison 8 : signe={signe_8} | maîtres={maitres_8}")

#     snippets = []

#     # ── A) Signe de la Maison 8 (Désir / Transformation)
#     if signe_8:
#         df_m8_signe = get_from_maisons_amour(
#             type_donnee="Maison 8",
#             valeur=signe_8,
#             bloc="Désir / Transformation",
#             polarite=polarite,
#         )
#         if not df_m8_signe.empty:
#             snippets.append(
#                 f"=== MAISON 8 EN {signe_8.upper()} ===\n" + df_to_snippets(df_m8_signe)
#             )

#     # ── B) Planètes en Maison 8 (Désir / Transformation)
#     for nom_planete, infos in planetes.items():
#         if infos.get("maison") == 8:
#             df_planete_8 = get_from_maisons_amour(
#                 type_donnee="Maison 8",
#                 valeur=nom_planete,
#                 bloc="Désir / Transformation",
#                 polarite=polarite,
#             )
#             if not df_planete_8.empty:
#                 snippets.append(
#                     f"=== PLANÈTE {nom_planete.upper()} EN MAISON 8 ===\n"
#                     + df_to_snippets(df_planete_8)
#                 )

#     # ── C) Maître(s) de la Maison 8
#     valeurs_deja_vues = set()
#     for nom_maitre in maitres_8:
#         infos_m = planetes.get(nom_maitre, {}) or {}
#         maison_maitre = infos_m.get("maison")
#         signe_maitre = infos_m.get("signe")
#         etat_maitre = infos_m.get("etat")

#         if maison_maitre is None:
#             continue

#         brut = str(maison_maitre).strip()
#         valeur_maitre_8 = f"Maison_{brut}" if brut.isdigit() else brut

#         if valeur_maitre_8 in valeurs_deja_vues:
#             continue
#         valeurs_deja_vues.add(valeur_maitre_8)

#         df_maitre_8 = get_from_maitre_en_maison(
#             type_donnee="maitre_maison_8",
#             valeur=valeur_maitre_8,
#             bloc="Désir / Transformation",
#             polarite=polarite,
#         )

#         if not df_maitre_8.empty:
#             contexte = f"{nom_maitre} en {signe_maitre}" if signe_maitre else nom_maitre
#             if etat_maitre:
#                 contexte += f", {etat_maitre}"

#             snippets.append(
#                 f"=== MAÎTRE DE 8 ({contexte.upper()}) EN MAISON {maison_maitre} ===\n"
#                 + df_to_snippets(df_maitre_8)
#             )

#     snippets_bruts = "\n".join(s for s in snippets if s).strip()

#     if not call_llm:
#         return (
#             "<pre>SNIPPETS MAISON 8 / MAITRE(S) MAISON 8:\n"
#             + (snippets_bruts or "(rien)")
#             + "</pre>"
#         )

#     if not snippets_bruts:
#         return ""

#     prompt = f"""
# On travaille ici la Maison 8 (intimité profonde, fusion, transformation, crises) et son ou ses maîtres.

# Voici les informations extraites de la base de données :

# {snippets_bruts}

# Rédige un texte clair, psychologique et incarné sur :
# - ta façon de vivre l'intimité, la fusion et la confiance profonde (Maison 8),
# - ce que cela raconte de ta manière de t'attacher, de te livrer et de traverser les crises à deux,
# - en tenant compte à la fois du signe de ta Maison 8, des planètes en Maison 8 et des maîtres de la Maison 8.

# IMPORTANT : Tiens compte du signe et de l'état du maître (dignité, chute, exil) pour nuancer ton analyse.

# Pas de bullet points. Pas d'emoji.
# Parle en "tu".
# """
#     texte = interroger_llm(prompt)
#     return texte

def generer_bloc_maison8_intimite(theme: dict, call_llm: bool = True) -> str:
    """
    Maison 8 : signe + maître(s) en maison X (avec contexte : signe + état du maître)
    + nuances spécifiques si le maître est en dignité / chute / exil / rétrograde.
    """
    polarite = "Femme"
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

    signe_8 = _get_signe_maison(theme, 8)
    signe_8_norm = _normalize_signe(signe_8) if isinstance(signe_8, str) else None
    maitres_8 = MAITRES_PAR_SIGNE.get(signe_8_norm, []) if signe_8_norm else []

    print(f"[AMOUR] DEBUG Maison 8 : signe={signe_8} | maîtres={maitres_8}")

    snippets = []
    nuances = []  # <= ici on va accumuler les nuances liées à l'état des maîtres

    # ── A) Signe de la Maison 8
    if signe_8:
        df_m8_signe = get_from_maisons_amour(
            maison="Maison 8",
            type_donnee="Signe",
            valeur=signe_8,
            bloc="Désir / Transformation",
            polarite=polarite,
        )
        if not df_m8_signe.empty:
            snippets.append(
                f"=== MAISON 8 EN {signe_8.upper()} ===\n" + df_to_snippets(df_m8_signe)
            )

    # ── B) Maître(s) de la Maison 8
    valeurs_deja_vues = set()

    for nom_maitre in maitres_8:
        infos_m = planetes.get(nom_maitre, {}) or {}
        maison_maitre = infos_m.get("maison")
        signe_maitre = infos_m.get("signe")
        etat_maitre = infos_m.get("etat")  # ex : "dignité", "chute", "exil", "rétrograde"

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()
        valeur_maitre_8 = f"Maison_{brut}" if brut.isdigit() else brut

        if valeur_maitre_8 in valeurs_deja_vues:
            continue
        valeurs_deja_vues.add(valeur_maitre_8)

        df_maitre_8 = get_from_maitre_en_maison(
            type_donnee="maitre_maison_8",
            valeur=valeur_maitre_8,
            bloc="Désir / Transformation",
            polarite=polarite,
        )

        if not df_maitre_8.empty:
            contexte = f"{nom_maitre} en {signe_maitre}" if signe_maitre else nom_maitre
            if etat_maitre:
                contexte += f", {etat_maitre}"

            snippets.append(
                f"=== MAÎTRE DE 8 ({contexte.upper()}) EN MAISON {maison_maitre} ===\n"
                + df_to_snippets(df_maitre_8)
            )

        # ───────────── NUANCES SPÉCIFIQUES MAISON 8 ─────────────
        etat_label = (etat_maitre or "").lower()

        # Chute / exil → sexualité plus compliquée / sensible / ambivalente
        if any(mot in etat_label for mot in ["chute", "exil", "detriment"]):
            txt = (
                f"- {nom_maitre} en {signe_maitre} est en {etat_maitre}. "
                "Cela nuance fortement ta Maison 8 : ton désir est profond, mais il peut être "
                "plus fragile, ambivalent ou chargé de peurs. Tu peux ressentir l’intensité, "
                "tout en ayant du mal à te livrer complètement ou à faire confiance."
            )
            nuances.append(txt)

        # Dignité / domicile / maîtrise → sexualité plus assumée, puissante
        elif any(mot in etat_label for mot in ["dignite", "dignité", "domicile", "maitrise", "maîtrise"]):
            txt = (
                f"- {nom_maitre} en {signe_maitre} est en {etat_maitre}. "
                "Cela renforce ta Maison 8 : sexualité, fusion et transformations profondes "
                "deviennent des leviers puissants d’évolution, que tu peux assumer avec plus "
                "de clarté et de force intérieure."
            )
            nuances.append(txt)

        # Rétrograde → intensité intériorisée, travail de fond
        elif "retro" in etat_label or "rétro" in etat_label:
            txt = (
                f"- {nom_maitre} en {signe_maitre} est rétrograde. "
                "Ton rapport à l’intimité et au désir fonctionne beaucoup en interne : "
                "remises en question, allers-retours, reprises, besoin de comprendre ce que "
                "tu projettes sur l’autre avant de te livrer vraiment."
            )
            nuances.append(txt)

    # ── On assemble les snippets de base
    snippets_bruts = "\n".join(s for s in snippets if s).strip()

    # ── On construit un petit bloc de texte pour les nuances, si on en a
    nuance_texte = ""
    if nuances:
        nuance_texte = (
            "\n\nNuances importantes liées à l'état du ou des maîtres de ta Maison 8 :\n"
            + "\n".join(nuances)
        )

    # ── MODE DEBUG (call_llm=False) : on montre tout brut
    if not call_llm:
        debug_full = (
            "SNIPPETS MAISON 8 / MAITRE(S) MAISON 8:\n"
            + (snippets_bruts or "(rien)")
        )
        if nuance_texte:
            debug_full += "\n\n" + nuance_texte
        return "<pre>" + debug_full + "</pre>"

    # ── Si vraiment aucun snippet, on ne fait rien
    if not snippets_bruts:
        return ""

    # ── Appel LLM
    prompt = f"""
On travaille ici la Maison 8 (intimité profonde, fusion, transformation, crises) et son ou ses maîtres.

Voici les informations extraites de la base de données :

{snippets_bruts}

Rédige un texte clair, psychologique et incarné sur :
- ta façon de vivre l'intimité, la fusion et la confiance profonde (Maison 8),
- ce que cela raconte de ta manière de t'attacher, de te livrer et de traverser les crises à deux (maître(s) de la Maison 8).

IMPORTANT : Tiens déjà compte du fait que tout ce qui touche à la Maison 8 est chargé, intense, souvent sensible.

Pas de bullet points. Pas d'emoji.
Parle en "tu".
"""
    
    print("\n" + "*" * 40)
    print("***        PROMPT ENVOYÉ AU LLM       ***")
    print("*" * 40)
    print(prompt)
    print("*" * 40 + "\n")

    texte = interroger_llm(prompt)

    # ── On ajoute les nuances APRÈS le texte généré
    if nuance_texte:
        texte = texte.strip() + "\n\n" + nuance_texte.strip()

    return texte


