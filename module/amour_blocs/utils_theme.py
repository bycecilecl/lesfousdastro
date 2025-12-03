# module/amour_blocs/utils_theme.py

def exporter_theme_complet(theme: dict) -> str:
    """
    Retourne un texte brut avec :
    - positions planètes + maisons
    - dignités (si dispo)
    - aspects significatifs
    Objectif : donner au LLM une vision globale du thème.
    """
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