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

def get_force_planetaire():
    """
    Hiérarchie de force/dominance planétaire
    Plus le score est élevé, plus la planète a d'influence dans une configuration
    """
    return {
        # Planètes de structure/transformation (les plus puissantes)
        'Saturne': 100,    # Structure, restriction, maître du temps
        'Pluton': 95,      # Transformation profonde, pouvoir occulte
        'Mars': 90,        # Action, guerre, énergie brute
        
        # Luminaires (importants mais influençables)
        'Soleil': 85,      # Ego, identité, mais peut être éclipsé
        'Lune': 75,        # Émotions, instincts, réceptive
        
        # Planètes sociales
        'Jupiter': 80,     # Expansion, philosophie, mais bienveillant
        'Uranus': 85,      # Révolution, changement brusque
        'Neptune': 70,     # Dissolution, illusion, spiritualité
        
        # Planètes personnelles (plus malléables)
        'Mercure': 60,     # Mental, communication
        'Vénus': 65,       # Amour, beauté, harmonie
        
        # Points fictifs (influence modérée)
        'Rahu': 55,        # Nœud Nord, obsession
        'Ketu': 55,        # Nœud Sud, détachement
        'Lune Noire': 50,  # Blessures, manques
        'Chiron': 45,      # Guérison, blessure
    }


def analyser_configuration_dominante(planetes_config):
    """
    Détermine quelle planète domine une configuration (amas, conjonction, etc.)
    et comment elle influence les autres
    """
    forces = get_force_planetaire()
    
    if not planetes_config or len(planetes_config) < 2:
        return None
    
    # Trier par force décroissante
    planetes_triees = sorted(planetes_config, 
                           key=lambda p: forces.get(p, 30), 
                           reverse=True)
    
    dominante = planetes_triees[0]
    subordonnees = planetes_triees[1:]
    
    # Déterminer le type d'influence
    if dominante == 'Saturne':
        effet = "bride, discipline, responsabilise"
    elif dominante == 'Pluton':
        effet = "transforme en profondeur, intensifie"
    elif dominante == 'Mars':
        effet = "dynamise, peut agresser ou défendre"
    elif dominante == 'Uranus':
        effet = "libère, révolutionne, rend imprévisible"
    elif dominante == 'Neptune':
        effet = "dissout, idéalise, peut créer illusions"
    elif dominante == 'Jupiter':
        effet = "amplifie, bénit, philosophise"
    elif dominante == 'Soleil':
        effet = "éclaire et révèle"
    elif dominante == 'Lune':
        effet = "émotionnalise, maternise"
    else:
        effet = "colore et module"
    
    return {
        'dominante': dominante,
        'subordonnees': subordonnees,
        'effet': effet,
        'description': f"{dominante} {effet} {', '.join(subordonnees)}"
    }


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

def detecter_amas_avec_dominance(data, seuil=3, par="signe", strict=False):
    """
    Version améliorée qui détecte les amas ET leur dynamique de dominance
    """
    points = []  # 🎯 INITIALISATION OBLIGATOIRE
    planetes = data.get('planetes', {})

    # Catégories (comme avant)
    personnelles = ['Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars']
    sociales = ['Jupiter', 'Saturne'] 
    generationnelles = ['Uranus', 'Neptune', 'Pluton']
    classiques = personnelles + sociales + generationnelles

    EXCLUS = {"Ascendant", "Descendant", "Milieu du Ciel", "Fond du Ciel", "Lune Noire", "Rahu", "Ketu", "Chiron"}

    if strict:
        planetes_filtrees = {n: i for n, i in planetes.items() if n in classiques}
    else:
        planetes_filtrees = {n: i for n, i in planetes.items() if n not in EXCLUS}

    # Grouper par signe/maison
    groupes_count = {}
    for nom, infos in planetes_filtrees.items():
        cle = infos.get(par)
        if not cle:
            continue
        if par == "signe":
            cle = (cle or "").strip().replace("\xa0", " ").strip().capitalize()
        groupes_count.setdefault(cle, []).append(nom)

    # Analyse des amas avec dominance
    for localisation, planetes_liste in groupes_count.items():
        if len(planetes_liste) < seuil:
            continue
            
        # Validation d'amas (logique existante)
        pers_dans_amas = [p for p in planetes_liste if p in personnelles]
        soc_dans_amas = [p for p in planetes_liste if p in sociales]
        gen_dans_amas = [p for p in planetes_liste if p in generationnelles]
        
        nb_personnelles = len(pers_dans_amas)
        nb_sociales = len(soc_dans_amas)
        total_planetes = len(planetes_liste)
        
        print(f"🔍 Analyse amas {localisation}: {planetes_liste}")
        print(f"   - Personnelles: {pers_dans_amas} ({nb_personnelles})")
        print(f"   - Sociales: {soc_dans_amas} ({nb_sociales})")
        print(f"   - Générationnelles: {gen_dans_amas} ({nb_generationnelles})")
        
        # Règles de validation (comme avant)
        amas_valide = False
        type_amas = ""
        
        if nb_personnelles >= 3:
            amas_valide = True
            type_amas = "🌟 Amas personnel fort"
        elif nb_personnelles >= 2:
            amas_valide = True
            type_amas = "🌟 Amas personnel"
        elif nb_personnelles == 1 and nb_sociales >= 1 and total_planetes >= 3:
            amas_valide = True
            type_amas = "Amas mixte"
        elif nb_personnelles == 0 and nb_sociales >= 2:
            amas_valide = True
            type_amas = "Amas générationnel"
        else:
            print(f"   ❌ Amas non validé (pas assez de planètes personnelles)")
            continue
        
        if amas_valide:
            # 🎯 Analyse de dominance
            dominance = analyser_configuration_dominante(planetes_liste)
            
            planetes_str = ", ".join(planetes_liste)
            if dominance:
                description = f"- {type_amas} en {localisation} ({planetes_str}) → {dominance['description']}"
                print(f"   ✅ {dominance['dominante']} domine : {dominance['effet']}")
            else:
                description = f"- {type_amas} en {localisation} ({planetes_str})"
            
            points.append(description)

    print(f"🔍 DEBUG - detecter_amas_avec_dominance retourne : {points}")
    return points  # 🎯 RETOUR OBLIGATOIRE


def detecter_conjonctions_avec_dominance(aspects, seuil_orbe=5):
    """
    Détecte les conjonctions importantes et leur dynamique de dominance
    """
    points = []
    
    for aspect in aspects:
        if aspect.get('type', '').lower() != 'conjonction':
            continue
            
        orbe = float(aspect.get('orbe', 99))
        if orbe > seuil_orbe:
            continue
            
        planete1 = aspect.get('source') or aspect.get('planete1')
        planete2 = aspect.get('cible') or aspect.get('planete2')
        
        if not planete1 or not planete2:
            continue
            
        # Analyse de dominance
        dominance = analyser_configuration_dominante([planete1, planete2])
        
        if dominance:
            description = f"Conjonction {planete1}-{planete2} (orbe {orbe:.1f}°)"
            description += f" → {dominance['description']}"
            points.append(description)
        else:
            # Fallback
            points.append(f"Conjonction {planete1}-{planete2} (orbe {orbe:.1f}°)")
    
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
    points, planetes, aspects = [], data.get('planetes', {}), data.get('aspects', [])
    for L in ['Soleil','Lune']:
        if L in planetes:
            dig = evaluer_dignite(L, planetes[L].get('signe',''))
            if dig['score'] != 0:
                points.append(f"{L} {dig['dignite']} en {planetes[L].get('signe','')}")
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

def formater_points_forts_avec_dominance(data):
    """
    Version améliorée de extraire_points_forts qui intègre les dynamiques de dominance
    """
    points = []
    
    # 1. Amas avec dominance
    print("🔍 DEBUG - Appel detecter_amas_avec_dominance par signe")
    amas_signes = detecter_amas_avec_dominance(data, seuil=3, par="signe")
    print(f"🔍 DEBUG - Amas signes trouvés : {amas_signes}")
    amas_maisons = detecter_amas_avec_dominance(data, seuil=3, par="maison")
    
    if amas_signes or amas_maisons:
        points.append("### Amas et configurations")
        points.extend(amas_signes)
        points.extend(amas_maisons)
    
    # 2. Conjonctions importantes avec dominance
    aspects = data.get('aspects', [])
    conjonctions = detecter_conjonctions_avec_dominance(aspects)
    
    if conjonctions:
        points.append("### Conjonctions majeures")
        points.extend(conjonctions)
    
    # 3. Autres points forts (logique existante)
    # ... le reste de ta logique actuelle
    
    return points

def extraire_points_forts(data):
    """
    Extrait tous les points forts d'un thème astrologique avec gestion d'erreur
    et intégration de la dominance planétaire
    """
    print("🔍 DEBUG EXTRACTION - Début")
    points = []
    
    try:
        # === RÉCUPÉRATION DES DONNÉES DE BASE ===
        maisons = data.get('maisons', {})
        planetes = data.get('planetes', {})
        aspects = data.get('aspects', [])
        
        angles_degres = {
            'Ascendant': data.get('planetes', {}).get('Ascendant', {}).get('degre'),
            'Milieu du Ciel': (maisons.get('Maison 10', {}).get('degre') or maisons.get('10', {}).get('degre')),
            'Descendant': (maisons.get('Maison 7', {}).get('degre') or maisons.get('7', {}).get('degre')),
            'Fond du Ciel': (maisons.get('Maison 4', {}).get('degre') or maisons.get('4', {}).get('degre')),
        }
        angles_degres = {k: v for k, v in angles_degres.items() if v is not None}

        # === 1. DIGNITÉS/CHUTES PLANÈTES PERSONNELLES ===
        print("🔍 DEBUG - Analyse dignités")
        PERSONNELLES = ('Soleil', 'Lune', 'Mercure', 'Vénus', 'Mars')
        for p in PERSONNELLES:
            if p in planetes:
                signe = (planetes[p].get('signe', '') or '').strip().replace("\xa0", " ").strip().capitalize()
                dig = evaluer_dignite(p, signe)
                if dig.get('score', 0) != 0:
                    points.append(f"{p} {dig['dignite']} en {signe}")

        # === 2. PLANÈTES ANGULAIRES ===
        print("🔍 DEBUG - Planètes angulaires")
        try:
            angles_result = detecter_angles_importants(planetes)
            if angles_result:
                points.extend(angles_result)
        except Exception as e:
            print(f"❌ Erreur planètes angulaires : {e}")

        # === 3. ASPECTS AUX LUMINAIRES ===
        print("🔍 DEBUG - Aspects luminaires")
        try:
            aspects_result = detecter_aspects_luminaire_detaille(aspects, stricte=True)
            if aspects_result:
                points.extend(aspects_result)
        except Exception as e:
            print(f"❌ Erreur aspects luminaires : {e}")

        # === 3B. CONJONCTIONS AVEC DOMINANCE (NOUVEAU) ===
        print("🔍 DEBUG - Conjonctions avec dominance")
        try:
            conjonctions_result = detecter_conjonctions_avec_dominance(aspects, seuil_orbe=5)
            if conjonctions_result:
                points.extend(conjonctions_result)
                print(f"✅ Conjonctions dominance ajoutées : {conjonctions_result}")
            else:
                print("ℹ️ Aucune conjonction avec dominance trouvée")
        except Exception as e:
            print(f"❌ Erreur conjonctions dominance : {e}")

        # === 4. CONJONCTIONS AUX ANGLES ===
        print("🔍 DEBUG - Conjonctions angles")
        try:
            positions_degres = {k: v['degre'] for k, v in planetes.items() if 'degre' in v}
            conj_angles_result = detecter_conjonction_angles(positions_degres, angles_degres)
            if conj_angles_result:
                points.extend(conj_angles_result)
        except Exception as e:
            print(f"❌ Erreur conjonctions angles : {e}")

        # === 5. AMAS AVEC DOMINANCE (PAR SIGNE) ===
        print("🔍 DEBUG - Amas par signe avec dominance")
        try:
            amas_signes = detecter_amas_avec_dominance(data, seuil=3, par="signe", strict=False)
            if amas_signes and isinstance(amas_signes, list):
                points.extend(amas_signes)
                print(f"✅ Amas signes ajoutés : {len(amas_signes)} éléments")
            else:
                print("ℹ️ Aucun amas par signe trouvé")
        except Exception as e:
            print(f"❌ Erreur amas signes : {e}")

        # === 6. AMAS AVEC DOMINANCE (PAR MAISON) ===
        print("🔍 DEBUG - Amas par maison avec dominance")
        try:
            amas_maisons = detecter_amas_avec_dominance(data, seuil=3, par="maison", strict=False)
            if amas_maisons and isinstance(amas_maisons, list):
                points.extend(amas_maisons)
                print(f"✅ Amas maisons ajoutés : {len(amas_maisons)} éléments")
            else:
                print("ℹ️ Aucun amas par maison trouvé")
        except Exception as e:
            print(f"❌ Erreur amas maisons : {e}")

        # === 7. MAÎTRE D'ASCENDANT ===
        print("🔍 DEBUG - Maître ascendant")
        try:
            maitre_asc = qualite_maitre_asc(data)
            if maitre_asc:
                points.append(maitre_asc)
        except Exception as e:
            print(f"❌ Erreur maître ascendant : {e}")

        # === 8. ÉTAT DES LUMINAIRES ===
        print("🔍 DEBUG - État luminaires")
        try:
            luminaires_result = etat_luminaires(data)
            if luminaires_result:
                points.extend(luminaires_result)
        except Exception as e:
            print(f"❌ Erreur luminaires : {e}")

        # === 9. CONFIGURATIONS (T-CARRÉ, GRAND CARRÉ) ===
        print("🔍 DEBUG - Configurations")
        try:
            config_result = detecter_configurations(data)
            if config_result:
                points.extend(config_result)
        except Exception as e:
            print(f"❌ Erreur configurations : {e}")

        # === 10. PROFIL ÉLÉMENTS/MODALITÉS ===
        print("🔍 DEBUG - Éléments/modalités")
        try:
            profil_result = profil_elements_modalites(data)
            if profil_result:
                points.extend(profil_result)
        except Exception as e:
            print(f"❌ Erreur profil éléments : {e}")

        # === 11. CAZIMI/COMBUSTION ===
        print("🔍 DEBUG - Cazimi/combustion")
        try:
            cazimi_result = detecter_cazimi_combust(data)
            if cazimi_result:
                points.extend(cazimi_result)
        except Exception as e:
            print(f"❌ Erreur cazimi : {e}")

        # === 12. AXES CARDINAUX ===
        print("🔍 DEBUG - Axes cardinaux")
        try:
            axes_result = lister_axes_cardinaux(data)
            if axes_result:
                points.extend(axes_result)
        except Exception as e:
            print(f"❌ Erreur axes cardinaux : {e}")

        # === 13. PLANÈTES RÉTROGRADES ===
        print("🔍 DEBUG - Rétrogrades")
        try:
            retro = detecter_retrogrades(data)
            if retro:
                points.append("Planètes rétrogrades: " + ", ".join(retro))
        except Exception as e:
            print(f"❌ Erreur rétrogrades : {e}")

        # === 14. RÉCEPTIONS MUTUELLES ===
        print("🔍 DEBUG - Réceptions mutuelles")
        try:
            receptions_result = detecter_receptions(data)
            if receptions_result:
                points.extend(receptions_result)
        except Exception as e:
            print(f"❌ Erreur réceptions : {e}")

        print(f"🔍 DEBUG EXTRACTION - Fin : {len(points)} points forts totaux")
        return points

    except Exception as e:
        print(f"❌ ERREUR CRITIQUE dans extraire_points_forts : {e}")
        import traceback
        traceback.print_exc()
        return []  # Retourne une liste vide en cas d'erreur critique



