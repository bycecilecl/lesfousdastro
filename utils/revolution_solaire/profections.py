"""Profection annuelle traditionnelle pour la révolution solaire.

La profection avance l'Ascendant natal d'un signe par année révolue. Les
maîtrises sont volontairement classiques : elles servent aux maîtres du temps
et ne sont pas les doubles maîtrises modernes utilisées dans d'autres modules.
"""

from __future__ import annotations

from utils.calculs_astrologiques import get_maison_planete


SIGNES = (
    "Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge",
    "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons",
)

MAITRES_TRADITIONNELS = {
    "Bélier": "Mars",
    "Taureau": "Vénus",
    "Gémeaux": "Mercure",
    "Cancer": "Lune",
    "Lion": "Soleil",
    "Vierge": "Mercure",
    "Balance": "Vénus",
    "Scorpion": "Mars",
    "Sagittaire": "Jupiter",
    "Capricorne": "Saturne",
    "Verseau": "Saturne",
    "Poissons": "Jupiter",
}


def _cuspides(theme: dict) -> list[float]:
    try:
        return [
            float(theme["maisons"][f"Maison {numero}"]["degre"])
            for numero in range(1, 13)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Les cuspides du thème RS sont incomplètes.") from exc


def _position(theme: dict, nom: str) -> dict | None:
    position = (theme.get("planetes") or {}).get(nom)
    return dict(position) if position else None


def calculer_profection_annuelle(
    theme_natal: dict,
    theme_rs: dict,
    *,
    age: int,
) -> dict:
    """Calcule l'Ascendant profecté et le maître traditionnel de l'année.

    ``age`` est l'âge atteint au retour solaire concerné. À 0 an, l'Ascendant
    profecté coïncide avec l'Ascendant natal ; le cycle se répète tous les 12 ans.
    """
    if isinstance(age, bool) or not isinstance(age, int) or age < 0:
        raise ValueError("L'âge de profection doit être un entier positif ou nul.")

    try:
        ascendant_natal = float(theme_natal["angles_deg"]["Ascendant"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Ascendant natal indisponible.") from exc

    degre_profecte = (ascendant_natal + age * 30) % 360
    index_signe = int(degre_profecte // 30)
    signe = SIGNES[index_signe]
    maitre = MAITRES_TRADITIONNELS[signe]

    return {
        "age": age,
        "cycle": age % 12,
        "convention": "profection annuelle traditionnelle, un signe par année",
        "ascendant_natal": {
            "degre": round(ascendant_natal, 2),
            "signe": SIGNES[int(ascendant_natal // 30)],
            "degre_dans_signe": round(ascendant_natal % 30, 2),
        },
        "ascendant_profecte": {
            "degre": round(degre_profecte, 2),
            "signe": signe,
            "degre_dans_signe": round(degre_profecte % 30, 2),
            "maison_rs": get_maison_planete(degre_profecte, _cuspides(theme_rs)),
        },
        "maitre_annee": {
            "nom": maitre,
            "natal": _position(theme_natal, maitre),
            "rs": _position(theme_rs, maitre),
        },
    }
