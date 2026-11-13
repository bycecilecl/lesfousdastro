# Journal à deux colonnes

Version validée par Cécile dans `WEBSITE_FDA_LAST`, reportée dans ce dépôt
pour préparer la publication. Ce document ne constate pas un déploiement.

- Une grande page d’écriture ou de lecture à gauche ; la liste des entrées
  à droite, regroupées par mois, avec date et aperçu.
- Un clic ouvre une seule entrée avec `?entree=<id>#page-journal` ; le serveur
  vérifie qu’elle appartient au membre connecté.
- « Nouvelle entrée » revient au formulaire vide. La modification et ses
  erreurs restent dans la même disposition ; la saisie est conservée.
- Les périodes gardent leurs dates et « Toujours en cours ».
- « Aller plus loin » regroupe les mécanismes et l’accès au décodage existant.
  Le champ de justification du mécanisme et le bloc de saisie des ressentis
  sont retirés du journal.
- Les émotions et valeurs d’énergie déjà enregistrées restent en base et en
  lecture. Modifier le texte sans ces champs ne les efface pas. Les émotions
  restent dans les six étapes du décodage.
- Sur téléphone, « Mes entrées » se replie au-dessus de la page. Les liens
  sont des liens GET utilisables sans JavaScript ; les anciens liens avec
  `#entree-ID` sont reconduits par JavaScript vers l’entrée correspondante.
- Le navigateur avertit avant de quitter une saisie modifiée. Aucun
  enregistrement automatique n’est ajouté.

Les décorateurs des routes, contrôles d’accès, CSRF et mécanismes de production
sont conservés. Aucun changement de schéma ni migration de données.
La centralisation des fiches de mécanismes et le futur bilan IA, encore en
local, ne font pas partie de ce report. Le lien de décodage emploie l’endpoint
existant `decoder_mecanisme`, compatible avec les deux environnements.

Contrôles par l’agent : inspection statique Python/Jinja/JavaScript, inclusions,
liens et périmètre du diff. Aucun serveur, test applicatif, appel IA, envoi
ou modification de données personnelles exécuté.
