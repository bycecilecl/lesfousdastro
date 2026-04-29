# utils/karmique/doctrine/maison_4.py
from typing import Dict

MAISON_4 = {
    "nom": "Maison IV — Fond du Ciel",
    "tagline": "Mémoire familiale, racines, personnages karmiques.",
    "logique": (
        "Maison transgénérationnelle majeure. Elle indique la mémoire du clan, "
        "les empreintes d’enfance et surtout les personnages déjà rencontrés "
        "dans d’autres vies (via les planètes 'personnages').\n\n"
        "On vient souvent dans une lignée qui réactive un bagage déjà connu : "
        "ce n’est pas 'punition', c’est résonance + opportunité de transformation."
    ),

    # Planètes dites “personnages” (jusqu’à Saturne, + Jupiter comme figure guide)
    "planetes_personnages": {
        "Soleil": "Père",
        "Lune": "Mère",
        "Saturne": "Père éducateur / cadre / autorité",
        "Mercure": "Fratrie / enfants / amis proches / jumeau-jumelle (motif de lien)",
        "Vénus": "Amante / sœur / relation affective / amie",
        "Mars": "Amant / frère / rival / dynamique de confrontation",
        "Jupiter": "Guide / mentor / figure de protection",
    },

    # Planètes lentes = tonalité transgénérationnelle plus “archétypale”
    "planetes_lentes": {
        "Uranus": "Blessure de rejet / rupture / instabilité du lien",
        "Neptune": "Blessure d’abandon / flou transgénérationnel / non-dits",
        "Pluton": "Violence / méfiance / survie / emprise (transformation forcée)",
    },

    # Règles / nuances (tu enrichiras au fil du temps)
    "nuances": [
        "Si une planète 'personnage' est en IV : possible résonance avec une figure réelle (père/mère/frère/sœur...) dans cette vie.",
        "Si pas de sœur/frère etc. : le motif se projette sur des rencontres-clés (archétype).",
        "Si la planète est rétrograde/interceptée/en tension : vécu plus lourd ou non résolu, sujet sensible dans la lignée.",
        "Les maîtres du FC et du MC peuvent aussi décrire les parents (logique à intégrer ensuite si tu veux).",
    ],
}


def get_maison_4() -> Dict:
    """Retourne la doctrine structurée de la Maison IV."""
    return MAISON_4