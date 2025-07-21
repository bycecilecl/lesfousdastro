def formater_positions_planetes(planetes):
    lignes = []
    for planete, infos in planetes.items():
        signe = infos.get("signe", "inconnu")
        degre = round(infos.get("degre_dans_signe", 0.0), 2)
        maison = infos.get("maison", "N/A")
        lignes.append(f"{planete} : {signe} {degre}° — Maison {maison}")
    return "\n".join(lignes)


def formater_aspects(aspects):
    lignes = []
    for aspect in aspects:
        p1 = aspect["planete1"]
        p2 = aspect["planete2"]
        nom_aspect = aspect["aspect"]
        orbe = round(aspect["orbe"], 2)
        lignes.append(f"{p1} {nom_aspect} {p2} (orbe : {orbe}°)")
    return "\n".join(lignes)