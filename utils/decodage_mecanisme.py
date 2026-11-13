"""Questions et lecture des réponses du décodage manuel ; aucun appel IA."""

import json


class ConflitDecodage(Exception):
    """Une autre sauvegarde de cet épisode est intervenue entre-temps."""


ETAPES_DECODAGE = (
    {
        "titre": "Photographier la scène",
        "questions": (
            ("declencheur", "Quel est le déclencheur exact, sans interprétation, juste le fait ?"),
            ("corps", "Que se passe-t-il dans mon corps dans les premières secondes ?"),
            ("premiere_pensee", "Quelle est la toute première pensée qui surgit ?"),
        ),
    },
    {
        "titre": "Trouver l’émotion cachée",
        "aide": "La colère cache souvent une autre émotion, comme la peur ou la tristesse.",
        "questions": (
            ("emotion_visible", "Quelle émotion est visible ?"),
            ("emotion_cachee", "Quelle émotion se cache derrière ?"),
            ("reactions", "Quelles ont été mes réactions ?"),
            ("consequences", "Quelles conséquences cela a-t-il pour moi, dans cette situation ou pour les personnes concernées ?"),
        ),
    },
    {
        "titre": "Débusquer la croyance",
        "questions": (
            ("sens", "Qu’est-ce que je me dis sur moi ou sur les autres à cause de cette situation ?"),
            ("pire", "Si c’était vrai, quel serait le pire ?"),
            ("besoin_manquant", "Quel besoin n’est pas comblé à ce moment-là ?"),
        ),
    },
    {
        "titre": "Remonter à la source",
        "questions": (
            ("souvenirs", "Est-ce que cette réaction me rappelle d’autres moments de ma vie ?"),
            ("comprehension_ancienne", "Si un souvenir me revient, qu’avais-je compris de cette situation ?"),
            ("protection_ancienne", "Comment avais-je essayé de me protéger ?"),
        ),
        "aide": "Tu peux noter ce qui te vient, laisser une question vide ou répondre « Je ne sais pas encore ».",
    },
    {
        "titre": "Comprendre à quoi ça sert",
        "questions": (
            ("eviter", "Qu’est-ce que ce mécanisme essaie de m’éviter de ressentir ?"),
            ("cout", "Qu’est-ce qu’il me coûte ?"),
            ("obtient", "Est-ce qu’il m’aide à obtenir ce que je cherche vraiment ?"),
        ),
    },
    {
        "titre": "Transformer",
        "questions": (
            ("autre_explication", "Qu’est-ce qui pourrait expliquer cette situation, à part ma première idée ?"),
            ("besoin_reponse", "De quoi ai-je besoin et comment puis-je y répondre ? Si cela implique quelqu’un, comment le demander ?"),
            ("prochain_geste", "Quel tout petit geste différent puis-je tester la prochaine fois ?"),
        ),
    },
)

CHAMPS_DECODAGE = tuple(cle for etape in ETAPES_DECODAGE for cle, _ in etape["questions"])


AIDES_DECODAGE = {
    "declencheur": {
        "amorce": "Si une caméra avait filmé la scène, qu’aurait-elle enregistré ?",
    },
    "corps": {
        "amorce": "Dans les premières secondes, j’ai remarqué…",
    },
    "premiere_pensee": {
        "amorce": "À cet instant, je me suis immédiatement dit que…",
    },
    "emotion_visible": {
        "amorce": "Ce qui se voyait, c’était… Mais à l’intérieur, je ressentais…",
    },
    "emotion_cachee": {
        "amorce": "Derrière ma colère, mon retrait ou mon agitation, qu’est-ce qui me touche autant ?",
    },
    "reactions": {
        "amorce": "J’ai dit, fait, évité ou gardé pour moi…",
    },
    "consequences": {
        "amorce": "Juste après ma réaction, il s’est passé… Puis…",
    },
    "sens": {
        "amorce": "Par exemple : « Si je fais une erreur, je suis nulle » ou « S’il ne répond pas, je ne compte pas ». Dans ma situation, je me dis…",
    },
    "pire": {
        "amorce": "Ce que je redoute le plus dans cette idée, c’est…",
    },
    "besoin_manquant": {
        "amorce": "J’aurais eu besoin de… Sécurité, attention, reconnaissance, preuve d’amour, liberté… ou autre chose qui compte pour moi.",
    },
    "souvenirs": {
        "amorce": "Cette sensation m’est-elle familière ? Dans quelles situations l’ai-je déjà ressentie ?",
    },
    "comprehension_ancienne": {
        "amorce": "À ce moment-là, j’avais compris sur moi, sur les autres ou sur ce que je devais faire pour être aimée, acceptée ou tranquille…",
    },
    "protection_ancienne": {
        "amorce": "Pour me protéger, j’avais commencé à… ou décidé de ne plus…",
    },
    "eviter": {
        "amorce": "Sur le moment, cette réaction m’évite de ressentir…",
    },
    "cout": {
        "amorce": "Sur le moment, ma réaction me permet de… Mais ensuite, elle me coûte…",
    },
    "obtient": {
        "amorce": "Ce que je cherchais, c’était… Ce que j’ai obtenu, c’est…",
    },
    "autre_explication": {
        "amorce": "Par exemple : un message sans réponse peut aussi vouloir dire que la personne est occupée. Dans ma situation, une autre possibilité serait…",
    },
    "besoin_reponse": {
        "amorce": "Ce dont j’ai besoin, c’est… Pour y répondre, je pourrais…",
    },
    "prochain_geste": {
        "amorce": "Je peux ressentir la même chose et choisir un petit geste différent : la prochaine fois, je pourrais…",
    },
}


def lire_reponses_decodage(texte):
    try:
        reponses = json.loads(texte or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(reponses, dict):
        return {}
    return {cle: reponses[cle] for cle in CHAMPS_DECODAGE
            if isinstance(reponses.get(cle), str)}


def reponses_depuis_formulaire(formulaire):
    reponses = {cle: formulaire.get(cle, "").strip() for cle in CHAMPS_DECODAGE}
    if any(len(texte) > 6000 for texte in reponses.values()):
        raise ValueError("Une réponse dépasse 6 000 caractères. Raccourcis-la pour pouvoir enregistrer.")
    return reponses
