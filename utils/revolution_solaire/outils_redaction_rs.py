"""Transport Claude et repères calculés du moteur RS validé."""
import os
import re
import time
import logging
from anthropic import APIConnectionError, RateLimitError, InternalServerError
from .plan_enjeux import construire_plan_chapitres
from .archives_generation import lire_json, ecrire_json
from utils.llm_client import ask_llm as appel_llm_standard
from utils.claude_llm import BlocTronqueError


def ask_llm(prompt, **options):
    if os.getenv('LLM_PROVIDER', 'claude').lower().strip() != 'claude':
        return appel_llm_standard(prompt, **options)
    from utils.claude_llm import CLIENT, MODEL
    options = dict(options)
    options.pop('retries', None)
    logger = logging.getLogger(__name__)
    for tentative in range(3):
        try:
            with CLIENT.messages.stream(model=MODEL, messages=[{'role':'user','content':prompt}], **options) as flux:
                reponse = flux.get_final_message()
            texte = ''.join(bloc.text for bloc in reponse.content if getattr(bloc, 'type', None) == 'text')
            logger.info('Claude RS stop_reason=%s input_tokens=%s output_tokens=%s',
                reponse.stop_reason, reponse.usage.input_tokens, reponse.usage.output_tokens)
            if reponse.stop_reason == 'max_tokens':
                raise BlocTronqueError(texte)
            if not texte.strip():
                raise ValueError('Claude a retourné une réponse vide.')
            return texte
        except (APIConnectionError, RateLimitError, InternalServerError):
            if tentative == 2:
                raise
            logger.warning('Claude RS indisponible temporairement : relance de cette partie (%s/3).', tentative+2)
            time.sleep(2 ** (tentative+1))


def catalogue_reperes(donnees):
    """Identifiants de faits calculés, sans plan par domaine transmis à Claude."""
    faits = []
    for chapitre in construire_plan_chapitres(donnees):
        for fait in reperes_chapitre(chapitre, donnees):
            if fait not in faits:
                faits.append(fait)
    return {f'R{i+1}': fait for i, fait in enumerate(faits)}


def reperes_chapitre(chapitre, donnees):
    """Au plus quatre faits sourcés, jamais de placement inféré du récit."""
    refs = chapitre['facteurs_a_developper']
    faits = []
    if 'ascendant_rs' in refs:
        asc = donnees.get('ascendant_rs') or {}
        if asc.get('signe'):
            faits.append('Ascendant RS : ' + asc['signe'])
    # Réserver de la place aux contacts natals qui fondent la personnalisation.
    for nom, fiche in (donnees.get('placements_rs') or {}).items():
        if any(ref.startswith(nom + ' RS :') for ref in refs) and fiche.get('signe') and fiche.get('maison'):
            faits.append(f"{nom} RS : {fiche['signe']}, maison {fiche['maison']} RS")
            if len(faits) >= 2:
                break
    for aspect in donnees.get('aspects_rs_natal') or []:
        label = f"{aspect.get('point_rs')} RS {aspect.get('aspect')} {aspect.get('point_natal')} natal"
        if label in refs and aspect.get('orbe') is not None:
            faits.append(label + f" (orbe {float(aspect['orbe']):.2f}°)")
            if len(faits) >= 4:
                break
    return faits


def inserer_reperes(texte, chapitres, donnees):
    catalogue = catalogue_reperes(donnees)
    resultat = []
    for section in re.split(r'(?=^## )', texte, flags=re.M):
        ids = []
        for marqueur in re.findall(r'<!-- REPERES: ([^>]*?) -->', section):
            ids.extend(re.findall(r'R\d+', marqueur))
        section = re.sub(r'<!-- REPERES: [^>]*? -->', '', section).rstrip()
        faits = list(dict.fromkeys(catalogue[i] for i in ids if i in catalogue))[:4]
        if faits:
            section += '\n\n> **Repères techniques calculés** — ' + ' ; '.join(faits) + '.\n'
        resultat.append(section)
    return '\n'.join(resultat)


def rediger_etape_complete(dossier, nom, prompt, limite, appel):
    """Continue les fragments tronqués et reprend le dernier fragment sauvegardé."""
    nom_cache = nom + '_continuation.json'
    sauvegarde = lire_json(dossier, nom_cache) or {'texte': '', 'termine': False, 'fragments': 0, 'limite': limite}
    while not sauvegarde['termine']:
        precedent = sauvegarde['texte']
        contenu = prompt
        if precedent:
            contenu += (
                '\n\nTEXTE DÉJÀ RÉDIGÉ POUR CETTE PARTIE — conservé par le programme :\n'
                + precedent
                + '\nFIN DU TEXTE CONSERVÉ.\n'
                'La réponse précédente a atteint sa limite de tokens. Poursuis exactement '
                'à partir de la dernière phrase, sans recommencer, sans recopier le texte, '
                'sans résumer ni ajouter de nouveau chapitre hors de la mission. '
                'Termine les éléments encore manquants de cette partie puis écris sa balise de fin. '
                'Retourne uniquement la suite ; le programme l’assemblera au texte conservé.')
        ecrire_json(dossier, 'etat.json', {'etape': nom, 'statut': 'continuation_automatique' if precedent else 'en_cours', 'fragments': sauvegarde['fragments']})
        ecrire_json(dossier, nom + '_fragment_' + str(sauvegarde['fragments']+1) + '_prompt.json', {'prompt': contenu})
        try:
            fragment = appel(contenu, max_tokens=sauvegarde['limite'], temperature=.65, retries=1,
                             stop_sequences=['<FIN_RAPPORT>', '<FIN_SYNTHESE>'])
            termine = True
        except BlocTronqueError as erreur:
            fragment = erreur.texte_partiel
            termine = False
        if not fragment or not fragment.strip():
            raise ValueError('Réponse vide : texte précédent conservé pour reprise.')
        # Ne pas retirer les blancs en bordure : une limite peut couper une phrase.
        texte = precedent + fragment if precedent else fragment
        sauvegarde = {'texte': texte, 'termine': termine,
                      'fragments': sauvegarde['fragments']+1,
                      'limite': min(28000, max(limite, sauvegarde['limite']*2))}
        ecrire_json(dossier, nom_cache, sauvegarde)
    return sauvegarde['texte']
