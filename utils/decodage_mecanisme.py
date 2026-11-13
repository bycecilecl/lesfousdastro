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
            ("sens", "Qu’est-ce que ça veut dire pour moi ?"),
            ("pire", "Si c’était vrai, quel serait le pire ?"),
            ("besoin_manquant", "Quel besoin n’est pas comblé à ce moment-là ?"),
        ),
        "aide": "Sécurité, attention, reconnaissance, preuve d’amour… ou autre chose qui compte pour toi.",
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
            ("autre_explication", "Quelle autre explication, plus douce et tout aussi plausible, pourrais-je me donner ?"),
            ("besoin_reponse", "De quoi ai-je besoin et comment puis-je y répondre ? Si cela implique quelqu’un, comment le demander ?"),
            ("prochain_geste", "Quel tout petit geste différent puis-je tester la prochaine fois ?"),
        ),
    },
)

CHAMPS_DECODAGE = tuple(cle for etape in ETAPES_DECODAGE for cle, _ in etape["questions"])


AIDES_DECODAGE = {
    "declencheur": {
        "amorce": "Si une caméra avait filmé la scène, qu’aurait-elle enregistré ?",
        "piste": "Décris ce qui s’est passé, ce qui a été dit ou ce qui n’a pas eu lieu. Qu’est-ce qui a déclenché ta réaction ?",
    },
    "corps": {
        "amorce": "Dans les premières secondes, j’ai remarqué…",
        "piste": "Une tension, une chaleur, la gorge serrée, une agitation… Qu’as-tu réellement remarqué, si quelque chose t’a marquée ?",
    },
    "premiere_pensee": {
        "amorce": "À cet instant, je me suis immédiatement dit que…",
        "piste": "Retrouve les mots qui te sont venus avant de réfléchir ou de te raisonner. Quelle phrase a traversé ton esprit ?",
    },
    "emotion_visible": {
        "amorce": "Ce qui se voyait, c’était… Mais à l’intérieur, je ressentais…",
        "piste": "Quelle émotion prenait le plus de place ? Était-elle exprimée, retenue ou difficile à nommer ?",
    },
    "emotion_cachee": {
        "amorce": "Derrière ma colère, mon retrait ou mon agitation, qu’est-ce qui me touche autant ?",
        "piste": "Si tu restes un instant avec ce que tu ressens, qu’est-ce qui apparaît derrière ta première réaction ?",
    },
    "reactions": {
        "amorce": "J’ai dit, fait, évité ou gardé pour moi…",
        "piste": "Pense aussi au silence, au retrait, au fait de te justifier ou de faire comme si tout allait bien. Comment as-tu réagi dans cette situation ?",
    },
    "consequences": {
        "amorce": "Juste après ma réaction, il s’est passé… Puis…",
        "piste": "Qu’est-ce que tu as observé pour toi, dans la situation ou pour les personnes concernées ? Qu’est-ce qui reste encore difficile à comprendre ?",
    },
    "sens": {
        "amorce": "Si cette situation signifie bien ce que je crois, alors ça voudrait dire que je suis… ou que je ne peux pas…",
        "piste": "Qu’est-ce que tu conclus sur toi, sur ta place ou sur ce que tu peux attendre de cette situation ?",
    },
    "pire": {
        "amorce": "Ce que je redoute le plus dans cette idée, c’est…",
        "piste": "Qu’est-ce qui serait si douloureux ou difficile à accepter si cette pensée était vraie ? Tu peux t’arrêter là où tu le souhaites.",
    },
    "besoin_manquant": {
        "amorce": "J’aurais eu besoin d’entendre, de recevoir ou de pouvoir faire…",
        "piste": "Qu’est-ce qui t’aurait aidée à ce moment-là : de la sécurité, du temps, une présence, de la liberté, une limite, une reconnaissance… ?",
    },
    "souvenirs": {
        "amorce": "Cette sensation m’est-elle familière ? Dans quelles situations l’ai-je déjà ressentie ?",
        "piste": "Un souvenir précis, une période ou une situation récente peuvent te venir. Si rien ne vient, « Je ne sais pas encore » suffit.",
    },
    "comprehension_ancienne": {
        "amorce": "À ce moment-là, j’avais compris sur moi, sur les autres ou sur ce que je devais faire pour être aimée, acceptée ou tranquille…",
        "piste": "Si tu repenses à cette situation, quelle conclusion en avais-tu tirée avec ce que tu comprenais à l’époque ?",
    },
    "protection_ancienne": {
        "amorce": "Pour me protéger, j’avais commencé à… ou décidé de ne plus…",
        "piste": "Qu’est-ce que cette manière de faire te permettait de préserver ou d’éviter à ce moment-là ?",
    },
    "eviter": {
        "amorce": "Sur le moment, cette réaction m’évite de ressentir…",
        "piste": "Que craindrais-tu de ressentir ou d’affronter si tu ne réagissais pas ainsi ?",
    },
    "cout": {
        "amorce": "Sur le moment, ma réaction me permet de… Mais ensuite, elle me coûte…",
        "piste": "Quelles conséquences remarques-tu sur ton énergie, tes choix, ton travail, tes projets ou tes liens ?",
    },
    "obtient": {
        "amorce": "Ce que je cherchais, c’était… Ce que j’ai obtenu, c’est…",
        "piste": "Qu’est-ce qui t’a aidée ? Qu’est-ce qui n’a pas répondu à ton besoin, ou seulement pour un moment ?",
    },
    "autre_explication": {
        "amorce": "Une autre façon de comprendre cette situation pourrait être…",
        "piste": "Quelle explication plus douce reste tout aussi plausible avec ce que tu sais de la situation ?",
    },
    "besoin_reponse": {
        "amorce": "Ce dont j’ai besoin, c’est… Pour y répondre, je pourrais…",
        "piste": "Quelle part dépend de toi ? Si quelqu’un est concerné, quelle demande concrète pourrais-tu formuler ?",
    },
    "prochain_geste": {
        "amorce": "Je peux ressentir la même chose et choisir un petit geste différent : la prochaine fois, je pourrais…",
        "piste": "Choisis un geste assez petit pour pouvoir l’essayer : prendre un moment, poser une question, exprimer un besoin, faire une pause… Qu’aimerais-tu tenter ?",
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
