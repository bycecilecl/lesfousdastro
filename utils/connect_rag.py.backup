# utils/connect_rag.py
import weaviate
import weaviate.classes as wvc
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="clé_api.env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_URL = "https://r4y9czmvtxquxcyluvjkw.c0.europe-west3.gcp.weaviate.cloud"

_client = None  # client global réutilisable

def get_weaviate_client():
    global _client
    
    # Vérifier si le client existe et est connecté
    if _client is None or not _client.is_ready():
        try:
            if _client is not None:
                _client.close()  # Fermer l'ancien client si nécessaire
        except:
            pass
        
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,
            auth_credentials=wvc.init.Auth.api_key(WEAVIATE_API_KEY),
            headers={"X-OpenAI-Api-Key": OPENAI_API_KEY}
        )
    
    return _client

def close_weaviate_client():
    """Fonction pour fermer proprement le client"""
    global _client
    if _client is not None:
        try:
            _client.close()
            _client = None
        except Exception as e:
            print(f"Erreur lors de la fermeture du client : {e}")
            _client = None