import os
from dotenv import load_dotenv
from openai import OpenAI
from .debug_logging import log_llm_call, debug_function
import time
from utils.utils_points_forts import extraire_points_forts



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

def interroger_llm(prompt):
    print(f"🤖 APPEL LLM - Prompt: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es une astrologue expérimentée avec un style unique : direct, drôle, sarcastique, moderne. "
                        "Tu utilises des attaques percutantes, des métaphores décalées, des parenthèses ironiques "
                        "et un humour bienveillant. Jamais de ton professoral ou scolaire. Toujours conversationnel."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=8000,
            temperature=0.9,  # Plus créatif pour l'humour
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0
        )
        texte = response.choices[0].message.content
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

 

# ────────────────────────────────────────────────
# FONCTION : generer_analyse_airops_style
# Objectif : Construire un prompt ultra-détaillé pour générer
# une analyse astrologique complète (style AirOps) avec
# intégration facultative d’éléments RAG et de points forts.
# Utilisation : Fonction principale pour produire le texte brut
# d’une analyse complète avant transformation HTML.
# Entrées :
#   - placements_str (str) : résumé des placements planétaires
#   - call_llm (callable, optionnel) : fonction personnalisée pour l’appel LLM
#   - brand_tone (non utilisé ici, optionnel)
#   - rag_snippets (str, optionnel) : contexte enrichi depuis une base RAG
#   - points_forts (str|list, optionnel) : axes majeurs à intégrer
#   - model (str) : modèle OpenAI à utiliser (par défaut "gpt-4o")
# Sortie :
#   - texte généré (str) respectant la structure demandée
# Remarques :
#   - Structure imposée en 5 parties (Personnalité, Potentiels, Défis, Dynamiques, Synthèse)
#   - Analyse exhaustive : aspects, nakshatra lunaire, maître d’ascendant, etc.
#   - Possibilité d’appeler le LLM soit via call_llm, soit directement.
#   - Conçu pour un ton narratif profond, humoristique et psychologique.
# ────────────────────────────────────────────────


def generer_analyse_airops_style(
    placements_str: str,
    call_llm=None,
    brand_tone=None,
    rag_snippets: str | None = None,
    points_forts: str | None = None,   # ✅ ICI: pas de data.get(...) dans la signature
    model: str = "gpt-4o",
) -> str:                               # ✅ ICI: flèche de retour -> str, à la fin
    """
    Génère une analyse style AirOps. Supporte optionnellement:
    - rag_snippets: texte RAG pour enrichir
    - points_forts: string formattée (ex: bloc 'Axes majeurs')
    """

    print(f"🔍 DEBUG points_forts reçu dans fonction: '{points_forts}'")
    print(f"🔍 DEBUG type: {type(points_forts)}")
    print(f"🔍 DEBUG bool: {bool(points_forts)}")
    if points_forts:
        print(f"🔍 DEBUG strip(): '{(points_forts or '').strip()}'")

    
    # Construction des placements avec RAG
    placements_complets = placements_str
    if rag_snippets and len(rag_snippets.strip()) > 100:
        placements_complets += f"""

CONTEXTE ASTROLOGIQUE ENRICHI (base de connaissances) :
{rag_snippets}

IMPORTANT : Utilise ces informations pour enrichir et approfondir ton analyse."""
        
    # ✅ Normalise points_forts (peut être None, list, str)
    if isinstance(points_forts, list):
        pf = "\n".join(str(x).strip() for x in points_forts if str(x).strip())
    else:
        pf = (points_forts or "").strip()

    if len(pf) > 1200:
        pf = pf[:1200] + "…"

    print("🔎 pf present ?", bool(pf))
    if pf:
        print("🔎 pf preview:", pf[:180])
    
    # Le prompt AirOps EXACT avec vos spécifications
    prompt = f"""Tu es un astrologue psychologue au ton direct, incarné, parfois sarcastique. 
Ton rôle est de produire une analyse astrologique profonde et incarnée. 
Pas un catalogue, pas des clichés.

Règles :
1. Commence par l’Ascendant et son maître.
2. Analyse la Trinité (Asc, Soleil, Lune) et les contradictions majeures.
3. Mets en avant les aspects serrés aux luminaires (Saturne, Uranus, Neptune, Pluton).
4. Intègre dignités/chutes, planètes angulaires, amas, dominantes.
5. Pour chaque point : distingue ce qui est ressenti intérieurement vs ce qui est exprimé extérieurement.
6. Illustre chaque contradiction par des exemples concrets de comportements (amour, travail, amitié).
7. Ne traite jamais un placement isolé : toujours en relation avec le reste du thème.
8. Ne minimise pas les placements difficiles : Exemples : Mars rétro Cancer, Vénus–Pluton, Mercure combust doivent être traités à fond.
9. Style : psychologique, incarné, direct. Tu peux être tranchant, mais jamais scolaire.
10. Chaque section (Ascendant, Trinité, Tensions, Atouts, Dominantes, Synthèse) doit faire 800–1200 mots, denses et nuancés. 
Texte final : environ 5 pages.

Le plus important, développe, vas au fond des choses, prends des exemples concrets. 
Le natif doit être surpris d'apprendre autant de choses sur ses mécanismes inconscients.

Voici les données astrologiques :
<placements>
{placements_str}
</placements>

"""
    
# -- axes majeurs (uniquement s'ils existent) --
    if pf:
        prompt += f"""
    ⚡ AXES MAJEURS À PRIVILÉGIER
    {pf}
    """

# -- RAG (uniquement s'il existe) --
    if rag_snippets and rag_snippets.strip():
        prompt += f"""

Informations complémentaires (utilise-les pour enrichir ton analyse) :
<rag_context>
{rag_snippets}
</rag_context>"""

    print(f"✅ Prompt AirOps construit: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")

    if call_llm is not None:
        print(f"🔄 Appel via fonction personnalisée: {call_llm.__name__}")
        return call_llm(prompt)
    else:
        print(f"❌ Aucune fonction call_llm fournie !")
        return "❌ Erreur: aucune fonction de génération disponible"
