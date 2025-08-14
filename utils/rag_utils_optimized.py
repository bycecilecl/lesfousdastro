# ─────────────────────────────────────────────────────────────────────────────
# FICHIER : rag_utils_optimized.py
# Rôle : Fournit toutes les fonctions liées au RAG (Recherche Augmentée par Graph)
#        en utilisant Weaviate + un système de cache local optimisé.
#        Permet de récupérer rapidement des interprétations astrologiques
#        à partir d'une base vectorisée (BddAstro) et de limiter les appels LLM.
#
# Fonctions principales :
#   - interroger_rag_original_weaviate(question)
#       → Requête hybride (vectorielle + mots-clés) sur la collection "BddAstro"
#         et renvoie les interprétations pertinentes (score > 0.6).
#   - interroger_rag_avec_cache(question, force_refresh=False)
#       → Version avec cache TTL (72h) + fallback LLM si aucun résultat Weaviate.
#   - recherche_exacte_weaviate(astre, donnee, valeur)
#       → Recherche précise d'une entrée correspondant aux 3 critères donnés.
#   - generer_corpus_rag_optimise(data_theme)
#       → Génère un corpus complet (occidental + védique) pour l'analyse
#         en regroupant les résultats RAG en un seul passage.
#   - optimiser_requetes_rag_par_batch(questions)
#       → Traite plusieurs requêtes en une seule connexion Weaviate (batch).
#
# Utilitaires :
#   - convertir_maison(maison_num) → Numéro de maison → chiffres romains.
#   - tester_rag_weaviate() → Lancer un test complet de connexion et recherche.
#   - cleanup_weaviate() → Fermer proprement les connexions à la fin du programme.
#   - nettoyer_cache_rag() → Supprime les entrées expirées du cache.
#   - backup_cache_rag() → Sauvegarde le cache complet sur disque.
#
# Points importants :
#   - Utilise `weaviate_manager` (connect_rag_optimized.py) pour gérer les connexions.
#   - Utilise `RAGCache` pour éviter les requêtes redondantes.
#   - Limite les requêtes par batch (max 10) pour éviter les timeouts.
#   - Filtre les résultats par score de pertinence (0.6 minimum).
#
# Où c’est utilisé :
#   - analyse_point_astral.py, decoupe_point_astral.py
#     pour enrichir les analyses avec des interprétations issues de la BddAstro.
# ─────────────────────────────────────────────────────────────────────────────

from utils.cache_rag import RAGCache
from utils.connect_rag_optimized import weaviate_manager
import weaviate.classes as wvc
from typing import Dict, List
import time

# Instance globale du cache
rag_cache = RAGCache(cache_dir="cache/rag", ttl_hours=72)  # 3 jours

def interroger_rag_original_weaviate(question: str) -> str:
    """
    Version Weaviate OPTIMISÉE qui réutilise les connexions
    """
    print(f"🔍 RAG Weaviate: {question[:50]}...")
    
    try:
        # CHANGEMENT : Utiliser le context manager au lieu de get_weaviate_client()
        with weaviate_manager.get_collection("BddAstro") as collection:
            # Recherche hybride (vectorielle + mot-clés)
            response = collection.query.hybrid(
                query=question,
                limit=3,  # Top 3 résultats
                alpha=0.7,  # 70% vectoriel, 30% mot-clés
                return_metadata=wvc.query.MetadataQuery(score=True)
            )
            
            if not response.objects:
                print(f"❌ Aucun résultat Weaviate pour: {question}")
                return ""
            
            # Assembler les résultats
            resultats = []
            for obj in response.objects:
                score = getattr(obj.metadata, 'score', 0)
                
                # Filtrer par score de confiance
                if score > 0.6:
                    # Adapter selon la structure de votre collection BddAstro
                    interpretation = obj.properties.get('INTERPRETATION', '') or obj.properties.get('interpretation', '')
                    texte = obj.properties.get('TEXTE', '') or obj.properties.get('texte', '')
                    
                    contenu = interpretation
                    if texte and str(texte) != 'nan' and texte.strip():
                        contenu += f"\n{texte}"
                    
                    if contenu.strip():
                        resultats.append(contenu)
                        print(f"  ✅ Score {score:.3f}: {len(contenu)} chars")
                    else:
                        print(f"  ❌ Score {score:.3f}: contenu vide")
                else:
                    print(f"  ❌ Score trop faible: {score:.3f}")
            
            if not resultats:
                print(f"❌ Aucun résultat avec score > 0.6")
                return ""
            
            reponse_finale = "\n\n".join(resultats)
            print(f"✅ RAG Weaviate: {len(resultats)} résultats, {len(reponse_finale)} chars")
            return reponse_finale
            
    except Exception as e:
        print(f"❌ Erreur RAG Weaviate: {e}")
        import traceback
        traceback.print_exc()
        return ""
    # CHANGEMENT : Plus de finally avec close_weaviate_client()

def interroger_rag_avec_cache(question: str, force_refresh: bool = False) -> str:
    """Version optimisée avec cache et fallback LLM"""
    from utils.openai_utils import interroger_llm

    # 1. Vérifie le cache
    if not force_refresh:
        cached_response = rag_cache.get(question)
        if cached_response:
            print(f"✅ Cache hit pour: {question[:50]}")
            return cached_response

    print(f"🔍 RAG - recherche Weaviate : {question[:50]}...")

    try:
        # 2. Essaye Weaviate (votre base vectorisée)
        reponse = interroger_rag_original_weaviate(question)

        if not reponse or reponse.strip() == "":
            raise ValueError("Pas de réponse RAG Weaviate")

        # 3. Mise en cache et retour
        rag_cache.set(question, reponse)
        print("💾 Réponse Weaviate enregistrée en cache")
        return reponse

    except Exception as e:
        print(f"❌ Erreur Weaviate : {e}")
        print("🤖 Tentative fallback LLM...")

        # 4. Fallback avec LLM
        try:
            fallback_prompt = f"Explique de manière synthétique en astrologie : {question}"
            reponse_llm = interroger_llm(fallback_prompt)

            if reponse_llm:
                rag_cache.set(question, reponse_llm)
                print("💡 Réponse LLM enregistrée")
                return reponse_llm
            else:
                return "❌ Aucune réponse générée par le LLM"

        except Exception as e_llm:
            return f"❌ Erreur RAG + LLM : {e_llm}"

def recherche_exacte_weaviate(astre: str, donnee: str, valeur: str) -> str:
    """Version optimisée de la recherche exacte"""
    print(f"🎯 Recherche exacte: {astre} {donnee} {valeur}")
    
    try:
        # CHANGEMENT : Utiliser le context manager
        with weaviate_manager.get_collection("BddAstro") as collection:
            # Utiliser recherche hybride au lieu de fetch_objects
            query = f"{astre} {donnee} {valeur}"
            response = collection.query.hybrid(query=query, limit=1)
            
            if response.objects:
                obj = response.objects[0]
                interpretation = obj.properties.get('interpretation', '')
                return interpretation
            
            return ""
            
    except Exception as e:
        print(f"❌ Erreur recherche: {e}")
        return ""
    # CHANGEMENT : Plus de finally avec close_weaviate_client()

def generer_corpus_rag_optimise(data_theme) -> str:
    """
    Version ULTRA-OPTIMISÉE qui utilise une seule connexion pour tout
    """
    print(f"\n🔍 === RAG WEAVIATE OPTIMISÉ ===")
    
    # 1. Préparer toutes les requêtes en une fois
    requetes_batch = []
    
    # Questions par planète/signe/maison
    for planete, placement in data_theme.get('planetes', {}).items():
        signe = placement.get('signe')
        maison = placement.get('maison')
        
        if signe:
            requetes_batch.append(f"{planete} en {signe} signification")
        if maison:
            maison_rom = convertir_maison(maison)
            requetes_batch.append(f"{planete} en maison {maison} interprétation")
    
    # Aspects importants seulement (limité à 5)
    for aspect in data_theme.get('aspects', [])[:5]:
        if aspect.get('orbe', 10) <= 6:  # Aspects serrés seulement
            requetes_batch.append(f"{aspect['planete1']} {aspect['aspect']} {aspect['planete2']} aspect")
    
    # Questions contextuelles (réduites)
    requetes_batch.extend([
        "développement personnel astrologie",
        "psychologie astrologique profonde"
    ])
    
    print(f"📋 {len(requetes_batch)} requêtes préparées")
    
    # 2. CHANGEMENT MAJEUR : Traitement en batch avec UNE SEULE connexion
    resultats = []
    
    try:
        with weaviate_manager.get_collection("BddAstro") as collection:
            print("🔥 Traitement batch avec connexion unique...")
            
            for i, question in enumerate(requetes_batch[:10]):  # Limiter à 10
                try:
                    # Vérifier cache d'abord
                    cached = rag_cache.get(question)
                    if cached:
                        resultats.append(cached[:500])  # Limiter la taille
                        print(f"  💾 Cache hit {i+1}/{len(requetes_batch[:10])}")
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
                                contenu_limite = interpretation[:500]
                                resultats.append(contenu_limite)
                                rag_cache.set(question, interpretation)
                                print(f"  ✅ {i+1}/{len(requetes_batch[:10])}: score {score:.3f}, {len(interpretation)} chars")
                        else:
                            print(f"  ❌ {i+1}/{len(requetes_batch[:10])}: score trop faible {score:.3f}")
                    else:
                        print(f"  ❌ {i+1}/{len(requetes_batch[:10])}: aucun résultat")
                    
                    # Petite pause pour éviter la surcharge
                    if i % 3 == 0 and i > 0:
                        time.sleep(0.1)
                        
                except Exception as e:
                    print(f"  ❌ Erreur requête {i+1}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ Erreur batch processing: {e}")
        import traceback
        traceback.print_exc()
        return ""
    
    # 3. Assembler le corpus final
    corpus_final = "\n\n".join(resultats)
    print(f"✅ Corpus optimisé: {len(corpus_final)} caractères (de {len(resultats)} résultats)")
    
    return corpus_final[:8000]  # Limiter à 8k

def convertir_maison(maison_num):
    """Convertit numéro de maison en chiffres romains"""
    conversion = {
        1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
        7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"
    }
    try:
        return conversion.get(int(maison_num), str(maison_num))
    except:
        return str(maison_num)

def optimiser_requetes_rag_par_batch(questions: List[str]) -> Dict[str, str]:
    """Version batch ULTRA-OPTIMISÉE avec une seule connexion"""
    resultats = {}
    
    # Identifier les requêtes déjà en cache
    nouvelles_requetes = []
    for question in questions:
        if len(question) < 50:  # Skip les questions trop courtes
            continue
        cached = rag_cache.get(question)
        if cached:
            resultats[question] = cached
        else:
            nouvelles_requetes.append(question)
    
    print(f"📊 Cache: {len(resultats)} hits, {len(nouvelles_requetes)} nouvelles requêtes")
    
    # CHANGEMENT : Traiter les nouvelles requêtes avec UNE connexion au lieu de ThreadPoolExecutor
    if nouvelles_requetes:
        try:
            with weaviate_manager.get_collection("BddAstro") as collection:
                for question in nouvelles_requetes[:5]:  # Limiter à 5 pour éviter timeout
                    try:
                        response = collection.query.hybrid(query=question, limit=1)
                        if response.objects:
                            obj = response.objects[0]
                            interpretation = obj.properties.get('interpretation', '')
                            if interpretation:
                                resultats[question] = interpretation
                                rag_cache.set(question, interpretation)
                                print(f"  ✅ Nouvelle requête traitée: {question[:30]}")
                    except Exception as e:
                        print(f"❌ Erreur pour {question[:30]}: {e}")
                        resultats[question] = f"❌ Erreur: {e}"
                        continue
        except Exception as e:
            print(f"❌ Erreur batch processing: {e}")
    
    return resultats

# Fonction de test optimisée
def tester_rag_weaviate():
    """Test pour vérifier que Weaviate fonctionne avec la nouvelle approche"""
    print("🧪 === TEST RAG WEAVIATE OPTIMISÉ ===")
    
    # Test recherche exacte
    print("\n1️⃣ Test recherche exacte...")
    resultat = recherche_exacte_weaviate("SOLEIL", "SIGNE", "BALANCE")
    print(f"Résultat: {len(resultat)} chars")
    if resultat:
        print(f"Début: {resultat[:100]}...")
    
    # Test recherche vectorielle
    print("\n2️⃣ Test recherche vectorielle...")
    resultat2 = interroger_rag_avec_cache("Soleil en Balance personnalité")
    print(f"Résultat: {len(resultat2)} chars")
    
    print("✅ Tests terminés!")

# NOUVEAU : Fonction de nettoyage à appeler à la fin de l'application
def cleanup_weaviate():
    """À appeler lors de l'arrêt de l'application"""
    weaviate_manager.close()

# Pour compatibilité avec votre code existant
interroger_rag = interroger_rag_avec_cache

# Fonctions utilitaires pour maintenance (inchangées)
def nettoyer_cache_rag():
    """Nettoie le cache RAG"""
    cleared = rag_cache.clear_expired()
    stats = rag_cache.get_stats()
    print(f"🧹 Cache nettoyé: {cleared} entrées supprimées")
    print(f"📊 Stats: {stats}")
    return stats

def backup_cache_rag(backup_path: str = "backups/rag_cache.json"):
    """Sauvegarde le cache complet"""
    from pathlib import Path
    import shutil
    
    backup_dir = Path(backup_path).parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if rag_cache.cache_dir.exists():
            shutil.copytree(rag_cache.cache_dir, backup_dir / "rag_cache", dirs_exist_ok=True)
            print(f"💾 Cache sauvegardé vers {backup_path}")
            return True
    except Exception as e:
        print(f"❌ Erreur backup cache: {e}")
        return False