# utils/llm_client.py
# ——————————————————————————————————————————————————————————
# Objectif :
# 1) Charger .env depuis la racine (de façon explicite et prévisible)
# 2) Nettoyer la clé API (doublons "sk-..." collés, retours \r\n)
# 3) Avoir un client avec timeout clair
# 4) Avoir un ask_llm robuste + un ping de santé pour diagnostiquer vite
# ——————————————————————————————————————————————————————————

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, BadRequestError

# 1) Charger .env explicitement depuis la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../WEBSITE_FDA_LAST
DOTENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

# 2) Récupérer et NETTOYER la clé API
raw_key = (os.getenv("OPENAI_API_KEY") or "").strip()

# Si quelqu'un a collé 2 clés d'affilée, ne garder que la première (séparateur "sk-")
if raw_key.startswith("sk-"):
    j = raw_key.find("sk-", 4)  # cherche une 2e occurrence
    if j != -1:
        raw_key = raw_key[:j].strip()

# Enlever tout retour chariot/ligne au cas où
CLEAN_API_KEY = raw_key.replace("\r", "").replace("\n", "").strip()

if not CLEAN_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY manquant. Vérifie ton .env à la racine (clé unique, une seule ligne).\n"
        f"Chemin lu : {DOTENV_PATH}"
    )

# 3) Initialiser le client avec un timeout clair
CLIENT = OpenAI(api_key=CLEAN_API_KEY, timeout=90.0)

# 4) Modèle par défaut (overridable via .env)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def ping_openai() -> bool:
    """Petit test de santé : renvoie True si l'API répond à un 'ping' minimal."""
    try:
        r = CLIENT.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0.0,
        )
        return bool(r and r.choices and r.choices[0].message.content)
    except Exception as e:
        print(f"[PING] KO: {type(e).__name__}: {e}", flush=True)
        return False


def ask_llm(
    prompt: str,
    system: str = "",
    max_tokens: int = 1200,
    temperature: float = 0.7,
    retries: int = 3,
    min_backoff: float = 1.5,
) -> str:
    """
    Appel LLM robuste avec retries et messages d'erreurs explicites.
    Retourne le texte (content) directement.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = CLIENT.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError("Réponse vide du LLM.")
            return content

        except RateLimitError as e:
            last_err = e
            wait = min_backoff ** attempt
            print(f"[LLM] Rate limit 429 (tentative {attempt}/{retries}) → pause {wait:.1f}s", flush=True)
            time.sleep(wait)

        except APIConnectionError as e:
            last_err = e
            wait = min_backoff ** attempt
            print(f"[LLM] Connexion/timeout (tentative {attempt}/{retries}) → pause {wait:.1f}s", flush=True)
            print("      Indices: réseau lent, VPN/Proxy, DNS/SSL, latence trop élevée pour un gros prompt.", flush=True)
            time.sleep(wait)

        except BadRequestError as e:
            # 400/401/404 : souvent param/modele/payload invalide (on ne retente pas)
            raise RuntimeError(f"[LLM] BadRequest: {e}") from e

        except APIError as e:
            # 5xx côté serveur → retentatives
            last_err = e
            wait = min_backoff ** attempt
            print(f"[LLM] Erreur API serveur 5xx (tentative {attempt}/{retries}) → pause {wait:.1f}s", flush=True)
            time.sleep(wait)

        except Exception as e:
            last_err = e
            # Erreur inconnue → on sort (mieux vaut la voir en clair)
            break

    raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")