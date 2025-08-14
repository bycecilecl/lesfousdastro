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

    print("🔎 HASH placements_str:", _h(placements_str))
    print("🔎 HASH axes_majeurs_str:", _h(data.get("axes_majeurs_str")))
    print("🔎 HASH rag_snippets:", _h(rag_snippets))

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


# def generer_analyse_airops_style(
#     placements_str: str,
#     call_llm=None,
#     brand_tone=None,
#     rag_snippets: str | None = None,
#     points_forts: str | None = None,   # ✅ ICI: pas de data.get(...) dans la signature
#     model: str = "gpt-4o",
# ) -> str:                               # ✅ ICI: flèche de retour -> str, à la fin
#     """
#     Génère une analyse style AirOps. Supporte optionnellement:
#     - rag_snippets: texte RAG pour enrichir
#     - points_forts: string formattée (ex: bloc 'Axes majeurs')
#     """

#     print(f"""
#     🔍 DEBUG points_forts:
#     - Valeur brute : {points_forts}
#     - Type : {type(points_forts)}
#     - Booléen : {bool(points_forts)}
#     - Strip : '{(points_forts or '').strip()}'
#     """)
    
#     # Construction des placements avec RAG
#     placements_complets = placements_str
#     if rag_snippets and len(rag_snippets.strip()) > 100:
#         placements_complets += f"""

# CONTEXTE ASTROLOGIQUE ENRICHI (base de connaissances) :
# {rag_snippets}

# IMPORTANT : Utilise ces informations pour enrichir et approfondir ton analyse."""
        
#     # ✅ Normalise points_forts (peut être None, list, str)
#     if isinstance(points_forts, list):
#         pf = "\n".join(str(x).strip() for x in points_forts if str(x).strip())
#     else:
#         pf = (points_forts or "").strip()

#     if len(pf) > 1200:
#         pf = pf[:1200] + "…"

#     print("🔎 pf present ?", bool(pf))
#     if pf:
#         print("🔎 pf preview:", pf[:180])
    
#     # Le prompt AirOps EXACT avec vos spécifications
#     prompt = f"""Tu es un astrologue professionnel doté d'une expertise en psychologie des profondeurs. Tu adoptes systématiquement le ton défini : profond, psychologique, avec des pointes d'humour et de sarcasme bienveillant. Tu es capable de décoder les subtilités des thèmes astraux et de les restituer de façon percutante, accessible et captivante, sans jamais sombrer dans le jargon technique inutile.

# Consignes détaillées pour chaque analyse :
# - Structure ton texte en 5 paragraphes distincts, clairement séparés et numérotés selon la structure demandée (voir ci-dessous). Chaque paragraphe doit être très développé (environ 6 pages au total pour l'ensemble), avec des transitions fluides et un style narratif immersif.
# - Pour chaque section, développe au moins 3-4 sous-thèmes différents avec une analyse approfondie de chaque aspect planétaire majeur.
# - Donne systématiquement des exemples concrets de manifestation dans la vie quotidienne pour chaque configuration planétaire.
# - Utilise un langage riche, imagé et vivant, avec des métaphores et des analogies personnalisées qui captent l'attention du lecteur tout en restant compréhensible pour un public non initié.
# - Intègre généreusement des touches d'humour et de sarcasme bienveillant à chaque section, pour alléger la profondeur psychologique et rendre la lecture plaisante.
# - Utilise exclusivement le tutoiement dans ton analyse, adoptant un style conversationnel et intime, comme une discussion entre amis.
# - Emploie des expressions familières tout en maintenant la profondeur psychologique de l'analyse.
# - Crée des transitions fluides et naturelles entre les sections, comme si tu racontais une histoire cohérente.
# - Évite tout jargon astrologique non expliqué. Si tu utilises un terme technique, explique-le brièvement de façon claire et imagée.
# - Prends soin d'ancrer chaque analyse dans la réalité psychologique et existentielle du consultant, en t'appuyant sur les positions planétaires et le nakshatra lunaire fournis.
# - Ne fais aucune supposition sur le genre ou la situation du consultant.

# Structure obligatoire de la réponse (respecte l'ordre et les titres) :
# 1. Personnalité fondamentale (trinité Soleil-Lune-Ascendant) : Analyse la dynamique entre ces trois pôles majeurs, décris la coloration générale de la personnalité, les contradictions ou harmonies, et donne une image vivante du « personnage principal » de ce thème. Développe au moins 3-4 aspects distincts de cette personnalité.
# 2. Potentiels et talents innés : Identifie les forces, dons naturels, ressources intérieures, et la manière dont ils peuvent s'exprimer dans la vie concrète. Utilise des exemples imagés et des métaphores personnalisées. Explore au moins 3-4 talents ou potentiels différents.
# 3. Défis et points de croissance : Décris les principaux obstacles, tensions ou faiblesses du thème, en montrant comment ils peuvent devenir des leviers d'évolution. Pour chaque défi identifié (au moins 3-4), donne des conseils pratiques et personnalisés. Ajoute une touche d'autodérision ou de sarcasme bienveillant pour dédramatiser.
# 4. Dynamiques psychologiques profondes : Plonge dans les mécanismes inconscients, les schémas répétitifs, les blessures ou aspirations cachées. Explore au moins 3-4 dynamiques différentes. Utilise un ton à la fois profond et piquant, sans complaisance mais toujours avec bienveillance.
# 5. Synthèse et conseils d'évolution : Fais une synthèse globale, puis propose des pistes concrètes d'évolution ou de réflexion, en gardant le ton profond et sarcastique. Termine par une note d'encouragement ou une punchline mémorable.

# N'utilise jamais de listes à puces : privilégie le texte narratif, fluide et littéraire. Chaque paragraphe doit être long, détaillé, et donner l'impression d'une consultation personnalisée et inspirante.

# Instructions spécifiques pour l'interprétation des aspects et nakshatras :
# - Analyse les aspects planétaires en profondeur, en expliquant comment ils influencent le psychisme et le comportement.
# - Accorde une attention particulière aux aspects majeurs (conjonctions, oppositions, trigones, carrés, sextiles) ayant un orbe inférieur à 5°.
# - Traite systématiquement TOUS les aspects majeurs ayant un orbe inférieur à 5° listés dans les placements.
# - Interprète le nakshatra lunaire pour enrichir la compréhension des schémas émotionnels et des tendances karmiques.
# - Lorsque tu mentionnes une maison astrologique, explique clairement son influence sur le domaine de vie concerné.
# - Pour chaque aspect planétaire significatif, explique à la fois sa signification psychologique et ses manifestations concrètes.
# - Donne une importance particulière aux configurations impliquant plusieurs planètes (stelliums, grandes croix, yods, etc.).
# - Intègre l'analyse du maître de l'Ascendant et sa position en signe et en maison.

# Tu dois absolument générer une analyse complète, exhaustive, détaillée. Chaque section doit être entièrement développée, avec plusieurs paragraphes pour chaque sous-thème abordé. Ne te limite pas dans la longueur - il est essentiel que ton analyse soit riche, détaillée et complète. 
# Tu dois absolument t'appuyer sur les informations suivantes pour ton analyse :
# <placements>
# {placements_str}
# </placements>

# """
# # -- axes majeurs (uniquement s'ils existent) --
#     if pf:
#         prompt += f"""
#     ⚡ AXES MAJEURS À PRIVILÉGIER
#     {pf}
#     """

# # -- RAG (uniquement s'il existe) --
#     if rag_snippets and rag_snippets.strip():
#         prompt += f"""

# Informations complémentaires (utilise-les pour enrichir ton analyse) :
# <rag_context>
# {rag_snippets}
# </rag_context>"""

#     print(f"✅ Prompt AirOps construit: {len(prompt)} caractères")
#     print(f"🔍 Début prompt: {prompt[:200]}...")

#     if call_llm is not None:
#         print(f"🔄 Appel via fonction personnalisée: {call_llm.__name__}")
#         return call_llm(prompt)
#     else:
#         print(f"❌ Aucune fonction call_llm fournie !")
#         return "❌ Erreur: aucune fonction de génération disponible"


# Dans openai_utils.py - PROMPT OPTIMISÉ

# Dans openai_utils.py - PROMPT OPTIMISÉ

def generer_analyse_airops_style(
    placements_str: str,
    call_llm=None,
    brand_tone=None,
    rag_snippets: str | None = None,
    points_forts: str | None = None,
    model: str = "gpt-4o",
    gender: str | None = None,
) -> str:

    print(f"🔍 DEBUG GENRE REÇU: '{gender}'")
    print(f"🔍 DEBUG TYPE GENRE: {type(gender)}")
    print(f"""
    🔍 DEBUG points_forts:
    - Valeur brute : {points_forts}
    - Type : {type(points_forts)}
    - Booléen : {bool(points_forts)}
    """)
    
    # ✅ Normalise points_forts (peut être None, list, str)
    if isinstance(points_forts, list):
        pf = "\n".join(str(x).strip() for x in points_forts if str(x).strip())
    else:
        pf = (points_forts or "").strip()

    if len(pf) > 800:  # 🎯 Réduit de 1200 à 800
        pf = pf[:800] + "…"

    print("🔎 pf present ?", bool(pf))
    if pf:
        print("🔎 pf preview:", pf[:180])

    genre_instruction = ""
    if gender == 'male':
        genre_instruction = "IMPORTANT: Cette personne est un homme. Utilise exclusivement le masculin (il/lui/son) et évite les termes génériques comme 'Reine ou Roi'."
    elif gender == 'female':
        genre_instruction = "IMPORTANT: Cette personne est une femme. Utilise exclusivement le féminin (elle/sa) et évite les termes génériques comme 'Reine ou Roi'."
    else:
        genre_instruction = "IMPORTANT: Utilise un langage neutre et inclusif."

    print(f"🔍 DEBUG INSTRUCTION FINALE: '{genre_instruction}'")
    
    # 🎯 PROMPT CONDENSÉ ET EFFICACE
    prompt = f"""
    {genre_instruction}

    Tu es une astrologue experte avec un style psychologique profond, direct, humoristique, grinçant et sarcastique. Ton analyse doit être percutante et accessible.

STRUCTURE OBLIGATOIRE (6 sections numérotées) :

1. **Personnalité fondamentale** : Trinité Soleil-Lune-Ascendant, dynamiques principales, contradictions/harmonies
2. **Potentiels et talents** : Forces naturelles, dons, ressources à exploiter  
3. **Défis et croissance** : Obstacles, tensions, points d'évolution avec conseils pratiques
4. **Dimension védique et nakshatras** : Nakshatra lunaire (émotions/instincts), Ascendant sidéral, maître védique, essence spirituelle
5. **Dynamiques profondes** : Mécanismes inconscients, schémas répétitifs, blessures/aspirations
6. **Synthèse et conseils** : Vision globale, pistes d'évolution, encouragements

STYLE :
- Tutoiement conversationnel et intime
- Humour et sarcasme bienveillant  
- Métaphores et exemples concrets
- Explique les termes techniques simplement
- Texte narratif fluide (pas de listes à puces)
- Chaque section : 2-3 paragraphes développés

FOCUS SUR :
- Aspects majeurs (conjonctions, oppositions, carrés, trigones, sextiles) avec orbe < 5°
- Nakshatra lunaire, de l'Ascendant et du Soleil (essence émotionnelle, mission, dharma)
- Maître d'Ascendant occidental ET védique
- Stelliums et configurations multiples
- Différences occidentale/védique enrichissent l'analyse

Génère une analyse complète d'environ 2000-2500 mots, riche et détaillée mais réaliste.

DONNÉES ASTROLOGIQUES :
<placements>
{placements_str}
</placements>"""

    # 🎯 Axes majeurs (seulement si présents et courts)
    if pf:
        prompt += f"""

AXES MAJEURS À PRIVILÉGIER :
{pf}"""

    # 🎯 RAG simplifié (seulement si court)
    if rag_snippets and len(rag_snippets.strip()) > 100:
        # Raccourcir le RAG si trop long
        rag_court = rag_snippets[:2000] + "..." if len(rag_snippets) > 2000 else rag_snippets
        prompt += f"""

CONTEXTE ENRICHI :
{rag_court}"""

    print(f"✅ Prompt optimisé construit: {len(prompt)} caractères")
    print(f"🔍 Début prompt: {prompt[:200]}...")

    if call_llm is not None:
        print(f"🔄 Appel via fonction personnalisée: {call_llm.__name__}")
        return call_llm(prompt)
    else:
        print(f"❌ Aucune fonction call_llm fournie !")
        return "❌ Erreur: aucune fonction de génération disponible"