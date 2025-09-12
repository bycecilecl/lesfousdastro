# orchestration/concat_analyses.py
import os
from datetime import datetime

from blocs.bloc_1 import generer_bloc_1
from blocs.bloc_2 import generer_bloc_2
from blocs.bloc_3 import generer_bloc_3
from blocs.bloc_4 import generer_bloc_4
from blocs.bloc_5 import generer_bloc_5

SEPARATEUR = "\n\n---\n\n"  # simple séparateur lisible

def construire_contexte(data_theme: dict) -> dict:
    """
    Transforme tes données calculées (ex: calcul_theme) en 'contexte' compact
    passé à chaque bloc. Ajuste selon ton projet.
    """
    return {
        "resume": data_theme.get("resume_global", ""),
        "donnees": data_theme.get("placements_occ", ""),
        "points_cles": data_theme.get("points_forts", ""),
        "aspects": data_theme.get("aspects_significatifs", ""),
        "amas_axes": data_theme.get("amas_axes", ""),
    }

def generer_analyse_complete(data_theme: dict) -> str:
    """
    Enchaîne les 5 appels LLM et renvoie un texte unique.
    """
    contexte = construire_contexte(data_theme)

    b1 = generer_bloc_1(contexte)
    b2 = generer_bloc_2(contexte)
    b3 = generer_bloc_3(contexte)
    b4 = generer_bloc_4(contexte)
    b5 = generer_bloc_5(contexte)

    rendu = SEPARATEUR.join([
        "# Bloc 1\n" + b1,
        "# Bloc 2\n" + b2,
        "# Bloc 3\n" + b3,
        "# Bloc 4\n" + b4,
        "# Bloc 5\n" + b5,
    ])

    return rendu

def sauvegarder_rendu(rendu: str, dossier: str = "outputs", prefix: str = "analyse") -> str:
    os.makedirs(dossier, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = os.path.join(dossier, f"{prefix}_{ts}.md")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(rendu)
    return chemin