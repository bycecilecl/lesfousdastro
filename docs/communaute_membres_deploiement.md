# Communauté, cartes, feedback et calendrier

Report de la version validée dans le local de Cécile. Ce commit prépare le
déploiement ; aucune donnée locale n’est importée et aucun accès n’est attribué.

- Communauté privée : Nos partages, commentaires et tchat ouvert ; pseudo dans
  Mon profil, avatar commun, charte et signalements réservés à l’administratrice.
- Cartes : Administration → Cartes natales des membres ; image/PDF privé,
  consultable et téléchargeable depuis le ciel natal du propriétaire, accessible
  depuis son profil. Aperçu de recadrage, choix de la page PDF et conversion
  WebP sans perte, proportions conservées ; affichage en grand centré. La carte
  déjà déposée peut être reprise sans réimport. Le dépôt et l’aperçu restent
  réservés à l’administratrice ; seule la validation finale remplace le document.
- Bêta-test → Ton feedback ; consultation uniquement par l’administratrice.
- Calendrier : repère ✉ et ouverture du mail envoyé de la RL ou lunaison.
  L’archive Mes mails vérifie propriétaire et statut envoyé ; lien vers le journal.

Le point d’entrée `espace_wsgi.py` enregistre les nouveaux blueprints. La
migration Railway existante crée neuf tables supplémentaires, sans recopier les
binds SQLite locaux, sans modification des notes ni attribution de droits.
Les PDF/images sont conservés en base PostgreSQL, pas dans un fichier éphémère.

L’accès à la communauté et au feedback exige une inscription bêta confirmée et
active ainsi que la formule bêta active/non expirée ; l’administratrice y accède
aussi. Les inscriptions peuvent participer avant le début des mails. Une adresse
invitée ou un compte gratuit seul ne suffit pas. La table d’adhésion est créée
vide ; ce commit ne migre pas les inscriptions locales, ne crée aucun abonnement
et ne déploie pas le parcours de souscription/paiement, traité séparément.

Les tables de rendez-vous/adhésion sont des prérequis de stockage et de lecture.
Le module d’archives n’importe aucun moteur de mail ni de paiement. Aucun worker,
cron, appel IA, transport de mail ou activation automatique n’est ajouté.
Les moteurs RS et les paiements existants restent ceux de production.

Contrôles : comparaison des changements, lecture syntaxique Python/Jinja/JS et
contrôles statiques Git. Pas de test fonctionnel, génération, appel IA, envoi ou
connexion à la base de production. Les essais locaux ont été effectués et validés
par Cécile avant le report ; les adaptations PostgreSQL restent à vérifier après
déploiement par Cécile.

La note sous la carte précise un possible écart de quelques minutes d’arc avec
les données du site, sans exemple. Le rendu PDF utilise `pypdfium2==4.30.0`.
Cette évolution des cartes ne nécessite aucune migration de données et ne
reconvertit pas les cartes existantes au déploiement.
