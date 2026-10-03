"""Regroupe les déclencheurs rapides et les transits de fond d'une RS.

Calcul local déterministe : aucun appel LLM. Un contact de Mars isolé ne
constitue pas une activation annuelle ; les angles d'un même axe ne comptent
qu'une fois. Les dates narratives sont les dates des pics, distinctes des
fenêtres d'orbe conservées dans les transits détaillés.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from utils.revolution_solaire.transits_annuels import (
    POIDS_TRANSIT, POIDS_ASPECT, selectionner_transits_directeurs_rs,
    _cibles_natales, _cibles_rs,
)
from utils.revolution_solaire.datation_detaillee import _position_vitesse, dater_fenetre

LENTES = {'Jupiter','Saturne','Uranus','Neptune','Pluton'}
AXES = {'Ascendant':'Asc–Dsc','Descendant':'Asc–Dsc',
        'MC':'MC–FC','FC':'MC–FC','Rahu':'Nœuds','Ketu':'Nœuds'}
PERSONNELLES = {'Soleil','Lune','Mercure','Vénus','Mars'}
ECART_SIGNES = {'conjonction':0,'sextile':2,'carré':3,'trigone':4,'opposition':6}


def _non_dissocie(e, cibles):
    if cibles is None:
        return True
    cible=cibles.get(e['reference'],{}).get(e['cible'])
    if cible is None:
        return False
    instant=datetime.fromisoformat(e['date_plus_serree']).replace(hour=12,tzinfo=timezone.utc)
    longitude=_position_vitesse(e['planete_transit'],instant)[0]
    ecart=(int(longitude//30)-int(cible//30))%12
    attendu=ECART_SIGNES.get(e['aspect'])
    return attendu is not None and ecart in ({attendu,(-attendu)%12})


def _retrograde_au_pic(e):
    instant=datetime.fromisoformat(e['date_plus_serree']).replace(hour=12,tzinfo=timezone.utc)
    return _position_vitesse(e['planete_transit'],instant)[1]<0


def _cibles(theme_natal,theme_rs,facteurs):
    if theme_natal is None or theme_rs is None:
        return None
    return {'natal':_cibles_natales(theme_natal),'rs':_cibles_rs(theme_rs,facteurs)}


def _jour(e):
    return date.fromisoformat(e['date_plus_serree'])


def _identite(e):
    """Retire la répétition mécanique Soleil RS / Soleil natal."""
    cible=e['cible']
    if cible=='Soleil' and e['reference']=='rs':
        return None
    return (e['planete_transit'],e['reference'],AXES.get(cible,cible),
            e['aspect'] if cible not in AXES else '')


def _facteurs_rs(facteurs):
    noms={'Ascendant','MC','Lune'}
    noms.update(x.get('nom') for x in facteurs.get('maitres_ascendant_rs') or [] if x.get('nom'))
    for f in facteurs.get('figures_majeures') or []:
        noms.update(f.get('planetes') or [])
    return noms


def _pertinent(e,facteurs_rs):
    if e['aspect']=='quinconce':
        return False
    if e['reference']=='rs':
        return e['cible'] in facteurs_rs
    if e['cible'] in PERSONNELLES|set(AXES):
        # Les Nœuds sont retenus comme axe uniquement pour les contacts
        # structurants ; ils ne sont pas prioritaires à chaque sextile isolé.
        return True
    return False


def _score(e,facteurs_rs):
    poids_cible=8 if e['reference']=='rs' and e['cible'] in facteurs_rs else 7 if e['cible'] in PERSONNELLES|set(AXES) else 0
    force=3 if e['orbe_plus_serre']<=0.3 else 2 if e['orbe_plus_serre']<=1 else 0
    return POIDS_TRANSIT[e['planete_transit']]+POIDS_ASPECT[e['aspect']]+poids_cible+force


def _dedoublonner(evenements):
    """Une seule preuve pour les deux extrémités d'un même axe."""
    resultat={}
    for e in evenements:
        identite=_identite(e)
        if identite is None:continue
        cle=(identite,e['date_plus_serree'])
        precedent=resultat.get(cle)
        if precedent is None or (e['cible']=='Rahu' and precedent['cible']=='Ketu') or (e['cible']!='Ketu' and e['orbe_plus_serre']<precedent['orbe_plus_serre']):
            resultat[cle]=e
    return list(resultat.values())


def _candidats(evenements,facteurs,cibles=None):
    facteurs_rs=_facteurs_rs(facteurs)
    filtres=_dedoublonner(e for e in evenements if _pertinent(e,facteurs_rs) and
                         e['orbe_plus_serre']<=1 and _non_dissocie(e,cibles))
    lentes=[e for e in filtres if e['planete_transit'] in LENTES and (e['cible'] not in {'Rahu','Ketu'} or e['aspect'] in {'conjonction','opposition','carré'})]
    rapides=[e for e in filtres if e['planete_transit']=='Mars']
    candidats=[]
    for lent in lentes:
        centre=_jour(lent)
        autour=[e for e in rapides if abs((_jour(e)-centre).days)<=7 and
                (e['cible'] not in {'Rahu','Ketu'} or
                 (lent['reference']==e['reference'] and AXES.get(lent['cible'])=='Nœuds'))]
        # Deux contacts rapides sur des points distincts, ou un contact
        # rapide au même point que le transit lent : réactivation démontrée.
        points={ (e['reference'],AXES.get(e['cible'],e['cible'])) for e in autour }
        meme=[e for e in autour if e['reference']==lent['reference']
              and AXES.get(e['cible'],e['cible'])==AXES.get(lent['cible'],lent['cible'])]
        if len(points)<2 and not meme:continue
        autour.sort(key=lambda e:(0 if e in meme else 1,abs((_jour(e)-centre).days),-_score(e,facteurs_rs)))
        retenus=autour[:4]
        evenements_groupe=[lent,*retenus]
        jours=[_jour(e) for e in evenements_groupe]
        score=_score(lent,facteurs_rs)+sum(_score(e,facteurs_rs) for e in retenus)
        score+=8 if meme else 0
        candidats.append({'du':min(jours).isoformat(),'au':max(jours).isoformat(),
            'pic':centre.isoformat(),'score':score,'climat':lent,'declencheurs':retenus})
    return candidats


def selectionner_activations_annuelles(evenements,facteurs,*,theme_natal=None,theme_rs=None,maximum=5):
    """Choisit des semaines fortes réparties dans l'année solaire.

    Les événements exhaustifs restent la source ; le top 30 historique ne
    peut donc plus masquer une semaine de convergences.
    """
    candidats=_candidats(evenements,facteurs,_cibles(theme_natal,theme_rs,facteurs))
    candidats.sort(key=lambda g:(-g['score'],g['pic']))
    retenus=[]
    for groupe in candidats:
        centre=date.fromisoformat(groupe['pic'])
        if any(abs((centre-date.fromisoformat(x['pic'])).days)<28 for x in retenus):
            continue
        retenus.append(groupe)
        if len(retenus)>=maximum:break
    return sorted(retenus,key=lambda x:x['pic'])


def transits_pour_rapport(evenements,facteurs,activations,*,theme_natal=None,theme_rs=None,maximum=50):
    """Conserve le socle historique et ajoute les preuves des activations.

    Le relevé transmis peut dépasser l'ancien top 30 pour éviter de perdre
    des climats annuels lorsque Mars apporte plusieurs déclencheurs.
    """
    facteurs_rs=_facteurs_rs(facteurs)
    cibles=_cibles(theme_natal,theme_rs,facteurs)
    admissibles=[e for e in evenements if _pertinent(e,facteurs_rs) and _identite(e) and _non_dissocie(e,cibles) and
                 (e['cible'] not in {'Rahu','Ketu'} or e['aspect'] in {'conjonction','opposition','carré'})]
    base=selectionner_transits_directeurs_rs(admissibles,facteurs,maximum=30)
    preuves=_dedoublonner(e for g in activations for e in [g['climat'],*g['declencheurs']])
    preuves.sort(key=lambda e:-_score(e,facteurs_rs))
    preuves=preuves[:maximum]
    # Les preuves restent prioritaires. La suite garde l'ordre de pertinence
    # existant, sans doubler Soleil RS ni les deux bouts d'un axe.
    deja=set();sortie=[]
    for e in [*preuves,*base]:
        identite=(_identite(e),e['date_plus_serree'])
        if identite in deja:continue
        deja.add(identite);sortie.append({
            **e,'score_priorite':e.get('score_priorite',_score(e,facteurs_rs)),
            'retrograde_au_plus_serre':_retrograde_au_pic(e),
        })
        if len(sortie)>=maximum:break
    return sortie


def dater_activations(activations,theme_natal,theme_rs,facteurs,debut_utc,fin_utc):
    """Donne au récit les vrais passages exacts, sans refaire le calcul céleste."""
    cibles=_cibles(theme_natal,theme_rs,facteurs)
    resultat=[]
    for groupe in activations:
        contacts=[]
        for evenement in [groupe['climat'],*groupe['declencheurs']]:
            detail=dater_fenetre(evenement,cibles,debut_utc,fin_utc)
            contacts.append({
                'transit':evenement['planete_transit'],
                'aspect':evenement['aspect'],
                'cible':evenement['cible'],
                'theme':evenement['reference'],
                'fenetre_utc':[detail['entree_utc'],detail['sortie_utc']],
                'exacts_utc':[x['date_utc'] for x in detail['passages_exacts']],
                'stations':detail['stations'],
            })
        resultat.append({'du':groupe['du'],'au':groupe['au'],'contacts':contacts})
    return resultat
