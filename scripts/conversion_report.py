"""Read-only conversion report; run on the server with a persistent CONVERSION_DB."""
import argparse
from collections import Counter
from datetime import date, timedelta
from html import escape
import json
from pathlib import Path
import sqlite3

STEPS = [('funnel_visit','Visites de la page'),('free_analysis_start','Analyses gratuites commencées'),
         ('free_analysis_success','Analyses gratuites terminées'),('paid_offer_click','Clics vers une offre'),
         ('add_to_cart','Ajouts au panier'),('begin_checkout','Paiements commencés'),('purchase','Commandes payées')]


def report(database, start, end):
    start = date.fromisoformat(start).isoformat()
    stop = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    if start >= stop:
        raise ValueError('La fin doit suivre le début.')
    conn = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = conn.execute('SELECT sid,event,payload FROM events WHERE date >= ? AND date < ? ORDER BY date', (start,stop)).fetchall()
    finally:
        conn.close()
    sets = {event:set() for event,_ in STEPS}
    feedback = Counter()
    offers = {key:{'success':set(),'click':set(),'purchase':set()} for key in ('flash_astral','forces_defis')}
    orders=set()
    for sid,event,raw in rows:
        data=json.loads(raw)
        if event == 'purchase' and data.get('sandbox'):
            continue
        if event in sets:
            sets[event].add(sid)
        if event == 'purchase':
            orders.add(data['transaction_id'])
        if event == 'offer_feedback':
            feedback[data.get('reason','other')] += 1
        offer=data.get('offered_product')
        metric={'offer_view':'success','paid_offer_click':'click','purchase':'purchase'}.get(event)
        if offer in offers and metric:
            offers[offer][metric].add(sid)
    body=''
    cohort=None
    for event,label in STEPS:
        previous=len(cohort) if cohort is not None else None
        cohort=sets[event] if cohort is None else cohort & sets[event]
        rate=f'{len(cohort)/previous:.1%}' if previous else '—'
        body+=f'<tr><td>{label}</td><td>{len(sets[event])}</td><td>{len(cohort)}</td><td>{rate}</td></tr>'
    offer_rows=''
    for offer,counts in offers.items():
        n=len(counts['success'])
        clicks=len(counts['click'] & counts['success']); purchases=len(counts['purchase'] & counts['success'])
        offer_rows+=f'<tr><td>{escape(offer)}</td><td>{n}</td><td>{clicks}</td><td>{purchases}</td><td>{purchases/n:.1%}</td></tr>' if n else f'<tr><td>{escape(offer)}</td><td colspan="4">Aucune exposition mesurée</td></tr>'
    return f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Conversion — Les Fous d’Astro</title><style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:16px;color:#18354a}}table{{border-collapse:collapse;width:100%;margin:24px 0}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #ddd}}th{{background:#e5f3f5}}.table{{overflow-x:auto}}</style>
<h1>Du gratuit à la commande</h1><p>Du {escape(start)} au {escape(end)} inclus, dates UTC. Données réelles enregistrées uniquement.</p>
<div class="table"><table><tr><th>Étape</th><th>Sessions distinctes</th><th>Sessions ayant toutes les étapes précédentes</th><th>Taux depuis l’étape précédente</th></tr>{body}</table></div>
<p>{len(orders)} commande(s) payée(s) distincte(s) observée(s), hors sandbox. Une session avec plusieurs commandes compte une seule fois dans le tunnel. Les achats directs figurent dans les totaux mais pas dans le parcours complet du gratuit.</p>
<h2>Recommandations</h2><div class="table"><table><tr><th>Offre</th><th>Offres affichées</th><th>Clics</th><th>Sessions acheteuses</th><th>Taux d’achat</th></tr>{offer_rows}</table></div>
<h2>Freins déclarés</h2><ul>{''.join(f'<li>{escape(reason)} : {n}</li>' for reason,n in feedback.items()) or '<li>Aucune réponse</li>'}</ul>
<p>Peu de résultats : formulaire, attente ou erreur. Peu de clics : promesse ou valeur mal comprise. Abandon du panier : prix, confiance ou friction. Abandon après confirmation : paiement à vérifier.</p>
<p>Limites : visites avec JavaScript actif, attribution dans une même session de navigateur et sur la période choisie ; les achats sans retour sur le site ne sont pas encore collectés. Les étapes ne constituent pas une preuve causale et ne sont pas ordonnées strictement dans ce rapport.</p></html>'''


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('--start',required=True)
    parser.add_argument('--end',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    Path(args.output).write_text(report(args.database,args.start,args.end))
