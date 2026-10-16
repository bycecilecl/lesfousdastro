"""Présentation des faits dans les prompts ; calculs et archives brutes conservés."""

import json

from ..memoire_redaction import compacter_faits as _compacter_faits


CONSIGNE_RETRO_SEULE = "Ne mentionne pas qu'une planète est directe ou non rétrograde. Mentionne seulement sa rétrogradation lorsqu'elle éclaire la lecture."


def retirer_etat_direct(objet):
    """Copie sans retrograde:false ; aucun changement d'un état rétrograde ou inconnu."""
    if isinstance(objet, dict):
        return {k: retirer_etat_direct(v) for k, v in objet.items()
                if not (k == "retrograde" and v is False)}
    if isinstance(objet, list):
        return [retirer_etat_direct(v) for v in objet]
    return objet


def compacter_faits(faits):
    return retirer_etat_direct(_compacter_faits(faits))


def normaliser_prompt_comparaison(prompt):
    """Tolère les seules corrections de présentation des rétrogradations validées."""
    texte, separateur, donnees = prompt.partition("\nDONNÉES DU BLOC 1\n")
    if not separateur:
        raise ValueError("Données du bloc 1 absentes du prompt de comparaison.")
    texte = texte.replace(CONSIGNE_RETRO_SEULE + "\n", "")
    texte = texte.replace("pluton_retrograde est un fait calculé RS. ", "")
    entree = retirer_etat_direct(json.loads(donnees))
    reperes = entree.get("faits_calcules", {}).get("REPERES_CALCULES", {})
    reperes.pop("pluton_retrograde", None)
    return texte + separateur + json.dumps(entree, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
