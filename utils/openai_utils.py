import os
from dotenv import load_dotenv
from openai import OpenAI
from .debug_logging import log_llm_call, debug_function
import time
from utils.utils_points_forts import extraire_points_forts
from utils.llm_system_prompts import SYSTEM_BASE



load_dotenv()  
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ────────────────────────────────────────────────
# FONCTION : interroger_llm
# Objectif : Appeler directement l’API OpenAI avec un prompt donné
# pour obtenir une réponse textuelle en appliquant un style prédéfini
# (astrologue expérimentée, ton direct, drôle, sarcastique et moderne).
# Utilisation : Fonction générique, utilisée pour de simples requêtes LLM
# sans mise en forme ou logique de prompt complexe.
# Entrées :
#   - prompt (str) : texte envoyé au modèle.
# Sortie :
#   - texte généré par le modèle (str), ou message d'erreur si échec.
# Remarques :
#   - Utilise le modèle "gpt-4o" avec paramètres fixes (température, max_tokens…)
#   - Gère les erreurs d’appel API et affiche un aperçu du prompt et de la réponse.
# ────────────────────────────────────────────────

def interroger_llm(prompt, system_prompt=None):
    print(f"🤖 APPEL LLM - Prompt: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")

    if system_prompt is None:
        system_prompt = SYSTEM_BASE

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=8000,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0
        )
        texte = response.choices[0].message.content or ""
        print(f"✅ RÉPONSE REÇUE - {len(texte)} caractères")
        print(f"🔍 Début réponse: {texte[:200]}...")
        return texte

    except Exception as e:
        print(f"❌ Erreur OpenAI API : {e}")
        return "Désolé, une erreur est survenue lors de la génération de l'analyse."

import hashlib, json

def _h(x): 
    if x is None: 
        return "None"
    if not isinstance(x, str):
        x = json.dumps(x, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(x.encode("utf-8")).hexdigest()

 