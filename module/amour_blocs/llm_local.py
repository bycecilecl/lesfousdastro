"""Moteur de référence isolé pour le profil amoureux local."""
import os
from openai import OpenAI
from utils.llm_system_prompts import SYSTEM_BASE

def _interroger_openai(prompt, system_prompt, single_attempt=False):
    """Ancien moteur OpenAI, conservé comme solution de repli."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquant.")

    client = OpenAI(api_key=api_key, max_retries=0) if single_attempt else OpenAI(api_key=api_key)
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
    if single_attempt and response.choices[0].finish_reason != "stop":
        raise RuntimeError("Réponse OpenAI incomplète : aucun rapport à livrer.")
    return response.choices[0].message.content or ""

def interroger_llm(prompt, system_prompt=None, provider=None, single_attempt=False,
                   max_tokens=8000, truncation_retry_tokens=None):
    print(f"🤖 APPEL LLM - Prompt: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")

    if system_prompt is None:
        system_prompt = SYSTEM_BASE

    try:
        fournisseur = (provider or "claude").strip().lower()

        if fournisseur == "claude":
            from module.amour_blocs.claude_reference import ask_claude, BlocTronqueError

            print("🤖 Fournisseur global : Claude")
            try:
                try:
                    texte = ask_claude(
                        prompt=prompt, system=system_prompt, max_tokens=max_tokens,
                        temperature=0.7, single_attempt=single_attempt,
                    )
                except BlocTronqueError:
                    if not single_attempt or not truncation_retry_tokens:
                        raise
                    # One explicit recovery only; SDK retries and provider fallback
                    # remain disabled. A second incomplete answer propagates.
                    texte = ask_claude(
                        prompt=prompt, system=system_prompt,
                        max_tokens=truncation_retry_tokens,
                        temperature=0.7, single_attempt=True,
                    )
            except Exception as claude_error:
                if single_attempt:
                    raise
                print(
                    "⚠️ Claude indisponible, repli ponctuel vers OpenAI : "
                    f"{claude_error}"
                )
                texte = _interroger_openai(prompt, system_prompt, single_attempt=single_attempt)
        elif fournisseur == "openai":
            print("🤖 Fournisseur global : OpenAI")
            texte = _interroger_openai(prompt, system_prompt, single_attempt=single_attempt)
        else:
            raise ValueError(
                "LLM_PROVIDER doit valoir 'claude' ou 'openai' "
                f"(valeur reçue : {fournisseur!r})."
            )

        print(f"✅ RÉPONSE REÇUE - {len(texte)} caractères")
        print(f"🔍 Début réponse: {texte[:200]}...")
        return texte

    except Exception as e:
        if single_attempt:
            raise
        print(f"❌ Erreur API LLM : {e}")
        return "Désolé, une erreur est survenue lors de la génération de l'analyse."
