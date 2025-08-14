from geopy.geocoders import Nominatim
from datetime import datetime
import pytz
import os
import swisseph as swe
from timezonefinder import TimezoneFinder
from utils.formatage import formater_positions_planetes, formater_aspects
from utils.utils_points_forts import extraire_points_forts
from utils.astro_utils import valider_donnees_avant_analyse, corriger_donnees_maisons
from utils.calculs_astrologiques import get_maison_planete, detecter_aspects, get_nakshatra_name, degre_vers_signe, get_maitre_ascendant, maisons_vediques_fixes, maison_vedique_planete_simple

# Initialiser TimezoneFinder une seule fois
tf = TimezoneFinder()

swe.set_ephe_path("/app/ephe")

# ────────────────────────────────────────────────
# FONCTION : get_timezone_for_coordinates_and_date(lat, lon, dt_naive)
# Objectif :
#   Retourner l’identifiant de fuseau horaire IANA le plus pertinent pour
#   des coordonnées géographiques et une date donnée, en gérant quelques
#   exceptions historiques (ex : Maroc avant 2008 → UTC).
#
# Entrées :
#   - lat (float) : latitude en degrés décimaux
#   - lon (float) : longitude en degrés décimaux
#   - dt_naive (datetime) : date/heure SANS tzinfo (naive) de l’événement
#
# Sortie :
#   - str : identifiant de fuseau (ex. "Europe/Paris") ou "UTC" en fallback
#
# Détails d’implémentation :
#   - Utilise timezonefinder (tf.timezone_at) pour déterminer le tzid moderne.
#   - Cas spécial : si tzid == "Africa/Casablanca" et année < 2008, renvoie "UTC"
#     (avant 2008 : pas d’heure d’été, UTC+0 stable).
#   - En cas d’erreur ou d’indétermination, renvoie "UTC" par défaut.
#
# Pré-requis :
#   - Avoir un objet `tf = TimezoneFinder()` initialisé au niveau module.
# ────────────────────────────────────────────────

def get_timezone_for_coordinates_and_date(lat, lon, dt_naive):
    """
    Obtient le fuseau horaire historiquement correct pour des coordonnées et une date donnée.
    Gère les cas spéciaux comme le Maroc avant 2008.
    """
    try:
        # Obtenir le fuseau moderne
        tzid = tf.timezone_at(lat=lat, lng=lon)
        
        if not tzid:
            return 'UTC'
            
        # Cas spéciaux historiques
        year = dt_naive.year
        
        # Maroc : avant 2008, pas d'heure d'été, toujours UTC+0
        if tzid == 'Africa/Casablanca' and year < 2008:
            print(f"📅 Maroc avant 2008 détecté -> UTC+0 fixe")
            return 'UTC'
        
        # Autres cas spéciaux peuvent être ajoutés ici...
        
        return tzid
        
    except Exception as e:
        print(f"❌ Erreur détection fuseau: {e}")
        return 'UTC'
    
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
#   dans les routes Flask pour alimenter les analyses (gratuite, Point Astral, etc.).
# ────────────────────────────────────────────────


def calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance,
                 lat=None, lon=None, dt_naissance_utc=None, tzid=None):
    
    print(f"🚀 DÉBUT CALCUL pour {nom}")
    print(f"   Paramètres reçus: lat={lat}, lon={lon}, tzid={tzid}")
    
    # --- ÉTAPE 1: Obtenir les coordonnées ---
    if lat is None or lon is None:
        print(f"🌍 Géocodage de '{lieu_naissance}'...")
        geolocator = Nominatim(user_agent="astro-app")
        try:
            location = geolocator.geocode(lieu_naissance, timeout=10)
            if location:
                lat, lon = location.latitude, location.longitude
                print(f"✅ Géocodage réussi: {lat:.6f}, {lon:.6f}")
            else:
                print(f"⚠️ Géocodage échoué, utilisation de Paris par défaut")
                lat, lon = 48.8566, 2.3522
        except Exception as e:
            print(f"❌ Erreur géocodage: {e}")
            lat, lon = 48.8566, 2.3522

    # --- ÉTAPE 2: Parser la date de naissance ---
    try:
        naive = datetime.strptime(f"{date_naissance} {heure_naissance}", '%Y-%m-%d %H:%M')
    except ValueError:
        try:
            naive = datetime.strptime(date_naissance, '%d %B %Y %H:%M')
        except ValueError as e:
            print(f"❌ Format de date non reconnu: {e}")
            raise

    print(f"📅 Date parsée: {naive}")

    # --- ÉTAPE 3: Obtenir le fuseau horaire correct ---
    if dt_naissance_utc is not None:
        # Cas 1: UTC déjà fourni (priorité absolue)
        dt_utc = dt_naissance_utc
        print(f"✅ UTC pré-calculé utilisé: {dt_utc}")
    else:
        # Cas 2: Déterminer le fuseau et convertir
        if tzid is None:
            tzid = get_timezone_for_coordinates_and_date(lat, lon, naive)
            print(f"🕐 Fuseau détecté: {tzid}")
        
        # Conversion avec le bon fuseau
        if tzid == 'UTC':
            dt_local = naive.replace(tzinfo=pytz.UTC)
            dt_utc = dt_local
        else:
            try:
                tz_local = pytz.timezone(tzid)
                dt_local = tz_local.localize(naive, is_dst=None)
                dt_utc = dt_local.astimezone(pytz.UTC)
            except pytz.AmbiguousTimeError:
                # Pendant le changement d'heure, prendre l'heure standard
                tz_local = pytz.timezone(tzid)
                dt_local = tz_local.localize(naive, is_dst=False)
                dt_utc = dt_local.astimezone(pytz.UTC)
            except pytz.NonExistentTimeError:
                # Heure inexistante (saut DST), prendre l'heure suivante
                tz_local = pytz.timezone(tzid)
                dt_local = tz_local.localize(naive, is_dst=True)
                dt_utc = dt_local.astimezone(pytz.UTC)
            except Exception as e:
                print(f"❌ Erreur conversion fuseau '{tzid}': {e}")
                # Fallback: traiter comme UTC
                dt_local = naive.replace(tzinfo=pytz.UTC)
                dt_utc = dt_local

    print(f"🔧 TEMPS FINAL:")
    print(f"   Heure locale: {dt_local.strftime('%Y-%m-%d %H:%M %Z%z') if hasattr(dt_local, 'strftime') else 'N/A'}")
    print(f"   Heure UTC: {dt_utc.strftime('%Y-%m-%d %H:%M %Z%z')}")

    # --- ÉTAPE 4: Calculs astrologiques ---
    swe.set_ephe_path(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ephe'))
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60.0)
    
    print(f"🌟 Jour Julien calculé: {jd}")
    
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    
    print(f"🌙 Ayanamsa (Lahiri): {ayanamsa:.4f}°")

    # Calcul des maisons avec Placidus
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    cusps_sid = [(cusp - ayanamsa) % 360 for cusp in cusps]

    asc_deg = round(ascmc[0], 2)
    signe_asc, deg_asc = degre_vers_signe(asc_deg)

    asc_deg_sid = (asc_deg - ayanamsa) % 360
    signe_asc_sid, deg_asc_sid = degre_vers_signe(asc_deg_sid)
    nakshatra_asc_sid = get_nakshatra_name(asc_deg_sid)

    print(f"🎯 ASCENDANTS CALCULÉS:")
    print(f"   Tropical: {asc_deg:.2f}° = {signe_asc} {deg_asc:.2f}°")
    print(f"   Sidéral: {asc_deg_sid:.2f}° = {signe_asc_sid} {deg_asc_sid:.2f}° (Nakshatra: {nakshatra_asc_sid})")

    # [Le reste du code pour les maisons, planètes, etc. reste identique...]
    
    maisons_tropicales = {}
    signes_detectes = []

    for i in range(12):
        deg = round(cusps[i], 2)
        signe, deg_signe = degre_vers_signe(deg)
        maisons_tropicales[f'Maison {i+1}'] = {
            'degre': deg,
            'signe': signe,
            'degre_dans_signe': deg_signe
        }
        signes_detectes.append(signe)

    # Détection des signes interceptés
    tous_les_signes = [
        "Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge",
        "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons"
    ]

    signes_interceptes = [s for s in tous_les_signes if signes_detectes.count(s) == 0]
    axes_interceptes = []

    for i in range(0, len(signes_interceptes), 2):
        if i + 1 < len(signes_interceptes):
            axes_interceptes.append((signes_interceptes[i], signes_interceptes[i + 1]))

    maisons_interceptées = {}
    for i in range(12):
        cusp1 = cusps[i]
        cusp2 = cusps[(i + 1) % 12]
        if cusp2 < cusp1:
            cusp2 += 360

        for signe in signes_interceptes:
            debut_signe = tous_les_signes.index(signe) * 30
            fin_signe = debut_signe + 30
            if (debut_signe > cusp1 and fin_signe < cusp2):
                maison_label = f"Maison {i+1}"
                maisons_interceptées[signe] = maison_label

    interceptions = {
        "signes_interceptes": signes_interceptes,
        "axes_interceptes": axes_interceptes,
        "maisons_interceptées": maisons_interceptées
    }

    maisons_vediques = maisons_vediques_fixes(signe_asc_sid)

    planetes = ['Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne',
                'Uranus', 'Neptune', 'Pluton', 'Rahu']
    codes = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER,
             swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO, swe.MEAN_NODE]

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
            'degre': round(asc_deg_sid, 2),
            'signe': signe_asc_sid,
            'degre_dans_signe': deg_asc_sid,
            'nakshatra': nakshatra_asc_sid
        }
    }

    for nomp, code in zip(planetes, codes):
        deg_trop = round(swe.calc_ut(jd, code)[0][0], 2)
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
            'signe': signe_trop,
            'degre_dans_signe': deg_signe_trop,
            'maison': maison_trop
        }

        resultats_vediques[nomp] = {
            'degre': round(deg_sid, 2),
            'signe': signe_ved,
            'degre_dans_signe': deg_signe_ved,
            'nakshatra': nakshatra,
            'nakshatra_pada': pada,
            'nakshatra_deg': deg_dans_nak,
            'maison': maison_ved
        }

        positions_tropicales[nomp] = deg_trop
        positions_vediques[nomp] = round(deg_sid, 2)

    # [Reste du code identique...]
    
    # Ajout de Ketu
    rahu_deg_trop = resultats_tropical['Rahu']['degre']
    ketu_deg_trop = (rahu_deg_trop + 180) % 360
    signe_ketu_trop, deg_ketu_trop = degre_vers_signe(ketu_deg_trop)
    maison_ketu_trop = get_maison_planete(ketu_deg_trop, cusps)
    resultats_tropical['Ketu'] = {
        'degre': round(ketu_deg_trop, 2),
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
        'degre': round(ketu_deg_ved, 2),
        'signe': signe_ketu_ved,
        'degre_dans_signe': deg_ketu_ved,
        'nakshatra': get_nakshatra_name(ketu_deg_ved),
        'maison': maison_ketu_ved
    }
    positions_vediques['Ketu'] = round(ketu_deg_ved, 2)

    aspects = detecter_aspects(positions_tropicales)

    nom_maitre_trop = get_maitre_ascendant(signe_asc)
    maitre_ascendant = None
    if nom_maitre_trop and nom_maitre_trop in resultats_tropical:
        infos = resultats_tropical[nom_maitre_trop]
        deg = infos['degre']
        maison = get_maison_planete(deg, cusps)
        maitre_ascendant = {
            'nom': nom_maitre_trop,
            'degre': deg,
            'signe': infos['signe'],
            'degre_dans_signe': infos['degre_dans_signe'],
            'maison': maison
        }

    nom_maitre_ved = get_maitre_ascendant(signe_asc_sid)
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

    # Ajout de la Lune Noire moyenne
    deg_lilith = round(swe.calc_ut(jd, 12)[0][0], 2)
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
    deg_chiron = round(swe.calc_ut(jd, 15)[0][0], 2)
    signe_chiron, deg_signe_chiron = degre_vers_signe(deg_chiron)
    maison_chiron = get_maison_planete(deg_chiron, cusps)

    resultats_tropical['Chiron'] = {
        'degre': deg_chiron,
        'signe': signe_chiron,
        'degre_dans_signe': deg_signe_chiron,
        'maison': maison_chiron
    }
    positions_tropicales['Chiron'] = deg_chiron

    points_forts = extraire_points_forts({
        'planetes': resultats_tropical,
        'aspects': aspects,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'planetes_vediques': resultats_vediques
    })

    ascendant = resultats_tropical.get("Ascendant", {"signe": "inconnu", "degre": "inconnu"})

    return {
        'nom': nom,
        'date': dt_local.strftime('%d %B %Y %H:%M') if hasattr(dt_local, 'strftime') else f"{date_naissance} {heure_naissance}",
        'planetes': resultats_tropical,
        'maisons': maisons_tropicales,
        'maisons_vediques': maisons_vediques,
        'aspects': aspects,
        'maitre_ascendant': maitre_ascendant,
        'ascendant': ascendant,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'maitre_ascendant_vedique': maitre_asc_vedique,
        'planetes_vediques': resultats_vediques,
        'interceptions': interceptions,
        'points_forts': points_forts
    }