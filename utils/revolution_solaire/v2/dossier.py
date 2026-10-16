"""Calculs locaux uniquement : aucune interprétation ni import du client IA."""

from copy import deepcopy
from collections import Counter
from datetime import datetime, timedelta, timezone
import math

from ..calculs_astrologiques_rs import (
    degre_vers_signe, detecter_aspects, get_maison_planete, get_maitres_ascendant,
    ORBES_DEFAUT,
)
from ..donnees_techniques import POINTS_RS, ANGLES, extraire_donnees_revolution_solaire
from utils.configurations_astrologiques import analyser_configurations_majeures

VERSION = "rs_v2_sequentielle_10"
PLANETES = POINTS_RS[:10]
CIBLES_TRANSITS_EXCLUES = frozenset({"Chiron", "Lune Noire", "Part de Fortune"})
NOEUDS_LUNAIRES = frozenset({"Rahu", "Ketu"})
PLANETES_TRANSITS_NOEUDS = frozenset({"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"})
ASPECTS_TRANSITS_NOEUDS = frozenset({"conjonction", "opposition", "carré"})
ORBE_TRANSITS_NOEUDS = 2.0
ASPECT_COMPLEMENTAIRE_NOEUD = {
    "conjonction": "opposition", "opposition": "conjonction", "carré": "carré",
}
ASPECTS_MARS_ANNUELS = frozenset({"conjonction", "opposition", "carré"})
FIGURES_MAJEURES_RS_MARS = frozenset({"stellium", "t_carre", "grand_trigone", "grand_carre", "diamant"})
AXES_ANGLES = {
    "Ascendant": ("Ascendant", "Descendant"), "Descendant": ("Ascendant", "Descendant"),
    "MC": ("MC", "FC"), "FC": ("MC", "FC"),
}
ASPECT_COMPLEMENTAIRE_ANGLE = {
    "conjonction": "opposition", "opposition": "conjonction", "carré": "carré",
    "sextile": "trigone", "trigone": "sextile",
}
MODES = {
    "Bélier": "cardinal", "Cancer": "cardinal", "Balance": "cardinal", "Capricorne": "cardinal",
    "Taureau": "fixe", "Lion": "fixe", "Scorpion": "fixe", "Verseau": "fixe",
    "Gémeaux": "mutable", "Vierge": "mutable", "Sagittaire": "mutable", "Poissons": "mutable",
}
ELEMENTS = {
    "Bélier": "feu", "Lion": "feu", "Sagittaire": "feu",
    "Taureau": "terre", "Vierge": "terre", "Capricorne": "terre",
    "Gémeaux": "air", "Balance": "air", "Verseau": "air",
    "Cancer": "eau", "Scorpion": "eau", "Poissons": "eau",
}


def _longitude(value):
    longitude = float(value)
    if not math.isfinite(longitude) or not 0 <= longitude < 360:
        raise ValueError("Longitude invalide : valeur finie entre 0 et 360° attendue.")
    return longitude


def _fiche(longitude):
    signe, degre = degre_vers_signe(longitude)
    return {"degre": longitude, "signe": signe, "degre_dans_signe": degre,
            "mode": MODES[signe], "element": ELEMENTS[signe]}


def inventorier_theme(theme, *, instant_utc=None):
    """Inventorie les 15 points validés, 4 angles et 12 cuspides sans sélection."""
    cuspides = {
        str(numero): _fiche(_longitude(theme["maisons"][f"Maison {numero}"]["degre"]))
        for numero in range(1, 13)
    }
    bornes = [cuspides[str(n)]["degre"] for n in range(1, 13)]
    # Les cuspides doivent parcourir le zodiaque exactement une fois.
    arcs = [(bornes[(i + 1) % 12] - bornes[i]) % 360 for i in range(12)]
    if any(arc <= 0 for arc in arcs) or not math.isclose(sum(arcs), 360, abs_tol=1e-6):
        raise ValueError("Les douze cuspides ne forment pas un cycle de maisons valide.")
    positions = {}
    retrogradations = {}
    if instant_utc is not None:
        import swisseph as swe
        if instant_utc.tzinfo is None:
            raise ValueError("L'instant du thème doit avoir un fuseau horaire.")
        instant = instant_utc.astimezone(timezone.utc)
        heure = instant.hour + instant.minute / 60 + instant.second / 3600 + instant.microsecond / 3600000000
        jd = swe.julday(instant.year, instant.month, instant.day, heure)
        for nom, code in (("Chiron", swe.CHIRON), ("Lune Noire", swe.MEAN_APOG),
                          ("Rahu", swe.MEAN_NODE), ("Ketu", swe.MEAN_NODE)):
            retrogradations[nom] = swe.calc_ut(jd, code, swe.FLG_SPEED)[0][3] < 0
    for nom in POINTS_RS:
        point = theme.get("planetes", {}).get(nom)
        if not point or point.get("degre") is None:
            raise ValueError(f"Point obligatoire manquant : {nom}.")
        longitude = _longitude(point["degre"])
        positions[nom] = {
            **_fiche(longitude),
            "maison": get_maison_planete(longitude, bornes),
            # Un état non calculé ne devient pas arbitrairement « direct ».
            "retrograde": retrogradations.get(nom, point.get("retrograde")),
        }
        if "diurne" in point:
            positions[nom]["diurne"] = point["diurne"]
        if nom in PLANETES[:7]:
            from ..points_forts_rs import evaluer_dignite
            positions[nom]["dignite_essentielle"] = evaluer_dignite(nom, positions[nom]["signe"])["dignite"]
    angles = {nom: _fiche(_longitude(theme["angles_deg"][nom])) for nom in ANGLES}
    maitrises = {
        numero: {"signe": fiche["signe"],
                 "maitres": [nom for nom in get_maitres_ascendant(fiche["signe"]) if nom]}
        for numero, fiche in cuspides.items()
    }
    longitudes = {nom: p["degre"] for nom, p in {**positions, **angles}.items()}
    aspects = detecter_aspects(longitudes)
    figures = analyser_configurations_majeures(
        [a for a in aspects if a["planete1"] in PLANETES and a["planete2"] in PLANETES],
        {nom: positions[nom] for nom in PLANETES},
        inclure_triangles_mineurs=True,
    )
    angularites = []
    for nom, point in positions.items():
        for angle, fiche in angles.items():
            distance = abs((point["degre"] - fiche["degre"] + 180) % 360 - 180)
            if distance <= 8:
                angularites.append({"point": nom, "angle": angle, "orbe": round(distance, 6)})
    return {
        "positions": positions, "angles": angles, "cuspides": cuspides,
        "maitrises": maitrises, "interceptions": deepcopy(theme.get("interceptions") or {}),
        "aspects": aspects, "configurations": figures, "angularites": angularites,
        "repartition": {
            "planetes_par_mode": dict(Counter(positions[nom]["mode"] for nom in PLANETES)),
            "planetes_par_element": dict(Counter(positions[nom]["element"] for nom in PLANETES)),
            "cuspides_par_mode": dict(Counter(p["mode"] for p in cuspides.values())),
        },
    }


def comparer_maisons(natal, rs):
    """Projette points et cuspides dans les deux sens, sans confondre les cartes."""
    resultat = {}
    for source, cible, libelle in ((rs, natal, "rs_vers_natal"), (natal, rs, "natal_vers_rs")):
        bornes = [cible["cuspides"][str(n)]["degre"] for n in range(1, 13)]
        resultat[libelle] = {
            "points": {
                nom: {"degre": p["degre"], "maison_cible": get_maison_planete(p["degre"], bornes)}
                for nom, p in {**source["positions"], **source["angles"]}.items()
            },
            "cuspides": {
                numero: {"degre": p["degre"], "maison_cible": get_maison_planete(p["degre"], bornes)}
                for numero, p in source["cuspides"].items()
            },
        }
    return resultat


def cibles_mars_annuels(natal, rs, maitre_annee=None):
    """Cibles validées pour Mars, communes aux deux thèmes."""
    cibles = {"Soleil", "Lune", *ANGLES}
    if maitre_annee is not None:
        if maitre_annee not in PLANETES[:7]:
            raise ValueError("Maître traditionnel de l'année invalide.")
        cibles.add(maitre_annee)
    for theme in (natal, rs):
        cibles.update(theme["maitrises"]["1"]["maitres"])
    for figure in rs["configurations"]:
        if figure["type"] in FIGURES_MAJEURES_RS_MARS:
            cibles.update(figure["planetes"])
    return cibles


def _bornes_transit(evenement):
    datation = evenement.get("datation") or {}
    if datation:
        return (datetime.fromisoformat(datation["entree_utc"]),
                datetime.fromisoformat(datation["sortie_utc"]))
    # Sans affinage, les dates sont des jours observés, pas des heures exactes.
    return (datetime.fromisoformat(evenement["debut"]).replace(tzinfo=timezone.utc),
            datetime.fromisoformat(evenement["fin"]).replace(tzinfo=timezone.utc) + timedelta(days=1))


def regrouper_transits_axes(evenements):
    """Regroupe les fenêtres chevauchantes d'un même axe, sans perdre leurs bornes.

    Les sextiles/trigones ont des orbes différents : leurs fenêtres restent
    enregistrées séparément au sein de l'activation regroupée. Ni thème,
    planète mobile, famille d'aspects ni périodes disjointes ne sont fusionnés.
    """
    from ..transits_annuels import ASPECTS_TRANSITS_RS
    groupes, resultat = {}, []
    for evenement in evenements:
        cible, aspect = evenement["cible"], evenement["aspect"]
        if cible not in AXES_ANGLES or aspect not in ASPECT_COMPLEMENTAIRE_ANGLE:
            resultat.append(evenement)
            continue
        axe = AXES_ANGLES[cible]
        canonique = aspect if cible == axe[0] else ASPECT_COMPLEMENTAIRE_ANGLE[aspect]
        cle = (evenement["planete_transit"], evenement["reference"], axe, canonique)
        groupes.setdefault(cle, []).append(evenement)

    def ajouter(contacts, axe):
        if len({e["cible"] for e in contacts}) < 2:
            resultat.extend(contacts)
            return
        principal = next((e for e in contacts if e["cible"] == axe[0]), contacts[0])
        activation = deepcopy(principal)
        activation["axe_angles"] = {e["cible"]: e["aspect"] for e in contacts}
        activation["contacts_complementaires_axe"] = []
        for contact in contacts:
            if contact is principal:
                continue
            datation = contact.get("datation") or {}
            complement = {
                "cible": contact["cible"], "aspect": contact["aspect"],
                "orbe_maximum": ASPECTS_TRANSITS_RS[contact["aspect"]][1],
                "debut": datation.get("entree_utc", contact["debut"]),
                "fin": datation.get("sortie_utc", contact["fin"]),
                "plus_serre": datation.get("plus_serre_utc", contact["date_plus_serree"]),
                "orbe_minimum": datation.get("orbe_minimum", contact["orbe_plus_serre"]),
                "retrograde_au_plus_serre": contact["retrograde_au_plus_serre"],
            }
            if datation:
                complement.update({cle: deepcopy(datation[cle]) for cle in (
                    "passages_exacts", "stations", "phases", "entree_coupee_par_cycle", "sortie_coupee_par_cycle")})
            activation["contacts_complementaires_axe"].append(complement)
        # La datation du contact principal garde son sens ; les bornes de
        # l'activation globale viennent de l'union des fenêtres calculées.
        if all("datation" in e for e in contacts):
            activation["fenetre_axe"] = {
                "debut_utc": min(_bornes_transit(e)[0] for e in contacts).isoformat(timespec="minutes"),
                "fin_utc": max(_bornes_transit(e)[1] for e in contacts).isoformat(timespec="minutes"),
            }
        else:
            activation["fenetre_axe"] = {
                "debut": min(e["debut"] for e in contacts), "fin": max(e["fin"] for e in contacts),
                "precision": "jours observés, sans datation affinée",
            }
        resultat.append(activation)

    for (_, _, axe, _), contacts in groupes.items():
        contacts = sorted(contacts, key=lambda e: _bornes_transit(e)[0])
        courant, fin_courante = [], None
        for contact in contacts:
            debut_contact, fin_contact = _bornes_transit(contact)
            if courant and debut_contact >= fin_courante:
                ajouter(courant, axe)
                courant = []
            courant.append(contact)
            fin_courante = max(fin_courante, fin_contact) if len(courant) > 1 else fin_contact
        if courant:
            ajouter(courant, axe)
    return sorted(resultat, key=lambda e: (e["date_plus_serree"], e["reference"], e["cible"], e["planete_transit"], e["aspect"]))


def calculer_transits_dossier(natal, rs, debut, fin, *, raffiner=True, maitre_annee=None):
    """Balayage quotidien de toutes les cibles retenues, sans plafond de fenêtres.

    Les bornes exactes du cycle sont incluses. Le Soleil RS est un alias du
    Soleil natal. Chiron, la Lune Noire et la Part de Fortune ne sont pas des cibles de transit.
    La conjonction d'une planète mobile à elle-même en RS est exclue comme
    contact mécanique. L'axe des Nœuds est calculé une fois via Rahu, avec les
    deux contacts conservés : planètes lentes, conjonction/opposition/carré,
    orbe de 2° en détection et en datation affinée. Les fenêtres peuvent ensuite être
    affinées avec le calculateur existant (pas de 6 h, précision de 1 minute).
    """
    from ..transits_annuels import ASPECTS_TRANSITS_RS, PLANETES_TRANSIT_ANNUELS
    from utils.transits.calcul_transits import calculer_positions_transits
    from ..datation_detaillee import dater_fenetre

    if debut.tzinfo is None or fin.tzinfo is None or fin <= debut:
        raise ValueError("Un cycle croissant avec fuseaux horaires est obligatoire.")
    debut, fin = debut.astimezone(timezone.utc), fin.astimezone(timezone.utc)
    cibles = {
        reference: {nom: p["degre"] for nom, p in {**theme["positions"], **theme["angles"]}.items()
                    if nom not in CIBLES_TRANSITS_EXCLUES and (reference != "rs" or nom != "Soleil")}
        for reference, theme in (("natal", natal), ("rs", rs))
    }
    cibles_mars = cibles_mars_annuels(natal, rs, maitre_annee)
    for reference, points in cibles.items():
        if not NOEUDS_LUNAIRES <= points.keys():
            raise ValueError("Axe des Nœuds incomplet : " + reference)
        distance = abs((points["Rahu"] - points["Ketu"] + 180) % 360 - 180)
        if not math.isclose(distance, 180, abs_tol=1e-6):
            raise ValueError("Les Nœuds ne forment pas un axe opposé : " + reference)
    ouvertes, fermees = {}, []
    dates = [debut]
    date = debut.replace(hour=12, minute=0, second=0, microsecond=0)
    if date <= debut:
        date += timedelta(days=1)
    while date < fin:
        dates.append(date)
        date += timedelta(days=1)
    dates.append(fin)
    for date in dates:
        positions = calculer_positions_transits(date.replace(tzinfo=None))["positions"]
        presentes = set()
        for planete in sorted(PLANETES_TRANSIT_ANNUELS):
            longitude = _longitude(positions[planete]["longitude"])
            for reference, points in cibles.items():
                for nom, cible in points.items():
                    if planete == "Mars" and nom not in cibles_mars:
                        continue
                    cible_nodale = nom in NOEUDS_LUNAIRES
                    # Ketu est l'autre extrémité de l'axe : son contact est
                    # conservé dans axe_noeuds, sans produire une seconde fenêtre.
                    if cible_nodale and (nom == "Ketu" or planete not in PLANETES_TRANSITS_NOEUDS):
                        continue
                    distance = abs((longitude - cible + 180) % 360 - 180)
                    for aspect, (angle, orbe_max) in ASPECTS_TRANSITS_RS.items():
                        if aspect == "quinconce" or (planete == "Mars" and aspect not in ASPECTS_MARS_ANNUELS):
                            continue
                        if cible_nodale and aspect not in ASPECTS_TRANSITS_NOEUDS:
                            continue
                        limite_orbe = ORBE_TRANSITS_NOEUDS if cible_nodale else orbe_max
                        orbe = abs(distance - angle)
                        if orbe > limite_orbe or (reference == "rs" and nom == planete and aspect == "conjonction"):
                            continue
                        cle = (planete, reference, nom, aspect)
                        presentes.add(cle)
                        if cle not in ouvertes:
                            ouvertes[cle] = {
                                "planete_transit": planete, "reference": reference, "cible": nom,
                                "aspect": aspect, "debut": date.date().isoformat(),
                                "fin": date.date().isoformat(), "date_plus_serree": date.date().isoformat(),
                                "orbe_plus_serre": orbe,
                                "retrograde_au_plus_serre": positions[planete]["retrograde"],
                            }
                            if cible_nodale:
                                ouvertes[cle]["axe_noeuds"] = {
                                    "Rahu": aspect,
                                    "Ketu": ASPECT_COMPLEMENTAIRE_NOEUD[aspect],
                                }
                                ouvertes[cle]["orbe_maximum"] = ORBE_TRANSITS_NOEUDS
                        fenetre = ouvertes[cle]
                        fenetre["fin"] = date.date().isoformat()
                        if orbe < fenetre["orbe_plus_serre"]:
                            fenetre.update(orbe_plus_serre=orbe, date_plus_serree=date.date().isoformat(),
                                           retrograde_au_plus_serre=positions[planete]["retrograde"])
                        break
        for cle in set(ouvertes) - presentes:
            fermees.append(ouvertes.pop(cle))
    fermees.extend(ouvertes.values())
    evenements = sorted(fermees, key=lambda e: (e["date_plus_serree"], e["reference"], e["cible"], e["planete_transit"], e["aspect"]))
    for evenement in evenements:
        evenement["orbe_plus_serre"] = round(evenement["orbe_plus_serre"], 6)
        if evenement["reference"] == "natal" and evenement["cible"] == "Soleil":
            evenement["alias_cible_rs"] = "Soleil"
        if raffiner:
            if "axe_noeuds" in evenement:
                evenement["datation"] = dater_fenetre(
                    evenement, cibles, debut, fin, orbe_maximum=ORBE_TRANSITS_NOEUDS)
            else:
                evenement["datation"] = dater_fenetre(evenement, cibles, debut, fin)
    evenements = regrouper_transits_axes(evenements)
    return {
        "planetes_mobiles": sorted(PLANETES_TRANSIT_ANNUELS),
        "orbes": {aspect: deepcopy(valeur) for aspect, valeur in ASPECTS_TRANSITS_RS.items() if aspect != "quinconce"},
        "cibles": cibles,
        "pas_detection": "quotidien avec bornes du cycle",
        "raffinement": "6 heures, précision numérique 1 minute" if raffiner else None,
        "filtre_noeuds": {"planetes": sorted(PLANETES_TRANSITS_NOEUDS),
                          "aspects": sorted(ASPECTS_TRANSITS_NOEUDS),
                          "orbe_maximum": ORBE_TRANSITS_NOEUDS,
                          "regroupement": "une fenêtre par activation de l'axe Rahu–Ketu"},
        "filtre_mars": {"cibles": sorted(cibles_mars), "aspects": sorted(ASPECTS_MARS_ANNUELS),
                        "maitre_annee": maitre_annee,
                        "figures_rs": sorted(FIGURES_MAJEURES_RS_MARS)},
        "regroupement_angles": "fenêtres chevauchantes du même axe, planète et thème ; contacts et dates conservés",
        "exclusions": ["Chiron, Lune Noire et Part de Fortune : cibles exclues au natal et en RS",
                       "Quinconces exclus du calendrier annuel",
                       "Soleil RS : alias du Soleil natal", "conjonction d'une planète en transit à elle-même en RS"],
        "evenements": evenements,
    }


def construire_catalogue(dossier):
    """Attribue un identifiant stable à chaque fait, exploitable par les contrôles."""
    faits = {}
    for reference in ("natal", "rs"):
        for categorie, collection in dossier[reference].items():
            if isinstance(collection, list):
                entrees = enumerate(collection, 1)
            elif categorie == "interceptions":
                entrees = [("ensemble", collection)]
            else:
                entrees = collection.items()
            for cle, valeur in entrees:
                identifiant = f"{reference.upper()}.{categorie}.{cle}"
                faits[identifiant] = {"source": reference, "type": categorie, "objet": str(cle), "valeur": valeur}
    for index, aspect in enumerate(dossier["comparaison"]["contacts"], 1):
        faits[f"CONTACT.{index}"] = {"source": "comparaison", "type": "contact", "valeur": aspect}
    for sens, projection in dossier["comparaison"]["maisons"].items():
        for categorie, collection in projection.items():
            for nom, valeur in collection.items():
                faits[f"SUPERPOSITION.{sens}.{categorie}.{nom}"] = {
                    "source": sens, "type": categorie, "objet": nom, "valeur": valeur}
    faits["PROFECTION.annuelle"] = {"source": "profection", "type": "profection", "valeur": dossier["profection"]}
    for index, evenement in enumerate(dossier["transits"]["evenements"], 1):
        faits[f"TRANSIT.{index}"] = {"source": "transits", "type": "transit", "valeur": evenement}
    return faits


def calculer_dossier_factuel_rs(*, personne, lieu_rs, annee, raffiner_transits=True):
    """Première fonction publique : calcule tout le dossier, sans contexte ni IA."""
    from ..theme_revolution_solaire import calculer_theme_revolution_solaire
    from ..calcul_retour_solaire import trouver_retour_solaire

    for donnees in (personne, lieu_rs):
        lat, lon = float(donnees["lat"]), float(donnees["lon"])
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Coordonnées géographiques invalides.")
    calcul = calculer_theme_revolution_solaire(personne["nom"], personne, lieu_rs, annee)
    natal = inventorier_theme(calcul["theme_natal"], instant_utc=calcul["naissance_utc"])
    rs = inventorier_theme(calcul["theme_revolution_solaire"], instant_utc=calcul["retour"]["retour_utc"])
    techniques = extraire_donnees_revolution_solaire(
        calcul["theme_natal"], calcul["theme_revolution_solaire"], age_profection=calcul["age_au_retour"])
    debut = calcul["retour"]["retour_utc"]
    fin = trouver_retour_solaire(calcul["naissance_locale"], annee + 1)["retour_utc"]
    dossier = {
        "version": VERSION,
        "cycle": {"debut_utc": debut.isoformat(), "fin_utc": fin.isoformat(),
                  "retour_local": calcul["retour_local"].isoformat(), "tzid_rs": lieu_rs["tzid"],
                  "annee": annee, "age": calcul["age_au_retour"]},
        "conventions": {"zodiaque": "tropical", "maisons": "Placidus",
                        "points_retenus": list(POINTS_RS), "lune_noire": "moyenne", "noeud_nord": "moyen",
                        "orbes_aspects_internes": dict(ORBES_DEFAUT),
                        "orbes_aspects_ascendant": "au moins 8° sauf quinconce (3°)",
                        "orbe_contacts": 6.0, "orbe_angularite": 8.0,
                        "soleil_rs_natal": "aspects exclus : retour à la longitude natale",
                        "superposition_cuspide": "position de la cuspide, pas inclusion de toute la maison"},
        "natal": natal, "rs": rs,
        "comparaison": {"contacts": techniques["aspects_rs_natal"], "maisons": comparer_maisons(natal, rs)},
        "profection": techniques["profection_annuelle"],
        "transits": calculer_transits_dossier(
            natal, rs, debut, fin, raffiner=raffiner_transits,
            maitre_annee=techniques["profection_annuelle"]["maitre_annee"]["nom"]),
        # Contrat du vérificateur historique ; jamais transmis à l'étape RS seule.
        "donnees_controle": techniques,
    }
    dossier["faits"] = construire_catalogue(dossier)
    controler_completude_dossier(dossier)
    return dossier


def controler_completude_dossier(dossier):
    """Refuse un dossier incomplet avant tout appel d'interprétation."""
    for reference in ("natal", "rs"):
        theme = dossier[reference]
        if set(theme["positions"]) != set(POINTS_RS) or set(theme["angles"]) != set(ANGLES):
            raise ValueError(f"Inventaire {reference} incomplet.")
        if set(theme["cuspides"]) != {str(n) for n in range(1, 13)}:
            raise ValueError(f"Cuspides {reference} incomplètes.")
        for point in theme["positions"].values():
            _longitude(point["degre"])
            if point["maison"] not in range(1, 13):
                raise ValueError(f"Maison de placement {reference} invalide.")
    for sens in ("rs_vers_natal", "natal_vers_rs"):
        projection = dossier["comparaison"]["maisons"][sens]
        if set(projection["points"]) != set(POINTS_RS) | set(ANGLES) or len(projection["cuspides"]) != 12:
            raise ValueError(f"Superpositions {sens} incomplètes.")
    if not dossier["profection"] or dossier["profection"]["maison_annuelle"] not in range(1, 13):
        raise ValueError("Profection annuelle manquante ou invalide.")
    debut, fin = (datetime.fromisoformat(dossier["cycle"][cle]) for cle in ("debut_utc", "fin_utc"))
    if debut.tzinfo is None or fin.tzinfo is None or not 364 < (fin - debut).total_seconds() / 86400 < 367:
        raise ValueError("Bornes du cycle annuel invalides.")
    if dossier["faits"] != construire_catalogue(dossier):
        raise ValueError("Le catalogue ne correspond pas aux faits du dossier.")
    return {"statut": "complet", "nombre_faits": len(dossier["faits"])}
