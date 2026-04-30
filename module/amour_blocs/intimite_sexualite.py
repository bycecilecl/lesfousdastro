# module/amour_blocs/intimite_sexualite.py
# MODULE 4 : Intimité & Sexualité avec FILTRAGE INTELLIGENT des aspects

from module.amour_bdd import (
    get_from_placements,
    get_from_aspects,
    get_from_maisons_amour,
    get_from_maitre_en_maison,
    get_from_etat_planete,
    df_to_snippets,
)
from module.amour_blocs.maisons_couple import (
    MAITRES_PAR_SIGNE,
    _get_signe_maison,
    _normalize_signe,
)
from module.amour_blocs.dignites import get_dignite_planete
from utils.openai_utils import interroger_llm
from module.amour_blocs.utils_theme import exporter_theme_complet
from module.amour_blocs.context_amour import generer_contexte_amour

# Maisons vraiment "intimes" pour la sexualité
MAISONS_INTIMES = [1, 5, 7, 8, 12]


def _get_maison_planete(theme: dict, planete: str) -> int | None:
    """
    Récupère le numéro de la maison d'une planète (int) à partir de theme['planetes'].
    """
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    data = planetes.get(planete, {}) or {}
    m = data.get("maison")
    if m is None:
        return None
    try:
        return int(str(m).strip())
    except ValueError:
        return None


def _get_aspects_reels_du_theme(theme: dict) -> list:
    """
    Extrait les aspects réels présents dans le thème.
    Retourne une liste de tuples (planete_1, planete_2, type_aspect, orbe)
    """
    aspects_list = theme.get("aspects", [])
    
    aspects_reels = []
    for asp in aspects_list:
        p1 = asp.get("planete1")
        p2 = asp.get("planete2")
        type_asp = asp.get("aspect")
        orbe = asp.get("orbe", 0)
        
        if p1 and p2 and type_asp:
            aspects_reels.append((p1, p2, type_asp, orbe))
    
    return aspects_reels


def _filtrer_aspects_durs_intelligents(
    theme: dict,
    planete_cible: str,
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> list[tuple[str, str, float]]:
    """
    Filtre intelligent des aspects DURS pour le Module 4 (Intimité).
    
    Stratégie spécifique sexualité :
    - TOUS les aspects serrés (≤ 5°) avec aspects durs
    - Max 3 trans-saturniennes (Pluton/Neptune/Chiron/Lune Noire)
    - Max 2 lentes (Saturne/Uranus/Jupiter)
    - Max 1 autre
    
    Retourne : liste de (autre_planete, type_aspect, orbe)
    """
    aspects_reels = _get_aspects_reels_du_theme(theme)
    aspects_durs = ["Conjonction", "Carre", "Carré", "Opposition"]
    
    trans_saturniennes = {"Pluton", "Neptune", "Chiron", "Lune Noire", "Lilith"}
    lentes = {"Saturne", "Uranus", "Jupiter"}
    
    candidats = []
    
    # Collecte des aspects durs concernant la planète cible
    for (p1, p2, type_asp, orbe) in aspects_reels:
        if type_asp not in aspects_durs:
            continue
        if orbe is None or orbe > orbe_max:
            continue
        
        if planete_cible not in (p1, p2):
            continue
        
        autre = p2 if p1 == planete_cible else p1
        
        # Catégorisation
        if orbe <= orbe_serre:
            categorie = "serré"
        elif autre in trans_saturniennes:
            categorie = "trans"
        elif autre in lentes:
            categorie = "lent"
        else:
            categorie = "autre"
        
        candidats.append({
            "autre": autre,
            "type": type_asp,
            "orbe": orbe,
            "categorie": categorie
        })
    
    # Tri par orbe
    candidats.sort(key=lambda x: x["orbe"])
    
    # Sélection
    selection = []
    count_trans = 0
    count_lent = 0
    count_autre = 0
    
    for asp in candidats:
        cat = asp["categorie"]
        
        if cat == "serré":
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            print(f"[INTIME] ✅ Aspect DUR SERRÉ gardé : {planete_cible} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "trans" and count_trans < 3:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_trans += 1
            print(f"[INTIME] ✅ Aspect DUR TRANS gardé : {planete_cible} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "lent" and count_lent < 2:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_lent += 1
            print(f"[INTIME] ✅ Aspect DUR LENT gardé : {planete_cible} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "autre" and count_autre < 1:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_autre += 1
            print(f"[INTIME] ✅ Aspect DUR AUTRE gardé : {planete_cible} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        else:
            print(f"[INTIME] ⏭️ Aspect DUR écarté (quota atteint) : {planete_cible} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
    
    return selection


def _get_aspects_durs_planete_filtres(
    theme: dict,
    planete_cible: str,
    polarite: str,
    bloc: str = "Intime",
    planetes_filtrees: tuple[str, ...] | None = None,
    filtrer_par_maison: bool = True,
) -> list:
    """
    VERSION FILTRÉE : Récupère les aspects DURS à une planète en utilisant le filtrage intelligent.
    """
    maison_cible = _get_maison_planete(theme, planete_cible)
    PLANETES_SEXUELLES = ["Pluton", "Uranus", "Lune Noire", "Lilith", "Chiron", "Saturne"]
    
    # Cas spécial : VÉNUS → si maison non intime, on zappe
    if planete_cible == "Vénus" and filtrer_par_maison:
        if maison_cible not in MAISONS_INTIMES:
            print(
                f"[{bloc.upper()}] 🚫 Vénus en maison {maison_cible} (non intime) : "
                "on ignore tous ses aspects."
            )
            return []
    
    # Filtrage intelligent
    aspects_filtres = _filtrer_aspects_durs_intelligents(theme, planete_cible)
    
    snippets = []
    
    for (autre_planete, type_asp, orbe) in aspects_filtres:
        # Filtre éventuel sur la liste de planètes autorisées
        if planetes_filtrees is not None and autre_planete not in planetes_filtrees:
            print(f"[{bloc.upper()}] ⏭️ Planète {autre_planete} non dans la liste autorisée, ignoré")
            continue
        
        # Filtre maisons intimes pour Mars/Lune
        if filtrer_par_maison and planete_cible in ("Mars", "Lune"):
            if autre_planete not in PLANETES_SEXUELLES:
                if maison_cible not in MAISONS_INTIMES:
                    print(
                        f"[{bloc.upper()}] 🚫 Aspect ignoré (maison {maison_cible} non intime) : "
                        f"{planete_cible} {type_asp} {autre_planete}"
                    )
                    continue
        
        # Chercher l'interprétation dans le CSV
        df = get_from_aspects(
            planete_1=planete_cible,
            planete_2=autre_planete,
            valeur=type_asp,
            bloc=bloc,
            polarite=polarite,
        )
        
        if df.empty:
            df = get_from_aspects(
                planete_1=autre_planete,
                planete_2=planete_cible,
                valeur=type_asp,
                bloc=bloc,
                polarite=polarite,
            )
        
        if not df.empty:
            txt = df_to_snippets(df)
            if txt:
                snippets.append(txt)
                print(f"[{bloc.upper()}]   ✅ Interprétation trouvée pour {planete_cible} {type_asp} {autre_planete}")
        else:
            print(f"[{bloc.upper()}]   ⚠️ Pas d'interprétation en BDD pour {planete_cible} {type_asp} {autre_planete}")
    
    return snippets


def _get_planetes_en_maison(theme: dict, numero: int) -> list[str]:
    """
    Retourne la liste des planètes présentes dans la maison `numero`.
    """
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    resultat = []
    for nom, donnees in planetes.items():
        if donnees.get("maison") == numero:
            resultat.append(nom)
    return resultat


def generer_bloc_intimite_sexualite(theme: dict, call_llm: bool = True, polarite: str = "Femme") -> str:
    """
    MODULE 4 · Intimité & Sexualité avec FILTRAGE INTELLIGENT

    Focus : aspects DURS filtrés intelligemment pour éviter surcharge
    """
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    snippets_parts = []

    # ═══════════════════════════════════════
    # 1) MARS : Désir & Action sexuelle
    # ═══════════════════════════════════════
    mars_data = planetes.get("Mars") or {}
    signe_mars = mars_data.get("signe")
    maison_mars = mars_data.get("maison")
    
    snippets_mars = []

    # Mars en signe
    if signe_mars:
        df_mars_signe = get_from_placements(
            planete="Mars",
            type_donnee="Signe",
            valeur=signe_mars,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_mars_signe.empty:
            snippets_mars.append(df_to_snippets(df_mars_signe))

    # Mars en maison
    if maison_mars is not None:
        valeur_maison = f"Maison_{maison_mars}"
        df_mars_maison = get_from_placements(
            planete="Mars",
            type_donnee="Maison",
            valeur=valeur_maison,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_mars_maison.empty:
            snippets_mars.append(df_to_snippets(df_mars_maison))

    # État de Mars
    if signe_mars:
        dignite_mars = get_dignite_planete("Mars", signe_mars)
        if dignite_mars in ["Chute", "Exil"]:
            df_mars_etat = get_from_etat_planete(
                planete_1="Mars",
                valeur=dignite_mars,
                bloc="Intime",
                polarite=polarite,
            )
            if not df_mars_etat.empty:
                snippets_mars.append(df_to_snippets(df_mars_etat))

    # Aspects durs à Mars (FILTRÉS)
    aspects_mars = _get_aspects_durs_planete_filtres(theme, "Mars", polarite, bloc="Intime")
    if aspects_mars:
        snippets_mars.extend(aspects_mars)

    if snippets_mars:
        snippets_parts.append("=== MARS : TON DÉSIR & ACTION SEXUELLE ===\n" + "\n".join(snippets_mars))

    # ═══════════════════════════════════════
    # 2) MAISON 8 : Intimité & Fusion
    # ═══════════════════════════════════════
    # [Code identique à l'original - non modifié car pas d'aspects ici]
    
    snippets_m8_sections = []
    signe_8 = _get_signe_maison(theme, 8)
    signe_8_norm = _normalize_signe(signe_8) if isinstance(signe_8, str) else None
    maitres_8 = MAITRES_PAR_SIGNE.get(signe_8_norm, []) if signe_8_norm else []

    if signe_8:
        df_m8_signe = get_from_maisons_amour(
            maison="Maison 8",
            type_donnee="Signe",
            valeur=signe_8,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_m8_signe.empty:
            texte_signe = df_to_snippets(df_m8_signe)
            snippets_m8_sections.append("→ [Signe de ta Maison 8]\n" + texte_signe)

    planetes_en_8 = _get_planetes_en_maison(theme, 8)
    bloc_planetes_m8 = []
    for nom_planete in planetes_en_8:
        df_m8_planete = get_from_maisons_amour(
            maison="Maison 8",
            type_donnee="Planète",
            valeur=nom_planete,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_m8_planete.empty:
            texte_planete = df_to_snippets(df_m8_planete)
            bloc_planetes_m8.append(f"[Planète en M8 : {nom_planete}]\n{texte_planete}")

    if bloc_planetes_m8:
        snippets_m8_sections.append("→ [Planètes présentes en Maison 8]\n" + "\n".join(bloc_planetes_m8))

    # Maîtres de M8
    valeurs_deja_vues = set()
    bloc_maitres_m8 = []

    for nom_maitre in maitres_8:
        infos_maitre = planetes.get(nom_maitre, {}) or {}
        maison_maitre = infos_maitre.get("maison")
        signe_maitre = infos_maitre.get("signe")
        retrograde = infos_maitre.get("retrograde", False)

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()

        if brut in valeurs_deja_vues:
            continue
        valeurs_deja_vues.add(brut)

        df_maitre_8 = get_from_maitre_en_maison(
            maitre_maison="maitre_maison_8",
            type_donnee="Maison",
            valeur=brut,
            bloc="Intime",
            polarite=polarite,
        )
        
        if not df_maitre_8.empty:
            texte_maitre = df_to_snippets(df_maitre_8)
            bloc_txt = [f"[Maître de M8 : {nom_maitre} en Maison {brut}]\n{texte_maitre}"]

            # ⚠️ ANALYSE CRITIQUE DE L'ÉTAT DU MAÎTRE
            if signe_maitre:
                dignite_maitre = get_dignite_planete(nom_maitre, signe_maitre)
                maitre_affaibli = dignite_maitre in ["Chute", "Exil"] or retrograde
                
                if maitre_affaibli:
                    print(f"[INTIMITÉ] ⚠️ ALERTE : Maître de M8 ({nom_maitre}) AFFAIBLI - {dignite_maitre}, rétro={retrograde}")
                    
                    # Construire l'avertissement explicite
                    details_affaiblissement = []
                    if dignite_maitre in ["Chute", "Exil"]:
                        details_affaiblissement.append(f"en {dignite_maitre} en {signe_maitre}")
                    if retrograde:
                        details_affaiblissement.append("rétrograde")
                    
                    texte_affaiblissement = " ET ".join(details_affaiblissement)
                    
                    avertissement_critique = f"""
⚠️ ATTENTION CRITIQUE : Le maître de ta Maison 8 ({nom_maitre}) est {texte_affaiblissement}.

Cela INVERSE COMPLÈTEMENT l'énergie classique de ta Maison 8 en {signe_8}.

Au lieu d'une intimité {signe_8.lower()} (directe, passionnée, intense), tu as plutôt :
- Une sexualité INHIBÉE, freinée, timide
- Du MAL À PASSER À L'ACTE malgré le désir
- Des BLOCAGES ÉMOTIONNELS dans la fusion
- Une CRAINTE de l'abandon ou de la vulnérabilité
- Besoin de SÉCURITÉ AFFECTIVE avant l'intimité physique

→ NE PAS interpréter comme une sexualité fougueuse. C'est l'inverse : hésitation, retenue, peur.
"""
                    bloc_txt.append(avertissement_critique)

            bloc_maitres_m8.append("\n".join(bloc_txt))

    if bloc_maitres_m8:
        snippets_m8_sections.append("→ [Maître(s) de la Maison 8]\n" + "\n\n".join(bloc_maitres_m8))

    if snippets_m8_sections:
        snippets_parts.append(
            "=== MAISON 8 : TON INTIMITÉ & FUSION ===\n"
            + "\n\n".join(snippets_m8_sections)
        )

    # ═══════════════════════════════════════
    # 3) PLUTON (avec filtre maison intime)
    # ═══════════════════════════════════════
    def _is_maison_intime(theme, planete):
        m = _get_maison_planete(theme, planete)
        return m in MAISONS_INTIMES if m else False

    def _pluton_devrait_etre_affiche(theme):
        if _is_maison_intime(theme, "Pluton"):
            return True
        
        # Vérifier aspects durs avec planètes intimes
        aspects_filtres = _filtrer_aspects_durs_intelligents(theme, "Pluton")
        planetes_intimes = [p for p in ["Mars", "Vénus", "Lune", "Soleil", "Lune Noire", "Chiron"]
                            if _is_maison_intime(theme, p)]
        
        for (autre, _, _) in aspects_filtres:
            if autre in planetes_intimes:
                return True
        
        return False

    if _pluton_devrait_etre_affiche(theme):
        pluton_data = planetes.get("Pluton") or {}
        maison_pluton = pluton_data.get("maison")
        snippets_pluton = []

        if maison_pluton is not None:
            valeur_maison = f"Maison_{maison_pluton}"
            df_pluton_maison = get_from_placements(
                planete="Pluton",
                type_donnee="Maison",
                valeur=valeur_maison,
                bloc="Intime",
                polarite=polarite,
            )
            if not df_pluton_maison.empty:
                snippets_pluton.append(df_to_snippets(df_pluton_maison))

        # Aspects durs à Pluton (FILTRÉS)
        aspects_pluton = _get_aspects_durs_planete_filtres(theme, "Pluton", polarite, bloc="Intime")
        if aspects_pluton:
            snippets_pluton.extend(aspects_pluton)

        if snippets_pluton:
            snippets_parts.append("=== PLUTON : TRANSFORMATION & POUVOIR ===\n" + "\n".join(snippets_pluton))

    # ═══════════════════════════════════════
    # 4) CHIRON
    # ═══════════════════════════════════════
    chiron = planetes.get("Chiron", {}) or {}
    maison_chiron = chiron.get("maison")
    snippets_chiron = []

    if maison_chiron is not None:
        valeur_mc = str(maison_chiron).strip()
        df_chiron_maison = get_from_placements(
            planete="Chiron",
            type_donnee="Maison",
            valeur=valeur_mc,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_chiron_maison.empty:
            snippets_chiron.append(df_to_snippets(df_chiron_maison))

    # Aspects critiques à Chiron (FILTRÉS)
    aspects_chiron = _get_aspects_durs_planete_filtres(
        theme,
        planete_cible="Chiron",
        polarite=polarite,
        bloc="Intime",
        planetes_filtrees=("Lune", "Vénus", "Mars", "Soleil"),
        filtrer_par_maison=False,
    )
    if aspects_chiron:
        snippets_chiron.extend(aspects_chiron)

    if snippets_chiron:
        snippets_parts.append(
            "=== CHIRON : BLESSURES INTIMES & VULNÉRABILITÉS ===\n"
            + "\n".join(snippets_chiron)
        )

    # ═══════════════════════════════════════
    # 5) LUNE NOIRE
    # ═══════════════════════════════════════
    lune_noire_data = planetes.get("Lune Noire") or planetes.get("Lilith") or {}
    signe_ln = lune_noire_data.get("signe")
    maison_ln = lune_noire_data.get("maison")
    
    snippets_ln = []

    if signe_ln:
        df_ln_signe = get_from_placements(
            planete="Lune Noire",
            type_donnee="Signe",
            valeur=signe_ln,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_ln_signe.empty:
            snippets_ln.append(df_to_snippets(df_ln_signe))

    if maison_ln is not None:
        valeur_maison = f"Maison_{maison_ln}"
        df_ln_maison = get_from_placements(
            planete="Lune Noire",
            type_donnee="Maison",
            valeur=valeur_maison,
            bloc="Intime",
            polarite=polarite,
        )
        if not df_ln_maison.empty:
            snippets_ln.append(df_to_snippets(df_ln_maison))

    # Aspects durs à Lune Noire (FILTRÉS)
    aspects_ln = _get_aspects_durs_planete_filtres(
        theme,
        "Lune Noire",
        polarite,
        bloc="Intime",
        filtrer_par_maison=False,
    )
    if aspects_ln:
        snippets_ln.extend(aspects_ln)

    if snippets_ln:
        snippets_parts.append("=== LUNE NOIRE : TES DÉSIRS CACHÉS & TABOUS ===\n" + "\n".join(snippets_ln))

    # ═══════════════════════════════════════
    # 6) Assemblage final & LLM
    # ═══════════════════════════════════════
    snippets_bruts = "\n\n".join(s for s in snippets_parts if s).strip()

    if not call_llm:
        return (
            "<pre>MODULE 4 · INTIMITÉ & SEXUALITÉ (FILTRÉ) :\n"
            + (snippets_bruts or "(aucun snippet)")
            + "</pre>"
        )

    if not snippets_bruts:
        return ""

    theme_complet = exporter_theme_complet(theme)
    contexte_amour = generer_contexte_amour(theme)
    consigne_genre = "Adresse-toi au masculin." if polarite == "Homme" else "Adresse-toi au féminin."

    prompt = f"""
On travaille ici le MODULE 4 : "Intimité & Sexualité".
{consigne_genre}

⚠️ RÈGLE CRITIQUE : RESPECTER L'ÉTAT DES MAÎTRES DE MAISON

Si tu vois dans les données un avertissement du type "ATTENTION CRITIQUE : Le maître de ta Maison X est affaibli",
tu DOIS IMPÉRATIVEMENT suivre cette directive et INVERSER l'interprétation classique du signe.

EXEMPLE CONCRET :
- Maison 8 en Bélier (classique = sexualité directe, fougueuse, intense)
- MAIS maître Mars en Cancer chute + rétrograde
- → Tu DOIS écrire : sexualité INHIBÉE, timide, besoin de sécurité, peur de l'abandon
- → Tu NE DOIS PAS écrire : sexualité fougueuse, directe, intense

C'est une RÈGLE ABSOLUE. Un maître affaibli inverse complètement l'énergie de la maison.

Voici un CONTEXTE GLOBAL du thème de la personne, centré sur sa dynamique émotionnelle et relationnelle :

{contexte_amour}

Les éléments suivants décrivent :
- ton désir sexuel et ta façon d'agir physiquement (Mars),
- ton besoin d'intimité profonde et de fusion (Maison 8),
- ta capacité de transformation par l'intensité (Pluton),
- tes désirs cachés, tes tabous et ta sexualité ombre (Lune Noire).

Voici les informations brutes extraites de la base de données :

{snippets_bruts}

À partir de ces éléments, rédige un texte psychologique, clair et incarné qui décrit :
- comment tu vis le désir physique et sexuel,
- ce que tu cherches dans l'intimité et la fusion,
- ton rapport au pouvoir, à l'intensité, à la transformation dans le lien,
- tes tabous, tes blessures ou tes zones d'ombre autour de la sexualité,
- les forces et fragilités de ta vie intime.

Ne parle PAS :
- de l'amour romantique (MODULE 1),
- du partenaire idéal (MODULE 2),
- du couple officiel (MODULE 3).

Reste centré(e) sur l'intimité PHYSIQUE et PROFONDE, le désir charnel, la fusion, les tabous.

Pas de bullet points. Pas d'emoji.
Parle en "tu".
- N’utilise pas de pronom possessif devant les planètes (évite : “ton Mars”, “ta Vénus”, “ta Saturne”).
Ton direct, cash, psychologique, sans pudeur.
"""

    print("\n\n===== PROMPT ENVOYÉ AU LLM =====\n")
    print(prompt)
    print("\n===== FIN PROMPT =====\n")
    
    texte = interroger_llm(prompt)
    return texte