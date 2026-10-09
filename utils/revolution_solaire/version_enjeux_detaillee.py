"""Essai local isolé : trois rédactions successives, puis synthèse personnelle.

Repart des calculs archivés pour comparer exactement les mêmes données à V1.
Aucune écriture dans les archives V1, aucun paiement ni envoi de mail.
"""
import json
import re
import time
import tempfile
from pathlib import Path
from .archives_generation import verrou_demande, ecrire_json, lire_json
from .plan_enjeux import construire_plan_chapitres
from .accords import genre_grammatical
from .prompt_synthese_contextuelle import construire_prompt_synthese_contextuelle, assembler_rapport
from .rapport_html import generer_rapport_html
from .rapport_pdf import habiller_rapport_pdf
from .controle_livraison import controler_placements
from .finalisation_v2 import finaliser_texte, titre_periode, MOIS
from .outils_redaction_rs import ask_llm, catalogue_reperes, inserer_reperes as reperes_enjeux, rediger_etape_complete
from utils.claude_llm import BlocTronqueError
from utils.pdf_utils import html_to_pdf

VERSION = "version_2_detaillee_enjeux_libres_2"


def chapitres_partie(preparation, numero):
    return []


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
    return reperes_enjeux(texte, chapitres, donnees)


CONSIGNES_PRIORITAIRES = """
⚠ INTERDICTION DE RÉUTILISER LES MÊMES FORMULATIONS
Relis les parties précédentes fournies avant de rédiger.
Ne reprends aucune phrase, image ou exemple déjà utilisé.
Changer les mots ne suffit pas : si l’idée a déjà été développée,
ajoute une nuance réellement nouvelle ou ne la répète pas.

⚠ OBLIGATION DE VÉRIFIER LES DONNÉES AVANT DE LES ÉNONCER
Avant de citer un placement, une maîtrise, un aspect ou une date,
vérifie qu’il correspond exactement aux données calculées fournies.
Vérifie les deux objets concernés et leur référentiel : RS, natal ou transit.
Le texte des parties précédentes ne constitue jamais une preuve.
Si une information est absente ou ambiguë, ne l’affirme pas.
"""


FIABILITE = """
- Seuls les inventaires calculés font foi. N'invente et ne recalcule aucun aspect,
  aucune date ni aucun orbe. Une absence ne devient pas un « aspect symbolique ».
- Un aspect ne se transmet pas par une troisième planète. Même signe ou même maison
  ne signifie pas conjonction. Deux planètes conjointes peuvent avoir des signes distincts.
- Une planète RS et une planète natale sont des positions fixes. Pour les périodes,
  le sujet mobile est toujours nommé « en transit », jamais « RS » ou « natal ».
  La cible garde son référentiel fourni. N'attribue pas au mobile la maison de sa position natale ou RS.
- Une maîtrise par interception est celle du signe intercepté : la planète maîtresse ne devient pas elle-même interceptée.
- Une superposition RS–natal n'est ni une position natale ni une dignité. Ne dis
  jamais « chute en maison ». Ne transforme pas une maîtrise interceptée en maîtrise de cuspide.
- Chiron, Nœuds, Lune Noire et Part de Fortune ne gouvernent aucune maison.
- Le maître de l'année est exclusivement celui de la profection. Les maîtres de
  l'Ascendant RS ne portent pas ce titre. N'interprète pas les aspects Soleil RS–natal.
- Préserve les liens natals distincts et utiles, les interceptions fournies, les
  conjonctions angulaires et les tensions des luminaires ; regroupe leurs conséquences
  communes. Les points symboliques confirment une lecture, sans remplacer ses facteurs majeurs.
- Pour les placements conjoints ou regroupés, conserve la maison de chaque planète distincte. Un aspect au Descendant ne devient jamais un aspect à une planète qui occupe la maison VII.
- Le texte antérieur n'est pas une source de faits : en cas de divergence, les calculs
  font autorité. Ne propage pas une erreur de la mémoire.
- Aucun événement garanti, aucune cause psychologique inventée, aucune obligation
  de rupture ou de sacrifice, aucune prédiction de maladie, décès ou résultat financier.
"""


def prompt_partie(preparation, demande, numero, precedent):
    chapitres = chapitres_partie(preparation, numero)
    # L'ouverture reçoit moins de place que les domaines : il ne s'agit pas d'un
    # catalogue de positions, les mêmes planètes seront interprétées dans leur domaine.
    cadre = """
PLAN LIBRE PAR ENJEUX, SANS CHAPITRES OBLIGATOIRES PAR DOMAINE DE VIE.
Choisis les enjeux qui ressortent vraiment du thème et crée tes propres titres ##.
Relie dans un même enjeu les domaines touchés par une même configuration ; ne la
réinterprète pas séparément sous des rubriques travail, argent, couple ou foyer.
La liberté concerne l'organisation, PAS la suppression des fondements astrologiques.
Développe les configurations majeures fournies, leurs tensions et ressources, les
angles marquants, l'Ascendant et son ou ses maîtres, les luminaires, la profection,
les interceptions pertinentes et surtout les contacts au natal qui personnalisent
la lecture. Ces facteurs peuvent être réunis : aucun ne demande automatiquement
son propre chapitre. Précise leurs interactions, les contradictions et les exemples
concrets, sans remplacer leur profondeur par des conseils génériques.
Avant de rédiger, vérifie dans les données quels facteurs sont réellement centraux.
Après chaque titre d'enjeu, choisis 2 à 4 identifiants de faits qui le fondent dans
un marqueur invisible <!-- REPERES: R1,R2 -->. Les libellés seront ajoutés par le code.
N'invente aucun identifiant. CATALOGUE :
""" + json.dumps(catalogue_reperes(preparation['donnees']), ensure_ascii=False)
    if numero == 1:
        mission = cadre + "\nOuvre obligatoirement par le signe de l’Ascendant RS fourni dans les données : nomme-le et interprète ce qu’il colore dans l’année à venir (posture, manière d’aborder les expériences et dynamique personnelle). Relie ensuite cette orientation à son maître ou ses maîtres, leurs placements et leurs aspects calculés. La seule mention dans les repères techniques ne suffit pas ; un aspect à l’Ascendant ne remplace pas l’interprétation de son signe. Poursuis avec les deux ou trois enjeux les plus structurants. Réserve les autres enjeux marquants à la partie suivante, sans faire de résumé final."
    elif numero == 2:
        mission = cadre + "\nLis les enjeux déjà développés dans la mémoire. Rédige seulement les autres enjeux réellement marquants et leurs liens natals distincts. Vérifie les facteurs essentiels encore absents ; développe-les ici sans refaire les premiers chapitres. Ne crée aucun chapitre pour remplir un domaine secondaire."
    else:
        mission = "Rédige les grandes périodes d'activation par les transits calculés, au maximum cinq. Utilise des titres naturels comme « Fin février – début mars 2027 », avec l'année, sans dates précises en titres. Pour chacune : ce qui s'active spécifiquement, ce qui change et un exemple inédit. Préserve la cible RS ou natale de chaque transit. Ne réexplique pas les enjeux annuels. Aucun inventaire de planètes."
    if numero < 3:
        mission += "\nDéveloppe uniquement les enjeux annuels. Ne rédige aucune chronologie, aucun aperçu des temps forts, aucun chapitre de périodes et ne cite aucune date de transit. Les périodes seront traitées exclusivement dans la partie 3."
    else:
        mission += "\nTu es la seule partie chargée de la chronologie. Développe au maximum cinq grandes périodes, chacune une seule fois. Commence directement par la première période, sans introduction ni aperçu récapitulant les cinq périodes."
    budget = '1 650 à 1 900 mots AU TOTAL pour cette partie, tous ses chapitres réunis' if numero < 3 else '200 à 250 mots par période, 1 250 mots au maximum pour toute cette partie'
    donnees = preparation['prompt'].split('RELEVÉ TECHNIQUE CALCULÉ — source astrologique unique', 1)[-1]
    donnees = donnees.split('PLAN DES CHAPITRES CALCULÉ', 1)[0]
    return f"""Tu rédiges la partie {numero}/3 d'une révolution solaire {demande['annee']}.
Tutoiement ; accords : {genre_grammatical(demande['personne'].get('genre', ''))}.
{CONSIGNES_PRIORITAIRES}
{mission}
{'Commence par # Ta révolution solaire ' + str(demande['annee']) if numero == 1 else 'Commence directement par le prochain intertitre ##.'}
BUDGET ÉDITORIAL : {budget}. Le rapport entier, encadrés et synthèse compris,
vise 5 000 à 6 000 mots. Ce budget n'est PAS à appliquer à chaque chapitre.
Ne remplis pas pour atteindre le minimum. L'ouverture fait 150 à 200 mots maximum.
Deux exemples concrets réellement différents au maximum par enjeu.
Ne rédige pas de listes de toutes les manifestations possibles.

PROFONDEUR ET CONCISION
Une explication par enjeu : regroupe les facteurs convergents au lieu d'interpréter
chaque aspect séparément. Conserve les liens natals qui personnalisent réellement
la lecture, leurs nuances et contradictions. Supprime les définitions scolaires,
les synonymes en chaîne, les listes de mots-clés et les résumés de ce qui précède.
Le récit explique ce que ces dynamiques peuvent faire vivre. Les noms des planètes
peuvent servir de repère, mais n'énumère dans le récit ni placements en signes ou maisons,
ni degrés, orbes, maîtrises ou listes d'aspects. Le code ajoutera les encadrés techniques
à partir des calculs : ne rédige AUCUN encadré technique toi-même.
Garde une voix directe, chaleureuse, vivante, avec un peu d'humour ; pas de sermon
sur le lâcher-prise, le mérite, les sacrifices ou la nécessité de souffrir pour grandir.
Tu ne connais pas le contexte personnel. Pas de biographie inventée.

FIABILITÉ
{FIABILITE}

MÉMOIRE DES PARTIES PRÉCÉDENTES — à consulter, pas à recopier :
{precedent or '(Première partie : aucun texte antérieur.)'}
FIN DE LA MÉMOIRE.
Pour chaque sujet déjà traité, ajoute seulement une nuance distincte ou omets-le.
Ne dis pas « comme expliqué précédemment » pour réexpliquer ensuite la même chose.
Les périodes ne reprennent ni les définitions, ni les scénarios annuels.
Évite les amorces automatiques « Tu pourrais », « Ce qui se construit », « Tu ne peux pas ».
Ne rédige pas de synthèse personnelle ni de conclusion. Termine par <FIN_RAPPORT>.

DONNÉES CALCULÉES — source technique, pas liste à commenter intégralement :
{donnees}
"""


def normaliser_titres_periodes(texte, debut_cycle):
    debut = str(debut_cycle).split('-')
    annee, mois_cycle = int(debut[0]), int(debut[1])
    def remplacer(m):
        dates, suffixe = m[1].strip(), m[2] or ''
        if not re.search(r'\b\d{4}\b', dates):
            mois = next((i+1 for i, nom in enumerate(MOIS) if re.search(r'\b'+nom+r'\b', dates)), None)
            if mois is None:
                return m[0]
            dates += ' ' + str(annee + (mois < mois_cycle))
        lisible = titre_periode(dates)
        return '## ' + lisible + suffixe
    return re.sub(r'^## (\d{1,2}(?:er)?[^\n:]*?)(\s*:[^\n]*)?$', remplacer, texte, flags=re.M)


def generer_version_2(source, racine):
    source = Path(source)
    demande = lire_json(source, 'demande.json')
    preparation = lire_json(source, 'preparation.json')
    if not demande or not preparation:
        raise ValueError('Les calculs et la demande source sont nécessaires.')
    with verrou_demande({'version': VERSION, 'source': source.name}, racine) as dossier:
        if not (dossier / 'source.json').exists():
            ecrire_json(dossier, 'source.json', {'demande': demande, 'preparation': preparation})
        snapshot = lire_json(dossier, 'source.json')
        demande, preparation = snapshot['demande'], snapshot['preparation']
        def etape(nom, prompt, limite):
            cache = lire_json(dossier, nom + '.json')
            if cache:
                return cache['texte']
            ecrire_json(dossier, nom + '_prompt.json', {'prompt': prompt})
            ecrire_json(dossier, 'etat.json', {'etape': nom, 'statut': 'en_cours'})
            debut = time.monotonic()
            try:
                texte = rediger_etape_complete(dossier, nom, prompt, limite, ask_llm)
            except Exception as erreur:
                ecrire_json(dossier, 'etat.json', {'etape': nom, 'statut': 'a_reprendre', 'erreur': type(erreur).__name__})
                raise
            ecrire_json(dossier, nom + '.json', {'texte': texte, 'secondes': round(time.monotonic()-debut, 2)})
            return texte
        parties = []
        for numero in range(1, 4):
            parties.append(etape(f'partie_{numero}', prompt_partie(preparation, demande, numero, '\n\n'.join(parties)), 14000))
        corps = '\n\n'.join(parties)
        synthese = etape('synthese', construire_prompt_synthese_contextuelle(
            corps, demande.get('contexte_client'), demande['personne'].get('genre', ''))
            + '\n' + CONSIGNES_PRIORITAIRES
            + '\nCONSIGNE FINALE : 400 à 500 mots pour toute la synthèse. Réponds au contexte personnel sans résumer les chapitres ou les périodes. N’énumère aucun placement, degré, orbe ou aspect technique. Aucun déterminisme ni mécanisme personnel inventé.', 2400)
        corps_avec_reperes = '\n\n'.join(inserer_reperes(partie,
            chapitres_partie(preparation, i), preparation['donnees'])
            for i, partie in enumerate(parties, 1))
        texte = assembler_rapport(corps_avec_reperes, synthese)
        texte = normaliser_titres_periodes(texte, preparation.get('debut_cycle') or str(demande['annee'])+'-01-01')
        texte, finalisation = finaliser_texte(texte, preparation['donnees'])
        ecrire_json(dossier, 'finalisation.json', finalisation)
        ecrire_json(dossier, 'longueur.json', {
            'mots_par_partie': [len(p.split()) for p in parties],
            'mots_synthese': len(synthese.split()), 'mots_total': len(texte.split()),
            'objectif': [5000, 6000], 'depassement': len(texte.split()) > 6000,
            'bloquant': False})
        controle = controler_placements(texte, preparation['donnees'])
        controle['bloquant'] = False
        ecrire_json(dossier, 'controle.json', controle)
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_rapport_html(texte, Path(tmp)/'rapport.html',
                nom=demande['personne']['nom'], annee=demande['annee'])
            html = chemin.read_text()
        ecrire_json(dossier, 'rapport.json', {'texte_markdown': texte, 'html': html})
        pdf = dossier/'rapport.pdf'
        if not pdf.exists() or finalisation:
            habille = habiller_rapport_pdf(html, personne=demande['personne'], lieu_rs=demande['lieu_rs'], annee=demande['annee'])
            if not html_to_pdf(habille, str(pdf)) or not pdf.exists() or not pdf.stat().st_size:
                pdf.unlink(missing_ok=True)
                raise RuntimeError('PDF indisponible ; texte conservé, reprends le même essai.')
        ecrire_json(dossier, 'etat.json', {'statut': 'termine'})
        return dossier
