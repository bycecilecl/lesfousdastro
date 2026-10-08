import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from utils.revolution_solaire.outils_redaction_rs import rediger_etape_complete, BlocTronqueError

class ContinuationTest(unittest.TestCase):
    def test_plusieurs_limites_jusqua_la_fin_sans_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier=Path(tmp)
            appel=Mock(side_effect=[BlocTronqueError('Début. '), BlocTronqueError('Milieu. '), BlocTronqueError('Encore. '), 'Fin.'])
            t=rediger_etape_complete(dossier,'partie_1','MISSION',14000,appel)
            self.assertEqual(t,'Début. Milieu. Encore. Fin.')
            self.assertEqual([c.kwargs['max_tokens'] for c in appel.call_args_list],[14000,28000,28000,28000])
            self.assertIn('Début. Milieu.',appel.call_args_list[2].args[0])
            self.assertEqual(rediger_etape_complete(dossier,'partie_1','MISSION',14000,appel),t)
            self.assertEqual(appel.call_count,4)

    def test_reprise_apres_interruption_garde_tout_le_texte(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier=Path(tmp);appel=Mock(side_effect=[BlocTronqueError('Texte sauvegardé. '),RuntimeError('réseau')])
            with self.assertRaises(RuntimeError):rediger_etape_complete(dossier,'partie_2','MISSION',14000,appel)
            suite=Mock(return_value='Suite terminée.')
            self.assertEqual(rediger_etape_complete(dossier,'partie_2','MISSION',14000,suite),'Texte sauvegardé. Suite terminée.')
            self.assertIn('Texte sauvegardé.',suite.call_args.args[0])
            suite.assert_called_once()

    def test_synthese_peut_aussi_continuer(self):
        with tempfile.TemporaryDirectory() as tmp:
            appel=Mock(side_effect=[BlocTronqueError('Synthèse : '),'fin.'])
            self.assertEqual(rediger_etape_complete(Path(tmp),'synthese','MISSION',2400,appel),'Synthèse : fin.')
            self.assertEqual(appel.call_args.kwargs['max_tokens'],4800)
