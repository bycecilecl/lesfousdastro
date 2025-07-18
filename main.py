from flask import Flask, render_template, request, jsonify
import pyswisseph as swe
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from analyse_synthetique import extraire_points_forts
from analyse_gratuite import analyse_gratuite
from openai_utils import interroger_llm
import os
import openai
from dotenv import load_dotenv


load_dotenv()  # charge le fichier .env

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

def degre_vers_signe(degre):
    signes = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
              'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
    index = int(degre // 30)
    return signes[index], round(degre % 30, 2)

def angle_diff(angle1, angle2):
    diff = abs(angle1 - angle2) % 360
    return diff if diff <= 180 else 360 - diff

def get_nakshatra_name(degree_sidereal):
    nakshatras = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
        'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
    ]
    index = int(degree_sidereal // (360 / 27))
    return nakshatras[index]

def detecter_aspects(positions):
    aspects = []
    noms = list(positions.keys())
    angles = {'conjonction': 0, 'opposition': 180, 'trigone': 120, 'carre': 90, 'sextile': 60}
    orbes = {'conjonction': 10, 'opposition': 8, 'trigone': 8, 'carre': 6, 'sextile': 6}

    for i in range(len(noms)):
        for j in range(i + 1, len(noms)):
            p1, p2 = noms[i], noms[j]
            if (p1, p2) in [("Rahu", "Ketu"), ("Ketu", "Rahu")]:
                continue
            a1, a2 = positions[p1], positions[p2]
            orb_used = orbes if ("Ascendant" not in (p1, p2)) else {k: max(8, v) for k, v in orbes.items()}

            for aspect, angle in angles.items():
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
    maitres = {
        'Bélier': 'Mars', 'Taureau': 'Vénus', 'Gémeaux': 'Mercure', 'Cancer': 'Lune',
        'Lion': 'Soleil', 'Vierge': 'Mercure', 'Balance': 'Vénus', 'Scorpion': 'Mars',
        'Sagittaire': 'Jupiter', 'Capricorne': 'Saturne', 'Verseau': 'Saturne', 'Poissons': 'Jupiter'
    }
    return maitres.get(signe_asc)

def get_maison_planete(degre, cusps):
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if end < start:
            end += 360
        pos = degre if degre >= start else degre + 360
        if start <= pos < end:
            return i + 1
    return 12

# --- NOUVELLES FONCTIONS POUR MAISONS VÉDIQUES ---

def maisons_vediques_fixes(signe_asc_sid):
    signes = ['Bélier', 'Taureau', 'Gémeaux', 'Cancer', 'Lion', 'Vierge',
              'Balance', 'Scorpion', 'Sagittaire', 'Capricorne', 'Verseau', 'Poissons']
    index_asc = signes.index(signe_asc_sid)
    maisons = {}
    for i in range(12):
        signe_mais = signes[(index_asc + i) % 12]
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

def formater_positions_planetes(planetes):
    lignes = []
    for nom, infos in planetes.items():
        signe = infos.get('signe', 'inconnu')
        degre = infos.get('degre', 'n/a')
        maison = infos.get('maison', 'n/a')
        lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
    return "\n".join(lignes)

def formater_aspects(aspects):
    lignes = []
    for asp in aspects:
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        type_asp = asp.get('aspect', '?')
        orbe = asp.get('orbe', '?')
        lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes)


# === ROUTES ===

@app.route('/analyse_gratuite', methods=['GET', 'POST'])
def route_analyse_gratuite():
    if request.method == 'GET':
        return "Page accessible uniquement via formulaire POST"
    else:
        print("✅ Route /analyse_gratuite appelée")
        print("📝 Données reçues :", request.form)

        # 1. Calcul du thème
        data = calcul_theme(
            nom=request.form['nom'],
            date_naissance=request.form['date_naissance'],
            heure_naissance=request.form['heure_naissance'],
            lieu_naissance=request.form['lieu_naissance']
        )

        # 2. Récupération de la Lune védique
        lune_vedique = data['planetes_vediques'].get('Lune', {})

        # 3. Analyse synthétique (résumé)
        texte_resume = analyse_gratuite(
            planetes=data['planetes'],
            aspects=data['aspects'],
            lune_vedique=lune_vedique
        )

        # 4. Conversion liste → chaîne de texte
        texte_resume_str = "\n".join(texte_resume)
        if len(texte_resume_str) > 600:
            texte_resume_str = texte_resume_str[:600] + "..."
        print("🪐 Résumé de l'analyse :", texte_resume_str)

        # 5. Préparer positions et aspects détaillés
        positions_str = formater_positions_planetes(data['planetes'])
        aspects_str = formater_aspects(data['aspects'])

        # 6. Construction du prompt pour l'IA
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

        # 7. Appel à OpenAI
        texte_analyse_complete = interroger_llm(prompt)
        print("✅ Analyse IA reçue :", texte_analyse_complete)

        # 8. Affichage dans le template
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
    return render_template('formulaire.html')

@app.route('/resultat', methods=['POST'])
def resultat():
    email = request.form['email']  # ⬅️ on récupère l’email ici
    print(f"Email reçu : {email}")  # (optionnel, pour test)

    data = calcul_theme(
        nom=request.form['nom'],
        date_naissance=request.form['date_naissance'],
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )
    return render_template(
        'resultat.html',
        nom=data['nom'],
        date=request.form['date_naissance'],
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

@app.route('/json', methods=['POST'])
def resultat_json():
    data = calcul_theme(
        nom=request.form['nom'],
        date_naissance=request.form['date_naissance'],
        heure_naissance=request.form['heure_naissance'],
        lieu_naissance=request.form['lieu_naissance']
    )
    return jsonify(data)


