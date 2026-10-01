"""Repères du ciel collectif, calculés sans thème natal ni appel IA."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from itertools import combinations, groupby
from statistics import median

import swisseph as swe

from utils.transits.calcul_transits import PLANETES_SWISSEPH


LENTES = ("Jupiter", "Saturne", "Uranus", "Neptune", "Pluton")
RAPIDES_RETENUES = ("Soleil", "Vénus", "Mars")
PLANETES = RAPIDES_RETENUES + LENTES
PLANETES_CARTE = ("Soleil", "Lune", "Mercure", "Vénus", "Mars") + LENTES
PLANETES_MOUVEMENT = ("Mercure", "Vénus", "Mars") + LENTES
SIGNES = ("Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge",
          "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons")
ASPECTS = (("conjonction", 0, 0), ("sextile", 60, 2), ("carré", 90, 3),
           ("trigone", 120, 4), ("opposition", 180, 6))
NATURE_ASPECT = {
    "carré": "tension", "opposition": "tension",
    "trigone": "fluide", "sextile": "fluide",
    "conjonction": "neutre",
}


def _positions_instant(instant: datetime) -> dict[str, tuple[float, float]]:
    """Longitude et vitesse géocentriques à un instant UTC."""
    instant = instant.astimezone(timezone.utc)
    julien = swe.julday(instant.year, instant.month, instant.day,
                        instant.hour + instant.minute / 60 + instant.second / 3600)
    return {
        nom: (valeurs[0] % 360, valeurs[3])
        for nom in PLANETES_CARTE
        for valeurs in (swe.calc_ut(julien, PLANETES_SWISSEPH[nom], swe.FLG_SPEED)[0],)
    }


def _positions(jour: date) -> dict[str, tuple[float, float]]:
    """Longitude et vitesse géocentriques à 12 h UTC."""
    return _positions_instant(datetime(jour.year, jour.month, jour.day, 12,
                                       tzinfo=timezone.utc))


def _vitesse_instant(planete: str, instant: datetime) -> float:
    instant = instant.astimezone(timezone.utc)
    julien = swe.julday(instant.year, instant.month, instant.day,
                        instant.hour + instant.minute / 60 + instant.second / 3600)
    return swe.calc_ut(julien, PLANETES_SWISSEPH[planete], swe.FLG_SPEED)[0][3]


def _vitesse_reference(annee: int, mois: int, planete: str) -> float:
    """Vitesse directe habituelle estimée autour du mois, propre à chaque planète."""
    centre = datetime(annee, mois, 15, 12, tzinfo=timezone.utc)
    vitesses = [_vitesse_instant(planete, centre + timedelta(days=15 * n))
                for n in range(-12, 13)]
    directes = [vitesse for vitesse in vitesses if vitesse > 0]
    return median(directes or [abs(vitesse) for vitesse in vitesses])


@lru_cache(maxsize=36)
def _periodes_stationnaires_mois(annee: int, mois: int) -> list[dict]:
    """Jours proches de la vitesse nulle autour d'un changement de direction."""
    debut = date(annee, mois, 1)
    fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
    plage = [debut - timedelta(days=30) + timedelta(days=n)
             for n in range((fin - debut).days + 61)]
    periodes = []
    for planete in PLANETES_MOUVEMENT:
        # 20 % de la vitesse directe habituelle : seuil relatif, non universel.
        seuil = _vitesse_reference(annee, mois, planete) * .20
        vitesses = {}
        stationnaires = {}
        for jour in plage:
            minuit = datetime(jour.year, jour.month, jour.day, tzinfo=timezone.utc)
            mesures = [_vitesse_instant(planete, minuit + timedelta(hours=heure))
                       for heure in (0, 12, 18)]
            vitesses[jour] = mesures[1]
            stationnaires[jour] = min(abs(vitesse) for vitesse in mesures) <= seuil
        deja_vus = set()
        dernier_signe = None
        dernier_jour = None
        for jour in plage:
            vitesse = vitesses[jour]
            if vitesse == 0:
                continue
            signe = 1 if vitesse > 0 else -1
            if dernier_signe is None or signe == dernier_signe:
                dernier_signe, dernier_jour = signe, jour
                continue
            gauche = dernier_jour if stationnaires[dernier_jour] else jour
            droite = jour
            while stationnaires.get(gauche - timedelta(days=1), False):
                gauche -= timedelta(days=1)
            while stationnaires.get(droite + timedelta(days=1), False):
                droite += timedelta(days=1)
            cle = (gauche, droite)
            dernier_signe, dernier_jour = signe, jour
            if cle in deja_vus or droite < debut or gauche >= fin:
                continue
            deja_vus.add(cle)
            periodes.append({
                "planete": planete, "debut": max(gauche, debut),
                "fin": min(droite, fin - timedelta(days=1)),
                "avant_mois": gauche < debut, "apres_mois": droite >= fin,
                "changement": jour,
                "direction": "rétrograde" if vitesses[jour] < 0 else "direct",
            })
    periodes.sort(key=lambda periode: (periode["debut"], periode["planete"]))
    return periodes


def _aspect(longitude_a: float, longitude_b: float):
    """Les signes doivent aussi former l'aspect : aucun aspect dissocié."""
    signe_a, signe_b = int(longitude_a // 30), int(longitude_b // 30)
    ecart_signes = min((signe_a - signe_b) % 12, (signe_b - signe_a) % 12)
    distance = abs((longitude_a - longitude_b + 180) % 360 - 180)
    for nom, angle, ecart_attendu in ASPECTS:
        if ecart_signes == ecart_attendu:
            return nom, abs(distance - angle)
    return None


def _paires(positions: dict[str, tuple[float, float]]):
    for premiere, seconde in combinations(PLANETES, 2):
        if premiere not in LENTES and seconde not in LENTES:
            continue
        aspect = _aspect(positions[premiere][0], positions[seconde][0])
        if aspect is not None:
            yield premiere, seconde, aspect[0], aspect[1]


@lru_cache(maxsize=36)
def _periodes_aspects_mois(annee: int, mois: int) -> list[dict]:
    """Fenêtres collectives à 3° et passages exacts, sans aspect dissocié."""
    debut = datetime(annee, mois, 1, tzinfo=timezone.utc)
    fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
    pas = timedelta(hours=6)
    instants = [debut - pas]
    while instants[-1] < fin + pas:
        instants.append(instants[-1] + pas)
    positions = {instant: _positions_instant(instant) for instant in instants}
    actifs = {}
    periodes = []

    def paire_active(instant, cle):
        premiere, seconde, aspect = cle
        valeurs = positions.get(instant) or _positions_instant(instant)
        resultat = _aspect(valeurs[premiere][0], valeurs[seconde][0])
        return resultat is not None and resultat[0] == aspect and resultat[1] <= 3

    def borne(a, b, cle, etat_a):
        while (b - a).total_seconds() > 1:
            milieu = a + (b - a) / 2
            if paire_active(milieu, cle) == etat_a:
                a = milieu
            else:
                b = milieu
        return a + (b - a) / 2

    for index, instant in enumerate(instants):
        presents = {
            (premiere, seconde, aspect)
            for premiere, seconde, aspect, orbe in _paires(positions[instant])
            if orbe <= 3
        }
        if index == 0:
            actifs = {cle: None for cle in presents}
            continue
        precedent = instants[index - 1]
        for cle in actifs.keys() - presents:
            sortie = borne(precedent, instant, cle, True)
            if sortie > debut and (actifs[cle] or debut) < fin:
                periodes.append((cle, actifs[cle], sortie))
        for cle in presents - actifs.keys():
            actifs[cle] = borne(precedent, instant, cle, False)
        actifs = {cle: actifs[cle] for cle in presents}
    periodes.extend((cle, entree, None) for cle, entree in actifs.items()
                    if (entree or debut) < fin)

    resultat = []
    for (premiere, seconde, aspect), entree, sortie in periodes:
        if (sortie is not None and sortie <= debut) or (entree is not None and entree >= fin):
            continue
        angle = next(angle for nom, angle, _ in ASPECTS if nom == aspect)
        cibles = {angle, (-angle) % 360}
        exacts = []
        for a, b in zip(instants, instants[1:]):
            if b <= (entree or instants[0]) or a >= (sortie or instants[-1]):
                continue
            for cible in cibles:
                def ecart(t):
                    valeurs = positions.get(t) or _positions_instant(t)
                    return ((valeurs[premiere][0] - valeurs[seconde][0] - cible + 180) % 360) - 180
                gauche, droite = ecart(a), ecart(b)
                if gauche * droite > 0 or abs(gauche - droite) >= 180:
                    continue
                lo, hi = a, b
                while (hi - lo).total_seconds() > 1:
                    milieu = lo + (hi - lo) / 2
                    if (ecart(milieu) >= 0) == (gauche >= 0):
                        lo = milieu
                    else:
                        hi = milieu
                exact = lo + (hi - lo) / 2
                if (abs(ecart(exact)) < .001 and debut <= exact < fin
                        and (entree is None or entree <= exact)
                        and (sortie is None or exact <= sortie)
                        and paire_active(exact, (premiere, seconde, aspect))):
                    if all(abs((exact - ancien).total_seconds()) > 60 for ancien in exacts):
                        exacts.append(exact)
        resultat.append({
            "titre": f"{premiere} {aspect} {seconde}",
            "planetes": [premiere, seconde],
            "aspect": aspect, "nature": NATURE_ASPECT[aspect],
            "start": entree.isoformat() if entree and entree > debut else None,
            "end": sortie.isoformat() if sortie and sortie < fin else None,
            "exacts": [instant.isoformat() for instant in sorted(exacts)],
        })
    resultat.sort(key=lambda periode: (periode["start"] or "", periode["titre"]))
    return resultat


@lru_cache(maxsize=36)
def _mois_calcule(annee: int, mois: int):
    if not 1900 <= annee <= 2100 or not 1 <= mois <= 12:
        raise ValueError("Mois hors de la plage prise en charge.")
    debut = date(annee, mois, 1)
    jours = monthrange(annee, mois)[1]
    positions_par_jour = {}
    meilleurs = {}
    stations = []
    entrees_signes = []
    precedentes = _positions(debut - timedelta(days=1))
    directions = {planete: (1 if precedentes[planete][1] > 0 else -1)
                  for planete in PLANETES_MOUVEMENT}
    for numero in range(jours):
        jour = debut + timedelta(days=numero)
        positions = _positions(jour)
        positions_par_jour[jour] = positions
        for premiere, seconde, aspect, orbe in _paires(positions):
            cle = (premiere, seconde, aspect)
            if cle not in meilleurs or orbe < meilleurs[cle][1]:
                meilleurs[cle] = (jour, orbe)
        for planete in PLANETES_MOUVEMENT:
            apres = positions[planete][1]
            direction = 1 if apres > 0 else -1 if apres < 0 else 0
            if direction and direction != directions[planete]:
                stations.append({
                    "date": jour,
                    "titre": f"{planete} stationnaire, puis {'direct' if apres > 0 else 'rétrograde'}",
                    "planete": planete,
                    "direction": "direct" if apres > 0 else "rétrograde",
                })
            if direction:
                directions[planete] = direction
            signe_avant = int(precedentes[planete][0] // 30)
            signe_apres = int(positions[planete][0] // 30)
            if signe_avant != signe_apres:
                entrees_signes.append({
                    "date": jour,
                    "titre": f"{planete} entre en {SIGNES[signe_apres]}",
                    "planete": planete,
                    "signe": SIGNES[signe_apres],
                })
        precedentes = positions

    temps_forts = []
    for (premiere, seconde, aspect), (jour, orbe) in meilleurs.items():
        # Les rendez-vous sont proches de l'exact ; le climat lent reste visible à 3°.
        if orbe <= 0.8:
            temps_forts.append({
                "date": jour,
                "titre": f"{premiere} {aspect} {seconde}",
                "aspect": aspect,
                "nature": NATURE_ASPECT[aspect],
                "orbe": round(orbe, 2),
                "lentes": premiere in LENTES and seconde in LENTES,
            })
    temps_forts.sort(key=lambda item: (item["date"], not item["lentes"], item["orbe"]))
    return positions_par_jour, temps_forts, stations, entrees_signes


def ciel_collectif_mois(annee: int, mois: int, *, jour_reference: date | None = None,
                       inclure_periodes: bool = False,
                       inclure_stations: bool = False) -> dict:
    """Climat lent du jour et principaux rapprochements du mois, sans natal."""
    positions_par_jour, temps_forts, stations, entrees_signes = _mois_calcule(annee, mois)
    jour_reference = jour_reference or datetime.now(timezone.utc).date()
    if jour_reference not in positions_par_jour:
        jour_reference = date(annee, mois, 1)
    climat = [
        {"titre": f"{premiere} {aspect} {seconde}", "aspect": aspect,
         "nature": NATURE_ASPECT[aspect], "orbe": round(orbe, 2)}
        for premiere, seconde, aspect, orbe in _paires(positions_par_jour[jour_reference])
        if premiere in LENTES and seconde in LENTES and orbe <= 3
    ]
    climat.sort(key=lambda item: item["orbe"])
    evenements = [*temps_forts, *(
        {**station, "station": True, "lentes": True, "nature": "station"}
        for station in stations
    ), *(
        {**entree, "entree_signe": True, "nature": "entree"}
        for entree in entrees_signes
    )]
    evenements.sort(key=lambda item: (item["date"], not item.get("lentes", False), item.get("orbe", 0)))
    groupes_dates = [
        {"date": jour, "evenements": list(groupe)}
        for jour, groupe in groupby(evenements, key=lambda item: item["date"])
    ]
    retrogradations = []
    jours_du_mois = sorted(positions_par_jour)
    for planete in PLANETES_MOUVEMENT:
        debut_retro = None
        for jour in jours_du_mois:
            retrograde = positions_par_jour[jour][planete][1] < 0
            if retrograde and debut_retro is None:
                debut_retro = jour
            elif not retrograde and debut_retro is not None:
                retrogradations.append({"planete": planete, "debut": debut_retro,
                                        "fin": jour - timedelta(days=1),
                                        "avant_mois": debut_retro == jours_du_mois[0],
                                        "apres_mois": False})
                debut_retro = None
        if debut_retro is not None:
            retrogradations.append({"planete": planete, "debut": debut_retro,
                                    "fin": jours_du_mois[-1],
                                    "avant_mois": debut_retro == jours_du_mois[0],
                                    "apres_mois": True})
    retrogradations.sort(key=lambda item: (item["debut"], item["planete"]))
    return {"jour_reference": jour_reference, "climat": climat,
            "temps_forts": temps_forts, "stations": stations,
            "entrees_signes": entrees_signes, "evenements": evenements,
            "groupes_dates": groupes_dates, "retrogradations": retrogradations,
            "periodes_aspects": _periodes_aspects_mois(annee, mois) if inclure_periodes else [],
            "periodes_stationnaires": _periodes_stationnaires_mois(annee, mois)
            if inclure_periodes or inclure_stations else []}
