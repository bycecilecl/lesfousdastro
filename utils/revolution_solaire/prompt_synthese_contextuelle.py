"""Synthèse finale : le seul stade qui reçoit le vécu confié par la personne."""

from __future__ import annotations

import json
from .accords import genre_grammatical


TITRE_SYNTHESE = "## Ce que cette année te demande vraiment"


def construire_prompt_synthese_contextuelle(corps: str, contexte_client: dict | None, genre: str = "") -> str:
    contexte = json.dumps(contexte_client or {}, ensure_ascii=False, indent=2)
    accord = genre_grammatical(genre)
    return f"""Tu rédiges uniquement la synthèse finale d'une révolution solaire, en français et au tutoiement. Accord grammatical demandé : {accord}. Si l'accord est précisé, utilise-le sans point médian ni double forme.

Le corps du rapport a été écrit SANS connaître le vécu de la personne. Il constitue la seule interprétation astrologique autorisée. Relie maintenant ses fils directeurs aux informations qu'elle a elle-même données, lorsqu'un lien est justifié. Un fait confié n'est jamais une preuve que l'astrologie l'avait prédit.

Rédige 350 à 500 mots, en paragraphes fluides, sans titre : il sera ajouté par le programme. N'ajoute aucun aspect, placement, transit, date, domaine ou événement astrologique absent du corps. Si le contexte est vide ou sans rapport avec le corps, fais une synthèse de l'année sans prétendre connaître la vie de la personne.

Montre comment deux ou trois enjeux déjà développés interagissent et quelles marges de choix se dessinent. N'énumère pas les configurations et ne refais pas la chronologie. Ne recopie ni les exemples, ni les images, ni les formules du corps ; apporte un éclairage nouveau. Varie les mots et les constructions de phrases : une même amorce ne doit pas revenir plus de deux fois. Donne une direction concrète, sans morale ni injonction. Ne récapitule pas les mois déjà racontés. Ne conditionne jamais la réussite financière ou amoureuse à une attitude supposée de la personne : pas de « ton projet décollera si », « l’amour viendra quand » ou équivalent. Distingue les pistes possibles des résultats garantis ; les difficultés ne prouvent aucun défaut personnel.

N'étends pas une confidence à toute l'année. Ne présente pas une hypothèse comme un fait, n'annonce aucun diagnostic, grossesse, décès, infidélité ou résultat financier certain. Le champ « sante » sert seulement à situer le vécu, jamais à faire un pronostic médical. Ne reproduis pas textuellement une confidence intime.

Après la dernière phrase, écris seule sur une ligne la balise <FIN_SYNTHESE>.

CORPS DU RAPPORT — déjà rédigé sans contexte personnel
{corps}

CONTEXTE FOURNI PAR LA PERSONNE — réservé à cette synthèse
{contexte}
"""


def assembler_rapport(corps: str, synthese: str) -> str:
    """Assemble les deux textes sans laisser Claude réécrire l'analyse neutre."""
    corps = corps.replace("<FIN_RAPPORT>", "").strip()
    synthese = synthese.replace("<FIN_SYNTHESE>", "").strip()
    if not corps or not synthese:
        raise ValueError("Corps ou synthèse de révolution solaire vide.")
    if TITRE_SYNTHESE in corps:
        raise ValueError("Le corps neutre contient déjà la synthèse finale.")
    if synthese.startswith(TITRE_SYNTHESE):
        synthese = synthese[len(TITRE_SYNTHESE):].strip()
    return f"{corps}\n\n{TITRE_SYNTHESE}\n\n{synthese}"
