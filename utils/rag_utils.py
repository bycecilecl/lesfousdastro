from openai import OpenAI
from utils.connect_rag import get_weaviate_client
import os


def interroger_rag(question, collection_name="Astro_BDD", limit=3):
    client = get_weaviate_client()
    collection = client.collections.get(collection_name)
    response = collection.query.near_text(
        query=question,
        limit=limit
    )
    results = response.objects
    contextes = [obj.properties.get("text", "") for obj in results]
    contenu = "\n\n".join(contextes)

    prompt = f"""
    Voici des extraits de textes astrologiques :
    {contenu}

    En te basant uniquement sur ces informations, réponds à la question suivante :
    {question}
    """

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return completion.choices[0].message.content