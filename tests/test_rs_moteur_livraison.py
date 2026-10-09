"""Moteur validé dans le parcours payé : reprises, PDF privé et mail singulier."""
import ast
import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from flask import Flask
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-test')
import test_revolution_solaire_vente as vente
from utils.revolution_solaire import service, version_archive_enjeux as moteur
from utils.revolution_solaire.archives_generation import ecrire_json
from utils.revolution_solaire.outils_redaction_rs import BlocTronqueError

class LivraisonMoteurValideTest(unittest.TestCase):
    def test_reprise_parties_pdf_stockage_et_cache_sans_v1(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            app = Flask(__name__, instance_path=tmp)
            stack.enter_context(app.app_context())
            def preparer(*, dossier, **kwargs):
                assert kwargs['preparation_seule']
                preparation={'donnees':{},'prompt':'RELEVÉ TECHNIQUE CALCULÉ — source astrologique unique\nDONNEES\nPLAN DES CHAPITRES CALCULÉ',
                    'transits_directeurs':[], 'activations_datees':[], 'releve_technique':'Faits calculés','debut_cycle':'2014-10-11','fin_cycle':'2015-10-11'}
                ecrire_json(dossier,'preparation.json',preparation)
                return preparation
            stack.enter_context(patch.object(service,'_generer_rapport_revolution_solaire',side_effect=preparer))
            v1=stack.enter_context(patch.object(service,'ask_claude',side_effect=AssertionError('V1 interdite')))
            llm=stack.enter_context(patch.object(moteur,'ask_llm',side_effect=[
                BlocTronqueError('# Ta révolution solaire 2014\n\n## Premier enjeu\nLecture. '), 'Suite conservée.', RuntimeError('Connexion interrompue'),
                'Synthèse personnelle.']))
            def pdf(html,path,**kwargs):
                Path(path).write_bytes(b'%PDF-test');return True
            stack.enter_context(patch.object(moteur,'html_to_pdf',side_effect=pdf))
            stack.enter_context(patch.object(vente.module,'private_pdf_path',return_value=str(Path(tmp)/'prive.pdf')))
            stack.enter_context(patch.object(vente.module,'html_to_pdf',side_effect=pdf))
            upload=stack.enter_context(patch.object(vente.module,'upload_client_pdf',return_value='https://example.invalid/pdf-prive'))
            stack.enter_context(patch('utils.revolution_solaire.relances.sleep'))
            resultat=vente.module.generer_revolution_solaire_pdf_s3(vente.donnees_valides(),commande_id='commande-test-payee')
            self.assertEqual(llm.call_count,4)
            v1.assert_not_called()
            self.assertIn('Après le socle obligatoire',llm.call_args_list[0].args[0])
            self.assertIn('Lecture.',llm.call_args_list[1].args[0])
            self.assertEqual([c.kwargs['max_tokens'] for c in llm.call_args_list[:2]], [14000, 28000])
            self.assertIn('Suite conservée.',resultat['rapport_html'])
            self.assertNotIn('Question relationnelle',llm.call_args_list[0].args[0])
            self.assertIn('Question relationnelle',llm.call_args_list[-1].args[0])
            self.assertIn('Lecture.',resultat['rapport_html'])
            self.assertIn('Synthèse personnelle',resultat['rapport_html'])
            self.assertEqual(resultat['product_id'],'revolution_solaire')
            upload.assert_called_once()
            vente.module.generer_revolution_solaire_pdf_s3(vente.donnees_valides(),commande_id='commande-test-payee')
            self.assertEqual(llm.call_count,4)

    def test_mail_analyse_seule_singulier_et_pack_inchange(self):
        path=Path(__file__).resolve().parents[1]/'routes/checkout.py'
        tree=ast.parse(path.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='envoyer_email_pack_termine')
        envoi=Mock(return_value=True)
        app=Flask(__name__)
        ns={'current_app':app,'duree_validite_lien_pdf':lambda:'7 jours','envoyer_email_avec_analyse':envoi}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
        rs={'product_id':'revolution_solaire','label':'Ma Révolution Solaire','pdf_url':'https://example.invalid/pdf'}
        for produit in ('revolution_solaire', 'flash_astral', 'profil_amoureux', 'analyse_karmique', 'transits'):
            with self.subTest(produit=produit):
                analyse = dict(rs, product_id=produit)
                ns['envoyer_email_pack_termine']({'email':'test@example.invalid','nom':'Camille'},[analyse])
                message=envoi.call_args.kwargs
                self.assertEqual(message['sujet'], 'Ton analyse astrologique est prête ✨')
                for cle in ('contenu_txt','contenu_html'):
                    self.assertIn('Voici ton analyse',message[cle])
                    self.assertNotIn('Tes analyses',message[cle])
                    self.assertIn('Télécharge le PDF',message[cle])
        ns['envoyer_email_pack_termine']({'email':'test@example.invalid'},[rs,{'product_id':'flash_astral'}])
        self.assertIn('Tes analyses sont prêtes',envoi.call_args.kwargs['contenu_txt'])
        self.assertIn('Tes analyses astrologiques',envoi.call_args.kwargs['sujet'])
