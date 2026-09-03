# ────────────────────────────────────────────────
# 🌌 FONCTIONS ASTROLOGIQUES UTILISÉES DANS calcul_theme
# Ce fichier regroupe les fonctions de calcul de base utilisées
# pour déterminer maisons, signes, aspects, nakshatras et dominances.
# Elles sont toutes utilisées dans le flux principal de calcul_theme().
# ────────────────────────────────────────────────

# get_maison_planete(degre, cusps)
# ➜ Détermine dans quelle maison se trouve un degré donné en fonction
#   des cuspides de maisons (liste de 12 valeurs en degrés).
#   Retourne un entier 1–12 (maison).
#
# degre_vers_signe(degre)
# ➜ Convertit un degré absolu (0–360°) en :
#   - Nom du signe zodiacal
#   - Degré dans ce signe (0–29.xx)
#
# angle_diff(a1, a2)
# ➜ Calcule la différence d’angle absolue entre deux positions,
#   en tenant compte du cercle (0°–360°). Sert pour les aspects.
#
# get_nakshatra_name(degree_sidereal)
# ➜ Détermine le nom du nakshatra (astrologie védique) associé
#   à un degré sidéral donné.
#
# detecter_aspects(positions)
# ➜ Analyse toutes les paires de planètes et retourne une liste
#   d’aspects trouvés (conjonction, opposition, trigone, carré, sextile)
#   avec orbe et distance exacts.
#
# get_maitre_ascendant(signe_asc)
# ➜ Retourne le maître planétaire d’un signe donné (astrologie occidentale).
#
# maisons_vediques_fixes(signe_asc_sid)
# ➜ Crée la structure des 12 maisons védiques fixes en fonction
#   du signe sidéral de l’Ascendant.
#
# maison_vedique_planete_simple(signe_planete, signe_asc_sid)
# ➜ Calcule la maison védique (1–12) d’une planète à partir
#   de son signe sidéral et du signe sidéral de l’Ascendant.
# ────────────────────────────────────────────────

SIGNES_ZODIAC = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
                 'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']

NAKSHATRAS = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
    'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
]

ANGLES_ASPECTS = {'conjonction': 0, 'opposition': 180, 'trigone': 120, 'carre': 90, 'sextile': 60}
ORBES_DEFAUT = {'conjonction': 10, 'opposition': 8, 'trigone': 8, 'carre': 8, 'sextile': 6}

MAITRES_SIGNES = {
    'Bélier': 'Mars', 'Taureau': 'Vénus', 'Gémeaux': 'Mercure', 'Cancer': 'Lune',
    'Lion': 'Soleil', 'Vierge': 'Mercure', 'Balance': 'Vénus', 'Scorpion': 'Pluton',
    'Sagittaire': 'Jupiter', 'Capricorne': 'Saturne', 'Verseau': 'Uranus', 'Poissons': 'Neptune'
}

SECONDS_MAITRES_SIGNES = {
    'Scorpion': 'Mars',
    'Verseau': 'Saturne',
    'Poissons': 'Jupiter',
}

def get_maison_planete(degre, cusps):
    degre = degre % 360  # Normaliser le degré
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        
        if start <= end:
            if start <= degre < end:
                return i + 1
        else:  # Passage par 0°
            if degre >= start or degre < end:
                return i + 1
    return 1  # Par défaut maison 1

def degre_vers_signe(degre):
    index = int(degre // 30)
    if index >= len(SIGNES_ZODIAC):  # Protection contre les débordements
        index = 0
    return SIGNES_ZODIAC[index], round(degre % 30, 2)

def angle_diff(a1, a2):
    """
    Calcule la différence d'angle absolue entre deux positions (en degrés),
    en tenant compte du cercle zodiacal (0°–360°).
    """
    diff = abs(a1 - a2) % 360
    return diff if diff <= 180 else 360 - diff

def get_nakshatra_name(degree_sidereal):
    index = int(degree_sidereal // (360 / 27))
    if index >= len(NAKSHATRAS):  # Protection
        index = 0
    return NAKSHATRAS[index]

def detecter_aspects(positions):
    aspects = []
    noms = list(positions.keys())

    for i in range(len(noms)):
        for j in range(i + 1, len(noms)):
            p1, p2 = noms[i], noms[j]
            if (p1, p2) in [("Rahu", "Ketu"), ("Ketu", "Rahu")]:
                continue
            a1, a2 = positions[p1], positions[p2]
            orb_used = ORBES_DEFAUT if ("Ascendant" not in (p1, p2)) else {k: max(8, v) for k, v in ORBES_DEFAUT.items()}

            for aspect, angle in ANGLES_ASPECTS.items():
                ecart = abs(angle_diff(a1, a2) - angle)
                if ecart <= orb_used[aspect]:
                    aspects.append({
                        'planete1': p1,
                        'planete2': p2,
                        'aspect': aspect.capitalize(),
                        'distance': round(angle_diff(a1, a2), 2),
                        'orbe': round(ecart, 2),
                        'angle_exact': angle
                    })
                    break
    aspects.sort(key=lambda x: x['orbe'])
    return aspects

def get_maitre_ascendant(signe_asc):
    """
    Retourne uniquement le maître principal (moderne).
    """
    return MAITRES_SIGNES.get(signe_asc)

def get_maitre_ascendant_vedique(signe_asc):
    """
    Retourne le maître traditionnel utilisé en astrologie védique.
    """
    maitres_vediques = {
        'Bélier': 'Mars',
        'Taureau': 'Vénus',
        'Gémeaux': 'Mercure',
        'Cancer': 'Lune',
        'Lion': 'Soleil',
        'Vierge': 'Mercure',
        'Balance': 'Vénus',
        'Scorpion': 'Mars',
        'Sagittaire': 'Jupiter',
        'Capricorne': 'Saturne',
        'Verseau': 'Saturne',
        'Poissons': 'Jupiter',
    }

    return maitres_vediques.get(signe_asc)

def get_maitres_ascendant(signe_asc):
    """
    Retourne le maître principal puis le second maître éventuel.

    Exemples :
        Scorpion -> ("Pluton", "Mars")
        Verseau  -> ("Uranus", "Saturne")
        Poissons -> ("Neptune", "Jupiter")
        Bélier   -> ("Mars", None)
    """
    principal = MAITRES_SIGNES.get(signe_asc)
    secondaire = SECONDS_MAITRES_SIGNES.get(signe_asc)

    return principal, secondaire

def formater_maitres_ascendant(principal, secondaire=None):
    if secondaire:
        return (
            f"Maître d’Ascendant principal : {principal} "
            f"— second maître traditionnel : {secondaire}"
        )

    return f"Maître d’Ascendant : {principal}"


def maisons_vediques_fixes(signe_asc_sid):
    index_asc = SIGNES_ZODIAC.index(signe_asc_sid)
    maisons = {}
    for i in range(12):
        signe_mais = SIGNES_ZODIAC[(index_asc + i) % 12]
        maisons[f'Maison {i+1}'] = {
            'signe': signe_mais,
            'degre': 0.0,
            'degre_dans_signe': 0.0
        }
    return maisons



def maison_vedique_planete_simple(signe_planete, signe_asc_sid):
    signes = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
              'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
    index_asc = signes.index(signe_asc_sid)
    index_plan = signes.index(signe_planete)
    distance = (index_plan - index_asc) % 12
    return distance + 1

def detecter_amas_et_zones_chargees(
    planetes: dict,
    min_planetes: int = 3,
    ecart_voisins_max: float = 8.0,
    etendue_max: float = 15.0,
) -> dict:
    """
    Détecte séparément :

    1. Les amas planétaires :
       - au moins 3 planètes ;
       - même signe ou même maison ;
       - écart maximal de 8° entre deux membres voisins ;
       - étendue totale maximale de 15°.

    2. Les signes et maisons chargés :
       - au moins 3 planètes ;
       - aucune obligation de proximité en degrés.

    Planètes prises en compte :
    Soleil, Lune, Mercure, Vénus, Mars,
    Jupiter, Saturne, Uranus, Neptune et Pluton.
    """

    planetes_autorisees = {
        "Soleil",
        "Lune",
        "Mercure",
        "Vénus",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturne",
        "Uranus",
        "Neptune",
        "Pluton",
    }

    planetes_personnelles = {
        "Soleil",
        "Lune",
        "Mercure",
        "Vénus",
        "Venus",
        "Mars",
    }

    placements_valides = []

    for nom, placement in (planetes or {}).items():
        if nom not in planetes_autorisees:
            continue

        if not isinstance(placement, dict):
            continue

        longitude = placement.get("longitude", placement.get("degre"))
        signe = placement.get("signe")
        maison = placement.get("maison")

        try:
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue

        nom_normalise = "Vénus" if nom == "Venus" else nom

        placements_valides.append({
            "planete": nom_normalise,
            "longitude": longitude % 360.0,
            "signe": signe,
            "maison": maison,
        })

    def classifier_amas(membres: list[dict]) -> str:
        nb_personnelles = sum(
            membre["planete"] in planetes_personnelles
            for membre in membres
        )

        if nb_personnelles >= 2:
            return "personnel"

        if nb_personnelles == 1:
            return "mixte"

        return "générationnel"

    def trouver_amas_dans_groupe(membres: list[dict]) -> list[dict]:
        """
        Cherche les sous-groupes rapprochés à l'intérieur
        d'un même signe ou d'une même maison.
        """
        if len(membres) < min_planetes:
            return []

        membres_tries = sorted(
            membres,
            key=lambda item: item["longitude"],
        )

        amas_trouves = []

        for debut in range(len(membres_tries)):
            groupe = [membres_tries[debut]]

            for suivant in membres_tries[debut + 1:]:
                ecart_voisin = suivant["longitude"] - groupe[-1]["longitude"]
                etendue = suivant["longitude"] - groupe[0]["longitude"]

                if (
                    ecart_voisin <= ecart_voisins_max
                    and etendue <= etendue_max
                ):
                    groupe.append(suivant)
                else:
                    break

            if len(groupe) >= min_planetes:
                noms = [membre["planete"] for membre in groupe]

                if not any(
                    item["membres"] == noms
                    for item in amas_trouves
                ):
                    amas_trouves.append({
                        "type": classifier_amas(groupe),
                        "membres": noms,
                        "etendue": round(
                            groupe[-1]["longitude"]
                            - groupe[0]["longitude"],
                            2,
                        ),
                    })

        return amas_trouves

    groupes_signes = {}
    groupes_maisons = {}

    for placement in placements_valides:
        signe = placement.get("signe")
        maison = placement.get("maison")

        if signe:
            groupes_signes.setdefault(signe, []).append(placement)

        if maison is not None:
            groupes_maisons.setdefault(str(maison), []).append(placement)

    signes_charges = []
    maisons_chargees = []
    amas_signes = []
    amas_maisons = []

    for signe, membres in groupes_signes.items():
        if len(membres) >= min_planetes:
            signes_charges.append({
                "signe": signe,
                "membres": [
                    item["planete"]
                    for item in sorted(
                        membres,
                        key=lambda item: item["longitude"],
                    )
                ],
            })

        for amas in trouver_amas_dans_groupe(membres):
            amas_signes.append({
                "signe": signe,
                **amas,
            })

    for maison, membres in groupes_maisons.items():
        if len(membres) >= min_planetes:
            maisons_chargees.append({
                "maison": int(maison),
                "membres": [
                    item["planete"]
                    for item in sorted(
                        membres,
                        key=lambda item: item["longitude"],
                    )
                ],
            })

        for amas in trouver_amas_dans_groupe(membres):
            amas_maisons.append({
                "maison": int(maison),
                **amas,
            })

    signes_charges.sort(
        key=lambda item: (-len(item["membres"]), item["signe"])
    )

    maisons_chargees.sort(
        key=lambda item: (-len(item["membres"]), item["maison"])
    )

    return {
        "amas_signes": amas_signes,
        "amas_maisons": amas_maisons,
        "signes_charges": signes_charges,
        "maisons_chargees": maisons_chargees,
    }