"""Résumé d'accueil issu des contacts et lectures du calendrier."""
import json
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo
from utils.calendrier_personnel import cadre_mois,donnees_astrales
@lru_cache(maxsize=32)
def resume_du_jour(theme_json,date,tzid):
    jour=datetime.strptime(date,'%Y-%m-%d')
    a,b,_=cadre_mois(jour.year,jour.month,tzid)
    data=donnees_astrales(json.loads(theme_json),a,b,mars_actif=True,lune_active=True)
    contacts=[p for p in data['periods'] if p['lente']]+[p for p in data['periods_1'] if not p['lente'] and p['planete'] not in ('Lune','Mercure') and (p.get('lien_natal') or p.get('maitre_ascendant'))]
    contacts=[p for p in contacts if date in p.get('mouvements',{})]
    axes={'Ascendant':'Asc–Dsc','Descendant':'Asc–Dsc','MC':'MC–FC','FC':'MC–FC'}
    families={'conjonction':'0/180','opposition':'0/180','sextile':'60/120','trigone':'60/120','carré':'90'}
    def cle(p):
        return (p['planete'],axes.get(p['point'],p['point']),families.get(p['aspect']) if p['point'] in axes else p['aspect'])
    fonds={cle(p) for p in contacts if p['lente']}
    rapides={cle(p) for p in contacts if not p['lente']}
    result=[{'nombre':len(fonds)+len(rapides)}]
    for event in data['events']:
        if not event['label'].startswith(('Nouvelle Lune','Pleine Lune')):continue
        if datetime.fromisoformat(event['date']).astimezone(ZoneInfo(tzid)).date().isoformat()==date:
            result.append({'titre':event['label']+' aujourd’hui'})
    return result
