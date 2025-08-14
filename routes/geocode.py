# ─────────────────────────────────────────────────────────────
# UTIL : tzid_from_latlon(lat, lon)
# Rôle : retourne l’identifiant de fuseau horaire IANA (ex. "Europe/Paris")
#        correspondant à des coordonnées (lat, lon).
# Entrées :
#   - lat (float) : latitude
#   - lon (float) : longitude
# Sortie :
#   - str | None : tzid si trouvé, sinon None (et log d’avertissement)
# Dépendances :
#   - TimezoneFinder (instancié en module-level : tf = TimezoneFinder())
# Utilisé par :
#   - /api/geocode (pour compléter chaque résultat avec son tzid)
#   - /api/reverse (pour renvoyer le tzid du point inversé)
# Remarques :
#   - Renvoie None si TimezoneFinder ne trouve rien (cas océans / zones limites).
#   - Gestion d’exception robuste avec logs.
# ─────────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify
import requests
from timezonefinder import TimezoneFinder

# Initialiser TimezoneFinder une seule fois
tf = TimezoneFinder()

def tzid_from_latlon(lat: float, lon: float) -> str | None:
    """Obtient le fuseau horaire IANA à partir des coordonnées"""
    try:
        tzid = tf.timezone_at(lat=lat, lng=lon)
        if tzid:
            return tzid
        else:
            print(f"⚠️ Aucun fuseau trouvé pour {lat}, {lon}")
            return None
    except Exception as e:
        print(f"❌ Erreur TimezoneFinder: {e}")
        return None

geocode_bp = Blueprint('geocode_bp', __name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org"

HEADERS = {
    "User-Agent": "LesFousDAstro/1.0 (contact: contact@lesfousdastro.fr)"
}

@geocode_bp.route("/api/geocode")
def api_geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "missing q"}), 400

    # Nominatim: recherche textuelle mondiale
    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,          
        "accept-language": "fr,en"  
    }
    
    try:
        r = requests.get(f"{NOMINATIM_URL}/search", params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        items = r.json()
    except requests.RequestException as e:
        print(f"❌ Erreur Nominatim: {e}")
        return jsonify({"error": "Erreur service géocodage"}), 500

    results = []
    for it in items:
        try:
            lat = float(it["lat"])
            lon = float(it["lon"])

            # Construire le label court : "Ville, Pays"
            address = it.get("address", {})
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
                or address.get("county")
                or it.get("display_name", "").split(",")[0]
                or q
            )
            country = address.get("country", "")
            short_label = f"{city}, {country}" if country else city

            # Obtenir le fuseau horaire
            tzid = tzid_from_latlon(lat, lon)

            results.append({
                "label": short_label,
                "lat": lat,
                "lon": lon,
                "tzid": tzid
            })
        except (ValueError, KeyError, TypeError) as e:
            print(f"⚠️ Erreur parsing résultat géocodage: {e}")
            continue

    return jsonify({"results": results})

@geocode_bp.route("/api/reverse")
def api_reverse():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid lat/lon"}), 400

    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "fr,en"
    }
    
    try:
        r = requests.get(f"{NOMINATIM_URL}/reverse", params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"❌ Erreur Nominatim reverse: {e}")
        return jsonify({"error": "Erreur service géocodage inverse"}), 500

    label = data.get("display_name") or f"{lat:.4f}, {lon:.4f}"
    tzid = tzid_from_latlon(lat, lon)  # ✅ Utiliser la fonction dédiée

    return jsonify({
        "label": label,
        "lat": lat,
        "lon": lon,
        "tzid": tzid
    })