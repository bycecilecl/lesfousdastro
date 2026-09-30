"""Repères courts du calendrier : base locale, puis vocabulaire de secours."""
import csv
import re
import unicodedata
from pathlib import Path
DOMAINES={1:"Identité et autonomie",2:"Revenus et sécurité matérielle",3:"Échanges et entourage proche",4:"Foyer et famille",5:"Créativité, plaisir et enfants",6:"Travail quotidien et hygiène de vie",7:"Couple et engagements",8:"Intimité et ressources partagées",9:"Études, voyages et convictions",10:"Carrière et place sociale",11:"Amitiés et projets",12:"Retrait et vie intérieure"}
MOUVEMENTS={"Soleil":"Un éclairage sur", "Lune":"Une sensibilité passagère autour de", "Mercure":"Des échanges ou une réflexion autour de", "Vénus":"Un besoin d’harmonie ou une réévaluation de", "Mars":"Un élan d’action autour de", "Jupiter":"Un besoin d’élargir", "Saturne":"Un besoin de structurer et de responsabiliser", "Uranus":"Un besoin de changement et de liberté dans", "Neptune":"Une recherche de sens, avec parfois du flou dans", "Pluton":"Une transformation profonde de"}
CIBLES={"Soleil":"ton identité, ta vitalité et tes priorités", "Lune":"ta sécurité émotionnelle et tes besoins", "Mercure":"ta manière de penser et de communiquer", "Vénus":"tes attachements, tes valeurs et tes désirs", "Mars":"ta manière d’agir et de t’affirmer", "Jupiter":"tes convictions et tes perspectives", "Saturne":"tes limites, tes engagements et tes repères", "Uranus":"ton autonomie et ton rapport au changement", "Neptune":"tes idéaux et tes aspirations", "Pluton":"ton rapport au contrôle et aux transformations", "Ascendant":"ta manière de te présenter et de prendre ta place", "Descendant":"ta manière de vivre tes relations", "MC":"ta direction professionnelle", "FC":"tes fondations personnelles", "Nœud Nord":"tes orientations et tes apprentissages", "Nœud Sud":"tes habitudes et tes repères familiers"}
ASPECTS={"carré":"Une tension peut demander des ajustements.","opposition":"Un équilibre est à trouver entre des besoins contradictoires.","conjonction":"Ces questions peuvent prendre davantage de place.","trigone":"Un appui possible, à mobiliser consciemment.","sextile":"Une ouverture possible, qui demande un petit pas de ta part."}
def normaliser(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s.strip().lower()) if unicodedata.category(c)!='Mn')
def enrichir_lectures(resultat,theme):
    base={}
    path=Path(__file__).resolve().parents[1]/'data/transits/transits_aspects.csv'
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                text=(row.get('INTERPRETATION') or '').strip()
                if text:base[tuple(normaliser(row.get(k) or '') for k in ('PLANETE_TRANSIT','ASPECT','PLANETE_NATALE'))]=text
    for key in ('periods','periods_1'):
        for c in resultat[key]:
            planet,point,aspect=c['planete'],c['point'],c['aspect']
            raw=base.get(tuple(map(normaliser,(planet,aspect,point))))
            if raw:
                phrases=re.split(r'(?<=[.!?])\s+',raw)
                text=' '.join(phrases[:2])
                source='base_locale'
            else:
                text=MOUVEMENTS.get(planet,'Un mouvement autour de')+' '+CIBLES.get(point,'tes repères personnels')+'. '+ASPECTS.get(aspect,'')
                source='reperes_generaux'
            # Exemple validé par Cécile ; utilisé si aucune entrée de sa base.
            if not raw and (planet,aspect,point)==('Saturne','carré','Soleil'):
                text='Possible baisse de vitalité, sentiment de limitation ou remise en question de ta place. Ce passage invite à clarifier tes priorités, poser tes limites et prendre tes responsabilités.'
            houses=[];facts=[]
            for name in dict.fromkeys((point,planet)):
                ruled=(theme.get('house_rulers_map') or {}).get(name,[])
                for number in ruled:
                    if int(number) in DOMAINES:houses.append(int(number));facts.append(f'{name} gouverne la maison {number} natale')
                natal=(theme.get('planetes') or {}).get(name,{})
                number=natal.get('maison')
                if number and int(number) in DOMAINES:houses.append(int(number));facts.append(f'{name} natal en maison {number}')
            if c.get('maitre_ascendant'):houses.insert(0,1);facts.insert(0,point+' est maître de l’Ascendant natal')
            personnalisation = ''
            if c.get('maitre_ascendant'):
                lecture_asc = base.get(tuple(map(normaliser,(planet,aspect,'Ascendant'))))
                if lecture_asc:
                    nuance = ' '.join(re.split(r'(?<=[.!?])\s+',lecture_asc)[:2])
                    personnalisation = (point+' gouverne ton Ascendant natal. En complément, par analogie avec '+planet+' '+aspect+' Ascendant : '+nuance)

            c['lecture_courte']={'texte':text,'personnalisation':personnalisation,'domaines':[DOMAINES[n] for n in dict.fromkeys(houses)],'faits':list(dict.fromkeys(facts)),'source':source}
