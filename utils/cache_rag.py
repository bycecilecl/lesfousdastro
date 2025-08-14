# utils/cache_rag.py
import hashlib
import json
import time
from typing import Dict, Optional, List
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées"""
    question: str
    reponse: str
    timestamp: float
    hash_key: str
    
class RAGCache:
    """Cache intelligent pour les requêtes RAG"""
    
    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self.memory_cache = {}  # Cache en mémoire pour la session
        
    def _generate_hash(self, question: str) -> str:
        """Génère un hash unique pour la question"""
        # Normalise la question pour éviter les doublons
        normalized = question.lower().strip().replace(" ", "_")
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _is_expired(self, timestamp: float) -> bool:
        """Vérifie si l'entrée a expiré"""
        return (time.time() - timestamp) > self.ttl_seconds
    
    def get(self, question: str) -> Optional[str]:
        """Récupère une réponse du cache"""
        hash_key = self._generate_hash(question)
        
        # Vérifier d'abord le cache mémoire
        if hash_key in self.memory_cache:
            entry = self.memory_cache[hash_key]
            if not self._is_expired(entry.timestamp):
                return entry.reponse
            else:
                del self.memory_cache[hash_key]
        
        # Vérifier le cache disque
        cache_file = self.cache_dir / f"{hash_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if not self._is_expired(data['timestamp']):
                    # Remettre en mémoire
                    entry = CacheEntry(**data)
                    self.memory_cache[hash_key] = entry
                    return entry.reponse
                else:
                    cache_file.unlink()  # Supprimer le fichier expiré
            except Exception as e:
                print(f"⚠️ Erreur lecture cache {hash_key}: {e}")
                
        return None
    
    def set(self, question: str, reponse: str) -> None:
        """Sauvegarde une réponse dans le cache"""
        hash_key = self._generate_hash(question)
        timestamp = time.time()
        
        entry = CacheEntry(
            question=question,
            reponse=reponse,
            timestamp=timestamp,
            hash_key=hash_key
        )
        
        # Cache mémoire
        self.memory_cache[hash_key] = entry
        
        # Cache disque
        cache_file = self.cache_dir / f"{hash_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'question': question,
                    'reponse': reponse,
                    'timestamp': timestamp,
                    'hash_key': hash_key
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde cache {hash_key}: {e}")
    
    def clear_expired(self) -> int:
        """Nettoie les entrées expirées et retourne le nombre supprimé"""
        cleared = 0
        
        # Nettoyer le cache mémoire
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if self._is_expired(entry.timestamp)
        ]
        for key in expired_keys:
            del self.memory_cache[key]
            cleared += 1
        
        # Nettoyer le cache disque
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if self._is_expired(data['timestamp']):
                        cache_file.unlink()
                        cleared += 1
            except Exception:
                cache_file.unlink()  # Supprimer les fichiers corrompus
                cleared += 1
                
        return cleared
    
    def get_stats(self) -> Dict:
        """Statistiques du cache"""
        disk_files = len(list(self.cache_dir.glob("*.json")))
        memory_entries = len(self.memory_cache)
        
        return {
            'memory_entries': memory_entries,
            'disk_files': disk_files,
            'cache_dir': str(self.cache_dir),
            'ttl_hours': self.ttl_seconds / 3600
        }


