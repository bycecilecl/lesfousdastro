"""Repères archivés et affichage des périodes ; aucun calcul astrologique."""

from .bloc_1 import nettoyer_parasites
from ..releve_transits import transit_compact


MOIS = ("", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")


def date_lisible(jour):
    annee, mois, numero = jour.split("-")
    return f"{int(numero)} {MOIS[int(mois)]} {annee}"


def construire_reperes_calendrier(transits, cycle):
    """Copie les jours, phases et passages exacts des données sélectionnées.

    Les identifiants de jours permettent à l'IA de regrouper la lecture sans
    inventer ou recalculer de dates. La plage de lecture est distincte des
    fenêtres complètes d'activité des transits.
    """
    jours = {cycle["debut_utc"].split("T", 1)[0], cycle["fin_utc"].split("T", 1)[0]}
    passages = {}
    for ref, fait in transits.items():
        compact = transit_compact(fait["valeur"])
        jours.update(j for j in compact.get("periode", []) if j)
        jours.update(j for j in compact.get("periode_axe", []) if j)
        for phase in compact.get("phases", []):
            jours.update(j for j in phase["periode"] if j)
        if (compact.get("minimum") or {}).get("date"):
            jours.add(compact["minimum"]["date"])
        for station in compact.get("stations", []):
            jours.add(station["date"])
        for exact in compact.get("exacts") or []:
            j = exact if isinstance(exact, str) else exact["date"]
            sens = compact.get("sens") if isinstance(exact, str) else exact.get("sens")
            jours.add(j)
            identifiant = f"EXACT.{ref}.{len([p for p in passages.values() if p['transit_reference'] == ref]) + 1}"
            passages[identifiant] = {"date": j, "transit_reference": ref,
                                    "planete_mobile": compact["transit"], "cible": compact["cible"],
                                    "aspect": compact["aspect"], "sens": sens}
    debut, fin = cycle["debut_utc"][:10], cycle["fin_utc"][:10]
    return {"jours": {f"J{i + 1}": j for i, j in enumerate(sorted(j for j in jours if debut <= j <= fin))},
            "passages_exacts": passages,
            "nature": "Jours calculés ; les plages de lecture ne prétendent pas à une activité continue de tous les transits."}


def assembler_periodes_bloc_4(periodes, reperes):
    """Les titres datés et les repères exacts viennent du moteur, jamais d'une date libre."""
    parties, resolues, alertes, parasites = [], [], [], []
    if not isinstance(periodes, list):
        return "", [], ["Liste des périodes absente ou illisible."], []
    jours, passages = reperes["jours"], reperes["passages_exacts"]
    for numero, p in enumerate(periodes, 1):
        if not isinstance(p, dict):
            alertes.append(f"Période {numero} illisible.")
            continue
        a, b = p.get("repere_debut"), p.get("repere_fin")
        debut, fin = jours.get(a) if isinstance(a, str) else None, jours.get(b) if isinstance(b, str) else None
        valide = isinstance(debut, str) and isinstance(fin, str) and debut <= fin
        if not valide:
            alertes.append(f"Période {numero} : repères de dates absents, inconnus ou inversés.")
        titre = " ".join(p.get("titre", "Période à relire").splitlines()) if isinstance(p.get("titre"), str) else "Période à relire"
        texte = p.get("texte", "")
        if not isinstance(texte, str):
            texte = ""
        texte, retires = nettoyer_parasites(texte)
        parasites.extend(retires)
        dates = p.get("reperes_exacts", [])
        if not isinstance(dates, list):
            dates = []
        affichables = []
        for cle in dict.fromkeys(c for c in dates if isinstance(c, str)):
            exact = passages.get(cle)
            if exact is None:
                alertes.append(f"Période {numero} : passage exact inconnu {cle}.")
                continue
            refs = p.get("transits", [])
            if not isinstance(refs, list) or exact["transit_reference"] not in refs:
                alertes.append(f"Période {numero} : passage exact sans transit associé {cle}.")
                continue
            if not valide or not debut <= exact["date"] <= fin:
                alertes.append(f"Période {numero} : passage exact hors de la plage {cle}.")
                continue
            affichables.append(exact)
        affichables.sort(key=lambda e: (e["date"], e["transit_reference"]))
        resolues.append({"titre": titre, "debut": debut, "fin": fin, "dates_valides": valide,
                         "transits": p.get("transits", []), "reperes_exacts": affichables, "texte": texte})
    # Le texte de chaque période reste inchangé ; seul l'ordre de présentation
    # est chronologique. La réponse d'origine demeure dans reponse.json.
    debuts = [p["debut"] for p in resolues if p["dates_valides"]]
    if debuts != sorted(debuts):
        alertes.append("Périodes reçues hors ordre chronologique ; affichage remis dans l'ordre des dates calculées.")
    resolues.sort(key=lambda p: (not p["dates_valides"], p["debut"] or "", p["fin"] or ""))
    for p in resolues:
        plage = f"Du {date_lisible(p['debut'])} au {date_lisible(p['fin'])}" if p["dates_valides"] else "Dates à vérifier"
        partie = f"## {plage} — {p['titre']}\n\n{p['texte'].strip()}"
        if p["reperes_exacts"]:
            partie += "\n\n**Passages repères :**\n\n" + "\n".join(
                f"- {date_lisible(e['date'])} : {e['planete_mobile']} — {e['aspect']} à {e['cible']}"
                + (" (rétrograde)" if e.get("sens") in {"rétrograde", "retrograde"} else "")
                for e in p["reperes_exacts"])
        parties.append(partie)
    return "\n\n".join(parties), resolues, alertes, parasites
