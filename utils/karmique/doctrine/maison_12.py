# utils/karmique/doctrine/maison_12.py
from typing import Dict

MAISON_12 = {
    "nom": "Maison XII",
    "tagline": "Vie immédiatement antérieure, inconscient, dettes/dissolution karmique.",
    "logique": (
        "Maison karmique majeure : elle parle des conditionnements inconscients "
        "encore actifs, souvent issus de la vie immédiatement antérieure.\n\n"
        "On y voit ce qui se rejoue en arrière-plan (peurs diffuses, culpabilité, "
        "auto-sabotage, fuite), mais aussi une immense capacité de guérison et de "
        "dissolution si on l’aborde avec lucidité."
    ),

    # Tu avais la même grille que VIII : ok, on la garde
    "contenu_karmique_par_planete": {
        "Soleil": "Karma parental / identité / fin de cycle",
        "Lune": "Karma parental / mémoire émotionnelle",
        "Mercure": "Karma lié à l’enfance / ruminations / mental",
        "Vénus": "Karma relationnel / attachements / idéalisation",
        "Mars": "Karma de domination / colère refoulée / fuite dans l’action",
        "Jupiter": "Karma de pouvoir / croyances / sens / de prise de place",
        "Saturne": "Karma parental / de responsabilités / isolement / épreuves",
        "Uranus": "Karma de gourou, idéologique / rejet / rupture inconsciente",
        "Neptune": "Karma de manipulation spirituelle / illusions / brouillard / fuite",
        "Pluton": "Karma assez violent de survie / peur / projet de transformation",
    },

    "nuances": [
        "Maison XII = ce qui agit avant même que tu comprennes : réflexes automatiques.",
        "Planètes en XII : puissantes, mais souvent vécues en 'caché' ou en retrait.",
        "Le signe de XII (et plus tard ton tableau 'XII en Bélier/Taureau…') donne la couleur de la vie précédente.",
    ],
}


def get_maison_12() -> Dict:
    return MAISON_12