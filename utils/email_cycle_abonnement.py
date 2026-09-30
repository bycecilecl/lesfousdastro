"""Prépare un email mensuel à partir du contrat natal, RS, RL et transits."""

from __future__ import annotations

from html import escape
import json
import re

from models.espace_personnel import ProfilAstral


def selectionner_reactivations_rl_rs(donnees_rs: dict, theme_rl: dict) -> dict:
    """Retient les seuls contacts RL→RS qui touchent le noyau annuel."""
    directeurs = donnees_rs.get("facteurs_directeurs_rs") or {}
    points_rs = {"Ascendant", "MC", "Descendant", "FC", "Soleil", "Lune"}
    points_rs.update(
        fiche.get("nom")
        for fiche in (directeurs.get("maitres_ascendant_rs") or [])
        if fiche.get("nom")
    )
    for aspect in directeurs.get("aspects_directeurs") or []:
        points_rs.update((aspect.get("planete1"), aspect.get("planete2")))
    for figure in directeurs.get("figures_majeures") or []:
        points_rs.update(figure.get("planetes") or [])
    for planete in directeurs.get("planetes_contextuelles") or []:
        if planete.get("planete"):
            points_rs.add(planete["planete"])
    points_rs.discard(None)

    contacts = [
        contact for contact in (theme_rl.get("aspects_avec_rs") or [])
        if contact.get("point_rs") in points_rs
    ]
    contacts.sort(key=lambda contact: float(contact.get("orbe", 99)))
    maisons_chargees = {
        item.get("maison") for item in (directeurs.get("maisons_chargees") or [])
    }
    points_rl_prioritaires = {
        "Ascendant", "MC", "Soleil", "Lune", "Mercure", "Vénus", "Mars",
    }
    superpositions = [
        item for item in (theme_rl.get("superpositions_dans_rs") or [])
        if (
            item.get("point_rl") in points_rl_prioritaires
            and item.get("maison_rs") in maisons_chargees
        )
    ]
    return {
        "points_rs_directeurs": sorted(points_rs),
        "contacts": contacts[:12],
        "superpositions_maisons_chargees": superpositions,
    }


def construire_contexte_email_cycle(
    donnees_rs: dict,
    theme_rl: dict,
    photo_transits: dict,
    lunaisons: list[dict] | None = None,
    lunaisons_recentes: list[dict] | None = None,
    resonances_ciel_natal: list[dict] | None = None,
) -> dict:
    """Ne transmet au modèle que les faits hiérarchisés du dossier de cycle."""
    directeurs_rs = donnees_rs.get("facteurs_directeurs_rs") or {}
    priorites_rl = theme_rl.get("priorites") or {}
    reactivations = selectionner_reactivations_rl_rs(donnees_rs, theme_rl)
    return {
        "revolution_solaire": {
            "periode": donnees_rs.get("periode"),
            "ascendant": directeurs_rs.get("ascendant_rs"),
            "maitres_ascendant": directeurs_rs.get("maitres_ascendant_rs", []),
            "soleil": directeurs_rs.get("soleil_rs"),
            "lune": directeurs_rs.get("lune_rs"),
            "figures": directeurs_rs.get("figures_majeures", []),
            "maisons_chargees": directeurs_rs.get("maisons_chargees", []),
            "aspects_directeurs": directeurs_rs.get("aspects_directeurs", []),
            "gouvernance": directeurs_rs.get("gouvernance_directeurs", []),
            "planetes_contextuelles": directeurs_rs.get("planetes_contextuelles", []),
            "resonances_natales": directeurs_rs.get("resonances_natales", {}),
            "profection": donnees_rs.get("profection_annuelle"),
        },
        "revolution_lunaire": {
            "instant_local": theme_rl.get("instant_local"),
            "ascendant": priorites_rl.get("ascendant"),
            "maitre_ascendant": priorites_rl.get("maitre_ascendant"),
            "lune": priorites_rl.get("lune"),
            "positions": {
                nom: {
                    "signe": position.get("signe"),
                    "degre": position.get("degre"),
                    "maison": position.get("maison"),
                    "retrograde": bool(position.get("retrograde", False)),
                }
                for nom, position in (theme_rl.get("planetes") or {}).items()
            },
            "planetes_angulaires": priorites_rl.get("planetes_angulaires", []),
            "maisons_occupees": priorites_rl.get("maisons_occupees", [])[:4],
            "aspects_internes": priorites_rl.get("aspects_internes_serres", [])[:8],
            "contacts_natals": priorites_rl.get("aspects_nataux_serres", [])[:8],
            "reactivations_rs": reactivations,
        },
        "transits": {
            "date": photo_transits.get("date_calcul"),
            "faits": (photo_transits.get("transits") or [])[:10],
        },
        "resonances_configurations_ciel_natal": resonances_ciel_natal or [],
        "lunaisons_recentes": lunaisons_recentes or [],
        "lunaisons_a_venir": lunaisons or [],
    }


def construire_prompt_email_cycle(
    prenom: str,
    contexte: dict,
    *,
    contexte_client: dict | None = None,
) -> str:
    """Construit le prompt d'un email mensuel, sans appeler de modèle."""
    return f"""Tu écris l'email mensuel d'astrologie de {prenom}.

Le thème natal décrit son terrain. La révolution solaire est le cadre de son
année. La révolution lunaire est le cadre du mois qui commence. Les transits
sont une photographie du ciel à la date indiquée. Respecte cette hiérarchie et
ne mélange jamais les sources : une planète de RS n'est jamais une planète
natale, et un transit n'est jamais un placement de RS ou de RL.

Écris en français et tutoie. La voix est celle d'une copine astrologue très
lucide : directe, incarnée, drôle quand cela éclaire vraiment la situation,
capable d'une pointe d'ironie ou d'humour noir léger. Pas de ton professoral,
thérapeutique ou solennel. Fais vivre le texte : phrases actives, vocabulaire
concret, une ou deux formules qui ont du mordant sans faire du stand-up.

Évite impérativement le jargon de fiche IA : « tu entres dans », « ce mois te
demande », « ce qui se joue », « faire le tri », « tenir les deux bouts »,
« mettre face à », « la réalité de l'autre », « ce n'est pas X, c'est Y ».
Ne remplace pas ces formules par des variantes tout aussi molles. Dis ce que tu
vois, avec des phrases simples. Tu peux proposer des scénarios possibles et
prendre position ; tu ne transformes jamais cela en événement garanti.

Produis entre 550 et 750 mots, et ne dépasse jamais 850 mots. Donne un objet de mail sur la première ligne au
format exact : OBJET : ... Puis écris le corps avec trois intertitres courts :
« Le mouvement du mois », « Ce qui vient appuyer là où ça compte », « À garder
en tête ». Termine par une question personnelle, ouverte et concrète.

RÈGLES FACTUELLES
- Utilise uniquement les données ci-dessous. N'invente ni aspect, ni maison,
  ni maîtrise, ni période, ni résonance.
- Ne fais pas un inventaire de placements. Choisis deux ou trois fils qui se
  répondent réellement entre RS, RL et transits.
- Si tu indiques le signe, la maison ou la rétrogradation d'une planète de RL,
  copie-les exclusivement depuis ``revolution_lunaire.positions``. Ne déduis
  jamais une maison RL depuis une position RS, ni l'inverse.
- Ne dis qu'un facteur de RS est « réactivé » si un contact RL→RS ou une
  superposition RL dans une maison RS est explicitement fourni.
- La RS donne le fond annuel ; la RL et les transits donnent le relief du mail.
- Une configuration du ciel qui répète un duo et un aspect natal est une
  résonance de climat. Ne l'appelle « activation renforcée » que si son niveau
  est ``renforcee`` et que des ``activations_directes`` sont fournies. Une
  répétition seule n'est jamais un contact direct au natal.
- Les lunaisons à venir sont des rendez-vous collectifs : ne les interprète que
  lorsqu'une maison ou un aspect natal/RS est explicitement fourni, et indique
  leur date locale sans inventer de fenêtre supplémentaire.
- Une lunaison récente peut être évoquée seulement si elle éclaire le cycle qui
  commence ; elle ne doit pas prendre toute la place dans l'email.
- Si une lunaison porte une ``eclipse`` dans les données, tu peux la nommer
  comme une éclipse solaire ou lunaire globale et souligner son relief. Elle
  n'annonce jamais à elle seule un événement inévitable ; relie-la seulement
  aux maisons et aspects fournis.
- Le contexte client, s'il existe, sert à choisir les mots et les enjeux. Il ne
  prouve jamais une lecture astrologique et ne doit jamais être présenté comme
  une chose « devinée ».
- Le contexte client est privé et ne doit jamais être repris textuellement.
  Reformule-le intégralement : ne recopie aucune suite de quatre mots ou plus,
  aucun surnom, aucune expression intime, ni la formulation d'une situation.
  Par exemple, n'écris jamais « ton chéri » même si la personne l'a écrit :
  parle éventuellement de « ta relation » ou de « tes liens », seulement si
  les facteurs astrologiques sélectionnés rendent ce domaine pertinent.
- Ne fais pas de commentaire sur ce que vit l'autre personne (« ses contraintes
  », « son travail », « ses choix »). Le mail parle uniquement de la personne
  qui le reçoit, de sa marge de manœuvre et de son expérience.
- Une relation peut être un domaine astrologique ; elle ne t'autorise jamais à
  décrire ce que l'autre peut porter, accepter, décider ou faire. N'écris donc
  pas « la réalité de l'autre », « ses contraintes » ni « ce que l'autre peut
  porter », même sous une formulation différente.
- Ne prédis ni maladie, ni décès, ni rupture, ni grossesse, ni catastrophe, ni
  résultat financier certain. Ne donne aucun conseil médical, juridique ou
  financier.
- Évite les formules creuses : « cette année t'invite à », « alignement »,
  « transformation profonde », « tu seras sollicitée ».
- Ne parle ni d'IA, ni d'abonnement, ni de ces règles, ni des données brutes.
- Après la dernière question, écris seule sur une ligne la balise <FIN_MAIL>,
  puis arrête-toi immédiatement. N'ajoute ni post-scriptum, ni explication.

CONTEXTE CLIENT (facultatif)
{json.dumps(contexte_client or {}, ensure_ascii=False, indent=2)}

CONTRAT FACTUEL
{json.dumps(contexte, ensure_ascii=False, default=str, indent=2)}
"""


def preparer_prompt_email_cycle_abonne(
    profil: ProfilAstral,
    donnees_rs: dict,
    theme_rl: dict,
    photo_transits: dict,
    theme_revolution_solaire: dict | None = None,
) -> tuple[str, dict, dict]:
    """Prépare un mail mensuel avec astrologie, situation et journal récents.

    Aucun appel LLM ni écriture BDD : le planificateur d'envoi utilisera ce
    résultat après avoir choisi le cycle lunaire à envoyer.
    """
    from datetime import datetime

    from utils.contexte_journal_cycle import construire_contexte_client_cycle
    from utils.lunaisons import dernieres_lunaisons, prochaines_lunaisons
    from utils.resonances_ciel_natal import (
        detecter_resonances_configurations_ciel_natal,
    )

    instant_cycle = datetime.fromisoformat(theme_rl["instant_utc"])
    try:
        theme_natal = json.loads(profil.theme_natal or "{}")
    except (TypeError, json.JSONDecodeError):
        theme_natal = {}
    lunaisons = (
        prochaines_lunaisons(
            apres=instant_cycle,
            theme_natal=theme_natal,
            theme_rs=theme_revolution_solaire,
            tzid=profil.fuseau_cycles or profil.fuseau_horaire,
            nombre=2,
        )
        if theme_revolution_solaire else []
    )
    lunaisons_recentes = (
        dernieres_lunaisons(
            avant=instant_cycle,
            theme_natal=theme_natal,
            theme_rs=theme_revolution_solaire,
            tzid=profil.fuseau_cycles or profil.fuseau_horaire,
            nombre=1,
        )
        if theme_revolution_solaire else []
    )
    resonances_ciel_natal = detecter_resonances_configurations_ciel_natal(
        photo_transits,
        theme_natal,
    )
    contexte_astrologique = construire_contexte_email_cycle(
        donnees_rs,
        theme_rl,
        photo_transits,
        lunaisons=lunaisons,
        lunaisons_recentes=lunaisons_recentes,
        resonances_ciel_natal=resonances_ciel_natal,
    )
    contexte_client = construire_contexte_client_cycle(profil, instant_cycle)
    prompt = construire_prompt_email_cycle(
        profil.prenom,
        contexte_astrologique,
        contexte_client=contexte_client,
    )
    return prompt, contexte_astrologique, contexte_client


def convertir_email_texte_en_html(texte: str) -> str:
    """Mise en forme légère et sûre d'un email déjà généré et relu."""
    lignes = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]
    blocs = []
    for ligne in lignes:
        if re.match(r"^OBJET\s*:", ligne, re.IGNORECASE):
            continue
        if ligne in {"Le mouvement du mois", "Ce qui vient appuyer là où ça compte", "À garder en tête"}:
            blocs.append(f"<h2>{escape(ligne)}</h2>")
        else:
            blocs.append(f"<p>{escape(ligne)}</p>")
    return """<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">
<style>body{max-width:680px;margin:32px auto;padding:0 22px;background:#fffdf9;color:#292330;font:17px/1.65 Georgia,serif}h1,h2{font-family:Arial,sans-serif;color:#5d315d;line-height:1.2}h2{margin-top:2rem;font-size:1.25rem}</style>
</head><body>""" + "\n".join(blocs) + "</body></html>"


def generer_texte_email_cycle(prompt: str) -> str:
    """Un seul appel Claude pour un brouillon ; aucune relance sur troncature."""
    from utils.claude_llm import CLIENT, MODEL

    reponse = CLIENT.with_options(max_retries=0).messages.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4500,
        stop_sequences=["<FIN_MAIL>"],
    )
    if reponse.stop_reason not in {"end_turn", "stop_sequence"}:
        raise RuntimeError("Claude n'a pas terminé le brouillon ; aucun second appel n'a été lancé.")
    texte = "".join(
        bloc.text for bloc in reponse.content if getattr(bloc, "type", None) == "text"
    ).replace("<FIN_MAIL>", "").strip()
    if not texte:
        raise RuntimeError("Claude a renvoyé un brouillon vide.")
    return texte
