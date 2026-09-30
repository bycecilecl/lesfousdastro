"""Calendrier personnel : transits et dates lunaires. Aucun accès BDD/LLM."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
import calendar
import json
import swisseph as swe
from utils.lunaisons import prochaines_lunaisons, EPHEMERIS_PATH
from utils.revolution_lunaire import prochaine_revolution_lunaire

PLANETES = {"Lune": swe.MOON, "Soleil": swe.SUN, "Mercure": swe.MERCURY, "Vénus": swe.VENUS,
            "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturne": swe.SATURN,
            "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluton": swe.PLUTO}
RAPIDES = {"Lune", "Soleil", "Mercure", "Vénus", "Mars"}

def maitres_ascendant(theme):
    maitre = theme.get("maitre_ascendant")
    if isinstance(maitre, str): return {maitre}
    if isinstance(maitre, dict):
        return {maitre[k] for k in ("nom", "second_nom") if maitre.get(k)}
    return set()

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")

def cadre_mois(annee, mois, tzid):
    tz = ZoneInfo(tzid)
    debut = datetime(annee, mois, 1, tzinfo=tz)
    fin = datetime(annee + (mois == 12), mois % 12 + 1, 1, tzinfo=tz)
    jours = []
    for n in range(1, calendar.monthrange(annee, mois)[1] + 1):
        jour = datetime(annee, mois, n, tzinfo=tz)
        jours.append({"date": jour.date().isoformat(), "debut": jour.isoformat(), "fin": (jour + timedelta(days=1)).isoformat(), "numero": n})
    return debut, fin, jours

def _longitude(t, planete):
    t = t.astimezone(timezone.utc)
    return swe.calc_ut(swe.julday(t.year,t.month,t.day,t.hour+t.minute/60+t.second/3600),PLANETES[planete])[0][0]

def _bisect(a,b,f):
    fa=f(a)
    while (b-a).total_seconds()>1:
        mid=a+(b-a)/2
        if (f(mid)>=0)==(fa>=0):a=mid;fa=f(a)
        else:b=mid
    return a+(b-a)/2

@lru_cache(maxsize=256)
def _periodes_planete(points_json, debut, fin, planete="Mars", orbe=3):
    points=json.loads(points_json)
    start=datetime.fromisoformat(debut).astimezone(timezone.utc)
    end=datetime.fromisoformat(fin).astimezone(timezone.utc)
    swe.set_ephe_path(str(EPHEMERIS_PATH))
    mars=lambda t: _longitude(t, planete)
    bisect=_bisect
    marge = 5 if planete == "Lune" else 120
    pas = 1 if planete == "Lune" else 6
    lo=start-timedelta(days=marge);hi=end+timedelta(days=marge)
    ts=[lo+timedelta(hours=pas*i) for i in range(int((hi-lo).total_seconds()/(pas*3600))+1)]
    longitudes=[mars(t) for t in ts];periods=[]
    for point,lon in points.items():
     for aspect,angle in [('conjonction',0),('sextile',60),('carré',90),('trigone',120),('opposition',180)]:
      for offset in sorted(set([angle,(-angle)%360])):
       target=(lon+offset)%360
       def delta(t):return (mars(t)-target+180)%360-180
       vals=[(m-target+180)%360-180 for m in longitudes]
       # L'intervalle doit rester dans le signe correspondant à l'aspect.
       # Tous les angles retenus sont des multiples de 30 degrés.
       degree=lon%30
       lower=max(-orbe,-degree);upper=min(orbe,30-degree)
       inside=lower<=vals[0]<upper;begin=lo if inside else None;exacts=[]
       for i in range(1,len(ts)):
        a,b=ts[i-1],ts[i];u,v=vals[i-1],vals[i]
        if abs(u-v)>180:continue
        now=lower<=v<upper
        if now!=inside:
         left,right=a,b
         while (right-left).total_seconds()>1:
          middle=left+(right-left)/2
          if (lower<=delta(middle)<upper)==inside:left=middle
          else:right=middle
         boundary=left+(right-left)/2
         if now:begin=boundary;exacts=[]
         else:
          if begin<end and boundary>start:
           periods.append({'planete':planete,'lente':planete not in RAPIDES,'point':point,'aspect':aspect,'start':begin.isoformat() if begin != lo else None,'end':boundary.isoformat(),'exacts':[x.isoformat() for x in exacts]})
          begin=None;exacts=[]
         inside=now
        if u*v<0 and abs(u-v)<180:exacts.append(bisect(a,b,delta))
       if inside and begin<end and hi>start:
        periods.append({'planete':planete,'lente':planete not in RAPIDES,'point':point,'aspect':aspect,'start':begin.isoformat() if begin != lo else None,'end':None,'exacts':[x.isoformat() for x in exacts]})
    periods.sort(key=lambda p:p['start'] or '')
    # Vérification numérique indépendante des bornes et passages exacts.
    for p in periods:
     angle={'conjonction':0,'sextile':60,'carré':90,'trigone':120,'quinconce':150,'opposition':180}[p['aspect']]
     def orb(t):return abs(abs((mars(t)-points[p['point']]+180)%360-180)-angle)
     for edge in ['start','end']:
      if p[edge]:
       instant=datetime.fromisoformat(p[edge]);longitude=mars(instant)
       # Une borne vient de l'orbe OU de l'entrée/sortie du signe.
       assert abs(orb(instant)-orbe)<.001 or min(longitude%30,30-longitude%30)<.001
     for x in p['exacts']:assert orb(datetime.fromisoformat(x))<.001
    return json.dumps(periods, ensure_ascii=False)

def nom_point(nom):
    return {"Rahu":"Nœud Nord", "Ketu":"Nœud Sud"}.get(nom, nom)


def liens_nataux_planete(theme, planete="Mars"):
    liens = {}
    for aspect in theme.get("aspects") or []:
        if not isinstance(aspect, dict) or not aspect.get("aspect"): continue
        a, b = nom_point(aspect.get("planete1")), nom_point(aspect.get("planete2"))
        cible = b if a == planete else a if b == planete else None
        if cible:
            liens[cible] = {"aspect": aspect["aspect"], "orbe": aspect.get("orbe")}
    return liens


def hierarchiser_contacts(resultat, debut, fin, cycles_rs=()):
    """Applique la règle éditoriale ; sépare les rapides aux frontières des RS."""
    def instant(valeur):
        d = datetime.fromisoformat(valeur) if isinstance(valeur, str) else valeur
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    cycles = sorted([{**r, "debut":instant(r["debut"]), "fin":instant(r["fin"])} for r in cycles_rs], key=lambda r:r["debut"])
    for cle in ("periods", "periods_1"):
        classes = []
        for original in resultat[cle]:
            if (original["planete"],original["point"],original["aspect"]) == ("Lune","Lune","conjonction"):
                continue
            if (original["planete"],original["point"],original["aspect"]) == ("Soleil","Soleil","conjonction"):
                if cle == "periods":
                    for exact in original["exacts"]:
                        t=instant(exact)
                        if debut <= t < fin:
                            resultat["events"].append({"date":t.astimezone(debut.tzinfo).isoformat(),"label":"Ton retour solaire — début de ton année astrologique","kind":"solar"})
                continue
            start=instant(original["start"]) if original["start"] else debut
            end=instant(original["end"]) if original["end"] else fin
            bornes = {start,end}
            if not original["lente"]:
                bornes.update(t for r in cycles for t in (r["debut"],r["fin"]) if start < t < end)
            bornes=sorted(bornes)
            for gauche,droite in zip(bornes,bornes[1:]):
                if gauche >= fin or droite <= debut: continue
                c=dict(original)
                if len(bornes)>2:
                    c["start"],c["end"]=gauche.isoformat(),droite.isoformat()
                    c["exacts"]=[x for x in original["exacts"] if gauche <= instant(x) < droite]
                    c["selection_segmentee_rs"]=True
                raisons=[]
                if c["maitre_ascendant"]:raisons.append("Contact au maître de ton Ascendant natal : " + c["point"] + ".")
                if c.get("lien_natal"):raisons.append("Duo présent au natal : " + c["planete"] + "–" + c["point"] + " (" + c["lien_natal"]["aspect"] + ").")
                rs=next((r for r in reversed(cycles) if r["debut"] <= gauche+(droite-gauche)/2 < r["fin"]),None)
                if not c["lente"] and rs and c["point"] in (set(PLANETES) - RAPIDES):
                    lien=liens_nataux_planete(rs["theme"],c["planete"]).get(c["point"])
                    if lien:
                        c["lien_rs"]={**lien,"cycle_id":rs.get("id"),"debut":rs["debut"].isoformat(),"fin":rs["fin"].isoformat()}
                        raisons.append("Duo présent dans la RS du " + rs["debut"].strftime("%d/%m/%Y") + " : " + c["planete"] + "–" + c["point"] + " (" + lien["aspect"] + "). Il s’agit d’un écho au duo annuel, pas d’un contact direct à une position de RS.")
                if c["lente"]:
                    c["niveau"]="prioritaire"
                    raisons.insert(0,"Climat de fond : transit de " + c["planete"] + " actif dans l’orbe de 3°.")
                elif c.get("lien_natal") or c["maitre_ascendant"] or c.get("lien_rs"):
                    c["niveau"]="declencheur"
                else:
                    c["niveau"]="climat"
                    raisons.append("Aucun des trois critères retenu : duo natal, maître d’Ascendant ou duo dans une RS disponible pour cette date.")
                if c.get("selection_segmentee_rs"):raisons.append("Fenêtre affichée découpée au changement de RS ; la période à 3° reste indiquée séparément.")
                c["raisons"]=raisons
                classes.append(c)
        resultat[cle]=classes


def donnees_astrales(theme, debut, fin, *, mars_actif=False, lune_active=False, cycles_rs=()):
    resultat={"periods": [], "periods_1": [], "events": []}
    maitres = maitres_ascendant(theme)
    resultat["maitres_ascendant"] = sorted(maitres)
    resultat["planetes_disponibles"] = list(PLANETES) if mars_actif else []
    if mars_actif:
        for planete in PLANETES:
            liens = liens_nataux_planete(theme, planete)
            cibles = set(PLANETES) | {"Lune"}
            # Les contacts aux nœuds sont réservés au climat des lentes.
            if planete not in RAPIDES:
                cibles |= {"Nœud Nord", "Nœud Sud"}
            points={nom_point(k): float(v["longitude"]) for k,v in theme.get("planetes", {}).items()
                    if nom_point(k) in cibles and v.get("longitude") is not None}
            points.update({k: float(v) for k,v in theme.get("angles_deg", {}).items() if v is not None})
            larges=json.loads(_periodes_planete(json.dumps(points,sort_keys=True),debut.isoformat(),fin.isoformat(),planete,1 if planete == "Lune" else 3))
            proches=json.loads(_periodes_planete(json.dumps(points,sort_keys=True),debut.isoformat(),fin.isoformat(),planete,1))
            for contact in larges + proches:
                contact["maitre_ascendant"] = contact["point"] in maitres
                if contact["point"] in liens: contact["lien_natal"] = liens[contact["point"]]
            for contact in proches:
                for periode in larges:
                    if (contact["point"], contact["aspect"]) != (periode["point"], periode["aspect"]): continue
                    if ((not periode["start"] or not contact["start"] or periode["start"] <= contact["start"])
                            and (not periode["end"] or not contact["end"] or periode["end"] >= contact["end"])):
                        contact["start_3"], contact["end_3"] = periode["start"], periode["end"]
                        break
            resultat["periods"].extend(larges)
            resultat["periods_1"].extend(proches)
    if lune_active:
        for x in prochaines_lunaisons(apres=debut, tzid=str(debut.tzinfo), nombre=3):
            instant=datetime.fromisoformat(x["instant_utc"])
            if debut <= instant < fin:
                resultat["events"].append({"date":x["instant_local"], "label":("Nouvelle Lune" if x["type"]=="nouvelle_lune" else "Pleine Lune") + " en " + x["position"]["signe"]})
        longitude=theme.get("planetes",{}).get("Lune",{}).get("longitude")
        if longitude is not None:
            curseur=debut.astimezone(timezone.utc)
            for _ in range(3):
                instant=prochaine_revolution_lunaire(float(longitude),apres=curseur)
                if instant >= fin:break
                if instant >= debut:
                    resultat["events"].append({"date":instant.astimezone(debut.tzinfo).isoformat(),"label":"Début de ta révolution lunaire"})
                curseur=instant+timedelta(minutes=1)
    hierarchiser_contacts(resultat, debut, fin, cycles_rs)
    if mars_actif:
        from utils.calendrier_mouvements import enrichir_mouvements
        enrichir_mouvements(resultat, theme, debut, fin)
        from utils.calendrier_lectures import enrichir_lectures
        enrichir_lectures(resultat, theme)
    return resultat
