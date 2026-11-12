"""Faits essentiels destinés aux mails, sans calcul ni appel IA.

Même principe que la présentation épurée de la RS : positions, maîtrises,
aspects identifiés et structure des figures. Les dossiers techniques restent
locaux ; aucune copie de leurs métadonnées n'est transmise au rédacteur.
"""
import json
import unicodedata


VERSION_DOSSIER = "essentiels_v1"
LIMITE_PROMPT_CARACTERES = 36000
PERSONNELS = {"Soleil", "Lune", "Ascendant", "MC", "Vénus", "Mercure", "Mars"}


def _normaliser(texte):
    return unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().casefold()


def _position(position):
    position = position or {}
    resultat = {k: position[k] for k in ("signe", "maison", "maison_natale", "maison_rs", "maison_rl")
                if position.get(k) is not None}
    if position.get("retrograde") is True:
        resultat["retrograde"] = True
    return resultat


def _aspects(aspects, *, source, cible=None, acteur=None, limite=12, centres=None):
    """Déduplique et conserve les contacts principaux, sans distances de calcul."""
    retenus = {}
    centres = set(centres or PERSONNELS)
    for a in aspects or []:
        premier = acteur or a.get("planete1") or a.get("point_1") or a.get("planete_revolution") or a.get("point_rl") or a.get("point_rs")
        second = a.get("planete2") or a.get("point_2") or a.get("point_natal")
        if not second:
            second = (a.get("point_rs") or a.get("point_rl")) if acteur else (a.get("point_rs") if a.get("point_rl") else a.get("point_rl"))
        if not premier or not second or not a.get("aspect"):
            continue
        if source == (cible or source) and {premier, second} <= {"Ascendant", "Descendant", "MC", "FC"}:
            continue
        # Le quasi-retour d'une planète lente en RL, quelques jours après la RS,
        # ne doit pas occuper toute la sélection des réactivations personnelles.
        if source == "RL" and cible == "RS" and premier == second and premier in {"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"}:
            continue
        try:
            orbe = round(float(a.get("orbe", 99)), 2)
        except (ValueError, TypeError):
            continue
        paire = tuple(sorted((premier, second))) if source == (cible or source) else (premier, second)
        cle = (paire, _normaliser(a["aspect"]))
        fiche = {"de": f"{source}.{premier}", "aspect": a["aspect"],
                 "vers": f"{cible or source}.{second}", "orbe": orbe}
        conjonction_personnelle = (_normaliser(a["aspect"]) == "conjonction"
                                  and bool({premier, second} & {"Soleil", "Lune", "Ascendant"}))
        priorite = (0 if conjonction_personnelle else 1 if {premier, second} & centres else 2, orbe)
        if cle not in retenus or priorite < retenus[cle][0]:
            retenus[cle] = (priorite, fiche)
    return [fiche for _, fiche in sorted(retenus.values(), key=lambda v: v[0])[:limite]]


def _figures(figures, centres=None):
    """Structure seulement : aucun score, source imbriquée ou copie de positions."""
    resultat, vus = [], set()
    for f in figures or []:
        membres = f.get("planetes") or []
        if centres and not set(membres) & set(centres):
            continue
        if f.get("type") == "conjonction" and len(membres) < 3:
            continue  # Déjà présente dans les aspects.
        cle = (f.get("type"), tuple(sorted(membres)), str(f.get("planete_focale", "")))
        if cle in vus:
            continue
        vus.add(cle)
        fiche = {k: f[k] for k in (
            "type", "planetes", "planete_focale", "planetes_focales",
            "planetes_en_opposition", "sommets_grand_trigone",
        ) if f.get(k)}
        # Les deux oppositions suffisent à décrire un grand carré ; les sources
        # et les valeurs de chaque opération géométrique sont écartées.
        oppositions = _aspects(f.get("aspects_constitutifs", []), source="figure", limite=12)
        oppositions = [a for a in oppositions if _normaliser(a["aspect"]) == "opposition"]
        if oppositions and f.get("type") in {"grand_carre", "diamant"}:
            fiche["oppositions"] = oppositions
        resultat.append(fiche)
    return resultat


def _carte(positions, maisons, maitrises, aspects, figures, *, cadre, ascendant=None, maitres_ascendant=None):
    if isinstance(maitrises, list):
        # Conserver la distinction moderne/traditionnel au lieu de les fusionner.
        maitrises = {
            maison["maison"]: {
                "principal": maison["maitre_principal"],
                **({"complementaire": maison["maitre_traditionnel"]}
                   if maison.get("maitre_traditionnel") and maison["maitre_traditionnel"] != maison["maitre_principal"] else {}),
            }
            for maison in maitrises if maison.get("maison") and maison.get("maitre_principal")
        }
    resultat = {
        "positions": {nom: _position(p) for nom, p in (positions or {}).items()},
        "maitrises": maitrises or {},
        "aspects_principaux": _aspects(aspects, source=cadre, limite=24 if cadre == "natal" else 12),
        "figures": _figures(figures),
    }
    if cadre == "natal":
        groupes = {}
        for nom, position in (positions or {}).items():
            if nom in {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton", "Lune Noire"} and position.get("maison") is not None:
                groupes.setdefault(str(position["maison"]), []).append(nom)
        resultat["maisons_chargees"] = {m: noms for m, noms in groupes.items() if len(noms) >= 3}
    if maisons:
        resultat["signes_des_maisons"] = {nom: p["signe"] for nom, p in maisons.items() if p.get("signe")}
    if ascendant:
        resultat["ascendant"] = _position(ascendant)
    if maitres_ascendant:
        resultat["maitres_ascendant"] = maitres_ascendant
    return resultat


def _rs(rs):
    technique = rs.get("donnees_techniques") or {}
    positions = technique.get("placements_rs") or {}
    if not positions:
        positions = {nom: rs[nom.lower()] for nom in ("Soleil", "Lune") if rs.get(nom.lower())}
        positions.update({p["nom"]: p for p in rs.get("maitres_ascendant", []) if p.get("nom")})
        positions.update({p["planete"]: p["placement_rs"] for p in rs.get("planetes_contextuelles", []) if p.get("placement_rs")})
    maitrises = technique.get("maisons_gouvernees_rs") or {
        p["planete"]: p.get("maisons_gouvernees_rs", []) for p in rs.get("gouvernance", []) if p.get("planete")
    }
    resultat = _carte(
        positions, {}, maitrises, rs.get("aspects_directeurs"), rs.get("figures"), cadre="RS",
        ascendant=rs.get("ascendant"),
        maitres_ascendant=[p["nom"] for p in rs.get("maitres_ascendant", []) if p.get("nom")],
    )
    resultat["periode"] = rs.get("periode")
    resultat["maisons_chargees"] = [{"maison": m.get("maison"), "planetes": m.get("planetes", [])} for m in rs.get("maisons_chargees", [])]
    resultat["contacts_natal"] = _aspects(technique.get("aspects_rs_natal", []), source="RS", cible="natal", limite=8)
    return resultat


def _rl(rl):
    if rl.get("usage_editorial") == "date_a_annoncer_sans_interpretation_anticipee":
        return {"debut": rl.get("instant_local"), "usage": "annoncer_uniquement_la_date"}
    resultat = _carte(
        rl.get("positions"), rl.get("maisons"), rl.get("maitrises_des_maisons"),
        rl.get("aspects_internes_complets") or rl.get("aspects_internes"), rl.get("figures"),
        cadre="RL", ascendant=rl.get("ascendant"), maitres_ascendant=rl.get("maitre_ascendant"),
    )
    resultat.update({
        "debut": rl.get("instant_local"), "fin": rl.get("fin_utc"),
        "maisons_dominantes": [{"maison": m.get("maison"), "planetes": m.get("planetes", [])} for m in rl.get("maisons_occupees", [])],
        "angularites": [{k: a[k] for k in ("planete", "angle", "orbe") if k in a} for a in rl.get("planetes_angulaires", [])],
        "contacts_natal": _aspects(rl.get("contacts_natals_complets") or rl.get("contacts_natals"), source="RL", cible="natal", limite=10),
        "contacts_RS": _aspects((rl.get("reactivations_rs") or {}).get("contacts"), source="RL", cible="RS", limite=6),
    })
    return resultat


def _acteur_lunaison(fiche, nom, *, rappel=False, inclure_rl=True, limite_cycles=3):
    resultat = {"situation": _position(fiche.get("position"))}
    if fiche.get("retrograde") is True:
        resultat["situation"]["retrograde"] = True
    for cle in ("maison_natale", "maison_rs", "maison_rl"):
        if cle == "maison_rl" and not inclure_rl:
            continue
        if fiche.get(cle) is not None and (not rappel or cle == "maison_natale"):
            resultat[cle] = fiche[cle]
    for cible, champ in (("natal", "aspects_natal"), ("RS", "aspects_rs"), ("RL", "aspects_rl")):
        if cible == "RL" and not inclure_rl:
            continue
        if rappel and cible != "natal":
            continue
        contacts = _aspects(fiche.get(champ), source="lunaison", cible=cible, acteur=nom,
                            limite=3 if cible == "natal" else limite_cycles)
        if contacts:
            resultat["contacts_" + cible] = contacts
    return resultat


def _lunaison(lunaison, *, rappel=False):
    lecture = lunaison.get("lecture_personnalisee") or {}
    inclure_rl = lunaison.get("usage_rl") != "annoncer_uniquement_la_date"
    resultat = {"type": lunaison.get("type"), "date_locale": lunaison.get("instant_local"),
                "luminaires": {nom: _acteur_lunaison(fiche, nom, rappel=rappel, inclure_rl=inclure_rl) for nom, fiche in (lunaison.get("luminaires") or {}).items()}}
    if not rappel and lunaison.get("analyse_cecile"):
        analyse = lunaison["analyse_cecile"]
        resultat["analyse_validee_de_cecile"] = {
            cle: analyse[cle] for cle in ("id", "revision", "validee_le", "titre", "texte") if cle in analyse
        }
    if rappel:
        return resultat
    maitres, centres = [], {"Soleil", "Lune"}
    acteurs = {a["planete"]: a for a in lecture.get("acteurs_importants", [])}
    for pole in ("maitre_pole_lunaire", "maitre_pole_solaire"):
        branche = lecture.get(pole) or {}
        for convention in ("maitre_principal", "maitre_traditionnel"):
            maitre = branche.get(convention)
            if not maitre:
                continue
            nom = maitre.get("planete")
            centres.add(nom)
            ciel = maitre.get("au_moment_de_la_lunaison") or {}
            fiche = {"pole": "lunaire" if pole == "maitre_pole_lunaire" else "solaire",
                     "signe_gouverne": branche.get("signe"), "role": convention, "planete": nom,
                     **_acteur_lunaison(ciel, nom, inclure_rl=inclure_rl)}
            if nom in acteurs:
                fiche["roles_dans_lunaison"] = acteurs[nom]["roles"]
            if ciel.get("retrograde") is True:
                fiche["situation"]["retrograde"] = True
            fiche["aspects_ciel"] = _aspects(maitre.get("aspects_dans_le_ciel"), source="lunaison", limite=6, centres={nom})
            maitres.append(fiche)
    resultat["maitres"] = maitres
    complementaires = {}
    for nom, acteur in acteurs.items():
        if nom in centres:
            continue  # Les luminaires et les maîtres ont déjà leur fiche.
        complementaires[nom] = {
            "roles": acteur["roles"],
            **_acteur_lunaison(acteur["au_moment_de_la_lunaison"], nom,
                               inclure_rl=inclure_rl, limite_cycles=2),
            "aspects_ciel": _aspects(acteur.get("aspects_dans_le_ciel"), source="lunaison",
                                      limite=4, centres={nom}),
        }
    if complementaires:
        resultat["planetes_importantes"] = complementaires
    figures = lecture.get("configurations_dans_le_ciel") or []
    resultat["figures"] = _figures(figures, centres)
    resultat["autres_acteurs_des_figures"] = {
        nom: _position(position) for f in figures if set(f.get("planetes", [])) & centres
        for nom, position in (f.get("positions") or {}).items()
        if nom not in centres and nom not in complementaires
    }
    if lunaison.get("eclipse"):
        resultat["eclipse_globale"] = lunaison["eclipse"]
    return resultat


def dossier_essentiel(contrat, contexte_client):
    """Liste blanche unique utilisée pour TOUT envoi, y compris les anciens essais."""
    contexte = contexte_client or {}
    journal_autorise = contexte.get("journal_autorise") is True
    natal = contrat.get("theme_natal") or {}
    maitre = natal.get("maitre_ascendant") or {}
    resultat = {
        "format": VERSION_DOSSIER,
        "periode_mail": {k: v for k, v in (contrat.get("periode_mail") or {}).items() if k.endswith("local") or k.endswith("locale")},
        "anniversaire": contrat.get("profil_calendrier"),
        "natal": _carte(
            natal.get("planetes"), natal.get("maisons"), natal.get("house_rulers_map"),
            (natal.get("aspects") or []) + (natal.get("aspects_avec_angles") or []),
            natal.get("configurations_majeures"), cadre="natal", ascendant=natal.get("ascendant"),
            maitres_ascendant=[maitre[k] for k in ("nom", "second_nom") if maitre.get(k)],
        ),
        "cadres": [], "cartes_RS": {}, "cartes_RL": {},
        "lunaisons_a_venir": [_lunaison(l) for l in contrat.get("lunaisons_dans_la_periode", [])],
    }
    references_rs, references_rl = {}, {}
    for cadre in contrat.get("cadres_rs_rl", []):
        enjeux = cadre.get("enjeux_annuels") or {}
        photo = cadre.get("transits") or {}
        transits = [{k: t[k] for k in ("planete_transit", "planete_natale", "aspect", "orbe") if k in t}
                    for t in photo.get("faits", [])[:5]]
        rs = _rs(cadre.get("revolution_solaire") or {})
        rl = _rl(cadre.get("revolution_lunaire") or {})
        contacts_rl_rs = rl.pop("contacts_RS", [])
        cle_rs, cle_rl = serialiser_dossier(rs), serialiser_dossier(rl)
        if cle_rs not in references_rs:
            references_rs[cle_rs] = f"RS{len(references_rs) + 1}"
            resultat["cartes_RS"][references_rs[cle_rs]] = rs
        if cle_rl not in references_rl:
            references_rl[cle_rl] = f"RL{len(references_rl) + 1}"
            resultat["cartes_RL"][references_rl[cle_rl]] = rl
        resultat["cadres"].append({
            "du": cadre.get("valable_du_utc"), "au": cadre.get("valable_au_exclu_utc"),
            "RS": references_rs[cle_rs], "RL": references_rl[cle_rl],
            "contacts_RL_RS": contacts_rl_rs,
            "enjeux_annuels_retenus": [{"titre": e.get("titre"), "contenu": e.get("contenu")} for e in enjeux.get("enjeux", [])],
            "photo_transits": {"date": photo.get("date"), "contacts": transits},
        })
    precedente = contrat.get("rl_precedente_de_reference") or {}
    if precedente:
        theme = precedente.get("theme") or {}
        priorites = theme.get("priorites") or {}
        resultat["rappel_RL_precedente"] = {
            "du": precedente.get("debut_utc"), "au": precedente.get("fin_utc"),
            "ascendant": _position(priorites.get("ascendant")),
            "maitre_ascendant": priorites.get("maitre_ascendant"),
            "maisons_dominantes": [{"maison": m.get("maison"), "planetes": m.get("planetes", [])} for m in priorites.get("maisons_occupees", [])[:3]],
        }
    anciennes = contrat.get("lunaison_precedente_de_reference") or []
    if isinstance(anciennes, dict):
        anciennes = [anciennes]
    resultat["rappel_lunaison_precedente"] = [_lunaison(l, rappel=True) for l in anciennes[:1]]
    resultat["mails_precedents"] = [{"statut": m.get("statut"), "objet": m.get("objet"),
                                    "extrait": (m.get("texte_recent") or "")[:400],
                                    "question_journal": m.get("question_journal")}
                                   for m in (contrat.get("mails_precedents", [])[:2] if journal_autorise else [])]
    resultat["profil_declare"] = contexte.get("situation_actuelle") or {}
    resultat["statut_profil"] = contexte.get("statut_profil")
    resultat["journal_autorise"] = journal_autorise
    resultat["journal_30_jours"] = (contexte.get("journal_recent") or {}) if journal_autorise else {}
    return resultat


def verifier_budget_prompt(prompt):
    taille = len(prompt)
    if taille > LIMITE_PROMPT_CARACTERES:
        raise ValueError(
            f"Appel IA bloqué avant envoi : prompt de {taille:,} caractères, "
            f"plafond de {LIMITE_PROMPT_CARACTERES:,}. Réduire le dossier essentiel. Aucun appel effectué."
        )
    return {"caracteres_prompt": taille, "plafond_caracteres": LIMITE_PROMPT_CARACTERES,
            "format_dossier": VERSION_DOSSIER, "comptage_tokens": "non_effectue_avant_appel"}


def serialiser_dossier(dossier):
    return json.dumps(dossier, ensure_ascii=False, separators=(",", ":"), default=str)
