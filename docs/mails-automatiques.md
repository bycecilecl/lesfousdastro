# Mails automatiques de l’espace abonné

Le moteur prépare les données actuelles, génère un mail puis remet au transport
la même version que celle archivée dans « Mes mails ». Le bouton de journal est
ajouté à l’envoi. Les essais restent séparés des rendez-vous automatiques.

## Installation

- Le programme s’exécute dans le service web existant sur Railway, sans nouveau
  service et sans modification du moteur de Révolution Solaire.
- Chaque processus peut démarrer un fil dédié ; un verrou PostgreSQL commun
  empêche deux passages simultanés, même pendant les appels externes.
- La réservation atomique de chaque mail est conservée. Un état de génération
  engagée ou d’envoi incertain n’est jamais repris automatiquement.
- Aucun traitement n’est lancé en important le module du programme.

## Activation

Les envois sont désactivés par défaut. Le démarrage exige Railway et
`MAILS_EVENEMENTS_ACTIFS=1`. Cette variable ne doit être activée qu’après les
essais réalisés par Cécile et la vérification des inscriptions.

`MAILS_EVENEMENTS_INTERVALLE_SECONDES` vaut 60 par défaut (30 à 300 secondes).
`MAILS_EVENEMENTS_MAX_PAR_PASSAGE` limite le nombre de mails traités à chaque
passage (10 par défaut). L’heure de début de traitement dépend du prochain
passage et du nombre de mails précédents à traiter.

Le programme est limité à la bêta du 1er décembre 2026 au 28 février 2027 inclus.
Avant l’ouverture, seuls les rendez-vous peuvent être préparés ; aucun appel IA
ni envoi automatique. Après la bêta, le programme s’arrête.

- RL : premier passage à 9 h après le retour lunaire, dans le fuseau du profil.
- Nouvelle/Pleine Lune : la veille à 9 h, dans ce même fuseau.
- Les lunaisons attendent une analyse collective validée, sans génération IA
  si elle manque. Aucun rattrapage n’est fait après expiration du créneau.
- Les droits, l’inscription, le destinataire, le lieu du cycle, le consentement
  au journal et les sources validées sont contrôlés avant les opérations externes.

## Suivi

`/admin/envois-automatiques` est réservé à l’administratrice. Cette page affiche
la configuration d’autorisation, les inscriptions, les échéances et les erreurs.
Elle ne génère et n’envoie rien. Elle permet de suspendre les prochains envois
d’un compte sans lui retirer son accès à l’espace.

Le raccordement au paiement et aux invitations bêta est une étape distincte.
Un compte existant n’est pas inscrit automatiquement par l’installation du programme.

En production, `python scripts/executer_mails_evenements.py` affiche seulement
les effectifs et états existants. Dans le dossier local, le même outil est
`python script/executer_mails_evenements.py`. Les options explicites
`--planifier` et `--executer` modifient respectivement le calendrier ou exécutent
le moteur ; aucune de ces options ne fait partie d’une vérification statique.

Les journaux préfixés `[MAILS AUTO]` indiquent le démarrage et le résultat des
passages. L’autorisation affichée dans la page ne remplace pas la confirmation
du fonctionnement dans les journaux du serveur.
