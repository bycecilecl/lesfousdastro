# 🌐 Librairies externes
from flask import Flask, render_template, request, jsonify, redirect, session
from geopy.geocoders import Nominatim
from datetime import datetime
import swisseph as swe
import pytz
import uuid
import os
import csv
import openai
from dotenv import load_dotenv

# 🔧 Fonctions personnalisées (app)
from utils.calcul_theme import calcul_theme
from utils.openai_utils import interroger_llm
from utils.astro_utils import corriger_donnees_maisons, valider_donnees_avant_analyse
from utils.utils_formatage import formater_positions_planetes, formater_aspects
from utils.utils_points_forts import extraire_points_forts
from utils.utils_analyse import analyse_gratuite
from utils.pdf_utils import html_to_pdf
from analyse_point_astral import analyse_point_astral
from analyse_gratuite import analyse_gratuite
from routes import register_routes



# Ajoutez au début du fichier, après les imports
try:
    import swisseph as swe
except ImportError:

    print("❌ SwissEph non installé. Installez avec: pip install pyephem")
    exit(1)

# Vérification de la clé API
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ OPENAI_API_KEY manquante dans le fichier .env")
    exit(1)
openai.api_key = api_key

# SIGNES_ZODIAC = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
#                  'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']

# NAKSHATRAS = [
#     'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
#     'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
#     'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
#     'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
#     'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
# ]

# ANGLES_ASPECTS = {'conjonction': 0, 'opposition': 180, 'trigone': 120, 'carre': 90, 'sextile': 60}
# ORBES_DEFAUT = {'conjonction': 10, 'opposition': 8, 'trigone': 8, 'carre': 6, 'sextile': 6}

# MAITRES_SIGNES = {
#     'Bélier': 'Mars', 'Taureau': 'Vénus', 'Gémeaux': 'Mercure', 'Cancer': 'Lune',
#     'Lion': 'Soleil', 'Vierge': 'Mercure', 'Balance': 'Vénus', 'Scorpion': 'Mars',
#     'Sagittaire': 'Jupiter', 'Capricorne': 'Saturne', 'Verseau': 'Saturne', 'Poissons': 'Jupiter'
# }

print("📁 Répertoire courant :", os.getcwd())
print("📄 Fichier existe ?", os.path.exists("utilisateurs.csv"))

load_dotenv()  # charge le fichier .env

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
register_routes(app)

# def get_maison_planete(degre, cusps):
#     degre = degre % 360  # Normaliser le degré
#     for i in range(12):
#         start = cusps[i] % 360
#         end = cusps[(i + 1) % 12] % 360
        
#         if start <= end:
#             if start <= degre < end:
#                 return i + 1
#         else:  # Passage par 0°
#             if degre >= start or degre < end:
#                 return i + 1
#     return 1  # Par défaut maison 1

# def degre_vers_signe(degre):
#     index = int(degre // 30)
#     if index >= len(SIGNES_ZODIAC):  # Protection contre les débordements
#         index = 0
#     return SIGNES_ZODIAC[index], round(degre % 30, 2)

# def angle_diff(a1, a2):
#     """
#     Calcule la différence d'angle absolue entre deux positions (en degrés),
#     en tenant compte du cercle zodiacal (0°–360°).
#     """
#     diff = abs(a1 - a2) % 360
#     return diff if diff <= 180 else 360 - diff

# def get_nakshatra_name(degree_sidereal):
#     index = int(degree_sidereal // (360 / 27))
#     if index >= len(NAKSHATRAS):  # Protection
#         index = 0
#     return NAKSHATRAS[index]

# def detecter_aspects(positions):
#     aspects = []
#     noms = list(positions.keys())

#     for i in range(len(noms)):
#         for j in range(i + 1, len(noms)):
#             p1, p2 = noms[i], noms[j]
#             if (p1, p2) in [("Rahu", "Ketu"), ("Ketu", "Rahu")]:
#                 continue
#             a1, a2 = positions[p1], positions[p2]
#             orb_used = ORBES_DEFAUT if ("Ascendant" not in (p1, p2)) else {k: max(8, v) for k, v in ORBES_DEFAUT.items()}

#             for aspect, angle in ANGLES_ASPECTS.items():
#                 ecart = abs(angle_diff(a1, a2) - angle)
#                 if ecart <= orb_used[aspect]:
#                     aspects.append({
#                         'planete1': p1,
#                         'planete2': p2,
#                         'aspect': aspect.capitalize(),
#                         'distance': round(angle_diff(a1, a2), 2),
#                         'orbe': round(ecart, 2),
#                         'angle_exact': angle
#                     })
#                     break
#     aspects.sort(key=lambda x: x['orbe'])
#     return aspects

# def get_maitre_ascendant(signe_asc):
#     return MAITRES_SIGNES.get(signe_asc)

# def maisons_vediques_fixes(signe_asc_sid):
#     index_asc = SIGNES_ZODIAC.index(signe_asc_sid)
#     maisons = {}
#     for i in range(12):
#         signe_mais = SIGNES_ZODIAC[(index_asc + i) % 12]
#         maisons[f'Maison {i+1}'] = {
#             'signe': signe_mais,
#             'degre': 0.0,
#             'degre_dans_signe': 0.0
#         }
#     return maisons

# def maison_vedique_planete_simple(signe_planete, signe_asc_sid):
#     index_asc = SIGNES_ZODIAC.index(signe_asc_sid)
#     index_plan = SIGNES_ZODIAC.index(signe_planete)
#     distance = (index_plan - index_asc) % 12
#     return distance + 1

# # --- NOUVELLES FONCTIONS POUR MAISONS VÉDIQUES ---

# def maisons_vediques_fixes(signe_asc_sid):
#     signes = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
#               'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
#     index_asc = signes.index(signe_asc_sid)
#     maisons = {}
#     for i in range(12):
#         signe_mais = signes[(index_asc + i) % 12]
#         maisons[f'Maison {i+1}'] = {
#             'signe': signe_mais,
#             'degre': 0.0,
#             'degre_dans_signe': 0.0
#         }
#     return maisons

# def maison_vedique_planete_simple(signe_planete, signe_asc_sid):
#     signes = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
#               'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
#     index_asc = signes.index(signe_asc_sid)
#     index_plan = signes.index(signe_planete)
#     distance = (index_plan - index_asc) % 12
#     return distance + 1


# theme_data = calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance)


# def calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance):
#     geolocator = Nominatim(user_agent="astro-app")
#     try:
#         location = geolocator.geocode(lieu_naissance, timeout=5)
#         lat, lon = (location.latitude, location.longitude) if location else (48.8566, 2.3522)
#     except:
#         lat, lon = 48.8566, 2.3522

#     tz = pytz.timezone('Europe/Paris')
#     #dt = tz.localize(datetime.strptime(date_naissance + ' ' + heure_naissance, '%Y-%m-%d %H:%M'))
#     # Gestion des deux formats possibles (brut ou déjà concaténé)
#     try:
#         dt = tz.localize(datetime.strptime(date_naissance + ' ' + heure_naissance, '%Y-%m-%d %H:%M'))
#     except ValueError:
#     # Format alternatif : date_naissance contient déjà l’heure
#         dt = tz.localize(datetime.strptime(date_naissance, '%d %B %Y %H:%M'))

#     dt_utc = dt.astimezone(pytz.utc)

#     swe.set_ephe_path('/usr/share/ephe')
#     jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60)
#     ayanamsa = swe.get_ayanamsa_ut(jd)

#     cusps, ascmc = swe.houses(jd, lat, lon, b'P')

#     cusps_sid = [(cusp - ayanamsa) % 360 for cusp in cusps]

#     asc_deg = round(ascmc[0], 2)
#     signe_asc, deg_asc = degre_vers_signe(asc_deg)
#     nakshatra_asc = get_nakshatra_name((asc_deg - ayanamsa) % 360)

#     asc_deg_sid = (asc_deg - ayanamsa) % 360
#     signe_asc_sid, deg_asc_sid = degre_vers_signe(asc_deg_sid)
#     nakshatra_asc_sid = get_nakshatra_name(asc_deg_sid)

#     maisons_tropicales = {}
#     for i in range(12):
#         deg = round(cusps[i], 2)
#         signe, deg_signe = degre_vers_signe(deg)
#         maisons_tropicales[f'Maison {i+1}'] = {
#             'degre': deg,
#             'signe': signe,
#             'degre_dans_signe': deg_signe
#         }

#     maisons_vediques = maisons_vediques_fixes(signe_asc_sid)

#     planetes = ['Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne',
#                 'Uranus', 'Neptune', 'Pluton', 'Rahu']
#     codes = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER,
#              swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO, swe.MEAN_NODE]

#     positions_tropicales = {'Ascendant': asc_deg}
#     positions_vediques = {'Ascendant': asc_deg_sid}

#     resultats_tropical = {
#         'Ascendant': {
#             'degre': asc_deg,
#             'signe': signe_asc,
#             'degre_dans_signe': deg_asc,
#         }
#     }
#     resultats_vediques = {
#         'Ascendant': {
#             'degre': round(asc_deg_sid, 2),
#             'signe': signe_asc_sid,
#             'degre_dans_signe': deg_asc_sid,
#             'nakshatra': nakshatra_asc_sid
#         }
#     }

#     for nomp, code in zip(planetes, codes):
#         deg_trop = round(swe.calc_ut(jd, code)[0][0], 2)
#         signe_trop, deg_signe_trop = degre_vers_signe(deg_trop)
#         maison_trop = get_maison_planete(deg_trop, cusps)

#         deg_sid = (deg_trop - ayanamsa) % 360
#         signe_ved, deg_signe_ved = degre_vers_signe(deg_sid)
#         nakshatra = get_nakshatra_name(deg_sid)
#         maison_ved = maison_vedique_planete_simple(signe_ved, signe_asc_sid)

#         resultats_tropical[nomp] = {
#             'degre': deg_trop,
#             'signe': signe_trop,
#             'degre_dans_signe': deg_signe_trop,
#             'maison': maison_trop
#         }

#         resultats_vediques[nomp] = {
#             'degre': round(deg_sid, 2),
#             'signe': signe_ved,
#             'degre_dans_signe': deg_signe_ved,
#             'nakshatra': nakshatra,
#             'maison': maison_ved
#         }

#         positions_tropicales[nomp] = deg_trop
#         positions_vediques[nomp] = round(deg_sid, 2)

#     # Ajout de Ketu
#     rahu_deg_trop = resultats_tropical['Rahu']['degre']
#     ketu_deg_trop = (rahu_deg_trop + 180) % 360
#     signe_ketu_trop, deg_ketu_trop = degre_vers_signe(ketu_deg_trop)
#     maison_ketu_trop = get_maison_planete(ketu_deg_trop, cusps)
#     resultats_tropical['Ketu'] = {
#         'degre': round(ketu_deg_trop, 2),
#         'signe': signe_ketu_trop,
#         'degre_dans_signe': deg_ketu_trop,
#         'maison': maison_ketu_trop
#     }
#     positions_tropicales['Ketu'] = ketu_deg_trop

#     rahu_deg_ved = resultats_vediques['Rahu']['degre']
#     ketu_deg_ved = (rahu_deg_ved + 180) % 360
#     signe_ketu_ved, deg_ketu_ved = degre_vers_signe(ketu_deg_ved)
#     maison_ketu_ved = maison_vedique_planete_simple(signe_ketu_ved, signe_asc_sid)
#     resultats_vediques['Ketu'] = {
#         'degre': round(ketu_deg_ved, 2),
#         'signe': signe_ketu_ved,
#         'degre_dans_signe': deg_ketu_ved,
#         'nakshatra': get_nakshatra_name(ketu_deg_ved),
#         'maison': maison_ketu_ved
#     }
#     positions_vediques['Ketu'] = round(ketu_deg_ved, 2)

#     aspects = detecter_aspects(positions_tropicales)

#     nom_maitre_trop = get_maitre_ascendant(signe_asc)
#     maitre_ascendant = None
#     if nom_maitre_trop and nom_maitre_trop in resultats_tropical:
#         infos = resultats_tropical[nom_maitre_trop]
#         deg = infos['degre']
#         maison = get_maison_planete(deg, cusps)
#         maitre_ascendant = {
#             'nom': nom_maitre_trop,
#             'degre': deg,
#             'signe': infos['signe'],
#             'degre_dans_signe': infos['degre_dans_signe'],
#             'maison': maison
#         }

#     nom_maitre_ved = get_maitre_ascendant(signe_asc_sid)
#     maitre_asc_vedique = None
#     if nom_maitre_ved and nom_maitre_ved in resultats_vediques:
#         infos = resultats_vediques[nom_maitre_ved]
#         deg = infos['degre']
#         nakshatra = infos['nakshatra']
#         maison = infos.get('maison')
#         maitre_asc_vedique = {
#             'nom': nom_maitre_ved,
#             'degre': deg,
#             'signe': infos['signe'],
#             'degre_dans_signe': infos['degre_dans_signe'],
#             'nakshatra': nakshatra,
#             'maison': maison
#         }

#     # 💡 AJOUT NOUVEAU : extraire les points forts
#     points_forts = extraire_points_forts({
#         'planetes': resultats_tropical,
#         'aspects': aspects,
#         'ascendant_sidereal': resultats_vediques['Ascendant'],
#         'planetes_vediques': resultats_vediques
#     })

#     return {
#         'nom': nom,
#         'date': dt.strftime('%d %B %Y %H:%M'),
#         'planetes': resultats_tropical,
#         'maisons': maisons_tropicales,
#         'maisons_vediques': maisons_vediques,
#         'aspects': aspects,
#         'maitre_ascendant': maitre_ascendant,
#         'ascendant_sidereal': resultats_vediques['Ascendant'],
#         'maitre_ascendant_vedique': maitre_asc_vedique,
#         'planetes_vediques': resultats_vediques,
#         'points_forts': points_forts  # ← on le transmet
#     }

# def formater_positions_planetes(planetes):
#     lignes = []
#     for nom, infos in planetes.items():
#         signe = infos.get('signe', 'inconnu')
#         degre = infos.get('degre', 'n/a')
#         maison = infos.get('maison', 'n/a')
#         lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
#     return "\n".join(lignes)

# def formater_aspects(aspects):
#     lignes = []
#     for asp in aspects:
#         p1 = asp.get('planete1', '?')
#         p2 = asp.get('planete2', '?')
#         type_asp = asp.get('aspect', '?')
#         orbe = asp.get('orbe', '?')
#         lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
#     return "\n".join(lignes)


# === ROUTES ===


@app.route('/generer_theme', methods=['POST'])
def generer_theme():
    nom = request.form.get('nom')
    date_naissance = request.form.get('date_naissance')
    heure_naissance = request.form.get('heure_naissance')
    lieu_naissance = request.form.get('lieu_naissance')

    theme_data = calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance)

    return render_template('resultat.html', data=theme_data)

@app.route('/analyse_gratuite', methods=['POST'])
def analyse_gratuite_post():
    print("✅ Route /analyse_gratuite appelée")
    print("📝 Données reçues :", request.form)

    if 'consentement' not in request.form:
        return "Consentement obligatoire pour générer l'analyse", 400

    # 1. Sauvegarde des données utilisateur
    donnees_utilisateur = [
        request.form['nom'],
        request.form['email'],
        request.form['date_naissance'],
        request.form['heure_naissance'],
        request.form['lieu_naissance']
    ]
    chemin_csv = os.path.join(os.path.dirname(__file__), 'utilisateurs.csv')
    fichier_existe = os.path.exists(chemin_csv)

    try:
        with open(chemin_csv, mode='a', newline='', encoding='utf-8') as fichier:
            writer = csv.writer(fichier)
            if not fichier_existe:
                writer.writerow(['nom', 'email', 'date_naissance', 'heure_naissance', 'lieu_naissance'])
            writer.writerow(donnees_utilisateur)
        print("✅ Données utilisateur enregistrées.")
    except Exception as e:
        print("❌ Erreur CSV :", e)

    # 2. Calcul du thème
    data = calcul_theme(
        nom=request.form['nom'],
        date_naissance=request.form['date_naissance'],
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )

    # 3. Analyse gratuite
    texte_resume = analyse_gratuite(
        planetes=data['planetes'],
        aspects=data['aspects'],
        lune_vedique=data['planetes_vediques'].get('Lune', {})
    )

    texte_resume_str = "\n".join(texte_resume)
    if len(texte_resume_str) > 600:
        texte_resume_str = texte_resume_str[:600] + "..."

    # 4. Préparer les textes à injecter dans le prompt
    positions_str = formater_positions_planetes(data['planetes'])
    aspects_str = formater_aspects(data['aspects'])

    # 5. Construction du prompt pour l'IA
    prompt = f"""
Tu es une astrologue expérimentée, à la plume fine, directe, drôle et lucide.
Tu proposes des analyses psychologiques profondes, qui vont à l’essentiel.
Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
Ton style est vivant mais jamais niais. Tu évites les clichés astrologiques.
Tu ne parles pas *de* la personne, tu lui parles *directement*.
Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

Voici les données du thème de {data['nom']} :

Résumé synthétique :
{texte_resume_str}

Positions planétaires :
{positions_str}

Aspects astrologiques :
{aspects_str}

Instruction : 

Écris une lecture globale, cohérente et incarnée du thème natal.
- Ne commente pas les positions une par une.
- Repère les tensions internes (les dissonances, les contradictions).
- Parle des dynamiques psychologiques sous-jacentes.
- Mets en lumière les ressources intérieures.
- Parle vrai, pas besoin de brosser dans le sens du poil.
- Ose montrer les tiraillements, les paradoxes, les excès ou inhibitions.
- Tu peux ajouter un regard existentiel si pertinent.
- Ne déduis pas que la personne est extravertie ou sociable sans raison valable.
- Utilise uniquement l’astrologie occidentale tropicale (signes, maisons, aspects) comme base d’interprétation.
- N’intègre pas les données védiques (signe sidéral, maisons égales, logique karmique, etc.).
- Fais exception uniquement pour le Nakshatra de la Lune védique, si celui-ci permet un éclairage complémentaire précis.
- Ne mélange pas les deux systèmes dans une même phrase ou logique d’interprétation.

Tu peux conclure par une ou deux questions qui ouvrent à la réflexion. 
Cette analyse doit donner envie d'en savoir plus, d'explorer plus en profondeur.

Fais une analyse de max 15 lignes.
"""

    print("📤 Prompt envoyé à l'IA :", prompt)

    # 6. Appel à OpenAI
    texte_analyse_complete = interroger_llm(prompt)
    print("✅ Analyse IA reçue :", texte_analyse_complete)

    # 7. Affichage dans le template
    return render_template(
        'analyse_gratuite.html',
        nom=data['nom'],
        date=data['date'],
        analyse=texte_analyse_complete,
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )

@app.route('/')
def formulaire():
    infos = session.get("infos_utilisateur", {})
    return render_template('formulaire.html', infos=infos)

@app.route('/tous_les_placements', methods=['POST'])
def tous_les_placements():
    nom = request.form.get('nom')
    date_naissance = request.form.get('date_naissance')
    heure_naissance = request.form.get('heure_naissance')
    lieu_naissance = request.form.get('lieu_naissance')

    data = calcul_theme(
        nom=nom,
        date_naissance=date_naissance,
        heure_naissance=heure_naissance,
        lieu_naissance=lieu_naissance
    )

    return render_template(
        'resultat.html',
        nom=data['nom'],
        date=data['date'],
        planetes=data['planetes'],
        maisons=data['maisons'],
        maisons_vediques=data['maisons_vediques'],
        aspects=data['aspects'],
        maitre_ascendant=data['maitre_ascendant'],
        ascendant_sidereal=data['ascendant_sidereal'],
        maitre_ascendant_vedique=data['maitre_ascendant_vedique'],
        planetes_vediques=data['planetes_vediques'],
        points_forts=data['points_forts']
    )

@app.route('/test_placements')
def test_placements():
    # données factices pour test
    data = {
        'nom': 'Test',
        'planetes': {
            'Soleil': {'signe': 'Lion', 'degre': 15.5, 'maison': 5},
            'Lune': {'signe': 'Cancer', 'degre': 22.0, 'maison': 4},
        },
        'aspects': [
            {'planete1': 'Soleil', 'planete2': 'Lune', 'aspect': 'Conjonction', 'orbe': 2}
        ]
    }
    positions_str = formater_positions_planetes(data['planetes'])
    aspects_str = formater_aspects(data['aspects'])
    return render_template('tous_les_placements.html', nom=data['nom'], positions=positions_str, aspects=aspects_str)

@app.route("/placements", methods=["GET"])
def placements():
    nom = request.args.get("nom")
    date_naissance = request.args.get("date")
    heure_naissance = request.args.get("heure", "10:00")
    lieu_naissance = request.args.get("lieu", "Paris")

    if not nom or not date_naissance:
        return "Erreur : paramètres manquants dans l'URL.", 400

    print("NOM =", nom)
    print("DATE =", date_naissance)

    # Appel du moteur de thème
    data = calcul_theme(
        nom=nom,
        date_naissance=date_naissance,
        heure_naissance=heure_naissance,
        lieu_naissance=lieu_naissance
    )

    return render_template(
        'tous_les_placements.html',
        nom=data['nom'],
        date=data['date'],
        planetes=data['planetes'],
        maisons=data['maisons'],
        maisons_vediques=data['maisons_vediques'],
        aspects=data['aspects'],
        maitre_ascendant=data['maitre_ascendant'],
        ascendant_sidereal=data['ascendant_sidereal'],
        maitre_ascendant_vedique=data['maitre_ascendant_vedique'],
        planetes_vediques=data['planetes_vediques'],
        points_forts=data['points_forts']
    )

@app.route('/analyse_point_astral', methods=['POST'])
def analyse_point_astral_post():
    print("✅ Route /analyse_point_astral appelée")

    if 'consentement' not in request.form:
        return "Consentement obligatoire pour générer l'analyse", 400

    nom = request.form.get('nom')
    email = request.form.get('email')
    date_naissance = request.form.get('date_naissance')
    heure_naissance = request.form.get('heure_naissance')
    lieu_naissance = request.form.get('lieu_naissance')

    # Calculer les données astrologiques AVANT de les stocker
    theme_data = calcul_theme(
        nom=nom,
        date_naissance=date_naissance,
        heure_naissance=heure_naissance,
        lieu_naissance=lieu_naissance
    )

    # Ensuite seulement, tu peux les stocker dans la session
    session["infos_utilisateur"] = {
        "nom": nom,
        "email": email,
        "date_naissance": date_naissance,
        "heure_naissance": heure_naissance,
        "lieu_naissance": lieu_naissance
    }

    session["donnees_astrologiques"] = theme_data

    # … puis tu continues avec l’analyse
    html_analyse = analyse_point_astral(theme_data, interroger_llm, session["infos_utilisateur"])

    filename = f"point_astral_{uuid.uuid4().hex}.pdf"
    output_path = f"static/pdfs/{filename}"
    os.makedirs("static/pdfs", exist_ok=True)
    html_to_pdf(html_analyse, output_path)

    return render_template("resultat_point_astral.html", 
                           analyse_html=html_analyse,
                           pdf_url=f"/static/pdfs/{filename}")

@app.route('/json', methods=['POST'])
def resultat_json():
    data = calcul_theme(
        nom=request.form['nom'],
        date_naissance=request.form['date_naissance'],
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )
    return jsonify(data)

@app.route("/analyse", methods=["POST"])
def analyse_post():
    form_data = request.form
    type_analyse = form_data.get("type_analyse")

    if not form_data.get("consentement"):
        return "Consentement obligatoire pour générer l'analyse", 400

    if type_analyse == "gratuite":
        return redirect("/analyse_gratuite", code=307)  # Garde les données POST
    elif type_analyse == "point_astral":
        return redirect("/analyse_point_astral", code=307)
    else:
        return "Type d’analyse inconnu", 400
    

@app.route("/mentions-legales")
def mentions_legales():
    return render_template("mentions_legales.html")

if __name__ == "__main__":
    # Ce bloc ne sera exécuté que quand tu lances localement avec "python main.py"
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=True, host="0.0.0.0", port=port)
