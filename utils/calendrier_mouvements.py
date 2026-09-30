"""Stations et phases du calendrier, sans appel IA ni modification des emails."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import swisseph as swe

ANGLES = {"conjonction": 0, "sextile": 60, "carré": 90, "trigone": 120, "opposition": 180}
SIGNES = "Bélier Taureau Gémeaux Cancer Lion Vierge Balance Scorpion Sagittaire Capricorne Verseau Poissons".split()

@lru_cache(maxsize=32768)
def position(instant, planete):
    from utils.calendrier_personnel import PLANETES
    t = instant.astimezone(timezone.utc)
    hour = t.hour + t.minute/60 + (t.second+t.microsecond/1e6)/3600
    values = swe.calc_ut(swe.julday(t.year,t.month,t.day,hour), PLANETES[planete], swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
    return values[0], values[3]

def ecart(longitude, natal, aspect):
    return abs(abs((longitude-natal+180)%360-180)-ANGLES[aspect])

def enrichir_mouvements(resultat, theme, debut, fin):
    from utils.calendrier_personnel import PLANETES, _bisect, nom_point, cadre_mois
    points = {nom_point(k):float(v["longitude"]) for k,v in theme.get("planetes",{}).items() if v.get("longitude") is not None}
    points.update({k:float(v) for k,v in theme.get("angles_deg",{}).items() if v is not None})
    stations = []
    for planet in PLANETES:
        if planet in ("Soleil", "Lune"): continue
        a = debut.astimezone(timezone.utc)
        while a < fin:
            b = min(a+timedelta(hours=12), fin)
            va,vb = position(a,planet)[1],position(b,planet)[1]
            if (va < 0) != (vb < 0):
                t = _bisect(a,b,lambda x:position(x,planet)[1])
                lon,_ = position(t,planet)
                direction = "rétrograde" if vb < 0 else "directe"
                contacts = []
                for p in resultat["periods"]:
                    if p["planete"] != planet: continue
                    if p["start"] and t < datetime.fromisoformat(p["start"]): continue
                    if p["end"] and t >= datetime.fromisoformat(p["end"]): continue
                    contacts.append({"point":p["point"],"aspect":p["aspect"],"orbe":round(ecart(lon,points[p["point"]],p["aspect"]),3),"maitre":p["maitre_ascendant"]})
                contacts = list({(p["point"],p["aspect"]):p for p in contacts}.values())
                stations.append({"date":t.isoformat(),"kind":"station","planete":planet,"label":planet+" · station "+direction,"longitude":lon,"signe":SIGNES[int(lon//30)],"degre":round(lon%30,2),"contacts":contacts})
            a=b
    resultat["events"].extend(stations)
    # Relier aussi les passages séparés par une sortie d'orbe, dans une
    # fenêtre bornée ; ne jamais inventer un premier ou dernier passage.
    series = {}
    search_start=debut-timedelta(days=120)
    search_end=fin+timedelta(days=120)
    for planet in PLANETES:
        if planet in ("Soleil", "Lune"): continue
        keys={(p["point"],p["aspect"]) for p in resultat["periods"] if p["planete"]==planet}
        if not keys:continue
        samples=[];t=search_start
        while t<search_end:
            samples.append((t,position(t,planet)[0]));t+=timedelta(hours=6)
        samples.append((search_end,position(search_end,planet)[0]))
        for point,aspect in keys:
            found=[]
            for offset in set((ANGLES[aspect],(-ANGLES[aspect])%360)):
                target=(points[point]+offset)%360
                def delta(t):return (position(t,planet)[0]-target+180)%360-180
                for (a,la),(b,lb) in zip(samples,samples[1:]):
                    u=(la-target+180)%360-180;v=(lb-target+180)%360-180
                    if u*v<0 and abs(u-v)<180:
                        exact=_bisect(a,b,delta)
                        found.append({"date":exact.isoformat(),"retrograde":position(exact,planet)[1]<0})
            series[(planet,point,aspect)]=sorted(found,key=lambda x:x["date"])
    days = cadre_mois(debut.year,debut.month,str(debut.tzinfo))[2]
    for key in ("periods", "periods_1"):
        for p in resultat[key]:
            planet=p["planete"];natal=points[p["point"]]
            p["mouvements"]={}
            for day in days:
                a=datetime.fromisoformat(day["debut"]);b=datetime.fromisoformat(day["fin"])
                left=max(a,datetime.fromisoformat(p["start"])) if p["start"] else a
                right=min(b,datetime.fromisoformat(p["end"])) if p["end"] else b
                if left>=right:continue
                t=left+(right-left)/2
                lon,speed=position(t,planet)
                before=ecart(position(t-timedelta(minutes=5),planet)[0],natal,p["aspect"])
                after=ecart(position(t+timedelta(minutes=5),planet)[0],natal,p["aspect"])
                exacts=[x for x in p["exacts"] if a<=datetime.fromisoformat(x)<b]
                p["mouvements"][day["date"]]={"date":t.isoformat(),"retrograde":speed<0,"orbe":round(ecart(lon,natal,p["aspect"]),3),"phase":"exact" if exacts else "approche" if after<before else "eloignement","exacts":exacts}
            p["passages"]=series.get((planet,p["point"],p["aspect"]),[{"date":x,"retrograde":position(datetime.fromisoformat(x),planet)[1]<0} for x in p["exacts"]])
            p["recherche_passages"]={"debut":search_start.isoformat(),"fin":search_end.isoformat()}
