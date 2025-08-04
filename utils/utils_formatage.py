
def formater_positions_planetes(planetes):
    lignes = []
    for nom, infos in planetes.items():
        signe = infos.get('signe', 'inconnu')
        degre = infos.get('degre', 'n/a')
        maison = infos.get('maison', 'n/a')
        lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
    return "\n".join(lignes)

def formater_aspects(aspects):
    lignes = []
    for asp in aspects:
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        type_asp = asp.get('aspect', '?')
        orbe = asp.get('orbe', '?')
        lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes)

def formater_aspects_significatifs(aspects, seuil_orbe=5.0):
    lignes = []
    for asp in aspects:
        orbe = asp.get('orbe')
        if orbe is not None and orbe <= seuil_orbe:
            p1 = asp.get('planete1', '?')
            p2 = asp.get('planete2', '?')
            type_asp = asp.get('aspect', '?')
            lignes.append(f"{p1} {type_asp} {p2} (orbe {orbe}°)")
    return "\n".join(lignes) if lignes else "Aucun aspect significatif (orbe ≤ 5°)."

# ✅ Exemples de test → protéger avec if __name__ == "__main__"
if __name__ == "__main__":
    aspects_exemple = [
        {'planete1': 'Lune', 'planete2': 'Uranus', 'aspect': 'opposition', 'orbe': 6.2},
        {'planete1': 'Soleil', 'planete2': 'Pluton', 'aspect': 'conjonction', 'orbe': 2.5},
        {'planete1': 'Mars', 'planete2': 'Neptune', 'aspect': 'carré', 'orbe': 5.0},
        {'planete1': 'Vénus', 'planete2': 'Saturne', 'aspect': 'sextile', 'orbe': 1.8}
    ]
    print(formater_aspects_significatifs(aspects_exemple))