import csv
from pathlib import Path
import logging
import unicodedata
from point_astral_famille.calculs_astrologiques import get_maitres_ascendant

logger = logging.getLogger(__name__)

BASE_PATH = Path("data/point_astral")
_CACHE: dict[str, list[dict]] = {}

DIGNITES_PLANETAIRES = {
    "Mercure": {
        "domicile": ["Gémeaux"],
        "exalté": ["Vierge"],
        "exil": ["Sagittaire"],
        "chute": ["Poissons"],
    },
}


def determiner_dignite_bdd(planete: str, signe: str | None) -> list[str]:
    """
    Retourne la dignité active de la planète selon le signe,
    conformément aux règles utilisées dans la BDD.

    Pour Mercure :
    - Gémeaux : domicile
    - Vierge : exalté
    - Sagittaire : exil
    - Poissons : chute
    """
    
    if not signe:
        return []

    dignites = DIGNITES_PLANETAIRES.get(planete, {})
    signe_normalise = normaliser_cle_bdd(signe)

    return [
        dignite
        for dignite, signes in dignites.items()
        if signe_normalise
        in {normaliser_cle_bdd(s) for s in signes}
    ]

COLONNES_POINT_ASTRAL = [
    "INTERPRETATION",
    "IDENTITE",
    "FAMILLE",
    "MA_MERE",
    "MA_PERE",
    "GRANDS_AXES",
    "COMMENT_GERER",
]


def charger_csv(nom_fichier: str) -> list[dict]:
    """
    Charge un CSV/TSV de la base Point Astral avec cache mémoire.
    Nettoie aussi les noms de colonnes.
    """
    if nom_fichier in _CACHE:
        return _CACHE[nom_fichier]

    path = BASE_PATH / nom_fichier

    if not path.exists():
        return []

    with open(path, newline="", encoding="utf-8") as f:
        sample = f.read(2048)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            logger.warning(
                "Impossible de détecter automatiquement le séparateur de %s. "
                "Utilisation du séparateur ';' par défaut.",
                nom_fichier,
            )
            dialect = csv.excel()
            dialect.delimiter = ";"

        reader = csv.DictReader(f, dialect=dialect)

        rows = []
        for row in reader:
            cleaned = {}

            for key, value in row.items():
                if key is None:
                    continue

                clean_key = str(key).strip()

                if isinstance(value, list):
                    clean_value = " ".join(str(v).strip() for v in value if v)
                else:
                    clean_value = str(value or "").strip()

                cleaned[clean_key] = clean_value

            rows.append(cleaned)

    _CACHE[nom_fichier] = rows
    return rows


def rechercher_interpretations(
    astre: str,
    donnee: str,
    valeur: str,
    fichier: str,
) -> list[str]:
    rows = charger_csv(fichier)
    resultats = []

    for row in rows:
        if (
            row.get("TYPE", row.get("ASTRE", "")).strip().lower() == astre.lower()
            and row.get("DONNEE", "").strip().lower() == donnee.lower()
            and row.get("VALEUR", "").strip().lower() == str(valeur).lower()
        ):
            interpretation = row.get("INTERPRETATION", "").strip()

            if interpretation:
                resultats.append(interpretation)

    return resultats


def normaliser_nom_fichier(planete: str) -> str:

    """
    Nouvelle BDD centralisée :
    toutes les planètes / signes / maisons sont dans un seul fichier.
    """
    return "LLM_bdd_astro_placements.csv"


def recuperer_interpretations_planete(
    theme: dict,
    planete: str,
) -> dict:
    """
    Récupère dans la BDD centralisée :

    - la planète en signe ;
    - la planète en maison ;
    - son interprétation rétrograde si elle est rétrograde ;
    - son interprétation d'interception si elle est interceptée.
    """

    planetes = theme.get("planetes", {})
    placement = planetes.get(planete, {}) or {}

    signe = placement.get("signe")
    maison = placement.get("maison")

    est_retrograde = bool(
        placement.get("retrograde", False)
    )

    interceptions = theme.get("interceptions", {}) or {}

    signes_interceptes = (
        interceptions.get("signes_interceptes")
        or interceptions.get("signes_interceptés")
        or interceptions.get("signes")
        or []
    )

    signes_interceptes_normalises = {
        normaliser_cle_bdd(signe)
        for signe in signes_interceptes
        if signe
    }

    est_interceptee = bool(
        placement.get("intercept", False)
        or placement.get("intercepte", False)
        or placement.get("intercepté", False)
        or (
            signe
            and normaliser_cle_bdd(signe)
            in signes_interceptes_normalises
        )
    )

    fichier = normaliser_nom_fichier(planete)

    result = {
        "planete": planete,

        "signe": {
            "valeur": signe,
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "maison": {
            "valeur": maison,
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "retrograde": {
            "actif": est_retrograde,
            "valeur": "retrograde" if est_retrograde else None,
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "interception": {
            "actif": est_interceptee,
            "valeur": planete if est_interceptee else None,
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "domicile": {
            "actif": False,
            "valeur": "domicile",
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "exalté": {
            "actif": False,
            "valeur": "exalté",
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "exil": {
            "actif": False,
            "valeur": "exil",
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },

        "chute": {
            "actif": False,
            "valeur": "chute",
            "trouve": False,
            "interpretation": None,
            "colonnes": {},
        },
    }

    # ==========================================================
    # Planète en signe
    # ==========================================================

    if signe:
        ligne_signe = rechercher_ligne_bdd(
            astre=planete,
            donnee="Signe",
            valeur=signe,
            fichier=fichier,
        )

        if ligne_signe:
            result["signe"]["trouve"] = True
            result["signe"]["interpretation"] = (
                ligne_signe.get("INTERPRETATION")
            )
            result["signe"]["colonnes"] = ligne_signe

    # ==========================================================
    # Planète en maison
    # ==========================================================

    if maison is not None:
        ligne_maison = rechercher_ligne_bdd(
            astre=planete,
            donnee="Maison",
            valeur=str(maison),
            fichier=fichier,
        )

        if ligne_maison:
            result["maison"]["trouve"] = True
            result["maison"]["interpretation"] = (
                ligne_maison.get("INTERPRETATION")
            )
            result["maison"]["colonnes"] = ligne_maison

        else:
            logger.warning(
                "BDD Point Astral: interprétation manquante "
                "pour %s en maison %s",
                planete,
                maison,
            )

    # ==========================================================
    # Planète rétrograde
    #
    # Exemple BDD :
    # Mercure | etat | retrograde
    # ==========================================================

    if est_retrograde:
        ligne_retrograde = rechercher_ligne_bdd(
            astre=planete,
            donnee="etat",
            valeur="retrograde",
            fichier=fichier,
        )

        if ligne_retrograde:
            result["retrograde"]["trouve"] = True
            result["retrograde"]["interpretation"] = (
                ligne_retrograde.get("INTERPRETATION")
            )
            result["retrograde"]["colonnes"] = ligne_retrograde

        else:
            logger.warning(
                "BDD Point Astral: interprétation rétrograde "
                "manquante pour %s",
                planete,
            )

    # ==========================================================
    # Planète interceptée
    #
    # Exemple BDD :
    # interception | planete | Mercure
    # ==========================================================

    if est_interceptee:
        ligne_interception = rechercher_ligne_bdd(
            astre="interception",
            donnee="planete",
            valeur=planete,
            fichier=fichier,
        )

        if ligne_interception:
            result["interception"]["trouve"] = True
            result["interception"]["interpretation"] = (
                ligne_interception.get("INTERPRETATION")
            )
            result["interception"]["colonnes"] = ligne_interception

        else:
            logger.warning(
                "BDD Point Astral: interprétation d'interception "
                "manquante pour %s",
                planete,
            )

    # ==========================================================
    # Dignités planétaires
    #
    # Exemples BDD :
    # Mercure | etat | domicile
    # Mercure | etat | exalté
    # Mercure | etat | exil
    # Mercure | etat | chute
    # ==========================================================

    dignites_actives = determiner_dignite_bdd(planete, signe)

    for dignite in dignites_actives:
        if dignite not in result:
            continue

        result[dignite]["actif"] = True

        ligne_dignite = rechercher_ligne_bdd(
            astre=planete,
            donnee="etat",
            valeur=dignite,
            fichier=fichier,
        )

        if ligne_dignite:
            result[dignite]["trouve"] = True
            result[dignite]["interpretation"] = (
                ligne_dignite.get("INTERPRETATION")
            )
            result[dignite]["colonnes"] = ligne_dignite

        else:
            logger.warning(
                "BDD Point Astral: interprétation de dignité "
                "manquante pour %s (%s)",
                planete,
                dignite,
            )

    return result

PLANETES_BDD = [
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
    "Chiron"
]


def charger_base_theme(theme: dict) -> dict:
    """
    Charge les interprétations astrologiques principales.
    """

    resultats = {}

    # --- Planètes ---
    for planete in PLANETES_BDD:
        resultats[planete] = recuperer_interpretations_planete(
            theme,
            planete,
        )

    # --- MAISONS / SIGNES / MAÎTRES ---
    resultats["domaines_signes"] = (
        recuperer_interpretations_domaines_signes(theme)
    )
    resultats["maitre_ascendant"] = (
        recuperer_interpretations_maitre_ascendant(theme)
    )

    return resultats


def formater_interpretation_planete_bdd(
    base_interpretations: dict,
    planete: str,
    colonnes: list[str] | None = None,
) -> str:
    """
    Formate les interprétations signe + maison d'une planète
    pour injection dans un prompt.
    """

    if colonnes is None:
        colonnes = ["INTERPRETATION", "IDENTITE", "GRANDS_AXES"]

    data = base_interpretations.get(planete, {}) or {}
    lignes = []

    for rubrique in ["signe", "maison"]:

        item = data.get(rubrique, {}) or {}

        if not item.get("trouve"):
            continue

        valeur = item.get("valeur")
        colonnes_data = item.get("colonnes", {}) or {}

        textes = []

        for col in colonnes:

            txt = colonnes_data.get(col, "").strip()

            if txt:
                label_map = {
                    "INTERPRETATION": "Lecture générale",
                    "IDENTITE": "Identité",
                    "GRANDS_AXES": "Grand axe psychologique",
                    "COMMENT_GERER": "Mécanisme de compensation",
                    "FAMILLE": "Dynamique familiale",
                }

                label = label_map.get(col, col)

                textes.append(f"{label} : {txt}")

        if textes:

            if rubrique == "signe":
                titre = f"{planete} en {valeur}"
            else:
                titre = f"{planete} en maison {valeur}"

            lignes.append(
                f"{titre}\n" + "\n".join(textes)
            )

    return "\n\n".join(lignes)

def formater_interpretation_etat_bdd(
    base_interpretations: dict,
    planete: str,
    etat: str,
    colonnes: list[str] | None = None,
) -> str:
    """
    Formate l'interprétation d'un état particulier d'une planète.

    États actuellement pris en charge :
    - "retrograde"
    - "interception"

    Retourne une chaîne vide si :
    - la planète n'est pas concernée ;
    - la ligne BDD n'a pas été trouvée ;
    - les colonnes demandées sont vides.
    """

    if colonnes is None:
        colonnes = ["INTERPRETATION"]

    etat_normalise = normaliser_cle_bdd(etat)

    etats_autorises = {
        "retrograde",
        "interception",
        "domicile",
        "exalte",
        "exil",
        "chute",
    }

    if etat_normalise not in etats_autorises:
        logger.warning(
            "BDD Point Astral: état inconnu '%s' pour %s",
            etat,
            planete,
        )
        return ""
    cle_etat = {
        "exalte": "exalté",
    }.get(etat_normalise, etat_normalise)

    data_planete = base_interpretations.get(planete, {}) or {}
    data_etat = data_planete.get(cle_etat, {}) or {}

    if not data_etat.get("trouve"):
        return ""

    colonnes_data = data_etat.get("colonnes", {}) or {}
    textes = []

    label_map = {
        "INTERPRETATION": "Lecture générale",
        "IDENTITE": "Identité",
        "FAMILLE": "Dynamique familiale",
        "GRANDS_AXES": "Grand axe psychologique",
        "COMMENT_GERER": "Mécanisme de compensation",
    }

    for colonne in colonnes:
        texte = str(colonnes_data.get(colonne) or "").strip()

        if not texte:
            continue

        label = label_map.get(colonne, colonne)
        textes.append(f"{label} : {texte}")

    if not textes:
        return ""

    titres = {
        "retrograde": f"{planete} rétrograde",
        "interception": f"{planete} intercepté(e)",
        "domicile": f"{planete} en domicile",
        "exalte": f"{planete} exalté",
        "exil": f"{planete} en exil",
        "chute": f"{planete} en chute",
    }

    titre = titres[etat_normalise]

    return f"{titre}\n" + "\n".join(textes)

def formater_aspects_emotionnels_bdd(aspects: list[dict]) -> str:
    """
    Formate les aspects émotionnels importants pour injection dans Bloc 2.
    """
    lignes = []

    for a in aspects:

        p1 = a.get("planete1")
        p2 = a.get("planete2")
        aspect = a.get("aspect")
        orbe = a.get("orbe")

        lignes.append(
            f"- {p1} {aspect} {p2} (orbe {orbe}°)"
        )

    return "\n".join(lignes)

def recuperer_interpretations_domaines_signes(
    theme: dict,
    maisons_cibles: list[int] | None = None,
) -> dict:
    """
    Récupère :
    - maison en signe
    - maître de maison en signe
    depuis data/point_astral/maisons_signes.csv
    """
    vus = set()
    rows = charger_csv("maisons_signes.csv")
    if maisons_cibles is not None:
        maisons_cibles = [str(m) for m in maisons_cibles]
    resultats = {
        "maisons": [],
        "maitres_maisons": [],
    }

    # 1. Maisons en signes
    maisons = theme.get("maisons", {})

    for maison, data in maisons.items():
        maison_num = str(maison).replace("Maison ", "")
        if maisons_cibles is not None and maison_num not in maisons_cibles:
            continue
        signe = data.get("signe") if isinstance(data, dict) else None

        if not signe:
            continue

        for row in rows:
            if (
                row.get("DONNEE", "").strip().lower()
                and str(row.get("MAISON", "")).strip() == maison_num
                and row.get("SIGNE", "").strip().lower() == signe.lower()
            ):
                
                cle = (maison, signe)
                if cle in vus:
                    continue

                resultats["maisons"].append({
                    "maison": maison,
                    "signe": signe,
                    "interpretation": row.get("INTERPRETATION", "").strip(),
                })
                vus.add(cle)

    # 2. Maîtres de maisons en signes
    rulers_map = theme.get("house_rulers_map") or {}
    planetes = theme.get("planetes", {})

    for maitre, maisons_associees in rulers_map.items():
        placement = planetes.get(maitre, {})
        signe_maitre = placement.get("signe")

        if not signe_maitre:
            continue

        for maison in maisons_associees:
            maison_num = str(maison)
            if maisons_cibles is not None and maison_num not in maisons_cibles:
                continue
            for row in rows:
                if (
                    row.get("DONNEE", "").strip().lower() == "maitre_maison"
                    and str(row.get("MAISON", "")).strip() == maison_num
                    and row.get("SIGNE", "").strip().lower() == signe_maitre.lower()
                ):
                    
                    cle = (maison_num, maitre, signe_maitre)
                    if cle in vus:
                        continue

                    resultats["maitres_maisons"].append({
                        "maison": maison,
                        "maitre": maitre,
                        "signe": signe_maitre,
                        "interpretation": row.get("INTERPRETATION", "").strip(),
                    })

                    vus.add(cle)

    return resultats

def recuperer_interpretations_maitre_ascendant(theme: dict) -> dict:
    """
    Récupère :
    - maître d’Ascendant en signe
    - maître d’Ascendant en maison
    """

    planetes = theme.get("planetes", {})
    maisons = theme.get("maisons", {})

    asc_data = maisons.get(1) or maisons.get("1") or {}
    signe_asc = asc_data.get("signe")

    maitre, second_maitre = get_maitres_ascendant(signe_asc)

    if not maitre:
        return {}

    placement = planetes.get(maitre, {}) or {}

    signe = placement.get("signe")
    maison = placement.get("maison")

    fichier = "LLM_bdd_astro_placements.csv"

    result = {
        "maitre": maitre,
        "signe": None,
        "maison": None,
    }

    if signe:
        ligne_signe = rechercher_ligne_bdd(
            astre="maitre_asc",
            donnee="Signe",
            valeur=signe,
            fichier=fichier,
        )

        if ligne_signe:
            result["signe"] = ligne_signe

    if maison:
        ligne_maison = rechercher_ligne_bdd(
            astre="MaitreAsc",
            donnee="Maison",
            valeur=str(maison),
            fichier=fichier,
        )

        if ligne_maison:
            result["maison"] = ligne_maison

    return result

def formater_domaines_signes_bdd(base_interpretations: dict) -> str:
    data = base_interpretations.get("domaines_signes", {})
    lignes = []

    for item in data.get("maisons", []):
        lignes.append(
            f"Maison {item['maison']} en {item['signe']} : {item['interpretation']}"
        )

    for item in data.get("maitres_maisons", []):
        lignes.append(
            f"Maître de maison {item['maison']} ({item['maitre']}) en {item['signe']} : {item['interpretation']}"
        )

    return "\n".join(f"- {ligne}" for ligne in lignes)

def normaliser_cle_bdd(valeur: str) -> str:
    """
    Normalise les clés de recherche BDD :
    - minuscules ;
    - suppression des accents ;
    - espaces extérieurs supprimés ;
    - harmonisation de quelques variantes.
    """
    v = str(valeur or "").strip().lower()

    v = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", v)
        if unicodedata.category(caractere) != "Mn"
    )

    remplacements = {
        "conjonction dissociee": "conjonction_dissociee",
        "conj_dissociee": "conjonction_dissociee",

        # Variantes utilisées pour le maître d’Ascendant
        "maitreasc": "maitre_asc",
        "maitre_asc": "maitre_asc",
        "maitre_ascendant": "maitre_asc",
    }

    return remplacements.get(v, v)

def rechercher_interpretation_aspect(
    planete1: str,
    aspect: str,
    planete2: str,
    fichier: str = "LLM_bdd_astro_aspects.csv",
    colonne: str = "INTERPRETATION",
    autoriser_fallback_generique: bool = True,
) -> str | None:
    """
    Recherche une interprétation d'aspect astrologique
    dans la base aspects.csv.

    Gère aussi l'ordre inversé :
    Mercure/Uranus = Uranus/Mercure

    Si la colonne demandée est vide, fallback sur INTERPRETATION.
    """

    rows = charger_csv(fichier)

    colonne = (colonne or "INTERPRETATION").strip().upper()

    planete1_norm = normaliser_cle_bdd(planete1)
    planete2_norm = normaliser_cle_bdd(planete2)
    aspect_norm = normaliser_cle_bdd(aspect)

    for row in rows:
        p1 = normaliser_cle_bdd(row.get("PLANETE_1", ""))
        p2 = normaliser_cle_bdd(row.get("PLANETE_2", ""))
        asp = normaliser_cle_bdd(row.get("ASPECT", ""))

        meme_sens = (
            p1 == planete1_norm
            and p2 == planete2_norm
        )

        sens_inverse = (
            p1 == planete2_norm
            and p2 == planete1_norm
        )

        if asp == aspect_norm and (meme_sens or sens_inverse):
            interpretation_contextuelle = row.get(colonne, "").strip()

            if interpretation_contextuelle:
                return interpretation_contextuelle

            colonne_fallback = (
                "FAMILLE"
                if colonne in {"MA_MERE", "MA_PERE"}
                else "INTERPRETATION"
            )

            interpretation_fallback = (
                row.get(colonne_fallback, "").strip()
            )

            if interpretation_fallback:
                return interpretation_fallback

    return None

def rechercher_ligne_bdd(
    astre: str,
    donnee: str,
    valeur: str,
    fichier: str,
) -> dict | None:
    """
    Recherche une ligne complète dans la BDD Point Astral.
    Retourne toutes les colonnes utiles, pas seulement INTERPRETATION.
    """

    rows = charger_csv(fichier)

    for row in rows:
        type_bdd = normaliser_cle_bdd(
            row.get("TYPE", row.get("ASTRE", ""))
        )

        donnee_bdd = normaliser_cle_bdd(
            row.get("DONNEE", "")
        )

        valeur_bdd = normaliser_cle_bdd(
            row.get("VALEUR", "")
        )

        astre_recherche = normaliser_cle_bdd(astre)
        donnee_recherche = normaliser_cle_bdd(donnee)
        valeur_recherche = normaliser_cle_bdd(str(valeur))

        if (
            type_bdd == astre_recherche
            and donnee_bdd == donnee_recherche
            and valeur_bdd == valeur_recherche
        ):
            resultat = {
                col: row.get(col, "").strip()
                for col in COLONNES_POINT_ASTRAL
                if row.get(col, "").strip()
            }

            return resultat if resultat else None

    return None