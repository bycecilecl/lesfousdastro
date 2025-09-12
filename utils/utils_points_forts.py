"""
===========================================================
FICHIER : utils/points_forts.py
===========================================================

RÔLE :
------
Ce module regroupe toutes les fonctions permettant de 
détecter, calculer et formater les "points forts" d'un 
thème astrologique, c’est-à-dire les éléments qui se 
démarquent par leur position, dignité ou relation aux angles.

UTILISATION :
-------------
- Utilisé principalement dans :
    - analyse_gratuite()
    - analyse_point_astral()
    - calcul_theme() (via extraction des points forts)
- Produit une liste de points forts (chaînes de texte) 
  qui peuvent être injectés directement dans les prompts LLM.

FONCTIONS PRINCIPALES :
-----------------------
1. Détection d’éléments notables :
   - est_angulaire(maison) : Vérifie si une maison est angulaire.
   - detecter_angles_importants() : Planètes en maisons angulaires.
   - detecter_conjonction_angles() : Conjonctions proches avec Asc/MC/DC/FC.
   - detecter_amas() : Regroupe les amas par signe ou maison.
   - detecter_configurations() : T-carrés, grands carrés.
   - detecter_cazimi_combust() : Planètes combustes ou cazimi.

2. Évaluation qualitative :
   - evaluer_dignite() : Domicile, exaltation, exil, chute.
   - qualite_maitre_asc() : État du maître d’ascendant.
   - etat_luminaires() : Dignité + aspect Soleil/Lune.
   - profil_elements_modalites() : Dominances / absences.

3. Particularités planétaires :
   - detecter_retrogrades() : Planètes rétrogrades.
   - detecter_receptions() : Réceptions mutuelles.
   - detecter_aspects_luminaire_detaille() : Aspects précis aux luminaires.

4. Extraction globale :
   - extraire_points_forts(data) :
       → Combine toutes les détections ci-dessus
       → Retourne une liste prête à être utilisée dans les analyses.

NOTES :
-------
- Les orbes sont paramétrables dans certaines fonctions.
- Certaines fonctions ont un mode `strict` pour filtrer sur 
  les planètes classiques.
- Le fichier produit UNIQUEMENT des chaînes prêtes à l’affichage,
  pas de structures complexes.

===========================================================
"""

def est_angulaire(maison):
    try:
        m = int(maison)
    except Exception:
        return maison in [1, 4, 7, 10]
    return m in [1, 4, 7, 10]

def detecter_angles_importants(planetes, include_lune_noire=True):
    points = []
    # On exclut les nœuds et les angles, mais on laisse la Lune Noire si include_lune_noire=True
    EXCLUS = {"Rahu", "Ketu", "Ascendant", "Descendant", "Milieu du Ciel", "Fond du Ciel"}
    if not include_lune_noire:
        EXCLUS.add("Lune Noire")

    for nom, infos in planetes.items():
        if nom in EXCLUS:
            continue
        maison = infos.get('maison')
        if maison and est_angulaire(maison):
            points.append(f"{nom} en maison angulaire ({maison})")
    return points

def detecter_amas(data, seuil=3, par="signe", strict=False):
    points = []
    planetes = data.get('planetes', {})

    # Catégories
    pers = ['Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars']
    soc  = ['Jupiter', 'Saturne']
    gen  = ['Uranus', 'Neptune', 'Pluton']
    classiques = pers + soc + gen

    # Exclusions possibles (si jamais tu veux strict=True+exclure angles/noeuds)
    EXCLUS = {"Ascendant","Descendant","Milieu du Ciel","Fond du Ciel","Lune Noire","Rahu","Ketu"}

    if strict:
        planetes_filtrees = {n:i for n,i in planetes.items() if n in classiques}
    else:
        planetes_filtrees = {n:i for n,i in planetes.items() if n not in EXCLUS}

    groupes_count = {}
    for nom, infos in planetes_filtrees.items():
        cle = infos.get(par)
        if not cle:
            continue
        if par == "signe":
            cle = (cle or "").strip().replace("\xa0", " ").strip().capitalize()
        groupes_count.setdefault(cle, []).append(nom)

    # DEBUG utile
    if par == "signe":
        print("DEBUG amas/signes:", [(k, len(v)) for k,v in groupes_count.items() if len(v) >= 2])
    else:
        print("DEBUG amas/maisons:", [(k, len(v)) for k,v in groupes_count.items() if len(v) >= 2])

    def categoriser(liste):
        nb_pers = len([p for p in liste if p in pers])
        nb_soc  = len([p for p in liste if p in soc])
        nb_gen  = len([p for p in liste if p in gen])
        if nb_pers >= 2:
            return "personnel"
        if nb_pers >= 1 and (nb_soc + nb_gen) >= 2:
            return "mixte"
        if nb_soc >= 1 and nb_gen >= 2:
            return "social-générationnel"
        if nb_gen >= 3:
            return "générationnel"
        return "standard"

    for groupe, liste in groupes_count.items():
        if len(liste) >= seuil:
            typ = categoriser(liste)
            if typ == "générationnel":
                points.append(f"Amas générationnel en {groupe} ({', '.join(liste)}) - effet collectif")
            elif typ == "personnel":
                points.append(f"🌟 Amas personnel en {groupe} ({', '.join(liste)})")
            elif typ == "mixte":
                points.append(f"Amas mixte en {groupe} ({', '.join(liste)})")
            else:
                points.append(f"Amas planétaire en {groupe} ({', '.join(liste)})")
    return points

def evaluer_dignite(planete, signe):
    domiciles = {
        'Soleil': ['Lion'], 'Lune': ['Cancer'], 'Mercure': ['Gémeaux', 'Vierge'],
        'Vénus': ['Taureau', 'Balance'], 'Mars': ['Bélier', 'Scorpion'],
        'Jupiter': ['Sagittaire', 'Poissons'], 'Saturne': ['Capricorne', 'Verseau']
    }
    exalt = {
        'Soleil': ['Bélier'], 'Lune': ['Taureau'], 'Mercure': ['Vierge'],
        'Vénus': ['Poissons'], 'Mars': ['Capricorne'], 'Jupiter': ['Cancer'],
        'Saturne': ['Balance']
    }
    exils = {
        'Soleil': ['Verseau'], 'Lune': ['Capricorne'], 'Mercure': ['Sagittaire', 'Poissons'],
        'Vénus': ['Scorpion', 'Bélier'], 'Mars': ['Balance', 'Taureau'],
        'Jupiter': ['Gémeaux', 'Vierge'], 'Saturne': ['Cancer', 'Lion']
    }
    chutes = {
        'Soleil': ['Balance'], 'Lune': ['Scorpion'], 'Mercure': ['Poissons'],
        'Vénus': ['Vierge'], 'Mars': ['Cancer'], 'Jupiter': ['Capricorne'],
        'Saturne': ['Bélier']
    }
    signe = (signe or "").strip().replace("\xa0"," ").strip().capitalize()
    if planete in domiciles and signe in domiciles[planete]: return {"dignite":"domicile","score":2}
    if planete in exalt and signe in exalt[planete]:         return {"dignite":"exaltation","score":1}
    if planete in exils and signe in exils[planete]:         return {"dignite":"exil","score":-2}
    if planete in chutes and signe in chutes[planete]:       return {"dignite":"chute","score":-1}
    return {"dignite":"neutre","score":0}

def qualite_maitre_asc(data):
    planetes = data.get('planetes', {})
    asc_signe = planetes.get('Ascendant', {}).get('signe')
    if not asc_signe:
        return "Signe de l'Ascendant non trouvé"

    maitres = {
        'Bélier':'Mars','Taureau':'Vénus','Gémeaux':'Mercure','Cancer':'Lune',
        'Lion':'Soleil','Vierge':'Mercure','Balance':'Vénus','Scorpion':'Mars',
        'Sagittaire':'Jupiter','Capricorne':'Saturne','Verseau':'Saturne','Poissons':'Jupiter'
    }
    maitre = maitres.get((asc_signe or "").strip().capitalize())
    if not maitre or maitre not in planetes:
        return f"Maître d'Ascendant ({maitre}) non trouvé"

    infos = planetes[maitre]
    tags = []
    dig = evaluer_dignite(maitre, infos.get('signe', ''))
    if dig['score'] > 0: tags.append(f"dignifié ({dig['dignite']})")
    elif dig['score'] < 0: tags.append(f"débilité ({dig['dignite']})")
    maison = infos.get('maison')
    if maison and est_angulaire(maison): tags.append("angulaire")
    return f"Maître d'Ascendant ({maitre}) {' et '.join(tags) if tags else 'en position neutre'}"

def etat_luminaires(data):
    """
    Version corrigée - ne traite QUE les aspects Soleil-Lune
    Les dignités sont déjà traitées dans la section PERSONNELLES de extraire_points_forts()
    """
    points = []
    aspects = data.get('aspects', [])
    
    # Traiter SEULEMENT les aspects Soleil-Lune (pas les dignités)
    for a in aspects:
        if {a.get('planete1'), a.get('planete2')} == {'Soleil','Lune'}:
            orbe = a.get('orbe', 0)
            if orbe <= 8:
                t = (a.get('aspect','') or '').lower()
                if t in ['conjonction','trigone','sextile']:
                    points.append(f"Aspect harmonique Soleil-Lune: {a['aspect']} (orbe {orbe}°)")
                else:
                    points.append(f"Aspect tendu Soleil-Lune: {a['aspect']} (orbe {orbe}°)")
    return points

def detecter_configurations(data):
    cfg, aspects = [], data.get('aspects', [])
    trig = [a for a in aspects if (a.get('aspect','').lower()=='trigone' and a.get('orbe',0)<=8)]
    car  = [a for a in aspects if (a.get('aspect','').lower()=='carré' and a.get('orbe',0)<=8)]
    opp  = [a for a in aspects if (a.get('aspect','').lower()=='opposition' and a.get('orbe',0)<=8)]
    #if len(trig) >= 3: cfg.append("Possible Grand Trigone détecté")
    if len(car) >= 2 and len(opp) >= 1: cfg.append("Possible T-carré détecté")
    if len(car) >= 4 and len(opp) >= 2: cfg.append("Possible Grand Carré détecté")
    return cfg

def profil_elements_modalites(data):
    points, planetes = [], data.get('planetes', {})
    elements = {'Bélier':'Feu','Taureau':'Terre','Gémeaux':'Air','Cancer':'Eau',
                'Lion':'Feu','Vierge':'Terre','Balance':'Air','Scorpion':'Eau',
                'Sagittaire':'Feu','Capricorne':'Terre','Verseau':'Air','Poissons':'Eau'}
    modalites = {'Bélier':'Cardinal','Taureau':'Fixe','Gémeaux':'Mutable','Cancer':'Cardinal',
                 'Lion':'Fixe','Vierge':'Mutable','Balance':'Cardinal','Scorpion':'Fixe',
                 'Sagittaire':'Mutable','Capricorne':'Cardinal','Verseau':'Fixe','Poissons':'Mutable'}
    count_e, count_m = {}, {}
    classiques = ['Soleil','Lune','Mercure','Vénus','Mars','Jupiter','Saturne']
    for p in classiques:
        if p in planetes:
            s = (planetes[p].get('signe','') or '').strip().replace("\xa0"," ").strip().capitalize()
            if s in elements:
                e, m = elements[s], modalites[s]
                count_e[e] = count_e.get(e,0)+1
                count_m[m] = count_m.get(m,0)+1
    for e,c in count_e.items():
        if c>=3: points.append(f"Dominance {e} ({c} planètes)")
        elif c==0: points.append(f"Singleton/Absence {e}")
    for m,c in count_m.items():
        if c>=3: points.append(f"Dominance {m} ({c} planètes)")
        elif c==0: points.append(f"Singleton/Absence {m}")
    return points

def detecter_cazimi_combust(data):
    points = []
    aspects = data.get('aspects', [])

    # Planètes concernées par la combustion (classiques)
    combustibles = {'Mercure','Vénus','Mars','Jupiter','Saturne'}  # pas d’Ascendant, pas d’outer
    for aspect in aspects:
        p1, p2 = aspect['planete1'], aspect['planete2']
        if 'Soleil' not in (p1, p2):
            continue
        if aspect.get('aspect','').lower() != 'conjonction':
            continue
        orbe = float(aspect.get('orbe', 99))
        autre = p2 if p1 == 'Soleil' else p1

        if autre not in combustibles:
            continue  # on ignore Ascendant, Pluton, etc.

        if orbe <= 0.17:
            points.append(f"Cazimi: {autre} au cœur du Soleil (orbe {orbe}°)")
        elif orbe <= 8:
            points.append(f"Combustion: {autre} brûlé par le Soleil (orbe {orbe}°)")
    return points

def detecter_retrogrades(data):
    return [f"{n} rétrograde" for n,infos in data.get('planetes',{}).items() if infos.get('retrograde',False)]

def detecter_receptions(data):
    points, planetes = [], data.get('planetes', {})
    maitres = {'Bélier':'Mars','Taureau':'Vénus','Gémeaux':'Mercure','Cancer':'Lune',
               'Lion':'Soleil','Vierge':'Mercure','Balance':'Vénus','Scorpion':'Mars',
               'Sagittaire':'Jupiter','Capricorne':'Saturne','Verseau':'Saturne','Poissons':'Jupiter'}
    classiques = ['Soleil','Lune','Mercure','Vénus','Mars','Jupiter','Saturne']
    for p1 in classiques:
        for p2 in classiques:
            if p1==p2 or p1 not in planetes or p2 not in planetes: 
                continue
            s1 = (planetes[p1].get('signe','') or '').strip().replace("\xa0"," ").strip().capitalize()
            s2 = (planetes[p2].get('signe','') or '').strip().replace("\xa0"," ").strip().capitalize()
            if maitres.get(s2)==p1 and maitres.get(s1)==p2:
                points.append(f"Réception mutuelle: {p1} en {s1} ↔ {p2} en {s2}")
    return points

def detecter_aspects_luminaire_detaille(aspects, stricte=True):
    """
    Retourne les aspects Soleil/Lune considérés forts (si stricte=True)
    - Majeurs (conj/opp/carré) : orbe <= 4°
    - Harmonique (trigone/sextile) : orbe <= 2.5°
    Si stricte=False : garde l’ancien comportement.
    """
    luminaires = ['Soleil', 'Lune']
    priorite_map = {'conjonction': 0, 'carré': 1, 'opposition': 2, 'trigone': 3, 'sextile': 4}

    def passe_filtre(aspect_type, orbe):
        if not stricte:
            return True
        t = aspect_type.lower()
        if t in ('conjonction', 'carré', 'carre', 'opposition'):
            return orbe <= 4
        if t in ('trigone', 'sextile'):
            return orbe <= 2.5
        return False

    filtres = []
    for asp in aspects:
        if asp.get('planete1') in luminaires or asp.get('planete2') in luminaires:
            t = asp.get('aspect','').lower()
            orbe = float(asp.get('orbe', 99))
            if passe_filtre(t, orbe):
                filtres.append(asp)

    # tri “important d’abord”
    def priorite(asp):
        t = asp.get('aspect','').lower()
        orbe = float(asp.get('orbe', 99))
        base = priorite_map.get(t, 5)
        return (base, orbe)

    filtres_trie = sorted(filtres, key=priorite)

    res = []
    for asp in filtres_trie:
        p1, p2 = asp['planete1'], asp['planete2']
        t = asp['aspect']
        orbe = asp.get('orbe', '?')
        res.append(f"{p1} {t} {p2} (orbe {orbe}°)")
    return res

def detecter_conjonction_angles(positions, angles_degres, seuil_orbe=5):
    points = []
    for planete, deg_planete in positions.items():
        for angle, deg_angle in angles_degres.items():
            if planete.lower() == angle.lower():
                continue
            diff = abs((deg_planete - deg_angle + 180) % 360 - 180)
            if diff <= seuil_orbe:
                points.append(f"{planete} en conjonction avec l'angle {angle} (écart {round(diff,2)}°)")
    return points

def lister_axes_cardinaux(data):
    maisons = data.get('maisons', {})
    angles = {
        'Ascendant': data.get('planetes', {}).get('Ascendant', {}).get('signe'),
        'Descendant': maisons.get('Maison 7', {}).get('signe') or maisons.get('7', {}).get('signe'),
        'Milieu du Ciel': maisons.get('Maison 10', {}).get('signe') or maisons.get('10', {}).get('signe'),
        'Fond du Ciel': maisons.get('Maison 4', {}).get('signe') or maisons.get('4', {}).get('signe')
    }
    result = []
    for angle, signe in angles.items():
        if signe:
            result.append(f"{angle} en {signe}")
    return result

def extraire_points_forts(data):
    points = []
    maisons = data.get('maisons', {})
    angles_degres = {
        'Ascendant': data.get('planetes', {}).get('Ascendant', {}).get('degre'),
        'Milieu du Ciel': (maisons.get('Maison 10', {}).get('degre') or maisons.get('10', {}).get('degre')),
        'Descendant':     (maisons.get('Maison 7', {}).get('degre')  or maisons.get('7',  {}).get('degre')),
        'Fond du Ciel':   (maisons.get('Maison 4', {}).get('degre')  or maisons.get('4',  {}).get('degre')),
    }
    angles_degres = {k:v for k,v in angles_degres.items() if v is not None}

    planetes = data.get('planetes', {})
    aspects   = data.get('aspects', [])

    # -- Dignités/chutes pour planètes personnelles (ajout Mercure/Vénus/Mars) --
    PERSONNELLES = ('Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars')
    for p in PERSONNELLES:
        if p in planetes:
            signe = (planetes[p].get('signe','') or '').strip().replace("\xa0"," ").strip().capitalize()
            dig = evaluer_dignite(p, signe)
            if dig.get('score', 0) != 0:
                points.append(f"{p} {dig['dignite']} en {signe}")

    points += detecter_angles_importants(planetes)
    points += detecter_aspects_luminaire_detaille(aspects, stricte=True)
    points += detecter_conjonction_angles({k:v['degre'] for k,v in planetes.items() if 'degre' in v}, angles_degres)

    # Amas (toutes planètes, sinon passe strict=True pour “classiques”)
    points += detecter_amas(data, seuil=3, par="signe", strict=False)
    points += detecter_amas(data, seuil=3, par="maison", strict=False)

    # Maître d’Ascendant
    points.append(qualite_maitre_asc(data))

    # Luminaires, configs, profils, phénomènes, rétro, réceptions
    points += etat_luminaires(data)
    points += detecter_configurations(data)
    points += profil_elements_modalites(data)
    points += detecter_cazimi_combust(data)
    points += lister_axes_cardinaux(data)

    retro = detecter_retrogrades(data)
    if retro:
        points.append("Planètes rétrogrades: " + ", ".join(retro))

    points += detecter_receptions(data)
    return points



