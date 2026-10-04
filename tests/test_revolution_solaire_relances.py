"""Une panne ponctuelle ne doit pas bloquer une RS payée."""
import unittest

from utils.revolution_solaire.relances import retenter


class RelancesRevolutionSolaireTest(unittest.TestCase):
    def test_relance_puis_livre_le_premier_resultat_valide(self):
        tentatives = []
        pauses = []

        def generer(numero):
            tentatives.append(numero)
            if numero < 3:
                raise RuntimeError("Claude indisponible")
            return "rapport complet"

        resultat = retenter(generer, pause=pauses.append)
        self.assertEqual(resultat, "rapport complet")
        self.assertEqual(tentatives, [1, 2, 3])
        self.assertEqual(pauses, [1, 2])

    def test_arrete_apres_trois_echecs(self):
        tentatives = []

        def generer(numero):
            tentatives.append(numero)
            raise RuntimeError("Claude indisponible")

        with self.assertRaises(RuntimeError):
            retenter(generer, pause=lambda _: None)
        self.assertEqual(tentatives, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
