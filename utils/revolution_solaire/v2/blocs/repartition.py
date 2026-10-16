"""Propriété des développements ; les rappels gardent leurs faits de référence."""


def repartir_pour_bloc(faits, numero_bloc, proprietaires_precedents=None, *, faits_a_developper):
    """Sépare les faits disponibles et les références affectées à un autre bloc.

    Seules les clés explicitement prévues pour un développement sont affectées
    au bloc courant. Les autres faits disponibles restent du contexte sans propriétaire.
    Les blocs suivants doivent charger la propriété et la mémoire de la version
    choisie par Cécile. Cette fonction ne génère ni ne valide aucun texte.
    """
    proprietaires = dict(proprietaires_precedents or {})
    a_developper = set(faits_a_developper)
    nouveaux, deja_traites = {}, {}
    for cle, fait in faits.items():
        precedent = proprietaires.get(cle)
        if precedent is not None and precedent != numero_bloc:
            deja_traites[cle] = {"bloc_proprietaire": precedent, "fait": fait}
        else:
            nouveaux[cle] = fait
            if cle in a_developper:
                proprietaires[cle] = numero_bloc
    return nouveaux, deja_traites, proprietaires


def repartir_sections_bloc_1(faits, dossier, *, reserves=()):
    """Affecte les seuls faits à développer ; le contexte n'entre pas dans les listes."""
    reserves = set(reserves)
    ordre = ("ascendant", "maitres_ascendant", "profection")
    acteurs = ({"Ascendant"}, set(dossier["rs"]["maitrises"]["1"]["maitres"]),
               {dossier["profection"]["maitre_annee"]["nom"]})

    def rang(noms):
        # Des rôles distincts remplacent le dictionnaire nom -> dernier rang.
        return next((i for i, ensemble in enumerate(acteurs) if ensemble & noms), None)

    parts = {nom: [] for nom in ordre}
    maitre_annee = dossier["profection"]["maitre_annee"]["nom"]
    for cle, fait in faits.items():
        v, categorie, source = fait["valeur"], fait["type"], fait["source"]
        # Réserver la lecture RS de ces positions n'enlève pas la situation
        # natale du maître de l'année à la profection.
        if source == "rs" and categorie in {"positions", "angles"} and fait["objet"] in reserves:
            continue
        section, noms = None, set()
        if cle == "PROFECTION.annuelle":
            section = 2
        elif cle.startswith("CONTACT."):
            noms = {v["point_rs"]}
            section = rang(noms)  # point_natal n'est jamais traité comme un acteur RS.
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points."):
            section = rang({fait["objet"]})
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.cuspides.") and str(fait["objet"]) == "1":
            section = 0
        elif cle == "RS.interceptions.ensemble":
            interceptes = set(v.get("signes_interceptes", []))
            if any(dossier["rs"]["positions"][maitre]["signe"] in interceptes
                   for maitre in dossier["rs"]["maitrises"]["1"]["maitres"]):
                section = 1
        elif source == "rs":
            if categorie == "aspects":
                noms = {v["planete1"], v["planete2"]}
            elif categorie == "angularites":
                noms = {v["point"], v["angle"]}
            elif categorie == "configurations":
                noms = set(v["planetes"])
            elif categorie in {"positions", "angles"}:
                noms = {fait["objet"]}
            elif categorie in {"cuspides", "maitrises"} and str(fait["objet"]) == "1":
                section = 0
            if section is None:
                section = rang(noms)
        elif source == "natal":
            # Le maître natal de l'année appartient à la profection ; les autres
            # cibles natales, leurs positions et maisons restent des références.
            if categorie in {"positions", "angles"} and fait["objet"] == maitre_annee:
                section = 2
            elif categorie == "aspects" and maitre_annee in {v["planete1"], v["planete2"]}:
                section = 2
            elif categorie == "angularites" and v["point"] == maitre_annee:
                section = 2
            elif categorie == "configurations" and maitre_annee in v["planetes"]:
                section = 2
        # Aucun repli automatique : positions des partenaires, cuspides,
        # maîtrises de leurs maisons restent du contexte. L'interception est
        # affectée aux maîtres seulement lorsqu'elle les concerne.
        if section is not None:
            parts[ordre[section]].append(cle)
    return parts


def repartir_sections_bloc_2(faits, dossier):
    """Soleil puis Lune ; leurs partenaires natals/RS restent du contexte."""
    ordre = ("soleil", "lune")
    luminaires = ("Soleil", "Lune")
    maisons = {nom: str(dossier["rs"]["positions"][nom]["maison"]) for nom in luminaires}
    parts = {section: [] for section in ordre}
    for cle, fait in faits.items():
        v, categorie, source = fait["valeur"], fait["type"], fait["source"]
        noms = set()
        if categorie == "contact":
            noms = {v["point_rs"]}
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points."):
            noms = {fait["objet"]}
        elif source == "rs":
            if categorie in {"positions", "angles"}:
                noms = {fait["objet"]}
            elif categorie == "aspects":
                noms = {v["planete1"], v["planete2"]}
            elif categorie == "angularites":
                noms = {v["point"]}
            elif categorie == "configurations":
                noms = set(v["planetes"])
            elif categorie in {"cuspides", "maitrises"}:
                noms = {nom for nom in luminaires if maisons[nom] == str(fait["objet"])}
            elif categorie == "interceptions":
                signes = set(v.get("signes_interceptes", []))
                noms = {nom for nom in luminaires if dossier["rs"]["positions"][nom]["signe"] in signes}
        section = next((ordre[i] for i, nom in enumerate(luminaires) if nom in noms), None)
        if section is not None:
            parts[section].append(cle)
    return parts


def repartir_sections_bloc_3(faits, dossier):
    """MC, maîtres du MC puis compléments ; références natales en contexte."""
    parts = {nom: [] for nom in ("mc", "maitres_mc", "complements")}
    maitres_mc = set(dossier["rs"]["maitrises"]["10"]["maitres"])
    maitres_asc = set(dossier["rs"]["maitrises"]["1"]["maitres"])
    maisons_luminaires = {str(dossier["rs"]["positions"][nom]["maison"]) for nom in ("Soleil", "Lune")}
    maisons_maitres = {str(dossier["rs"]["positions"][nom]["maison"]) for nom in maitres_mc}
    for cle, fait in faits.items():
        v, categorie, source = fait["valeur"], fait["type"], fait["source"]
        noms, section = set(), None
        if categorie == "contact":
            noms = {v["point_rs"]}
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.points."):
            noms = {fait["objet"]}
        elif cle.startswith("SUPERPOSITION.rs_vers_natal.cuspides."):
            maison = str(fait["objet"])
            if maison == "10":
                section = "mc"
            elif maison not in maisons_luminaires | {"1"}:
                section = "maitres_mc" if maison in maisons_maitres else "complements"
        elif source == "rs":
            if categorie == "positions":
                # Les portraits des luminaires et des maîtres d'Ascendant ont
                # déjà leur bloc ; leur position peut situer un nouveau lien.
                if fait["objet"] in ({"Soleil", "Lune"} | maitres_asc) - maitres_mc:
                    continue
                noms = {fait["objet"]}
            elif categorie == "angles" and fait["objet"] == "MC":
                noms = {"MC"}
            elif categorie == "aspects":
                noms = {v["planete1"], v["planete2"]}
            elif categorie == "angularites":
                noms = {v["point"], v["angle"]}
            elif categorie == "configurations":
                noms = set(v["planetes"])
            elif categorie == "interceptions":
                section = "complements"
            elif categorie in {"cuspides", "maitrises"}:
                maison = str(fait["objet"])
                if maison == "10":
                    section = "mc"
                elif maison not in maisons_luminaires | {"1"}:
                    section = "maitres_mc" if maison in maisons_maitres else "complements"
        if section is None and noms:
            section = "mc" if noms & {"MC", "FC"} else "maitres_mc" if noms & maitres_mc else "complements"
        if section is not None:
            parts[section].append(cle)
    return parts
