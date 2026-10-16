"""Sélection des faits déjà calculés pour l'appel consacré à la profection."""

from copy import deepcopy

from .filtrage_aspects import fait_autorise


def selectionner_profection(dossier, analyses):
    """Centre l'entrée sur le maître annuel, sans recalcul ni ajout par l'historique."""
    catalogue = dossier["faits"]
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    retenus = {"PROFECTION.annuelle"}
    ancres = {f"{theme}.positions.{maitre}" for theme in ("NATAL", "RS")}
    retenus.update(ancres)
    retenus.update({"RS.positions.Soleil", "RS.positions.Lune", "RS.angles.Ascendant",
                    "RS.angles.MC", "RS.cuspides.1", "RS.cuspides.10",
                    "RS.maitrises.1", "RS.maitrises.10"})
    figures = []
    for cle, fait in catalogue.items():
        valeur = fait["valeur"]
        if not fait_autorise(fait):
            continue
        pertinent = False
        if fait.get("source") in {"natal", "rs"}:
            if fait["type"] == "aspects":
                pertinent = maitre in {valeur["planete1"], valeur["planete2"]}
            elif fait["type"] == "angularites":
                pertinent = valeur.get("point") == maitre
            elif fait["type"] == "maitrises":
                pertinent = maitre in valeur.get("maitres", [])
                if pertinent:
                    retenus.add(f"{fait['source'].upper()}.cuspides.{fait['objet']}")
            elif fait["type"] == "configurations":
                pertinent = maitre in valeur.get("planetes", [])
                if pertinent:
                    figures.append((fait["source"], set(valeur["planetes"])))
        elif cle.startswith("CONTACT."):
            pertinent = maitre in {valeur.get("point_rs"), valeur.get("point_natal")}
        if pertinent:
            retenus.add(cle)
            ancres.add(cle)
    # Conserver les aspects constitutifs d'une figure retenue, sans en inventer.
    for cle, fait in catalogue.items():
        if fait["type"] == "aspects" and fait_autorise(fait):
            membres = {fait["valeur"]["planete1"], fait["valeur"]["planete2"]}
            if any(fait["source"] == source and membres <= figure for source, figure in figures):
                retenus.add(cle)
    # Maison occupée par le maître : cuspide et maîtrise calculées de ce secteur.
    for theme in ("NATAL", "RS"):
        maison = catalogue[f"{theme}.positions.{maitre}"]["valeur"]["maison"]
        retenus.update({f"{theme}.cuspides.{maison}", f"{theme}.maitrises.{maison}"})
    # Positions des participants aux facteurs retenus : une seule passe, sans
    # élargir ensuite à tous leurs propres aspects ou maîtrises.
    participants = set()
    for cle in list(retenus):
        fait = catalogue.get(cle)
        if fait is None:
            continue
        valeur, source = fait["valeur"], fait.get("source")
        if source in {"natal", "rs"}:
            noms = []
            if fait["type"] == "aspects":
                noms = [valeur["planete1"], valeur["planete2"]]
            elif fait["type"] == "maitrises":
                noms = valeur.get("maitres", [])
            elif fait["type"] == "configurations":
                noms = valeur.get("planetes", [])
            elif fait["type"] == "angularites":
                noms = [valeur["point"], valeur["angle"]]
            participants.update((source.upper(), nom) for nom in noms)
        elif cle.startswith("CONTACT."):
            participants.update({("RS", valeur["point_rs"]), ("NATAL", valeur["point_natal"])})
    for theme, nom in participants:
        retenus.update({f"{theme}.positions.{nom}", f"{theme}.angles.{nom}"})
    # Conserver l'état intercepté des seules positions effectivement transmises.
    for theme in ("NATAL", "RS"):
        cle = f"{theme}.interceptions.ensemble"
        if cle in catalogue:
            signes = set(catalogue[cle]["valeur"].get("signes_interceptes", []))
            if any(k.startswith(f"{theme}.positions.") and catalogue[k]["valeur"]["signe"] in signes
                   for k in retenus if k in catalogue):
                retenus.add(cle)
    faits = {cle: fait for cle, fait in catalogue.items() if cle in retenus and fait_autorise(fait)}
    historique = {}
    champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet")
    for etape, precedente in analyses.items():
        enjeux = []
        for enjeu in precedente.get("enjeux", []):
            if set(enjeu["preuves"]) & ancres:
                extrait = {champ: deepcopy(enjeu[champ]) for champ in champs}
                extrait["preuves"] = [cle for cle in extrait["preuves"] if cle in faits]
                enjeux.append(extrait)
        if enjeux:
            historique[etape] = {"enjeux": enjeux}
    ids = {e["id"] for a in historique.values() for e in a["enjeux"]}
    for precedente in historique.values():
        for enjeu in precedente["enjeux"]:
            enjeu["liens"] = [cle for cle in enjeu["liens"] if cle in ids]
    return faits, historique
