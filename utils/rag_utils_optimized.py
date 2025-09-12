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
import time
from typing import List, Dict, Iterable
from collections import defaultdict

# Instance globale du cache
rag_cache = RAGCache(cache_dir="cache/rag", ttl_hours=72)  # 3 jours

def interroger_rag_original_weaviate(question: str) -> str:
    """
    Version Weaviate OPTIMISÉE qui réutilise les connexions
    """
    print(f"🔍 RAG Weaviate: {question[:50]}...")
    try:
        # Utilise la collection par défaut du manager (issue du .env)
        with weaviate_manager.get_collection() as collection:
            response = collection.query.hybrid(
                query=question,
                limit=3,
                alpha=0.7,
                return_metadata=wvc.query.MetadataQuery(score=True),
            )
            if not response.objects:
                print(f"❌ Aucun résultat Weaviate pour: {question}")
                return ""

            resultats = []
            for obj in response.objects:
                score = getattr(obj.metadata, "score", 0.0) or 0.0
                if score <= 0.6:
                    print(f"  ❌ Score trop faible: {score:.3f}")
                    continue

                props = obj.properties or {}
                props_l = {str(k).lower(): v for k, v in props.items()}
                interpretation = (
                    props_l.get("interpretation")
                    or props.get("INTERPRETATION")
                    or props.get("iNTERPRETATION")
                )
                texte = (
                    props_l.get("texte")
                    or props.get("TEXTE")
                )

                contenu = ""
                if interpretation and str(interpretation).strip():
                    contenu = str(interpretation).strip()
                if texte and str(texte).strip().lower() != "nan":
                    contenu = (contenu + "\n" + str(texte).strip()).strip()

                if contenu:
                    resultats.append(contenu)
                    print(f"  ✅ Score {score:.3f}: {len(contenu)} chars")
                else:
                    print(f"  ❌ Score {score:.3f}: contenu vide")

            if not resultats:
                print("❌ Aucun résultat avec score > 0.6")
                return ""

            reponse_finale = "\n\n".join(resultats)
            print(f"✅ RAG Weaviate: {len(resultats)} résultats, {len(reponse_finale)} chars")
            return reponse_finale

    except Exception as e:
        print(f"❌ Erreur RAG Weaviate: {e}")
        import traceback; traceback.print_exc()
        return ""

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
        with weaviate_manager.get_collection() as collection:
            query = f"{astre} {donnee} {valeur}"
            response = collection.query.hybrid(query=query, limit=1,
                                               return_metadata=wvc.query.MetadataQuery(score=True))
            if not response.objects:
                return ""

            obj = response.objects[0]
            score = getattr(obj.metadata, "score", 0.0) or 0.0
            if score <= 0.6:
                print(f"  ❌ Score trop faible: {score:.3f}")
                return ""

            props = obj.properties or {}
            props_l = {str(k).lower(): v for k, v in props.items()}
            interpretation = (
                props_l.get("interpretation")
                or props.get("INTERPRETATION")
                or props.get("iNTERPRETATION")
            )
            texte = (
                props_l.get("texte")
                or props.get("TEXTE")
            )

            contenu = ""
            if interpretation and str(interpretation).strip():
                contenu = str(interpretation).strip()
            if texte and str(texte).strip().lower() != "nan":
                contenu = (contenu + "\n" + str(texte).strip()).strip()

            print(f"  ✅ Résultat exact: score {score:.3f}, {len(contenu)} chars")
            return contenu

    except Exception as e:
        print(f"❌ Erreur recherche: {e}")
        return ""

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
        try:
            orbe = float(str(aspect.get('orbe', 10)).replace(",", "."))
        except Exception:
            orbe = 10
        if orbe <= 6:
            requetes_batch.append(
                f"{aspect.get('planete1')} {aspect.get('aspect')} {aspect.get('planete2')} aspect"
            )
    
    # Questions contextuelles (réduites)
    requetes_batch.extend([
        "développement personnel astrologie",
        "psychologie astrologique profonde"
    ])
    
    print(f"📋 {len(requetes_batch)} requêtes préparées")
    
    # 2) Traitement en batch avec UNE SEULE connexion
    resultats = []
    try:
        with weaviate_manager.get_collection() as collection:
            print("🔥 Traitement batch avec connexion unique...")

            for i, question in enumerate(requetes_batch[:10], start=1):  # Limiter à 10
                # 1) Cache d'abord
                cached = rag_cache.get(question)
                if cached:
                    resultats.append(cached[:500])  # limiter la taille
                    print(f"  💾 Cache hit {i}/{min(10, len(requetes_batch))}")
                    continue

                # 2) Recherche hybride
                try:
                    resp = collection.query.hybrid(
                        query=question,
                        limit=1,
                        alpha=0.5,
                        return_metadata=wvc.query.MetadataQuery(score=True)
                    )
                except Exception as e:
                    print(f"  ❌ Erreur requête {i}: {e}")
                    continue

                if not resp.objects:
                    print(f"  ❌ {i}: aucun résultat")
                    continue

                obj = resp.objects[0]
                score = (getattr(obj.metadata, "score", 0.0) or 0.0)
                if score <= 0.6:
                    print(f"  ❌ {i}: score trop faible {score:.3f}")
                    continue

                # 3) Lecture des propriétés avec tolérance de casse
                props = obj.properties or {}
                props_l = {str(k).lower(): v for k, v in props.items()}

                interpretation = (
                    props_l.get("interpretation")
                    or props.get("INTERPRETATION")
                    or props.get("iNTERPRETATION")
                )
                texte = (
                    props_l.get("texte")
                    or props.get("TEXTE")
                )

                if interpretation and len(str(interpretation).strip()) > 50:
                    snippet = str(interpretation).strip()[:500]
                    if texte and str(texte).strip().lower() != "nan":
                        snippet = (snippet + "\n" + str(texte).strip()[:500]).strip()

                    resultats.append(snippet)
                    rag_cache.set(question, str(interpretation).strip())
                    print(f"  ✅ {i}: score {score:.3f}, kept {len(snippet)} chars")
                else:
                    print(f"  ❌ {i}: interprétation vide/courte")

                # 4) Micro pause pour éviter surcharge
                if i % 3 == 0:
                    time.sleep(0.1)

    except Exception as e:
        print(f"❌ Erreur batch processing: {e}")
        import traceback; traceback.print_exc()
        return ""

    # 3. Assembler le corpus final
    corpus_final = "\n\n".join(resultats)
    print(f"✅ Corpus optimisé: {len(corpus_final)} caractères (de {len(resultats)} résultats)")
    
    return corpus_final[:8000]  # Limiter à 8k


def _cap_snippet(txt: str, max_chars: int = 350) -> str:
    return (txt or "")[:max_chars].rsplit("\n", 1)[0]

def _dedup(snips: Iterable[Dict]) -> List[Dict]:
    seen = set(); out = []
    for s in snips:
        key = (s.get("texte","").strip().lower(), s.get("source","").lower())
        if key in seen: 
            continue
        seen.add(key); out.append(s)
    return out

def _mmr_diversify(snips: List[Dict], k: int = 8) -> List[Dict]:
    """Heuristique simple pour éviter les doublons très proches (placeholder)."""
    # on triche : on prend un sur deux après tri score, ça suffit souvent
    snips_sorted = sorted(snips, key=lambda x: x.get("score", 0), reverse=True)
    return snips_sorted[:k] if k <= 2 else snips_sorted[0:1] + snips_sorted[2:k+1:2]

def selectionner_snippets_par_topic(
    snippets: List[Dict],
    top_k_par_topic: int = 6,
    min_score: float = 0.35,
    max_chars_par_snippet: int = 350
) -> Dict[str, List[Dict]]:
    """
    Regroupe par 'topic' (ex: 'Ascendant','Soleil','Lune','MaîtreAsc', etc.)
    Garde top‑k par topic, score >= min_score, dédupliqués et raccourcis.
    Attendu par snippet: {'texte': str, 'source': str, 'score': float, 'topic': str}
    """
    buckets = defaultdict(list)
    for s in snippets:
        if s.get("score", 0) < min_score:
            continue
        topic = s.get("topic") or "general"
        buckets[topic].append(s)

    out = {}
    for topic, lst in buckets.items():
        lst = _dedup(lst)
        lst = sorted(lst, key=lambda x: x.get("score", 0), reverse=True)
        lst = _mmr_diversify(lst, k=top_k_par_topic)
        for s in lst:
            s["texte"] = _cap_snippet(s.get("texte",""), max_chars_par_snippet)
        out[topic] = lst
    return out

def construire_rag_digest(par_topic: Dict[str, List[Dict]], max_chars_total: int = 1600) -> str:
    """
    Concatène les snippets par topic en un texte court.
    - Garde les en-têtes [Topic]
    - Une ligne par snippet: "- texte (src:..., score:..)"
    - Tronque proprement à max_chars_total
    """
    blocs = []
    for topic, lst in par_topic.items():
        if not lst:
            continue
        blocs.append(f"[{topic}]")
        for s in lst:
            src = s.get("source", "")
            score = round(s.get("score", 0), 2)
            t = s.get("texte", "").replace("\n", " ").strip()
            if not t:
                continue
            blocs.append(f"- {t} (src:{src}, score:{score})")

    if not blocs:
        return ""

    joined = "\n".join(blocs)
    # coupe proprement
    return joined[:max_chars_total].rsplit("\n", 1)[0]


def digest_pour_bloc(par_topic: Dict[str, List[Dict]], topics: List[str], max_chars: int = 1200) -> str:
    """
    Construit un digest restreint à une liste de topics pour un bloc donné.
    Exemple 
    Bloc 1: topics = ["Ascendant", "Maison I", "MaîtreAsc"]
    Bloc 2 : ["Ascendant", "Soleil", "Lune"]
    """
    subset = {k: par_topic.get(k, []) for k in topics}
    return construire_rag_digest(subset, max_chars_total=max_chars)

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
        if len(question) < 30:  # Skip les questions trop courtes
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
            # ⚠️ Sans argument → utilise la collection par défaut (WEAVIATE_COLLECTION du .env)
            with weaviate_manager.get_collection() as collection:
                for question in nouvelles_requetes[:5]:  # Limiter à 5 pour éviter timeout
                    try:
                        resp = collection.query.hybrid(
                            query=question,
                            limit=1,
                            alpha=0.7,
                            return_metadata=wvc.query.MetadataQuery(score=True),
                        )

                        if not resp.objects:
                            print(f"❌ Aucun résultat pour: {question[:40]}…")
                            continue

                        obj = resp.objects[0]
                        score = getattr(obj.metadata, "score", 0.0) or 0.0
                        if score <= 0.6:
                            print(f"❌ Score trop faible ({score:.3f}) pour: {question[:40]}…")
                            continue

                        props = obj.properties or {}
                        props_l = {str(k).lower(): v for k, v in props.items()}
                        interpretation = (
                            props_l.get("interpretation")
                            or props.get("INTERPRETATION")
                            or props.get("iNTERPRETATION")
                        )

                        if interpretation and len(str(interpretation).strip()) > 0:
                            resultats[question] = str(interpretation).strip()
                            rag_cache.set(question, resultats[question])
                            print(f"  ✅ Nouvelle requête traitée: {question[:30]}…")
                        else:
                            print(f"❌ Interprétation vide pour: {question[:40]}…")

                    except Exception as e:
                        print(f"❌ Erreur pour {question[:30]}…: {e}")
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