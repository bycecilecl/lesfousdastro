"""Repères du ciel collectif, calculés sans thème natal ni appel IA."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from itertools import combinations, groupby

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


def _positions(jour: date) -> dict[str, tuple[float, float]]:
    """Longitude et vitesse géocentriques à 12 h UTC."""
    julien = swe.julday(jour.year, jour.month, jour.day, 12)
    return {
        nom: (valeurs[0] % 360, valeurs[3])
        for nom in PLANETES_CARTE
        for valeurs in (swe.calc_ut(julien, PLANETES_SWISSEPH[nom], swe.FLG_SPEED)[0],)
    }


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
    for numero in range(jours):
        jour = debut + timedelta(days=numero)
        positions = _positions(jour)
        positions_par_jour[jour] = positions
        for premiere, seconde, aspect, orbe in _paires(positions):
            cle = (premiere, seconde, aspect)
            if cle not in meilleurs or orbe < meilleurs[cle][1]:
                meilleurs[cle] = (jour, orbe)
        for planete in PLANETES_MOUVEMENT:
            avant, apres = precedentes[planete][1], positions[planete][1]
            if avant * apres < 0:
                stations.append({
                    "date": jour,
                    "titre": f"{planete} stationnaire, puis {'direct' if apres > 0 else 'rétrograde'}",
                    "planete": planete,
                })
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


def ciel_collectif_mois(annee: int, mois: int, *, jour_reference: date | None = None) -> dict:
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
            "groupes_dates": groupes_dates, "retrogradations": retrogradations}
