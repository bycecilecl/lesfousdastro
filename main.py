# 🌐 Librairies externes
from flask import Flask, render_template, request, jsonify, redirect, session, send_file, url_for, abort, Blueprint
from geopy.geocoders import Nominatim
from datetime import datetime, timezone
import swisseph as swe
import pytz
import uuid
import os
import csv
import openai
import atexit

from dotenv import load_dotenv

# 🔧 Fonctions personnalisées (app)
from utils.rag_utils_optimized import cleanup_weaviate
from utils.calcul_theme import calcul_theme
from utils.openai_utils import interroger_llm
from utils.astro_utils import corriger_donnees_maisons, valider_donnees_avant_analyse
from utils.formatage import formater_positions_planetes, formater_aspects
from utils.pdf_utils import html_to_pdf
from routes.legales import legal_bp
from utils.s3_utils import presign_key
#from utils.prod_hardening import harden_app

from routes import register_routes
from routes.geocode import geocode_bp
from routes.paypal import payments_bp


from utils.axes_majeurs import organiser_points_forts, formater_axes_majeurs
from utils.utils_points_forts import extraire_points_forts  
from routes.analyse_gratuite_api import gratuite_api_bp
from routes.point_astral_blocs import point_astral_blocs_bp


import logging
logging.getLogger('weasyprint').setLevel(logging.CRITICAL)
logging.getLogger('fontTools').setLevel(logging.CRITICAL)
logging.getLogger('fontTools.subset').setLevel(logging.CRITICAL)
logging.getLogger('fontTools.ttLib').setLevel(logging.CRITICAL)

print("🧭 RUN main.py depuis:", __file__)

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # si besoin (pip install backports.zoneinfo)

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


def local_to_utc(date_str: str, heure_str: str, tzid: str) -> datetime:
    """
    Convertit date+heure locales (YYYY-MM-DD, HH:MM) avec tzid -> datetime en UTC (aware),
    via IANA tzdb (zoneinfo), plus fiable pour l'historique (Casablanca 1998 = UTC+00).
    """
    naive = datetime.fromisoformat(f"{date_str}T{heure_str}:00")
    local = naive.replace(tzinfo=ZoneInfo(tzid))
    return local.astimezone(timezone.utc)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ⚙️ Sécurité cookies et URLs
app.config.update(
    SESSION_COOKIE_SECURE=True,        # cookies seulement en HTTPS
    SESSION_COOKIE_HTTPONLY=True,      # inaccessible en JS
    SESSION_COOKIE_SAMESITE="Lax",
    REMEMBER_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
    PREFERRED_URL_SCHEME="https",
)

# --- Blueprint principal: créer -> définir routes -> enregistrer
main_bp = Blueprint("main", __name__)

# --- Blueprints tiers d'abord si tu veux, peu importe l'ordre entre eux
app.register_blueprint(geocode_bp)
app.register_blueprint(gratuite_api_bp)
app.register_blueprint(point_astral_blocs_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(legal_bp)

# 5) Headers de sécurité (après enregistrement des routes)
from security_headers import add_security_headers
add_security_headers(app)


@main_bp.route("/")
def index():
    mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
    client_id = (
        os.getenv("PAYPAL_CLIENT_ID_LIVE")
        if mode == "live"
        else os.getenv("PAYPAL_CLIENT_ID_SANDBOX")
    )
    print(f"[PayPal] mode={mode} client_id={'***' + (client_id or '')[-6:]}")
    infos = session.get("infos_utilisateur", {})
    return render_template(
        "astro_form.html",   # ← la page qui contient le formulaire et PayPal
        infos=infos,
        PAYPAL_CLIENT_ID=client_id,
        PAYPAL_CURRENCY=os.getenv("PAYPAL_CURRENCY", "EUR"),
    )
@main_bp.route("/analyses")
def analyses():
    # alias si tu veux que /analyses affiche la même page d’accueil “Analyses cosmiques”
    return render_template("index.html")

app.register_blueprint(main_bp)
#app.register_blueprint(main_bp, name='main')

@app.get("/dl/<path:key>")
def dl_presign(key):
    try:
        url = presign_key(key)   # génère une URL S3 présignée à la volée
        return redirect(url, code=302)
    except Exception as e:
        print(f"dl_presign error: {e}")
        return "Lien indisponible ou expiré. Réessaie depuis ton espace.", 410


# tes routes centralisées
#harden_app(app)
register_routes(app)

print("=== URL MAP ===")
print(app.url_map)

print("🔎 Main URL MAP")
for r in app.url_map.iter_rules():
    print(f"{r.endpoint:45} -> {r.rule}")

# === ROUTES ===

# ────────────────────────────────────────────────
# ROUTE : /generer_theme
# Objectif : Récupère les infos du formulaire, calcule le thème astrologique
# via calcul_theme(), puis affiche le résultat dans resultat.html.
# Cette route sert à générer un thème complet à partir des données de naissance.
# ────────────────────────────────────────────────

@app.route('/generer_theme', methods=['POST'])
def generer_theme():
    nom = request.form.get('nom')
    date_naissance = request.form.get('date_naissance')
    heure_naissance = request.form.get('heure_naissance')
    lieu_naissance = request.form.get('lieu_naissance')

    theme_data = calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance)

    return render_template('resultat.html', data=theme_data)

# ────────────────────────────────────────────────
# ROUTE : /
# Objectif : Affiche la page d’accueil avec le formulaire de saisie.
# Si des informations utilisateur existent déjà en session (nom, date, heure, lieu),
# elles sont passées au template pour préremplir le formulaire.
# ────────────────────────────────────────────────


# => ANCIEN FORMULAIRE
# @app.route('/')
# def formulaire():
#     infos = session.get("infos_utilisateur", {})
#     return render_template('formulaire.html', infos=infos)

# @app.route('/', methods=["GET"])
# def formulaire():
#     infos = session.get("infos_utilisateur", {})
#     return render_template('astro_form.html', infos=infos)

# @main_bp.route("/")
# def index():
#     # affiche templates/index.html (qui étend base.html)
#     return render_template("index.html")

# @app.get("/")
# def home():
#     mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
#     client_id = (
#         os.getenv("PAYPAL_CLIENT_ID_LIVE")
#         if mode == "live"
#         else os.getenv("PAYPAL_CLIENT_ID_SANDBOX")
#     )
#     # Facile à tracer en console
#     print(f"[PayPal] mode={mode} client_id={'***' + (client_id or '')[-6:]}")
#     infos = session.get("infos_utilisateur", {})
#     return render_template(
#         "astro_form.html",               # ← unifie le nom du template
#         infos=infos,
#         PAYPAL_CLIENT_ID=client_id,
#         PAYPAL_CURRENCY=os.getenv("PAYPAL_CURRENCY", "EUR"),
#     )



def preparer_donnees_analyse(data):
    """
    Range les 'points_forts' existants en Axes Majeurs et prépare un bloc texte
    prêt à injecter dans le Point Astral.
    """
    # 0) Sécurité : si points_forts manquants, on tente de les extraire
    raw_pf = data.get("points_forts")
    if not raw_pf:
        try:
            raw_pf = extraire_points_forts(data)
            data["points_forts"] = raw_pf
        except Exception as e:
            print(f"⚠️ Impossible d'extraire points_forts: {e}")
            raw_pf = []

    # 1) Normalisation (liste propre)
    if isinstance(raw_pf, str):
        lignes = [l.strip("•-–—* ").strip() for l in raw_pf.splitlines() if l.strip()]
        points_forts_list = [l for l in lignes if l]
    else:
        points_forts_list = list(raw_pf) if raw_pf else []

    # 2) Organisation Axes Majeurs
    axes = organiser_points_forts(points_forts_list)
    axes_str = formater_axes_majeurs(axes)

    # 3) Stockage
    data["axes_majeurs"] = axes
    data["axes_majeurs_str"] = axes_str

    # 4) Occidental : Rahu/Ketu → Nœud Nord/Sud
    data["axes_majeurs_str"] = (
        data["axes_majeurs_str"]
        .replace("Rahu", "Nœud Nord")
        .replace("Ketu", "Nœud Sud")
    )
    return data

# ------------------------------------------------------------
# preparer_donnees_analyse(data)
# ------------------------------------------------------------
# But :
#   Préparer les données pour l'analyse complète (Point Astral).
#   - Vérifie ou extrait les "points forts" depuis le thème.
#   - Nettoie et normalise la liste.
#   - Classe ces points forts en "axes majeurs" grâce à organiser_points_forts.
#   - Formate le texte final (axes_majeurs_str) pour affichage.
#   - Remplace Rahu/Ketu par Nœud Nord/Sud pour l'astrologie occidentale.
#   - Ajoute ces données à "data" avant retour.
#
# Entrée :
#   data (dict) : contient toutes les données astrologiques d'un thème
#
# Sortie :
#   dict : même objet data, enrichi avec "axes_majeurs" et "axes_majeurs_str"
# ------------------------------------------------------------

@app.route('/tous_les_placements', methods=['POST'])
def tous_les_placements():
    nom = request.form.get('nom')
    date_naissance = request.form.get('date_naissance')   # "1998-03-04"
    heure_naissance = request.form.get('heure_naissance') # "03:15"
    lieu_naissance = request.form.get('lieu_naissance')

    print(f"📍 Main Lieu saisi : {lieu_naissance}")

    # ⬇️ NOUVEAU : on récupère les champs cachés
    lat = request.form.get('lat')
    lon = request.form.get('lon')
    tzid = request.form.get('tzid')

    print(f"🧭 Main Coords reçues : lat={lat}, lon={lon}, tzid={tzid}")

    # Sécurités légères
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except ValueError:
        lat = lon = None

    dt_utc = None
    if tzid and date_naissance and heure_naissance:
        try:
            dt_utc = local_to_utc(date_naissance, heure_naissance, tzid)
        except Exception as e:
            print(f"⚠️ Conversion locale->UTC échouée: {e}")
            dt_utc = None

    # ✅ Appel du calculateur
    # On tente d'abord avec de nouveaux kwargs (si ton calcul_theme les supporte déjà),
    # sinon on retombe sur l'ancien appel intact.

    print(f"➡️ Main ENTRÉE CALCUL: lat={lat}, lon={lon}, tzid={tzid}, dt_utc={dt_utc}")
    try:
        data = calcul_theme(
            nom=nom,
            date_naissance=date_naissance,
            heure_naissance=heure_naissance,
            lieu_naissance=lieu_naissance,
            lat=lat, lon=lon, dt_naissance_utc=dt_utc,
            tzid=tzid  
        )
    except TypeError:
        # Compat: ancienne signature (ton code continue de marcher)
        data = calcul_theme(
            nom=nom,
            date_naissance=date_naissance,
            heure_naissance=heure_naissance,
            lieu_naissance=lieu_naissance
        )
        # On glisse quand même les infos (utile pour debug/affichage)
        data["_coords"] = {
            "lat": lat, "lon": lon, "tzid": tzid,
            "dt_utc": dt_utc.isoformat() if dt_utc else None
        }

        print("=" * 50)
        print("🔍 Main DEBUG INTERCEPTIONS")
        print("=" * 50)
        print("🧩 Main CLÉS DATA:", sorted(list(data.keys())))
        print("🔎 Main Interceptions présentes ?", "interceptions" in data or "axes_interceptes" in data)
        
        print("🧪 Main Aperçu interceptions:", data.get("interceptions") or data.get("axes_interceptes"))

        if "interceptions" in data:
            interceptions_data = data["interceptions"]
            print(f"📋 Main Type interceptions: {type(interceptions_data)}")
            print(f"📋 Main Contenu interceptions: {interceptions_data}")
            
            if isinstance(interceptions_data, dict):
                for cle, valeur in interceptions_data.items():
                    print(f"   {cle}: {valeur}")
        else:
            print("❌ Main Clé 'interceptions' manquante dans data")
            
            # Chercher d'autres noms possibles
            autres_cles = [cle for cle in data.keys() if 'intercept' in cle.lower()]
            if autres_cles:
                print(f"🔍 Main Clés similaires trouvées: {autres_cles}")
                for cle in autres_cles:
                    print(f"   {cle}: {data[cle]}")
            else:
                print("🔍 Aucune clé contenant 'intercept' trouvée")
        
        print("🧪 Main Aperçu complet data keys:")
        for cle in sorted(data.keys()):
            valeur = data[cle]
            if isinstance(valeur, dict):
                print(f"   {cle}: dict avec {len(valeur)} éléments")
            elif isinstance(valeur, list):
                print(f"   {cle}: list avec {len(valeur)} éléments")
            else:
                print(f"   {cle}: {type(valeur).__name__}")
        print("=" * 50)
    # FIN DU DEBUG


    # 🔹 Calcul des axes majeurs - à enlever si ça ne fonctionne pas
    try:
        # Utiliser la fonction preparer_donnees_analyse qui existe déjà
        data = preparer_donnees_analyse(data)
        axes_majeurs_str = data.get("axes_majeurs_str", "")
        print(f"✅ Axes majeurs calculés : {len(axes_majeurs_str)} caractères")
    except Exception as e:
        print(f"⚠️ Impossible de calculer les axes majeurs: {e}")
        axes_majeurs_str = ""
    # 🔹 Calcul des axes majeurs -fin


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
        points_forts=data['points_forts'],
        axes_majeurs_str=axes_majeurs_str,
        interceptions=data.get('interceptions', {})
    )



# -----------------------------------------------------------
# ROUTE /placements
# -----------------------------------------------------------
# 🔹 Objectif :
#   Affiche la page "tous_les_placements.html" avec tous les
#   éléments calculés du thème astral (planètes, maisons, aspects,
#   points forts, axes majeurs, interceptions...).
#
# 🔹 Fonctionnement :
#   1. Récupère les paramètres du thème depuis l’URL (GET).
#   2. Convertit éventuellement l’heure locale en UTC si tzid fourni.
#   3. Appelle calcul_theme() pour produire toutes les données.
#   4. Calcule et formate les axes majeurs avec preparer_donnees_analyse().
#   5. Passe toutes les données au template "tous_les_placements.html".
#
# 🔹 Utilité :
#   - Utile pour afficher une vue complète du thème sans passer par
#     l’analyse gratuite ou le Point Astral.
#   - Pratique pour visualiser ou déboguer les calculs bruts.
# -----------------------------------------------------------

@app.route("/placements", methods=["GET"])
def placements():
    nom = request.args.get("nom")
    date_naissance = request.args.get("date")           # ex: 1998-03-04
    heure_naissance = request.args.get("heure", "10:00")
    lieu_naissance = request.args.get("lieu", "Paris")

    if not nom or not date_naissance:
        return "Erreur : paramètres manquants dans l'URL.", 400

    # NEW: récup des coords/fuseau depuis l’URL si fournis
    tzid = request.args.get("tzid")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except ValueError:
        lat = lon = None

    # NEW: conversion locale -> UTC si on a tzid
    dt_utc = None
    if tzid and heure_naissance:
        try:
            dt_utc = local_to_utc(date_naissance, heure_naissance, tzid)
        except Exception as e:
            print(f"⚠️ GET /placements: conversion UTC échouée: {e}")

    print(f"➡️ Main GET /placements → lat={lat}, lon={lon}, tzid={tzid}, dt_utc={dt_utc}")

    # Appel du moteur de thème (on passe les overrides)
    data = calcul_theme(
        nom=nom,
        date_naissance=date_naissance,
        heure_naissance=heure_naissance,
        lieu_naissance=lieu_naissance,
        lat=lat, lon=lon,
        tzid=tzid,
        dt_naissance_utc=dt_utc
    )

# ✅ AJOUT : Calcul des axes majeurs
    try:
        data = preparer_donnees_analyse(data)
        axes_majeurs_str = data.get("axes_majeurs_str", "")
    except Exception as e:
        print(f"⚠️ Erreur calcul axes majeurs dans /placements: {e}")
        axes_majeurs_str = ""


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
        points_forts=data['points_forts'],
        axes_majeurs_str=axes_majeurs_str,
        interceptions=data.get('interceptions', {})
    )


# 📡 Route POST /json
# -------------------------------------------
# Reçoit les données de naissance depuis un formulaire
# (nom, date, heure, lieu) et retourne le thème natal
# calculé par calcul_theme() au format JSON.
# Utile pour un usage API ou pour des appels AJAX
# depuis le front-end, sans passer par un template HTML.

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
    version = form_data.get("version_analyse", "classique")
    
    if not form_data.get("consentement"):
        return "Consentement obligatoire", 400
    
    if type_analyse == "point_astral":
        if version == "blocs":
            return redirect("/analyse_point_astral_blocs", code=307)
        else:
            return redirect("/analyse_point_astral", code=307)
    


# 🚀 Point d’entrée principal (si exécution directe de main.py)
# -------------------------------------------
# - Récupère le port depuis la variable d’environnement PORT (par défaut 5050)
# - Affiche dans la console la liste des routes Flask disponibles (debug)
# - Lance l’application Flask en mode debug, accessible sur toutes les IP locales (0.0.0.0)
    


@app.route("/paiement/effectue")
def paiement_effectue():
    return render_template("paiement_effectue.html")






# 📝 Route POST /analyse_point_astral
# -------------------------------------------
# Cette route gère la génération complète d’un Point Astral payant.
# Étapes :
# 1. Vérifie le consentement obligatoire.
# 2. Récupère et valide les données de naissance envoyées via formulaire.
# 3. Stocke les infos personnelles en session pour affichage ou téléchargement ultérieur.
# 4. Calcule le thème natal via calcul_theme().
# 5. Vérifie la validité des données calculées.
# 6. Prépare et ajoute les "Axes Majeurs" au jeu de données.
# 7. Génère l’analyse complète via analyse_point_astral_avec_sections() et un appel LLM.
# 8. Sauvegarde l’analyse HTML en session pour un éventuel export PDF.
# 9. Retourne la page HTML point_astral_resultat.html avec l’analyse prête à afficher.
# En cas d’erreur → affiche la page erreur.html avec le message adapté.

# @app.route("/analyse_point_astral", methods=["POST"])
# def analyse_point_astral_route():
#     """Route pour générer l'analyse Point Astral"""
#     try:
#         form_data = request.form
        
#         # Vérification du consentement
#         if not form_data.get("consentement"):
#             return "Consentement obligatoire pour générer l'analyse", 400

#         # Récupération des données du formulaire
#         nom = form_data.get('nom', 'Analyse Anonyme')
#         date_naissance = form_data.get('date_naissance')
#         heure_naissance = form_data.get('heure_naissance')
#         lieu_naissance = form_data.get('lieu_naissance')

#         # Validation des données obligatoires
#         if not all([nom, date_naissance, heure_naissance, lieu_naissance]):
#             return "Toutes les informations de naissance sont requises", 400

#         print(f"🚀 Génération Point Astral pour {nom}")
        
#         # Stockage des informations en session
#         infos_personnelles = {
#             'nom': nom,
#             'date_naissance': date_naissance,
#             'heure_naissance': heure_naissance,
#             'lieu_naissance': lieu_naissance
#         }
#         session["infos_utilisateur"] = infos_personnelles

#         # Calcul du thème natal
#         print("📊 Calcul du thème natal...")
#         data = calcul_theme(nom, date_naissance, heure_naissance, lieu_naissance)
        
#         # Validation des données calculées
#         if not valider_donnees_avant_analyse(data):
#             return "Erreur dans le calcul du thème natal. Vérifiez vos données de naissance.", 400
        
#         # 🔴 AJOUT ICI : on enrichit data avec les Axes Majeurs (tri + bloc prêt)
#         data = preparer_donnees_analyse(data)
#         print("✅ Axes majeurs prêts pour LLM et template.")

        
        
        # Génération de l'analyse Point Astral par BLOC
@app.route("/analyse_point_astral", methods=["POST"])
def analyse_point_astral_route():
    """Route pour générer l'analyse Point Astral - VERSION BLOCS (5 prompts)"""
    try:
        form_data = request.form
        
        # Vérification du consentement
        if not form_data.get("consentement"):
            return "Consentement obligatoire pour générer l'analyse", 400

        # Récupération des données du formulaire
        infos_personnelles = {
            'nom': form_data.get('nom', 'Analyse Anonyme'),
            'date_naissance': form_data.get('date_naissance'),
            'heure_naissance': form_data.get('heure_naissance'),
            'lieu_naissance': form_data.get('lieu_naissance'),
            'email': form_data.get('email'),
            'gender': form_data.get('gender'),
            'lat': form_data.get('lat'),
            'lon': form_data.get('lon'),
            'tzid': form_data.get('tzid')
        }

        # Validation des données obligatoires
        if not all([infos_personnelles['nom'], infos_personnelles['date_naissance'], 
                   infos_personnelles['heure_naissance'], infos_personnelles['lieu_naissance']]):
            return "Toutes les informations de naissance sont requises", 400

        print(f"🚀 Main Génération Point Astral BLOCS pour {infos_personnelles['nom']}")
        
        # Stockage en session
        session["infos_utilisateur"] = infos_personnelles
        
        # Redirection vers la version blocs
        return redirect('/point_astral_blocs/complet')

    except Exception as e:
        print(f"❌ Main Erreur dans analyse_point_astral_route : {e}")
        import traceback
        traceback.print_exc()

        return render_template(
            'erreur.html',
            titre="Erreur dans l'analyse Point Astral",
            message=f"Une erreur s'est produite lors de la génération : {str(e)}",
            details="Veuillez vérifier vos données de naissance et réessayer."
        ), 500
    

# 📝 Route GET /telecharger_point_astral/<nom_fichier>
# ----------------------------------------------------
# Sert à télécharger le Point Astral sous forme de fichier PDF.
# Étapes :
# 1. Récupère le HTML de l’analyse en session (clé : "html_point_astral_<nom_fichier>").
# 2. Si absent → retourne une erreur 404.
# 3. Utilise html_to_pdf() pour convertir le HTML en PDF.
# 4. Sauvegarde le PDF dans "generated_pdfs/".
# 5. Envoie le fichier PDF en téléchargement au navigateur.
# En cas d’échec → retourne une erreur 500.


@app.route("/telecharger_point_astral/<nom_fichier>")
def telecharger_point_astral(nom_fichier):
    """Route pour télécharger le PDF du Point Astral"""
    try:
        # Récupérer le contenu HTML de la session
        html_content = session.get(f"html_point_astral_{nom_fichier}")
        
        if not html_content:
            return "Fichier non trouvé ou expiré", 404

        # Générer le PDF
        from utils.pdf_utils import html_to_pdf
        
        # Créer le répertoire de sortie si nécessaire
        import os
        output_dir = "generated_pdfs"
        os.makedirs(output_dir, exist_ok=True)
        
        pdf_path = os.path.join(output_dir, f"{nom_fichier}.pdf")
        
        # Conversion HTML vers PDF
        success = html_to_pdf(html_content, pdf_path)
        
        if not success or not os.path.exists(pdf_path):
            print(f"❌ Échec de la génération PDF : {pdf_path}")
            return "Erreur lors de la génération du PDF", 500

        print(f"✅ PDF généré : {pdf_path}")

        # Retourner le fichier PDF
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"{nom_fichier}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"❌ Erreur dans telecharger_point_astral : {e}")
        import traceback
        traceback.print_exc()
        return f"Erreur lors du téléchargement : {str(e)}", 500


# 📝 Route GET /apercu_point_astral/<nom_fichier>
# ------------------------------------------------
# Sert à afficher un aperçu HTML du Point Astral dans le navigateur.
# Étapes :
# 1. Récupère le HTML de l’analyse en session.
# 2. Si absent → retourne une erreur 404.
# 3. Retourne directement le HTML (pas de conversion en PDF).
# En cas d’échec → retourne une erreur 500.


@app.route("/apercu_point_astral/<nom_fichier>")
def apercu_point_astral(nom_fichier):
    """Route pour prévisualiser le Point Astral en HTML"""
    try:
        # Récupérer le contenu HTML de la session
        html_content = session.get(f"html_point_astral_{nom_fichier}")
        
        if not html_content:
            return "Aperçu non trouvé ou expiré", 404

        # Retourner directement le HTML pour prévisualisation
        return html_content

    except Exception as e:
        print(f"❌ Erreur dans apercu_point_astral : {e}")
        return f"Erreur lors de l'aperçu : {str(e)}", 500


atexit.register(cleanup_weaviate)

if __name__ == "__main__":
    # Ce bloc ne sera exécuté que quand tu lances localement avec "python main.py"
    port = int(os.environ.get("PORT", 5050))

    # ✅ N’afficher qu’une seule fois malgré le reloader Flask
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("\n📍 Liste des endpoints Flask enregistrés :")
        for rule in app.url_map.iter_rules():
            print(f"{rule.endpoint:35} ➝ {rule.methods} ➝ {rule.rule}")
    app.run(debug=True, host="0.0.0.0", port=port)


