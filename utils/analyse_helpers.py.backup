# ────────────────────────────────────────────────
# FICHIER : utils/analyse_helpers.py
# Rôle : utilitaires “legacy” pour :
#   1) Générer un petit corpus RAG (HTML) à partir des points forts
#   2) Charger un prompt depuis un fichier Jinja2
#   3) Valider minimalement la présence de clés dans le dict thème
#
# ⚠️ STATUT : optionnel / non critique dans le flux actuel.
#   - Le pipeline principal utilise plutôt rag_utils_optimized.generer_corpus_rag_optimise
#   - Cette lib peut être archivée si non utilisée.
# ────────────────────────────────────────────────

from routes.archives.rag_utils import interroger_rag
from jinja2 import Template
import os

# ────────────────────────────────────────────────
# FONCTION : generer_corpus_rag(points_forts)
# Objectif : Pour chaque “point fort”, interroge le RAG et
#            renvoie un bloc HTML concaténé (simple aperçu).
# Entrée :  points_forts (list[str])
# Sortie :  str (HTML)
# Remarque : Legacy — le pipeline actuel préfère la version “_optimise”.
# ────────────────────────────────────────────────

def generer_corpus_rag(points_forts):
    """Centralise la génération du corpus RAG"""
    questions = [f"Signification astrologique de : {point}" for point in points_forts]
    corpus = []
    for question in questions:
        try:
            réponse = interroger_rag(question)
            corpus.append(f"<div class='rag-item'><strong>{question}</strong><br>{réponse}</div>")
        except Exception as e:
            corpus.append(f"<div class='rag-item error'><strong>{question}</strong><br>\u274c Erreur : {e}</div>")
    return "\n".join(corpus)


# ────────────────────────────────────────────────
# FONCTION : charger_prompt_template(template_path, variables)
# Objectif : Charger un template Jinja2 depuis un fichier
#            et remplir les variables pour produire un prompt.
# Entrées : template_path (str), variables (dict)
# Sortie :  str (prompt prêt pour le LLM)
# ⚠️ Le rendu n’est pas sandboxé (Jinja2 direct).
# ────────────────────────────────────────────────
def charger_prompt_template(template_path, variables):
    """
    Charge le prompt depuis un fichier template (Jinja2)
    :param template_path: chemin vers le fichier de template
    :param variables: dictionnaire avec les données à injecter
    :return: prompt string prêt à envoyer au LLM
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template introuvable : {template_path}")

    with open(template_path, encoding="utf-8") as f:
        template = Template(f.read())
    return template.render(**variables)


# ────────────────────────────────────────────────
# FONCTION : valider_donnees_astrologiques(data)
# Objectif : Vérifier rapidement la présence de clés essentielles.
# Entrée : data (dict)
# Sortie : None (raise ValueError si clé manquante)
# Remarque : doublon léger avec valider_donnees_avant_analyse().
# ────────────────────────────────────────────────
def valider_donnees_astrologiques(data):
    """Valide la structure des données avant traitement"""
    required_keys = ["planetes", "aspects", "planetes_vediques", "maisons", "maitre_ascendant"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Clé manquante dans les données : {key}")