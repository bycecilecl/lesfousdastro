"""Préparation et validation d'une synthèse courte des enjeux de Transits.

Ce module ne contacte aucun fournisseur d'IA et n'écrit dans aucune base.
"""

from dataclasses import dataclass
import json
import re


NOMBRE_MIN_ENJEUX = 4
NOMBRE_MAX_ENJEUX = 5
LONGUEUR_MAX_ENJEU = 240


class ReponseEnjeuxInvalide(ValueError):
    """La synthèse ne respecte pas le format court attendu."""


@dataclass(frozen=True)
class EnjeuExtrait:
    contenu: str
    references_astrologiques: list[str]
    cle_section: str


def _nettoyer(texte):
    return re.sub(r"\s+", " ", str(texte or "")).strip()


def _charger_json(reponse):
    if not isinstance(reponse, str):
        return reponse
    texte = reponse.strip()
    bloc = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", texte, re.I | re.S)
    if bloc:
        texte = bloc.group(1).strip()
    return json.loads(texte)


def construire_messages_enjeux_transits(sections):
    """Construit la consigne d'une synthèse de quatre ou cinq lignes."""
    sections_valides = []
    for section in sections:
        cle = _nettoyer(section.get("cle_section"))
        titre = _nettoyer(section.get("titre"))
        contenu = _nettoyer(section.get("contenu"))
        if cle and titre and contenu:
            sections_valides.append(f"SECTION [{cle}] — {titre}\n{contenu}")
    if not sections_valides:
        raise ValueError("Aucune section de Transits exploitable n'a été fournie.")

    systeme = """Tu synthétises un rapport astrologique de Transits déjà rédigé.
Tu ne recrées pas le rapport : tu en fais ressortir seulement les grands enjeux de la période.
Tu décris une météo temporaire et jamais un trait permanent, un diagnostic ou un événement certain.
Tu conserves le tutoiement et le ton direct du rapport sans augmenter son degré de certitude.
Réponds exclusivement avec un objet JSON valide, sans markdown ni commentaire."""

    utilisateur = f"""Produis 4 ou 5 enjeux distincts à partir du rapport ci-dessous.

Contrat JSON obligatoire :
{{
  "enjeux": [
    {{
      "contenu": "une seule phrase courte sur un enjeu dominant de la période",
      "references_astrologiques": ["configuration explicitement citée dans le rapport"],
      "cle_section": "clé exacte de la section principale"
    }}
  ]
}}

Règles :
- exactement 4 ou 5 enjeux ;
- une seule phrase par enjeu, 240 caractères maximum ;
- pas de titre, pas de paragraphe explicatif, pas de conseil développé ;
- privilégie les tendances répétées ou fortement structurantes ;
- fusionne les transits qui racontent le même enjeu au lieu de les énumérer ;
- ne transforme jamais une possibilité temporaire en vérité sur la personne ;
- n'annonce aucun événement concret, diagnostic ou problème de santé ;
- chaque enjeu doit être soutenu par la section indiquée ;
- une à trois références astrologiques maximum par enjeu, toutes présentes dans le rapport ;
- ignore les listes techniques secondaires lorsqu'elles n'ajoutent pas un enjeu dominant.

SECTIONS DU RAPPORT
{chr(10).join(chr(10) + section for section in sections_valides)}"""
    return [
        {"role": "system", "content": systeme},
        {"role": "user", "content": utilisateur},
    ]


def valider_reponse_enjeux_transits(reponse, sections):
    """Valide le nombre, la brièveté et la provenance des enjeux."""
    try:
        donnees = _charger_json(reponse)
    except json.JSONDecodeError as erreur:
        raise ReponseEnjeuxInvalide("La réponse n'est pas un JSON valide.") from erreur

    if not isinstance(donnees, dict) or set(donnees) != {"enjeux"}:
        raise ReponseEnjeuxInvalide("La réponse doit contenir uniquement 'enjeux'.")
    enjeux = donnees["enjeux"]
    if not isinstance(enjeux, list) or not NOMBRE_MIN_ENJEUX <= len(enjeux) <= NOMBRE_MAX_ENJEUX:
        raise ReponseEnjeuxInvalide("La réponse doit contenir 4 ou 5 enjeux.")

    cles_sections = {
        _nettoyer(section.get("cle_section"))
        for section in sections
        if _nettoyer(section.get("cle_section")) and _nettoyer(section.get("contenu"))
    }
    resultat = []
    champs = {"contenu", "references_astrologiques", "cle_section"}
    for index, enjeu in enumerate(enjeux, 1):
        if not isinstance(enjeu, dict) or set(enjeu) != champs:
            raise ReponseEnjeuxInvalide(f"Enjeu {index} : champs incorrects.")
        contenu = _nettoyer(enjeu["contenu"])
        cle_section = _nettoyer(enjeu["cle_section"]).strip("[]")
        references = enjeu["references_astrologiques"]
        if not contenu or len(contenu) > LONGUEUR_MAX_ENJEU:
            raise ReponseEnjeuxInvalide(f"Enjeu {index} : texte vide ou trop long.")
        if cle_section not in cles_sections:
            raise ReponseEnjeuxInvalide(f"Enjeu {index} : section inconnue.")
        if not isinstance(references, list) or not 1 <= len(references) <= 3:
            raise ReponseEnjeuxInvalide(f"Enjeu {index} : références invalides.")
        references_nettoyees = [_nettoyer(reference) for reference in references]
        if any(not reference for reference in references_nettoyees):
            raise ReponseEnjeuxInvalide(f"Enjeu {index} : référence vide.")
        resultat.append(EnjeuExtrait(contenu, references_nettoyees, cle_section))
    return resultat


def generer_enjeux_transits_avec_claude(sections, modele=None):
    """Appelle Claude explicitement puis retourne les enjeux validés et l'usage."""
    from utils.claude_espace import CLIENT, MODEL, creer_message_claude, ouvrir_flux_claude

    messages = construire_messages_enjeux_transits(sections)
    reponse = creer_message_claude(client=CLIENT, 
        model=modele or MODEL,
        system=messages[0]["content"],
        messages=[{"role": "user", "content": messages[1]["content"]}],
        temperature=0.2,
        max_tokens=900,
    )
    contenu = "".join(
        bloc.text
        for bloc in reponse.content
        if getattr(bloc, "type", None) == "text"
    ).strip()
    enjeux = valider_reponse_enjeux_transits(contenu, sections)
    usage = {
        "tokens_entree": reponse.usage.input_tokens,
        "tokens_sortie": reponse.usage.output_tokens,
        "tokens_total": reponse.usage.input_tokens + reponse.usage.output_tokens,
    }
    return enjeux, usage
