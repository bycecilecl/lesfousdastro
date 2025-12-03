# module/amour_blocs/context_amour.py

from __future__ import annotations
from typing import Dict, Any, List

# On considère les planètes perso + Pluton pour les amas
PERSONNELLES = ("Soleil", "Lune", "Vénus", "Mars", "Pluton")


# ─────────────────────────────────────────────────────────────
# Helpers de base
# ─────────────────────────────────────────────────────────────

def _get_planetes(theme: dict) -> dict:
    return theme.get("planetes") or theme.get("planètes") or {}


def _safe_planete(planetes: dict, nom: str) -> dict:
    return planetes.get(nom, {}) or {}


def _fmt_planete(planetes: dict, nom: str) -> str | None:
    p = _safe_planete(planetes, nom)
    signe = p.get("signe")
    maison = p.get("maison")
    if not signe and maison is None:
        return None

    texte = f"{nom} en {signe}" if signe else nom
    if maison is not None:
        texte += f" maison {maison}"
    return texte


# ─────────────────────────────────────────────────────────────
# Évaluation de l'état du maître (fort / affaibli / neutre)
# ─────────────────────────────────────────────────────────────

def _evaluer_etat_maitre(planete_data: dict, nom_planete: str) -> str:
    """
    Retourne 'fort', 'affaibli', ou 'neutre' selon :
    - Dignité (domicile/exaltation = fort, chute/exil = affaibli)
    - Rétrogradation
    - Maison (angulaire = fort, cadente = affaibli)
    """
    # Dignités essentielles (domicile simplifié)
    dignites_fortes = {
        "Soleil": ["Lion"],
        "Lune": ["Cancer"],
        "Mercure": ["Gémeaux", "Vierge"],
        "Vénus": ["Taureau", "Balance"],
        "Mars": ["Bélier", "Scorpion"],
        "Jupiter": ["Sagittaire", "Poissons"],
        "Saturne": ["Capricorne", "Verseau"],
    }

    # Chutes et exils (version simplifiée)
    chutes_exils = {
        "Soleil": ["Verseau", "Balance"],
        "Lune": ["Capricorne", "Scorpion"],
        "Mars": ["Cancer", "Balance", "Taureau"],
        "Vénus": ["Scorpion", "Bélier", "Vierge"],
        "Jupiter": ["Gémeaux", "Capricorne", "Vierge"],
        "Saturne": ["Cancer", "Bélier", "Lion"],
        "Mercure": ["Sagittaire", "Poissons"],
    }

    signe = planete_data.get("signe", "")
    maison = planete_data.get("maison")
    retro = planete_data.get("retrograde") or planete_data.get("rétrograde") or False

    points = 0

    # Dignité
    if signe in dignites_fortes.get(nom_planete, []):
        points += 2
    elif signe in chutes_exils.get(nom_planete, []):
        points -= 2

    # Rétrogradation
    if retro:
        points -= 1

    # Maison (angulaire = fort, cadente = faible)
    if maison in (1, 4, 7, 10):  # Angulaires
        points += 1
    elif maison in (3, 6, 9, 12):  # Cadentes
        points -= 1

    if points >= 2:
        return "fort"
    elif points <= -2:
        return "affaibli"
    else:
        return "neutre"


# ─────────────────────────────────────────────────────────────
# Amas
# ─────────────────────────────────────────────────────────────

def _detect_amas_signes(planetes: dict, cibles: tuple[str, ...] = PERSONNELLES) -> list[str]:
    """
    Détecte des amas simples : ≥ 3 planètes personnelles dans le même signe.
    Retourne une liste de phrases.
    """
    par_signe: Dict[str, list[str]] = {}
    for nom in cibles:
        p = _safe_planete(planetes, nom)
        signe = p.get("signe")
        if not signe:
            continue
        par_signe.setdefault(signe, []).append(nom)

    phrases: List[str] = []
    for signe, noms in par_signe.items():
        if len(noms) >= 3:
            noms_txt = ", ".join(noms)
            phrases.append(f"**Amas en {signe}** ({noms_txt}) : concentration majeure d'énergie dans ce signe.")
    return phrases


def _detect_amas_maisons(planetes: dict, cibles: tuple[str, ...] = PERSONNELLES) -> list[str]:
    """
    Amas en maisons : ≥ 3 planètes perso dans la même maison.
    """
    par_maison: Dict[int, list[str]] = {}
    for nom in cibles:
        p = _safe_planete(planetes, nom)
        maison = p.get("maison")
        if maison is None:
            continue
        par_maison.setdefault(maison, []).append(nom)

    phrases: List[str] = []
    for maison, noms in par_maison.items():
        if len(noms) >= 3:
            noms_txt = ", ".join(noms)
            phrases.append(f"**Amas en Maison {maison}** ({noms_txt}) : vie affective très liée à ce secteur.")
    return phrases


# ─────────────────────────────────────────────────────────────
# Maisons relationnelles 5–7–8 + état du maître
# ─────────────────────────────────────────────────────────────

def _analyser_maisons_relationnelles(planetes: dict, theme: dict) -> list[str]:
    """
    Regarde les maisons 5-7-8 : planètes présentes + état du maître
    """
    maisons_data = (
        theme.get("maisons")
        or theme.get("maisons_tropicales")
        or {}
    )
    maisons_relationnelles = {5, 7, 8}
    occupees: Dict[int, list[str]] = {}

    # Planètes présentes dans les maisons
    for nom, data in planetes.items():
        maison = data.get("maison")
        if maison in maisons_relationnelles:
            occupees.setdefault(maison, []).append(nom)

    phrases: List[str] = []

    for m in sorted(maisons_relationnelles):
        maison_info = maisons_data.get(m, {}) or {}
        signe = maison_info.get("signe") or maison_info.get("cuspide_signe")
        maitre = maison_info.get("maitre")

        # Planètes présentes
        if m in occupees:
            noms = ", ".join(occupees[m])
            if m == 5:
                desc = "le plaisir, la romance, la créativité"
            elif m == 7:
                desc = "le couple, les partenariats, le miroir relationnel"
            else:  # m == 8
                desc = "l'intimité, la fusion, la sexualité, les transformations"
            phrases.append(f"**Maison {m} occupée** ({noms}) : {desc} au cœur de la vie.")

        # État du maître (important si affaibli, ou fort sur maison vide)
        if maitre and signe:
            maitre_data = _safe_planete(planetes, maitre)
            if not maitre_data:
                continue

            etat = _evaluer_etat_maitre(maitre_data, maitre)

            maitre_signe = maitre_data.get("signe", "")
            maitre_maison = maitre_data.get("maison")
            maitre_retro = maitre_data.get("retrograde") or maitre_data.get("rétrograde")

            detail = f"{maitre} en {maitre_signe}" if maitre_signe else maitre
            if maitre_retro:
                detail += " rétro"
            if maitre_maison:
                detail += f" M{maitre_maison}"

            if etat == "affaibli":
                if m == 5:
                    desc_faible = "créativité amoureuse bridée, difficulté à s'autoriser le plaisir"
                elif m == 7:
                    desc_faible = "difficulté à structurer le couple, patterns relationnels complexes"
                else:  # 8
                    desc_faible = "blocages dans l'intimité, peur de la fusion, sexualité inhibée"

                phrases.append(
                    f"**Maison {m}** (maître {detail} affaibli) : {desc_faible}."
                )

            elif etat == "fort" and m not in occupees:
                # Maison vide mais maître fort = énergie disponible
                if m == 5:
                    desc_fort = "créativité amoureuse forte malgré maison vide"
                elif m == 7:
                    desc_fort = "capacité relationnelle forte, couple structuré"
                else:  # 8
                    desc_fort = "intensité et profondeur disponibles dans l'intimité"

                phrases.append(
                    f"**Maison {m}** (maître {detail} fort) : {desc_fort}."
                )

    return phrases


# ─────────────────────────────────────────────────────────────
# Aspects durs entre planètes d'amour
# ─────────────────────────────────────────────────────────────

def _analyser_aspects_majeurs(theme: dict) -> list[str]:
    """
    Détecte les aspects durs (Conjonction, Carré/Carre, Opposition) entre planètes d'amour.
    """
    aspects = (
        theme.get("aspects_significatifs")
        or theme.get("aspects")
        or []
    )
    planetes_amour = {"Lune", "Vénus", "Mars", "Saturne", "Pluton", "Chiron", "Lune Noire"}

    aspects_amour: List[str] = []
    for asp in aspects:
        if not isinstance(asp, dict):
            continue

        p1 = asp.get("planete1") or asp.get("planete_1") or asp.get("planète_1") or asp.get("p1")
        p2 = asp.get("planete2") or asp.get("planete_2") or asp.get("planète_2") or asp.get("p2")
        aspect_type = asp.get("aspect") or asp.get("type") or asp.get("valeur")
        orbe = asp.get("orbe", 999)

        if not (p1 and p2 and aspect_type):
            continue

        if p1 in planetes_amour and p2 in planetes_amour:
            at_norm = str(aspect_type).lower()
            is_dur = any(
                key in at_norm
                for key in ("conjonction", "carre", "carré", "opposition")
            )
            if is_dur and orbe is not None and orbe < 5:
                aspects_amour.append(f"{p1} {aspect_type} {p2} (orbe {orbe:.1f}°)")

    if aspects_amour:
        return [f"**Aspects majeurs impactant l'amour** : {' ; '.join(aspects_amour[:3])}."]
    return []


# ─────────────────────────────────────────────────────────────
# Points forts déjà calculés (filtrés amour)
# ─────────────────────────────────────────────────────────────

def _extraire_points_forts_amour(theme: dict) -> list[str]:
    """
    Filtre quelques points forts déjà présents dans le thème.
    On ne garde que ce qui touche à Lune / Vénus / maisons 5-7-8-12, etc.
    """
    candidats = (
        theme.get("points_forts")
        or theme.get("axes_majeurs")
        or theme.get("resume_points_forts")
        or []
    )

    if isinstance(candidats, str):
        candidats = [c.strip("•- ") for c in candidats.split("\n") if c.strip()]

    mots_cles = (
        "Lune",
        "Vénus",
        "Maison 5",
        "Maison 7",
        "Maison 8",
        "Maison 12",
        "Chiron",
        "Lune Noire",
        "amas",
        "Amas",
        "relation",
        "couple",
        "Saturne",
    )

    selection: List[str] = []
    for ligne in candidats:
        if any(m in ligne for m in mots_cles):
            selection.append(ligne.strip())

    return selection


# ─────────────────────────────────────────────────────────────
# Contexte amour global
# ─────────────────────────────────────────────────────────────

def generer_contexte_amour(theme: dict) -> str:
    """
    Génère un contexte 'amour / psycho' enrichi à injecter dans CHAQUE prompt amour.
    - centré sur : planètes perso, maisons relationnelles, aspects, rétrogradations, Chiron, Pluton, Maison 5
    - générique : pas de cas par cas manuel
    """
    planetes = _get_planetes(theme)
    bouts: list[str] = []

    # === 1. ASCENDANT ===
    asc = (
        _safe_planete(planetes, "Ascendant")
        or theme.get("ascendant")
        or {}
    )
    asc_signe = asc.get("signe") or asc.get("sign")
    if asc_signe:
        bouts.append(
            f"**Ascendant en {asc_signe}** : manière spontanée d'entrer en relation, première énergie perçue par l'autre."
        )

    # === 2. PLANÈTES PERSONNELLES ===
    perso_fmt = []
    for nom in PERSONNELLES:
        txt = _fmt_planete(planetes, nom)
        if txt:
            perso_fmt.append(txt)
    if perso_fmt:
        bouts.append("**Planètes personnelles** : " + "; ".join(perso_fmt) + ".")

    # === 3. LUNE - patterns spécifiques ===
    lune = _safe_planete(planetes, "Lune")
    lune_signe = lune.get("signe")
    lune_maison = lune.get("maison")

    if lune_signe:
        patterns_lune = {
            "Capricorne": "besoin de sécurité émotionnelle, retenue, pudeur affective, peur de la dépendance.",
            "Cancer": "hypersensibilité, besoin de fusion et de nid affectif, peur de l'abandon.",
            "Scorpion": "intensité émotionnelle extrême, possessivité, peur de la trahison.",
            "Poissons": "perméabilité émotionnelle, idéalisation, confusion entre soi et l'autre.",
            "Verseau": "détachement émotionnel, besoin de liberté, difficulté avec la fusion.",
            "Vierge": "contrôle des émotions, perfectionnisme affectif, service à l'autre.",
            "Bélier": "réactivité émotionnelle, impulsivité, besoin d'autonomie affective.",
            "Balance": "besoin d'harmonie et de validation par l'autre, évitement du conflit.",
        }
        if lune_signe in patterns_lune:
            bouts.append(f"**Lune en {lune_signe}** : {patterns_lune[lune_signe]}")
        else:
            bouts.append(
                f"**Lune en {lune_signe}** : style émotionnel particulier à ce signe dans la vie affective."
            )

    if lune_maison in (2, 4, 7, 8, 12):
        bouts.append(
            f"Lune en Maison {lune_maison} : la sécurité affective et les besoins émotionnels passent par ce domaine."
        )

    # === 4. VÉNUS - patterns + rétro ===
    venus = _safe_planete(planetes, "Vénus")
    venus_signe = venus.get("signe")
    venus_maison = venus.get("maison")
    venus_retro = venus.get("retrograde") or venus.get("rétrograde") or False

    if venus_signe:
        patterns_venus = {
            "Scorpion": "amour fusionnel, possessif, transformateur ; peur viscérale de la trahison.",
            "Capricorne": "besoin de preuves concrètes, loyauté, engagement dans la durée, lenteur à s'ouvrir.",
            "Verseau": "besoin de liberté et d'amitié dans l'amour, originalité, détachement affectif.",
            "Poissons": "idéalisation, dévotion, sacrifice de soi, confusion des frontières.",
            "Bélier": "passion impulsive, conquête, besoin de challenge et de spontanéité.",
            "Taureau": "sensualité, possessivité, stabilité, besoin de sécurité matérielle et affective.",
            "Gémeaux": "papillonnage, besoin de variété, communication au cœur de l'amour.",
            "Cancer": "nid affectif, maternage, protection, hypersensibilité aux rejets.",
        }
        if venus_signe in patterns_venus:
            bouts.append(f"**Vénus en {venus_signe}** : {patterns_venus[venus_signe]}")
        else:
            bouts.append(
                f"**Vénus en {venus_signe}** : manière d'aimer colorée par ce signe."
            )

    if venus_maison in (5, 7, 8, 12):
        secteurs = {
            5: "le plaisir, la créativité, le jeu amoureux",
            7: "le couple, le miroir relationnel, l'engagement",
            8: "la fusion, l'intimité sexuelle, la transformation par l'autre",
            12: "l'amour idéalisé, le sacrifice, les amours cachées ou karmiques",
        }
        bouts.append(
            f"Vénus en Maison {venus_maison} : l'amour est intimement lié à {secteurs[venus_maison]}."
        )

    if venus_retro:
        bouts.append(
            "**Vénus RÉTROGRADE** : difficulté à recevoir l'amour, doute sur sa valeur affective, besoin de réapprendre à aimer."
        )

    # === 5. MARS - patterns + rétro ===
    mars = _safe_planete(planetes, "Mars")
    mars_signe = mars.get("signe")
    mars_retro = mars.get("retrograde") or mars.get("rétrograde") or False

    if mars_signe in ("Scorpion", "Bélier", "Capricorne", "Cancer"):
        patterns_mars = {
            "Scorpion": "désir intense, magnétisme sexuel, jalousie, vengeance si blessé.",
            "Bélier": "passion fulgurante, impulsivité, conquête, agressivité si frustré.",
            "Capricorne": "désir contrôlé, endurance, domination subtile, frustration chronique.",
            "Cancer": "colère refoulée, passivité-agressivité, désir de protection.",
        }
        bouts.append(f"**Mars en {mars_signe}** : {patterns_mars[mars_signe]}")

    if mars_retro:
        bouts.append(
            "**Mars RÉTROGRADE** : désir inhibé, difficulté à initier, colère refoulée, sexualité complexe."
        )

    # === 6. SATURNE - blocages / leçons ===
    saturne = _safe_planete(planetes, "Saturne")
    saturne_signe = saturne.get("signe")
    saturne_maison = saturne.get("maison")

    if saturne_maison in (5, 7, 8):
        secteurs_saturne = {
            5: "le plaisir, la spontanéité amoureuse, la légèreté",
            7: "l'engagement, le couple, la confiance en l'autre",
            8: "l'intimité, la fusion, le lâcher-prise sexuel",
        }
        bouts.append(
            f"**Saturne en Maison {saturne_maison}** : blocage/peur/leçon majeure autour de {secteurs_saturne[saturne_maison]}."
        )
    elif saturne_signe:
        bouts.append(
            f"**Saturne en {saturne_signe}** : zone de peur, restriction ou apprentissage lent en amour."
        )

    # === 7. PLUTON (maisons relationnelles) ===
    pluton = _safe_planete(planetes, "Pluton")
    pluton_signe = pluton.get("signe")
    pluton_maison = pluton.get("maison")

    if pluton_maison in (2, 5, 7, 8):
        bouts.append(
            f"**Pluton en {pluton_signe} maison {pluton_maison}** : intensité, obsession, transformation profonde dans ce secteur."
        )

    # === 8. CHIRON (blessure relationnelle) ===
    chiron = _safe_planete(planetes, "Chiron")
    chiron_signe = chiron.get("signe")
    chiron_maison = chiron.get("maison")

    if chiron_signe or chiron_maison:
        texte_chiron = "**Chiron"
        if chiron_signe:
            texte_chiron += f" en {chiron_signe}"
        if chiron_maison:
            texte_chiron += f" maison {chiron_maison}"
        texte_chiron += (
            "** : blessure relationnelle à guérir, zone de vulnérabilité et de potentiel de guérison."
        )
        bouts.append(texte_chiron)

    # === 9. MAISON 5 (créativité amoureuse) ===
    maisons = (
        theme.get("maisons")
        or theme.get("maisons_tropicales")
        or {}
    )
    m5 = maisons.get(5, {}) or {}
    m5_signe = m5.get("signe") or m5.get("cuspide_signe")
    m5_maitre = m5.get("maitre")

    if m5_signe:
        texte_m5 = f"**Maison 5 en {m5_signe}**"
        if m5_maitre:
            maitre_data = _safe_planete(planetes, m5_maitre)
            maitre_maison = maitre_data.get("maison")
            if maitre_maison:
                texte_m5 += f" (maître en M{maitre_maison})"
        texte_m5 += " : créativité amoureuse, style de séduction, jeu amoureux."
        bouts.append(texte_m5)

    # === 10. AMAS ===
    bouts.extend(_detect_amas_signes(planetes))
    bouts.extend(_detect_amas_maisons(planetes))

    # === 11. MAISONS 5–7–8 + état des maîtres ===
    bouts.extend(_analyser_maisons_relationnelles(planetes, theme))

    # === 12. ASPECTS MAJEURS AMOUR ===
    bouts.extend(_analyser_aspects_majeurs(theme))

    # === 13. POINTS FORTS DÉJÀ CALCULÉS ===
    pf_amour = _extraire_points_forts_amour(theme)
    if pf_amour:
        bouts.append("\n**Points forts / enjeux relationnels déjà repérés** :")
        bouts.extend(f"- {ligne}" for ligne in pf_amour[:3])

    # Limite dure pour ne pas noyer le LLM
    lignes = [b for b in bouts if b and b.strip()]
    MAX_LIGNES = 22
    lignes = lignes[:MAX_LIGNES]

    texte = "\n".join(lignes).strip()
    return (
        texte
        or "Contexte amour : données globales du thème non disponibles, mais les placements détaillés sont fournis ci-dessous."
    )