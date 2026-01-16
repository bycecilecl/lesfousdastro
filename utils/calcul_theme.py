from geopy.geocoders import Nominatim
from datetime import datetime
import pytz
import os
import swisseph as swe
from timezonefinder import TimezoneFinder
from utils.formatage import formater_positions_planetes
from utils.utils_points_forts import extraire_points_forts
from utils.astro_utils import valider_donnees_avant_analyse, corriger_donnees_maisons
from utils.calculs_astrologiques import get_maison_planete, detecter_aspects, get_nakshatra_name, degre_vers_signe, get_maitre_ascendant, maisons_vediques_fixes, maison_vedique_planete_simple

# Initialiser TimezoneFinder une seule fois
tf = TimezoneFinder()

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
#   dans les routes Flask pour alimenter les analyses (gratuite, Flash Astral, etc.).
# ────────────────────────────────────────────────


def calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance,
                 lat=None, lon=None, dt_naissance_utc=None, tzid=None):
    
    nom_utilisateur = nom
    
    print(f"🚀 Calcul_Theme_DÉBUT CALCUL pour {nom}")
    print(f"   Calcul_Theme_Paramètres reçus: lat={lat}, lon={lon}, tzid={tzid}")
    print(f"DEBUT calcul_theme: nom = '{nom}'")
    
    # --- ÉTAPE 1: Obtenir les coordonnées ---
    # if lat is None or lon is None:
    #     print(f"🌍 Géocodage de '{lieu_naissance}'...")
    #     geolocator = Nominatim(user_agent="astro-app")
    #     try:
    #         location = geolocator.geocode(lieu_naissance, timeout=10)
    #         if location:
    #             lat, lon = location.latitude, location.longitude
    #             print(f"✅ Géocodage réussi: {lat:.6f}, {lon:.6f}")
    #         else:
    #             print(f"⚠️ Géocodage échoué, utilisation de Paris par défaut")
    #             lat, lon = 48.8566, 2.3522
    #     except Exception as e:
    #         print(f"❌ Erreur géocodage: {e}")
    #         lat, lon = 48.8566, 2.3522

    def _to_float_or_none(x):
        if x is None:
            return None
        x = str(x).strip().replace(",", ".")
        try:
            return float(x)
        except Exception:
            return None

    lat_f = _to_float_or_none(lat)
    lon_f = _to_float_or_none(lon)

    if lat_f is not None and lon_f is not None:
        # ✅ on a des coordonnées précises → pas de géocodage
        lat, lon = lat_f, lon_f
        print(f"🎯 Calcul_Theme_Coordonnées fournies: {lat}, {lon}")
    else:
        # 🌍 fallback géocodage (Nominatim) avec User-Agent obligatoire en prod
        print(f"🌍 Calcul_Theme_Géocodage de '{lieu_naissance}'...")
        ua = os.getenv("GEOCODER_UA", "lesfousdastro/1.0 contact:admin@example.com")
        geolocator = Nominatim(user_agent=ua)
        try:
            location = geolocator.geocode(lieu_naissance, timeout=10, language="fr")
            if location:
                lat, lon = float(location.latitude), float(location.longitude)
                print(f"✅ Calcul_Theme_Géocodage réussi: {lat:.6f}, {lon:.6f}")
            else:
                print("⚠️ Calcul_Theme_Géocodage échoué, utilisation de Paris par défaut")
                lat, lon = 48.8566, 2.3522
        except Exception as e:
            print(f"❌ Calcul_Theme_Erreur géocodage: {e} → Paris par défaut")
            lat, lon = 48.8566, 2.3522

    # --- ÉTAPE 2: Parser la date de naissance ---
    try:
        naive = datetime.strptime(f"{date_naissance} {heure_naissance}", '%Y-%m-%d %H:%M')
    except ValueError:
        try:
            naive = datetime.strptime(date_naissance, '%d %B %Y %H:%M')
        except ValueError as e:
            print(f"❌ Calcul_Theme_Format de date non reconnu: {e}")
            raise

    print(f"📅 Calcul_Theme_Date parsée: {naive}")

    # --- ÉTAPE 3: Obtenir le fuseau horaire correct ---
    dt_local = None  # ✅ évite UnboundLocalError lors du print final
    if dt_naissance_utc is not None:
    # Cas 1: UTC déjà fourni (priorité absolue)
        dt_utc = dt_naissance_utc
        print(f"✅ Calcul_Theme_UTC pré-calculé utilisé: {dt_utc}")

        # ✅ définir aussi l'heure locale pour le log final
        try:
            tzid = tzid or "UTC"
            if tzid == "UTC":
                dt_local = dt_utc
            else:
                tz_local = pytz.timezone(tzid)
                # 🔥 correction ici :
                dt_local = dt_utc.astimezone(tz_local)
        except Exception as e:
            print(f"⚠️ Calcul_Theme_Impossible de reconstruire l'heure locale depuis l'UTC ({e}), on garde UTC")
            dt_local = dt_utc
    else:
        # Cas 2: Déterminer le fuseau et convertir
        if tzid is None:
            tzid = get_timezone_for_coordinates_and_date(lat, lon, naive)
            print(f"🕐 Calcul_Theme_Fuseau détecté: {tzid}")
        
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
                tz_local = pytz.timezone(tzid)
                dt_local = tz_local.localize(naive, is_dst=False)
                dt_utc = dt_local.astimezone(pytz.UTC)
            except pytz.NonExistentTimeError:
                tz_local = pytz.timezone(tzid)
                dt_local = tz_local.localize(naive, is_dst=True)
                dt_utc = dt_local.astimezone(pytz.UTC)
            except Exception as e:
                print(f"❌ Erreur conversion fuseau '{tzid}': {e}")
                dt_local = naive.replace(tzinfo=pytz.UTC)
                dt_utc = dt_local
    print(f"🔧 Calcul_Theme_TEMPS FINAL:")
    print(f"   Calcul_Theme_Heure locale: {dt_local.strftime('%Y-%m-%d %H:%M %Z%z') if hasattr(dt_local, 'strftime') else 'N/A'}")
    print(f"   Calcul_Theme_Heure UTC: {dt_utc.strftime('%Y-%m-%d %H:%M %Z%z')}")
    print("🧪 Calcul_Theme_Sanity check:", "aware/local=", dt_local.tzinfo is not None, "aware/utc=", dt_utc.tzinfo is not None)
    print("🧪 Calcul_Theme_Round-trip OK ?",
      abs((dt_local.astimezone(pytz.UTC) - dt_utc).total_seconds()) < 1)

    # --- ÉTAPE 4: Calculs astrologiques ---
    swe.set_ephe_path(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ephe'))
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60.0)
    
    print(f"🌟 Calcul_Theme_Jour Julien calculé: {jd}")
    
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    
    print(f"🌙 Calcul_Theme_Ayanamsa (Lahiri): {ayanamsa:.4f}°")

    # Calcul des maisons avec Placidus
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    #cusps_sid = [(cusp - ayanamsa) % 360 for cusp in cusps]

    asc_deg = round(ascmc[0], 2)
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
            'degre': round(asc_deg_sid, 2),
            'signe': signe_asc_sid,
            'degre_dans_signe': deg_asc_sid,
            'nakshatra': nakshatra_asc_sid
        }
    }

    for nomp, code in zip(planetes, codes):
       
       # --- 1) Récupérer aussi la vitesse pour détecter le rétrograde
        pos, _ = swe.calc_ut(jd, code)            # pos = [longitude, latitude, distance, vitesse_longitude]
        deg_trop = round(pos[0], 2)                # remplace: swe.calc_ut(jd, code)[0][0]
        speed = pos[3]

        # --- 2) Déterminer si la planète est rétrograde (que pour ces 5-là)
        planetes_retro_ok = ["Mercure", "Vénus", "Mars", "Jupiter", "Saturne"]
        is_retro = (nomp in planetes_retro_ok) and (speed < 0)
       
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
            'maison': maison_trop,
            'retrograde': is_retro,
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
        "degre": round(pof_deg, 2),
        "signe": signe_pof,
        "degre_dans_signe": round(deg_pof, 2),
        "maison": maison_pof,
        "diurne": is_day
    }

    #positions_tropicales["Part de Fortune"] = round(pof_deg, 2)

    
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

    # --- AJOUT : Axe des Portes Uranus → Saturne ---
    uranus_deg = float(resultats_tropical["Uranus"]["degre"])
    saturne_deg = float(resultats_tropical["Saturne"]["degre"])

    def _delta_circulaire(a, b):
        d = (b - a) % 360.0
        return d if d >= 0 else d + 360.0

    axe_portes = {
        "depart": "Uranus",
        "arrivee": "Saturne",
        "uranus_deg": round(uranus_deg, 2),
        "saturne_deg": round(saturne_deg, 2),
        "arc_uranus_vers_saturne": round(_delta_circulaire(uranus_deg, saturne_deg), 2),
        "porte": "invisible"
    }




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

    print(f"FIN calcul_theme: nom = '{nom}'")

    return {
        'nom': nom_utilisateur,
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
        'points_forts': points_forts,
        'angles_deg': angles_deg,         
        'planetes_deg': planetes_deg,
        'axe_des_portes': axe_portes,
        'part_de_fortune': resultats_tropical.get("Part de Fortune"),     
    }