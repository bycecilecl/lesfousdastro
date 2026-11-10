from module.amour_blocs.normalisation_maisons import normaliser_maisons_theme
from module.amour_blocs.aspects_facilitants import est_facilitant, orbe_facilitant, ressource_factuelle
# module/amour_blocs/couple_ideal.py
# MODULE 3 : Dynamique de couple avec FILTRAGE INTELLIGENT des aspects

import logging
import math
from module.amour_bdd import (
    get_from_maisons_amour,
    get_from_maitre_en_maison,
    get_from_placements,
    get_from_aspects,
    get_from_aspects_maitre,
    df_to_snippets,
    get_from_noeuds,
)
from module.amour_blocs.maisons_couple import (
    _get_signe_maison,
    _normalize_signe,
    MAITRES_PAR_SIGNE,
)
from module.amour_blocs.llm_local import interroger_llm
from module.amour_blocs.dignites import get_dignite_planete
from module.amour_blocs.utils_theme import exporter_theme_complet, filtrer_point_illumination_amour
from module.amour_blocs.maniere_aimer import generer_snippets_maniere_aimer, _identite_maitre
from module.amour_blocs.context_amour import generer_contexte_amour

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def _lire_orbe(valeur):
    """Nombre fini positif ou nul ; une valeur inconnue ne vaut jamais zéro."""
    if isinstance(valeur, bool):
        return None
    try:
        orbe = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None
    return orbe if math.isfinite(orbe) and orbe >= 0 else None


def _normaliser_orbes_theme(theme):
    """Copie locale pour les filtres, le contexte et l'export du module Couple."""
    copie = dict(theme)
    for cle in ("aspects", "aspects_significatifs"):
        if cle not in theme:
            continue
        aspects = []
        for aspect in theme.get(cle) or []:
            if not isinstance(aspect, dict):
                continue
            orbe = _lire_orbe(aspect.get("orbe"))
            if orbe is None:
                logger.warning("[COUPLE] Aspect exclu : orbe absente ou invalide.")
                continue
            aspects.append({**aspect, "orbe": orbe})
        copie[cle] = aspects
    return copie


def _get_aspect_soleil_lune(theme: dict) -> str | None:
    """
    Cherche l'aspect réel entre Soleil et Lune dans le thème.
    """
    aspects = theme.get("aspects_significatifs") or theme.get("aspects") or []

    if isinstance(aspects, list):
        for asp in aspects:
            if not isinstance(asp, dict):
                continue

            p1 = (
                asp.get("planete1")
                or asp.get("planete_1")
                or asp.get("planète_1")
                or asp.get("p1")
            )
            p2 = (
                asp.get("planete2")
                or asp.get("planete_2")
                or asp.get("planète_2")
                or asp.get("p2")
            )
            aspect = (
                asp.get("aspect")
                or asp.get("type")
                or asp.get("valeur")
            )

            if {p1, p2} == {"Soleil", "Lune"} and isinstance(aspect, str):
                orbe = _lire_orbe(asp.get("orbe"))
                if orbe is None:
                    logger.warning("[COUPLE] Aspect Soleil-Lune exclu : orbe absente ou invalide.")
                    continue
                if est_facilitant(aspect) and orbe_facilitant(orbe) is None:
                    continue
                return aspect.strip().title()

    return None


def _get_conjonctions_avec(theme, nom_planete_ref: str, orbe_max: float = 5.0):
    """
    Retourne les conjonctions à orbe connue, valide et dans le seuil inclusif.
    """
    aspects = theme.get("aspects_significatifs") or theme.get("aspects") or []
    result = set()

    for asp in aspects:
        if not isinstance(asp, dict):
            continue
        if asp.get("aspect") != "Conjonction":
            continue
        p1 = asp.get("planete1")
        p2 = asp.get("planete2")
        if nom_planete_ref not in (p1, p2):
            continue

        orbe = _lire_orbe(asp.get("orbe"))
        if orbe is None:
            logger.warning(
                "[COUPLE] Conjonction de %s exclue : orbe absente ou invalide.",
                nom_planete_ref,
            )
            continue
        if orbe > orbe_max:
            continue

        if p1 == nom_planete_ref and p2:
            result.add(p2)
        elif p2 == nom_planete_ref and p1:
            result.add(p1)

    logger.debug(f"[COUPLE] Conjonctions trouvées avec {nom_planete_ref}: {result}")
    return result


def _get_planetes_en_maison(theme: dict, numero: int) -> list[str]:
    """
    Retourne la liste des planètes présentes dans la maison `numero`.
    """
    theme = normaliser_maisons_theme(theme)
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
    aspects_list = theme.get("aspects_significatifs") or theme.get("aspects") or []

    aspects_reels = []
    for asp in aspects_list:
        if not isinstance(asp, dict):
            continue

        p1 = (
            asp.get("planete1")
            or asp.get("planete_1")
            or asp.get("planète_1")
            or asp.get("p1")
        )
        p2 = (
            asp.get("planete2")
            or asp.get("planete_2")
            or asp.get("planète_2")
            or asp.get("p2")
        )
        type_asp = (
            asp.get("aspect")
            or asp.get("type")
            or asp.get("valeur")
        )
        orbe = _lire_orbe(asp.get("orbe"))
        if orbe is None:
            logger.warning("[COUPLE] Aspect exclu : orbe absente ou invalide.")
            continue
        if est_facilitant(type_asp):
            orbe = orbe_facilitant(orbe)
            if orbe is None:
                continue
            type_asp = str(type_asp).strip().title()

        if p1 and p2 and type_asp:
            aspects_reels.append((p1, p2, type_asp, orbe))

    return aspects_reels


def _filtrer_aspects_maitre7_intelligents(
    theme: dict,
    nom_maitre: str,
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> list[tuple[str, str, float]]:
    """
    Filtre intelligent des aspects du Maître de 7.
    
    Focus DYNAMIQUE DE COUPLE :
    - TOUS les aspects serrés (≤ 5°) avec aspects durs (Conj/Carré/Opp)
    - Max 3 trans-saturniennes
    - Max 2 lentes
    - Max 1 autre
    
    Retourne : liste de (autre_planete, type_aspect, orbe)
    """
    aspects_reels = _get_aspects_reels_du_theme(theme)
    aspects_durs = ["Conjonction", "Carre", "Carré", "Opposition", "Sextile", "Trigone"]
    
    trans_saturniennes = {"Pluton", "Neptune", "Chiron", "Lune Noire", "Lilith"}
    lentes = {"Saturne", "Uranus", "Jupiter"}
    
    candidats = []
    
    for (p1, p2, type_asp, orbe) in aspects_reels:
        if type_asp not in aspects_durs:
            continue
        if orbe is None or orbe > orbe_max:
            continue
        
        if nom_maitre not in (p1, p2):
            continue
        
        autre = p2 if p1 == nom_maitre else p1
        
        # Catégorisation
        if est_facilitant(type_asp) or orbe <= orbe_serre:
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
            logger.info(f"[COUPLE] ✅ Aspect Maître 7 SERRÉ gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "trans" and count_trans < 3:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_trans += 1
            logger.info(f"[COUPLE] ✅ Aspect Maître 7 TRANS gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "lent" and count_lent < 2:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_lent += 1
            logger.info(f"[COUPLE] ✅ Aspect Maître 7 LENT gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "autre" and count_autre < 1:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_autre += 1
            logger.info(f"[COUPLE] ✅ Aspect Maître 7 AUTRE gardé : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        else:
            logger.debug(f"[COUPLE] ⏭️ Aspect Maître 7 écarté (quota atteint) : {nom_maitre} {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
    
    return selection


def _filtrer_aspects_planete_intelligents(
    theme: dict,
    planete: str,
    orbe_serre: float = 5.0,
    orbe_max: float = 8.0,
) -> list[tuple[str, str, float]]:
    """
    Filtre intelligent des aspects pour Soleil/Lune.
    
    Pour le modèle intérieur (masculin/féminin) :
    - TOUS les aspects serrés (≤ 5°)
    - Max 2 trans-saturniennes
    - Max 1 lente
    
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
        
        if planete not in (p1, p2):
            continue
        
        autre = p2 if p1 == planete else p1
        
        # Catégorisation
        if est_facilitant(type_asp) or orbe <= orbe_serre:
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
    
    # Sélection (plus permissif que Maître 7)
    selection = []
    count_trans = 0
    count_lent = 0
    
    for asp in candidats:
        cat = asp["categorie"]
        
        if cat == "serré":
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            logger.info(f"[COUPLE] ✅ Aspect {planete} SERRÉ gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "trans" and count_trans < 2:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_trans += 1
            logger.info(f"[COUPLE] ✅ Aspect {planete} TRANS gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        elif cat == "lent" and count_lent < 1:
            selection.append((asp["autre"], asp["type"], asp["orbe"]))
            count_lent += 1
            logger.info(f"[COUPLE] ✅ Aspect {planete} LENT gardé : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
        
        else:
            logger.debug(f"[COUPLE] ⏭️ Aspect {planete} écarté (quota atteint) : {asp['type']} {asp['autre']} (orbe {asp['orbe']:.1f}°)")
    
    return selection


def generer_bloc_couple_ideal(
    theme: dict,
    call_llm: bool = True,
    polarite: str = "Femme",
    bilan_amour: str | None = None,
) -> str:
    """
    MODULE 3 : DYNAMIQUE DE COUPLE & FONCTIONNEMENT RELATIONNEL
    Avec filtrage intelligent des aspects
    """
    theme = normaliser_maisons_theme(filtrer_point_illumination_amour(theme))
    theme = _normaliser_orbes_theme(theme)
    logger.info(f"--- DÉBUT GÉNÉRATION MODULE COUPLE (polarite reçue={polarite!r}) ---")

    # Normalisation de la polarité
    if isinstance(polarite, str):
        polarite = polarite.strip().capitalize()

    if polarite not in ("Femme", "Homme"):
        logger.warning(f"[COUPLE] Polarité invalide ou absente ({polarite!r}), fallback sur 'Femme'")
        polarite = "Femme"

    logger.info(f"[COUPLE] Polarité normalisée utilisée : {polarite}")

    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    snippets = []

    # ═══════════════════════════════════════════════════════════
    # 1) MAISON 7 : L'AMBIANCE DU COUPLE
    # ═══════════════════════════════════════════════════════════
    signe_7 = _get_signe_maison(theme, 7)
    signe_7_norm = _normalize_signe(signe_7) if isinstance(signe_7, str) else None
    maitres_7 = MAITRES_PAR_SIGNE.get(signe_7_norm, []) if signe_7_norm else []

    logger.info(f"[COUPLE] Maison 7 en {signe_7} (Maîtres: {maitres_7})")

    # 1A) Signe de la Maison 7
    if signe_7:
        df_m7_signe = get_from_maisons_amour(
            maison="Maison 7",
            type_donnee="Signe",
            valeur=signe_7,
            bloc="Couple",
            polarite=polarite,
        )
        if not df_m7_signe.empty:
            snippets.append(
                f"=== MAISON 7 EN {signe_7.upper()} : L'AMBIANCE DE TON COUPLE ===\n"
                + df_to_snippets(df_m7_signe)
            )

    # 1B) Planètes en Maison 7
    planetes_en_7 = _get_planetes_en_maison(theme, 7)
    if planetes_en_7:
        logger.info(f"[COUPLE] Planètes en M7 : {planetes_en_7}")
    
    for nom_planete in planetes_en_7:
        df_planete_7 = get_from_maisons_amour(
            maison="Maison 7",
            type_donnee="Planète",
            valeur=nom_planete,
            bloc="Couple",
            polarite=polarite,
        )
        if not df_planete_7.empty:
            snippets.append(
                f"=== {nom_planete.upper()} EN MAISON 7 ===\n"
                + df_to_snippets(df_planete_7)
            )

    # ═══════════════════════════════════════════════════════════
    # 2) MAÎTRE(S) DE LA MAISON 7
    # ═══════════════════════════════════════════════════════════
    valeurs_deja_vues = set()
    
    for nom_maitre in maitres_7:
        infos_m = planetes.get(nom_maitre, {}) or {}
        maison_maitre = infos_m.get("maison")
        signe_maitre = infos_m.get("signe")

        if maison_maitre is None:
            continue

        brut = str(maison_maitre).strip()

        snippets.append(_identite_maitre(7, nom_maitre, infos_m))
        # Seul le commentaire de maison est partagé entre les deux maîtres.
        if brut not in valeurs_deja_vues:
            df_m7_maitre = None
            for val in (f"Maison_{brut}", brut):
                df = get_from_maitre_en_maison(
                    maitre_maison="maitre_maison_7", type_donnee="Maison",
                    valeur=val, bloc="Couple", polarite=polarite,
                )
                if not df.empty:
                    df_m7_maitre = df
                    break
            if df_m7_maitre is None:
                logger.warning(f"[COUPLE] Pas de texte pour Maître de 7 ({nom_maitre}) en Maison {brut}")
            else:
                snippets.append(df_to_snippets(df_m7_maitre))
                valeurs_deja_vues.add(brut)

        # 2B) Dignité du maître de VII
        if signe_maitre:
            dignite_maitre = get_dignite_planete(nom_maitre, signe_maitre)
            retrograde = infos_m.get("retrograde") or infos_m.get("rétrograde") or False
            maitre_affaibli = dignite_maitre in ("Chute", "Exil") or retrograde
            
            if maitre_affaibli:
                logger.info(f"[COUPLE] ⚠️ ALERTE : Maître de 7 ({nom_maitre}) AFFAIBLI - {dignite_maitre}, rétro={retrograde}")
                
                # Construire l'avertissement explicite
                details_affaiblissement = []
                if dignite_maitre in ("Chute", "Exil"):
                    details_affaiblissement.append(f"en {dignite_maitre} en {signe_maitre}")
                if retrograde:
                    details_affaiblissement.append("rétrograde")
                
                texte_affaiblissement = " ET ".join(details_affaiblissement)
                
                avertissement_critique = f"""
ÉTAT DU MAÎTRE À NUANCER : Le maître de ta Maison 7 ({nom_maitre}) est {texte_affaiblissement}.

La Maison 7 en {signe_7} conserve sa symbolique. Cet état du maître en module l'expression, sans inversion automatique.
Relie cette nuance à la nature du maître, à son signe, à sa maison et aux aspects fournis, sans effacer les ressources du thème.
Si le maître est en chute ou en exil, explicite la difficulté symbolique propre à cette planète dans ce signe : ne te contente pas de dire qu'elle nuance le fonctionnement. Décris ce qui peut se contrarier, demander un ajustement ou constituer un point de blocage, et comment cela peut se manifester concrètement dans le domaine relationnel de ce chapitre.
Nomme cette difficulté clairement, sans la transformer en incapacité, en événement vécu certain ou en inversion du signe de la maison. Les aspects facilitants peuvent offrir des ressources pour la gérer, mais ne l'effacent pas.
S'il est rétrograde, distingue cette rétrogradation de sa dignité : une possible intériorisation n'est pas une incapacité.
"""
                snippets.append(avertissement_critique)

        # 2C) Aspects du maître de la Maison 7 (FILTRÉS)
        aspects_filtres = _filtrer_aspects_maitre7_intelligents(theme, nom_maitre)
        
        for (autre, type_asp, orbe) in aspects_filtres:
            if est_facilitant(type_asp):
                snippets.append(ressource_factuelle(nom_maitre, type_asp, autre, orbe))
                continue
            df_m7_aspect = get_from_aspects_maitre(
                "maitre_maison_7", autre, type_asp, "Couple", polarite,
            )

            if not df_m7_aspect.empty:
                snippets.append(
                    f"=== ASPECT DU MAÎTRE DE 7 ({nom_maitre.upper()} {type_asp.upper()} {autre.upper()}) ===\n"
                    + df_to_snippets(df_m7_aspect)
                )

    # ═══════════════════════════════════════════════════════════
    # 3) ASPECT SOLEIL-LUNE : TON MODÈLE INTÉRIEUR
    # ═══════════════════════════════════════════════════════════
    aspect_sl = _get_aspect_soleil_lune(theme)
    
    if aspect_sl:
        logger.info(f"[COUPLE] Aspect Soleil-Lune détecté : {aspect_sl}")
        df_sl = get_from_aspects(
            planete_1="Soleil",
            planete_2="Lune",
            valeur=aspect_sl,
            bloc="Couple",
            polarite=polarite,
        )
        if not df_sl.empty:
            snippets.append(
                f"=== ASPECT SOLEIL–LUNE ({aspect_sl.upper()}) : TON MODÈLE INTÉRIEUR ===\n"
                + df_to_snippets(df_sl)
            )

    # ═══════════════════════════════════════════════════════════
    # 4) JUNON : L'ENGAGEMENT & LE CONTRAT
    # ═══════════════════════════════════════════════════════════
    junon = planetes.get("Junon", {}) or {}
    signe_junon = junon.get("signe")
    maison_junon = junon.get("maison")

    # 4A) Junon en signe
    if signe_junon:
        df_junon_signe = get_from_placements(
            planete="Junon",
            type_donnee="Signe",
            valeur=signe_junon,
            bloc="Couple",
            polarite=polarite,
        )
        if not df_junon_signe.empty:
            snippets.append(
                f"=== JUNON EN {signe_junon.upper()} : TON STYLE D'ENGAGEMENT ===\n"
                + df_to_snippets(df_junon_signe)
            )

    # 4B) Junon en maison
    if maison_junon is not None:
        brut = str(maison_junon).strip()
        
        df_junon_maison = get_from_placements(
            planete="Junon",
            type_donnee="Maison",
            valeur=brut,
            bloc="Couple",
            polarite=polarite,
        )

        if not df_junon_maison.empty:
            snippets.append(
                f"=== JUNON EN MAISON {maison_junon} : LE DOMAINE DE TON ENGAGEMENT ===\n"
                + df_to_snippets(df_junon_maison)
            )

    # 4C) Junon conjointe à d'autres planètes
    planetes_conjointes = _get_conjonctions_avec(theme, "Junon")
    if planetes_conjointes:
        logger.info(f"[COUPLE] Junon est conjointe à : {planetes_conjointes}")

    for autre in sorted(planetes_conjointes):
        df_junon_cj = get_from_aspects(
            planete_1="Junon",
            planete_2=autre,
            valeur="Conjonction",
            bloc="Couple",
            polarite=polarite,
        )
        if df_junon_cj.empty:
            df_junon_cj = get_from_aspects(
                planete_1=autre,
                planete_2="Junon",
                valeur="Conjonction",
                bloc="Couple",
                polarite=polarite,
            )
        
        if not df_junon_cj.empty:
            snippets.append(
                f"=== JUNON CONJOINTE À {autre.upper()} ===\n"
                + df_to_snippets(df_junon_cj)
            )

    # ═══════════════════════════════════════════════════════════
    # 5) NŒUDS LUNAIRES : ÉVOLUTION RELATIONNELLE
    # ═══════════════════════════════════════════════════════════
    noeud_nord = planetes.get("Nœud Nord") or planetes.get("Rahu") or {}
    signe_nn = noeud_nord.get("signe")

    if signe_nn:
        df_nn = get_from_noeuds(
            type_donnee="Signe",
            valeur=signe_nn,
            bloc="Evolution",
            polarite=polarite,
        )

        if not df_nn.empty:
            snippets.append(
                "=== NŒUDS LUNAIRES : TON ÉVOLUTION EN AMOUR ===\n"
                + df_to_snippets(df_nn)
            )

    # ═══════════════════════════════════════════════════════════
    # 6) Soleil/Lune selon la polarité (FILTRÉS)
    # ═══════════════════════════════════════════════════════════
    if polarite == "Homme":
        lune = planetes.get("Lune", {})
        signe_lune = lune.get("signe")
        maison_lune = lune.get("maison")

        part = f"=== LUNE : TON FÉMININ INTÉRIEUR ===\n"
        if signe_lune:
            part += f"- Lune en {signe_lune}\n"
        if maison_lune is not None:
            part += f"- Lune en Maison {maison_lune}\n"

        # Aspects à la Lune (FILTRÉS)
        aspects_lune = _filtrer_aspects_planete_intelligents(theme, "Lune")
        if aspects_lune:
            part += "\nAspects majeurs :\n"
            for autre, asp, orbe in aspects_lune:
                part += f"- {asp} à {autre} (orbe {orbe:.1f}°)\n"

        snippets.append(part)

    elif polarite == "Femme":
        soleil = planetes.get("Soleil", {})
        signe_soleil = soleil.get("signe")
        maison_soleil = soleil.get("maison")

        part = f"=== SOLEIL : TON MASCULIN INTÉRIEUR ===\n"
        if signe_soleil:
            part += f"- Soleil en {signe_soleil}\n"
        if maison_soleil is not None:
            part += f"- Soleil en Maison {maison_soleil}\n"

        # Aspects au Soleil (FILTRÉS)
        aspects_soleil = _filtrer_aspects_planete_intelligents(theme, "Soleil")
        if aspects_soleil:
            part += "\nAspects majeurs :\n"
            for autre, asp, orbe in aspects_soleil:
                part += f"- {asp} à {autre} (orbe {orbe:.1f}°)\n"

        snippets.append(part)

    # ═══════════════════════════════════════════════════════════
    # ASSEMBLAGE FINAL
    # ═══════════════════════════════════════════════════════════
    snippets_bruts = "\n\n".join(s for s in snippets if s).strip()
    
    logger.info(f"--- FIN EXTRACTION COUPLE --- Taille snippets: {len(snippets_bruts)} chars")

    if not call_llm:
        return (
            "<pre>MODULE 3 · DYNAMIQUE DE COUPLE (FILTRÉ) :\n"
            + (snippets_bruts or "(rien)")
            + "</pre>"
        )

    if not snippets_bruts:
        logger.warning("[COUPLE] Aucun snippet généré, pas d'appel LLM.")
        return ""

    # ═══════════════════════════════════════════════════════════
    # PROMPT LLM
    # ═══════════════════════════════════════════════════════════
    if aspect_sl:
        consigne_soleil_lune = """
3) **Ton modèle intérieur** (Soleil-Lune) : quelle image du couple tu portes en toi ? Comment ton masculin et ton féminin intérieurs dialoguent ?
"""
    else:
        consigne_soleil_lune = ""

    snippets_amour = generer_snippets_maniere_aimer(theme, polarite)
    theme_complet = exporter_theme_complet(theme)
    contexte_amour = generer_contexte_amour(theme)
    consigne_genre = "Adresse-toi au masculin." if polarite == "Homme" else "Adresse-toi au féminin."

    prompt = f"""
ASPECTS FACILITANTS : RESSOURCES, PAS ANNULATION
Seuls les sextiles et trigones à 3° d'orbe maximum sont retenus comme facilitants.
Explique les difficultés clairement et directement, puis les ressources pertinentes : aucun aspect facilitant n'annule une tension.
Une ressource peut aider à gérer une difficulté ; sa présence ne prouve pas qu'elle est utilisée ni que la difficulté est résolue.
Ne compense pas les tensions par un comptage des aspects. Même nombreux, les facilitants ne rendent pas les tensions restantes négligeables.
Évalue la pertinence pour ce chapitre, les planètes impliquées et la précision des aspects ; n'invente pas une souffrance dominante si l'ensemble est plus fluide.
Ne classe pas automatiquement les conjonctions parmi les ressources.

Tu es une astrologue experte en psychologie des relations. On travaille le MODULE 3 : "Ta dynamique de couple".

{consigne_genre}

LECTURE NUANCÉE DES MAÎTRES DE MAISON

Conserve la symbolique de la maison et de son signe. L'état du maître en module l'expression, sans inversion automatique.
Articule la nature du maître, son signe, sa maison, sa dignité et les aspects effectivement fournis : tensions comme soutiens.
Si le maître est en chute ou en exil, explicite la difficulté symbolique propre à cette planète dans ce signe : ne te contente pas de dire qu'elle nuance le fonctionnement. Décris ce qui peut se contrarier, demander un ajustement ou constituer un point de blocage, et comment cela peut se manifester concrètement dans le domaine relationnel de ce chapitre.
Nomme cette difficulté clairement, sans la transformer en incapacité, en événement vécu certain ou en inversion du signe de la maison. Les aspects facilitants peuvent offrir des ressources pour la gérer, mais ne l'effacent pas.
Une rétrogradation ne constitue pas à elle seule une faiblesse : évoque une possible intériorisation ou réélaboration, sans en faire un blocage certain.
Ne déduis pas de ce seul indicateur une peur du rejet, un sentiment d'indignité, des partenaires toxiques ou une sexualité inhibée.
Présente les manifestations possibles avec nuance et rattache chacune aux données disponibles. N'invente aucun facteur manquant.
Si un extrait impose une inversion automatique ou un résultat négatif certain, reformule-le selon ces principes.

Voici un CONTEXTE GLOBAL du thème de la personne, centré sur sa dynamique émotionnelle et relationnelle :

{contexte_amour}

⚠️ CONTEXTE IMPORTANT :
Le Module 2 (Partenaire idéal) a DÉJÀ décrit le type de personne qui attire cette personne.
Ici, on ne reparle PAS de qui l'attire. On parle de COMMENT elle fonctionne une fois EN COUPLE.

DONNÉES ASTROLOGIQUES :
{snippets_bruts}

Voici un RAPPEL TECHNIQUE de ta manière d'aimer
(éléments utiles tirés du Module 1, mais sans texte littéraire) :

{snippets_amour}

CONSIGNES :
À partir de ces éléments, rédige un texte INCARNÉ et CONCRET qui décrit :

1) **L'ambiance de ton couple** (Maison 7) : quelle énergie règne entre vous ? C'est quoi le "parfum" de ta relation idéale ?

2) **Ton fonctionnement relationnel** (Maître de 7) : comment tu te comportes une fois engagé(e) ? Comment tu gères le quotidien, les tensions, l'espace de chacun ?
{consigne_soleil_lune}
4) **Ton style d'engagement** (Junon) : qu'est-ce que tu attends d'une union ? Quel "contrat" implicite tu proposes à l'autre ?
Pour les conjonctions de Junon, utilise uniquement une orbe connue et valide de 0 à 5° inclus.
Même si l'export du thème ou un autre extrait les mentionne, n'interprète pas celles qui dépassent 5° ou dont l'orbe est absente ou invalide.
Une conjonction de Junon n'est pas automatiquement favorable : distingue les difficultés et les ressources selon les définitions fournies.

5) **Les schémas relationnels** : qu'est-ce qui fonctionne bien pour toi en couple ? Et qu'est-ce qui dérape souvent ? Les cycles attraction-crise-réparation.

6) **Tes besoins concrets** : de quoi tu as besoin pour que ça dure ? Espace, fusion, confrontation, stabilité ?

STYLE :
- Parle en "tu", ton direct et cash
- Concret et incarné : donne des exemples de situations ("Quand il y a un conflit, tu as tendance à...")
- Pas de bullet points, pas d'emoji
- Synthèse fluide, environ 400-500 mots
- Ose nommer les zones de friction sans complaisance
- N’utilise pas de pronom possessif devant les planètes (évite : “ton Mars”, “ta Vénus”, “ta Saturne”).

NE PARLE PAS de :
- Qui t'attire / le portrait du partenaire (c'est fait dans le Module 2)
- Les projections sur l'autre
- Ce qui te fait "flasher" au début
"""
    
    print("\n\n===== PROMPT ENVOYÉ AU LLM =====\n")
    print(prompt)
    print("\n===== FIN PROMPT =====\n")
    
    logger.info("[COUPLE] Appel LLM en cours...")
    texte = interroger_llm(prompt)
    logger.info("[COUPLE] Réponse LLM reçue.")
    return texte
