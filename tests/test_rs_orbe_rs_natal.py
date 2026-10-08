import inspect
import unittest

from utils.revolution_solaire.donnees_techniques import (
    _aspects_rs_natal,
    extraire_donnees_revolution_solaire,
)


class OrbeRsNatalTest(unittest.TestCase):
    def test_carre_saturne_rs_soleil_natal_a_quatre_degres(self):
        rs = {'planetes': {'Saturne': {'degre': 8.41283557056}}}
        natal = {'planetes': {'Soleil': {'degre': 282.40271426751}}}
        aspect = {'point_rs': 'Saturne', 'point_natal': 'Soleil',
                  'aspect': 'carré', 'orbe': 3.99}
        self.assertIn(aspect, _aspects_rs_natal(rs, natal, 6.0, 6.0))
        self.assertNotIn(aspect, _aspects_rs_natal(rs, natal, 3.0, 4.0))

    def test_seuils_par_defaut(self):
        params = inspect.signature(extraire_donnees_revolution_solaire).parameters
        self.assertEqual(params['orbe_rs_natal'].default, 6.0)
        self.assertEqual(params['orbe_rs_natal_angles'].default, 6.0)


if __name__ == '__main__':
    unittest.main()
