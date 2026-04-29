# utils/karmique/karmique_anaretic.py

ANARETIC_29 = {
    "Soleil": "Le degré 29 du Soleil indique une tension autour de l’identité, avec un sentiment d’urgence à s’affirmer ou à exister pleinement.",
    "Lune": "Le degré 29 de la Lune indique des émotions exacerbées, des crises familiales ou de sécurité émotionnelle.",
    "Mercure": "Le degré 29 de Mercure met la pensée et la parole sous pression, avec une difficulté à relâcher le mental.",
    "Vénus": "Le degré 29 de Vénus intensifie les enjeux relationnels et affectifs, ainsi que les crises financières",
    "Mars": "Le degré 29 de Mars crée une tension dans l’action, la colère ou le désir, avec une énergie à la fois puissante et difficile à canaliser.",
    "Jupiter": "Le degré 29 de Jupiter met sous pression les croyances, les aspirations ou la confiance, avec une impression d’excès ou de débordement.",
    "Saturne": "Le degré 29 de Saturne accentue la peur de l’échec ou le poids des responsabilités ainsi que des pressions liées à l'autorité ou à l'ordre",
    "Uranus": "Le degré 29 d’Uranus intensifie le besoin de rupture, de libération ou de changement brusque.",
    "Neptune": "Le degré 29 de Neptune accentue la confusion, la porosité ou l’idéalisation, avec une difficulté à poser des limites claires.",
    "Pluton": "Le degré 29 de Pluton donne une intensité extrême aux processus de contrôle, de survie ou de transformation."
}

ANARETIC_SIGN = {
    "Bélier": "pression dans l’action, impulsivité, besoin urgent d’agir ou de s’imposer",
    "Taureau": "tension autour de la sécurité, de la possession ou de l’attachement matériel",
    "Gémeaux": "surcharge mentale, difficulté à canaliser la pensée ou la communication",
    "Cancer": "intensité émotionnelle, besoin de sécurité affective très fort",
    "Lion": "enjeux d’ego, besoin de reconnaissance, difficulté à trouver sa juste place",
    "Vierge": "hypercontrôle, perfectionnisme, tension sur les détails et le mental",
    "Balance": "déséquilibre relationnel, difficulté à trouver une position juste",
    "Scorpion": "intensité émotionnelle extrême, luttes de pouvoir, transformation profonde",
    "Sagittaire": "crise de sens, remise en question des croyances ou de la direction",
    "Capricorne": "pression liée aux responsabilités, au contrôle ou à la réussite",
    "Verseau": "besoin de rupture, tension entre liberté et appartenance",
    "Poissons": "confusion, hypersensibilité, difficulté à poser des limites"
}

def get_anaretic_interp(planete: str) -> str:
    return ANARETIC_29.get(planete, "")

def get_anaretic_sign_interp(signe: str) -> str:
    return ANARETIC_SIGN.get(signe, "")