import os
import csv
import uuid
from datetime import datetime
from flask import request
from utils.envoi_a_zapier import envoyer_a_zapier

def enregistrer_utilisateur_et_envoyer(form_data):
    # Chemin du CSV (à la racine du projet)
    chemin_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utilisateurs.csv')
    fichier_existe = os.path.exists(chemin_csv)

    # Générer un ID unique pour chaque soumission
    id_session = str(uuid.uuid4())

    # Horodatage actuel
    horodatage = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Champs classiques
    nom = form_data.get('nom', '').strip()
    email = form_data.get('email', '').strip()
    date_naissance = form_data.get('date_naissance', '').strip()
    heure_naissance = form_data.get('heure_naissance', '').strip()
    lieu_naissance = form_data.get('lieu_naissance', '').strip()

    # Type d’analyse (utile si on veut différencier gratuite / payante)
    analyse_type = form_data.get('type', 'gratuite')

    # Consentement
    consentement = 'oui' if form_data.get('consentement') else 'non'

    # Adresse IP (si contexte Flask)
    ip_address = request.remote_addr if request else "inconnue"

    # Origine (peut être un champ masqué dans le formulaire ou un paramètre GET futur)
    origine = form_data.get('origine', 'direct')

    # User-Agent (optionnel)
    user_agent = request.headers.get('User-Agent') if request else "inconnu"   

    # Écriture dans le fichier CSV
    try:
        with open(chemin_csv, mode='a', newline='', encoding='utf-8') as fichier:
            writer = csv.writer(fichier, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            if not fichier_existe:
                writer.writerow([
                    'id_session', 'horodatage', 
                    'nom', 'email', 'date_naissance', 'heure_naissance', 'lieu_naissance',
                    'analyse_type', 'consentement',
                    'ip', 'origine', 'user_agent'
                ])
            writer.writerow([
                id_session, horodatage, nom, email, date_naissance, heure_naissance, lieu_naissance,
                analyse_type, consentement,
                ip_address, origine, user_agent
            ])
    

        print("✅ Données utilisateur enregistrées.")
    except Exception as e:
        print("❌ Erreur CSV :", e)

    # Envoi à Zapier
    try:
        envoyer_a_zapier(form_data)
    except Exception as e:
        print("❌ Erreur Zapier :", e)