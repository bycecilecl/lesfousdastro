"""Dernière passe conservatrice : formulations vérifiables et titres de périodes.

Les corrections du récit ne s'appliquent que si leurs faits sont établis dans
les calculs. Les formulations ambiguës restent intactes, sans bloquer le rapport.
"""
import re

MOIS = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']


def titre_periode(dates):
    morceaux = re.findall(r"(\d{1,2})(?:er)?\s+("+'|'.join(MOIS)+r")\s+(\d{4})", dates)
    if not morceaux:
        return dates
    debut, fin = morceaux[0], morceaux[-1]
    # Dans « 10 décembre – 18 décembre 2026 », seule la fin porte l'année.
    sans_annee = re.match(r"(\d{1,2})(?:er)?\s+("+'|'.join(MOIS)+r")\s*[–—-]", dates)
    if sans_annee:
        debut = (sans_annee[1],sans_annee[2],fin[2])
    jour_seul = re.match(r"(\d{1,2})(?:er)?\s*[–—-]", dates)
    if jour_seul:
        debut = (jour_seul[1], fin[1], fin[2])
    def moment(jour):
        return 'Début' if int(jour) <= 10 else 'Mi' if int(jour) <= 20 else 'Fin'
    if debut[1:] == fin[1:]:
        if moment(debut[0]) == moment(fin[0]):
            prefixe = moment(debut[0])
            return (prefixe+'-'+fin[1] if prefixe=='Mi' else prefixe+' '+fin[1])+' '+fin[2]
        return moment(debut[0])+' à '+moment(fin[0]).lower()+('-' if moment(fin[0])=='Mi' else ' ')+fin[1]+' '+fin[2]
    def segment(d, premier):
        m = moment(d[0]); m = m if premier else m.lower()
        return m+('-' if m.lower()=='mi' else ' ')+d[1]
    return segment(debut,True)+' – '+segment(fin,False)+' '+fin[2]


def finaliser_texte(texte, donnees):
    audit = []
    placements = donnees.get('placements_rs') or {}
    aspects = donnees.get('aspects_rs_natal') or []
    def remplacer(avant, apres, code):
        nonlocal texte
        if avant in texte:
            texte=texte.replace(avant,apres)
            audit.append({'code':code,'avant':avant,'apres':apres})
    # Une opposition au Descendant ne devient pas une opposition à Uranus RS.
    desc = any(a.get('point_rs')=='Descendant' and a.get('point_natal')=='Uranus'
               and a.get('aspect','').lower()=='opposition' for a in aspects)
    uranus = any(a.get('point_rs')=='Uranus' and a.get('point_natal')=='Uranus'
                 and a.get('aspect','').lower()=='opposition' for a in aspects)
    if desc and not uranus:
        remplacer('Uranus en maison 7 RS, opposé à ton Uranus natal et en carré à ton Vénus natal',
                  'Uranus en maison 7 RS, en carré à ta Vénus natale', 'referentiel_uranus')
    saturne = placements.get('Saturne') or {}
    if any(i.get('maison')==2 and i.get('signe')=='Capricorne'
           for i in saturne.get('maisons_gouvernees_interceptees_rs') or []):
        remplacer('et intercepté en maison 2 RS','et maître du Capricorne intercepté en maison 2 RS','maitrise_interception')
    neptune = placements.get('Neptune') or {}
    if saturne.get('maison')==5 and neptune.get('maison')==4:
        remplacer('La conjonction de Saturne RS à Neptune RS, tous deux en maison 4 RS',
                  'La conjonction de Saturne RS à Neptune RS, respectivement en maisons 5 et 4 RS','maisons_distinctes')
    def titre(m):
        dates, sous_titre = m[1], m[2]
        lisible = titre_periode(dates.strip())
        if lisible == dates.strip():
            return m[0]
        audit.append({'code':'titre_periode','avant':m[0], 'apres':lisible})
        return '## '+lisible+' : '+sous_titre+'\n\n> **Dates des passages calculés** — '+dates.strip()+'.'
    texte=re.sub(r'^## ((?:\d{1,2})(?:er)?[^\n:]*\d{4})\s*:\s*([^\n]+)$',titre,texte,flags=re.M)
    return texte,audit
