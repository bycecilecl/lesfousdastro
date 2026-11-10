from module.amour_blocs.normalisation_maisons import normaliser_maisons_theme
from copy import deepcopy
# module/amour_blocs/utils_theme.py

def filtrer_point_illumination_amour(theme: dict) -> dict:
    """Prepare une copie sans ce point, uniquement pour les donnees du profil amoureux."""
    copie = deepcopy(theme)

    def nom_normalise(valeur):
        return "".join(c for c in str(valeur).casefold() if c.isalnum())

    def est_point(valeur):
        return nom_normalise(valeur) in {"pointdillumination", "pointillumination"}

    def mentionne_point(valeur):
        if isinstance(valeur, str):
            texte = nom_normalise(valeur)
            return "pointdillumination" in texte or "pointillumination" in texte
        if isinstance(valeur, dict):
            return any(mentionne_point(cle) or mentionne_point(v) for cle, v in valeur.items())
        if isinstance(valeur, (list, tuple)):
            return any(mentionne_point(v) for v in valeur)
        return False

    for cle in list(copie):
        if est_point(cle):
            del copie[cle]

    for cle in (
        "planetes", "planètes", "planetes_deg", "positions_tropicales",
        "positions_vediques", "planetes_vediques", "placements_occidentaux",
        "placements_occ", "resultats_tropical",
    ):
        positions = copie.get(cle)
        if isinstance(positions, dict):
            copie[cle] = {nom: valeur for nom, valeur in positions.items() if not est_point(nom)}

    for cle in ("aspects", "aspects_significatifs", "aspects_avec_angles", "aspects_occidentaux"):
        aspects = copie.get(cle)
        if isinstance(aspects, (list, tuple)):
            copie[cle] = type(aspects)(aspect for aspect in aspects if not mentionne_point(aspect))

    for cle in ("points_forts", "axes_majeurs", "resume_points_forts"):
        valeur = copie.get(cle)
        if isinstance(valeur, str):
            copie[cle] = "".join(ligne for ligne in valeur.splitlines(keepends=True) if not mentionne_point(ligne))
        elif isinstance(valeur, (list, tuple)):
            copie[cle] = type(valeur)(entree for entree in valeur if not mentionne_point(entree))
        elif isinstance(valeur, dict):
            copie[cle] = {
                nom: entree for nom, entree in valeur.items()
                if not mentionne_point(nom) and not mentionne_point(entree)
            }

    return copie


def exporter_theme_complet(theme: dict) -> str:
    """
    Retourne un texte brut avec :
    - positions planètes + maisons
    - dignités (si dispo)
    - aspects significatifs
    Objectif : donner au LLM une vision globale du thème.
    """
    theme = normaliser_maisons_theme(theme)
    planetes = theme.get("planetes", {}) or theme.get("planètes", {}) or {}
    aspects = theme.get("aspects_significatifs") or theme.get("aspects") or []

    lignes = []

    # Positions planètes
    lignes.append("=== POSITIONS PLANÈTES & MAISONS ===")
    for nom, d in planetes.items():
        signe = d.get("signe")
        maison = d.get("maison")
        degre = d.get("degre") or d.get("degré")
        retro = d.get("retro") or d.get("r") or d.get("retrograde")
        suffix_retro = " (rétrograde)" if retro else ""
        lignes.append(f"- {nom} : {signe} {f'{degre}° ' if degre is not None else ''}(Maison {maison}){suffix_retro}")

    # Dignités (si tu veux les donner systématiquement)
    try:
        from module.amour_blocs.dignites import get_dignite_planete
        lignes.append("\n=== DIGNITÉS PLANÉTAIRES ===")
        for nom, d in planetes.items():
            signe = d.get("signe")
            if not signe:
                continue
            dign = get_dignite_planete(nom, signe)
            if dign:
                lignes.append(f"- {nom} en {signe} : {dign}")
    except Exception:
        # On ne plante pas le module si import raté
        pass

    # Aspects
    lignes.append("\n=== ASPECTS SIGNIFICATIFS ===")
    if isinstance(aspects, list):
        for asp in aspects:
            p1 = asp.get("planete1")
            p2 = asp.get("planete2")
            type_asp = asp.get("aspect")
            orbe = asp.get("orbe")
            if p1 and p2 and type_asp:
                txt_orbe = f" (orbe {orbe}°)" if orbe is not None else ""
                lignes.append(f"- {p1} {type_asp} {p2}{txt_orbe}")

    return "\n".join(lignes).strip()
