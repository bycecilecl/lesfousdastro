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
from utils.analyse_gratuite import analyse_gratuite
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

print("📁 Répertoire courant :", os.getcwd())
print("📄 Fichier existe ?", os.path.exists("utilisateurs.csv"))

load_dotenv()  # charge le fichier .env
openai.api_key = os.getenv("OPENAI_API_KEY")


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "jcg)c+og9c47o=cufp-%)o6q@$14#8980_(z23a$+t771sn!@*")
register_routes(app)


# === ROUTES ===

@app.route('/generer_theme', methods=['POST'])
def generer_theme():
    nom = request.form.get('nom')
    date_naissance = request.form.get('date_naissance')
    heure_naissance = request.form.get('heure_naissance')
    lieu_naissance = request.form.get('lieu_naissance')

    theme_data = calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance)

    return render_template('resultat.html', data=theme_data)


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

    print("\n📍 Liste des endpoints Flask enregistrés :")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint:35} ➝ {rule.methods} ➝ {rule.rule}")
    app.run(debug=True, host="0.0.0.0", port=port)

