# ─────────────────────────────────────────────────────────────────────────────
# Rôle : Fonctions de formatage “texte” pour afficher les placements et aspects.
# Contexte : utilisé par l’analyse gratuite, le Point Astral et les résumés.
# Doublons connus :
#   - utils_analyse.py (formater_positions_planetes / formater_aspects)
#   - utils/format_utils.py (variantes proches)
# Recommandation :
#   → Centraliser ici et supprimer/archiver les doublons ailleurs.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_positions_planetes(planetes)
# Rôle : transforme le dict de planètes en lignes lisibles "Nom : Signe X° (Maison N)".
# Entrée :
#   - planetes (dict) : {"Soleil": {"signe": "...", "degre": 12.3, "maison": 5}, ...}
# Sortie :
#   - str multi‑ligne prêt à afficher (une ligne par planète)
# Tolérance :
#   - valeurs manquantes → "inconnu" / "n/a"
# ─────────────────────────────────────────────────────────────────────────────

def formater_positions_planetes(planetes, style="standard"):
    def _fmt_degre(infos):
        # accepte 'degre' ou 'degre_dans_signe', nombre ou chaîne
        deg = infos.get('degre')
        if deg is None:
            deg = infos.get('degre_dans_signe')
        if deg is None or deg == "":
            return "n/a"
        try:
            return f"{round(float(str(deg).replace(',', '.').replace('°','')), 2)}"
        except (TypeError, ValueError):
            return "n/a"

    lignes = []
    for nom, infos in planetes.items():
        signe = infos.get('signe', 'inconnu')
        degre = _fmt_degre(infos)
        maison = infos.get('maison', 'n/a')
        maison = maison if maison not in (None, "") else "n/a"

        if style == "compact":
            lignes.append(f"{nom} : {signe} {degre}° — Maison {maison}")
        else:  # "standard"
            lignes.append(f"{nom} : {signe} {degre}° (Maison {maison})")
    return "\n".join(lignes)

# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_aspects(aspects)
# Rôle : formate tous les aspects au format "P1 Aspect P2 (orbe X°)".
# Entrée :
#   - aspects (list[dict]) : [{'planete1','planete2','aspect','orbe'}, ...]
# Sortie :
#   - str multi‑ligne listant tous les aspects (sans filtrage d’orbe)
# ─────────────────────────────────────────────────────────────────────────────


ASPECTS_MAJEURS = ("conjonction", "opposition", "carré", "trigone", "sextile")
ASPECTS_MINEURS = ("quinconce", "semi-carré", "sesqui-carré")

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


# ─────────────────────────────────────────────────────────────────────────────
# UTIL : formater_aspects_significatifs(aspects, seuil_orbe=5.0)
# Rôle : idem formater_aspects mais NE GARDE que les aspects avec orbe ≤ seuil.
# Entrées :
#   - aspects (list[dict]) : mêmes clés que ci‑dessus
#   - seuil_orbe (float)   : filtre (par défaut 5°)
# Sortie :
#   - str multi‑ligne filtré, ou message “Aucun aspect significatif …”
# ─────────────────────────────────────────────────────────────────────────────

def formater_aspects_significatifs(aspects, seuil_orbe=5.0, avec_arrondi=True):
    lignes = []
    for asp in aspects:
        o = _to_float(asp.get('orbe'))
        if o is None or o > float(seuil_orbe):
            continue
        p1 = asp.get('planete1', '?')
        p2 = asp.get('planete2', '?')
        t_norm = _norm_aspect_name(asp.get('aspect', '?'))
        orbe_affichage = f"{round(o, 2)}" if avec_arrondi else asp.get('orbe', o)
        lignes.append(f"{p1} {t_norm.capitalize()} {p2} (orbe {orbe_affichage}°)")
    return "\n".join(lignes) if lignes else f"Aucun aspect significatif (orbe ≤ {seuil_orbe}°)."


def formater_resume_complet(planetes, aspects, seuil_orbe_significatif=5.0, avec_titres=True):
    blocs = []
    if avec_titres: blocs.append("=== POSITIONS ===")
    blocs.append(formater_positions_planetes(planetes))

    if avec_titres: blocs.append("\n=== ASPECTS SIGNIFICATIFS ===")
    blocs.append(formater_aspects_significatifs(aspects, seuil_orbe_significatif))

    return "\n".join(blocs)

__all__ = [
    "ASPECTS_MAJEURS",
    "ASPECTS_MINEURS",
    "formater_positions_planetes",
    "formater_aspects",
    "formater_aspects_significatifs",
    "formater_resume_complet",
]


# ✅ Exemples de test → protéger avec if __name__ == "__main__"
if __name__ == "__main__":
    aspects_exemple = [
        {'planete1': 'Lune', 'planete2': 'Uranus', 'aspect': 'OPPOSITION', 'orbe': 6.2},
        {'planete1': 'Soleil', 'planete2': 'Pluton', 'aspect': 'conjonction', 'orbe': 2.5},
        {'planete1': 'Mars', 'planete2': 'Neptune', 'aspect': 'carre', 'orbe': 5.0},     # <- sans accent
        {'planete1': 'Vénus', 'planete2': 'Saturne', 'aspect': 'semi-carre', 'orbe': 1.8} # <- sans accent
    ]
    print(formater_aspects_significatifs(aspects_exemple))