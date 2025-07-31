from geopy.geocoders import Nominatim
from datetime import datetime
import pytz
import swisseph as swe
from utils.utils_formatage import formater_positions_planetes, formater_aspects

from utils.utils_points_forts import extraire_points_forts
from utils.astro_utils import valider_donnees_avant_analyse, corriger_donnees_maisons
from utils.calculs_astrologiques import get_maison_planete, detecter_aspects, get_nakshatra_name, degre_vers_signe, get_maitre_ascendant, maisons_vediques_fixes, maison_vedique_planete_simple

def calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance):
    geolocator = Nominatim(user_agent="astro-app")
    try:
        location = geolocator.geocode(lieu_naissance, timeout=5)
        lat, lon = (location.latitude, location.longitude) if location else (48.8566, 2.3522)
    except:
        lat, lon = 48.8566, 2.3522

    tz = pytz.timezone('Europe/Paris')
    #dt = tz.localize(datetime.strptime(date_naissance + ' ' + heure_naissance, '%Y-%m-%d %H:%M'))
    # Gestion des deux formats possibles (brut ou déjà concaténé)
    try:
        dt = tz.localize(datetime.strptime(date_naissance + ' ' + heure_naissance, '%Y-%m-%d %H:%M'))
    except ValueError:
    # Format alternatif : date_naissance contient déjà l’heure
        dt = tz.localize(datetime.strptime(date_naissance, '%d %B %Y %H:%M'))

    dt_utc = dt.astimezone(pytz.utc)

    swe.set_ephe_path('/usr/share/ephe')
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60)
    ayanamsa = swe.get_ayanamsa_ut(jd)

    cusps, ascmc = swe.houses(jd, lat, lon, b'P')

    cusps_sid = [(cusp - ayanamsa) % 360 for cusp in cusps]

    asc_deg = round(ascmc[0], 2)
    signe_asc, deg_asc = degre_vers_signe(asc_deg)
    nakshatra_asc = get_nakshatra_name((asc_deg - ayanamsa) % 360)

    asc_deg_sid = (asc_deg - ayanamsa) % 360
    signe_asc_sid, deg_asc_sid = degre_vers_signe(asc_deg_sid)
    nakshatra_asc_sid = get_nakshatra_name(asc_deg_sid)

    maisons_tropicales = {}
    for i in range(12):
        deg = round(cusps[i], 2)
        signe, deg_signe = degre_vers_signe(deg)
        maisons_tropicales[f'Maison {i+1}'] = {
            'degre': deg,
            'signe': signe,
            'degre_dans_signe': deg_signe
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
            'maison': maison_ved
        }

        positions_tropicales[nomp] = deg_trop
        positions_vediques[nomp] = round(deg_sid, 2)

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

    # 💡 AJOUT NOUVEAU : extraire les points forts
    points_forts = extraire_points_forts({
        'planetes': resultats_tropical,
        'aspects': aspects,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'planetes_vediques': resultats_vediques
    })

    return {
        'nom': nom,
        'date': dt.strftime('%d %B %Y %H:%M'),
        'planetes': resultats_tropical,
        'maisons': maisons_tropicales,
        'maisons_vediques': maisons_vediques,
        'aspects': aspects,
        'maitre_ascendant': maitre_ascendant,
        'ascendant_sidereal': resultats_vediques['Ascendant'],
        'maitre_ascendant_vedique': maitre_asc_vedique,
        'planetes_vediques': resultats_vediques,
        'points_forts': points_forts  # ← on le transmet
    }

