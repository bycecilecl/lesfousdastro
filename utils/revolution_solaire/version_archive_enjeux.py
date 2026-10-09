"""Essai local du rendu pré-V2 : un corps neutre, puis synthèse personnelle.
Les contradictions sont archivées sans suspendre la sortie ; les fragments tronqués sont continués.
"""
from pathlib import Path
import tempfile
from .archives_generation import verrou_demande, lire_json, ecrire_json
from .prompt_archive_enjeux import construire_prompt_rapport_complet
from .synthese_archive_enjeux import construire_prompt_synthese_contextuelle, assembler_rapport
from .outils_redaction_rs import ask_llm, rediger_etape_complete
from .controle_livraison import controler_placements
from .rapport_html import generer_rapport_html
from .rapport_pdf import habiller_rapport_pdf
from .version_enjeux_detaillee import normaliser_titres_periodes
from utils.pdf_utils import html_to_pdf

VERSION = 'rendu_archive_enjeux_dominants_2'

def generer_version_2(source, racine):
    source = Path(source)
    demande, preparation = lire_json(source, 'demande.json'), lire_json(source, 'preparation.json')
    if not demande or not preparation:
        raise ValueError('Demande et calculs nécessaires.')
    with verrou_demande({'version': VERSION, 'source': source.name}, racine) as dossier:
        snapshot = lire_json(dossier, 'source.json')
        if snapshot is None:
            snapshot = {'demande': demande, 'preparation': preparation}
            ecrire_json(dossier, 'source.json', snapshot)
        demande, preparation = snapshot['demande'], snapshot['preparation']
        def etape(nom, prompt, limite):
            cache = lire_json(dossier, nom + '.json')
            if cache:
                return cache['texte']
            ecrire_json(dossier, nom + '_prompt.json', {'prompt': prompt})
            texte = rediger_etape_complete(dossier, nom, prompt, limite, ask_llm)
            ecrire_json(dossier, nom + '.json', {'texte': texte})
            return texte
        donnees = preparation['donnees']
        prompt = construire_prompt_rapport_complet(
            donnees, preparation['transits_directeurs'],
            nom=demande['personne']['nom'], genre=demande['personne'].get('genre', ''),
            annee=demande['annee'], debut_transits=preparation['debut_cycle'],
            fin_transits=preparation['fin_cycle'], synthese_interne='',
            releve_technique=preparation['releve_technique'],
            themes_prioritaires=donnees.get('themes_prioritaires'),
            activations_calculees=preparation.get('activations_datees'))
        corps = etape('corps_neutre', prompt, 14000)
        synthese = etape('synthese', construire_prompt_synthese_contextuelle(
            corps, demande.get('contexte_client'), demande['personne'].get('genre', '')), 1600)
        texte = assembler_rapport(corps, synthese)
        texte = normaliser_titres_periodes(texte, preparation['debut_cycle'])
        controle = controler_placements(texte, donnees)
        controle['bloquant'] = False
        ecrire_json(dossier, 'controle.json', controle)
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_rapport_html(texte, Path(tmp)/'rapport.html', nom=demande['personne']['nom'], annee=demande['annee'])
            html = chemin.read_text()
        ecrire_json(dossier, 'rapport.json', {'texte_markdown': texte, 'html': html})
        pdf = dossier/'rapport.pdf'
        if not pdf.exists():
            habille = habiller_rapport_pdf(html, personne=demande['personne'], lieu_rs=demande['lieu_rs'], annee=demande['annee'])
            if not html_to_pdf(habille, str(pdf)) or not pdf.exists() or not pdf.stat().st_size:
                pdf.unlink(missing_ok=True)
                raise RuntimeError('PDF indisponible ; texte conservé pour reprise.')
        ecrire_json(dossier, 'etat.json', {'statut': 'termine'})
        return dossier
