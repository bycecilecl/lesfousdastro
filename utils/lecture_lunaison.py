"""Dossier personnalisé d'une lunaison : ciel, maître et structure natale.

Ce module organise des données calculées ; il ne génère aucune interprétation.
"""
from utils.calculs_astrologiques import MAITRES_SIGNES, SECONDS_MAITRES_SIGNES, ORBES_DEFAUT, detecter_aspects
from utils.configurations_astrologiques import (
    analyser_configurations_majeures, ORBE_OPPOSITION_T_CARRE, ORBE_CARRE_T_CARRE,
)


CHAMPS_NATAL_MAIL = (
    "planetes", "maisons", "angles_deg", "aspects", "aspects_avec_angles",
    "ascendant", "maitre_ascendant", "house_rulers_map", "configurations_majeures",
)
VERSION_CONTACTS_IMPORTANTS = 1
MAX_PLANETES_COMPLEMENTAIRES = 4
ORBE_CONTACT_LUMINAIRE_IMPORTANT = 3


def natal_pour_mail(theme_natal):
    """Conserve le natal tropical et ses structures utiles, sans mélanger le sidéral."""
    return {cle: theme_natal[cle] for cle in CHAMPS_NATAL_MAIL if cle in theme_natal}


def maitrises_des_maisons(maisons):
    """Associe les cuspides fournies à leurs maîtres, sans nouveau calcul de carte."""
    resultat = []
    for nom, maison in (maisons or {}).items():
        signe = maison.get("signe")
        principal = MAITRES_SIGNES.get(signe)
        if principal is None:
            continue
        traditionnel = SECONDS_MAITRES_SIGNES.get(signe, principal)
        resultat.append({
            "maison": nom, "signe_cuspide": signe,
            "maitre_principal": principal,
            "maitre_traditionnel": traditionnel if traditionnel != principal else None,
        })
    return resultat


def _membres(aspect):
    return {aspect.get("planete1"), aspect.get("planete2"), aspect.get("point_1"), aspect.get("point_2")}


def _fiche_natale(nom, natal):
    natal = natal or {}
    position = (natal.get("planetes") or {}).get(nom)
    if position is None and nom in (natal.get("angles_deg") or {}):
        position = {"longitude": natal["angles_deg"][nom]}
    aspects = []
    deja_vus = set()
    for aspect in (natal.get("aspects") or []) + (natal.get("aspects_avec_angles") or []):
        if nom not in _membres(aspect):
            continue
        identite = (aspect.get("planete1"), aspect.get("planete2"), aspect.get("aspect"))
        if identite not in deja_vus:
            aspects.append(aspect)
            deja_vus.add(identite)
    return {
        "point": nom, "position_natale": position,
        "maisons_gouvernees": (natal.get("house_rulers_map") or {}).get(nom, []),
        "aspects_natals": aspects,
        "configurations_natales": [c for c in (natal.get("configurations_majeures") or []) if nom in (c.get("planetes") or [])],
    }


def _acteurs_importants(fiches_ciel, aspects_ciel, figures_ciel, maitres):
    """Maîtres, focales et proches des luminaires ; pas tout le ciel en entrée IA."""
    noms_maitres = {
        fiche["planete"] for branche in maitres if branche
        for convention in ("maitre_principal", "maitre_traditionnel")
        if (fiche := branche.get(convention))
    }
    centres = {"Soleil", "Lune"} | noms_maitres
    roles, priorites, orbes = {}, {}, {}

    def retenir(nom, role, priorite, orbe=99):
        if nom not in fiches_ciel or nom in {"Soleil", "Lune"}:
            return
        roles.setdefault(nom, set()).add(role)
        priorites[nom] = min(priorites.get(nom, 99), priorite)
        orbes[nom] = min(orbes.get(nom, 99), float(orbe))

    for nom in noms_maitres:
        retenir(nom, "maitre_lunaison", 0)
    for aspect in aspects_ciel:
        membres = _membres(aspect)
        for luminaire in {"Soleil", "Lune"} & membres:
            orbe = float(aspect.get("orbe", 99))
            if orbe > ORBE_CONTACT_LUMINAIRE_IMPORTANT:
                continue
            conjonction = str(aspect.get("aspect", "")).casefold() == "conjonction"
            for nom in membres - {luminaire}:
                retenir(nom, ("conjointe_" if conjonction else "contact_serre_") + luminaire,
                        2 if conjonction else 3, orbe)
    for figure in figures_ciel:
        membres = set(figure.get("planetes") or [])
        if not membres & centres:
            continue
        focales = set(figure.get("planetes_focales") or [])
        if figure.get("planete_focale"):
            focales.add(figure["planete_focale"])
        for nom in focales:
            retenir(nom, "planete_focale", 1)
        for nom in membres:
            retenir(nom, "figure_liee_aux_luminaires_ou_maitres", 4)
    complementaires = sorted(
        roles.keys() - noms_maitres,
        key=lambda nom: (priorites[nom], orbes[nom], nom),
    )[:MAX_PLANETES_COMPLEMENTAIRES]
    selection = sorted((noms_maitres & roles.keys()) | set(complementaires),
                       key=lambda nom: (priorites[nom], orbes[nom], nom))
    return [{"planete": nom, "roles": sorted(roles[nom]),
             "au_moment_de_la_lunaison": fiches_ciel[nom],
             "aspects_dans_le_ciel": [a for a in aspects_ciel
                                      if nom in _membres(a) and (_membres(a) - {nom}) & centres]}
            for nom in selection]


def dossier_lecture_lunaison(luminaires, positions_ciel, fiches_ciel, natal):
    aspects_ciel = detecter_aspects({nom: position["longitude"] for nom, position in positions_ciel.items()})
    figures_ciel = analyser_configurations_majeures(aspects_ciel, positions_ciel)
    signe_lune = luminaires["Lune"]["position"]["signe"]
    signe_soleil = luminaires["Soleil"]["position"]["signe"]

    def maitre_signe(signe):
        principal = MAITRES_SIGNES[signe]
        traditionnel = SECONDS_MAITRES_SIGNES.get(signe, principal)

        def fiche(nom):
            figures = [c for c in figures_ciel if nom in (c.get("planetes") or [])]
            return {
                "planete": nom, "au_moment_de_la_lunaison": fiches_ciel[nom],
                "aspects_dans_le_ciel": [a for a in aspects_ciel if nom in _membres(a)],
                "configurations_dans_le_ciel": figures,
                "apex_t_carres": [c for c in figures if c.get("type") == "t_carre"
                                  and (c.get("planete_focale") == nom or nom in (c.get("planetes_focales") or []))],
                "dans_le_natal": _fiche_natale(nom, natal),
            }

        return {"signe": signe, "convention_principale": "maîtrises modernes du projet",
                "maitre_principal": fiche(principal),
                "maitre_traditionnel": fiche(traditionnel) if traditionnel != principal else None}

    maitre_lune = maitre_signe(signe_lune)
    maitre_soleil = maitre_signe(signe_soleil) if signe_soleil != signe_lune else None
    acteurs = _acteurs_importants(fiches_ciel, aspects_ciel, figures_ciel,
                                 (maitre_lune, maitre_soleil))
    points_touches = sorted({a["point_natal"] for luminaire in luminaires.values()
                             for a in luminaire["aspects_natal"]})
    return {
        "version_contacts_importants": VERSION_CONTACTS_IMPORTANTS,
        "configurations_dans_le_ciel": figures_ciel,
        "maitre_pole_lunaire": maitre_lune,
        "maitre_pole_solaire": maitre_soleil,
        "acteurs_importants": acteurs,
        "structure_natale_des_points_touches": [_fiche_natale(nom, natal) for nom in points_touches],
        "orbes_aspects_du_ciel": ORBES_DEFAUT,
        "orbes_t_carre": {"opposition_max": ORBE_OPPOSITION_T_CARRE, "carres_max": ORBE_CARRE_T_CARRE},
    }
