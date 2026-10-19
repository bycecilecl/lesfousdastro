"""Client Claude réservé à Forces & Défis ; aucun repli vers OpenAI."""
import json
import logging

logger = logging.getLogger(__name__)


def interroger_llm(prompt, system_prompt=None, max_tokens=12000):
    from utils.claude_llm import CLIENT, BlocTronqueError
    # Même modèle et paramètres de réflexion que le parcours RS v2 local.
    MODEL = "claude-sonnet-5-5"

    payload = dict(model=MODEL, max_tokens=max_tokens,
                   thinking={"type": "adaptive"},
                   extra_body={"output_config": {"effort": "medium"}},
                   messages=[{'role': 'user', 'content': prompt}])
    if system_prompt:
        payload['system'] = system_prompt
    # Trace du contenu réellement envoyé, sans clé API ni en-têtes.
    print('\n=== FORCES & DEFIS — REQUÊTE CLAUDE COMPLÈTE ===\n'
          + json.dumps(payload, ensure_ascii=False, indent=2)
          + '\n=== FIN REQUÊTE CLAUDE ===\n', flush=True)

    # Un seul appel facturé : conserver la réponse partielle sans régénérer.
    client = CLIENT.with_options(max_retries=0)
    with client.messages.stream(**payload) as stream:
        response = stream.get_final_message()
    text = '\n'.join(block.text for block in response.content
                     if getattr(block, 'type', None) == 'text').strip()
    logger.info('FD Claude model=%s stop_reason=%s input_tokens=%s output_tokens=%s',
                MODEL, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens)
    # Contenu et usage consultables dans les logs du moteur, sans clé ni en-têtes.
    print('=== FORCES & DEFIS — RÉPONSE CLAUDE BRUTE ===', flush=True)
    print(response.model_dump_json(indent=2), flush=True)
    if response.stop_reason == 'max_tokens':
        logger.error('FD Claude tronqué : texte partiel conservé, aucune relance automatique.')
        raise BlocTronqueError(text)
    if not text:
        raise ValueError('Analyse Claude vide : aucun rapport à livrer.')
    return text
