"""Calcul du thème figé pour la RS, issu du moteur validé dans WEBSITE_FDA_LAST.

Cette copie évite de changer les calculs des autres analyses lors du lancement.
"""

from geopy.geocoders import Nominatim
from datetime import datetime
import pytz
import os
import math
from pathlib import Path
import swisseph as swe
from timezonefinder import TimezoneFinder
from utils.formatage import formater_positions_planetes
from .points_forts_rs import extraire_points_forts
from utils.astro_utils import valider_donnees_avant_analyse, corriger_donnees_maisons
from utils.revolution_solaire.calculs_astrologiques_rs import (
    get_maison_planete,
    detecter_interceptions,
    detecter_aspects,
    get_nakshatra_name,
    degre_vers_signe,
    get_maitre_ascendant,
    get_maitres_ascendant,
    get_maitre_ascendant_vedique,
    maisons_vediques_fixes,
    maison_vedique_planete_simple,
)
# Initialiser TimezoneFinder une seule fois
tf = TimezoneFinder()

class ThemeInputError(ValueError):
    """Données à corriger avant de générer une interprétation."""


def get_timezone_for_coordinates_and_date(lat, lon, dt_naive):
    """Zone IANA géographique ; la base historique fournit ensuite l'offset."""
    try:
        tzid = tf.timezone_at(lat=lat, lng=lon)
    except Exception as exc:
        raise ThemeInputError("Impossible de déterminer le fuseau du lieu de naissance.") from exc
    if not tzid:
        raise ThemeInputError("Fuseau introuvable : précise le fuseau du lieu de naissance.")
    return tzid


def _local_to_utc(naive, tzid):
    try:
        tz_local = pytz.timezone(tzid)
        dt_local = tz_local.localize(naive, is_dst=None)
    except pytz.AmbiguousTimeError as exc:
        raise ThemeInputError("Cette heure existe deux fois lors du changement d'heure. Précise l'instant de naissance avant de générer le rapport.") from exc
    except pytz.NonExistentTimeError as exc:
        raise ThemeInputError("Cette heure locale n'existe pas lors du changement d'heure. Vérifie l'heure de naissance.") from exc
    except pytz.UnknownTimeZoneError as exc:
        raise ThemeInputError("Le fuseau de naissance est invalide.") from exc
    return dt_local, dt_local.astimezone(pytz.UTC)

# ────────────────────────────────────────────────
# FONCTION : calcul_theme(date_naissance, heure_naissance, lieu_naissance, ...)
# Objectif :
#   Calculer l’intégralité des données astrologiques occidentales et védiques
#   à partir des informations de naissance fournies.
#
# Entrées (principales) :
#   - date_naissance (str ou date) : date de naissance
#   - heure_naissance (str ou time) : heure locale de naissance
#   - lieu_naissance (str) : nom de la ville ou coordonnées
#   - (optionnel) email, nom, autres infos utilisateur
#
# Étapes clés :
#   1. Géocodage du lieu → coordonnées (lat, lon).
#   2. Détermination du fuseau horaire correct (historique si nécessaire).
#   3. Conversion de la date/heure locale → UTC.
#   4. Calcul des positions planétaires tropicales (Swisseph).
#   5. Calcul des maisons astrologiques.
#   6. Calcul des aspects entre planètes.
#   7. Calcul des positions védiques (sidéral, nakshatras, etc.).
#   8. Identification des points forts (amas, dominances, dignités, tensions…).
#   9. Détection d’éléments complémentaires (Chiron, Lune Noire, interceptions).
#
# Sortie :
#   - dict complet contenant :
#       • planetes (occidentales)
#       • planetes_vediques
#       • aspects
#       • maisons
#       • points_forts
#       • données enrichies (nakshatra, maître d’ascendant, etc.)
#
# Utilisation :
#   Cette fonction est le cœur du calcul du thème natal, utilisée
#   dans les routes Flask pour alimenter les analyses (gratuite, Flash Astral, etc.).
# ────────────────────────────────────────────────


def calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance,
                 lat=None, lon=None, dt_naissance_utc=None, tzid=None):
    
    nom_utilisateur = nom
    
    print(f"🚀 Calcul_Theme_DÉBUT CALCUL pour {nom}")
    print(f"   Calcul_Theme_Paramètres reçus: lat={lat}, lon={lon}, tzid={tzid}")
    print(f"DEBUT calcul_theme: nom = '{nom}'")
    

    has_lat, has_lon = lat not in (None, ""), lon not in (None, "")
    if has_lat != has_lon:
        raise ThemeInputError("Latitude et longitude doivent être renseignées ensemble.")
    if has_lat:
        try:
            lat, lon = float(str(lat).replace(",", ".")), float(str(lon).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise ThemeInputError("Les coordonnées de naissance sont invalides.") from exc
    else:
        ua = os.getenv("GEOCODER_UA", "lesfousdastro/1.0 contact:admin@example.com")
        try:
            location = Nominatim(user_agent=ua).geocode(lieu_naissance, timeout=10, language="fr")
        except Exception as exc:
            raise ThemeInputError("La recherche du lieu a échoué. Réessaie ou fournis ses coordonnées.") from exc
        if location is None:
            raise ThemeInputError("Lieu de naissance introuvable. Sélectionne un lieu ou fournis ses coordonnées.")
        lat, lon = float(location.latitude), float(location.longitude)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ThemeInputError("Les coordonnées de naissance sont hors limites.")

    # --- ÉTAPE 2: Parser la date de naissance ---
    try:
        naive = datetime.strptime(f"{date_naissance} {heure_naissance}", '%Y-%m-%d %H:%M')
    except ValueError:
        try:
            naive = datetime.strptime(date_naissance, '%d %B %Y %H:%M')
        except ValueError as e:
            raise ThemeInputError("Le format de la date ou de l'heure de naissance est invalide.") from e

    print(f"📅 Calcul_Theme_Date parsée: {naive}")

    # --- ÉTAPE 3: Obtenir le fuseau horaire correct ---
    if dt_naissance_utc is not None:
        if not isinstance(dt_naissance_utc, datetime) or dt_naissance_utc.tzinfo is None or dt_naissance_utc.utcoffset() is None:
            raise ThemeInputError("L'instant de naissance fourni doit comporter un fuseau horaire.")
        dt_utc = dt_naissance_utc.astimezone(pytz.UTC)
        try:
            dt_local = dt_utc.astimezone(pytz.timezone(tzid or "UTC"))
        except pytz.UnknownTimeZoneError as exc:
            raise ThemeInputError("Le fuseau de naissance est invalide.") from exc
    else:
        tzid = tzid or get_timezone_for_coordinates_and_date(lat, lon, naive)
        dt_local, dt_utc = _local_to_utc(naive, tzid)
    print(f"🔧 Calcul_Theme_TEMPS FINAL:")
    print(f"   Calcul_Theme_Heure locale: {dt_local.strftime('%Y-%m-%d %H:%M %Z%z') if hasattr(dt_local, 'strftime') else 'N/A'}")
    print(f"   Calcul_Theme_Heure UTC: {dt_utc.strftime('%Y-%m-%d %H:%M %Z%z')}")
    print("🧪 Calcul_Theme_Sanity check:", "aware/local=", dt_local.tzinfo is not None, "aware/utc=", dt_utc.tzinfo is not None)
    print("🧪 Calcul_Theme_Round-trip OK ?",
      abs((dt_local.astimezone(pytz.UTC) - dt_utc).total_seconds()) < 1)

    # --- ÉTAPE 4: Calculs astrologiques ---
    swe.set_ephe_path(str(Path(__file__).resolve().parents[2] / 'ephe'))
    jd = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3_600_000_000.0,
    )
    
    print(f"🌟 Calcul_Theme_Jour Julien calculé: {jd}")
    
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    
    print(f"🌙 Calcul_Theme_Ayanamsa (Lahiri): {ayanamsa:.4f}°")

    # Calcul des maisons avec Placidus
    try:
        cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    except swe.Error as exc:
        raise ThemeInputError("Les maisons Placidus ne peuvent pas être calculées pour ce lieu et cette date, notamment aux latitudes polaires. Aucun système de maisons alternatif n'a été appliqué.") from exc
    #cusps_sid = [(cusp - ayanamsa) % 360 for cusp in cusps]

    asc_deg = float(ascmc[0]) % 360.0
    signe_asc, deg_asc = degre_vers_signe(asc_deg)

    asc_deg_sid = (asc_deg - ayanamsa) % 360
    signe_asc_sid, deg_asc_sid = degre_vers_signe(asc_deg_sid)
    nakshatra_asc_sid = get_nakshatra_name(asc_deg_sid)

    print(f"🎯 Calcul_Theme_ASCENDANTS CALCULÉS:")
    print(f"   Calcul_Theme_Tropical: {asc_deg:.2f}° = {signe_asc} {deg_asc:.2f}°")
    print(f"   Calcul_Theme_Sidéral: {asc_deg_sid:.2f}° = {signe_asc_sid} {deg_asc_sid:.2f}° (Nakshatra: {nakshatra_asc_sid})")

    # [Le reste du code pour les maisons, planètes, etc. reste identique...]

    # --- AJOUT: angles (Asc, MC, Desc, FC) en degrés tropicaux ---
    mc_deg = float(ascmc[1])
    angles_deg = {
        "Ascendant": asc_deg,
        "MC": mc_deg,
        "Descendant": (asc_deg + 180.0) % 360.0,
        "FC": (mc_deg + 180.0) % 360.0,
    }
    
    
    maisons_tropicales = {}
    signes_detectes = []

    for i in range(12):
        deg = float(cusps[i]) % 360.0
        signe, deg_signe = degre_vers_signe(deg)
        maisons_tropicales[f'Maison {i+1}'] = {
            'degre': deg,
            'signe': signe,
            'degre_dans_signe': deg_signe
        }
        signes_detectes.append(signe)

    # Travailler sur les cuspides non arrondies et leurs intervalles circulaires.
    interceptions = detecter_interceptions(cusps)

    maisons_vediques = maisons_vediques_fixes(signe_asc_sid)

    planetes = ['Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne',
                'Uranus', 'Neptune', 'Pluton', 'Rahu', 'Junon']
    codes = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER,
             swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO, swe.MEAN_NODE, 19]

    positions_tropicales = {'Ascendant': asc_deg}
    positions_vediques = {'Ascendant': asc_deg_sid}

    resultats_tropical = {
        'Ascendant': {
            'degre': asc_deg,
            'signe': signe_asc,
            'degre_dans_signe': deg_asc,
        }
    }
    resultats_vediques = {
        'Ascendant': {
            'degre': asc_deg_sid,
            'signe': signe_asc_sid,
            'degre_dans_signe': deg_asc_sid,
            'nakshatra': nakshatra_asc_sid
        }
    }

    for nomp, code in zip(planetes, codes):
       
       # --- 1) Récupérer aussi la vitesse pour détecter le rétrograde
        pos, _ = swe.calc_ut(jd, code)            # pos = [longitude, latitude, distance, vitesse_longitude]
        deg_trop = float(pos[0]) % 360.0  # précision conservée pour signe/maison/aspects
        speed = pos[3]

        # Le mouvement vient de la vitesse éphéméride, y compris les lentes.
        is_retro = speed < 0
       
        signe_trop, deg_signe_trop = degre_vers_signe(deg_trop)
        maison_trop = get_maison_planete(deg_trop, cusps)

        deg_sid = (deg_trop - ayanamsa) % 360
        signe_ved, deg_signe_ved = degre_vers_signe(deg_sid)
        nakshatra = get_nakshatra_name(deg_sid)
        maison_ved = maison_vedique_planete_simple(signe_ved, signe_asc_sid)

        SECTEUR = 360.0 / 27.0
        offset = deg_sid % SECTEUR
        pada = int(offset // (SECTEUR / 4)) + 1
        if pada < 1: 
            pada = 1
        elif pada > 4:
            pada = 4
        deg_dans_nak = round(offset, 2)

        resultats_tropical[nomp] = {
            'degre': deg_trop,
            'longitude': deg_trop,
            'signe': signe_trop,
            'degre_dans_signe': deg_signe_trop,
            'maison': maison_trop,
            'retrograde': is_retro,
        }

        resultats_vediques[nomp] = {
            'degre': deg_sid,
            'signe': signe_ved,
            'degre_dans_signe': deg_signe_ved,
            'nakshatra': nakshatra,
            'nakshatra_pada': pada,
            'nakshatra_deg': deg_dans_nak,
            'maison': maison_ved
        }

        positions_tropicales[nomp] = deg_trop
        positions_vediques[nomp] = deg_sid


    # --- AJOUT : Part de Fortune (tropicale) ---
    def _is_day_chart(sun_deg: float, cusps) -> bool:
        """Jour si le Soleil est au-dessus de l'horizon (souvent maisons 7→12)."""
        sun_house = get_maison_planete(sun_deg, cusps)
        return sun_house in [7, 8, 9, 10, 11, 12]

    sun_deg = float(resultats_tropical["Soleil"]["degre"])
    moon_deg = float(resultats_tropical["Lune"]["degre"])
    asc_deg_f = float(asc_deg)

    is_day = _is_day_chart(sun_deg, cusps)

    # Formule classique
    # Jour : ASC + Lune - Soleil
    # Nuit : ASC + Soleil - Lune
    pof_deg = (asc_deg_f + (moon_deg - sun_deg)) % 360 if is_day else (asc_deg_f + (sun_deg - moon_deg)) % 360

    signe_pof, deg_pof = degre_vers_signe(pof_deg)
    maison_pof = get_maison_planete(pof_deg, cusps)

    resultats_tropical["Part de Fortune"] = {
        "degre": pof_deg,
        "signe": signe_pof,
        "degre_dans_signe": deg_pof,
        "maison": maison_pof,
        "diurne": is_day
    }

    # --- AJOUT : Point d’Illumination (opposé à la Part de Fortune) ---
    illum_deg = (pof_deg + 180.0) % 360.0
    signe_illum, deg_illum = degre_vers_signe(illum_deg)
    maison_illum = get_maison_planete(illum_deg, cusps)

    resultats_tropical["Point d’Illumination"] = {
        "degre": illum_deg,
        "signe": signe_illum,
        "degre_dans_signe": deg_illum,
        "maison": maison_illum
    }

    positions_tropicales["Point d’Illumination"] = illum_deg

    
    # Ajout de Ketu
    rahu_deg_trop = resultats_tropical['Rahu']['degre']
    ketu_deg_trop = (rahu_deg_trop + 180) % 360
    signe_ketu_trop, deg_ketu_trop = degre_vers_signe(ketu_deg_trop)
    maison_ketu_trop = get_maison_planete(ketu_deg_trop, cusps)
    resultats_tropical['Ketu'] = {
        'degre': ketu_deg_trop,
        'signe': signe_ketu_trop,
        'degre_dans_signe': deg_ketu_trop,
        'maison': maison_ketu_trop
    }
    positions_tropicales['Ketu'] = ketu_deg_trop

    rahu_deg_ved = resultats_vediques['Rahu']['degre']
    ketu_deg_ved = (rahu_deg_ved + 180) % 360
    signe_ketu_ved, deg_ketu_ved = degre_vers_signe(ketu_deg_ved)
    maison_ketu_ved = maison_vedique_planete_simple(signe_ketu_ved, signe_asc_sid)
    resultats_vediques['Ketu'] = {
        'degre': ketu_deg_ved,
        'signe': signe_ketu_ved,
        'degre_dans_signe': deg_ketu_ved,
        'nakshatra': get_nakshatra_name(ketu_deg_ved),
        'maison': maison_ketu_ved
    }
    positions_vediques['Ketu'] = ketu_deg_ved

    # Ajout de la Lune Noire moyenne
    deg_lilith = float(swe.calc_ut(jd, 12)[0][0]) % 360.0
    signe_lilith, deg_signe_lilith = degre_vers_signe(deg_lilith)
    maison_lilith = get_maison_planete(deg_lilith, cusps)

    resultats_tropical['Lune Noire'] = {
        'degre': deg_lilith,
        'signe': signe_lilith,
        'degre_dans_signe': deg_signe_lilith,
        'maison': maison_lilith
    }
    positions_tropicales['Lune Noire'] = deg_lilith

    # Ajout de Chiron
    deg_chiron = float(swe.calc_ut(jd, 15)[0][0]) % 360.0
    signe_chiron, deg_signe_chiron = degre_vers_signe(deg_chiron)
    maison_chiron = get_maison_planete(deg_chiron, cusps)

    resultats_tropical['Chiron'] = {
        'degre': deg_chiron,
        'signe': signe_chiron,
        'degre_dans_signe': deg_signe_chiron,
        'maison': maison_chiron
    }
    positions_tropicales['Chiron'] = deg_chiron

    # --- AJOUT : Axe des Portes Uranus ↔ Saturne ---
    uranus_deg = float(resultats_tropical["Uranus"]["degre"])
    saturne_deg = float(resultats_tropical["Saturne"]["degre"])

    def _delta_circulaire(a, b):
        return (b - a) % 360.0

    delta_forward = _delta_circulaire(uranus_deg, saturne_deg)
    delta_backward = _delta_circulaire(saturne_deg, uranus_deg)

    # On prend l’arc le plus court entre Uranus et Saturne
    if delta_forward <= delta_backward:
        arc_court = delta_forward
        porte_invisible_deg = (uranus_deg + arc_court / 2.0) % 360.0
    else:
        arc_court = delta_backward
        porte_invisible_deg = (saturne_deg + arc_court / 2.0) % 360.0

    # La porte visible est à l’opposé exact
    porte_visible_deg = (porte_invisible_deg + 180.0) % 360.0

    porte_invisible_maison = get_maison_planete(porte_invisible_deg, cusps)
    porte_visible_maison = get_maison_planete(porte_visible_deg, cusps)

    porte_invisible_signe, porte_invisible_deg_signe = degre_vers_signe(porte_invisible_deg)
    porte_visible_signe, porte_visible_deg_signe = degre_vers_signe(porte_visible_deg)

    axe_portes = {
        "depart": "Uranus",
        "arrivee": "Saturne",
        "uranus_deg": uranus_deg,
        "saturne_deg": saturne_deg,
        "arc_uranus_saturne_court": arc_court,

        "porte_invisible_deg": porte_invisible_deg,
        "porte_invisible_signe": porte_invisible_signe,
        "porte_invisible_deg_signe": porte_invisible_deg_signe,
        "porte_invisible_maison": porte_invisible_maison,

        "porte_visible_deg": porte_visible_deg,
        "porte_visible_signe": porte_visible_signe,
        "porte_visible_deg_signe": porte_visible_deg_signe,
        "porte_visible_maison": porte_visible_maison,
    }

    print("DEBUG AXE DES PORTES :", axe_portes)

    positions_tropicales_avec_angles = dict(positions_tropicales)
    positions_tropicales_avec_angles.update({
        "MC": mc_deg,
        "Descendant": (asc_deg + 180.0) % 360.0,
        "FC": (mc_deg + 180.0) % 360.0,
    })

    aspects_avec_angles = detecter_aspects(positions_tropicales_avec_angles)

    aspects = detecter_aspects(positions_tropicales)
    

    nom_maitre_trop, nom_second_maitre = get_maitres_ascendant(signe_asc)

    maitre_ascendant = None
    if nom_maitre_trop and nom_maitre_trop in resultats_tropical:
        infos = resultats_tropical[nom_maitre_trop]
        deg = infos["degre"]
        maison = get_maison_planete(deg, cusps)

        maitre_ascendant = {
            "nom": nom_maitre_trop,
            "second_nom": nom_second_maitre,
            "degre": deg,
            "signe": infos["signe"],
            "degre_dans_signe": infos["degre_dans_signe"],
            "maison": maison,
        }

    nom_maitre_ved = get_maitre_ascendant_vedique(signe_asc_sid)
    maitre_asc_vedique = None
    if nom_maitre_ved and nom_maitre_ved in resultats_vediques:
        infos = resultats_vediques[nom_maitre_ved]
        deg = infos['degre']
        nakshatra = infos['nakshatra']
        maison = infos.get('maison')
        maitre_asc_vedique = {
            'nom': nom_maitre_ved,
            'degre': deg,
            'signe': infos['signe'],
            'degre_dans_signe': infos['degre_dans_signe'],
            'nakshatra': nakshatra,
            'maison': maison
        }


    points_forts = extraire_points_forts({
        'planetes': resultats_tropical,
        'aspects': aspects,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'planetes_vediques': resultats_vediques
    })

    ascendant = resultats_tropical.get("Ascendant", {"signe": "inconnu", "degre": "inconnu"})

    # --- AJOUT: dictionnaire des longitudes planètes/points en degrés tropicaux ---
    planetes_deg = {}
    for nom_planete, infos in resultats_tropical.items():
        # on exclut l'angle "Ascendant" du set planétaire
        if nom_planete == "Ascendant":
            continue
        deg = infos.get("degre")
        if deg is not None:
            try:
                planetes_deg[nom_planete] = float(deg)  # ← ICI la correction
            except Exception:
                pass

    def _delta_deg(a: float, b: float) -> float:
        d = abs((a - b) % 360.0)
        return d if d <= 180.0 else 360.0 - d

    try:
        angles_dbg = []
        for pl, deg in (planetes_deg or {}).items():
            for angle, dang in (angles_deg or {}).items():
                ecart = round(_delta_deg(deg, dang), 2)
                if ecart <= 1.0:
                    angles_dbg.append(f"→ {pl} ~ {angle} (écart {ecart}°)")
        if angles_dbg:
            print("🧭 Conjonctions aux angles détectées (≤1°):")
            for l in sorted(angles_dbg):
                print("   ", l)
    except Exception as e:
        print("⚠️ SanityCheck angles:", e)

    # --- AJOUT : maisons dirigées par chaque planète (pour interceptions / karma / lectures avancées) --- 20/03/26
    SIGN_RULERS = {
        "Bélier": ["Mars"],
        "Taureau": ["Vénus"],
        "Gémeaux": ["Mercure"],
        "Cancer": ["Lune"],
        "Lion": ["Soleil"],
        "Vierge": ["Mercure"],
        "Balance": ["Vénus"],
        "Scorpion": ["Mars", "Pluton"],
        "Sagittaire": ["Jupiter"],
        "Capricorne": ["Saturne"],
        "Verseau": ["Saturne", "Uranus"],
        "Poissons": ["Jupiter", "Neptune"],
    }

    house_rulers_map = {}

    for maison_label, infos_maison in (maisons_tropicales or {}).items():
        signe_cuspide = infos_maison.get("signe")
        if not signe_cuspide:
            continue

        rulers = SIGN_RULERS.get(signe_cuspide, [])
        if not rulers:
            continue

        # extraire le numéro de maison depuis "Maison 1"
        try:
            maison_num = int(str(maison_label).replace("Maison", "").strip())
        except Exception:
            continue

        for ruler in rulers:
            house_rulers_map.setdefault(ruler, []).append(maison_num)

    # petit tri propre
    for ruler in house_rulers_map:
        house_rulers_map[ruler] = sorted(set(house_rulers_map[ruler]))

    print("🏠 Calcul_Theme_house_rulers_map :", house_rulers_map)

    print(f"FIN calcul_theme: nom = '{nom}'")

    return {
        'nom': nom_utilisateur,
        'date': dt_local.strftime('%d %B %Y %H:%M') if hasattr(dt_local, 'strftime') else f"{date_naissance} {heure_naissance}",
        'planetes': resultats_tropical,
        'maisons': maisons_tropicales,
        'maisons_vediques': maisons_vediques,
        'aspects': aspects,
        'aspects_avec_angles': aspects_avec_angles,
        'maitre_ascendant': maitre_ascendant,
        'ascendant': ascendant,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'maitre_ascendant_vedique': maitre_asc_vedique,
        'planetes_vediques': resultats_vediques,
        'interceptions': interceptions,
        'points_forts': points_forts,
        'angles_deg': angles_deg,         
        'planetes_deg': planetes_deg,
        'axe_des_portes': axe_portes,
        'part_de_fortune': resultats_tropical.get("Part de Fortune"),
        'point_illumination': resultats_tropical.get("Point d’Illumination"),
        'house_rulers_map': house_rulers_map,    
    }
