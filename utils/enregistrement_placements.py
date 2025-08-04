import os
import csv
from datetime import datetime
import uuid

def enregistrer_placements_utilisateur(data, infos_personnelles):
    chemin_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'placements.csv')
    fichier_existe = os.path.exists(chemin_csv)

    planetes = data.get("planetes", {})
    ascendant = data.get("ascendant", {})
    maisons = data.get("maisons", {})
    maitre_ascendant = data.get("maitre_ascendant", {})

    def get_info(nom_planete):
        planete = planetes.get(nom_planete, {})
        return planete.get("signe", "inconnu"), planete.get("maison", "inconnu")

    # ID + horodatage
    id_session = str(uuid.uuid4())
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Structuration des données
    donnees = {
        "id_session": id_session,
        "horodatage": horodatage,
        "nom": infos_personnelles.get("nom", ""),
        "date_naissance": infos_personnelles.get("date_naissance", ""),
        "heure_naissance": infos_personnelles.get("heure_naissance", ""),
        "lieu_naissance": infos_personnelles.get("lieu_naissance", ""),

        "ascendant_signe": ascendant.get("signe", "inconnu"),

        "soleil_signe": get_info("Soleil")[0],
        "soleil_maison": get_info("Soleil")[1],
        "lune_signe": get_info("Lune")[0],
        "lune_maison": get_info("Lune")[1],
        "mercure_signe": get_info("Mercure")[0],
        "mercure_maison": get_info("Mercure")[1],
        "venus_signe": get_info("Vénus")[0],
        "venus_maison": get_info("Vénus")[1],
        "mars_signe": get_info("Mars")[0],
        "mars_maison": get_info("Mars")[1],
        "jupiter_signe": get_info("Jupiter")[0],
        "jupiter_maison": get_info("Jupiter")[1],
        "saturne_signe": get_info("Saturne")[0],
        "saturne_maison": get_info("Saturne")[1],
        "uranus_signe": get_info("Uranus")[0],
        "uranus_maison": get_info("Uranus")[1],
        "neptune_signe": get_info("Neptune")[0],
        "neptune_maison": get_info("Neptune")[1],
        "pluton_signe": get_info("Pluton")[0],
        "pluton_maison": get_info("Pluton")[1],
        "lilith_signe": get_info("Lune Noire")[0],
        "lilith_maison": get_info("Lune Noire")[1],

        "maitre_ascendant": maitre_ascendant.get("nom", "inconnu"),
        "maitre_asc_signe": maitre_ascendant.get("signe", "inconnu"),
        "maitre_asc_maison": maitre_ascendant.get("maison", "inconnu")
    }

    try:
        with open(chemin_csv, mode='a', newline='', encoding='utf-8') as fichier:
            writer = csv.DictWriter(fichier, fieldnames=donnees.keys(), delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            if not fichier_existe:
                writer.writeheader()
            writer.writerow(donnees)
        print("✅ Placements astrologiques enregistrés.")
    except Exception as e:
        print("❌ Erreur lors de l'enregistrement des placements :", e)