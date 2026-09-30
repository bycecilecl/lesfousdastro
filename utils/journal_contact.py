"""Valide le contact choisi contre le thème du compte courant."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.calendrier_personnel import PLANETES, RAPIDES, _periodes_planete, nom_point
DOMAINES = ("Amour", "Travail", "Foyer", "Enfants", "Santé", "Finances", "Autre")
def contact_du_jour(theme, date, tzid, planet, point, aspect):
    if planet not in PLANETES or aspect not in ("conjonction","sextile","carré","trigone","opposition"):raise ValueError("Contact invalide")
    points={nom_point(k):float(v["longitude"]) for k,v in theme.get("planetes",{}).items() if v.get("longitude") is not None}
    points.update({k:float(v) for k,v in theme.get("angles_deg",{}).items() if v is not None})
    if point not in points:raise ValueError("Point inconnu")
    a=datetime.strptime(date,"%Y-%m-%d").replace(tzinfo=ZoneInfo(tzid));b=a+timedelta(days=1)
    if not 1900<=a.year<=2100:raise ValueError("Date invalide")
    periods=json.loads(_periodes_planete(json.dumps({point:points[point]}),a.isoformat(),b.isoformat(),planet,1 if planet in RAPIDES else 3))
    if not any(p["aspect"]==aspect for p in periods):raise ValueError("Contact inactif ce jour")
    return {"planete":planet,"point":point,"aspect":aspect,"date":date,"libelle":f"{planet} {aspect} {point} natal"}
