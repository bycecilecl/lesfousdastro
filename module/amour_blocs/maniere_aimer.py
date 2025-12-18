# module/amour_blocs/maniere_aimer.py
# MODULE 1 : Ma manière d'aimer avec FILTRAGE INTELLIGENT des aspects

import logging
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
from utils.openai_utils import interroger_llm
from module.amour_blocs.dignites import get_dignite_planete
from module.amour_blocs.utils_theme import exporter_theme_complet
from module.amour_blocs.context_amour import generer_contexte_amour

# Configuration du logger
logger = logging.getLogger(__name__)


    

def _normalize_house_value(maison):
    """
    Normalise un numéro de maison pour matcher placements.csv.
    Ex: 11, 11.0, "11", "11.0" -> "11"
    """
    if maison is None:
        return None
    try:
        maison_int = int(float(str(maison).strip()))
        return str(maison_int)
    except (ValueError, TypeError):
        return None


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


def _get_aspects_reels_du_theme(theme: dict) -> list[tuple[str, str, str, float]]:
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


def _filtrer_aspects_intelligents(
    theme: dict,
    planete_cible: str,
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> list[tuple[str, str, float]]:
    """
    Filtre intelligent des aspects pour le Module 1 (Manière d'aimer).
    
    Stratégie :
    - TOUS les aspects serrés (≤ 5°) avec aspects majeurs
    - Max 3 trans-saturniennes
    - Max 2 lentes
    - Max 1 autre
    
    Retourne : liste de (autre_planete, type_aspect, orbe)
    """
    aspects_reels = _get_aspects_reels_du_theme(theme)
    aspects_majeurs = ["Conjonction", "Carre", "Carré", "Opposition", "Trigone", "Sextile"]
    
    trans_saturniennes = {"Pluton", "Neptune", "Chiron", "Lune Noire", "Lilith"}
    lentes = {"Saturne", "Uranus", "Jupiter"}
    
    candidats = []
    
    for (p1, p2, type_asp, orbe) in aspects_reels:
        if type_asp not in aspects_majeurs:
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
            logger.info(f"[M1] ✅ Aspect {planete_cible} SERRÉ gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "trans" and count_trans < 3:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_trans += 1
            logger.info(f"[M1] ✅ Aspect {planete_cible} TRANS gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "lent" and count_lent < 2:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_lent += 1
            logger.info(f"[M1] ✅ Aspect {planete_cible} LENT gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "autre" and count_autre < 1:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_autre += 1
            logger.info(f"[M1] ✅ Aspect {planete_cible} AUTRE gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        else:
            logger.debug(f"[M1] ⏭️ Aspect {planete_cible} écarté (quota atteint) : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
    
    return selection


def _get_aspects_majeurs_planete_filtres(
    theme: dict,
    nom_planete: str,
    polarite: str,
    bloc: str = "Style",
) -> str:
    """
    VERSION FILTRÉE : Récupère les aspects majeurs filtrés intelligemment.
    """
    aspects_filtres = _filtrer_aspects_intelligents(theme, nom_planete)
    
    snippets_aspects = []
    
    for (autre_planete, type_asp, orbe) in aspects_filtres:
        # Chercher dans la BDD
        df = get_from_aspects(
            planete_1=nom_planete,
            planete_2=autre_planete,
            valeur=type_asp,
            bloc=bloc,
            polarite=polarite,
        )

        if df.empty:
            df = get_from_aspects(
                planete_1=autre_planete,
                planete_2=nom_planete,
                valeur=type_asp,
                bloc=bloc,
                polarite=polarite,
            )
        
        if not df.empty:
            txt = df_to_snippets(df)
            if txt:
                snippets_aspects.append(txt)

    return "\n".join(snippets_aspects) if snippets_aspects else ""


def _filtrer_aspects_maitre5_intelligents(
    theme: dict,
    nom_maitre: str,
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> list[tuple[str, str, float]]:
    """
    Filtre intelligent des aspects du Maître de 5 (même logique que Maître de 7).
    """
    aspects_reels = _get_aspects_reels_du_theme(theme)
    aspects_majeurs = ["Conjonction", "Carre", "Carré", "Opposition", "Trigone", "Sextile"]
    
    trans_saturniennes = {"Pluton", "Neptune", "Chiron", "Lune Noire", "Lilith"}
    lentes = {"Saturne", "Uranus", "Jupiter"}
    
    candidats = []
    
    for (p1, p2, type_asp, orbe) in aspects_reels:
        if type_asp not in aspects_majeurs:
            continue
        if orbe is None or orbe > orbe_max:
            continue
        
        if nom_maitre not in (p1, p2):
            continue
        
        autre = p2 if p1 == nom_maitre else p1
        
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
            logger.info(f"[M1] ✅ Aspect Maître 5 SERRÉ gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "trans" and count_trans < 3:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_trans += 1
            logger.info(f"[M1] ✅ Aspect Maître 5 TRANS gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "lent" and count_lent < 2:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_lent += 1
            logger.info(f"[M1] ✅ Aspect Maître 5 LENT gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "autre" and count_autre < 1:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_autre += 1
            logger.info(f"[M1] ✅ Aspect Maître 5 AUTRE gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        else:
            logger.debug(f"[M1] ⏭️ Aspect Maître 5 écarté (quota atteint) : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
    
    return selection


def generer_snippets_maniere_aimer(theme: dict, polarite: str = "Homme") -> str:
    """
    Version SNIPPETS du Module 1.
    Retourne UNIQUEMENT les extraits techniques (Vénus, Mars, Lune, Maison 5, maître de 5…)
    SANS LLM, SANS style rédactionnel.
    Utilisé pour guider le Module 3 (Couple).
    """

    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    snippets_parts = []

    # === 1) VÉNUS : langage amoureux ===
    venus_data = planetes.get("Vénus") or planetes.get("Venus") or {}
    signe_venus = venus_data.get("signe")
    maison_venus = venus_data.get("maison")

    snippets_venus = []

    if signe_venus:
        df_venus_signe = get_from_placements("Vénus", "Signe", signe_venus, "Style", polarite)
        if not df_venus_signe.empty:
            snippets_venus.append(df_to_snippets(df_venus_signe))

    valeur_maison = _normalize_house_value(maison_venus)
    if valeur_maison:
        df_venus_maison = get_from_placements("Vénus", "Maison", valeur_maison, "Style", polarite)
        if not df_venus_maison.empty:
            snippets_venus.append(df_to_snippets(df_venus_maison))

    aspects_venus = _get_aspects_majeurs_planete_filtres(theme, "Vénus", polarite, "Style")
    if aspects_venus:
        snippets_venus.append(aspects_venus)

    if signe_venus:
        dignite = get_dignite_planete("Vénus", signe_venus)
        if dignite in ["Chute", "Exil"]:
            df_etat = get_from_etat_planete("Vénus", dignite, "Style", polarite)
            if not df_etat.empty:
                snippets_venus.append(df_to_snippets(df_etat))

    if snippets_venus:
        details = []
        if signe_venus:
            details.append(signe_venus)
        if maison_venus is not None:
            details.append(f"Maison {maison_venus}")

        header = "=== VÉNUS"
        if details:
            header += " (" + ", ".join(details) + ")"
        header += " ==="

        snippets_parts.append(header + "\n" + "\n".join(snippets_venus))


    # === 2) MARS : action amoureuse ===
    mars_data = planetes.get("Mars") or {}
    signe_mars = mars_data.get("signe")
    maison_mars = mars_data.get("maison")

    snippets_mars = []

    if signe_mars:
        df_mars_signe = get_from_placements("Mars", "Signe", signe_mars, "Style", polarite)
        if not df_mars_signe.empty:
            snippets_mars.append(df_to_snippets(df_mars_signe))

    if maison_mars is not None:
        brut = str(maison_mars).strip()
        df_mars_maison = get_from_placements("Mars", "Maison", f"Maison_{brut}", "Style", polarite)
        if not df_mars_maison.empty:
            snippets_mars.append(df_to_snippets(df_mars_maison))

    aspects_mars = _get_aspects_majeurs_planete_filtres(theme, "Mars", polarite, "Style")
    if aspects_mars:
        snippets_mars.append(aspects_mars)

    if signe_mars:
        dignite = get_dignite_planete("Mars", signe_mars)
        if dignite in ["Chute", "Exil"]:
            df_etat = get_from_etat_planete("Mars", dignite, "Style", polarite)
            if not df_etat.empty:
                snippets_mars.append(df_to_snippets(df_etat))

    if snippets_mars:
        details = []
        if signe_mars:
            details.append(signe_mars)
        if maison_mars is not None:
            details.append(f"Maison {maison_mars}")

        header = "=== MARS"
        if details:
            header += " (" + ", ".join(details) + ")"
        header += " ==="

        snippets_parts.append(header + "\n" + "\n".join(snippets_mars))


    # === 3) LUNE : besoins émotionnels ===
    lune_data = planetes.get("Lune") or {}
    signe_lune = lune_data.get("signe")
    maison_lune = lune_data.get("maison")

    snippets_lune = []

    if signe_lune:
        df_lune_signe = get_from_placements("Lune", "Signe", signe_lune, "Style", polarite)
        if not df_lune_signe.empty:
            snippets_lune.append(df_to_snippets(df_lune_signe))

    if maison_lune is not None:
        brut = str(maison_lune).strip()
        df_lune_maison = get_from_placements("Lune", "Maison", f"Maison_{brut}", "Style", polarite)
        if not df_lune_maison.empty:
            snippets_lune.append(df_to_snippets(df_lune_maison))

    aspects_lune = _get_aspects_majeurs_planete_filtres(theme, "Lune", polarite, "Style")
    if aspects_lune:
        snippets_lune.append(aspects_lune)

    if snippets_lune:
        details = []
        if signe_lune:
            details.append(signe_lune)
        if maison_lune is not None:
            details.append(f"Maison {maison_lune}")

        header = "=== LUNE"
        if details:
            header += " (" + ", ".join(details) + ")"
        header += " ==="

        snippets_parts.append(header + "\n" + "\n".join(snippets_lune))


    # === 4) MAISON 5 : désir, jeu amoureux ===
    snippets_m5 = []

    signe_5 = _get_signe_maison(theme, 5)
    if signe_5:
        df_m5_signe = get_from_maisons_amour("Maison 5", "Signe", signe_5, "Style", polarite)
        if not df_m5_signe.empty:
            snippets_m5.append(df_to_snippets(df_m5_signe))

    planetes_en_5 = _get_planetes_en_maison(theme, 5)
    for nom_planete in planetes_en_5:
        df_m5_planete = get_from_maisons_amour("Maison 5", "Planète", nom_planete, "Style", polarite)
        if not df_m5_planete.empty:
            snippets_m5.append(df_to_snippets(df_m5_planete))

    # Maître(s) de 5 (FILTRÉ)
    signe_norm = _normalize_signe(signe_5) if isinstance(signe_5, str) else None
    maitres_5 = MAITRES_PAR_SIGNE.get(signe_norm, [])

    for nom_maitre in maitres_5:
        infos = planetes.get(nom_maitre, {})
        maison_maitre = infos.get("maison")
        signe_maitre = infos.get("signe")

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()
        df_maitre_5 = get_from_maitre_en_maison("maitre_maison_5", "Maison", brut, "Style", polarite)
        if not df_maitre_5.empty:
            snippets_m5.append(df_to_snippets(df_maitre_5))

        if signe_maitre:
            dignite = get_dignite_planete(nom_maitre, signe_maitre)
            if dignite in ["Chute", "Exil"]:
                snippets_m5.append(
                    f"(Maître de 5 {nom_maitre} en {signe_maitre}, dignité {dignite})"
                )

        # Aspects du maître de 5 (FILTRÉ)
        aspects_filtres = _filtrer_aspects_maitre5_intelligents(theme, nom_maitre)
        
        for (autre, type_asp, orbe) in aspects_filtres:
            if type_asp == "Conjonction":
                val = "Conjonction"
            elif type_asp in ("Carre", "Opposition"):
                val = "Carré / Opposition"
            else:
                val = "Trigone / Sextile"

            df_asp = get_from_aspects("maitre_maison_5", autre, val, "Style", polarite)
            if not df_asp.empty:
                snippets_m5.append(df_to_snippets(df_asp))

    if snippets_m5:
        details = []
        if signe_5:
            details.append(f"Signe {signe_5}")
        if planetes_en_5:
            details.append("Planètes : " + ", ".join(planetes_en_5))

        header = "=== MAISON 5"
        if details:
            header += " (" + " | ".join(details) + ")"
        header += " ==="

        snippets_parts.append(header + "\n" + "\n".join(snippets_m5))

    # === 5) NŒUD NORD ===
    noeud = planetes.get("Nœud Nord") or planetes.get("Rahu") or {}
    signe_nn = noeud.get("signe")

    if signe_nn:
        df_nn = get_from_placements("Noeud Nord", "Signe", signe_nn, "Evolution", polarite)
        if not df_nn.empty:
            snippets_parts.append("=== NŒUD NORD ===\n" + df_to_snippets(df_nn))

    # Assemblage final
    return "\n".join(snippets_parts).strip() or ""


def generer_bloc_maniere_aimer(theme: dict, call_llm: bool = True, polarite: str = "Homme") -> str:
    """
    MODULE 1 · Ma manière d'aimer avec FILTRAGE INTELLIGENT

    Contenu :
      - Vénus : signe + maison + aspects majeurs FILTRÉS + état
      - Mars : signe + maison + aspects majeurs FILTRÉS + état
      - Lune : signe + maison + aspects majeurs FILTRÉS
      - Maison 5 : signe + planètes + maître(s) FILTRÉS
    """
    logger.info(f"--- DÉBUT GÉNÉRATION MODULE 1: MANIÈRE D'AIMER ({polarite}) ---")
    
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    snippets_parts = []

    # ═════════════════════════════════════════
    # 1) VÉNUS : langage amoureux
    # ═════════════════════════════════════════
    venus_data = planetes.get("Vénus") or planetes.get("Venus") or {}
    signe_venus = venus_data.get("signe")
    maison_venus = venus_data.get("maison")

    valeur_maison = _normalize_house_value(maison_venus)

    logger.info(f"[AMOUR M1] Vénus en {signe_venus}, Maison {maison_venus}")
    logger.info(f"[AMOUR M1] Valeur maison Vénus envoyée BDD: {valeur_maison}")
    
    snippets_venus = []

    if signe_venus:
        df_venus_signe = get_from_placements(
            planete="Vénus",
            type_donnee="Signe",
            valeur=signe_venus,
            bloc="Style",
            polarite=polarite,
        )
        if not df_venus_signe.empty:
            snippets_venus.append(df_to_snippets(df_venus_signe))

    valeur_maison = _normalize_house_value(maison_venus)
    if valeur_maison:
        df_venus_maison = get_from_placements(
            planete="Vénus",
            type_donnee="Maison",
            valeur=valeur_maison,
            bloc="Style",
            polarite=polarite,
        )
        if not df_venus_maison.empty:
            snippets_venus.append(df_to_snippets(df_venus_maison))

    # Aspects majeurs à Vénus (FILTRÉS)
    aspects_venus = _get_aspects_majeurs_planete_filtres(theme, "Vénus", polarite, bloc="Style")
    if aspects_venus:
        snippets_venus.append(aspects_venus)

    if signe_venus:
        dignite_venus = get_dignite_planete("Vénus", signe_venus)
        if dignite_venus in ["Chute", "Exil"]:
            logger.info(f"[AMOUR M1] Vénus en {dignite_venus} ({signe_venus})")
            df_venus_etat = get_from_etat_planete(
                planete_1="Vénus",
                valeur=dignite_venus,
                bloc="Style",
                polarite=polarite,
            )
            if not df_venus_etat.empty:
                snippets_venus.append(df_to_snippets(df_venus_etat))

    if snippets_venus:
        snippets_parts.append("=== VÉNUS : TA MANIÈRE D'AIMER ===\n" + "\n".join(snippets_venus))

    # ═════════════════════════════════════════
    # 2) MARS : action, initiative amoureuse
    # ═════════════════════════════════════════
    mars_data = planetes.get("Mars") or {}
    signe_mars = mars_data.get("signe")
    maison_mars = mars_data.get("maison")
    
    logger.info(f"[AMOUR M1] Mars en {signe_mars}, Maison {maison_mars}")
    
    snippets_mars = []

    if signe_mars:
        df_mars_signe = get_from_placements(
            planete="Mars",
            type_donnee="Signe",
            valeur=signe_mars,
            bloc="Style",
            polarite=polarite,
        )
        if not df_mars_signe.empty:
            snippets_mars.append(df_to_snippets(df_mars_signe))

    if maison_mars is not None:
        brut = str(maison_mars).strip()
        valeur_maison = f"Maison_{brut}" if brut.isdigit() else brut
        
        df_mars_maison = get_from_placements(
            planete="Mars",
            type_donnee="Maison",
            valeur=valeur_maison,
            bloc="Style",
            polarite=polarite,
        )
        if not df_mars_maison.empty:
            snippets_mars.append(df_to_snippets(df_mars_maison))

    # Aspects majeurs à Mars (FILTRÉS)
    aspects_mars = _get_aspects_majeurs_planete_filtres(theme, "Mars", polarite, bloc="Style")
    if aspects_mars:
        snippets_mars.append(aspects_mars)

    if signe_mars:
        dignite_mars = get_dignite_planete("Mars", signe_mars)
        if dignite_mars in ["Chute", "Exil"]:
            logger.info(f"[AMOUR M1] Mars en {dignite_mars} ({signe_mars})")
            df_mars_etat = get_from_etat_planete(
                planete_1="Mars",
                valeur=dignite_mars,
                bloc="Style",
                polarite=polarite,
            )
            if not df_mars_etat.empty:
                snippets_mars.append(df_to_snippets(df_mars_etat))

    if snippets_mars:
        snippets_parts.append("=== MARS : TON INITIATIVE & DÉSIR ===\n" + "\n".join(snippets_mars))

    # ═════════════════════════════════════════
    # 3) LUNE : besoins émotionnels
    # ═════════════════════════════════════════
    lune_data = planetes.get("Lune") or {}
    signe_lune = lune_data.get("signe")
    maison_lune = lune_data.get("maison")

    logger.info(f"[AMOUR M1] Lune en {signe_lune}, Maison {maison_lune}")

    snippets_lune = []

    if signe_lune:
        df_lune = get_from_placements(
            planete="Lune",
            type_donnee="Signe",
            valeur=signe_lune,
            bloc="Style",
            polarite=polarite,
        )
        if not df_lune.empty:
            txt_lune = df_to_snippets(df_lune)
            if txt_lune:
                snippets_lune.append(txt_lune)

    if maison_lune is not None:
        brut = str(maison_lune).strip()
        valeur_maison = f"Maison_{brut}" if brut.isdigit() else brut
        
        df_lune_maison = get_from_placements(
            planete="Lune",
            type_donnee="Maison",
            valeur=valeur_maison,
            bloc="Style",
            polarite=polarite,
        )
        if not df_lune_maison.empty:
            snippets_lune.append(df_to_snippets(df_lune_maison))

    # Aspects majeurs à la Lune (FILTRÉS)
    aspects_lune = _get_aspects_majeurs_planete_filtres(
        theme,
        nom_planete="Lune",
        polarite=polarite,
        bloc="Style",
    )
    if aspects_lune:
        snippets_lune.append(aspects_lune)

    if snippets_lune:
        snippets_parts.append(
            "=== LUNE : TES BESOINS ÉMOTIONNELS ===\n" + "\n".join(snippets_lune)
        )

    # ═════════════════════════════════════════
    # 4) MAISON 5 : style amoureux, séduction
    # ═════════════════════════════════════════
    snippets_m5 = []

    signe_5 = _get_signe_maison(theme, 5)
    signe_5_norm = _normalize_signe(signe_5) if isinstance(signe_5, str) else None
    maitres_5 = MAITRES_PAR_SIGNE.get(signe_5_norm, []) if signe_5_norm else []

    logger.info(f"[AMOUR M1] Maison 5 en {signe_5} (Maîtres: {maitres_5})")

    if signe_5:
        df_m5_signe = get_from_maisons_amour(
            maison="Maison 5",
            type_donnee="Signe",
            valeur=signe_5,
            bloc="Style",
            polarite=polarite,
        )
        if not df_m5_signe.empty:
            snippets_m5.append(df_to_snippets(df_m5_signe))

    planetes_en_5 = _get_planetes_en_maison(theme, 5)
    if planetes_en_5:
        logger.info(f"[AMOUR M1] Planètes en M5: {planetes_en_5}")

    for nom_planete in planetes_en_5:
        df_m5_planete = get_from_maisons_amour(
            maison="Maison 5",
            type_donnee="Planète",
            valeur=nom_planete,
            bloc="Style",
            polarite=polarite,
        )
        if not df_m5_planete.empty:
            snippets_m5.append(df_to_snippets(df_m5_planete))

    # Maître(s) de la Maison 5 (FILTRÉ)
    valeurs_deja_vues = set()
    for nom_maitre in maitres_5:
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

        df_maitre_5 = get_from_maitre_en_maison(
            maitre_maison="maitre_maison_5",
            type_donnee="Maison",
            valeur=brut,
            bloc="Style",
            polarite=polarite,
        )
        if not df_maitre_5.empty:
            snippets_m5.append(df_to_snippets(df_maitre_5))

        # ⚠️ ANALYSE CRITIQUE DE L'ÉTAT DU MAÎTRE
        if signe_maitre:
            dignite_maitre_5 = get_dignite_planete(nom_maitre, signe_maitre)
            maitre_affaibli = dignite_maitre_5 in ("Chute", "Exil") or retrograde
            
            if maitre_affaibli:
                logger.info(f"[AMOUR M1] ⚠️ ALERTE : Maître de M5 ({nom_maitre}) AFFAIBLI - {dignite_maitre_5}, rétro={retrograde}")
                
                # Construire l'avertissement explicite
                details_affaiblissement = []
                if dignite_maitre_5 in ("Chute", "Exil"):
                    details_affaiblissement.append(f"en {dignite_maitre_5} en {signe_maitre}")
                if retrograde:
                    details_affaiblissement.append("rétrograde")
                
                texte_affaiblissement = " ET ".join(details_affaiblissement)
                
                avertissement_critique = f"""
⚠️ ATTENTION CRITIQUE : Le maître de ta Maison 5 ({nom_maitre}) est {texte_affaiblissement}.

Cela INVERSE COMPLÈTEMENT l'énergie classique de ta Maison 5 en {signe_5}.

Au lieu d'un style amoureux {signe_5.lower()} (spontané, créatif, joueur), tu as plutôt :
- Une DIFFICULTÉ À TE LÂCHER en amour
- Le sentiment de DEVOIR MÉRITER l'affection
- Une RETENUE dans l'expression de tes sentiments
- Une PEUR du rejet ou du ridicule
- Besoin de SÉCURITÉ avant de montrer ton cœur

→ NE PAS interpréter comme un style spontané et léger. C'est l'inverse : hésitation, retenue, autocensure.
"""
                snippets_m5.append(avertissement_critique)

        # Aspects du maître de 5 (FILTRÉS)
        aspects_filtres = _filtrer_aspects_maitre5_intelligents(theme, nom_maitre)
        
        for (autre, type_asp, orbe) in aspects_filtres:
            if type_asp == "Conjonction":
                valeur_csv = "Conjonction"
            elif type_asp in ("Carre", "Opposition"):
                valeur_csv = "Carré / Opposition"
            else:
                valeur_csv = "Trigone / Sextile"

            df_m5_aspect = get_from_aspects(
                planete_1="maitre_maison_5",
                planete_2=autre,
                valeur=valeur_csv,
                bloc="Style",
                polarite=polarite,
            )

            if not df_m5_aspect.empty:
                snippets_m5.append(
                    f"=== ASPECT DU MAÎTRE DE 5 ({nom_maitre.upper()} {type_asp.upper()} {autre.upper()}) ===\n"
                    + df_to_snippets(df_m5_aspect)
                )

    if snippets_m5:
        snippets_parts.append("=== MAISON 5 : TON STYLE AMOUREUX ===\n" + "\n".join(snippets_m5))

    # ═════════════════════════════════════════
    # 5) NŒUD NORD : axe d'évolution affective
    # ═════════════════════════════════════════
    noeud_nord = planetes.get("Nœud Nord") or planetes.get("Rahu") or {}
    signe_nn = noeud_nord.get("signe")

    snippets_nn = []

    if signe_nn:
        df_nn = get_from_placements(
            planete="Noeud Nord",
            type_donnee="Signe",
            valeur=signe_nn,
            bloc="Evolution",
            polarite=polarite,
        )
        if not df_nn.empty:
            snippets_nn.append(df_to_snippets(df_nn))

    if snippets_nn:
        snippets_parts.append(
            "=== NŒUD NORD : TON AXE D'ÉVOLUTION AFFECTIVE ===\n"
            + "\n".join(snippets_nn)
        )

    # ═════════════════════════════════════════
    # ASSEMBLAGE FINAL
    # ═════════════════════════════════════════
    snippets_bruts = "\n".join(s for s in snippets_parts if s).strip()
    
    logger.info(f"--- FIN MODULE 1 --- Taille snippets: {len(snippets_bruts)} chars")

    if not call_llm:
        return (
            "<pre>MODULE 1 · MA MANIÈRE D'AIMER (FILTRÉ) :\n"
            + (snippets_bruts or "(aucun snippet trouvé)")
            + "</pre>"
        )

    if not snippets_bruts:
        logger.warning("[AMOUR M1] Aucun snippet, pas d'appel LLM.")
        return ""

    # ═════════════════════════════════════════
    # PROMPT LLM
    # ═════════════════════════════════════════
    theme_complet = exporter_theme_complet(theme)
    contexte_amour = generer_contexte_amour(theme)
    consigne_genre = "Adresse-toi au masculin." if polarite == "Homme" else "Adresse-toi au féminin."

    prompt = f"""
On travaille ici le MODULE 1 : "Ma manière d'aimer".
{consigne_genre}

⚠️ RÈGLE CRITIQUE : RESPECTER L'ÉTAT DES MAÎTRES DE MAISON

Si tu vois dans les données un avertissement du type "ATTENTION CRITIQUE : Le maître de ta Maison X est affaibli",
tu DOIS IMPÉRATIVEMENT suivre cette directive et INVERSER l'interprétation classique du signe.

EXEMPLE CONCRET :
- Maison 5 en Sagittaire (classique = style amoureux spontané, léger, joueur, aventureux)
- MAIS maître Jupiter en Capricorne chute + rétrograde
- → Tu DOIS écrire : difficulté à te lâcher, retenue dans l'expression des sentiments, besoin de sécurité avant de montrer ton cœur
- → Tu NE DOIS PAS écrire : style spontané, léger, joueur, aventureux

C'est une RÈGLE ABSOLUE. Un maître affaibli inverse complètement l'énergie de la maison.

Voici un CONTEXTE GLOBAL du thème de la personne, centré sur sa dynamique émotionnelle et relationnelle :

{contexte_amour}

Les éléments suivants décrivent :
- ton langage amoureux (Vénus : comment tu aimes, ce qui te touche, tes valeurs affectives),
- ton initiative et ton désir (Mars : comment tu agis en amour, comment tu séduis),
- tes besoins émotionnels profonds (Lune : ce qui te sécurise, te nourrit affectivement),
- ton style de séduction et ta créativité amoureuse (Maison 5, son signe, ses planètes et son maître).

Voici les informations brutes extraites de la base de données :

{snippets_bruts}

À partir de ces éléments, rédige un texte psychologique, clair et incarné qui décrit :
- ce que tu recherches inconsciemment en amour,
- ta manière de montrer que tu aimes,
- comment tu prends (ou non) l'initiative dans le lien,
- tes besoins affectifs et émotionnels,
- ton rapport à la spontanéité, à la séduction et au jeu amoureux,
- comment s'exprime ton "cœur amoureux" (Maison 5 et son maître),
- les forces et fragilités de ta dynamique affective.

Ne parle PAS :
- du partenaire idéal (ce sera le module 2),
- de la sexualité explicite (ce sera le module 4),
- du couple engagé et du mariage (ce sera le module 3).

Reste centré(e) sur ta manière d'aimer, sur ta dynamique intérieure, ton fonctionnement affectif.

Pas de bullet points. Pas d'emoji.
Parle en "tu".
Ton direct, cash, psychologique.
"""
    

    print("\n\n===== PROMPT ENVOYÉ AU LLM =====\n")
    print(prompt)
    print("\n===== FIN PROMPT =====\n")
    
    logger.info("[AMOUR M1] Appel LLM en cours...")
    texte = interroger_llm(prompt)
    return texte