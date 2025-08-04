import os
from openai import OpenAI

# Debug - voir toutes les variables d'environnement
print("=== DEBUG VARIABLES D'ENVIRONNEMENT ===")
print(f"OPENAI_API_KEY existe: {'OPENAI_API_KEY' in os.environ}")
print(f"Valeur OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'NON_TROUVEE')}")
print(f"Toutes les variables qui contiennent 'API': {[k for k in os.environ.keys() if 'API' in k]}")
print("=======================================")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(f"OPENAI_API_KEY non trouvée. Variables disponibles: {list(os.environ.keys())}")

client = OpenAI(api_key=api_key)

def interroger_llm(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # ou "gpt-4", selon ton usage
            messages=[
                {
                    "role": "system",
                    "content": (
                    "Tu es une astrologue expérimentée, à la plume fine, directe et lucide."
                    "Tu proposes des analyses psychologiques profondes, incarnées et nuancées." 
                    "Tu t’adresses à la personne directement, sans flatterie inutile, ni phrasé pompeux."
                    "Ton style est clair, vivant, parfois tranchant, mais toujours bienveillant."
                    "Tu vas à l’essentiel, tu n’utilises pas de clichés, et tu aides la personne à mieux se comprendre." 
                    "Tu utilises un langage naturel, parfois familier, mais jamais niais."  
                    "Ton objectif est d’éveiller la conscience avec subtilité et justesse."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=800,
            temperature=0.8,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0
        )
        texte = response.choices[0].message.content
        return texte
    except Exception as e:
        print(f"Erreur OpenAI API : {e}")
        return "Désolé, une erreur est survenue lors de la génération de l’analyse."