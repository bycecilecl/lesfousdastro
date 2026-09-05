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
def _get_openai_client():
    """Initialise OpenAI uniquement lorsqu'il est choisi comme moteur de repli."""
    raw_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    clean_api_key = raw_key.replace("\r", "").replace("\n", "").strip()
    if not clean_api_key:
        raise RuntimeError(f"OPENAI_API_KEY manquant. Chemin lu : {DOTENV_PATH}")
    return OpenAI(api_key=clean_api_key, timeout=90.0)

# 4) Modèle par défaut (overridable via .env)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def ping_openai() -> bool:
    """Petit test de santé : renvoie True si l'API répond à un 'ping' minimal."""
    try:
        r = _get_openai_client().chat.completions.create(
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
    Appel Claude par défaut, avec OpenAI conservé comme moteur de repli.
    Les retries ci-dessous concernent le chemin OpenAI.
    Retourne le texte (content) directement.
    """
    provider = os.getenv("LLM_PROVIDER", "claude").lower().strip()

    if provider == "claude":
        from utils.claude_llm import ask_claude

        try:
            return ask_claude(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as claude_error:
            print(
                "[LLM] Claude indisponible, repli ponctuel vers OpenAI : "
                f"{claude_error}",
                flush=True,
            )
            provider = "openai"

    if provider != "openai":
        raise ValueError(
            "LLM_PROVIDER doit valoir 'claude' ou 'openai' "
            f"(valeur reçue : {provider!r})."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = _get_openai_client().chat.completions.create(
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
