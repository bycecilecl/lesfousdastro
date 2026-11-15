"""Conjonctions collectives de la Lune et lectures locales pour le calendrier."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import swisseph as swe

from utils.calendrier_lectures import DOMAINES
from utils.calendrier_personnel import _bisect, _longitude
from utils.lunaisons import EPHEMERIS_PATH
from utils.transits.maisons import extraire_cuspides, trouver_maison

# Sélection éditoriale : intensités et ressources, sans multiplier les aspects.
LECTURES = {
    "Vénus": "Le besoin de douceur, de lien ou de plaisir peut se faire plus présent. Observe ce qui te fait du bien et la place que tu lui accordes.",
    "Mars": "Une émotion peut vite chercher à devenir une action : affirmer un besoin, répondre du tac au tac ou poser une limite. Observe ce qui te mobilise avant de décider comment agir.",
    "Jupiter": "L’enthousiasme, la générosité ou les attentes peuvent prendre de l’ampleur. Observe ce qui t’ouvre des perspectives et ce que tu as envie de nourrir.",
    "Saturne": "Les besoins affectifs peuvent rencontrer la question des limites, des responsabilités ou du manque. Observe le soutien concret dont tu aurais besoin et ce qui t’aide à tenir sans tout porter.",
    "Uranus": "Le besoin d’espace ou de changement peut se faire sentir plus vivement. Observe ce qui te donne envie de sortir d’une habitude et la liberté que tu cherches à retrouver.",
    "Neptune": "La sensibilité, l’imaginaire ou la perméabilité aux ambiances peuvent être au premier plan. Observe ce qui vient de tes propres ressentis et ce que tu absorbes autour de toi.",
    "Pluton": "Les émotions peuvent être plus intenses, avec quelque chose qui remonte ou devient difficile à contenir. Observe ce que cela touche en profondeur, sans confondre l’intensité du ressenti avec l’urgence d’agir.",
}
LECTURES_MAISONS = {
    1: "Dans ta maison natale 1, cela peut éclairer ta façon de te présenter, d’affirmer tes besoins et de prendre ta place.",
    2: "Dans ta maison natale 2, observe ce qui touche ta sécurité matérielle, tes ressources et la valeur que tu t’accordes.",
    3: "Dans ta maison natale 3, observe tes échanges, tes pensées et ce qui se joue avec ton entourage proche.",
    4: "Dans ta maison natale 4, observe ton besoin de sécurité intérieure, tes liens familiaux et ce qui se joue dans ton foyer ou ton intimité.",
    5: "Dans ta maison natale 5, observe la place de tes envies, du plaisir et de la création, ainsi que tes relations avec les enfants si cela te concerne.",
    6: "Dans ta maison natale 6, observe ton quotidien, ton rythme et la place que prennent le travail et les obligations.",
    7: "Dans ta maison natale 7, observe ce que les relations, les attentes réciproques et les engagements viennent mobiliser en toi.",
    8: "Dans ta maison natale 8, observe ce qui se joue autour de l’intimité, de la confiance, du partage et des ressources communes.",
    9: "Dans ta maison natale 9, observe ce qui touche tes convictions, ta recherche de sens et tes envies d’explorer ou d’apprendre.",
    10: "Dans ta maison natale 10, observe ta place professionnelle, ce que tu souhaites accomplir et ton rapport au regard extérieur.",
    11: "Dans ta maison natale 11, observe tes liens amicaux, les groupes auxquels tu appartiens et tes projets pour la suite.",
    12: "Dans ta maison natale 12, observe ton besoin de retrait et de repos, ainsi que les ressentis que tu gardes habituellement pour toi.",
}


@lru_cache(maxsize=48)
def _conjonctions_exactes(debut_utc, fin_utc):
    """Instants exacts à une seconde environ ; calcul commun à tous les membres."""
    debut, fin = datetime.fromisoformat(debut_utc), datetime.fromisoformat(fin_utc)
    swe.set_ephe_path(str(EPHEMERIS_PATH))
    pas = timedelta(hours=3)
    instants = [debut - pas]
    while instants[-1] < fin:
        instants.append(min(instants[-1] + pas, fin))
    lunes = [_longitude(instant, "Lune") for instant in instants]
    resultat = []
    for planete in LECTURES:
        ecarts = [(lune - _longitude(instant, planete) + 180) % 360 - 180
                  for instant, lune in zip(instants, lunes)]
        for index in range(1, len(instants)):
            gauche, droite = ecarts[index - 1], ecarts[index]
            # Le saut à l’opposition ne doit pas être pris pour une conjonction.
            if not (gauche < 0 <= droite and abs(droite - gauche) < 180):
                continue
            instant = _bisect(instants[index - 1], instants[index],
                lambda t: (_longitude(t, "Lune") - _longitude(t, planete) + 180) % 360 - 180)
            if debut <= instant < fin:
                resultat.append((instant.replace(microsecond=0).isoformat(), planete, _longitude(instant, "Lune")))
    return tuple(sorted(resultat))


def conjonctions_lunaires_du_mois(debut, fin, theme_natal):
    """Seules l’heure, la maison natale et la lecture utile partent au navigateur."""
    if debut.tzinfo is None or fin.tzinfo is None or fin <= debut:
        raise ValueError("Les bornes du mois doivent être datées avec leur fuseau.")
    try:
        cuspides = extraire_cuspides(theme_natal)
    except (KeyError, TypeError, ValueError):
        cuspides = []
    resultat = []
    for instant, planete, longitude in _conjonctions_exactes(
        debut.astimezone(timezone.utc).isoformat(), fin.astimezone(timezone.utc).isoformat(),
    ):
        maison = trouver_maison(longitude, cuspides) if cuspides else None
        resultat.append({
            "date": instant, "planete": planete, "titre": f"Lune conjointe à {planete}",
            "maison_natale": maison, "domaine": DOMAINES.get(maison),
            "lecture": LECTURES[planete], "lecture_maison": LECTURES_MAISONS.get(maison, ""),
        })
    return resultat
