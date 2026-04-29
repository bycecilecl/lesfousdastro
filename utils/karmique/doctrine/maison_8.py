# utils/karmique/doctrine/maison_8.py
from typing import Dict

MAISON_8 = {
    "nom": "Maison VIII",
    "tagline": "Crises, tabous, transformation : comportements karmiques à épurer.",
    "logique": (
        "Maison karmique de transformation : elle parle moins des 'personnages' "
        "et plus des comportements, tabous, schémas de pouvoir/peur, et des erreurs "
        "ou excès à purifier.\n\n"
        "Le signe sur la cuspide de VIII et le maître de VIII indiquent la zone "
        "d’apprentissage. Les planètes en VIII : zones de crise -> zones de mue."
    ),

    # Ton tableau “contenu karmique” (version claire)
    "contenu_karmique_par_planete": {
        "Soleil": "Karma parental / ego / autorité",
        "Lune": "Karma parental / attachement / sécurité",
        "Mercure": "Karma lié à l’enfance / mental / apprentissages",
        "Vénus": "Karma relationnel / affectif / amour / argent",
        "Mars": "Karma de domination / conflit / impulsivité",
        "Jupiter": "Karma de pouvoir / prise de place / influence",
        "Saturne": "Karma de responsabilités / limites / devoir",
        "Uranus": "Karma idéologique / rupture / gourou intérieur",
        "Neptune": "Karma spirituel / illusion / fuite / manipulation subtile",
        "Pluton": "Karma de transformation profonde / intensité / survie",
    },

    "nuances": [
        "Maison VIII = 'je ne peux plus faire comme avant' : elle force l’évolution.",
        "Plus il y a de planètes en VIII, plus la vie pousse à transmuter plutôt qu’éviter.",
        "Le maître de VIII (signe+maison+aspects) est une clé majeure : à interpréter systématiquement plus tard.",
    ],
}


def get_maison_8() -> Dict:
    return MAISON_8