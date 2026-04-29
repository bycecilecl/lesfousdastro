# utils/karmique/doctrine/maison_12_signes.py
from typing import Dict

MAISON_12_PAR_SIGNE: Dict[str, str] = {
    "Bélier": (
        "Vie de conquête, territoriale, sexuelle, guerrière. "
        "Problématique de colère, prises de positions tranchées et impulsives. "
        "Originaire de pays rudes où la valeur se prouvait à travers le combat. "
        "Métiers (vie antérieure) : soldat, mercenaire, légionnaire, entrepreneur, "
        "métiers du fer (forgeron, soudeur), sportif/compétiteur."
    ),
    "Taureau": (
        "Vie régulière, routinière et laborieuse. "
        "Problématique d’adaptabilité, de sécurité, de possessivité. "
        "Originaire de pays où l’on s’enrichissait par le commerce, avec un lien fort à la terre. "
        "Métiers (vie antérieure) : agriculteur, éleveur, banquier, marchand, restaurateur, cuisinier, "
        "charcutier, boucher, marchand de vins."
    ),
    "Gémeaux": (
        "Vie de légèreté, curiosité, rires et voyages. "
        "Problématique pour se stabiliser, s’ancrer, s’engager. "
        "Originaire de communautés de voyageurs/nomades. "
        "Métiers (vie antérieure) : écrivain, éditeur, journaliste, commerçant, voleur, facteur, danseur, "
        "trapéziste, prestidigitateur, marchand d’oiseaux, conteur."
    ),
    "Cancer": (
        "Vie de famille, sensibilité, simplicité. "
        "Problématique émotionnelle : sentiment d’abandon, dépendance affective. "
        "Originaire de sociétés matriarcales, respect des anciens. "
        "Métiers (vie antérieure) : agent immobilier, hôtelier, décorateur d’intérieur, métiers de la marine, "
        "au foyer, pâtissier, cuisinier, cafetier, puériculteur, éducateur."
    ),
    "Lion": (
        "Vie de luxe, d’apparat, de créativité. "
        "Problématique de reconnaissance, d’ego, de confiance en soi. "
        "Originaire de pays royalistes/fastueux (époque des grands siècles). "
        "Métiers (vie antérieure) : roi, président, chef, noble, acteur, décorateur, costumier, métiers du spectacle, "
        "mécène, couturier, cardiologue, bijoutier."
    ),
    "Vierge": (
        "Vie de service, rigueur, précision, austérité. "
        "Problématique de perfectionnisme, d’exigence. "
        "Originaire de pays à moralité rigide, diktats de comportement. "
        "Métiers (vie antérieure) : domestique, employé de ménage, maître d’hôtel, pharmacien, secrétaire, sage-femme, "
        "infirmier, kiné, diététicien, botaniste, critique."
    ),
    "Balance": (
        "Vie de beauté, harmonie, équilibre. "
        "Problématique d’affirmation de soi, prise de position et décision. "
        "Originaire de lieux calmes, plaines et hautes montagnes. "
        "Métiers (vie antérieure) : juge, notaire, diplomate, législateur, danseur, artiste, amateur d’art, "
        "collectionneur, modiste, couturier, décorateur, esthétique."
    ),
    "Scorpion": (
        "Vie tourmentée, prise de risque et ruptures. "
        "Problématique d’anxiété, défiance, possessivité. "
        "Originaire de pays dangereux/en guerre, où la survie était omniprésente. "
        "Métiers (vie antérieure) : espion, enquêteur, fossoyeur, pompes funèbres, gynéco, chercheur, psychanalyste, "
        "philosophe, médium, éboueur, antiquaire."
    ),
    "Sagittaire": (
        "Vie de voyage, découverte, spiritualité. "
        "Problématique de prise de place, affirmation de soi, apprentissage. "
        "Originaire d’un milieu privilégié (bourgeoisie/aristocratie). "
        "Métiers (vie antérieure) : chef, cavalier, éleveur de chevaux, explorateur, ambassadeur, notable, député, juge, "
        "enseignant/professeur, missionnaire, ministre."
    ),
    "Capricorne": (
        "Vie de méditation, silence, construction. "
        "Problématique de rigidité, commandement. "
        "Originaire de pays arides : vies de pauvreté ou d’exil, importance des traditions. "
        "Métiers (vie antérieure) : spéléologue, guide-montagne, historien, archiviste, ostéopathe, tailleur de pierres, "
        "sculpteur, président, restaurateur d’objets."
    ),
    "Verseau": (
        "Vie d’altruisme, d’amitiés, d’idéologies. "
        "Problématique de liberté, rejet des normes, volonté de chaos. "
        "Originaire de pays en bouleversement (changement de régime). "
        "Métiers (vie antérieure) : gourou, ingénieur, technicien radio/télé, inventeur, astronaute, aviateur, électricien, "
        "animateur de groupes, anarchiste, leader."
    ),
    "Poissons": (
        "Vie de spiritualité, d’art, ou au contraire de déchéance et de maladie. "
        "Problématique d’idéalisation, rêverie trop prononcée, fuite. "
        "Originaire de pays humides, communautés spirituelles. "
        "Métiers (vie antérieure) : guérisseur, médium, prêtre, voyant, barman, trafiquant de drogues, officier de la marine, "
        "professions hospitalières, artiste, SDF, musicien."
    ),
}


def get_maison_12_par_signe(signe: str) -> str:
    """Retourne le texte 'Maison 12 en <signe>' si dispo."""
    return (MAISON_12_PAR_SIGNE.get(signe) or "").strip()