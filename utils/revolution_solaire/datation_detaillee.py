"""Datation détaillée et indépendante des fenêtres de transits annuels RS.

Ne change pas le moteur de sélection : affine ses fenêtres, passage par passage.
Les calculs Swiss Ephemeris sont géocentriques tropicaux en UTC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import swisseph as swe

from utils.revolution_solaire.transits_annuels import (
    ASPECTS_TRANSITS_RS, _cibles_natales, _cibles_rs,
)

PLANETES = {
    'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturne': swe.SATURN,
    'Uranus': swe.URANUS, 'Neptune': swe.NEPTUNE, 'Pluton': swe.PLUTO,
}
UTC = timezone.utc
PAS = timedelta(hours=6)
PRECISION = timedelta(minutes=1)


def _utc(valeur):
    if valeur.tzinfo is None:
        raise ValueError('Date UTC avec fuseau obligatoire')
    return valeur.astimezone(UTC)


@lru_cache(maxsize=40000)
def _position_vitesse(planete, instant):
    date = _utc(instant)
    heure = date.hour + date.minute / 60 + date.second / 3600 + date.microsecond / 3600000000
    jd = swe.julday(date.year, date.month, date.day, heure)
    coordonnees = swe.calc_ut(jd, PLANETES[planete], swe.FLG_SPEED)[0]
    return coordonnees[0] % 360, coordonnees[3]


def _ecart(a, b):
    difference = (a - b + 180) % 360 - 180
    return abs(difference)


def _orbe(planete, cible, angle, instant):
    return abs(_ecart(_position_vitesse(planete, instant)[0], cible) - angle)


def _signe_ecart(planete, cible, angle, instant, orientation):
    longitude = _position_vitesse(planete, instant)[0]
    return (longitude - cible - orientation * angle + 180) % 360 - 180


def _grille(debut, fin):
    dates = [debut]
    while dates[-1] + PAS < fin:
        dates.append(dates[-1] + PAS)
    if dates[-1] != fin:
        dates.append(fin)
    return dates


def _bissection(fonction, gauche, droite):
    a, b = fonction(gauche), fonction(droite)
    if a == 0:
        return gauche
    if b == 0:
        return droite
    if a * b > 0:
        raise ValueError('La racine n’est pas encadrée')
    while droite - gauche > PRECISION:
        milieu = gauche + (droite - gauche) / 2
        value = fonction(milieu)
        if a * value <= 0:
            droite, b = milieu, value
        else:
            gauche, a = milieu, value
    return gauche + (droite - gauche) / 2


def _iso(instant):
    return instant.isoformat(timespec='minutes')


def _uniques(passages):
    resultat = []
    for item in sorted(passages, key=lambda x:x['instant']):
        if not resultat or item['instant'] - resultat[-1]['instant'] > timedelta(hours=3):
            resultat.append(item)
    return resultat


def _minimum(planete, cible, angle, dates):
    i = min(range(len(dates)), key=lambda k:_orbe(planete,cible,angle,dates[k]))
    a,b=dates[max(i-1,0)],dates[min(i+1,len(dates)-1)]
    # Recherche locale autour du plus petit échantillon, utile pour un passage
    # exact tangent à la grille ou pour une station sans contact exact.
    for _ in range(30):
        if b-a <= PRECISION:
            break
        x=a+(b-a)/3; y=b-(b-a)/3
        if _orbe(planete,cible,angle,x) <= _orbe(planete,cible,angle,y):
            b=y
        else:
            a=x
    return a+(b-a)/2


def dater_fenetre(evenement, cibles, debut_utc, fin_utc):
    """Affine une fenêtre existante, sans la fusionner avec un autre aspect."""
    planete = evenement['planete_transit']
    cible = cibles[evenement['reference']][evenement['cible']]
    angle, orbe_max = ASPECTS_TRANSITS_RS[evenement['aspect']]
    debut_cycle, fin_cycle = _utc(debut_utc), _utc(fin_utc)
    # Les dates de l'ancien moteur sont des journées observées à midi UTC.
    recherche_debut = max(debut_cycle, datetime.fromisoformat(evenement['debut']).replace(tzinfo=UTC)-timedelta(days=2))
    recherche_fin = min(fin_cycle, datetime.fromisoformat(evenement['fin']).replace(tzinfo=UTC)+timedelta(days=2))
    dates = _grille(recherche_debut, recherche_fin)
    dans_orbe = [(_orbe(planete,cible,angle,t) <= orbe_max) for t in dates]
    if not any(dans_orbe):
        raise ValueError(f"Fenêtre introuvable au pas de 6 h : {evenement}")
    premier = dans_orbe.index(True)
    dernier = len(dans_orbe)-1-dans_orbe[::-1].index(True)
    entree = recherche_debut if premier == 0 else _bissection(
        lambda t:_orbe(planete,cible,angle,t)-orbe_max,dates[premier-1],dates[premier])
    sortie = recherche_fin if dernier == len(dates)-1 else _bissection(
        lambda t:_orbe(planete,cible,angle,t)-orbe_max,dates[dernier],dates[dernier+1])
    # À l'intérieur d'une même fenêtre, un retour rétrograde peut provoquer
    # plusieurs passages exacts. Les deux orientations sont nécessaires.
    exacts=[]
    for orientation in ((1,) if angle in (0,180) else (1,-1)):
        for a,b in zip(dates,dates[1:]):
            if b < entree or a > sortie:
                continue
            f=lambda t:_signe_ecart(planete,cible,angle,t,orientation)
            x,y=f(a),f(b)
            if abs(x-y)>180:
                continue
            if x*y<=0:
                instant=_bissection(f,a,b)
                if entree-PRECISION <= instant <= sortie+PRECISION:
                    vitesse=_position_vitesse(planete,instant)[1]
                    exacts.append({'instant':instant,'date_utc':_iso(instant),
                        'sens':'rétrograde' if vitesse<0 else 'direct'})
    exacts=_uniques(exacts)
    stations=[]
    stations_brutes=[]
    for a,b in zip(dates,dates[1:]):
        v1,v2=_position_vitesse(planete,a)[1],_position_vitesse(planete,b)[1]
        if v1*v2 < 0:
            instant=_bissection(lambda t:_position_vitesse(planete,t)[1],a,b)
            if entree <= instant <= sortie:
                stations_brutes.append(instant)
                stations.append({'date_utc':_iso(instant),
                    'sens_apres':'rétrograde' if v2<0 else 'direct',
                    'orbe':round(_orbe(planete,cible,angle,instant),3)})
    phases=[]
    bornes=[entree,*stations_brutes,sortie]
    for a,b in zip(bornes,bornes[1:]):
        if b-a <= PRECISION:
            continue
        milieu=a+(b-a)/2
        sens='rétrograde' if _position_vitesse(planete,milieu)[1]<0 else 'direct'
        phases.append({'debut_utc':_iso(a),'fin_utc':_iso(b),'sens':sens,
            'passages_exacts':[x['date_utc'] for x in exacts if a-PRECISION <= x['instant'] <= b+PRECISION]})
    minimum=_minimum(planete,cible,angle,dates[premier:dernier+1])
    # Le minimum sur toute la fenêtre peut être à une borne calculée.
    minimum=min((minimum,entree,sortie),key=lambda t:_orbe(planete,cible,angle,t))
    return {
        'planete_transit':planete,'reference':evenement['reference'],
        'cible':evenement['cible'],'aspect':evenement['aspect'],
        'ancienne_fenetre':{'debut':evenement['debut'],'fin':evenement['fin'],
                            'plus_serre':evenement['date_plus_serree']},
        'entree_utc':_iso(entree),'sortie_utc':_iso(sortie),
        'entree_coupee_par_cycle':entree==debut_cycle,
        'sortie_coupee_par_cycle':sortie==fin_cycle,
        'passages_exacts':[{k:v for k,v in x.items() if k!='instant'} for x in exacts],
        'stations':stations,
        'phases':phases,
        'plus_serre_utc':_iso(minimum),
        'orbe_minimum':round(_orbe(planete,cible,angle,minimum),3),
        'exact':bool(exacts),
    }


def dater_transits_annuels(theme_natal,theme_rs,facteurs,debut_utc,fin_utc,evenements):
    cibles={'natal':_cibles_natales(theme_natal),'rs':_cibles_rs(theme_rs,facteurs)}
    return [dater_fenetre(e,cibles,debut_utc,fin_utc) for e in evenements]
