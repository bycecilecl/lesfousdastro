import weaviate
import os
from dotenv import load_dotenv

# 1. Charger les variables d’environnement depuis .env
load_dotenv(dotenv_path="clé_api.env")

# Configuration de base
WEAVIATE_URL = "https://r4y9czmvtxquxcyluvjkw.c0.europe-west3.gcp.weaviate.cloud"  # ou "http://localhost:8080" si local
API_KEY = "RElXSVNwemMyWmRTdkNPZV9odk0yQTlxeitPV1UwQmF4WGdKYm5BQnVwZHFkMWFtVmNCdHZyNDBiejZnPV92MjAwn"  # None si public

# 3. Créer un client Weaviate avec authentification OpenAI (si tu utilises OpenAI vectorizer)
client = weaviate.Client(
    url=WEAVIATE_URL,
    additional_headers={
        "X-OpenAI-Api-Key": OPENAI_API_KEY
    }
)

# Vérification de la connexion
if client.is_ready():
    print("✅ Connecté à Weaviate")
else:
    print("❌ Impossible de se connecter")

# Exemple : requête pour voir les 3 premières entrées de la classe "Astro_BDD"
result = client.query.get("Astro_BDD", ["astre", "donnee", "valeur", "texte"]).with_limit(3).do()
print("🔎 Résultat de la requête :")
for item in result['data']['Get']['Astro_BDD']:
    print(item)