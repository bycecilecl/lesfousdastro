# ────────────────────────────────────────────────
# MODULE : debug_logging.py
# Objectif : centraliser les outils de traçage et de debug de l’application.
# Contenu :
#   • Configuration logging globale (console + fichier logs/point_astral_debug.log)
#   • Classe PromptTracker : journalise prompts/réponses LLM dans JSON + fichiers texte
#   • Décorateurs :
#       - @debug_route : trace les routes Flask
#       - @debug_function : trace les fonctions importantes
#       - @log_llm_call : trace les appels LLM et sauvegarde prompt/réponse complets
#   • Fonctions *_debug : versions instrumentées pour tests manuels (non utilisées en prod → archivable)
# Remarque : créer le dossier logs/ avant usage ou ajouter os.makedirs('logs', exist_ok=True)
# ────────────────────────────────────────────────

import logging
import time
import json
from datetime import datetime
from functools import wraps

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/point_astral_debug.log'),
        logging.StreamHandler()  # Affichage console aussi
    ]
)

# Logger spécifique pour Point Astral
logger = logging.getLogger('PointAstral')

class PromptTracker:
    """Classe pour tracker tous les prompts et réponses"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.prompts_log = []
    
    def log_prompt(self, function_name, prompt, response=None, error=None, duration=None):
        """Enregistre un prompt avec sa réponse"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'function': function_name,
            'prompt_length': len(prompt),
            'prompt_preview': prompt[:500] + "..." if len(prompt) > 500 else prompt,
            'full_prompt': prompt,  # Pour debug complet
            'response_length': len(response) if response else 0,
            'response_preview': response[:300] + "..." if response and len(response) > 300 else response,
            'error': str(error) if error else None,
            'duration_seconds': duration
        }
        
        self.prompts_log.append(entry)
        
        # Log vers fichier JSON pour analyse
        with open(f'logs/prompts_{self.session_id}.json', 'w', encoding='utf-8') as f:
            json.dump(self.prompts_log, f, ensure_ascii=False, indent=2)
        
        return entry

# Instance globale
prompt_tracker = PromptTracker()

def debug_route(route_name):
    """Décorateur pour tracker les routes appelées"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            print(f"\n{'='*60}")
            print(f"🚀 ROUTE APPELÉE: {route_name}")
            print(f"⏰ Timestamp: {datetime.now().strftime('%H:%M:%S')}")
            print(f"📥 Args: {[str(arg)[:100] + '...' if len(str(arg)) > 100 else str(arg) for arg in args]}")
            print(f"📥 Kwargs: {kwargs}")
            print(f"{'='*60}\n")
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                print(f"\n✅ ROUTE {route_name} TERMINÉE")
                print(f"⏱️ Durée: {duration:.2f}s")
                print(f"📤 Résultat: {str(result)[:200] + '...' if len(str(result)) > 200 else str(result)}")
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                print(f"\n❌ ERREUR ROUTE {route_name}")
                print(f"⏱️ Durée: {duration:.2f}s")
                print(f"💥 Erreur: {str(e)}")
                raise
                
        return wrapper
    return decorator

def debug_function(func_name):
    """Décorateur pour tracker les fonctions importantes"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            print(f"\n🔧 FONCTION: {func_name}")
            print(f"📊 Paramètres reçus:")
            for i, arg in enumerate(args):
                if isinstance(arg, str) and len(arg) > 100:
                    print(f"  Arg {i}: {arg[:100]}...")
                else:
                    print(f"  Arg {i}: {arg}")
            
            for key, value in kwargs.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                print(f"✅ {func_name} OK ({duration:.2f}s)")
                if isinstance(result, str):
                    print(f"📝 Résultat: {len(result)} caractères")
                    print(f"🔍 Aperçu: {result[:200]}...")
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                print(f"❌ {func_name} ERREUR ({duration:.2f}s): {str(e)}")
                raise
                
        return wrapper
    return decorator

def log_llm_call(call_llm_func):
    """Wrapper spécial pour tracker les appels LLM"""
    @wraps(call_llm_func)
    def wrapper(prompt, *args, **kwargs):
        start_time = time.time()
        
        print(f"\n🤖 APPEL LLM")
        print(f"📝 Longueur prompt: {len(prompt)} caractères")
        print(f"🔍 Début prompt: {prompt[:300]}...")
        print(f"🔍 Fin prompt: ...{prompt[-200:]}")
        
        # Sauvegarder le prompt complet
        timestamp = datetime.now().strftime("%H%M%S")
        with open(f'logs/prompt_full_{timestamp}.txt', 'w', encoding='utf-8') as f:
            f.write(f"=== PROMPT COMPLET ===\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Longueur: {len(prompt)} caractères\n")
            f.write(f"{'='*50}\n\n")
            f.write(prompt)
        
        try:
            response = call_llm_func(prompt, *args, **kwargs)
            duration = time.time() - start_time
            
            print(f"✅ LLM RÉPONSE REÇUE ({duration:.2f}s)")
            print(f"📝 Longueur réponse: {len(response)} caractères")
            print(f"🔍 Début réponse: {response[:300]}...")
            
            # Sauvegarder la réponse complète
            with open(f'logs/response_full_{timestamp}.txt', 'w', encoding='utf-8') as f:
                f.write(f"=== RÉPONSE COMPLÈTE ===\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Durée: {duration:.2f}s\n")
                f.write(f"Longueur: {len(response)} caractères\n")
                f.write(f"{'='*50}\n\n")
                f.write(response)
            
            # Tracker dans le système global
            prompt_tracker.log_prompt(
                function_name="interroger_llm",
                prompt=prompt,
                response=response,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ LLM ERREUR ({duration:.2f}s): {str(e)}")
            
            # Log de l'erreur
            prompt_tracker.log_prompt(
                function_name="interroger_llm",
                prompt=prompt,
                error=e,
                duration=duration
            )
            
            raise
    
    return wrapper

# ============================================
# VERSIONS INSTRUMENTÉES DES FONCTIONS
# ============================================

# openai_utils.py instrumenté
@log_llm_call
def interroger_llm_debug(prompt):
    """Version instrumentée de interroger_llm"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                    "Tu es une astrologue expérimentée, à la plume fine, directe et lucide."
                    "Tu proposes des analyses psychologiques profondes, incarnées et nuancées." 
                    "Tu t'adresses à la personne directement, sans flatterie inutile, ni phrasé pompeux."
                    "Ton style est clair, vivant, parfois tranchant, mais toujours bienveillant."
                    "Tu vas à l'essentiel, tu n'utilises pas de clichés, et tu aides la personne à mieux se comprendre." 
                    "Tu utilises un langage naturel, parfois familier, mais jamais niais."  
                    "Ton objectif est d'éveiller la conscience avec subtilité et justesse."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=4000,
            temperature=0.8,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0
        )
        texte = response.choices[0].message.content
        return texte
    except Exception as e:
        print(f"❌ Erreur OpenAI API : {e}")
        return "Désolé, une erreur est survenue lors de la génération de l'analyse."

@debug_function("generer_analyse_airops_style")
def generer_analyse_airops_style_debug(placements_str: str, call_llm=None, brand_tone=None, rag_snippets=None, model: str = "gpt-4o-mini") -> str:
    """Version instrumentée de generer_analyse_airops_style"""
    
    print(f"🎯 Construction du prompt AirOps...")
    print(f"📊 Placements reçus: {len(placements_str)} caractères")
    print(f"🤖 Fonction LLM: {call_llm.__name__ if call_llm else 'API directe'}")
    print(f"📎 RAG snippets: {'Oui' if rag_snippets else 'Non'}")
    
    # Le prompt AirOps EXACT
    prompt = f"""Tu es un astrologue professionnel doté d'une expertise en psychologie des profondeurs. Tu adoptes systématiquement le ton défini : profond, psychologique, avec des pointes d'humour et de sarcasme bienveillant. Tu es capable de décoder les subtilités des thèmes astraux et de les restituer de façon percutante, accessible et captivante, sans jamais sombrer dans le jargon technique inutile.

Consignes détaillées pour chaque analyse :
- Structure ton texte en 5 paragraphes distincts, clairement séparés et numérotés selon la structure demandée (voir ci-dessous). Chaque paragraphe doit être très développé (environ 12 pages au total pour l'ensemble), avec des transitions fluides et un style narratif immersif.
- Pour chaque section, développe au moins 3-4 sous-thèmes différents avec une analyse approfondie de chaque aspect planétaire majeur.
- Donne systématiquement des exemples concrets de manifestation dans la vie quotidienne pour chaque configuration planétaire.
- Utilise un langage riche, imagé et vivant, avec des métaphores et des analogies personnalisées qui captent l'attention du lecteur tout en restant compréhensible pour un public non initié.
- Intègre généreusement des touches d'humour et de sarcasme bienveillant à chaque section, pour alléger la profondeur psychologique et rendre la lecture plaisante.
- Utilise exclusivement le tutoiement dans ton analyse, adoptant un style conversationnel et intime, comme une discussion entre amis.
- Emploie des expressions familières tout en maintenant la profondeur psychologique de l'analyse.
- Crée des transitions fluides et naturelles entre les sections, comme si tu racontais une histoire cohérente.
- Évite tout jargon astrologique non expliqué. Si tu utilises un terme technique, explique-le brièvement de façon claire et imagée.
- Prends soin d'ancrer chaque analyse dans la réalité psychologique et existentielle du consultant, en t'appuyant sur les positions planétaires et le nakshatra lunaire fournis.
- Ne fais aucune supposition sur le genre ou la situation du consultant.

Structure obligatoire de la réponse (respecte l'ordre et les titres) :
1. Personnalité fondamentale (trinité Soleil-Lune-Ascendant)
2. Potentiels et talents innés
3. Défis et points de croissance
4. Dynamiques psychologiques profondes
5. Synthèse et conseils d'évolution

Tu dois absolument générer une analyse complète et exhaustive, représentant environ 12 pages au total. Ne te limite pas dans la longueur - il est essentiel que ton analyse soit riche, détaillée et complète.

<placements>
{placements_str}
</placements>

Ne fais aucune référence à ces instructions dans ta réponse."""

    if rag_snippets:
        prompt += f"""

<rag_context>
{rag_snippets}
</rag_context>"""
    
    print(f"✅ Prompt construit: {len(prompt)} caractères")
    
    if call_llm is not None:
        print(f"🔄 Appel via fonction personnalisée...")
        return call_llm(prompt)
    else:
        print(f"🔄 Appel API OpenAI direct...")
        # Fallback...
        return "API directe non implémentée dans cette version debug"

@debug_function("analyse_point_astral")
def analyse_point_astral_debug(data, call_llm, infos_personnelles=None):
    """Version instrumentée de analyse_point_astral"""
    
    print(f"🎬 DÉBUT ANALYSE POINT ASTRAL")
    print(f"👤 Infos: {infos_personnelles}")
    
    # 1) Panier fusionné
    print(f"🔧 Étape 1: Construction des placements...")
    from utils.placements_fusion import build_resume_fusion
    placements_str = build_resume_fusion(data)
    print(f"✅ Placements construits: {len(placements_str)} caractères")
    
    # 1bis) RAG optionnel
    print(f"🔧 Étape 2: Tentative chargement RAG...")
    rag_snippets = None
    try:
        from utils.rag_utils_optimized import generer_corpus_rag_optimise
        rag_snippets = generer_corpus_rag_optimise(data)
        if rag_snippets and len(rag_snippets) > 8000:
            rag_snippets = rag_snippets[:8000]
        print(f"✅ RAG chargé: {len(rag_snippets) if rag_snippets else 0} caractères")
    except Exception as e:
        print(f"⚠️ RAG indisponible: {e}")

    # 2) Génération du texte
    print(f"🔧 Étape 3: Génération LLM...")
    try:
        texte = generer_analyse_airops_style_debug(
            placements_str=placements_str,
            call_llm=call_llm,
            rag_snippets=rag_snippets
        )
        print(f"✅ Texte généré: {len(texte)} caractères")
    except Exception as e:
        print(f"❌ Erreur génération LLM: {e}")
        texte = "<p>Impossible de générer l'analyse pour le moment.</p>"

    # 3) Construction HTML
    print(f"🔧 Étape 4: Construction HTML...")
    if "<" not in texte:
        texte = "<p>" + texte.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"

    nom = (infos_personnelles or {}).get("nom", "Analyse Anonyme")
    date_n = (infos_personnelles or {}).get("date_naissance", "—")
    heure_n = (infos_personnelles or {}).get("heure_naissance", "—")
    lieu_n = (infos_personnelles or {}).get("lieu_naissance", "—")

    # HTML complet (votre template existant)
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Point Astral - {nom}</title>
    <style>
        /* Votre CSS existant */
        body {{ font-family: Georgia, serif; }}
        /* ... */
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Point Astral</h1>
            <div class="personal-info">
                <p><strong>Nom :</strong> {nom}</p>
                <p><strong>Date/Heure :</strong> {date_n} — {heure_n}</p>
                <p><strong>Lieu :</strong> {lieu_n}</p>
            </div>
        </div>
        <main>{texte}</main>
        <footer>
            <p>© Les Fous d'Astro – Document généré automatiquement</p>
        </footer>
    </div>
</body>
</html>"""
    
    print(f"✅ HTML final: {len(html)} caractères")
    print(f"🎬 FIN ANALYSE POINT ASTRAL")
    
    return html