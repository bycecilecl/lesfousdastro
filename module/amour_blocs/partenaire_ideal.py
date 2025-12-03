# module/amour_blocs/partenaire_ideal.py
# VERSION OPTIMISÉE AVEC FILTRAGE INTELLIGENT DES ASPECTS

import logging
from module.amour_bdd import (
    get_from_placements,
    get_from_aspects,
    df_to_snippets,
)
from module.amour_blocs.utils_theme import exporter_theme_complet
from module.amour_blocs.context_amour import generer_contexte_amour

# Configuration du logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def _df_to_interpretations_only(df) -> str:
    """
    Pour ce module Partenaire idéal, on ne prend QUE la colonne INTERPRÉTATION.
    """
    if df is None or df.empty:
        return ""

    df = df.rename(columns={c: c.strip().lower() for c in df.columns})

    if "interpretation" not in df.columns:
        logger.warning(f"[PARTENAIRE] Colonne 'interpretation' absente. Colonnes dispo: {list(df.columns)}")
        return ""

    lignes = []
    for _, row in df.iterrows():
        val = str(row["interpretation"]).strip()
        if val and val.lower() != "nan":
            lignes.append(f"- {val}")
    return "\n".join(lignes)


def _normaliser_nom(nom: str) -> str:
    """Normalise le nom d'une planète ou d'un aspect (capitalize)"""
    if not nom:
        return ""
    # Cas spéciaux
    nom_clean = nom.strip()
    if nom_clean.lower() == "lune noire":
        return "Lune Noire"
    # Capitalisation standard
    return nom_clean.capitalize()


def _get_aspects_reels_du_theme(theme: dict) -> list:
    """
    Extrait les aspects réels présents dans le thème.
    Retourne une liste de tuples (planete_1, planete_2, type_aspect, orbe)
    AVEC NORMALISATION des noms pour éviter les problèmes de casse.
    """
    aspects_list = theme.get("aspects", [])
    print("\n=== DEBUG: TOUS LES ASPECTS DU THÈME ===")
    
    aspects_reels = []
    for asp in aspects_list:
        p1 = asp.get("planete1")
        p2 = asp.get("planete2")
        type_asp = asp.get("aspect")
        orbe = asp.get("orbe", 0)
        print(f"{p1} {type_asp} {p2} (orbe: {orbe}°)")

        
        if p1 and p2 and type_asp:
            # Normalisation
            p1_norm = _normaliser_nom(p1)
            p2_norm = _normaliser_nom(p2)
            type_asp_norm = _normaliser_nom(type_asp)
            
            aspects_reels.append((p1_norm, p2_norm, type_asp_norm, orbe))
    
    logger.debug(f"[PARTENAIRE] {len(aspects_reels)} aspects bruts extraits du thème.")
    return aspects_reels


def _snippets_planetes_partenaires(theme: dict, polarite: str) -> str:
    """
    Bloc 1 : Planètes "partenaire" en SIGNE
    Femme  : Mars + Soleil
    Homme  : Vénus + Lune
    """
    planetes_theme = theme.get("planetes", {}) or theme.get("planètes", {}) or {}

    if polarite == "Femme":
        combos = [("Mars", "Partenaire"), ("Soleil", "Partenaire")]
    else:
        combos = [("Vénus", "Partenaire"), ("Lune", "Partenaire")]

    lignes = []
    logger.info(f"[PARTENAIRE] Recherche des positions en SIGNE pour : {[c[0] for c in combos]}")

    for nom_planete, bloc in combos:
        donnees = planetes_theme.get(nom_planete, {}) or {}
        signe = donnees.get("signe")
        
        if not signe:
            logger.warning(f"[PARTENAIRE] ⚠️ Pas de signe trouvé dans le JSON pour {nom_planete}")
            continue

        df = get_from_placements(
            planete=nom_planete,
            type_donnee="Signe",
            valeur=signe,
            bloc=bloc,
            polarite=polarite,
        )

        if not df.empty:
            logger.info(f"[PARTENAIRE] ✅ Trouvé : {nom_planete} en {signe} ({len(df)} interprétations)")
            txt = _df_to_interpretations_only(df)
            if txt:
                lignes.append(f"=== {nom_planete.upper()} EN {signe.upper()} ===")
                lignes.append(txt)
        else:
            logger.warning(f"[PARTENAIRE] ❌ Rien trouvé en BDD pour {nom_planete} en {signe} (Bloc: {bloc})")

    return "\n".join(lignes).strip()


def _filtrer_aspects_partenaires_intelligent(
    theme: dict,
    planetes_ref: list[str],
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> dict[str, list[tuple[str, str, str, float]]]:
    """
    Filtrage INTELLIGENT des aspects vers les planètes partenaires.
    
    Stratégie :
    - TOUS les aspects serrés (orbe <= orbe_serre) → gardés automatiquement
    - Max 3 aspects avec trans-saturniennes (Pluton/Neptune/Chiron) si orbe > serre
    - Max 2 aspects avec lentes (Saturne/Jupiter/Uranus) si orbe > serre
    - Max 1 autre aspect (planètes rapides)
    
    Résultat : entre 4-7 aspects en moyenne, priorisant les plus importants.
    """
    aspects_reels = _get_aspects_reels_du_theme(theme)
    aspects_majeurs = {"Conjonction", "Carre", "Carré", "Opposition", "Trigone", "Sextile"}
    
    trans_saturniennes = {"Pluton", "Neptune", "Chiron"}
    lentes = {"Saturne", "Uranus", "Jupiter"}
    
    par_planete_ref: dict[str, list] = {ref: [] for ref in planetes_ref}
    
    # 1. COLLECTE BRUTE avec catégorisation
    logger.info(f"[PARTENAIRE] 🔍 Analyse des aspects pour : {planetes_ref}")
    
    for (p1, p2, type_asp, orbe) in aspects_reels:
        if type_asp not in aspects_majeurs:
            logger.debug(f"[PARTENAIRE] ⏭️ Aspect ignoré (type mineur) : {p1} {type_asp} {p2}")
            continue
        if orbe is None or orbe > orbe_max:
            logger.debug(f"[PARTENAIRE] ⏭️ Aspect ignoré (orbe trop large: {orbe}°) : {p1} {type_asp} {p2}")
            continue
        
        for ref in planetes_ref:
            if ref not in (p1, p2):
                continue
            
            autre = p2 if p1 == ref else p1
            
            # LOG: Aspect détecté AVANT filtrage
            logger.info(f"[PARTENAIRE] 📊 Aspect DÉTECTÉ : {ref} {type_asp} {autre} (orbe {orbe:.1f}°)")
            
            # Catégoriser l'aspect
            if orbe <= orbe_serre:
                categorie = "serré"
            elif autre in trans_saturniennes:
                categorie = "trans"
            elif autre in lentes:
                categorie = "lent"
            else:
                categorie = "autre"
            
            par_planete_ref[ref].append({
                "autre": autre,
                "type": type_asp,
                "orbe": orbe,
                "categorie": categorie
            })
    
    # 2. TRI ET SÉLECTION PAR CATÉGORIE
    resultat = {}
    
    for ref, aspects_list in par_planete_ref.items():
        if not aspects_list:
            continue
        
        # Tri par orbe (plus serré = prioritaire)
        aspects_list.sort(key=lambda x: x["orbe"])
        
        selection = []
        count_trans = 0
        count_lent = 0
        count_autre = 0
        
        for asp in aspects_list:
            cat = asp["categorie"]
            autre = asp["autre"]
            
            if cat == "serré":
                # TOUS les aspects serrés sont TOUJOURS gardés
                selection.append((ref, autre, asp["type"], asp["orbe"]))
                logger.info(f"[PARTENAIRE] ✅ Aspect SERRÉ gardé : {ref} {asp['type']} {autre} (orbe {asp['orbe']:.1f}°)")
            
            elif cat == "trans" and count_trans < 3:
                # Max 3 trans-saturniennes (Pluton/Neptune/Chiron)
                selection.append((ref, autre, asp["type"], asp["orbe"]))
                count_trans += 1
                logger.info(f"[PARTENAIRE] ✅ Aspect TRANS gardé : {ref} {asp['type']} {autre} (orbe {asp['orbe']:.1f}°)")
            
            elif cat == "lent" and count_lent < 2:
                # Max 2 lentes (Saturne/Jupiter/Uranus)
                selection.append((ref, autre, asp["type"], asp["orbe"]))
                count_lent += 1
                logger.info(f"[PARTENAIRE] ✅ Aspect LENT gardé : {ref} {asp['type']} {autre} (orbe {asp['orbe']:.1f}°)")
            
            elif cat == "autre" and count_autre < 1:
                # Max 1 autre (planètes rapides)
                selection.append((ref, autre, asp["type"], asp["orbe"]))
                count_autre += 1
                logger.info(f"[PARTENAIRE] ✅ Aspect AUTRE gardé : {ref} {asp['type']} {autre} (orbe {asp['orbe']:.1f}°)")
            
            else:
                logger.debug(f"[PARTENAIRE] ⏭️ Aspect écarté (quota atteint) : {ref} {asp['type']} {autre} (orbe {asp['orbe']:.1f}°)")
        
        resultat[ref] = selection
    
    return resultat


def _snippets_aspects_planetes_partenaires(theme: dict, polarite: str) -> str:
    """
    Bloc 2 : Aspects MAJEURS et PERTINENTS vers les planètes partenaires,
    filtrés intelligemment.

    Femme  : Mars + Soleil
    Homme  : Vénus + Lune
    """
    if polarite == "Femme":
        planetes_ref = ["Mars", "Soleil"]
    else:
        planetes_ref = ["Vénus", "Lune"]

    # On récupère les aspects filtrés intelligemment
    aspects_sel = _filtrer_aspects_partenaires_intelligent(theme, planetes_ref)

    lignes = []
    aspects_traites = set()  # Pour éviter les doublons Mars–Pluton / Pluton–Mars

    logger.info(f"[PARTENAIRE] Aspects sélectionnés (après filtre intelligent) : {aspects_sel}")

    for p_ref in planetes_ref:
        lst = aspects_sel.get(p_ref, [])
        if not lst:
            continue

        section_aspects = []

        for (ref, autre_planete, type_asp, orbe) in lst:
            key = tuple(sorted([ref, autre_planete])) + (type_asp,)
            if key in aspects_traites:
                continue
            aspects_traites.add(key)

            # On cherche le texte en BDD dans les deux sens
            df = get_from_aspects(
                planete_1=ref,
                planete_2=autre_planete,
                valeur=type_asp,
                bloc="Partenaire",
                polarite=polarite,
            )
            if df.empty:
                df = get_from_aspects(
                    planete_1=autre_planete,
                    planete_2=ref,
                    valeur=type_asp,
                    bloc="Partenaire",
                    polarite=polarite,
                )

            if not df.empty:
                logger.info(f"[PARTENAIRE] ✅ Aspect interprété : {ref} {type_asp} {autre_planete} (orbe {orbe:.1f}°)")
                txt = _df_to_interpretations_only(df)
                if txt:
                    section_aspects.append(
                        f"• {ref} {type_asp} {autre_planete} (orbe {orbe:.1f}°) :\n{txt}"
                    )
            else:
                logger.debug(f"[PARTENAIRE] (Ignoré) Pas de texte en BDD pour {ref} {type_asp} {autre_planete}")

        if section_aspects:
            lignes.append(f"=== ASPECTS MAJEURS À {p_ref.upper()} ===")
            lignes.extend(section_aspects)

    return "\n".join(lignes).strip()


def generer_bloc_partenaire_ideal(theme: dict, call_llm: bool = True, polarite: str = "Femme") -> str:
    """
    MODULE 2 : PARTENAIRE IDÉAL
    Génération avec filtrage intelligent des aspects pour éviter la surcharge.
    """
    if polarite not in ("Femme", "Homme"):
        logger.warning(f"[PARTENAIRE] Polarité '{polarite}' inconnue, défaut sur Femme")
        polarite = "Femme"

    logger.info(f"--- DÉBUT GÉNÉRATION MODULE PARTENAIRE ({polarite}) ---")
    
    snippets_sections = []

    # 1) Planètes partenaires en signe
    txt_planetes = _snippets_planetes_partenaires(theme, polarite)
    if txt_planetes: 
        snippets_sections.append(txt_planetes)

    # 2) Aspects majeurs (filtrés intelligemment)
    txt_aspects = _snippets_aspects_planetes_partenaires(theme, polarite)
    if txt_aspects: 
        snippets_sections.append(txt_aspects)

    snippets_bruts = "\n\n".join(s for s in snippets_sections if s).strip()
    
    logger.info(f"--- FIN EXTRACTION --- Taille snippets: {len(snippets_bruts)} chars")

    # Mode debug (sans LLM)
    if not call_llm:
        return (
            "<pre>MODULE 2 · PARTENAIRE IDÉAL (SNIPPETS FILTRÉS INTELLIGEMMENT) :\n"
            + (snippets_bruts or "(rien)")
            + "</pre>"
        )

    if not snippets_bruts:
        logger.warning("[PARTENAIRE] Aucun snippet généré, pas d'appel LLM.")
        return ""

    # === PROMPT LLM ===
    genre_txt = "d'homme" if polarite == "Femme" else "de femme"
    theme_complet = exporter_theme_complet(theme)
    contexte_amour = generer_contexte_amour(theme)
    consigne_genre = "Adresse-toi au masculin." if polarite == "Homme" else "Adresse-toi au féminin."

    prompt = f"""
Tu es une astrologue experte en psychologie des relations. On travaille le MODULE 2 : "Quel type de partenaire t'attire".
{consigne_genre}

Voici un CONTEXTE GLOBAL du thème de la personne, centré sur sa dynamique émotionnelle et relationnelle :

{contexte_amour}

CONTEXTE :
Ce module parle UNIQUEMENT du PORTRAIT de l'autre — la personne qui te fait vibrer, ton "type", tes projections.
On ne parle PAS ici de comment le couple fonctionne (c'est le Module 3).

DONNÉES ASTROLOGIQUES :
{snippets_bruts}

CONSIGNES :
À partir de ces éléments, rédige un texte INTENSE et INCARNÉ qui décrit :

1) **Le type {genre_txt} qui t'attire** : son énergie, sa vibe, son charisme, ce qui te fait flasher
2) **Ce que tu projettes sur l'autre** : tes attentes inconscientes, ce que tu cherches à travers lui/elle
3) **Les schémas d'attraction** : le genre de profils que tu répètes, pourquoi
4) **Les forces et les pièges** : ce qui fonctionne dans tes choix vs ce qui te fait tomber dans le panneau
5) **L'intensité particulière** : si Pluton/Neptune/Chiron sont impliqués, explore le magnétisme fatal, l'idéalisation, ou les blessures qui attirent

STYLE :
- Parle en "tu", ton direct et cash, pas de langue de bois
- Psychologique et profond, pas superficiel
- Pas de bullet points, pas d'emoji
- Fais une synthèse fluide, pas un collage de phrases
- Ose nommer les zones d'ombre sans complaisance
- Environ 400-500 mots

NE PARLE PAS de :
- Comment le couple fonctionne au quotidien
- L'engagement, le mariage, la Maison 7
- Les conflits ou la dynamique relationnelle
- Ce sera traité dans le Module 3
"""

    print("\n\n===== PROMPT ENVOYÉ AU LLM =====\n")
    print(prompt)
    print("\n===== FIN PROMPT =====\n")

    from utils.openai_utils import interroger_llm
    logger.info("[PARTENAIRE] Appel LLM en cours...")
    texte = interroger_llm(prompt)
    logger.info("[PARTENAIRE] Réponse LLM reçue.")
    return texte