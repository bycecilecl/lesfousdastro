"""Formatage du gratuit identique au local validé, isolé des autres rapports."""

ASPECTS_MAJEURS = ("conjonction", "opposition", "carré", "quinconce", "trigone", "sextile")

ASPECTS_MINEURS = ("semi-carré", "sesqui-carré")

def _to_float(x):
    try:
        return float(str(x).replace(',', '.'))
    except (TypeError, ValueError):
        return None

def _norm_aspect_name(x: str) -> str:
    if not isinstance(x, str):
        return "?"
    t = x.strip().lower()
    # variantes sans accent
    t = t.replace("carre", "carré").replace("semi-carre", "semi-carré").replace("sesqui-carre", "sesqui-carré")
    return t

def formater_aspects(aspects, avec_arrondi=True, tri="importance"):
    items = list(aspects)

    if tri == "importance":
        ordre = {n: i for i, n in enumerate(ASPECTS_MAJEURS + ASPECTS_MINEURS)}
        items.sort(key=lambda a: (
            ordre.get(_norm_aspect_name(a.get("aspect", "?")), 999),
            abs(_to_float(a.get("orbe")) or 9e9)
        ))
    elif tri == "orbe":
        items.sort(key=lambda a: abs(_to_float(a.get("orbe")) or 9e9))

    lignes = []
    for asp in items:
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        t_norm = _norm_aspect_name(asp.get('aspect', '?'))
        o = _to_float(asp.get('orbe'))
        orbe_txt = f"{round(o, 2)}" if (avec_arrondi and o is not None) else (
            asp.get('orbe', '?') if asp.get('orbe') is not None else "?"
        )
        lignes.append(f"{p1} {t_norm.capitalize()} {p2} (orbe {orbe_txt}°)")
    return "\n".join(lignes)
