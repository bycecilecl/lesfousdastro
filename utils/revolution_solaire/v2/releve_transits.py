"""Calendrier au jour en UTC ; les données précises restent dans les archives."""

from copy import deepcopy


def _jour(date):
    return date.split("T", 1)[0] if date is not None else None


def _cible(nom, reference):
    if reference == "rs":
        return nom + " RS"
    return nom + (" natale" if nom in {"Lune", "Vénus", "Lune Noire", "Part de Fortune"} else " natal")


def _dates_compactes(datation):
    debut = datation.get("entree_utc", datation.get("debut"))
    fin = datation.get("sortie_utc", datation.get("fin"))
    resultat = {"periode": [_jour(debut), _jour(fin)]}
    phases = datation.get("phases", [])
    passages = deepcopy(datation.get("passages_exacts", []))
    connus = {(p["date_utc"], p.get("sens")) for p in passages}
    # Une date figurant uniquement dans une phase reste également disponible.
    for phase in phases:
        for date in phase.get("passages_exacts", []):
            cle = (date, phase["sens"])
            if cle not in connus:
                passages.append({"date_utc": date, "sens": phase["sens"]})
                connus.add(cle)
    passages.sort(key=lambda p: p["date_utc"])
    phase_unique = (len(phases) == 1 and phases[0]["debut_utc"] == debut and phases[0]["fin_utc"] == fin)
    if phase_unique:
        resultat["sens"] = phases[0]["sens"]
    elif phases:
        resultat["phases"] = [{"periode": [_jour(p["debut_utc"]), _jour(p["fin_utc"])], "sens": p["sens"]}
                              for p in phases]
    if phase_unique and all(p.get("sens") == phases[0]["sens"] for p in passages):
        resultat["exacts"] = [_jour(p["date_utc"]) for p in passages]
    else:
        resultat["exacts"] = [{"date": _jour(p["date_utc"]),
                               **({"sens": p["sens"]} if "sens" in p else {})} for p in passages]
    if not passages:
        resultat["minimum"] = {"date": _jour(datation.get("plus_serre_utc", datation.get("plus_serre"))),
                               "orbe_deg": datation.get("orbe_minimum")}
        if datation.get("exact") is True:
            resultat["exacts"] = None
            resultat["precision"] = "Passage exact signalé, mais sa date manque dans cette archive."
    for nom in ("entree", "sortie"):
        if datation.get(nom + "_coupee_par_cycle"):
            resultat[nom + "_coupee"] = True
    # Un changement déjà représenté dans les phases n'est pas répété en station.
    transitions = {(p["debut_utc"], p["sens"]) for p in phases[1:]} if not phase_unique else set()
    stations = [{"date": _jour(s["date_utc"]), "sens_apres": s["sens_apres"]}
                for s in datation.get("stations", []) if (s["date_utc"], s["sens_apres"]) not in transitions]
    if stations:
        resultat["stations"] = stations
    return resultat


def transit_compact(evenement):
    resultat = {"transit": evenement["planete_transit"],
                "cible": _cible(evenement["cible"], evenement["reference"]), "aspect": evenement["aspect"]}
    datation = evenement.get("datation")
    if datation:
        resultat.update(_dates_compactes(datation))
    else:
        resultat.update({"periode": [_jour(evenement.get("debut")), _jour(evenement.get("fin"))],
                         "exacts": None,
                         "minimum": {"date": _jour(evenement.get("date_plus_serree")),
                                     "orbe_deg": evenement.get("orbe_plus_serre")}})
        resultat["precision"] = "Fenêtre de détection ; datation affinée absente."
    for cle in ("axe_noeuds", "axe_angles"):
        if cle in evenement:
            resultat[cle] = deepcopy(evenement[cle])
    if "fenetre_axe" in evenement:
        axe = evenement["fenetre_axe"]
        resultat["periode_axe"] = [_jour(axe["debut_utc"]), _jour(axe["fin_utc"])]
    if evenement.get("contacts_complementaires_axe"):
        complementaires = []
        for contact in evenement["contacts_complementaires_axe"]:
            compact = {"cible": _cible(contact["cible"], evenement["reference"]),
                       "aspect": contact["aspect"], **_dates_compactes(contact)}
            communs = [cle for cle, valeur in compact.items()
                       if cle not in {"cible", "aspect"} and cle in resultat and resultat[cle] == valeur]
            if communs:
                for cle in communs:
                    del compact[cle]
                compact["identiques_au_contact_principal"] = communs
            complementaires.append(compact)
        resultat["complements"] = complementaires
    return resultat
