"""Contradictions explicites de placement, maîtrise et aspect ; aucune réécriture ni appel IA.

Ce contrôle volontairement limité ne certifie pas la totalité du rapport.
Les alertes heuristiques historiques restent distinctes des erreurs bloquantes.
"""
import re
import unicodedata
from .verification_rapport import AFFICHAGE_VERS_INTERNE, ROMAINS
from .archives_generation import GenerationARevoir

VERSION = 4

class RapportFactuelInvalide(GenerationARevoir):
    """La réponse payée est conservée mais sa livraison est suspendue."""


def _normaliser(texte):
    texte = unicodedata.normalize('NFD', texte.lower().replace('œ', 'oe').replace('’', "'"))
    return ''.join(c for c in texte if unicodedata.category(c) != 'Mn')


def controler_placements(texte, donnees):
    erreurs = []
    noms = '|'.join(re.escape(n) for n in sorted(AFFICHAGE_VERS_INTERNE, key=len, reverse=True))
    # Le sujet et le placement doivent se suivre : jamais de recherche à travers
    # une maîtrise, une autre planète ou un changement de référentiel.
    motif = re.compile(
        rf"\b(?P<point>{noms})\s+(?P<source>rs|natale?)\s+"
        r"(?:(?:est|se trouve|tombe|est placee?|se situe)\s+)?"
        r"(?:en|dans (?:ta |la )?)\s*maison\s+(?P<maison>\d+|[ivx]+)\b"
        r"(?:\s+(?P<cible>rs|natale?)\b)?"
    )
    for phrase in re.split(r'(?<=[.!?;])\s+|\n', texte):
        normalise = _normaliser(phrase.replace('**', '').replace('*', ''))
        # Les citations, hypothèses et négations ne sont pas des assertions sûres.
        if re.search(r"\b(si|pas|jamais|pourrait|serait|supposons|exemple)\b|[«»\"]", normalise):
            continue
        for match in motif.finditer(normalise):
            point = AFFICHAGE_VERS_INTERNE[match['point']]
            source = 'rs' if match['source'] == 'rs' else 'natal'
            cible = ('rs' if match['cible'] == 'rs' else 'natal') if match['cible'] else source
            if source == 'natal' and cible == 'rs':
                continue  # Projection inverse non fournie par ce contrat.
            collection = 'placements_rs' if source == 'rs' else 'placements_natals_verifies'
            champ = 'maison_natale' if source == 'rs' and cible == 'natal' else 'maison'
            attendu = (donnees.get(collection, {}).get(point) or {}).get(champ)
            annonce = int(match['maison']) if match['maison'].isdigit() else ROMAINS.get(match['maison'])
            if attendu is None or annonce is None:
                continue
            if annonce != int(attendu):
                erreurs.append({'code': 'maison_contradictoire', 'point': point,
                    'source': source, 'cible': cible, 'annonce': annonce,
                    'attendu': int(attendu), 'fait': f'{collection}.{point}.{champ}',
                    'extrait': phrase.strip()})
    autres_erreurs, avertissements = _controles_maitrises_aspects(texte, donnees)
    erreurs.extend(autres_erreurs)
    erreurs_figures, alertes_figures = _controles_angles_figures(texte, donnees)
    erreurs.extend(erreurs_figures)
    avertissements.extend(alertes_figures)
    erreurs_roles, alertes_roles = _controles_composition_figures(texte, donnees)
    erreurs.extend(erreurs_roles)
    avertissements.extend(alertes_roles)
    return {'version': VERSION, 'portee': 'placements, maîtrises, aspects, angularités et éléments des grands trigones et rôles des T-carrés/diamants explicitement identifiés',
            'avertissements': avertissements,
            'statut': 'bloque' if erreurs else 'aucune_contradiction_identifiee',
            'erreurs': erreurs}


def _entier(valeur):
    return int(valeur) if str(valeur).isdigit() else ROMAINS.get(str(valeur))


def corriger_references_maitrises(texte, donnees, erreurs):
    """Corrige seulement une confusion natale/RS prouvée par les deux maîtrises.

    Une phrase ambiguë, une liste de maisons ou un autre type d'erreur reste
    intact et sera traité par le circuit normal de relance de la RS payée.
    """
    corrections = []
    for erreur in erreurs:
        if erreur.get('code') != 'maitrise_contradictoire' or erreur.get('reference') != 'natales':
            continue
        point, maison = erreur.get('point'), erreur.get('annonce')
        fiche = donnees.get('placements_rs', {}).get(point, {})
        maisons_rs = {_entier(n) for n in fiche.get('maisons_gouvernees_rs', [])}
        maisons_rs.update(_entier(n.get('maison')) for n in fiche.get('maisons_gouvernees_interceptees_rs', []))
        maisons_natales = {_entier(n) for n in fiche.get('maisons_gouvernees_natales', [])}
        maisons_natales.update(_entier(n.get('maison')) for n in fiche.get('maisons_gouvernees_interceptees_natales', []))
        if maison not in maisons_rs or maison in maisons_natales:
            continue
        extrait = erreur.get('extrait') or ''
        if not extrait or texte.count(extrait) != 1:
            continue
        motif = re.compile(r'\bmaison\s+(?P<numero>\d+|[IVX]+)\s+natale\b', re.I)
        occurrences = [m for m in motif.finditer(extrait) if _entier(m['numero'].lower()) == maison]
        if len(occurrences) != 1:
            continue
        occurrence = occurrences[0]
        nouveau_extrait = (
            extrait[:occurrence.start()] + occurrence.group().replace('natale', 'de révolution solaire')
            + extrait[occurrence.end():]
        )
        if nouveau_extrait == extrait:
            continue
        texte = texte.replace(extrait, nouveau_extrait, 1)
        corrections.append({
            'code': 'reference_maitrise_rs', 'point': point, 'maison': maison,
            'avant': extrait, 'apres': nouveau_extrait,
        })
    return texte, corrections


def _controles_maitrises_aspects(texte, donnees):
    erreurs, avertissements = [], []
    noms = '|'.join(re.escape(n) for n in sorted(AFFICHAGE_VERS_INTERNE, key=len, reverse=True))
    nombre = r'(?:\d+|[ivx]+)\b'
    maitrise = re.compile(
        rf'\b(?P<point>{noms})(?:\s+(?:rs|natale?))?\s+'
        rf'gouverne(?: aussi)?\s+(?:(?:ta|tes|la|les)\s+)?maisons?\s+'
        rf'(?P<maisons>{nombre}(?:(?:\s*,\s*|\s+et\s+){nombre})*)\s+'
        r'(?P<reference>rs|natales?)\b')
    aspect = re.compile(
        rf'\b(?P<p1>{noms})\s+(?P<r1>rs|natale?)\s+'
        r'(?:(?:forme|fait)\s+(?:un|une)\s+|(?:est\s+)?en\s+)?'
        r'(?P<aspect>conjonction|opposition|carre|trigone|sextile|quinconce)\s+'
        rf'(?:avec|a)\s+(?:(?:ta|ton|le|la)\s+|l\x27)?'
        rf'(?P<p2>{noms})\s+(?P<r2>rs|natale?)\b')
    for phrase in re.split(r'(?<=[.!?;])\s+|\n', texte):
        normalise = _normaliser(phrase.replace('*', ''))
        if re.search(r'\b(si|pas|jamais|pourrait|serait|supposons|exemple)\b|[«»"]', normalise):
            continue
        for m in maitrise.finditer(normalise):
            point = AFFICHAGE_VERS_INTERNE[m['point']]
            suffixe = 'rs' if m['reference'] == 'rs' else 'natales'
            fiche = donnees.get('placements_rs', {}).get(point, {})
            champ = f'maisons_gouvernees_{suffixe}'
            interceptions = f'maisons_gouvernees_interceptees_{suffixe}'
            # Sans les deux listes, on ne peut pas exclure une maîtrise interceptée.
            if champ not in fiche or interceptions not in fiche:
                avertissements.append({'code': 'maitrises_incompletes', 'extrait': phrase.strip()})
                continue
            attendues = {_entier(n) for n in fiche[champ]}
            attendues.update(_entier(n.get('maison')) for n in fiche[interceptions])
            attendues.discard(None)
            annoncees = {_entier(n) for n in re.findall(nombre, m['maisons'])}
            for maison in sorted(annoncees - attendues, key=lambda n: n or 0):
                if maison is not None:
                    erreurs.append({'code': 'maitrise_contradictoire', 'point': point,
                        'reference': suffixe, 'annonce': maison, 'attendu': sorted(attendues),
                        'fait': f'placements_rs.{point}.{champ}', 'extrait': phrase.strip()})
        for m in aspect.finditer(normalise):
            p1, p2 = AFFICHAGE_VERS_INTERNE[m['p1']], AFFICHAGE_VERS_INTERNE[m['p2']]
            r1, r2 = m['r1'] == 'rs', m['r2'] == 'rs'
            if not r1 and not r2:
                continue  # Les aspects natals ne sont pas dans ces deux listes.
            champ = 'aspects_internes_rs' if r1 and r2 else 'aspects_rs_natal'
            correspondances = []
            for fait in donnees.get(champ, []):
                if champ == 'aspects_internes_rs':
                    ok = {fait.get('planete1'), fait.get('planete2')} == {p1, p2}
                else:
                    prs, pnatal = (p1, p2) if r1 else (p2, p1)
                    ok = fait.get('point_rs') == prs and fait.get('point_natal') == pnatal
                if ok:
                    correspondances.append(_normaliser(fait.get('aspect', '')))
            if m['aspect'] not in correspondances:
                item = {'code': 'aspect_contradictoire' if correspondances else 'aspect_non_verifie',
                        'annonce': m['aspect'], 'attendu': sorted(set(correspondances)),
                        'fait': champ, 'extrait': phrase.strip()}
                # Une absence peut provenir d'un seuil d'orbe ou d'une exclusion
                # du relevé. Seul un aspect différent établi bloque la livraison.
                (erreurs if correspondances else avertissements).append(item)
    return erreurs, avertissements


def _controles_angles_figures(texte, donnees):
    """Contrôle conservateur : une absence du détecteur n'est pas une preuve."""
    erreurs, avertissements = [], []
    noms = '|'.join(re.escape(n) for n in sorted(AFFICHAGE_VERS_INTERNE, key=len, reverse=True))
    angles = r'ascendant|descendant|mc|fc'
    motif = re.compile(
        rf'\b(?P<point>{noms})\s+rs\s+(?:est\s+)?'
        r'(?:(?:en\s+)?conjonction(?:\s+(?P<exacte>exacte))?\s+(?:a|avec)|conjointe?\s+a|pile\s+sur)\s+'
        rf"(?:(?:ton|ta|le|la)\s+|l')?(?P<angle>{angles})\s+(?P<ref>rs|natal)\b")
    membres = rf'(?:{noms})(?:\s+rs)?'
    figure = re.compile(
        r"grand trigone(?:\s+rs)?\s+(?:d'|de\s+)(?P<element>eau|air|terre|feu)"
        r'\s+(?:entre|forme par|compose de)\s+'
        rf'(?P<membres>{membres}(?:(?:\s*,\s*|\s+et\s+){membres}){{2,}})')
    elements = {s:e for e,signes in {
        'feu':['belier','lion','sagittaire'], 'terre':['taureau','vierge','capricorne'],
        'air':['gemeaux','balance','verseau'], 'eau':['cancer','scorpion','poissons']}.items() for s in signes}
    for phrase in re.split(r'(?<=[.!?;])\s+|\n', texte):
        normalise = _normaliser(phrase.replace('*',''))
        if re.search(r'\b(si|pas|jamais|pourrait|serait|supposons|exemple|transit)\b|[«»"]',normalise):
            continue
        for m in motif.finditer(normalise):
            point, angle = AFFICHAGE_VERS_INTERNE[m['point']], AFFICHAGE_VERS_INTERNE[m['angle']]
            ref = m['ref']
            if ref == 'rs':
                contacts = [a for a in donnees.get('points_angulaires_rs',[]) if a.get('point') == point and a.get('angle') == angle]
                autres = [a for a in donnees.get('aspects_internes_rs',[]) if {a.get('planete1'),a.get('planete2')} == {point,angle}]
            else:
                autres = [a for a in donnees.get('aspects_rs_natal',[]) if a.get('point_rs') == point and a.get('point_natal') == angle]
                contacts = [a for a in autres if _normaliser(a.get('aspect','')) == 'conjonction']
            if contacts:
                # « Serrée » ou « pile » sont laissés au contrôle humain.
                if m['exacte'] and all(float(a.get('orbe',0)) > 1 for a in contacts):
                    erreurs.append({'code':'angularite_exacte_contradictoire','point':point,'angle':angle,'reference':ref,
                        'orbe_calcule':min(float(a['orbe']) for a in contacts),'extrait':phrase.strip()})
            elif autres and all(_normaliser(a.get('aspect','')) != 'conjonction' for a in autres):
                erreurs.append({'code':'conjonction_angle_contradictoire','point':point,'angle':angle,'reference':ref,
                    'attendu':[a['aspect'] for a in autres],'extrait':phrase.strip()})
            else:
                avertissements.append({'code':'angularite_non_verifiee','extrait':phrase.strip()})
        for m in figure.finditer(normalise):
            # Exige une référence RS dans la description, sans référence natale.
            if not re.search(r'\brs\b',m.group()) or re.search(r'\bnatal',normalise):
                continue
            points = [AFFICHAGE_VERS_INTERNE[x.group()] for x in re.finditer(rf'\b(?:{noms})\b',m['membres'])]
            for point in dict.fromkeys(points):
                signe = (donnees.get('placements_rs',{}).get(point) or {}).get('signe','')
                element = elements.get(_normaliser(signe))
                if element and element != m['element']:
                    erreurs.append({'code':'element_figure_contradictoire','point':point,'signe':signe,
                        'annonce':m['element'],'attendu':element,'extrait':phrase.strip()})
            calculees = [set(f.get('planetes',[])) for f in donnees.get('configurations_majeures_rs',[]) if f.get('type') == 'grand_trigone']
            if not any(set(points).issubset(f) for f in calculees):
                avertissements.append({'code':'composition_figure_non_verifiee','points':points,'extrait':phrase.strip()})
    return erreurs, avertissements


def _controles_composition_figures(texte, donnees):
    """Contrôle les rôles dans une figure identifiée par ses membres explicites.

    Une liste abrégée peut représenter des sommets composites. On conserve
    toutes les figures candidates ; aucune absence ne devient une erreur sûre.
    """
    erreurs, avertissements = [], []
    noms = '|'.join(re.escape(n) for n in sorted(AFFICHAGE_VERS_INTERNE, key=len, reverse=True))
    membre = rf'(?:{noms})(?:\s+rs)?'
    motif = re.compile(
        r'\b(?P<type>t[- ]carre|diamant|cerf[- ]volant)\s+rs\s+'
        r'(?:entre|forme par|compose de)\s+'
        rf'(?P<membres>{membre}(?:(?:\s*,\s*|\s+et\s+){membre}){{2,}})'
        rf'(?:\s*,?\s+avec\s+(?P<role>{noms})(?:\s+rs)?\s+'
        r'(?P<position>au sommet|a la pointe|comme planete focale))?')
    for phrase in re.split(r'(?<=[.!?;])\s+|\n', texte):
        normalise = _normaliser(phrase.replace('*',''))
        if re.search(r'\b(si|pas|jamais|pourrait|serait|supposons|exemple|natal\w*|transit)\b|[«»"]', normalise):
            continue
        for m in motif.finditer(normalise):
            nature = 't_carre' if m['type'].startswith('t') else 'diamant'
            points = {AFFICHAGE_VERS_INTERNE[p.group()] for p in re.finditer(rf'\b(?:{noms})\b',m['membres'])}
            candidats = [f for f in donnees.get('configurations_majeures_rs',[])
                if f.get('type') == nature and points.issubset(set(f.get('planetes',[])))]
            if not candidats:
                avertissements.append({'code':'composition_figure_non_verifiee','type':nature,
                    'points':sorted(points),'extrait':phrase.strip()})
                continue
            if not m['role']:
                continue
            # Un diamant a plusieurs sommets : « au sommet » n'identifie pas sa pointe.
            if nature == 'diamant' and m['position'] != 'a la pointe':
                continue
            point = AFFICHAGE_VERS_INTERNE[m['role']]
            roles = []
            for f in candidats:
                if nature == 'diamant':
                    role = f.get('pointe')
                else:
                    role = f.get('planetes_focales') or f.get('planete_focale')
                roles.append({role} if isinstance(role,str) else set(role or []))
            if any(not role for role in roles):
                avertissements.append({'code':'role_figure_non_verifie','extrait':phrase.strip()})
            elif not any(point in role for role in roles):
                erreurs.append({'code':'role_figure_contradictoire','type':nature,'annonce':point,
                    'attendu':sorted(set().union(*roles)),
                    'fait':'configurations_majeures_rs','extrait':phrase.strip()})
    return erreurs, avertissements
