import os
from dotenv import load_dotenv
from openai import OpenAI
from .debug_logging import log_llm_call, debug_function
import time
from utils.utils_points_forts import extraire_points_forts
from utils.llm_system_prompts import SYSTEM_BASE



load_dotenv()


def _interroger_openai(prompt, system_prompt):
    """Ancien moteur OpenAI, conservé comme solution de repli."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquant.")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=8000,
        temperature=0.7,
        top_p=1.0,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return response.choices[0].message.content or ""

# ────────────────────────────────────────────────
# FONCTION : interroger_llm
# Objectif : conserver l'interface historique tout en sélectionnant le moteur
# pour obtenir une réponse textuelle en appliquant un style prédéfini
# (astrologue expérimentée, ton direct, drôle, sarcastique et moderne).
# Utilisation : Fonction générique, utilisée pour de simples requêtes LLM
# sans mise en forme ou logique de prompt complexe.
# Entrées :
#   - prompt (str) : texte envoyé au modèle.
# Sortie :
#   - texte généré par le modèle (str), ou message d'erreur si échec.
# Remarques :
#   - Utilise Claude par défaut ; OpenAI reste sélectionnable par configuration.
#   - Gère les erreurs d’appel API et affiche un aperçu du prompt et de la réponse.
# ────────────────────────────────────────────────

def interroger_llm(prompt, system_prompt=None, provider=None):
    print(f"🤖 APPEL LLM - Prompt: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")

    if system_prompt is None:
        system_prompt = SYSTEM_BASE

    try:
        fournisseur = (provider or os.getenv("LLM_PROVIDER", "claude")).strip().lower()

        if fournisseur == "claude":
            from utils.claude_llm import ask_claude

            print("🤖 Fournisseur global : Claude")
            try:
                texte = ask_claude(
                    prompt=prompt,
                    system=system_prompt,
                    max_tokens=8000,
                    temperature=0.7,
                )
            except Exception as claude_error:
                print(
                    "⚠️ Claude indisponible, repli ponctuel vers OpenAI : "
                    f"{claude_error}"
                )
                texte = _interroger_openai(prompt, system_prompt)
        elif fournisseur == "openai":
            print("🤖 Fournisseur global : OpenAI")
            texte = _interroger_openai(prompt, system_prompt)
        else:
            raise ValueError(
                "LLM_PROVIDER doit valoir 'claude' ou 'openai' "
                f"(valeur reçue : {fournisseur!r})."
            )

        print(f"✅ RÉPONSE REÇUE - {len(texte)} caractères")
        print(f"🔍 Début réponse: {texte[:200]}...")
        return texte

    except Exception as e:
        print(f"❌ Erreur API LLM : {e}")
        return "Désolé, une erreur est survenue lors de la génération de l'analyse."

import hashlib, json

def _h(x): 
    if x is None: 
        return "None"
    if not isinstance(x, str):
        x = json.dumps(x, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(x.encode("utf-8")).hexdigest()
