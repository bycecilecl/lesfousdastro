from utils.transits.selection import selectionner_transits_flash
from utils.transits.modeles import TransitActif


def transit(planete, aspect, cible, orbe, importance):
    return TransitActif(
        planete_transit=planete,
        planete_natale=cible,
        aspect=aspect,
        orbe=orbe,
        importance=importance,
    )


def test_flash_garde_un_seul_transit_de_mars():
    aspects = [
        transit("Mars", "carré", "Vénus", 1.0, 20),
        transit("Mars", "opposition", "Mercure", 0.5, 18),
        transit("Saturne", "trigone", "Soleil", 1.0, 17),
    ]

    selection = selectionner_transits_flash(aspects)

    assert [t.planete_transit for t in selection].count("Mars") == 1
    assert selection[0].planete_natale == "Vénus"


def test_flash_applique_des_orbes_martiens_plus_serres():
    aspects = [
        transit("Mars", "carré", "Vénus", 2.1, 30),
        transit("Mars", "conjonction", "Soleil", 3.0, 25),
        transit("Mars", "trigone", "Lune", 0.1, 40),
        transit("Jupiter", "sextile", "Mercure", 4.0, 15),
    ]

    selection = selectionner_transits_flash(aspects)

    assert [(t.planete_transit, t.planete_natale) for t in selection] == [
        ("Mars", "Soleil"),
        ("Jupiter", "Mercure"),
    ]


def test_flash_ne_depasse_pas_sept_transits_et_reserve_une_place_a_mars():
    aspects = [
        transit("Saturne", "carré", f"Cible {index}", 1.0, 30 - index)
        for index in range(8)
    ]
    aspects.append(transit("Mars", "opposition", "Ascendant", 1.0, 10))

    selection = selectionner_transits_flash(aspects)

    assert len(selection) == 7
    assert any(t.planete_transit == "Mars" for t in selection)
