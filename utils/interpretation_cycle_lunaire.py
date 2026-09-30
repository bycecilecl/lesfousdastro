"""Construction et validation d'une interprétation de révolution lunaire."""

from __future__ import annotations

import json
import re


CHAMPS_ATTENDUS = {
    "tonalite",
    "domaines_actives",
    "dynamique_emotionnelle",
    "tensions",
    "ressources",
    "fil_rouge",
    "question_journal",
    "experience",
}


def _aspects_internes_explicites(aspects: list[dict]) -> list[dict]:
    """Nomme sans ambiguïté les deux corps du thème de révolution."""
    resultat = []
    for aspect in aspects or []:
        corps_1 = aspect.get("point_1") or aspect.get("planete1")
        corps_2 = aspect.get("point_2") or aspect.get("planete2")
        nom_aspect = aspect.get("aspect")
        if not corps_1 or not corps_2 or not nom_aspect:
            continue
        resultat.append({
            "corps_1_cycle": corps_1,
            "aspect": nom_aspect,
            "corps_2_cycle": corps_2,
            "orbe": aspect.get("orbe"),
            "formulation": (
                f"{corps_1} du cycle {nom_aspect} "
                f"{corps_2} du cycle"
            ),
        })
    return resultat


POINTS_NATAUX_SECONDAIRES = {
    "Chiron",
    "Lune Noire",
    "Rahu",
    "Ketu",
    "Nœud Nord",
    "Nœud Sud",
    "Junon",
    "Cérès",
    "Pallas",
    "Vesta",
}
PLANETES_PERSONNELLES = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}


def _contact_secondaire_exceptionnel(
    aspect: dict,
    maitre_ascendant: str | None,
) -> bool:
    """Ne retient un point natal secondaire que s'il est vraiment dominant."""
    if aspect.get("point_natal") not in POINTS_NATAUX_SECONDAIRES:
        return True
    corps_autorises = set(PLANETES_PERSONNELLES)
    if maitre_ascendant:
        corps_autorises.add(maitre_ascendant)
    try:
        orbe = float(aspect.get("orbe"))
    except (TypeError, ValueError):
        return False
    return (
        aspect.get("aspect") == "conjonction"
        and orbe <= 1
        and aspect.get("planete_revolution") in corps_autorises
    )


def _contacts_nataux_explicites(
    *groupes: list[dict],
    maitre_ascendant: str | None = None,
) -> list[dict]:
    """Fusionne et déduplique les contacts cycle→natal en conservant les rôles."""
    resultat = []
    deja_vus = set()
    for groupe in groupes:
        for aspect in groupe or []:
            if not _contact_secondaire_exceptionnel(
                aspect,
                maitre_ascendant,
            ):
                continue
            corps_cycle = aspect.get("planete_revolution")
            point_natal = aspect.get("point_natal")
            nom_aspect = aspect.get("aspect")
            if not corps_cycle or not point_natal or not nom_aspect:
                continue
            cle = (
                corps_cycle,
                nom_aspect,
                point_natal,
                aspect.get("orbe"),
            )
            if cle in deja_vus:
                continue
            deja_vus.add(cle)
            resultat.append({
                "corps_cycle": corps_cycle,
                "aspect": nom_aspect,
                "point_natal": point_natal,
                "orbe": aspect.get("orbe"),
                "formulation": (
                    f"{corps_cycle} du cycle {nom_aspect} "
                    f"{point_natal} natal"
                ),
            })
    return resultat


def construire_messages_interpretation(prenom: str, lieu: str, theme: dict) -> list[dict]:
    priorites = theme.get("priorites") or {}
    placements_cycle = {
        nom: {
            "signe": position.get("signe"),
            "degre": position.get("degre"),
            "maison": position.get("maison"),
            "retrograde": bool(position.get("retrograde", False)),
        }
        for nom, position in (theme.get("planetes") or {}).items()
    }
    aspects_internes = _aspects_internes_explicites(
        priorites.get("aspects_internes_serres", [])
    )
    contacts_nataux = _contacts_nataux_explicites(
        priorites.get("aspects_nataux_serres", []),
        priorites.get("contacts_nataux_majeurs", []),
        maitre_ascendant=priorites.get("maitre_ascendant"),
    )
    contexte = {
        "instant_local": theme.get("instant_local"),
        "lieu": lieu,
        "placements_cycle": placements_cycle,
        "ascendant": priorites.get("ascendant"),
        "maitre_ascendant": priorites.get("maitre_ascendant"),
        "lune": priorites.get("lune"),
        "maisons_occupees": priorites.get("maisons_occupees", []),
        "amas_signes": priorites.get("amas_signes", []),
        "amas_maisons": priorites.get("amas_maisons", []),
        "dominantes_elements_modalites": priorites.get(
            "dominantes_elements_modalites",
            [],
        ),
        "configurations_majeures": priorites.get(
            "configurations_majeures",
            [],
        ),
        "planetes_angulaires": priorites.get("planetes_angulaires", []),
        "aspects_internes_cycle": aspects_internes,
        "contacts_cycle_vers_natal": contacts_nataux,
    }
    systeme = """Tu interprètes une révolution lunaire dans un cadre d'introspection astrologique.
Tu écris en français, tu tutoies la personne et tu adoptes un ton incarné, direct, chaleureux et précis.
Tu hiérarchises les facteurs au lieu de commenter chaque donnée séparément.
Tu présentes des dynamiques possibles, jamais des certitudes ni des prédictions factuelles.
Tu ne poses aucun diagnostic psychologique ou médical.
Tu ne mentionnes aucune configuration absente du contexte fourni.
La conjonction Lune de révolution–Lune natale n'est jamais une interprétation : elle définit seulement le retour lunaire.
Réponds exclusivement avec un objet JSON valide, sans markdown ni commentaire."""
    utilisateur = f"""Interprète le prochain cycle lunaire de {prenom or 'la personne'} à partir du contexte technique filtré ci-dessous.

Contrat JSON exact :
{{
  "tonalite": "synthèse générale en 2 paragraphes courts",
  "domaines_actives": [{{"titre": "domaine", "lecture": "lecture concrète"}}],
  "dynamique_emotionnelle": "ce qui peut se jouer intérieurement",
  "tensions": ["tension possible"],
  "ressources": ["ressource mobilisable"],
  "fil_rouge": "une phrase centrale",
  "question_journal": "une seule question ouverte",
  "experience": "une expérience concrète et réaliste à tenter"
}}

Règles :
- sélectionne 2 à 4 domaines activés ;
- relie les configurations entre elles au lieu de produire un catalogue ;
- croise toujours une dominante par signe avec les maisons réellement occupées par les mêmes planètes ;
- lorsqu'un amas significatif est détecté, traduis ensemble son signe, sa maison et les fonctions des planètes concernées ;
- ne transforme pas un simple comptage en dominante psychologique absolue : présente-le comme une tonalité du cycle ;
- n'attribue jamais mécaniquement à un signe ses clichés habituels : toute proposition doit être soutenue par la planète, la maison ou un aspect fourni ;
- n'utilise pas de vocabulaire dramatique ou ésotérique vague comme « ombre », « invisible », « perte », « pouvoir » ou « fusion » sans configuration précise qui le justifie ;
- formule la question du journal sans présupposer un déni, une peur, une blessure ou un comportement chez la personne ;
- respecte strictement le rôle indiqué dans les contacts : « corps_cycle » appartient à la révolution lunaire et « point_natal » au thème natal ; ne les inverse jamais et ne qualifie jamais le corps du cycle de natal ;
- distingue les aspects internes, qui relient deux corps du cycle, des contacts cycle→natal ;
- n'annonce jamais comme probable un événement concret tel qu'une rupture, une séparation, une rencontre ou un problème de santé ;
- ignore les dominantes et configurations vides ou secondaires face aux angles, à la Lune et aux aspects serrés ;
- cite naturellement les placements déterminants, sans noyer le texte sous la technique ;
- tensions et ressources contiennent chacune 1 à 3 éléments ;
- aucune recommandation thérapeutique, juridique, médicale ou financière ;
- n'invente aucune date intermédiaire : le contexte décrit la tonalité du cycle entier ;
- ne parle ni d'abonnement, ni de paiement, ni du fonctionnement de l'IA.

CONTEXTE TECHNIQUE
{json.dumps(contexte, ensure_ascii=False, default=str, indent=2)}"""
    return [
        {"role": "system", "content": systeme},
        {"role": "user", "content": utilisateur},
    ]


def valider_interpretation(reponse: str | dict) -> dict:
    if isinstance(reponse, str):
        texte = reponse.strip()
        bloc = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", texte, re.I | re.S)
        if bloc:
            texte = bloc.group(1).strip()
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as exc:
            raise ValueError("Claude n’a pas renvoyé un JSON valide.") from exc
    else:
        donnees = reponse

    if not isinstance(donnees, dict) or set(donnees) != CHAMPS_ATTENDUS:
        raise ValueError("La structure de l’interprétation est incorrecte.")
    champs_textes = {
        "tonalite",
        "dynamique_emotionnelle",
        "fil_rouge",
        "question_journal",
        "experience",
    }
    if any(not isinstance(donnees[champ], str) or not donnees[champ].strip() for champ in champs_textes):
        raise ValueError("Un texte obligatoire de l’interprétation est vide.")
    domaines = donnees["domaines_actives"]
    if not isinstance(domaines, list) or not 2 <= len(domaines) <= 4:
        raise ValueError("L’interprétation doit contenir entre 2 et 4 domaines.")
    if any(
        not isinstance(domaine, dict)
        or set(domaine) != {"titre", "lecture"}
        or not all(isinstance(valeur, str) and valeur.strip() for valeur in domaine.values())
        for domaine in domaines
    ):
        raise ValueError("Un domaine activé est incomplet.")
    for champ in ("tensions", "ressources"):
        valeurs = donnees[champ]
        if not isinstance(valeurs, list) or not 1 <= len(valeurs) <= 3:
            raise ValueError(f"Le champ {champ} doit contenir entre 1 et 3 éléments.")
        if any(not isinstance(valeur, str) or not valeur.strip() for valeur in valeurs):
            raise ValueError(f"Le champ {champ} contient un élément vide.")
    return donnees


def generer_interpretation_avec_claude(prenom: str, lieu: str, theme: dict) -> tuple[dict, dict]:
    from utils.claude_llm import CLIENT, MODEL

    messages = construire_messages_interpretation(prenom, lieu, theme)
    reponse = CLIENT.with_options(max_retries=0).messages.create(
        model=MODEL,
        system=messages[0]["content"],
        messages=[{"role": "user", "content": messages[1]["content"]}],
        temperature=0.35,
        max_tokens=2200,
    )
    if reponse.stop_reason != "end_turn":
        raise RuntimeError("Claude n'a pas terminé l'interprétation lunaire ; aucun second appel n'a été lancé.")
    contenu = "".join(
        bloc.text
        for bloc in reponse.content
        if getattr(bloc, "type", None) == "text"
    ).strip()
    interpretation = valider_interpretation(contenu)
    usage = {
        "tokens_entree": reponse.usage.input_tokens,
        "tokens_sortie": reponse.usage.output_tokens,
        "tokens_total": reponse.usage.input_tokens + reponse.usage.output_tokens,
    }
    return interpretation, usage
