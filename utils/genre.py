# utils/genre.py (ou à l'endroit où tu l'as déjà mise)
from typing import Dict, Any
from flask import request, session

def get_user_prefs(session, request) -> Dict[str, str]:
    """
    Récupère tonalité et genre depuis plusieurs sources :
    - session["infos_utilisateur"]
    - request.form / request.json
    - data_theme éventuel (fallback)
    Normalise:
      tonalité -> "tu"|"vous"
      genre    -> "homme"|"femme"|"" (si inconnu)
    """
    infos = session.get("infos_utilisateur") or {}

    # 1) Inputs bruts (multi-sources + alias)
    # Tonalité
    tonalite_in = (
        infos.get("tonalite")
        or (request.form.get("tonalite") if request else None)
        or ((request.get_json(silent=True) or {}).get("tonalite") if request and request.is_json else None)
    )

    # Genre/sex/gender + flags éventuels
    gender_in = (
        infos.get("gender") or infos.get("genre") or infos.get("sex") or infos.get("sexe")  # 🔥 gender EN PREMIER
        or (request.form.get("genre") if request else None)
        or (request.form.get("gender") if request else None)
        or (request.form.get("sex") if request else None)
        or ((request.get_json(silent=True) or {}).get("genre") if request and request.is_json else None)
        or ((request.get_json(silent=True) or {}).get("gender") if request and request.is_json else None)
        or ((request.get_json(silent=True) or {}).get("sex") if request and request.is_json else None)
    )

    # 2) Normalisation tonalité
    t = str(tonalite_in or "").strip().lower()
    tonalite = "vous" if t == "vous" else "tu"

    # 3) Normalisation genre (accepte beaucoup de variantes)
    g = str(gender_in or "").strip().lower()
    femme_vals = {"f", "femme", "female", "woman", "w"}  # ✅ "female" est bien là
    homme_vals = {"m", "homme", "male", "man", "h"}     # ✅ "male" est bien là

    if g in femme_vals or g.startswith(("f", "w")):
        genre = "femme"
    elif g in homme_vals or g.startswith(("m", "h")):
        genre = "homme"
    else:
        genre = ""   # neutre si on ne sait pas
    # 4) Debug compact (temporaire)
    print(f"🔧 PREFS.get_user_prefs -> tonalite={tonalite} | genre={genre} | raw='{gender_in}'")

    return {"tonalite": tonalite, "genre": genre}