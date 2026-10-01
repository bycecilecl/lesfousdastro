"""Le ciel collectif ne dépend d'aucun thème natal."""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from utils.ciel_collectif import _aspect, _periodes_aspects_mois, ciel_collectif_mois
from utils.figures_ciel_collectif import _figures, figures_ciel_collectif


class TestCielCollectif(unittest.TestCase):
    def test_aspect_collectif_occupe_sa_periode_a_trois_degres(self):
        depart = datetime(2026, 10, 1, tzinfo=timezone.utc)

        def positions(instant):
            jours = (instant - depart).total_seconds() / 86400
            return {"Vénus": (214 + jours, 1), "Pluton": (307, 0)}

        def paires(valeurs):
            aspect = _aspect(valeurs["Vénus"][0], valeurs["Pluton"][0])
            if aspect:
                yield "Vénus", "Pluton", *aspect

        _periodes_aspects_mois.cache_clear()
        with patch("utils.ciel_collectif._positions_instant", side_effect=positions), \
             patch("utils.ciel_collectif._paires", side_effect=paires):
            periodes = _periodes_aspects_mois(2026, 10)
        carre = next(p for p in periodes if p["titre"] == "Vénus carré Pluton")
        self.assertIsNone(carre["start"])
        self.assertTrue(carre["end"].startswith("2026-10-07"))
        self.assertEqual(len(carre["exacts"]), 1)
        self.assertAlmostEqual(
            abs((datetime.fromisoformat(carre["exacts"][0]) - datetime(2026, 10, 4, tzinfo=timezone.utc)).total_seconds()),
            0, delta=1,
        )
        _periodes_aspects_mois.cache_clear()

    def test_aspect_dissocie_exclu(self):
        self.assertIsNone(_aspect(29.8, 30.2))
        self.assertIsNone(_aspect(359.8, 0.2))
        self.assertEqual(_aspect(10, 70)[0], "sextile")

    def test_octobre_2026_sans_theme_natal(self):
        ciel = ciel_collectif_mois(2026, 10, jour_reference=date(2026, 10, 1))
        titres = {evenement["titre"] for evenement in ciel["evenements"]}
        self.assertIn("Mars opposition Pluton", titres)
        self.assertTrue(any("Pluton stationnaire" in titre for titre in titres))
        self.assertTrue(all(
            "Mercure" not in evenement["titre"] and "Lune" not in evenement["titre"]
            for evenement in ciel["temps_forts"]
        ))
        self.assertEqual(ciel["jour_reference"], date(2026, 10, 1))
        self.assertEqual(
            [groupe["date"] for groupe in ciel["groupes_dates"]],
            sorted({evenement["date"] for evenement in ciel["evenements"]}),
        )
        self.assertEqual(
            sum(len(groupe["evenements"]) for groupe in ciel["groupes_dates"]),
            len(ciel["evenements"]),
        )
        self.assertEqual(
            next(e for e in ciel["evenements"] if e["titre"] == "Mars opposition Pluton")["nature"],
            "tension",
        )
        self.assertEqual(
            next(e for e in ciel["evenements"] if e["titre"] == "Mars trigone Neptune")["nature"],
            "fluide",
        )
        self.assertEqual(
            next(e for e in ciel["evenements"] if e.get("station"))["nature"],
            "station",
        )

    def test_figures_et_mouvements_octobre_2026(self):
        figures = figures_ciel_collectif(date(2026, 10, 1))
        self.assertTrue(any(
            figure["nom"] == "T-carré" and set(figure["planetes"]) == {"Vénus", "Mars", "Pluton"}
            for figure in figures
        ))
        ciel = ciel_collectif_mois(2026, 10, jour_reference=date(2026, 10, 1))
        evenements = {(e["date"], e["titre"]) for e in ciel["evenements"]}
        self.assertIn((date(2026, 10, 3), "Vénus stationnaire, puis rétrograde"), evenements)
        self.assertIn((date(2026, 10, 24), "Mercure stationnaire, puis rétrograde"), evenements)
        self.assertIn((date(2026, 10, 25), "Vénus entre en Balance"), evenements)
        self.assertTrue(any(
            p["planete"] == "Vénus" and p["debut"] == date(2026, 10, 3) and p["apres_mois"]
            for p in ciel["retrogradations"]
        ))

    def test_grand_carre_et_diamant_sont_des_figures_completes(self):
        def aspect(a, b, nom):
            return {"premiere": a, "seconde": b, "aspect": nom}

        grand_carre = [
            aspect("Soleil", "Mars", "opposition"),
            aspect("Vénus", "Saturne", "opposition"),
            aspect("Soleil", "Vénus", "carré"),
            aspect("Soleil", "Saturne", "carré"),
            aspect("Mars", "Vénus", "carré"),
            aspect("Mars", "Saturne", "carré"),
        ]
        noms = [f["nom"] for f in _figures(grand_carre)]
        self.assertEqual(noms, ["Grand carré"])

        diamant = [
            aspect("Soleil", "Jupiter", "trigone"),
            aspect("Soleil", "Uranus", "trigone"),
            aspect("Jupiter", "Uranus", "trigone"),
            aspect("Mars", "Soleil", "opposition"),
            aspect("Mars", "Jupiter", "sextile"),
            aspect("Mars", "Uranus", "sextile"),
        ]
        noms = [f["nom"] for f in _figures(diamant)]
        self.assertEqual(noms, ["Diamant (cerf-volant)"])


if __name__ == "__main__":
    unittest.main()
