"""Repères du ciel collectif, calculés sans thème natal ni appel IA."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from itertools import combinations

import swisseph as swe

from utils.transits.calcul_transits import PLANETES_SWISSEPH


LENTES = ("Jupiter", "Saturne", "Uranus", "Neptune", "Pluton")
RAPIDES_RETENUES = ("Soleil", "Vénus", "Mars")
PLANETES = RAPIDES_RETENUES + LENTES
ASPECTS = (("conjonction", 0, 0), ("sextile", 60, 2), ("carré", 90, 3),
           ("trigone", 120, 4), ("opposition", 180, 6))


def _positions(jour: date) -> dict[str, tuple[float, float]]:
    """Longitude et vitesse géocentriques à 12 h UTC."""
    julien = swe.julday(jour.year, jour.month, jour.day, 12)
    return {
        nom: (valeurs[0] % 360, valeurs[3])
        for nom in PLANETES
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
    precedentes = _positions(debut - timedelta(days=1))
    for numero in range(jours):
        jour = debut + timedelta(days=numero)
        positions = _positions(jour)
        positions_par_jour[jour] = positions
        for premiere, seconde, aspect, orbe in _paires(positions):
            cle = (premiere, seconde, aspect)
            if cle not in meilleurs or orbe < meilleurs[cle][1]:
                meilleurs[cle] = (jour, orbe)
        for planete in LENTES:
            avant, apres = precedentes[planete][1], positions[planete][1]
            if avant * apres < 0:
                stations.append({
                    "date": jour,
                    "titre": f"{planete} stationnaire, puis {'direct' if apres > 0 else 'rétrograde'}",
                })
        precedentes = positions

    temps_forts = []
    for (premiere, seconde, aspect), (jour, orbe) in meilleurs.items():
        # Les rendez-vous sont proches de l'exact ; le climat lent reste visible à 3°.
        if orbe <= 0.8:
            temps_forts.append({
                "date": jour,
                "titre": f"{premiere} {aspect} {seconde}",
                "orbe": round(orbe, 2),
                "lentes": premiere in LENTES and seconde in LENTES,
            })
    temps_forts.sort(key=lambda item: (item["date"], not item["lentes"], item["orbe"]))
    return positions_par_jour, temps_forts, stations


def ciel_collectif_mois(annee: int, mois: int, *, jour_reference: date | None = None) -> dict:
    """Climat lent du jour et principaux rapprochements du mois, sans natal."""
    positions_par_jour, temps_forts, stations = _mois_calcule(annee, mois)
    jour_reference = jour_reference or datetime.now(timezone.utc).date()
    if jour_reference not in positions_par_jour:
        jour_reference = date(annee, mois, 1)
    climat = [
        {"titre": f"{premiere} {aspect} {seconde}", "orbe": round(orbe, 2)}
        for premiere, seconde, aspect, orbe in _paires(positions_par_jour[jour_reference])
        if premiere in LENTES and seconde in LENTES and orbe <= 3
    ]
    climat.sort(key=lambda item: item["orbe"])
    evenements = [*temps_forts, *(
        {**station, "station": True, "lentes": True} for station in stations
    )]
    evenements.sort(key=lambda item: (item["date"], not item["lentes"], item.get("orbe", 0)))
    return {"jour_reference": jour_reference, "climat": climat,
            "temps_forts": temps_forts, "stations": stations, "evenements": evenements}
