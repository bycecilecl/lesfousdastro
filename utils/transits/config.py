# utils/transits/config.py

print("🔥 CONFIG LOADED")

PLANETES_TRANSIT = [
    "Jupiter",
    "Saturne",
    "Uranus",
    "Neptune",
    "Pluton",
    "Mars",
]

PLANETES_NATALES_CIBLES = [
    "Soleil",
    "Lune",
    "Mercure",
    "Vénus",
    "Mars",
    "Ascendant",
    "Milieu du Ciel",
]

ASPECTS_TRANSITS = {
    "conjonction": 0,
    "sextile": 60,
    "carré": 90,
    "trigone": 120,
    "opposition": 180,
}

ORBES_TRANSITS = {
    "conjonction": 5,
    "opposition": 5,
    "carré": 4,
    "trigone": 4,
    "sextile": 3,
}

PLANETES_LENTES = [
    "Jupiter",
    "Saturne",
    "Uranus",
    "Neptune",
    "Pluton",
]

# Mars apporte le déclencheur concret d'une période, sans avoir la portée
# structurelle des planètes lentes. Il suit donc des règles plus strictes.
ASPECTS_MARS_FLASH = [
    "conjonction",
    "opposition",
    "carré",
]

CIBLES_MARS_ORBE_ELARGI = [
    "Soleil",
    "Lune",
    "Ascendant",
    "Descendant",
    "Milieu du Ciel",
    "Fond du Ciel",
]

ORBE_MARS_FLASH = 2.0
ORBE_MARS_FLASH_CIBLES_MAJEURES = 3.0
MAX_TRANSITS_MARS_AFFICHES = 1

ASPECTS_MAJEURS = [
    "conjonction",
    "opposition",
    "carré",
    "trigone",
    "sextile",
]

CIBLES_PERSONNELLES = [
    "Soleil",
    "Lune",
    "Ascendant",
    "Mercure",
    "Vénus",
    "Mars",
]

POIDS_CIBLES_NATALES = {
    "Soleil": 5,
    "Lune": 5,
    "Ascendant": 5,
    "Descendant": 5,
    "Milieu du Ciel": 5,
    "Fond du Ciel": 5,
    "MC": 5,
    "Mercure": 4,
    "Vénus": 4,
    "Mars": 4,
    "Jupiter": 2,
    "Saturne": 3,
    "Uranus": 1,
    "Neptune": 1,
    "Pluton": 1,
    "Chiron": 1,
    "Lune Noire": 1,
    "Junon": 0,
}

POIDS_ASPECTS = {
    "conjonction": 5,
    "opposition": 4,
    "carré": 4,
    "trigone": 3,
    "sextile": 2,
}

CIBLES_PRIORITAIRES_TRANSITS = [
    "Soleil", "Lune", "Ascendant", "Mercure", "Vénus", "Mars", "Saturne"
]

PLANETES_EXCLUES = [
    "Junon",
]


MAX_TRANSITS_AFFICHES = 7
IMPORTANCE_MIN_AFFICHAGE = 4


# ─────────────────────────────────────────────────────────────
# PONDÉRATION NARRATIVE DES TRANSITS
# Sert à hiérarchiser le climat astrologique réel
# ─────────────────────────────────────────────────────────────

POIDS_PLANETES_TRANSIT = {
    "Pluton": 10,
    "Neptune": 9,
    "Saturne": 9,
    "Uranus": 8,
    "Chiron": 7,
    "Jupiter": 5,
    "Mars": 4,
    "Vénus": 2,
    "Mercure": 1,
    "Lune": 1,
}

POIDS_PLANETES_NATALES = {
    "Soleil": 10,
    "Lune": 10,
    "Ascendant": 10,
    "Descendant": 10,
    "Milieu du Ciel": 10,
    "Fond du Ciel": 10,
    "MC": 10,
    "Saturne": 8,
    "Pluton": 8,
    "Mars": 7,
    "Vénus": 7,
    "Mercure": 6,
    "Jupiter": 6,
    "Neptune": 6,
    "Uranus": 6,
    "Chiron": 7,
}

POIDS_ASPECTS = {
    "conjonction": 10,
    "opposition": 9,
    "carré": 9,
    "trigone": 6,
    "sextile": 4,
}
