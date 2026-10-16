"""Exclusions communes avant rédaction ; aucun choix de période ni appel IA."""

from ..filtrage_aspects import fait_autorise


LENTES = frozenset({"Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"})
PERSONNELLES = frozenset({"Soleil", "Lune", "Mercure", "Vénus", "Mars"})
ANGLES = frozenset({"Ascendant", "Descendant", "MC", "FC"})
CIBLES_EXCLUES = frozenset({"Chiron", "Lune Noire", "Part de Fortune", "Rahu", "Ketu"})


def points_transit(evenement):
    return {evenement["cible"], *evenement.get("axe_angles", {}),
            *evenement.get("axe_noeuds", {}),
            *(c["cible"] for c in evenement.get("contacts_complementaires_axe", []))}


def bornes_transit(evenement):
    datation = evenement.get("datation") or {}
    axe = evenement.get("fenetre_axe") or {}
    debut = axe.get("debut_utc") or datation.get("entree_utc") or evenement.get("debut")
    fin = axe.get("fin_utc") or datation.get("sortie_utc") or evenement.get("fin")
    return tuple(v.split("T", 1)[0] if isinstance(v, str) else None for v in (debut, fin))


def motif_exclusion_transit(dossier, fait):
    """Règles sans dépendance aux textes précédents ; Mars reste un candidat déclencheur.

    L'admission ne signifie pas que le transit mérite une période. Le bloc 4
    conserve son choix de familles, ses plafonds et son rattachement de Mars.
    """
    if fait.get("type") != "transit":
        return "Ce fait n'est pas un transit."
    e = fait["valeur"]
    noms = points_transit(e)
    if noms & CIBLES_EXCLUES or not fait_autorise(fait) or e["aspect"] == "quinconce":
        return "Cible ou aspect exclu."
    maitre = dossier["profection"]["maitre_annee"]["nom"]
    if e["reference"] == "natal" and not noms & (PERSONNELLES | ANGLES | {maitre}):
        return "Cible lente natale secondaire : priorité aux personnelles, angles et maître de l'année."
    debut, fin = bornes_transit(e)
    if not debut or not fin or fin < debut:
        return "Bornes archivées absentes ou incohérentes."
    if e["planete_transit"] not in LENTES | {"Mars"}:
        return "Planète mobile hors sélection annuelle."
    return None


def transit_autorise(dossier, fait):
    return motif_exclusion_transit(dossier, fait) is None
