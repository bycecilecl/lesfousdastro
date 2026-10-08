import unittest

from utils.revolution_solaire.corrections_faits_rs import corriger_contacts_et_roles
from utils.revolution_solaire.plan_chapitres import construire_plan_chapitres


class PlanEtCorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.donnees = {
            'placements_rs': {'Mars': {'maison': 9}, 'Pluton': {'maison': 3},
                              'Vénus': {'maison': 12}, 'Saturne': {'maison': 5},
                              'Uranus': {'maison': 7}},
            'configurations_majeures_rs': [{
                'type': 't_carre', 'planetes': ['Mars', 'Pluton', 'Vénus'],
                'planete_focale': 'Vénus', 'planetes_en_opposition': ['Mars', 'Pluton'],
            }],
            'themes_prioritaires': [{'code': 'relation', 'libelle': 'Relations'},
                                    {'code': 'mobilite', 'libelle': 'Mobilité'}],
            'aspects_rs_natal': [
                {'point_rs': 'MC', 'point_natal': 'Vénus', 'aspect': 'conjonction', 'orbe': .2},
                {'point_rs': 'Vénus', 'point_natal': 'Vénus', 'aspect': 'sextile', 'orbe': .05},
            ],
            'profection_annuelle': {'ascendant_profecte': {'maison_rs': 9}},
        }

    def test_dynamiques_distinctes_et_pas_de_placement_invente(self):
        titres = [item['titre'] for item in construire_plan_chapitres(self.donnees)]
        self.assertTrue(any('carre' in titre for titre in titres))
        self.assertIn('Saturne RS en maison 5', titres)
        self.assertIn('Uranus RS en maison 7', titres)
        self.assertIn('Mobilité', titres)
        self.assertNotIn('Relations', titres)
        donnees = {**self.donnees, 'placements_rs': {'Mars': {'maison': 9}}}
        titres = [item['titre'] for item in construire_plan_chapitres(donnees)]
        self.assertNotIn('Uranus RS en maison 7', titres)

    def test_inversion_corrigee_sans_perdre_le_sextile_vrai(self):
        texte = ('Elle est au sextile de Vénus natale et en conjonction avec le MC natal : '
                 'cela touche sa visibilité.')
        corrige, audit = corriger_contacts_et_roles(texte, self.donnees)
        self.assertIn('sextile de Vénus natale', corrige)
        self.assertIn('le MC RS est conjoint à Vénus natale', corrige)
        self.assertNotIn('conjonction avec le MC natal', corrige)
        self.assertEqual(audit[0]['code'], 'contact_inverse_corrige')
        self.assertEqual(corriger_contacts_et_roles(corrige, self.donnees)[1], [])

    def test_role_t_carre_corrige_uniquement_si_figure_calculee(self):
        texte = 'T-carré Vénus apex M12 RS, opposée Mars–Pluton.'
        corrige, audit = corriger_contacts_et_roles(texte, self.donnees)
        self.assertIn('carrée à Mars et à Pluton', corrige)
        self.assertEqual(audit[-1]['code'], 'role_t_carre_corrige')
        sans_figure = {**self.donnees, 'configurations_majeures_rs': []}
        self.assertEqual(corriger_contacts_et_roles(texte, sans_figure), (texte, []))

    def test_maison_rs_de_profection_ne_devient_pas_natale(self):
        texte = "La profection annuelle arrive en maison 9 natale, dans le signe du Lion."
        corrige, audit = corriger_contacts_et_roles(texte, self.donnees)
        self.assertIn('maison 9 de RS', corrige)
        self.assertNotIn('maison 9 natale', corrige)
        self.assertEqual(audit[0]['code'], 'maison_profection_rs_corrigee')
        self.assertEqual(corriger_contacts_et_roles(corrige, self.donnees)[1], [])

    def test_positions_mc_et_maitrise_collective(self):
        donnees = {**self.donnees,
            'placements_rs': {**self.donnees['placements_rs'],
                'Soleil': {'maison': 3, 'maisons_gouvernees_rs': [10]},
                'Jupiter': {'maison': 10, 'maisons_gouvernees_rs': [3, 5]},
                'Pluton': {'maison': 4, 'maisons_gouvernees_rs': [2]},
                'Uranus': {'maison': 8, 'maisons_gouvernees_rs': [4]}},
            'points_angulaires_rs': [{'point': 'Pluton', 'angle': 'FC', 'orbe': 2.7}],
        }
        texte = ('## Travail : le Soleil au MC\n'
                 'Jupiter au sommet, rétrograde, occupe le MC.\n'
                 'Pluton au Fond du Ciel et Uranus en maison VIII, '
                 'tous deux gouverneurs de ta maison IV, dessinent un mouvement.\n'
                 'Saturne RS est au MC natal.')
        corrige, audit = corriger_contacts_et_roles(texte, donnees)
        self.assertIn('Soleil maître du MC RS', corrige)
        self.assertIn('Jupiter au sommet, rétrograde, occupe la maison 10 RS', corrige)
        self.assertIn('Pluton au Fond du Ciel et Uranus en maison VIII dessinent', corrige)
        self.assertIn('Saturne RS est au MC natal', corrige)
        self.assertEqual(len(audit), 3)

    def test_carre_natal_attribue_a_tort_au_theme_natal(self):
        donnees = {**self.donnees,
            'placements_natals_verifies': {'Jupiter': {'degre': 20}, 'Mars': {'degre': 236}},
            'aspects_rs_natal': self.donnees['aspects_rs_natal'] + [
                {'point_rs': 'Jupiter', 'point_natal': 'Mars', 'aspect': 'carré', 'orbe': .32}],
        }
        texte = ('Jupiter natal se trouve en Bélier en maison XII. '
                 'Il reçoit cette année un carré de Mars natal, réactivé par Jupiter RS.')
        corrige, audit = corriger_contacts_et_roles(texte, donnees)
        self.assertIn('Jupiter RS forme cette année un carré à Mars natal (0.32°).', corrige)
        self.assertEqual(audit[0]['code'], 'carre_natal_attribue_a_rs')


if __name__ == '__main__':
    unittest.main()
