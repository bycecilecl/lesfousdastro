# Cartes des lunaisons — report validé le 23 novembre 2026

Cécile a validé dans `WEBSITE_FDA_LAST` l’import et l’affichage de sa carte
carrée, puis demandé la mise en production avec les cartes et les lectures.
Le report est ciblé : le modèle utilise PostgreSQL sans bind local, les
contrôles d’administration de production sont conservés, et la migration
additive existante ajoute `cartes_lunaisons` et ses index avant le démarrage.

Dans **Mes lectures de lunaisons**, ajouter une image PNG/JPG/WebP ou un PDF
(première page), 15 Mo maximum. La normalisation conserve les proportions et
limite le grand côté à 2 400 pixels. La carte reste facultative.

**Enregistrer le brouillon** conserve la nouvelle image sans la publier.
**Valider pour les mails et l’espace** publie le texte et sa carte ensemble.
Les abonnés actifs retrouvent les lectures collectives, y compris les anciennes,
dans **Les lunaisons**, avec carte centrée et accès au grand format.

La source du mail fige la référence de la carte validée. Le HTML reprend
l’image et un lien vers l’espace ; la version texte contient les liens.
Les anciennes cartes publiées sont conservées pour les mails déjà envoyés.
Un changement éditorial bloque l’envoi d’un ancien brouillon selon les contrôles
existants. Aucun appel IA supplémentaire, aucun prompt de rapport et aucun
comportement de Révolution Solaire n’est modifié.

Les cartes publiées sont servies par une URL opaque, lisible par les logiciels
de courrier sans connexion. Les brouillons restent réservés à l’administration.
Leur contenu PNG est enregistré en base et n’inclut aucune donnée de membre.
Le contrôleur d’image reste accessible pendant la maintenance ; cela n’ouvre
aucune page membre ni autre fichier.

## Carte déjà validée en local

Le paquet collectif du 24 novembre est préparé hors du dépôt Git, dans
`WEBSITE_FDA_LAST/preparation_prod/cartes_lunaisons_20261123/`.
`scripts/importer_lunaison_validee.py` peut le transférer explicitement vers
PostgreSQL, sans importer Flask ni démarrer de worker. Sans `--apply`, il
inspecte seulement. L’application exige une sauvegarde et refuse le
remplacement d’une publication plus récente. Un éventuel brouillon distinct
en production est conservé. Le transfert ne modifie aucun compte et ne génère
ni rapport ni mail.

Une réimportation manuelle depuis l’administration de production reste
possible après le déploiement. Aucun document privé de membre n’est copié.

## Vérification

Inspection des différences, de la syntaxe Python/Jinja et des branchements.
Aucun test fonctionnel, rapport, paiement, appel IA ou essai d’envoi lancé par
Codex. Les générations et la relecture des mails restent effectuées par Cécile.
