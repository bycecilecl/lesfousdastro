"""
Détection et structuration des configurations astrologiques.

Ce module transforme une liste d'aspects individuels en figures
astrologiques cohérentes, tout en conservant les aspects qui ne sont
pas absorbés par une configuration.
"""

from typing import Any, Dict, List, Optional

# ============================================================
# CONSTANTES
# ============================================================

ORBE_CONJONCTION_BLOC = 8.0
ORBE_POINTS_CONJONCTIONS_IDENTITAIRES = 5.0
ORBE_ASPECT_CONFIGURATION = 5.0
ORBE_OPPOSITION_T_CARRE = 8.0
ORBE_CARRE_T_CARRE = 7.0
ORBE_OPPOSITION_GRAND_CARRE = 8.0
ORBE_CARRE_GRAND_CARRE = 10.0
ORBE_GRAND_TRIGONE = 10.0
# ORBE_STELLIUM = 8.0
# ORBE_T_CARRE = 5.0
# ORBE_GRAND_TRIGONE = 5.0

CORPS_CONFIGURATIONS_MAJEURES = {
    "Ascendant",
    "MC",
    "Soleil",
    "Lune",
    "Mercure",
    "Vénus",
    "Mars",
    "Jupiter",
    "Saturne",
    "Uranus",
    "Neptune",
    "Pluton",
}

POINTS_CONJONCTIONS_IDENTITAIRES = {
    "Chiron",
    "Lune Noire",
}

ANCRAGES_CONJONCTIONS_IDENTITAIRES = {
    "Soleil",
    "Lune",
    "Ascendant",
}

DIGNITES_ASTROLOGIQUES = {
    "Soleil": {
        "domicile": ["Lion"],
        "exaltation": ["Bélier"],
        "exil": ["Verseau"],
        "chute": ["Balance"],
    },
    "Lune": {
        "domicile": ["Cancer"],
        "exaltation": ["Taureau"],
        "exil": ["Capricorne"],
        "chute": ["Scorpion"],
    },
    "Mercure": {
        "domicile": ["Gémeaux", "Vierge"],
        "exaltation": ["Vierge"],
        "exil": ["Sagittaire", "Poissons"],
        "chute": ["Poissons"],
    },
    "Vénus": {
        "domicile": ["Taureau", "Balance"],
        "exaltation": ["Poissons"],
        "exil": ["Scorpion", "Bélier"],
        "chute": ["Vierge"],
    },
    "Mars": {
        "domicile": ["Bélier", "Scorpion"],
        "exaltation": ["Capricorne"],
        "exil": ["Balance", "Taureau"],
        "chute": ["Cancer"],
    },
    "Jupiter": {
        "domicile": ["Sagittaire", "Poissons"],
        "exaltation": ["Cancer"],
        "exil": ["Gémeaux", "Vierge"],
        "chute": ["Capricorne"],
    },
    "Saturne": {
        "domicile": ["Capricorne", "Verseau"],
        "exaltation": ["Balance"],
        "exil": ["Cancer", "Lion"],
        "chute": ["Bélier"],
    },

    "Uranus": {
    "domicile": ["Verseau"],
    "exaltation": ["Scorpion"],
    "exil": ["Lion"],
    "chute": ["Taureau"],
    },

    "Neptune": {
        "domicile": ["Poissons"],
        "exaltation": ["Lion"],
        "exil": ["Vierge"],
        "chute": ["Verseau"],
    },

    "Pluton": {
        "domicile": ["Scorpion"],
        "exaltation": ["Bélier"],
        "exil": ["Taureau"],
        "chute": ["Balance"],
    },
}

SCORES_DIGNITES = {
    "domicile": 4,
    "exaltation": 3,
    "neutre": 0,
    "exil": -3,
    "chute": -4,
}

AFFINITES_PLANETES_MAISONS = {
    "Soleil": {
        "tres_forte": [1, 5],
        "delicate": [7, 11],
    },
    "Lune": {
        "tres_forte": [4],
        "delicate": [10],
    },
    "Mercure": {
        "tres_forte": [3, 6],
        "delicate": [9, 12],
    },
    "Vénus": {
        "tres_forte": [2, 7],
        "delicate": [8, 1],
    },
    "Mars": {
        "tres_forte": [1, 8],
        "delicate": [7, 2],
    },
    "Jupiter": {
        "tres_forte": [9, 12],
        "delicate": [3, 6],
    },
    "Saturne": {
        "tres_forte": [10, 11],
        "delicate": [4, 5],
    },
    "Uranus": {
        "tres_forte": [11],
        "delicate": [5],
    },
    "Neptune": {
        "tres_forte": [12],
        "delicate": [6],
    },
    "Pluton": {
        "tres_forte": [8],
        "delicate": [2],
    },
}

SCORES_AFFINITES_MAISONS = {
    "tres_forte": 2,
    "neutre": 0,
    "delicate": -1,
}

ORBE_STELLIUM = 8.0

ORDRE_SIGNES = {
    "Bélier": 0,
    "Taureau": 1,
    "Gémeaux": 2,
    "Cancer": 3,
    "Lion": 4,
    "Vierge": 5,
    "Balance": 6,
    "Scorpion": 7,
    "Sagittaire": 8,
    "Capricorne": 9,
    "Verseau": 10,
    "Poissons": 11,
}

PLANETES_STELLIUM = {
    "Soleil",
    "Lune",
    "Mercure",
    "Vénus",
    "Mars",
    "Jupiter",
    "Saturne",
    "Uranus",
    "Neptune",
    "Pluton",
}

PLANETES_PERSONNELLES_STELLIUM = {
    "Soleil",
    "Lune",
    "Mercure",
    "Vénus",
    "Mars",
}





# ============================================================
# OUTILS GÉNÉRAUX
# ============================================================

def normaliser_aspect(aspect: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Normalise un aspect pour permettre la détection des configurations.

    Retourne une structure uniforme :
      {
          "planete1": "Mars",
          "planete2": "Saturne",
          "aspect": "conjonction",
          "orbe": 2.4,
          "source": {...}
      }

    Tolère les clés :
      - planete1 / planete2
      - p1 / p2
    """
    if not isinstance(aspect, dict):
        return None

    planete1 = str(
        aspect.get("planete1")
        or aspect.get("p1")
        or ""
    ).strip()

    planete2 = str(
        aspect.get("planete2")
        or aspect.get("p2")
        or ""
    ).strip()

    nom_aspect = str(aspect.get("aspect") or "").strip().lower()
    nom_aspect = (
        nom_aspect
        .replace("semi-carre", "semi-carré")
        .replace("sesqui-carre", "sesqui-carré")
        .replace("carre", "carré")
    )

    try:
        orbe = float(str(aspect.get("orbe")).replace(",", "."))
    except (TypeError, ValueError):
        return None

    if not planete1 or not planete2 or not nom_aspect:
        return None

    return {
        "planete1": planete1,
        "planete2": planete2,
        "aspect": nom_aspect,
        "orbe": orbe,
        "source": aspect,
    }

def calculer_position_absolue(
    position: Dict[str, Any],
) -> Optional[float]:
    """
    Retourne la longitude zodiacale absolue d'une position,
    comprise entre 0° et 360°.

    Formats acceptés :
    - longitude
    - degre_absolu
    - position_absolue
    - signe + degré dans le signe
    - degré déjà absolu
    """
    if not isinstance(position, dict):
        return None

    longitude = position.get("longitude")

    if longitude is None:
        longitude = position.get("degre_absolu")

    if longitude is None:
        longitude = position.get("position_absolue")

    if longitude is not None:
        try:
            return float(longitude) % 360
        except (TypeError, ValueError):
            return None

    degre = position.get("degre")

    if degre is None:
        degre = position.get("degree")

    if degre is None:
        return None

    try:
        degre = float(degre)
    except (TypeError, ValueError):
        return None

    # Le degré fourni est déjà une longitude absolue.
    if degre >= 30:
        return degre % 360

    signe = position.get("signe") or position.get("sign")

    if not signe:
        return degre % 360

    index_signe = ORDRE_SIGNES.get(signe)

    if index_signe is None:

        return None

    return (index_signe * 30 + degre) % 360

def calculer_amplitude_zodiacale(
    longitudes: List[float],
) -> float | None:
    """
    Calcule la plus petite amplitude zodiacale contenant toutes
    les longitudes fournies.

    Cette méthode gère correctement le passage par 0° Bélier.

    Exemples :
      [209, 211, 214] -> 5°
      [358, 1, 4]     -> 6°
    """
    if not longitudes:
        return None

    try:
        positions = sorted(
            float(longitude) % 360
            for longitude in longitudes
        )
    except (TypeError, ValueError):
        return None

    if len(positions) == 1:
        return 0.0

    ecarts = []

    for index in range(len(positions) - 1):
        ecarts.append(
            positions[index + 1] - positions[index]
        )

    ecart_passage_zero = (
        positions[0] + 360 - positions[-1]
    )
    ecarts.append(ecart_passage_zero)

    plus_grand_vide = max(ecarts)

    return 360 - plus_grand_vide

def construire_graphe_conjonctions(
    conjonctions: List[Dict[str, Any]],
) -> Dict[str, set[str]]:
    """
    Construit un graphe des planètes reliées par des conjonctions.

    Exemple :

        Mars ----- Saturne
                   |
                 Pluton

    devient :

    {
        "Mars": {"Saturne"},
        "Saturne": {"Mars", "Pluton"},
        "Pluton": {"Saturne"},
    }
    """
    graphe: Dict[str, set[str]] = {}

    for conjonction in conjonctions:
        planetes = conjonction["planetes"]

        if len(planetes) != 2:
            continue

        p1, p2 = planetes

        graphe.setdefault(p1, set()).add(p2)
        graphe.setdefault(p2, set()).add(p1)

    return graphe

def detecter_groupes_conjonctions(
    graphe: Dict[str, set[str]],
) -> List[List[str]]:
    """
    Détecte les groupes de planètes reliées entre elles
    dans le graphe des conjonctions.

    Exemple :

    {
        "Mars": {"Saturne"},
        "Saturne": {"Mars", "Pluton"},
        "Pluton": {"Saturne"},
        "Mercure": {"Vénus"},
        "Vénus": {"Mercure"},
    }

    devient :

    [
        ["Mars", "Pluton", "Saturne"],
        ["Mercure", "Vénus"],
    ]
    """
    groupes: List[List[str]] = []
    planetes_visitees: set[str] = set()

    for planete_depart in graphe:
        if planete_depart in planetes_visitees:
            continue

        groupe: set[str] = set()
        planetes_a_visiter = [planete_depart]

        while planetes_a_visiter:
            planete = planetes_a_visiter.pop()

            if planete in planetes_visitees:
                continue

            planetes_visitees.add(planete)
            groupe.add(planete)

            voisines = graphe.get(planete, set())

            for voisine in voisines:
                if voisine not in planetes_visitees:
                    planetes_a_visiter.append(voisine)

        if groupe:
            groupes.append(sorted(groupe))

    return groupes

def detecter_candidats_stelliums(
    groupes: List[List[str]],
) -> List[List[str]]:
    """
    Conserve uniquement les groupes contenant au moins trois
    planètes principales.

    Les astéroïdes, angles, nœuds et points fictifs peuvent enrichir
    un stellium, mais ne servent pas à atteindre le minimum de trois.
    """
    candidats = []

    for groupe in groupes:
        planetes_principales = [
            planete
            for planete in groupe
            if planete in PLANETES_STELLIUM
        ]

        if len(planetes_principales) >= 3:
            candidats.append(groupe)

    return candidats

def valider_candidats_stelliums(
    candidats: List[List[str]],
    positions: Dict[str, Dict[str, Any]],
    orbe_max: float = ORBE_STELLIUM,
) -> List[Dict[str, Any]]:
    """
    Valide les candidats stelliums selon leur amplitude zodiacale.

    Un candidat est conservé si :
      - toutes les positions planétaires sont disponibles ;
      - son amplitude zodiacale est inférieure ou égale à l'orbe maximal.

    Cette fonction crée les premiers objets stelliums,
    encore non enrichis.
    """
    stelliums: List[Dict[str, Any]] = []

    for planetes in candidats:
        planetes_principales = [
            planete
            for planete in planetes
            if planete in PLANETES_STELLIUM
        ]

        if len(planetes_principales) < 3:
            continue

        planetes_personnelles = [
            planete
            for planete in planetes_principales
            if planete in PLANETES_PERSONNELLES_STELLIUM
        ]

        if len(planetes_personnelles) < 2:
            continue
        longitudes = []
        positions_manquantes = False

        for planete in planetes_principales:
            position = positions.get(planete, {})
            longitude = calculer_position_absolue(position)

            if longitude is None:
                positions_manquantes = True
                break

            longitudes.append(longitude)

        if positions_manquantes:
            continue

        amplitude = calculer_amplitude_zodiacale(longitudes)

        if amplitude is None:
            continue

        if amplitude > orbe_max:
            continue

        planetes_triees = sorted(planetes)

        stelliums.append({
            "id": f"stellium_{'_'.join(planetes_triees)}",
            "type": "stellium",
            "etat": "valide",
            "planetes": planetes_triees,
            "nb_planetes": len(planetes_triees),
            "nb_planetes_principales": len(planetes_principales),
            "nb_planetes_personnelles": len(planetes_personnelles),
            "amplitude": amplitude,
            "orbe_max": orbe_max,
            "signes": [],
            "maisons": [],
            "dissociee": None,
            "planete_dominante": None,
            "niveau_dominance": None,
            "raison_dominance": None,
            "aspects_recus": [],
        })

    return stelliums

def analyser_stelliums(
    conjonctions: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]],
    orbe_max: float = ORBE_STELLIUM,
) -> List[Dict[str, Any]]:
    """
    Détecte, valide et enrichit les stelliums
    à partir des conjonctions.
    """
    graphe = construire_graphe_conjonctions(
        conjonctions
    )

    groupes = detecter_groupes_conjonctions(
        graphe
    )

    candidats = detecter_candidats_stelliums(
        groupes
    )

    stelliums = valider_candidats_stelliums(
        candidats,
        positions,
        orbe_max=orbe_max,
    )

    stelliums = enrichir_configurations_avec_positions(
        stelliums,
        positions,
    )

    stelliums = enrichir_configurations_avec_signes(
        stelliums,
    )

    stelliums = enrichir_configurations_avec_maisons(
        stelliums,
    )

    stelliums = enrichir_configurations_avec_aspects(
        stelliums,
        aspects,
    )

    stelliums = enrichir_configurations_avec_dominance(
        stelliums,
    )

    return stelliums


# ============================================================
# CALCULS ASTROLOGIQUES
# ============================================================


def determiner_dignite_planete(
    planete: str,
    signe: str,
) -> Dict[str, Any]:
    """
    Détermine la dignité essentielle d'une planète dans un signe.

    Retourne :
      {
          "planete": "Soleil",
          "signe": "Bélier",
          "dignite": "exaltation",
          "score": 3,
      }
    """
    planete = str(planete or "").strip()
    signe = str(signe or "").strip()

    dignite = "neutre"

    dignites_planete = DIGNITES_ASTROLOGIQUES.get(planete, {})

    for nom_dignite in (
        "domicile",
        "exaltation",
        "exil",
        "chute",
    ):
        signes = dignites_planete.get(nom_dignite, [])

        if signe in signes:
            dignite = nom_dignite
            break

    return {
        "planete": planete,
        "signe": signe,
        "dignite": dignite,
        "score": SCORES_DIGNITES[dignite],
    }


def determiner_affinite_maison(
    planete: str,
    maison: int | str | None,
) -> Dict[str, Any]:
    """
    Détermine l'affinité d'une planète avec la maison qu'elle occupe.

    Retourne par exemple :
      {
          "planete": "Vénus",
          "maison": 7,
          "affinite": "tres_forte",
          "score": 2,
      }

    Une maison absente ou invalide retourne une affinité neutre.
    """
    planete = str(planete or "").strip()

    try:
        numero_maison = int(maison)
    except (TypeError, ValueError):
        numero_maison = None

    affinite = "neutre"

    affinites_planete = AFFINITES_PLANETES_MAISONS.get(
        planete,
        {},
    )

    if numero_maison is not None:
        for nom_affinite in (
            "tres_forte",
            "delicate",
        ):
            maisons = affinites_planete.get(nom_affinite, [])

            if numero_maison in maisons:
                affinite = nom_affinite
                break

    return {
        "planete": planete,
        "maison": numero_maison,
        "affinite": affinite,
        "score": SCORES_AFFINITES_MAISONS[affinite],
    }

def calculer_force_planete(
    planete: str,
    position: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcule la force d'une planète à partir de :
      - sa dignité dans le signe ;
      - son affinité avec la maison.

    Format attendu pour position :
      {
          "signe": "Bélier",
          "maison": 1,
      }
    """
    signe = str(
        position.get("signe")
        or position.get("sign")
        or ""
    ).strip()

    maison = (
        position.get("maison")
        or position.get("house")
    )

    dignite = determiner_dignite_planete(
        planete,
        signe,
    )

    affinite_maison = determiner_affinite_maison(
        planete,
        maison,
    )

    score_total = (
        dignite["score"]
        + affinite_maison["score"]
    )

    return {
        "planete": planete,
        "signe": signe,
        "maison": affinite_maison["maison"],
        "dignite": dignite["dignite"],
        "score_dignite": dignite["score"],
        "affinite_maison": affinite_maison["affinite"],
        "score_maison": affinite_maison["score"],
        "score_total": score_total,
    }


# ============================================================
# CONFIGURATIONS
# ============================================================

def detecter_conjonctions(
    aspects: List[Dict[str, Any]],
    orbe_max: float = ORBE_CONJONCTION_BLOC,
) -> List[Dict[str, Any]]:
    """
    Détecte les conjonctions suffisamment serrées pour former un bloc.

    La fonction :
      - normalise chaque aspect ;
      - conserve uniquement les conjonctions ;
      - exclut celles dont l'orbe dépasse la limite ;
      - retourne une structure exploitable par les futures configurations.

    Elle ne calcule pas encore :
      - les signes ;
      - les maisons ;
      - la planète dominante ;
      - les aspects reçus par la conjonction.
    """
    conjonctions: List[Dict[str, Any]] = []

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        if aspect["aspect"] != "conjonction":
            continue

        if aspect["orbe"] > orbe_max:
            continue

        planete1 = aspect["planete1"]
        planete2 = aspect["planete2"]

        conjonction_majeure = (
            planete1 in CORPS_CONFIGURATIONS_MAJEURES
            and planete2 in CORPS_CONFIGURATIONS_MAJEURES
        )

        point_identitaire_avec_ancrage = (
            aspect["orbe"]
            <= ORBE_POINTS_CONJONCTIONS_IDENTITAIRES
            and (
                (
                    planete1 in POINTS_CONJONCTIONS_IDENTITAIRES
                    and planete2 in ANCRAGES_CONJONCTIONS_IDENTITAIRES
                )
                or (
                    planete2 in POINTS_CONJONCTIONS_IDENTITAIRES
                    and planete1 in ANCRAGES_CONJONCTIONS_IDENTITAIRES
                )
            )
        )

        if not (
            conjonction_majeure
            or point_identitaire_avec_ancrage
        ):
            continue

        planetes = sorted([planete1, planete2])

        conjonctions.append({
            "id": f"conjonction_{planetes[0]}_{planetes[1]}",
            "type": "conjonction",
            "etat": "simple",
            "planetes": planetes,
            "orbe": aspect["orbe"],
            "nb_planetes": len(planetes),
            "source": aspect["source"],
            "signes": [],
            "maisons": [],
            "dissociee": None,
            "planete_dominante": None,
            "niveau_dominance": None,
            "raison_dominance": None,
            "aspects_recus": [],
        })

    return conjonctions

def detecter_t_carres(
    aspects: List[Dict[str, Any]],
    orbe_opposition: float = ORBE_OPPOSITION_T_CARRE,
    orbe_carre: float = ORBE_CARRE_T_CARRE,
) -> List[Dict[str, Any]]:
    """
    Détecte les T-carrés simples à trois planètes.

    Structure recherchée :

        planète A opposée à planète B
        planète C carrée à planète A
        planète C carrée à planète B

    La planète C est la planète focale du T-carré.

    Cette première version fonctionne directement à partir
    des aspects bruts et ne gère pas encore les pôles composés
    de plusieurs planètes conjointes.
    """
    aspects_normalises: List[Dict[str, Any]] = []

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        planete1 = aspect["planete1"]
        planete2 = aspect["planete2"]

        if (
            planete1 not in CORPS_CONFIGURATIONS_MAJEURES
            or planete2 not in CORPS_CONFIGURATIONS_MAJEURES
        ):
            continue

        aspects_normalises.append(aspect)

    oppositions = [
        aspect
        for aspect in aspects_normalises
        if (
            aspect["aspect"] == "opposition"
            and aspect["orbe"] <= orbe_opposition
        )
    ]

    carres = [
        aspect
        for aspect in aspects_normalises
        if (
            aspect["aspect"] == "carré"
            and aspect["orbe"] <= orbe_carre
        )
    ]

    t_carres: List[Dict[str, Any]] = []
    ids_deja_detectes: set[str] = set()

    for opposition in oppositions:
        extremite1 = opposition["planete1"]
        extremite2 = opposition["planete2"]

        planetes_candidates = set()

        for carre in carres:
            p1 = carre["planete1"]
            p2 = carre["planete2"]

            if p1 == extremite1:
                planetes_candidates.add(p2)
            elif p2 == extremite1:
                planetes_candidates.add(p1)

        for planete_focale in planetes_candidates:
            if planete_focale in {
                extremite1,
                extremite2,
            }:
                continue

            carre_extremite1 = None
            carre_extremite2 = None

            for carre in carres:
                paire = {
                    carre["planete1"],
                    carre["planete2"],
                }

                if paire == {
                    extremite1,
                    planete_focale,
                }:
                    carre_extremite1 = carre

                elif paire == {
                    extremite2,
                    planete_focale,
                }:
                    carre_extremite2 = carre

            if (
                carre_extremite1 is None
                or carre_extremite2 is None
            ):
                continue

            extremites_triees = sorted([
                extremite1,
                extremite2,
            ])

            id_t_carre = (
                f"t_carre_"
                f"{extremites_triees[0]}_"
                f"{extremites_triees[1]}_"
                f"{planete_focale}"
            )

            if id_t_carre in ids_deja_detectes:
                continue

            ids_deja_detectes.add(id_t_carre)

            planetes = sorted({
                extremite1,
                extremite2,
                planete_focale,
            })

            t_carres.append({
                "id": id_t_carre,
                "type": "t_carre",
                "etat": "valide",
                "planetes": planetes,
                "nb_planetes": len(planetes),

                "planetes_en_opposition": extremites_triees,
                "planete_focale": planete_focale,

                "aspects_constitutifs": [
                    {
                        "planete1": opposition["planete1"],
                        "planete2": opposition["planete2"],
                        "aspect": opposition["aspect"],
                        "orbe": opposition["orbe"],
                        "source": opposition["source"],
                    },
                    {
                        "planete1": carre_extremite1["planete1"],
                        "planete2": carre_extremite1["planete2"],
                        "aspect": carre_extremite1["aspect"],
                        "orbe": carre_extremite1["orbe"],
                        "source": carre_extremite1["source"],
                    },
                    {
                        "planete1": carre_extremite2["planete1"],
                        "planete2": carre_extremite2["planete2"],
                        "aspect": carre_extremite2["aspect"],
                        "orbe": carre_extremite2["orbe"],
                        "source": carre_extremite2["source"],
                    },
                ],

                "compose_de": [],

                "signes": [],
                "maisons": [],
                "dissociee": None,

                "planete_dominante": None,
                "niveau_dominance": None,
                "raison_dominance": None,
                "aspects_recus": [],
            })

    return t_carres

def fusionner_t_carres_sommets_conjoints(
    t_carres: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
    orbe_conjonction: float = ORBE_CONJONCTION_BLOC,
) -> List[Dict[str, Any]]:
    """
    Regroupe les T-carrés qui possèdent :

    - la même opposition de base ;
    - des planètes focales conjointes.

    Exemple :
    - Lune opposée Saturne, Vénus focale
    - Lune opposée Saturne, Jupiter focal
    - Vénus conjointe Jupiter

    deviennent un seul T-carré à sommet conjoint
    Vénus–Jupiter.
    """

    if not t_carres:
        return []

    # ========================================================
    # 1. Construire les groupes de planètes conjointes
    # ========================================================

    parents: Dict[str, str] = {}

    def trouver_racine(planete: str) -> str:
        parents.setdefault(planete, planete)

        if parents[planete] != planete:
            parents[planete] = trouver_racine(
                parents[planete]
            )

        return parents[planete]

    def unir(planete1: str, planete2: str) -> None:
        racine1 = trouver_racine(planete1)
        racine2 = trouver_racine(planete2)

        if racine1 == racine2:
            return

        # Racine stable pour éviter des résultats variables.
        racine_commune = min(racine1, racine2)
        autre_racine = max(racine1, racine2)

        parents[autre_racine] = racine_commune

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        if aspect["aspect"] != "conjonction":
            continue

        if aspect["orbe"] > orbe_conjonction:
            continue

        planete1 = aspect.get("planete1")
        planete2 = aspect.get("planete2")

        if not planete1 or not planete2:
            continue

        unir(planete1, planete2)

    # Enregistrer aussi toutes les planètes des T-carrés,
    # même lorsqu’elles ne participent à aucune conjonction.
    for t_carre in t_carres:
        for planete in (
            t_carre.get("planetes_en_opposition")
            or []
        ):
            if planete:
                trouver_racine(planete)

        planete_focale = t_carre.get(
            "planete_focale"
        )

        if planete_focale:
            trouver_racine(planete_focale)

        for planete in (
            t_carre.get("planetes_focales")
            or []
        ):
            if planete:
                trouver_racine(planete)

    # ========================================================
    # 2. Regrouper les T-carrés par sommets équivalents
    #
    # Deux planètes conjointes représentent ici le même sommet,
    # qu’il s’agisse de l’apex ou d’un pôle d’opposition.
    # ========================================================

    groupes_t_carres: Dict[
        tuple,
        List[Dict[str, Any]],
    ] = {}

    t_carres_non_groupables: List[
        Dict[str, Any]
    ] = []

    for t_carre in t_carres:
        opposition = list(
            t_carre.get("planetes_en_opposition")
            or []
        )

        if len(opposition) != 2:
            t_carres_non_groupables.append(
                t_carre
            )
            continue

        focales = list(
            t_carre.get("planetes_focales")
            or []
        )

        if not focales:
            planete_focale = t_carre.get(
                "planete_focale"
            )

            if planete_focale:
                focales = [planete_focale]

        if not focales:
            t_carres_non_groupables.append(
                t_carre
            )
            continue

        racines_opposition = tuple(sorted({
            trouver_racine(opposition[0]),
            trouver_racine(opposition[1]),
        }))

        racines_focales = tuple(sorted({
            trouver_racine(planete)
            for planete in focales
        }))

        # Un T-carré doit garder deux pôles d’opposition
        # réellement distincts.
        if len(racines_opposition) != 2:
            t_carres_non_groupables.append(
                t_carre
            )
            continue

        cle_groupe = (
            racines_opposition,
            racines_focales,
        )

        groupes_t_carres.setdefault(
            cle_groupe,
            [],
        ).append(t_carre)

    # ========================================================
    # 3. Fusionner chaque groupe
    # ========================================================

    resultats: List[Dict[str, Any]] = []

    for cle_groupe, groupe in groupes_t_carres.items():
        if len(groupe) == 1:
            resultats.append(groupe[0])
            continue

        racines_opposition, racines_focales = (
            cle_groupe
        )

        poles_par_racine = {
            racine: set()
            for racine in racines_opposition
        }

        focales_fusionnees = set()
        aspects_constitutifs = []

        aspects_deja_vus = set()

        for t_carre in groupe:
            for planete in (
                t_carre.get(
                    "planetes_en_opposition"
                )
                or []
            ):
                racine = trouver_racine(
                    planete
                )

                if racine in poles_par_racine:
                    poles_par_racine[
                        racine
                    ].add(planete)

            focales = list(
                t_carre.get(
                    "planetes_focales"
                )
                or []
            )

            if not focales:
                planete_focale = t_carre.get(
                    "planete_focale"
                )

                if planete_focale:
                    focales = [
                        planete_focale
                    ]

            focales_fusionnees.update(
                focales
            )

            for aspect in (
                t_carre.get(
                    "aspects_constitutifs"
                )
                or []
            ):
                cle_aspect = (
                    aspect.get("planete1"),
                    aspect.get("aspect"),
                    aspect.get("planete2"),
                    aspect.get("orbe"),
                )

                if cle_aspect in aspects_deja_vus:
                    continue

                aspects_deja_vus.add(
                    cle_aspect
                )

                aspects_constitutifs.append(
                    aspect
                )

        groupes_opposition = [
            sorted(
                poles_par_racine[racine]
            )
            for racine in racines_opposition
        ]

        planetes_opposition_fusionnees = sorted({
            planete
            for groupe_pole in groupes_opposition
            for planete in groupe_pole
        })

        focales_fusionnees = sorted(
            focales_fusionnees
        )

        configuration_fusionnee = dict(
            groupe[0]
        )

        configuration_fusionnee["id"] = (
            "t_carre_"
            + "_".join(
                planetes_opposition_fusionnees
            )
            + "_sommet_"
            + "_".join(
                focales_fusionnees
            )
        )

        configuration_fusionnee["etat"] = (
            "sommets_conjoints"
        )

        # Nouvelle information structurée :
        # chaque sous-liste représente un pôle d’opposition.
        configuration_fusionnee[
            "groupes_opposition"
        ] = groupes_opposition

        configuration_fusionnee[
            "planetes_en_opposition"
        ] = planetes_opposition_fusionnees

        if len(focales_fusionnees) == 1:
            configuration_fusionnee[
                "planete_focale"
            ] = focales_fusionnees[0]
        else:
            configuration_fusionnee[
                "planete_focale"
            ] = None

        configuration_fusionnee[
            "planetes_focales"
        ] = focales_fusionnees

        configuration_fusionnee[
            "planetes"
        ] = sorted(
            set(
                planetes_opposition_fusionnees
            )
            | set(focales_fusionnees)
        )

        configuration_fusionnee[
            "nb_planetes"
        ] = len(
            configuration_fusionnee[
                "planetes"
            ]
        )

        configuration_fusionnee[
            "aspects_constitutifs"
        ] = aspects_constitutifs

        configuration_fusionnee[
            "configurations_fusionnees"
        ] = [
            t_carre.get("id")
            for t_carre in groupe
            if t_carre.get("id")
        ]

        resultats.append(
            configuration_fusionnee
        )

    resultats.extend(
        t_carres_non_groupables
    )

    return resultats

def detecter_grands_trigones(aspects):
    """
    Détecte les grands trigones entre les corps astrologiques majeurs.

    Un grand trigone est formé de trois corps reliés
    chacun aux deux autres par un trigone.
    """

    trigones = set()

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        if aspect["aspect"] != "trigone":
            continue

        planete1 = aspect["planete1"]
        planete2 = aspect["planete2"]
        orbe = aspect["orbe"]

        if orbe > ORBE_GRAND_TRIGONE:
            continue

        if (
            planete1 not in CORPS_CONFIGURATIONS_MAJEURES
            or planete2 not in CORPS_CONFIGURATIONS_MAJEURES
        ):
            continue

        trigones.add(
            tuple(sorted((planete1, planete2)))
        )

    planetes = sorted(
        {
            planete
            for paire in trigones
            for planete in paire
        }
    )

    grands_trigones = []

    for index1 in range(len(planetes)):
        for index2 in range(index1 + 1, len(planetes)):
            for index3 in range(index2 + 1, len(planetes)):
                planete1 = planetes[index1]
                planete2 = planetes[index2]
                planete3 = planetes[index3]

                paire12 = tuple(sorted((planete1, planete2)))
                paire13 = tuple(sorted((planete1, planete3)))
                paire23 = tuple(sorted((planete2, planete3)))

                if (
                    paire12 in trigones
                    and paire13 in trigones
                    and paire23 in trigones
                ):
                    grands_trigones.append(
                        {
                            "type": "grand_trigone",
                            "planetes": [
                                planete1,
                                planete2,
                                planete3,
                            ],
                        }
                    )

    return grands_trigones


def fusionner_grands_trigones_sommets_conjoints(
    grands_trigones,
    conjonctions,
):
    """
    Fusionne les grands trigones qui représentent une même structure
    lorsque certains sommets sont constitués de planètes conjointes.

    Exemple :
        Lune - Soleil - Neptune
        Lune - Vénus - Neptune
        Lune - Soleil - Uranus
        Lune - Vénus - Uranus

    devient :
        Lune / Soleil-Vénus / Neptune-Uranus
    """

    if not grands_trigones:
        return []

    groupes_conjonctions = []

    for conjonction in conjonctions:
        planetes = set(
            conjonction.get(
                "planetes",
                [],
            )
        )

        if len(planetes) >= 2:
            groupes_conjonctions.append(planetes)

    def trouver_groupe(planete):
        """
        Retourne le groupe de conjonction auquel appartient la planète.
        Si elle n'est dans aucune conjonction, elle forme son propre groupe.
        """

        for groupe in groupes_conjonctions:
            if planete in groupe:
                return frozenset(groupe)

        return frozenset([planete])

    structures_fusionnees = {}

    for grand_trigone in grands_trigones:
        planetes = grand_trigone.get(
            "planetes",
            [],
        )

        if len(planetes) != 3:
            continue

        sommets = [
            trouver_groupe(planete)
            for planete in planetes
        ]

        sommets_uniques = []

        for sommet in sommets:
            if sommet not in sommets_uniques:
                sommets_uniques.append(sommet)

        if len(sommets_uniques) != 3:
            continue

        cle = tuple(
            sorted(
                (
                    tuple(sorted(sommet))
                    for sommet in sommets_uniques
                ),
                key=lambda groupe: tuple(groupe),
            )
        )

        structures_fusionnees[cle] = {
            "type": "grand_trigone",
            "sommets": [
                list(sommet)
                for sommet in sommets_uniques
            ],
            "planetes": sorted(
                {
                    planete
                    for sommet in sommets_uniques
                    for planete in sommet
                }
            ),
        }

    return list(structures_fusionnees.values())

def detecter_grands_carres(aspects):
    """
    Détecte les Grands Carrés entre les corps astrologiques majeurs.

    Un Grand Carré comporte quatre corps avec :
    - deux paires en opposition ;
    - quatre carrés reliant les deux axes d'opposition.

    Les six aspects constitutifs sont conservés afin de pouvoir
    indiquer ensuite qu'un aspect individuel appartient au Grand Carré.
    """

    oppositions = set()
    carres = set()

    # Conserve les données complètes de chaque aspect :
    # planètes, type et orbe.
    aspects_par_paire = {}

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        type_aspect = aspect["aspect"]
        planete1 = aspect["planete1"]
        planete2 = aspect["planete2"]

        orbe = aspect["orbe"]

        if (
            type_aspect == "opposition"
            and orbe > ORBE_OPPOSITION_GRAND_CARRE
        ):
            continue

        if (
            type_aspect == "carré"
            and orbe > ORBE_CARRE_GRAND_CARRE
        ):
            continue

        if (
            planete1 not in CORPS_CONFIGURATIONS_MAJEURES
            or planete2 not in CORPS_CONFIGURATIONS_MAJEURES
        ):
            continue

        paire = tuple(
            sorted(
                (
                    planete1,
                    planete2,
                )
            )
        )

        if type_aspect == "opposition":
            oppositions.add(paire)
            aspects_par_paire[
                (paire, "opposition")
            ] = aspect

        elif type_aspect == "carré":
            carres.add(paire)
            aspects_par_paire[
                (paire, "carré")
            ] = aspect

    grands_carres = []
    configurations_vues = set()

    liste_oppositions = list(oppositions)

    for index1 in range(len(liste_oppositions)):
        opposition1 = liste_oppositions[index1]

        for index2 in range(
            index1 + 1,
            len(liste_oppositions),
        ):
            opposition2 = liste_oppositions[index2]

            planetes = set(opposition1 + opposition2)

            # Un Grand Carré doit comporter quatre corps différents.
            if len(planetes) != 4:
                continue

            planete_a, planete_c = opposition1
            planete_b, planete_d = opposition2

            carres_attendus = {
                tuple(sorted((planete_a, planete_b))),
                tuple(sorted((planete_a, planete_d))),
                tuple(sorted((planete_c, planete_b))),
                tuple(sorted((planete_c, planete_d))),
            }

            if not carres_attendus.issubset(carres):
                continue

            cle = tuple(sorted(planetes))

            if cle in configurations_vues:
                continue

            configurations_vues.add(cle)

            aspects_constitutifs = []

            # Les deux oppositions du Grand Carré.
            for paire_opposition in (
                opposition1,
                opposition2,
            ):
                aspect = aspects_par_paire.get(
                    (paire_opposition, "opposition")
                )

                if aspect:
                    aspects_constitutifs.append({
                        "planete1": aspect["planete1"],
                        "planete2": aspect["planete2"],
                        "aspect": aspect["aspect"],
                        "orbe": aspect["orbe"],
                        "source": aspect["source"],
                    })

            # Les quatre carrés du Grand Carré.
            for paire_carre in sorted(carres_attendus):
                aspect = aspects_par_paire.get(
                    (paire_carre, "carré")
                )

                if aspect:
                    aspects_constitutifs.append({
                        "planete1": aspect["planete1"],
                        "planete2": aspect["planete2"],
                        "aspect": aspect["aspect"],
                        "orbe": aspect["orbe"],
                        "source": aspect["source"],
                    })

            grands_carres.append(
                {
                    "type": "grand_carre",
                    "planetes": sorted(planetes),
                    "oppositions": [
                        list(opposition1),
                        list(opposition2),
                    ],
                    "aspects_constitutifs": aspects_constitutifs,
                }
            )

    return grands_carres

# def detecter_grands_carres(aspects):
#     """
#     Détecte les Grands Carrés entre les corps astrologiques majeurs.

#     Un Grand Carré comporte quatre corps avec :
#     - deux paires en opposition ;
#     - quatre carrés reliant les deux axes d'opposition.
#     """

#     oppositions = set()
#     carres = set()

#     for aspect in aspects:
#         type_aspect = aspect.get("aspect")
#         planete1 = aspect.get("planete1")
#         planete2 = aspect.get("planete2")

#         if (
#             planete1 not in CORPS_CONFIGURATIONS_MAJEURES
#             or planete2 not in CORPS_CONFIGURATIONS_MAJEURES
#         ):
#             continue

#         paire = tuple(
#             sorted(
#                 (
#                     planete1,
#                     planete2,
#                 )
#             )
#         )

#         if type_aspect == "Opposition":
#             oppositions.add(paire)

#         elif type_aspect in {"Carre", "Carré"}:
#             carres.add(paire)

#     grands_carres = []
#     configurations_vues = set()

#     liste_oppositions = list(oppositions)

#     for index1 in range(len(liste_oppositions)):
#         opposition1 = liste_oppositions[index1]

#         for index2 in range(
#             index1 + 1,
#             len(liste_oppositions),
#         ):
#             opposition2 = liste_oppositions[index2]

#             planetes = set(opposition1 + opposition2)

#             # Un Grand Carré doit comporter quatre corps différents.
#             if len(planetes) != 4:
#                 continue

#             planete_a, planete_c = opposition1
#             planete_b, planete_d = opposition2

#             carres_attendus = {
#                 tuple(sorted((planete_a, planete_b))),
#                 tuple(sorted((planete_a, planete_d))),
#                 tuple(sorted((planete_c, planete_b))),
#                 tuple(sorted((planete_c, planete_d))),
#             }

#             if not carres_attendus.issubset(carres):
#                 continue

#             cle = tuple(sorted(planetes))

#             if cle in configurations_vues:
#                 continue

#             configurations_vues.add(cle)

#             grands_carres.append(
#                 {
#                     "type": "grand_carre",
#                     "planetes": sorted(planetes),
#                     "oppositions": [
#                         list(opposition1),
#                         list(opposition2),
#                     ],
#                 }
#             )

#     return grands_carres


def fusionner_grands_carres_sommets_conjoints(
    grands_carres,
    conjonctions,
):
    """
    Regroupe les sommets d'un Grand Carré lorsque certaines planètes
    sont conjointes.

    Exemple :
        Soleil opposé Saturne
        Vénus opposée Saturne
        Lune opposée Mars

    avec Soleil conjoint Vénus devient un sommet :
        Soleil + Vénus
    """

    if not grands_carres:
        return []

    groupes_conjonctions = []

    for conjonction in conjonctions:
        planetes = set(
            conjonction.get(
                "planetes",
                [],
            )
        )

        if len(planetes) >= 2:
            groupes_conjonctions.append(planetes)

    # Fusionne aussi les groupes de conjonctions qui se chevauchent.
    groupes_fusionnes = []

    for groupe in groupes_conjonctions:
        groupe_courant = set(groupe)
        groupes_restants = []

        for groupe_existant in groupes_fusionnes:
            if groupe_courant & groupe_existant:
                groupe_courant.update(groupe_existant)
            else:
                groupes_restants.append(groupe_existant)

        groupes_restants.append(groupe_courant)
        groupes_fusionnes = groupes_restants

    def trouver_groupe(planete):
        for groupe in groupes_fusionnes:
            if planete in groupe:
                return frozenset(groupe)

        return frozenset([planete])

    configurations_fusionnees = {}

    for grand_carre in grands_carres:
        planetes = grand_carre.get(
            "planetes",
            [],
        )

        if len(planetes) != 4:
            continue

        sommets = []

        for planete in planetes:
            groupe = trouver_groupe(planete)

            if groupe not in sommets:
                sommets.append(groupe)

        # Une conjonction peut réduire les quatre planètes détectées
        # à moins de quatre groupes astrologiques distincts.
        # On conserve malgré tout la structure enrichie.
        cle = tuple(
            sorted(
                (
                    tuple(sorted(sommet))
                    for sommet in sommets
                ),
                key=lambda groupe: tuple(groupe),
            )
        )

        oppositions_fusionnees = []

        for opposition in grand_carre.get(
            "oppositions",
            [],
        ):
            if len(opposition) != 2:
                continue

            sommet1 = trouver_groupe(opposition[0])
            sommet2 = trouver_groupe(opposition[1])

            opposition_fusionnee = [
                list(sommet1),
                list(sommet2),
            ]

            cle_opposition = tuple(
                sorted(
                    (
                        tuple(sorted(sommet1)),
                        tuple(sorted(sommet2)),
                    )
                )
            )

            if not any(
                opposition_existante["cle"]
                == cle_opposition
                for opposition_existante
                in oppositions_fusionnees
            ):
                oppositions_fusionnees.append(
                    {
                        "cle": cle_opposition,
                        "sommets": opposition_fusionnee,
                    }
                )

        configurations_fusionnees[cle] = {
            "type": "grand_carre",
            "sommets": [
                sorted(sommet)
                for sommet in sommets
            ],
            "planetes": sorted(
                {
                    planete
                    for sommet in sommets
                    for planete in sommet
                }
            ),
            "oppositions": [
                opposition["sommets"]
                for opposition in oppositions_fusionnees
            ],

            # Conserver les six aspects détectés en amont :
            # deux oppositions et quatre carrés.
            "aspects_constitutifs": grand_carre.get(
                "aspects_constitutifs",
                [],
            ),
        }

    return list(configurations_fusionnees.values())

def retirer_t_carres_inclus_dans_grands_carres(
    t_carres: List[Dict[str, Any]],
    grands_carres: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Retire les T-carrés déjà contenus dans un Grand Carré.

    Un T-carré est inclus dans un Grand Carré lorsque toutes
    les planètes qui le composent appartiennent également
    au Grand Carré.
    """

    if not t_carres:
        return []

    if not grands_carres:
        return t_carres

    ensembles_grands_carres = []

    for grand_carre in grands_carres:
        planetes_grand_carre = {
            planete
            for planete in grand_carre.get("planetes", [])
            if planete
        }

        if planetes_grand_carre:
            ensembles_grands_carres.append(
                planetes_grand_carre
            )

    t_carres_conserves = []

    for t_carre in t_carres:
        planetes_t_carre = {
            planete
            for planete in t_carre.get("planetes", [])
            if planete
        }

        inclus_dans_grand_carre = any(
            planetes_t_carre
            and planetes_t_carre.issubset(
                planetes_grand_carre
            )
            for planetes_grand_carre
            in ensembles_grands_carres
        )

        if not inclus_dans_grand_carre:
            t_carres_conserves.append(t_carre)

    return t_carres_conserves

def enrichir_configurations_avec_positions(
    configurations: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ajoute les positions détaillées des planètes à chaque configuration.

    Deux clés sont alimentées pour rester compatible avec tout le moteur :

    - "positions" :
      utilisée par les fonctions d'enrichissement internes
      comme les signes, les maisons et la dominance ;

    - "infos_planetes" :
      utilisée par le formateur destiné au prompt du LLM.
    """

    for configuration in configurations:
        positions_configuration: Dict[
            str,
            Dict[str, Any],
        ] = {}

        infos_planetes: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for planete in configuration.get("planetes", []):
            position_source = positions.get(planete) or {}

            signe = str(
                position_source.get("signe")
                or position_source.get("sign")
                or ""
            ).strip()

            maison = position_source.get("maison")

            if maison is None:
                maison = position_source.get("house")

            degre = position_source.get("degre")

            if degre is None:
                degre = position_source.get("degree")

            longitude = calculer_position_absolue(
                position_source
            )

            donnees_position = {
                "signe": signe or None,
                "degre": degre,
                "maison": maison,
                "longitude": longitude,
            }

            positions_configuration[planete] = dict(
                donnees_position
            )

            infos_planetes[planete] = dict(
                donnees_position
            )

        configuration["positions"] = (
            positions_configuration
        )

        configuration["infos_planetes"] = (
            infos_planetes
        )

    return configurations

def enrichir_configurations_avec_signes(
    configurations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ajoute les signes des planètes et détermine si la configuration
    est dissociée.

    Cette fonction utilise les positions déjà intégrées
    dans chaque configuration.
    """
    for configuration in configurations:
        signes = []

        for position in configuration.get("positions", {}).values():
            signe = position.get("signe")

            if signe and signe not in signes:
                signes.append(signe)

        configuration["signes"] = signes

        if len(signes) >= 2:
            configuration["dissociee"] = True
        elif len(signes) == 1:
            configuration["dissociee"] = False
        else:
            configuration["dissociee"] = None

    return configurations

def enrichir_configurations_avec_maisons(
    configurations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ajoute les maisons occupées par les planètes
    de chaque configuration.

    Les positions doivent avoir été intégrées auparavant avec
    enrichir_configurations_avec_positions().

    Cette fonction modifie les configurations en place
    et retourne la même liste enrichie.
    """
    for configuration in configurations:
        maisons = []

        for position in configuration.get("positions", {}).values():
            maison = position.get("maison")

            if maison is None:
                continue

            try:
                maison = int(maison)
            except (TypeError, ValueError):
                continue

            if maison not in maisons:
                maisons.append(maison)

        configuration["maisons"] = sorted(maisons)

    return configurations

def enrichir_conjonctions_avec_signes(
    conjonctions: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fonction de compatibilité pour les anciens appels.

    Les positions sont intégrées dans les configurations avant
    l'enrichissement des signes.
    """
    conjonctions = enrichir_configurations_avec_positions(
        conjonctions,
        positions,
    )

    return enrichir_configurations_avec_signes(
        conjonctions,
    )

def enrichir_configurations_avec_aspects(
    configurations: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Recherche les aspects reçus par chaque configuration.

    Compatible avec :
      - les conjonctions ;
      - les stelliums ;
      - les futures configurations contenant un champ "planetes".

    Cette fonction modifie les configurations en place
    et retourne la même liste enrichie.
    """
    aspects_normalises = []

    for aspect_brut in aspects:
        aspect = normaliser_aspect(aspect_brut)

        if aspect is None:
            continue

        if aspect["orbe"] > ORBE_ASPECT_CONFIGURATION:
            continue

        aspects_normalises.append(aspect)

    for configuration in configurations:
        planetes_configuration = set(
            configuration.get("planetes", [])
        )

        aspects_groupes: Dict[tuple, Dict[str, Any]] = {}

        for aspect in aspects_normalises:
            if aspect["aspect"] == "conjonction":
                continue

            planete1 = aspect["planete1"]
            planete2 = aspect["planete2"]

            planete_interne = None
            planete_exterieure = None

            if (
                planete1 in planetes_configuration
                and planete2 not in planetes_configuration
            ):
                planete_interne = planete1
                planete_exterieure = planete2

            elif (
                planete2 in planetes_configuration
                and planete1 not in planetes_configuration
            ):
                planete_interne = planete2
                planete_exterieure = planete1

            if (
                planete_interne is None
                or planete_exterieure is None
            ):
                continue

            cle = (
                planete_exterieure,
                aspect["aspect"],
            )

            if cle not in aspects_groupes:
                aspects_groupes[cle] = {
                    "planete_exterieure": planete_exterieure,
                    "aspect": aspect["aspect"],
                    "planetes_touchees": [],
                    "orbes": [],
                    "sources": [],
                }

            groupe = aspects_groupes[cle]

            if planete_interne not in groupe["planetes_touchees"]:
                groupe["planetes_touchees"].append(
                    planete_interne
                )

            groupe["orbes"].append(aspect["orbe"])
            groupe["sources"].append(aspect["source"])

        aspects_recus = []

        for aspect_recu in aspects_groupes.values():
            planetes_touchees = set(
                aspect_recu["planetes_touchees"]
            )

            if planetes_touchees == planetes_configuration:
                aspect_recu["portee"] = "bloc"
            else:
                aspect_recu["portee"] = "partielle"

            aspect_recu["orbe_representatif"] = min(
                aspect_recu["orbes"]
            )

            aspects_recus.append(aspect_recu)

        configuration["aspects_recus"] = aspects_recus

    return configurations

def enrichir_conjonctions_avec_aspects(
    conjonctions: List[Dict[str, Any]],
    aspects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fonction de compatibilité pour les anciens appels.
    """
    return enrichir_configurations_avec_aspects(
        conjonctions,
        aspects,
    )

def enrichir_configurations_avec_dominance(
    configurations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Calcule la force de chaque planète d'une configuration
    et détermine la planète dominante.

    Les positions doivent avoir été ajoutées auparavant avec
    enrichir_configurations_avec_positions().

    En cas d'égalité au meilleur score :
      - aucune planète dominante unique n'est désignée ;
      - les planètes arrivées en tête sont enregistrées
        dans "planetes_codominantes".

    Cette fonction modifie les configurations en place
    et retourne la même liste enrichie.
    """
    for configuration in configurations:
        forces_planetes: Dict[str, Dict[str, Any]] = {}

        positions_configuration = configuration.get(
            "positions",
            {},
        )

        for planete in configuration.get("planetes", []):
            position = positions_configuration.get(
                planete,
                {},
            )

            force = calculer_force_planete(
                planete,
                position,
            )

            forces_planetes[planete] = {
                "signe": force["signe"],
                "maison": force["maison"],
                "dignite": force["dignite"],
                "affinite_maison": force[
                    "affinite_maison"
                ],
                "criteres": {
                    "dignite": force["score_dignite"],
                    "maison": force["score_maison"],
                },
                "score_total": force["score_total"],
            }

        configuration["forces_planetes"] = forces_planetes
        configuration["planetes_codominantes"] = []

        if not forces_planetes:
            configuration["planete_dominante"] = None
            configuration["niveau_dominance"] = None
            configuration["raison_dominance"] = (
                "aucune_donnee"
            )
            continue

        score_max = max(
            force["score_total"]
            for force in forces_planetes.values()
        )

        planetes_en_tete = [
            planete
            for planete, force in forces_planetes.items()
            if force["score_total"] == score_max
        ]

        if len(planetes_en_tete) > 1:
            configuration["planete_dominante"] = None
            configuration["planetes_codominantes"] = sorted(
                planetes_en_tete
            )
            configuration["niveau_dominance"] = (
                "codominance"
            )
            configuration["raison_dominance"] = (
                "scores_maximaux_identiques"
            )
            continue

        planete_dominante = planetes_en_tete[0]

        autres_scores = [
            force["score_total"]
            for planete, force in forces_planetes.items()
            if planete != planete_dominante
        ]

        ecart = (
            score_max - max(autres_scores)
            if autres_scores
            else 0
        )

        if ecart >= 5:
            niveau = "tres_forte"
        elif ecart >= 3:
            niveau = "forte"
        else:
            niveau = "legere"

        configuration["planete_dominante"] = (
            planete_dominante
        )
        configuration["niveau_dominance"] = niveau
        configuration["raison_dominance"] = (
            "score_superieur"
        )

    return configurations

def enrichir_conjonctions_avec_dominance(
    conjonctions: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Fonction de compatibilité pour les anciens appels.

    Le paramètre positions est conservé temporairement,
    mais les données sont désormais lues dans chaque configuration.
    """
    if positions is not None:
        conjonctions = enrichir_configurations_avec_positions(
            conjonctions,
            positions,
        )

    return enrichir_configurations_avec_dominance(
        conjonctions,
    )

def analyser_conjonctions(
    aspects: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]],
    orbe_max: float = ORBE_CONJONCTION_BLOC,
) -> List[Dict[str, Any]]:
    """
    Détecte et enrichit toutes les conjonctions du thème.
    """
    conjonctions = detecter_conjonctions(
        aspects,
        orbe_max=orbe_max,
    )

    conjonctions = enrichir_configurations_avec_positions(
        conjonctions,
        positions,
    )

    conjonctions = enrichir_configurations_avec_signes(
        conjonctions,
    )

    conjonctions = enrichir_configurations_avec_maisons(
        conjonctions,
    )

    conjonctions = enrichir_configurations_avec_aspects(
        conjonctions,
        aspects,
    )

    conjonctions = enrichir_configurations_avec_dominance(
        conjonctions,
    )

    return conjonctions

# def enrichir_configurations_avec_positions(
#     configurations: List[Dict[str, Any]],
#     positions: Dict[str, Dict[str, Any]],
# ) -> List[Dict[str, Any]]:
#     """
#     Ajoute à chaque configuration les informations de position
#     des planètes concernées : signe, maison et longitude.
#     """

#     for configuration in configurations:
#         infos_planetes = {}

#         for planete in configuration.get("planetes", []):
#             position = positions.get(planete) or {}

#             infos_planetes[planete] = {
#                 "signe": position.get("signe"),
#                 "maison": position.get("maison"),
#                 "longitude": position.get("longitude"),
#             }

#         configuration["infos_planetes"] = infos_planetes

#     return configurations

def analyser_configurations_majeures(
    aspects: List[Dict[str, Any]],
    positions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Détecte l'ensemble des grandes configurations du thème.

    Cette fonction constitue le point d'entrée unique du moteur
    des configurations astrologiques.

    Chaque nouvelle figure (T-carré, Yod, Grand Trigone...)
    viendra simplement s'ajouter ici.
    """

    configurations: List[Dict[str, Any]] = []

    conjonctions = analyser_conjonctions(
        aspects,
        positions,
    )

    stelliums = analyser_stelliums(
        conjonctions,
        aspects,
        positions,
    )

    t_carres = detecter_t_carres(
        aspects,
    )
    
    t_carres = fusionner_t_carres_sommets_conjoints(
        t_carres,
        aspects,
    )
    grands_trigones = detecter_grands_trigones(
        aspects,
    )

    grands_trigones = fusionner_grands_trigones_sommets_conjoints(
        grands_trigones,
        conjonctions,
    )

    grands_carres = detecter_grands_carres(
        aspects,
    )

    grands_carres = fusionner_grands_carres_sommets_conjoints(
        grands_carres,
        conjonctions,
    )

    t_carres = retirer_t_carres_inclus_dans_grands_carres(
        t_carres,
        grands_carres,
    )

    configurations.extend(conjonctions)
    configurations.extend(stelliums)
    configurations.extend(t_carres)
    configurations.extend(grands_trigones)
    configurations.extend(grands_carres)

    configurations = enrichir_configurations_avec_positions(
        configurations,
        positions,
    )

    return configurations

def annoter_aspects_appartenant_aux_configurations(
    texte_aspects: str,
    configurations: List[Dict[str, Any]],
) -> str:
    """
    Annote les aspects individuels qui appartiennent déjà
    à une configuration majeure.

    Exemple :

    Mars Carre Saturne (orbe 0.12°)

    devient :

    Mars Carre Saturne (orbe 0.12°)
    [fait partie du Grand Carré Mars-Pluton-Saturne-Uranus]
    """

    if not texte_aspects or not configurations:
        return texte_aspects

    def cle_aspect(
        planete1: str,
        aspect: str,
        planete2: str,
    ) -> tuple:
        nom_aspect = (
            str(aspect or "")
            .strip()
            .lower()
            .replace("carre", "carré")
        )

        planetes = sorted([
            str(planete1 or "").strip(),
            str(planete2 or "").strip(),
        ])

        return (
            planetes[0],
            nom_aspect,
            planetes[1],
        )

    noms_par_aspect = {}

    for configuration in configurations:
        type_configuration = configuration.get("type")

        if type_configuration == "t_carre":
            nom_type = "T-carré"

        elif type_configuration == "grand_carre":
            nom_type = "Grand Carré"

        elif type_configuration == "grand_trigone":
            nom_type = "Grand Trigone"

        else:
            continue

        planetes_configuration = sorted(
            configuration.get("planetes", [])
        )

        nom_configuration = (
            f"{nom_type} "
            + "-".join(planetes_configuration)
        )

        for aspect in configuration.get(
            "aspects_constitutifs",
            [],
        ):
            cle = cle_aspect(
                aspect.get("planete1"),
                aspect.get("aspect"),
                aspect.get("planete2"),
            )

            noms_par_aspect.setdefault(
                cle,
                [],
            )

            if nom_configuration not in noms_par_aspect[cle]:
                noms_par_aspect[cle].append(
                    nom_configuration
                )

    lignes_resultat = []

    for ligne in texte_aspects.splitlines():
        ligne_propre = ligne.strip()

        if not ligne_propre:
            continue

        ligne_sans_tiret = ligne_propre.lstrip("- ").strip()
        morceaux = ligne_sans_tiret.split()

        cle_trouvee = None

        # Format attendu :
        # Mars Carre Saturne (orbe 0.12°)
        if len(morceaux) >= 3:
            planete1 = morceaux[0]
            aspect = morceaux[1]
            planete2 = morceaux[2]

            cle_candidate = cle_aspect(
                planete1,
                aspect,
                planete2,
            )

            if cle_candidate in noms_par_aspect:
                cle_trouvee = cle_candidate

        lignes_resultat.append(ligne_propre)

        if cle_trouvee:
            noms = noms_par_aspect[cle_trouvee]

            lignes_resultat.append(
                "[fait partie de "
                + " et de ".join(noms)
                + " ; à interpréter avec la configuration, "
                + "sans répéter séparément la même dynamique]"
            )

    return "\n".join(lignes_resultat)

def formater_configurations_majeures(configurations):
    """
    Transforme les configurations astrologiques en texte lisible
    destiné au prompt des LLM.
    """

    if not configurations:
        return "Aucune configuration majeure détectée."

    lignes = []

    groupes_stelliums = [
        set(configuration.get("planetes", []))
        for configuration in configurations
        if configuration.get("type") == "stellium"
    ]

    conjonctions_dans_stelliums = set()

    for configuration in configurations:
        if configuration.get("type") != "conjonction":
            continue

        planetes_conjonction = set(
            configuration.get("planetes", [])
        )

        if any(
            planetes_conjonction.issubset(groupe_stellium)
            for groupe_stellium in groupes_stelliums
        ):
            conjonctions_dans_stelliums.add(
                configuration.get("id")
            )

    for configuration in configurations:
        type_configuration = configuration.get("type", "")

        if (
            type_configuration == "conjonction"
            and configuration.get("id")
            in conjonctions_dans_stelliums
        ):
            continue
    
        type_cfg = type_configuration.replace("_", " ").title()

        infos_planetes = configuration.get(
            "infos_planetes",
            {},
        )

        def formater_planete(planete):
            infos = infos_planetes.get(planete, {})

            signe = infos.get("signe")
            maison = infos.get("maison")

            texte = planete

            if signe:
                texte += f" en {signe}"

            if maison is not None:
                texte += f" maison {maison}"

            return texte

        if type_configuration == "stellium":
            planetes_stellium = set(
                configuration.get("planetes", [])
            )

            planetes = ", ".join(
                formater_planete(planete)
                for planete in configuration.get(
                    "planetes",
                    [],
                )
            )

            conjonctions_internes = []

            for conjonction in configurations:
                if (
                    conjonction.get("id")
                    not in conjonctions_dans_stelliums
                ):
                    continue

                planetes_conjonction = set(
                    conjonction.get("planetes", [])
                )

                if not planetes_conjonction.issubset(
                    planetes_stellium
                ):
                    continue

                noms = conjonction.get("planetes", [])
                orbe = conjonction.get("orbe")

                if len(noms) == 2:
                    conjonctions_internes.append(
                        f"{noms[0]} conjoint {noms[1]} "
                        f"(orbe {orbe}°)"
                    )

            ligne = f"- Stellium : {planetes}"

            if conjonctions_internes:
                ligne += (
                    "\n  Composition interne : "
                    + " ; ".join(conjonctions_internes)
                )

        elif type_configuration == "t_carre":
            focales = configuration.get(
                "planetes_focales",
                [],
            )

            if focales:
                sommet = " + ".join(
                    formater_planete(planete)
                    for planete in focales
                )
            else:
                sommet = formater_planete(
                    configuration.get(
                        "planete_focale",
                        "non précisée",
                    )
                )

            groupes_opposition = configuration.get(
                "groupes_opposition",
                [],
            )

            if groupes_opposition:
                poles_formates = []

                for groupe_pole in groupes_opposition:
                    pole = " + ".join(
                        formater_planete(planete)
                        for planete in groupe_pole
                    )

                    poles_formates.append(pole)

                opposition = " / ".join(
                    poles_formates
                )

            else:
                opposition = " / ".join(
                    formater_planete(planete)
                    for planete in configuration.get(
                        "planetes_en_opposition",
                        [],
                    )
                )

            ligne = (
                f"- T-carré : {sommet} "
                f"(apex), carré à {opposition}"
            )
        

        elif type_configuration == "grand_trigone":

            sommets = configuration.get("sommets")

            if sommets:
                texte_sommets = []

                for sommet in sommets:
                    texte_sommets.append(
                        " + ".join(
                            formater_planete(planete)
                            for planete in sommet
                        )
                    )

                ligne = (
                    "- Grand Trigone : "
                    + " / ".join(texte_sommets)
                )

            else:
                planetes = " / ".join(
                    formater_planete(planete)
                    for planete in configuration.get(
                        "planetes",
                        [],
                    )
                )

                ligne = f"- Grand Trigone : {planetes}"

        elif type_configuration == "grand_carre":

            sommets = configuration.get(
                "sommets",
                [],
            )

            oppositions = configuration.get(
                "oppositions",
                [],
            )

            def formater_sommet(sommet):
                return " + ".join(
                    formater_planete(planete)
                    for planete in sommet
                )

            if oppositions:
                oppositions_formatees = []

                for opposition in oppositions:
                    if len(opposition) != 2:
                        continue

                    sommet1 = formater_sommet(
                        opposition[0]
                    )

                    sommet2 = formater_sommet(
                        opposition[1]
                    )

                    oppositions_formatees.append(
                        f"{sommet1} opposé à {sommet2}"
                    )

                if oppositions_formatees:
                    ligne = (
                        "- Grand Carré : "
                        + " / ".join(oppositions_formatees)
                    )

                else:
                    ligne = (
                        "- Grand Carré : "
                        + " / ".join(
                            formater_sommet(sommet)
                            for sommet in sommets
                        )
                    )

            elif sommets:
                ligne = (
                    "- Grand Carré : "
                    + " / ".join(
                        formater_sommet(sommet)
                        for sommet in sommets
                    )
                )

            else:
                planetes = " / ".join(
                    formater_planete(planete)
                    for planete in configuration.get(
                        "planetes",
                        [],
                    )
                )

                ligne = f"- Grand Carré : {planetes}"

        else:
            planetes = ", ".join(
                configuration.get(
                    "planetes",
                    [],
                )
            )

            ligne = f"- {type_cfg} : {planetes}"

        lignes.append(ligne)

    return "\n".join(lignes)


