"""Corrections déterministes et conservatrices avant livraison d'une RS.

Une affirmation calculablement fausse est remplacée uniquement par un fait
vérifié. On ne demande pas au modèle de réécrire tout le rapport payant.
"""
from __future__ import annotations

import re

from .verification_rapport import _controle_contacts_rs_natal

ALERTE_CONJONCTION = re.compile(
    r'^Conjonction RS–natal absente du calcul \((?P<planete>.+?) RS / '
    r'(?P<angle>Ascendant|Descendant|MC|FC) natal\) : « (?P<phrase>.+) »$'
)
PLANETES = r'Soleil|Lune|Mercure|Vénus|Mars|Jupiter|Saturne|Uranus|Neptune|Pluton'
MAISONS_ROMAINES = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
                   'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12}


def _maison(numero):
    return int(numero) if numero.isdigit() else MAISONS_ROMAINES.get(numero.upper())


def _corrections_maitrises_angles(texte: str, donnees: dict, corrections: list[dict]) -> str:
    placements = donnees.get('placements_rs') or {}
    angles = donnees.get('points_angulaires_rs') or []
    au_mc = re.compile(rf'\b(?P<point>{PLANETES})\s+au\s+MC\b(?!\s+natal)', re.IGNORECASE)

    def remplacer_au_mc(match):
        point = match['point']
        fiche = placements.get(point) or {}
        if any(a.get('point') == point and a.get('angle') == 'MC' for a in angles):
            return match.group(0)
        if 10 in (fiche.get('maisons_gouvernees_rs') or []):
            apres = f'{point} maître du MC RS'
        elif fiche.get('maison') is not None:
            apres = f"{point} en maison {fiche['maison']} RS"
        else:
            return match.group(0)
        corrections.append({'code': 'au_mc_sans_conjonction',
                            'avant': match.group(0), 'apres': apres})
        return apres

    texte = au_mc.sub(remplacer_au_mc, texte)

    occupe_mc = re.compile(
        rf'\b(?P<point>{PLANETES})\s+au sommet,\s+rétrograde,\s+occupe le MC\b'
    )

    def remplacer_occupe_mc(match):
        point = match['point']
        if any(a.get('point') == point and a.get('angle') == 'MC' for a in angles):
            return match.group(0)
        maison = (placements.get(point) or {}).get('maison')
        if maison is None:
            return match.group(0)
        apres = match.group(0).replace('occupe le MC', f'occupe la maison {maison} RS')
        corrections.append({'code': 'occupe_mc_sans_conjonction',
                            'avant': match.group(0), 'apres': apres})
        return apres

    texte = occupe_mc.sub(remplacer_occupe_mc, texte)

    deux_maitres = re.compile(
        rf'(?P<prefix>(?P<p1>{PLANETES})\b[^,\n.]{{0,100}}?\bet\s+'
        rf'(?P<p2>{PLANETES})\b[^,\n.]{{0,100}}?),\s*'
        r'tous deux gouverneurs de ta maison (?P<maison>[IVXivx\d]+),',
        re.IGNORECASE,
    )

    def remplacer_deux_maitres(match):
        maison = _maison(match['maison'])
        if maison is None or all(maison in ((placements.get(match[n]) or {}).get('maisons_gouvernees_rs') or [])
                                 for n in ('p1', 'p2')):
            return match.group(0)
        apres = match['prefix']
        corrections.append({'code': 'maitrise_collective_fausse',
                            'avant': match.group(0), 'apres': apres})
        return apres

    return deux_maitres.sub(remplacer_deux_maitres, texte)


def _corriger_carre_natal_attribue_a_rs(texte: str, donnees: dict, corrections: list[dict]) -> str:
    motif = re.compile(
        rf'(?P<point>{PLANETES}) natal se trouve[^.\n]{{0,120}}\.\s+'
        rf'(?P<erreur>Il reçoit cette année un carré de (?P<cible>{PLANETES}) natal, '
        rf'réactivé par (?P<rs>{PLANETES}) RS\.)'
    )
    natals = donnees.get('placements_natals_verifies') or {}
    contacts = donnees.get('aspects_rs_natal') or []

    def remplacer(match):
        point, cible, rs = match['point'], match['cible'], match['rs']
        if point != rs:
            return match.group(0)
        longitude1 = (natals.get(point) or {}).get('degre')
        longitude2 = (natals.get(cible) or {}).get('degre')
        if longitude1 is None or longitude2 is None:
            return match.group(0)
        distance = abs(float(longitude1) - float(longitude2)) % 360
        orbe_carre_natal = abs(min(distance, 360 - distance) - 90)
        if orbe_carre_natal <= 6:
            return match.group(0)
        fait = next((a for a in contacts if a.get('point_rs') == rs
                     and a.get('point_natal') == cible and a.get('aspect') == 'carré'), None)
        if fait is None:
            return match.group(0)
        apres = f"{rs} RS forme cette année un carré à {cible} natal ({float(fait['orbe']):.2f}°)."
        corrections.append({'code': 'carre_natal_attribue_a_rs',
                            'avant': match['erreur'], 'apres': apres})
        return match.group(0).replace(match['erreur'], apres)

    return motif.sub(remplacer, texte)


def corriger_contacts_et_roles(texte: str, donnees: dict) -> tuple[str, list[dict]]:
    """Corrige les inversions vérifiées et retire les assertions non calculées.

    Si l'angle RS touche réellement la planète natale, on remplace la phrase
    fautive par ce contact dans le bon sens. Sinon, on retire cette phrase.
    La formulation originale n'est jamais conservée comme fait astrologique.
    """
    corrections: list[dict] = []
    texte = _corrections_maitrises_angles(texte, donnees, corrections)
    texte = _corriger_carre_natal_attribue_a_rs(texte, donnees, corrections)
    profection = donnees.get('profection_annuelle') or {}
    maison_rs = (profection.get('ascendant_profecte') or {}).get('maison_rs')
    if maison_rs:
        # La maison fournie par ce calcul est celle de l'Ascendant profecté
        # dans la RS. Le modèle peut la présenter à tort comme natale.
        motif_profection = re.compile(
            r'(\bprofection annuelle\s+arrive\s+en\s+maison\s+)'
            r'(?P<maison>[IVXivx\d]+)(?P<qualificatif>\s+natale\b)',
            re.IGNORECASE,
        )
        def corriger_profection(match):
            avant = match.group(0)
            apres = f"{match.group(1)}{maison_rs} de RS"
            corrections.append({'code': 'maison_profection_rs_corrigee',
                                'avant': avant, 'apres': apres})
            return apres
        texte = motif_profection.sub(corriger_profection, texte)

    aspects = donnees.get('aspects_rs_natal') or []
    for alerte in _controle_contacts_rs_natal(texte, donnees):
        match = ALERTE_CONJONCTION.match(alerte)
        if not match:
            continue
        phrase = match['phrase']
        if phrase not in texte:
            continue
        planete, angle = match['planete'], match['angle']
        inverse = next((a for a in aspects
            if a.get('point_rs') == angle and a.get('point_natal') == planete
            and a.get('aspect') == 'conjonction'), None)
        if inverse is not None:
            formulation_fausse = f"en conjonction avec le {angle} natal"
            if formulation_fausse in phrase:
                replacement = phrase.replace(
                    formulation_fausse,
                    f"le {angle} RS est conjoint à {planete} natale",
                    1,
                )
            else:
                replacement = f"Le {angle} RS est conjoint à {planete} natale ({float(inverse['orbe']):.2f}°)."
            nature = 'contact_inverse_corrige'
        else:
            replacement = ''
            nature = 'contact_non_calcule_retire'
        texte = texte.replace(phrase, replacement, 1)
        corrections.append({'code': nature, 'planete': planete, 'angle': angle,
                            'avant': phrase, 'apres': replacement})

    for figure in donnees.get('configurations_majeures_rs') or []:
        if figure.get('type') != 't_carre':
            continue
        focale = figure.get('planete_focale')
        base = figure.get('planetes_en_opposition') or []
        if not focale or len(base) != 2:
            continue
        # Ne touche qu'à une formulation explicitement incompatible avec la
        # figure calculée : l'apex est carré aux deux extrémités de la base.
        motif = re.compile(
            rf'(T-carré[^\n.]{{0,100}}?\b{re.escape(focale)}\s+apex[^\n.]{{0,100}}?,\s*)'
            rf'(?P<erreur>opposée?\s+{re.escape(base[0])}[–-]{re.escape(base[1])})',
            re.IGNORECASE,
        )
        match = motif.search(texte)
        if match:
            replacement = f"carrée à {base[0]} et à {base[1]}"
            texte = texte[:match.start('erreur')] + replacement + texte[match.end('erreur'):]
            corrections.append({'code': 'role_t_carre_corrige',
                                'avant': match['erreur'], 'apres': replacement})
    return texte, corrections
