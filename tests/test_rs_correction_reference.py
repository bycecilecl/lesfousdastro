"""Une confusion explicite de référentiel ne doit pas bloquer une RS payée."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.revolution_solaire.controle_livraison import (
    controler_placements, corriger_references_maitrises,
)

os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-test')
from utils.revolution_solaire import service


class CorrectionReferenceMaitriseTest(unittest.TestCase):
    def setUp(self):
        self.texte = (
            "Mercure gouverne aussi la maison XI natale : les projets collectifs "
            "et les alliances deviennent importants."
        )
        self.donnees = {
            'placements_rs': {
                'Mercure': {
                    'maisons_gouvernees_rs': [9, 11],
                    'maisons_gouvernees_interceptees_rs': [],
                    'maisons_gouvernees_natales': [1, 5],
                    'maisons_gouvernees_interceptees_natales': [],
                },
            },
        }

    def test_corrige_uniquement_le_referentiel_prouve(self):
        avant = controler_placements(self.texte, self.donnees)
        self.assertEqual([e['code'] for e in avant['erreurs']], ['maitrise_contradictoire'])

        texte, corrections = corriger_references_maitrises(
            self.texte, self.donnees, avant['erreurs'])

        self.assertEqual(len(corrections), 1)
        self.assertEqual(
            texte,
            self.texte.replace('maison XI natale', 'maison XI de révolution solaire'),
        )
        self.assertEqual(controler_placements(texte, self.donnees)['erreurs'], [])

    def test_ne_corrige_pas_si_la_maitrise_rs_n_est_pas_etablie(self):
        donnees = {'placements_rs': {'Mercure': {
            **self.donnees['placements_rs']['Mercure'], 'maisons_gouvernees_rs': [9],
        }}}
        erreurs = controler_placements(self.texte, donnees)['erreurs']
        texte, corrections = corriger_references_maitrises(self.texte, donnees, erreurs)
        self.assertEqual((texte, corrections), (self.texte, []))

    def test_ne_corrige_pas_une_formulation_ambigue(self):
        texte = self.texte.replace('maison XI natale', 'maisons XI et XII natales')
        erreurs = [{'code': 'maitrise_contradictoire', 'reference': 'natales',
                    'point': 'Mercure', 'annonce': 11, 'extrait': texte}]
        self.assertEqual(corriger_references_maitrises(texte, self.donnees, erreurs),
                         (texte, []))

    def test_rapport_archive_corrige_sans_nouvel_appel_ia(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = Path(temporaire)
            preparation = {
                'donnees': self.donnees, 'transits_directeurs': [],
                'releve_technique': '', 'debut_cycle': '2026-10-11',
                'fin_cycle': '2027-10-11', 'prompt': 'Déjà envoyé',
                'parametres': {'max_tokens': 14000, 'temperature': 0.65,
                               'stop_sequences': ['<FIN_RAPPORT>']},
            }
            (dossier / 'preparation.json').write_text(json.dumps(preparation))
            (dossier / 'reponse.json').write_text(json.dumps({'texte': self.texte}))

            with patch.object(service, 'ask_claude', side_effect=AssertionError('Nouvel appel IA')) as ia, \
                    patch.object(service, 'verifier_rapport_revolution_solaire', return_value='OK'):
                rapport = service._generer_rapport_revolution_solaire(
                    dossier=dossier, personne={'nom': 'Test'}, lieu_rs={'lieu': 'Paris'},
                    annee=2026,
                )

            ia.assert_not_called()
            self.assertIn('maison XI de révolution solaire', rapport.texte_markdown)
            self.assertNotIn('maison XI natale', rapport.texte_markdown)
            self.assertTrue(rapport.html)
            self.assertEqual(json.loads((dossier / 'controle.json').read_text())['erreurs'], [])
            self.assertEqual(len(json.loads((dossier / 'corrections_factuelles.json').read_text())), 1)


if __name__ == '__main__':
    unittest.main()
