"""Le ciel collectif ne dépend d'aucun thème natal."""

import unittest
from datetime import date

from utils.ciel_collectif import _aspect, ciel_collectif_mois


class TestCielCollectif(unittest.TestCase):
    def test_aspect_dissocie_exclu(self):
        self.assertIsNone(_aspect(29.8, 30.2))
        self.assertIsNone(_aspect(359.8, 0.2))
        self.assertEqual(_aspect(10, 70)[0], "sextile")

    def test_octobre_2026_sans_theme_natal(self):
        ciel = ciel_collectif_mois(2026, 10, jour_reference=date(2026, 10, 1))
        titres = {evenement["titre"] for evenement in ciel["evenements"]}
        self.assertIn("Mars opposition Pluton", titres)
        self.assertTrue(any("Pluton stationnaire" in titre for titre in titres))
        self.assertTrue(all("Mercure" not in titre and "Lune" not in titre for titre in titres))
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


if __name__ == "__main__":
    unittest.main()
