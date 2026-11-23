"""Filtrage des sources des rapports hors karmique, sans mutation du thème natal."""


def mentionne_point_illumination(valeur):
    if isinstance(valeur, str):
        nom = "".join(c for c in valeur.casefold() if c.isalnum())
        return any(point in nom for point in (
            "pointdillumination", "pointillumination", "signeillumination",
            "maisonillumination", "degreillumination",
        )) or nom == "illumination"
    if isinstance(valeur, dict):
        return any(mentionne_point_illumination(k) or mentionne_point_illumination(v)
                   for k, v in valeur.items())
    if isinstance(valeur, (list, tuple)):
        return any(mentionne_point_illumination(v) for v in valeur)
    return False


def sans_point_illumination(valeur):
    """Copie les sources sans le point, ses contacts, figures et lignes associées.

    À appeler à l'entrée des moteurs hors karmique seulement. Les calculs
    partagés et le thème original restent disponibles pour le karmique.
    """
    if isinstance(valeur, dict):
        return {k: sans_point_illumination(v) for k, v in valeur.items()
                if not mentionne_point_illumination(str(k))}
    if isinstance(valeur, (list, tuple)):
        return type(valeur)(sans_point_illumination(v) for v in valeur
                            if not mentionne_point_illumination(v))
    if isinstance(valeur, str):
        return "".join(ligne for ligne in valeur.splitlines(keepends=True)
                       if not mentionne_point_illumination(ligne))
    return valeur
