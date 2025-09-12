# ────────────────────────────────────────────────
# 📡 RAG WEAVIATE – VERSION OPTIMISÉE
# Ces fichiers gèrent la connexion à Weaviate et les recherches RAG
# de manière performante (réutilisation des connexions, cache local, batch).
#
# FICHIER : utils/connect_rag_optimized.py
#
# 1. WeaviateManager (classe)
#    ➜ Singleton gérant :
#        - Ouverture/fermeture optimisée des connexions
#        - Pooling (réutilisation d’un client existant)
#        - Timeout après 5 minutes d’inactivité
#    ➜ Fournit :
#        - get_client() : récupère le client Weaviate
#        - get_collection(name) : context manager pour travailler sur une collection
#        - close() : fermeture propre
#
# 2. Fonctions utilitaires
#    ➜ get_weaviate_client() : compatibilité avec ancien code
#    ➜ close_weaviate_client() : ne ferme plus la connexion à chaque appel
#    ➜ close_all_connections() : fermeture définitive de toutes les connexions
#
# ────────────────────────────────────────────────
# FICHIER : utils/rag_utils_optimized.py
#
# 1. interroger_rag_original_weaviate_optimized(question)
#    ➜ Effectue une recherche hybride (vecteur + mots-clés)
#      sur la collection "BddAstro".
#    ➜ Limite à 3 résultats, filtre par score > 0.6,
#      assemble et retourne le texte trouvé.
#
# 2. recherche_exacte_weaviate_optimized(astre, donnee, valeur)
#    ➜ Recherche exacte (hybride mais ciblée) pour un astre précis.
#
# 3. generer_corpus_rag_optimise_v2(data_theme)
#    ➜ Construit un corpus RAG à partir :
#         - des positions planétaires (planète + signe, planète + maison)
#         - des aspects majeurs (≤ 6° d’orbe)
#         - requêtes contextuelles ("psychologie astrologique profonde", etc.)
#      Exécute en batch avec une seule connexion.
#      Limite à 10 requêtes, utilise un cache TTL 72h.
#
# 4. optimiser_requetes_rag_par_batch_v2(questions)
#    ➜ Exécute un lot de requêtes RAG optimisé :
#         - vérifie d’abord le cache
#         - exécute seulement les nouvelles requêtes
#         - limite à 5 requêtes par batch
#
# 5. cleanup_weaviate()
#    ➜ Ferme toutes les connexions Weaviate (à appeler en fin d’app).
#
# ALIAS DE COMPATIBILITÉ :
#    interroger_rag → interroger_rag_original_weaviate_optimized
#    generer_corpus_rag_optimise → generer_corpus_rag_optimise_v2
# ────────────────────────────────────────────────

import weaviate
import weaviate.classes as wvc
import os
import threading
import time
from contextlib import contextmanager
from typing import Optional
from weaviate.auth import AuthApiKey
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv()) 

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_COLLECTION = os.getenv("WEAVIATE_COLLECTION") or "Astro_BDD"
WEAVIATE_TENANT = os.getenv("WEAVIATE_TENANT") or None

if not WEAVIATE_URL:
    raise RuntimeError("❌ WEAVIATE_URL manquant dans le fichier .env")

print(f"🔗 Weaviate URL utilisé: {WEAVIATE_URL}")
print(f"📚 Collection: {WEAVIATE_COLLECTION} | Tenant: {WEAVIATE_TENANT or '(none)'}")

class WeaviateManager:
    """Gestionnaire singleton pour les connexions Weaviate avec pooling"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._client = None
        self._last_used = 0
        self._connection_timeout = 300  # 5 minutes
        self._lock = threading.Lock()
        self._initialized = True
        print("🔧 WeaviateManager initialisé")
    
    def get_client(self):
        """Récupère un client Weaviate réutilisable"""
        with self._lock:
            current_time = time.time()
            
            # Vérifier si on a besoin d'une nouvelle connexion
            if (self._client is None or 
                current_time - self._last_used > self._connection_timeout):
                
                # Fermer l'ancienne connexion si elle existe
                if self._client is not None:
                    try:
                        self._client.close()
                        print("🔌 Ancienne connexion fermée")
                    except Exception as e:
                        print(f"⚠️ Erreur fermeture: {e}")
                
                # Créer nouvelle connexion
                try:
                    self._client = weaviate.connect_to_weaviate_cloud(
                        cluster_url=WEAVIATE_URL,
                        auth_credentials=AuthApiKey(WEAVIATE_API_KEY),
                        headers={"X-OpenAI-Api-Key": OPENAI_API_KEY},
                        skip_init_checks=True,  # ← évite l'appel /v1/meta (source de ton 404)
                    )
                    # petit "ping" sain via /v1/schema
                    try:
                        _ = self._client.collections.list_all()
                        print("✅ Nouvelle connexion Weaviate établie (schema OK)")
                    except Exception as e:
                        raise RuntimeError(f"Weaviate not ready: {e}")
                except Exception as e:
                    print(f"❌ Erreur connexion Weaviate: {e}")
                    raise

                self._last_used = current_time
                return self._client
                    
    @contextmanager
    
    def get_collection(self, collection_name: str | None = None):
        client = self.get_client()
        target = collection_name or WEAVIATE_COLLECTION

        # list_all() retourne List[str] en v4
        available = client.collections.list_all()  # <-- liste de noms (str)
        if target not in available:
            print("❌ Collection introuvable:", target)
            print("📃 Collections disponibles:", available)
            raise RuntimeError(f"Collection '{target}' absente du schema Weaviate.")


        coll = client.collections.get(target)

        # If multi-tenancy enabled, bind tenant
        if WEAVIATE_TENANT:
            coll = coll.with_tenant(WEAVIATE_TENANT)

        try:
            yield coll
        finally:
            pass  # keep pooled connection open
    
    def close(self):
        """Ferme proprement toutes les connexions"""
        with self._lock:
            if self._client is not None:
                try:
                    self._client.close()
                    print("🔌 Connexion Weaviate fermée définitivement")
                except Exception as e:
                    print(f"❌ Erreur fermeture: {e}")
                finally:
                    self._client = None

# Instance globale
weaviate_manager = WeaviateManager()

def get_weaviate_client():
    """Fonction de compatibilité avec l'ancien code"""
    return weaviate_manager.get_client()

def close_weaviate_client():
    """Fonction de compatibilité - ne ferme plus systématiquement"""
    # On ne ferme plus à chaque appel, juste un message
    print("📌 Connexion maintenue (optimisation)")

def close_all_connections():
    """Ferme définitivement toutes les connexions"""
    weaviate_manager.close()


# utils/rag_utils_optimized.py (version optimisée)

from utils.cache_rag import RAGCache
from utils.connect_rag_optimized import weaviate_manager
import weaviate.classes as wvc
from typing import Dict, List
import concurrent.futures
import time

# Instance globale du cache
rag_cache = RAGCache(cache_dir="cache/rag", ttl_hours=72)

def interroger_rag_original_weaviate_optimized(question: str) -> str:
    """Version optimisée qui réutilise les connexions"""
    print(f"🔍 Connect_Rag_Opt_RAG Weaviate: {question[:50]}...")
    
    try:
        with weaviate_manager.get_collection("BddAstro") as collection:
            # Recherche hybride (vectorielle + mot-clés)
            response = collection.query.hybrid(
                query=question,
                limit=3,
                alpha=0.7,
                return_metadata=wvc.query.MetadataQuery(score=True)
            )
            
            if not response.objects:
                print(f"❌ Aucun résultat pour: {question}")
                return ""
            
            # Assembler les résultats
            resultats = []
            for obj in response.objects:
                score = getattr(obj.metadata, 'score', 0)
                
                if score > 0.6:
                    interpretation = obj.properties.get('INTERPRETATION', '') or obj.properties.get('interpretation', '')
                    texte = obj.properties.get('TEXTE', '') or obj.properties.get('texte', '')
                    
                    contenu = interpretation
                    if texte and str(texte) != 'nan' and texte.strip():
                        contenu += f"\n{texte}"
                    
                    if contenu.strip():
                        resultats.append(contenu)
                        print(f"  ✅ Score {score:.3f}: {len(contenu)} chars")
            
            if not resultats:
                return ""
            
            reponse_finale = "\n\n".join(resultats)
            print(f"✅ Connect_Rag_Opt_RAG / RAG Weaviate: {len(resultats)} résultats, {len(reponse_finale)} chars")
            return reponse_finale
            
    except Exception as e:
        print(f"❌ Connect_Rag_Opt_RAG / Erreur RAG Weaviate: {e}")
        return ""

def recherche_exacte_weaviate_optimized(astre: str, donnee: str, valeur: str) -> str:
    """Version optimisée de la recherche exacte"""
    try:
        with weaviate_manager.get_collection("BddAstro") as collection:
            query = f"{astre} {donnee} {valeur}"
            response = collection.query.hybrid(query=query, limit=1)
            
            if response.objects:
                obj = response.objects[0]
                interpretation = obj.properties.get('interpretation', '')
                return interpretation
            
            return ""
            
    except Exception as e:
        print(f"❌ Connect_Rag_Opt_RAG / Erreur recherche: {e}")
        return ""

def generer_corpus_rag_optimise_v2(data_theme) -> str:
    """Version ultra-optimisée qui minimise les connexions"""
    print(f"\n Connect_Rag_Opt_RAG 🔍 === RAG WEAVIATE OPTIMISÉ ===")
    
    # 1. Préparer toutes les requêtes en une fois
    requetes_batch = []
    
    # Questions par planète/signe/maison
    for planete, placement in data_theme.get('planetes', {}).items():
        signe = placement.get('signe')
        maison = placement.get('maison')
        
        if signe:
            requetes_batch.append(f"{planete} en {signe} signification")
        if maison:
            requetes_batch.append(f"{planete} en maison {maison} interprétation")
    
    # Aspects importants seulement
    for aspect in data_theme.get('aspects', [])[:5]:  # Limiter à 5 aspects
        if aspect.get('orbe', 10) <= 6:
            requetes_batch.append(f"{aspect['planete1']} {aspect['aspect']} {aspect['planete2']} aspect")
    
    # Questions contextuelles
    requetes_batch.extend([
        "développement personnel astrologie",
        "psychologie astrologique profonde"
    ])
    
    print(f"📋 Connect_Rag_Opt_RAG {len(requetes_batch)} requêtes préparées")
    
    # 2. Traitement en batch avec UNE SEULE connexion
    resultats = []
    
    try:
        with weaviate_manager.get_collection("BddAstro") as collection:
            print("🔥 Connect_Rag_Opt_RAG Traitement batch avec connexion unique...")
            
            for i, question in enumerate(requetes_batch[:10]):  # Limiter à 10
                try:
                    # Vérifier cache d'abord
                    cached = rag_cache.get(question)
                    if cached:
                        resultats.append(cached)
                        continue
                    
                    # Recherche Weaviate
                    response = collection.query.hybrid(
                        query=question,
                        limit=1,
                        alpha=0.7,
                        return_metadata=wvc.query.MetadataQuery(score=True)
                    )
                    
                    if response.objects:
                        obj = response.objects[0]
                        score = getattr(obj.metadata, 'score', 0)
                        
                        if score > 0.6:
                            interpretation = obj.properties.get('INTERPRETATION', '') or obj.properties.get('interpretation', '')
                            if interpretation and len(interpretation) > 50:
                                resultats.append(interpretation[:500])
                                rag_cache.set(question, interpretation)
                                print(f"  ✅ {i+1}/{len(requetes_batch[:10])}: {len(interpretation)} chars")
                    
                    # Petite pause pour éviter la surcharge
                    if i % 3 == 0:
                        time.sleep(0.1)
                        
                except Exception as e:
                    print(f"  ❌ Erreur requête {i+1}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ Connect_Rag_Opt_RAG Erreur batch processing: {e}")
        return ""
    
    # 3. Assembler le corpus final
    corpus_final = "\n\n".join(resultats)
    print(f"✅ Connect_Rag_Opt_RAG Corpus optimisé: {len(corpus_final)} caractères")
    
    return corpus_final[:8000]

def optimiser_requetes_rag_par_batch_v2(questions: List[str]) -> Dict[str, str]:
    """Version batch ultra-optimisée"""
    resultats = {}
    
    # Vérifier le cache en premier
    nouvelles_requetes = []
    for question in questions:
        if len(question) < 50:
            continue
        cached = rag_cache.get(question)
        if cached:
            resultats[question] = cached
        else:
            nouvelles_requetes.append(question)
    
    print(f"📊 Connect_Rag_Opt_RAG Cache: {len(resultats)} hits, {len(nouvelles_requetes)} nouvelles")
    
    # Traiter les nouvelles requêtes avec UNE connexion
    if nouvelles_requetes:
        try:
            with weaviate_manager.get_collection("Astro_BDD") as collection:
                for question in nouvelles_requetes[:5]:  # Limiter à 5
                    try:
                        response = collection.query.hybrid(query=question, limit=1)
                        if response.objects:
                            obj = response.objects[0]
                            interpretation = obj.properties.get('interpretation', '')
                            if interpretation:
                                resultats[question] = interpretation
                                rag_cache.set(question, interpretation)
                    except Exception as e:
                        print(f"❌ Connect_Rag_Opt_RAG Erreur pour {question[:30]}: {e}")
                        continue
        except Exception as e:
            print(f"❌ Connect_Rag_Opt_RAG Erreur batch: {e}")
    
    return resultats

# Fonction de nettoyage à appeler à la fin de l'application
def cleanup_weaviate():
    """À appeler lors de l'arrêt de l'application"""
    from utils.connect_rag_optimized import close_all_connections
    close_all_connections()

# Fonctions de compatibilité
interroger_rag = interroger_rag_original_weaviate_optimized
generer_corpus_rag_optimise = generer_corpus_rag_optimise_v2