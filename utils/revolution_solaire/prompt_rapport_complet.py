"""Prompt du corps neutre d'un rapport de révolution solaire."""

from __future__ import annotations

import json
from copy import deepcopy

from .presentation import traduire_pour_affichage
from .accords import genre_grammatical
from .prompt_points_symboliques import extraire_points_symboliques
from .plan_enjeux import construire_plan_chapitres


def _nommer_superpositions_rs(valeur):
    """Évite de présenter la maison natale traversée par un point RS comme
    la maison de ce point dans le thème natal."""
    if isinstance(valeur, list):
        return [_nommer_superpositions_rs(item) for item in valeur]
    if not isinstance(valeur, dict):
        return valeur
    resultat = {}
    for cle, contenu in valeur.items():
        cle_affichee = "maison_RS_dans_theme_natal" if cle == "maison_natale" else cle
        resultat[cle_affichee] = _nommer_superpositions_rs(contenu)
    return resultat


def construire_prompt_rapport_complet(
    donnees: dict,
    transits_directeurs: list[dict],
    *,
    nom: str,
    genre: str = "",
    annee: int,
    debut_transits: str,
    fin_transits: str,
    synthese_interne: str,
    releve_technique: str = "",
    themes_prioritaires: list[dict] | None = None,
    activations_calculees: list[dict] | None = None,
) -> str:
    """Construit le corps astrologique sans exposer le contexte personnel."""
    transits_json = json.dumps(traduire_pour_affichage(transits_directeurs), ensure_ascii=False, separators=(",", ":"))
    themes_prioritaires_json = json.dumps(themes_prioritaires or [], ensure_ascii=False, separators=(",", ":"))
    activations_json = json.dumps(activations_calculees or [], ensure_ascii=False, separators=(",", ":"))
    plan_chapitres_json = json.dumps(construire_plan_chapitres(donnees), ensure_ascii=False, separators=(",", ":"))
    accord = genre_grammatical(genre)
    return f"""Tu rédiges le corps astrologique d'une révolution solaire pour {nom}, année {annee}, en français et au tutoiement. Accord grammatical demandé : {accord}. Si l'accord est précisé, accorde tous les adjectifs et participes en conséquence, sans point médian ni double forme (par exemple « prêt » au masculin, « prête » au féminin). Tu ne connais pas la situation personnelle de cette personne : interprète les configurations sans inventer sa biographie.

Titre obligatoire :
# Ta révolution solaire {annee}

Tu écris pour une personne qui veut se reconnaître dans ce qu'elle lit, comprendre son année et avoir plaisir à avancer dans le texte. Le rapport est une narration astrologique, pas une suite de fiches techniques. Il doit faire sentir un fil conducteur, les contradictions réelles et les moments où l'année change de rythme.

STRUCTURE
- Suis le PLAN DES CHAPITRES CALCULÉ ci-dessous : chaque entrée reçoit son propre intertitre `##` et un développement utile avant les périodes. Le plan décrit des facteurs vérifiés, pas des événements garantis. Traite chaque dynamique sous son angle propre ; ne fusionne pas deux entrées pour raccourcir. Les facteurs_a_developper désignent le seul chapitre où chaque facteur reçoit son interprétation complète. Ces libellés renvoient aux faits du relevé ; ne les affiche pas comme une liste. N'écris jamais un bloc de plus de quatre paragraphes sans intertitre.
- Le premier développement s'ouvre obligatoirement sur l'Ascendant RS : son signe, son ou ses maîtres et leur placement. C'est le point d'entrée du récit annuel. Développe ensuite les angles, les figures, les maisons chargées, les luminaires, les maisons gouvernées, Saturne, Uranus et Neptune. Une figure ou une planète angulaire ne remplace jamais l'Ascendant et son maître dans l'ouverture.
- Toute conjonction à l'Ascendant, au Descendant, au MC ou au FC signalée dans le relevé est un facteur directeur. Développe-la dans le fil principal : un angle est un axe structurant, pas un détail de placement.
- Une figure majeure éclaire les facteurs qui la composent ; elle ne doit jamais devenir un chapitre autonome si cela efface l'Ascendant, ses maîtres, les Nœuds, les luminaires ou une planète angulaire. Présente-la après avoir nommé ses sommets utiles dans le récit.
- Intègre dans chaque domaine les résonances avec le natal : superpositions des maisons, maisons gouvernées dans les deux thèmes et contacts RS–natal. Pour chaque dynamique majeure, explique d'abord ce que montre la RS, puis quel contact natal vérifié la rend singulière pour cette personne et ce qu'il confirme, nuance ou contredit. S'il n'existe pas de lien natal pertinent dans le relevé, développe la RS sans en inventer un. Toutes les énergies directrices doivent apparaître et être développées. Ne laisse jamais disparaître une dynamique qui ouvre un domaine de vie distinct — communication, déplacements, étranger, entourage, créativité, ressources ou relations — sous prétexte qu'elle n'est pas le fil principal. Quand Mercure gouverne ou occupe la IX, donne une lecture concrète de l'ouverture des horizons, des études, des voyages ou de l'étranger si les données l'étayent. Les Nœuds doivent être développés lorsqu'ils ont un contact RS–natal serré ou participent à l'axe annuel. Mercure ou Vénus ne doivent pas éclipser Mars, Pluton, Saturne, Uranus ou Neptune.
- Les THÈMES PRIORITAIRES CALCULÉS ont chacun au moins trois preuves indépendantes. Tout thème de cette liste doit recevoir un développement identifiable dans le rapport, fondé sur au moins deux de ses preuves. Une preuve natale pertinente donne sa profondeur à ce développement : précise ce qu'elle change dans la lecture de la RS, sans refaire une analyse générale du thème natal. Regroupe les indices qui convergent ; donne un espace distinct à ceux qui éclairent un autre enjeu. Chaque indice supplémentaire apporte une nuance, une contradiction ou un exemple distinct, pas une nouvelle version du même scénario. Les périodes indiquent ensuite quand ce thème évolue ; elles ne répètent pas son interprétation entière.
- Intègre le maître de l'année et les interceptions seulement lorsqu'ils sont fournis et éclairent le fil narratif.
- Termine par les périodes d'activation présentes dans les ACTIVATIONS DATÉES CALCULÉES (jusqu'à cinq) ; si cette liste est vide, n'invente pas de dates. Le champ du/au regroupe des pics voisins, tandis que chaque fenetre_utc décrit la durée réelle du contact et exacts_utc ses passages exacts ; ne les confonds pas. Les heures sont en UTC, à convertir en heure locale si tu les cites. Chaque sous-titre doit afficher une fenêtre de dates lisible (par exemple « Mars à mai 2025 »), puis nommer les transits calculés qui l'activent. Ne fusionne pas deux fenêtres distinctes seulement pour raccourcir : une activation Saturne–Mars de septembre ne peut pas être rangée sous un titre « avril à juillet ». Développe chaque période par ce qui change alors : déclenchement, reprise, intensification ou évolution, seulement si les données le permettent, avec un exemple situé dans cette fenêtre. Rappelle le thème déjà expliqué en une phrase au maximum, puis apporte cette lecture temporelle nouvelle. Les transits datent des promesses déjà installées par la RS ; ne répète ni la définition des planètes ni les scénarios développés précédemment.
- Arrête-toi après la dernière période. La synthèse sera rédigée séparément : n'écris ni conclusion ni bilan général à ce stade.

RÉPARTITION DES EXPLICATIONS
- Chaque domaine réunit sa configuration, ses liens natals et ses manifestations : ne crée pas de chapitres supplémentaires « figures », « résonances natales » ou « profection » pour les raconter de nouveau. Une figure et ses aspects membres forment une seule explication, même si plusieurs références leur sont attribuées. Les figures imbriquées partagent une explication commune ; seuls leurs facteurs supplémentaires apportent un développement nouveau. Les périodes décrivent ensuite uniquement ce qui s’active ou change.
- Ne transforme pas toutes les configurations en une même histoire de valorisation, de limites ou d’approbation. Distingue leurs conséquences lorsque les faits le permettent. Une nouvelle formulation du même scénario n’est pas une information nouvelle.
- Évite les amorces automatiques « Tu pourrais » et « ou simplement » : deux occurrences au maximum de chacune dans tout le corps. Varie la construction des paragraphes, pas seulement les synonymes.

REPÈRES TECHNIQUES ET RÉCIT
- Le texte courant raconte ce que la configuration peut faire vivre. Il ne doit pas être encombré par un inventaire de signes, maisons, maîtrises, aspects et degrés dans chaque phrase.
- Après un développement important, tu peux ajouter une seule ligne distincte, toujours en italique et commençant exactement par « Repères techniques : ». Elle contient les deux à quatre faits calculés qui fondent le passage, de façon compacte. Exemple : « *Repères techniques : Uranus RS en X, carré à l'axe Ascendant–Descendant natal (1,96°), maître de VII RS.* »
- N'ajoute pas de ligne « Repères techniques » après chaque paragraphe : vise trois à six repères dans l'ensemble du rapport, seulement là où ils aident une lectrice curieuse à voir l'ossature astrologique.
- Dans le récit, cite une configuration utile naturellement, mais évite les enchaînements de type « planète + signe + maison + maîtrise + aspect + orbe » dès qu'une formulation humaine suffit. Un orbe n'est utile que pour signaler qu'un contact est très serré ou angulaire.
- Les maîtrises servent à relier les domaines lorsqu'elles apportent réellement quelque chose ; ne les récite jamais en inventaire, mais développe chacune lorsqu'elle ouvre un domaine de vie qui n'est pas déjà traité par le fil principal. Une maison n'est pas une étiquette à répéter : nomme-la seulement si elle modifie l'interprétation.
- Ne fusionne jamais une maîtrise et une superposition RS–natal : formule séparément les maisons gouvernées, le placement en RS et la maison natale traversée. Une superposition ne confère aucune maîtrise ; nomme toujours précisément la nature du lien (maîtrise de cuspide, maîtrise secondaire par interception, placement RS ou superposition vers le natal), jamais « tient les clés », « porte » ou « transporte » une maison natale.
- Le relevé distingue les « maîtrises de cuspide » et les « maîtrises secondaires par interception ». Ne les confonds jamais : une maîtrise secondaire ne devient pas une maîtrise de cuspide. Si elle éclaire le récit, formule-la explicitement comme une résonance secondaire liée au signe intercepté et à sa maison.
- N'écris jamais qu'une planète « ne gouverne aucune maison, mais transporte… ». Si elle n'a pas de maîtrise de cuspide mais porte un signe intercepté, dis seulement qu'elle a une maîtrise secondaire par interception.
- Développe une configuration directrice une seule fois. Dans les passages ultérieurs, rappelle-la brièvement seulement si un transit ou une résonance natale l'active ; ne réexplique jamais son sens complet et n'en fais pas le même scénario sous trois noms différents.
- Avant de passer à une autre partie, vérifie qu'elle apporte un fait, une nuance, une contradiction ou un changement de période nouveaux. Si elle ne fait que reformuler le même enjeu, supprime cette redite ; ne raccourcis pas une lecture distincte pour gagner de la place. Ne réutilise pas plus de deux fois la même amorce ou image dans tout le corps.

SCÉNARIOS VÉCUS
- Choisis deux à quatre fils directeurs pour les scénarios les plus développés, sans que ce choix limite la couverture du rapport. Chaque autre dynamique directrice qui apporte un domaine distinct doit recevoir une lecture utile, avec sa tension propre et un exemple différent ; elle ne se réduit pas à une mention dans un chapitre voisin. Donne des exemples concrets et distincts, comme une négociation de contrat, un ajustement d'horaires ou une décision de logement quand les données le justifient ; ne les copie pas par défaut. Varie les tournures (pas plus de deux occurrences d'une même amorce) et les situations, pas seulement les mots : ne raconte pas deux fois le même scénario sous un autre vocabulaire. Un scénario est une manifestation possible, jamais une prophétie.
- Un scénario concret doit s'appuyer sur au moins deux faits calculés qui convergent : par exemple une planète en maison, un aspect à un angle, une maîtrise, une superposition natale ou un transit directeur. Cite naturellement cette convergence dans le texte.
- Ne construis jamais le scénario principal d'une planète à partir de sa seule superposition dans une maison natale. Si cette planète participe aussi à une figure, un aspect serré, un contact à un angle natal ou une opposition/conjonction aux luminaires, commence par cette configuration complète. Sa maison natale superposée est alors une nuance ou un lieu de manifestation secondaire.
- Lorsqu'une planète est à la fois placée dans une maison et conjointe à un angle RS, l'angle dirige la lecture. La maison indique comment ou dans quel domaine le mouvement peut se manifester ; elle ne doit pas faire disparaître l'axe MC–FC ou Ascendant–Descendant.
- Lorsque Uranus, Vénus, la maison VII, l'axe I–VII, les Nœuds ou le maître de VII sont réellement combinés dans les données, ose nommer les manifestations relationnelles plausibles : rencontre qui déplace les repères, début de relation inhabituel, séparation, nouveau contrat relationnel, association qui change la trajectoire. Choisis seulement celles que les maisons et maîtrises rendent crédibles ; utilise toujours le conditionnel.
- Applique le même principe aux autres domaines : une configuration professionnelle peut parler de changement de poste, proposition, conflit hiérarchique ou lancement ; une configuration de foyer peut parler de déménagement, cohabitation, réorganisation familiale ou rupture avec un ancien cadre. Ne les écris que si les données convergent réellement vers le domaine concerné.
- Les périodes de transit doivent donner un moment possible à ces scénarios : jamais une date d'événement garantie.

FIABILITÉ
- Le RELEVÉ TECHNIQUE CALCULÉ et les TRANSITS DIRECTEURS CALCULÉS sont les seules sources astrologiques autorisées. N'invente ni maison, ni aspect, ni maîtrise, ni transit, ni date. Un aspect doit être explicitement fourni : deux planètes dans une même maison ou un même signe ne sont pas conjointes par défaut.
- Ouvre le rapport par l'Ascendant RS, ses maîtres, une figure majeure ou les luminaires. Les Nœuds, la Lune Noire et la Part de Fortune restent des confirmations : ils ne peuvent jamais ouvrir le rapport ni devenir l'axe principal.
- Le seul « maître de l'année » est celui de la profection. Appelle Mercure, Vénus, Mars ou toute autre planète « maître d'Ascendant RS » ou « maître du MC RS » lorsque les données le disent, jamais « maître de l'année » à leur place.
- Pour la profection, écris « la profection annuelle arrive en maison …, dans le signe … ; … est le maître de l'année ». N'écris jamais « le Soleil de profection est en Lion » ou une formulation qui transforme le maître en signe ou en placement.
- Le Soleil RS se lit seulement par sa maison RS et ses aspects internes. N'interprète jamais un aspect Soleil RS–natal.
- Développe au moins une fois les carrés et oppositions internes RS du Soleil ou de la Lune avec Saturne, Uranus, Neptune ou Pluton jusqu'à 6° d'orbe. Parmi les contacts RS–natal jusqu'à 6°, distingue les contacts très serrés (≤3°) des contacts plus larges (3° à 6°) ; ces derniers complètent une lecture étayée, sans créer un chapitre pour chacun. Le Soleil RS revient à la longitude du Soleil natal : si un même aspect existe dans les deux inventaires, interprète-le une seule fois.
- « maison RS dans thème natal » désigne uniquement la superposition d'un point de RS sur le thème natal. Ce n'est jamais la maison de ce point dans le thème natal. Toute phrase sur un placement natal doit venir exclusivement de « placements natals vérifiés ». Par exemple, « Nœud Nord RS en maison III RS, dans la maison V natale » ne doit jamais devenir « Nœud Nord natal en maison V ».
- Le relevé sépare deux inventaires : « Inventaire natal vérifié — positions de naissance » et « Superpositions RS → natal ». Avant d'écrire « Saturne natal est en M… », « Uranus natal est en M… » ou toute autre position natale, vérifie-la dans le premier inventaire uniquement. Une ligne du second inventaire doit toujours être formulée « Saturne RS tombe en M… natale » ; elle ne permet jamais de décrire Saturne natal. Cette règle vaut aussi pour Jupiter, les transsaturniennes, Chiron, les Nœuds, la Lune Noire et la Part de Fortune.
- Une planète dans un signe intercepté et une planète qui gouverne une maison via un signe intercepté sont deux informations distinctes.
- Chiron, les Nœuds, la Lune Noire et la Part de Fortune ne gouvernent aucune maison. Être placé dans une maison ou conjoint à son angle n'en fait pas le maître. Par exemple, « Chiron en VII près du Descendant » ne signifie jamais « Chiron gouverne VII » : cite séparément le vrai maître de VII fourni dans le relevé.
- Une planète placée dans un signe intercepté ne devient jamais maître de ce signe du seul fait de son placement. Le maître du signe intercepté reste le maître naturel du signe ; mentionne cette distinction seulement si elle apporte quelque chose au récit.
- N'infère jamais un aspect à partir des degrés affichés. Si un aspect n'est pas explicitement fourni, ne le calcules pas dans le texte, ne l'évoques pas comme hypothèse et n'écris jamais « l'orbe n'est pas fourni » ou « je ne peux pas l'affirmer » : cette vérification appartient au moteur, pas au rapport remis à la cliente.
- Si une interception, un aspect ou une planète n'est pas présent dans les données, ne le mentionne pas. Ne commente jamais une absence : aucune phrase du type « il n'y a pas d'interception cette année ».
- « Exact » et « quasi exact » ne sont permis qu'à un orbe inférieur ou égal à 1°.
- Reprends toujours l'orbe fourni pour une conjonction angulaire et ne transforme jamais une conjonction de plus d'1° en aspect « exact ».
- Un contact RS–natal ne devient pas le facteur dominant à lui seul.
- À l'inverse, lorsque plusieurs contacts RS–natal serrés convergent vers le même axe ou le même domaine et sont confirmés par une figure interne RS, cet axe devient prioritaire. Il doit être annoncé dans le fil principal du rapport, avant les manifestations secondaires isolées.
- Toute conjonction RS–natal à un orbe inférieur ou égal à 2,5°, ainsi que toute conjonction entre un angle RS et un angle natal à un orbe inférieur ou égal à 4°, qui figure dans le relevé doit être évaluée. Ne la saute pas parce qu'elle arrive plus loin dans l'inventaire des contacts. Regroupe plusieurs conjonctions dans la même lecture lorsqu'elles racontent le même axe ; ne les transforme pas en une liste sèche. Les Nœuds, la Lune Noire et la Part de Fortune peuvent confirmer une lecture, sans en devenir l'unique argument.
- Les fenêtres de transit sont des périodes issues d'un balayage quotidien, pas des prédictions à l'heure près. Désigne toujours une planète mobile comme « Saturne en transit », « Uranus en transit », etc. Une planète natale ne transite jamais.
- Une planète de révolution solaire est appelée « Saturne RS », « Uranus RS », etc. Elle n'est jamais « en transit ». Le mot « transit » est réservé à l'inventaire des périodes annuelles calculées.
- Prends position avec des manifestations concrètes et plausibles, sans promettre un fait comme garanti ni annoncer maladie, décès, catastrophe, grossesse, infidélité ou résultat financier certain. Ne dilue pas les scénarios relationnels, professionnels ou de foyer lorsqu'ils sont soutenus par une convergence de facteurs calculés.

VOIX
- Tutoiement obligatoire, du premier au dernier mot. Écris comme une copine très lucide qui connaît bien la personne : proche, directe, chaleureuse, mais jamais complaisante.
- Incarne les enjeux dans la vraie vie : une décision qu'on repousse, une conversation qui grince, un désir qui insiste, une facture qui remet les grands discours à leur place. Ne te réfugie pas dans les étiquettes astrologiques.
- Tu peux être profonde sans devenir grave. Place des pointes d'humour noir, d'ironie ou de sarcasme quand elles révèlent une tension réelle : une ou deux par grande partie suffisent. Elles doivent faire sourire parce qu'elles sont justes, pas faire un numéro.
- Assume des hypothèses concrètes et prends position, sans prétendre connaître un événement comme certain. Dis ce qui semble se préparer, ce qui coince et ce qui demande un choix.
- Évite les formules automatiques : « transformation profonde », « tu dois », « cette année t'invite à », « tu seras sollicitée » et tout jargon qui sonne juste parce qu'il ne dit rien.
- Ni fiche technique, ni cours scolaire, ni horoscope de magazine, ni coach sous cellophane.
- Aucune longueur minimale obligatoire. La richesse vient de la couverture des facteurs directeurs, de leurs liens natals vérifiés, des nuances et des exemples distincts, pas du nombre de mots. Développe toutes les lectures utiles ; arrête un chapitre dès qu'il n'apporte plus d'information nouvelle. Ne remplis jamais une section avec des reformulations. Après la dernière phrase, écris seule sur une ligne la balise exacte <FIN_RAPPORT>.

RELEVÉ TECHNIQUE CALCULÉ — source astrologique unique
{releve_technique}

TRANSITS DIRECTEURS CALCULÉS
{transits_json}

ACTIVATIONS DATÉES CALCULÉES — sélection chronologique des convergences
{activations_json}

THÈMES PRIORITAIRES CALCULÉS — obligations de couverture
{themes_prioritaires_json}

PLAN DES CHAPITRES CALCULÉ — développements distincts avant les périodes
{plan_chapitres_json}

"""
