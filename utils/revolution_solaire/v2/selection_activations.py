"""Contexte utile au calendrier : cibles et facteurs annuels, sans nouveau transit."""

from copy import deepcopy

from .filtrage_aspects import fait_autorise


def selectionner_activations(dossier, analyses):
    catalogue = dossier["faits"]
    retenus = {cle for cle in catalogue if cle.startswith("TRANSIT.")}
    retenus.add("PROFECTION.annuelle")
    cibles = set()
    for cle in retenus:
        if not cle.startswith("TRANSIT."):
            continue
        valeur = catalogue[cle]["valeur"]
        theme = valeur["reference"].upper()
        cibles.add((theme, valeur["cible"]))
        for axe in ("axe_noeuds", "axe_angles"):
            cibles.update((theme, nom) for nom in valeur.get(axe, {}))
        cibles.update((theme, contact["cible"]) for contact in valeur.get("contacts_complementaires_axe", []))
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    cibles.update({("NATAL", maitre), ("RS", maitre), ("RS", "Soleil"), ("RS", "Lune"),
                   ("RS", "Ascendant"), ("RS", "MC")})
    historique = {}
    champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet")
    for etape, precedente in analyses.items():
        enjeux = []
        for enjeu in precedente["enjeux"]:
            figures = [cle for cle in enjeu["preuves"] if catalogue[cle]["type"] == "configurations"]
            figure_active = any(any((catalogue[cle]["source"].upper(), nom) in cibles
                                    for nom in catalogue[cle]["valeur"].get("planetes", [])) for cle in figures)
            if enjeu["importance"] == "majeur" or figure_active:
                enjeux.append({champ: deepcopy(enjeu[champ]) for champ in champs})
        if enjeux:
            historique[etape] = {"enjeux": enjeux}
    # Cadre de la RS : uniquement les facteurs cités par ces enjeux.
    for etape, precedente in historique.items():
        for enjeu in precedente["enjeux"]:
            for cle in enjeu["preuves"]:
                fait = catalogue[cle]
                if cle.startswith("RS.") or etape == "profection":
                    if not cle.startswith("CONTACT.") and fait_autorise(fait):
                        retenus.add(cle)
                elif cle.startswith("NATAL.") and fait["type"] in {"aspects", "configurations", "maitrises", "angularites"}:
                    retenus.add(cle)
    retenus.update({"RS.maitrises.1", "RS.maitrises.10"})
    figures = [(catalogue[cle]["source"], set(catalogue[cle]["valeur"]["planetes"]))
               for cle in retenus if cle in catalogue and catalogue[cle]["type"] == "configurations"]
    for cle, fait in catalogue.items():
        if fait["type"] == "aspects" and fait_autorise(fait):
            membres = {fait["valeur"]["planete1"], fait["valeur"]["planete2"]}
            if any(fait["source"] == source and membres <= figure for source, figure in figures):
                retenus.add(cle)
    # Inclure la situation des participants, sans élargir à leurs autres aspects.
    for cle in list(retenus):
        fait = catalogue.get(cle)
        if fait is None or fait.get("source") not in {"natal", "rs"}:
            continue
        valeur, theme = fait["valeur"], fait["source"].upper()
        if fait["type"] == "aspects":
            cibles.update({(theme, valeur["planete1"]), (theme, valeur["planete2"])})
        elif fait["type"] == "configurations":
            cibles.update((theme, nom) for nom in valeur["planetes"])
        elif fait["type"] == "maitrises":
            cibles.update((theme, nom) for nom in valeur["maitres"])
    for theme, nom in cibles:
        retenus.update({f"{theme}.positions.{nom}", f"{theme}.angles.{nom}"})
    for theme in ("NATAL", "RS"):
        cle = f"{theme}.interceptions.ensemble"
        if cle in catalogue:
            signes = set(catalogue[cle]["valeur"].get("signes_interceptes", []))
            if any(k.startswith(f"{theme}.positions.") and catalogue[k]["valeur"]["signe"] in signes
                   for k in retenus if k in catalogue):
                retenus.add(cle)
    faits = {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}
    ids = {e["id"] for a in historique.values() for e in a["enjeux"]}
    for precedente in historique.values():
        for enjeu in precedente["enjeux"]:
            enjeu["preuves"] = [cle for cle in enjeu["preuves"] if cle in faits]
            enjeu["liens"] = [cle for cle in enjeu["liens"] if cle in ids]
    return faits, historique
