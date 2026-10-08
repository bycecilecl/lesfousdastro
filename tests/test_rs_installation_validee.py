import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import httpx
from anthropic import APIConnectionError, BadRequestError
from utils.revolution_solaire import outils_redaction_rs as outils
from utils.revolution_solaire import version_enjeux_detaillee as moteur
from utils import claude_llm

class InstallationValideeTest(unittest.TestCase):
    def response(self):
        return SimpleNamespace(content=[SimpleNamespace(type='text',text='Texte complet')],
            stop_reason='stop_sequence',usage=SimpleNamespace(input_tokens=1,output_tokens=2))

    def test_streaming_et_relance_connexion_sans_reponse_complete(self):
        client=MagicMock()
        flux=MagicMock();flux.__enter__.return_value.get_final_message.return_value=self.response()
        client.messages.stream.side_effect=[APIConnectionError(request=httpx.Request('POST','https://example.invalid')), flux]
        with patch.dict('os.environ',{'LLM_PROVIDER':'claude'}),patch.object(claude_llm,'CLIENT',client),patch.object(outils.time,'sleep'):
            self.assertEqual(outils.ask_llm('prompt',max_tokens=28000,retries=1),'Texte complet')
        self.assertEqual(client.messages.stream.call_count,2)
        client.messages.create.assert_not_called()
        self.assertEqual(client.messages.stream.call_args.kwargs['max_tokens'],28000)

    def test_erreur_configuration_pas_de_boucle_infinie(self):
        client=MagicMock()
        client.messages.stream.side_effect=BadRequestError('paramètre invalide',response=httpx.Response(400,request=httpx.Request('POST','https://example.invalid')),body={})
        with patch.dict('os.environ',{'LLM_PROVIDER':'claude'}),patch.object(claude_llm,'CLIENT',client):
            with self.assertRaises(BadRequestError):outils.ask_llm('prompt',max_tokens=14000)
        self.assertEqual(client.messages.stream.call_count,1)

    def test_troncature_conserve_le_texte_pour_la_relance_du_moteur(self):
        client=MagicMock();r=self.response();r.stop_reason='max_tokens'
        client.messages.stream.return_value.__enter__.return_value.get_final_message.return_value=r
        with patch.dict('os.environ',{'LLM_PROVIDER':'claude'}),patch.object(claude_llm,'CLIENT',client):
            with self.assertRaises(outils.BlocTronqueError) as erreur:outils.ask_llm('prompt',max_tokens=14000)
        self.assertEqual(erreur.exception.texte_partiel,'Texte complet')

    def test_periodes_sans_annee_sans_sous_titre_et_cycle_decale(self):
        texte='## 27 février – 5 mars\nLecture.\n## 1er – 7 mai : soutien\nSuite.'
        t=moteur.normaliser_titres_periodes(texte,'2027-01-03')
        self.assertIn('## Fin février – début mars 2027',t)
        self.assertIn('## Début mai 2027 : soutien',t)
        self.assertEqual(moteur.normaliser_titres_periodes('## 1er – 7 mai','2026-10-11'),'## Début mai 2027')
        self.assertEqual(moteur.normaliser_titres_periodes(t,'2027-01-03'),t)

    def test_identifiants_reperes_inconnus_jamais_affiches(self):
        texte='## Enjeu\n<!-- REPERES: R999 -->\nLecture.'
        self.assertEqual(outils.inserer_reperes(texte,[],{}).strip(),'## Enjeu\n\nLecture.')
