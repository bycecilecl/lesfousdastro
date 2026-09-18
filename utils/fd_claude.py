"""Client Claude réservé à Forces & Défis ; aucun repli vers OpenAI."""
import json
import logging

logger = logging.getLogger(__name__)


def interroger_llm(prompt, system_prompt=None, max_tokens=12000, single_attempt=True):
    from utils.claude_llm import CLIENT, MODEL, BlocTronqueError

    payload = dict(model=MODEL, max_tokens=max_tokens, temperature=0.7,
                   messages=[{'role': 'user', 'content': prompt}])
    if system_prompt:
        payload['system'] = system_prompt
    # Trace du contenu réellement envoyé, sans clé API ni en-têtes.
    print('\n=== FORCES & DEFIS — REQUÊTE CLAUDE COMPLÈTE ===\n'
          + json.dumps(payload, ensure_ascii=False, indent=2)
          + '\n=== FIN REQUÊTE CLAUDE ===\n', flush=True)

    # Streaming pour les rapports longs ; pas de retry SDK ni de régénération.
    client = CLIENT.with_options(max_retries=0)
    with client.messages.stream(**payload) as stream:
        response = stream.get_final_message()
    text = '\n'.join(block.text for block in response.content
                     if getattr(block, 'type', None) == 'text').strip()
    logger.info('FD Claude model=%s stop_reason=%s input_tokens=%s output_tokens=%s',
                MODEL, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens)
    if response.stop_reason == 'max_tokens':
        raise BlocTronqueError(text)
    if not text:
        raise ValueError('Analyse Claude vide : aucun rapport à livrer.')
    return text
