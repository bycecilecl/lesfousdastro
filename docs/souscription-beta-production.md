# Souscription bêta — préparation du 20 novembre 2026

La présentation reste à `/abonnements` (alias `/offre-beta`). Elle pourra
accueillir les offres définitives après la bêta. Cette version présente un
paiement unique de 35 € pour le 1er décembre 2026 au 28 février 2027 inclus,
avec une RS facultative à 39 € (pack à 74 €). Aucun renouvellement automatique.

## Parcours préparé

- Cécile autorise les adresses dans `/admin/envois-automatiques#invitations`.
  Aucun compte, accès offert ou message n'est créé par cette action.
- Le membre crée son compte avec l'adresse invitée, confirme son adresse par
  le parcours existant de définition du mot de passe et revient à son inscription.
- `/mon-espace/abonnement` demande le natal, le lieu des cycles et un choix
  explicite pour le journal (oui ou non). Le profil propose le retour à l'inscription.
- Le montant est déterminé côté serveur, jamais accepté depuis le navigateur.
  La commande est unique par compte/offre/mode. Le débit est réservé atomiquement
  avant la requête PayPal ; une confirmation incertaine n'est pas redébitée automatiquement.
- L'accès et l'inscription au calendrier sont enregistrés seulement après
  contrôle serveur de la capture, de son montant et de ses références.
  L'autorisation d'une adresse n'accorde pas un abonnement gratuit.
- Un achat confirmé du pack donne un bouton séparé pour préparer puis générer
  la RS incluse. La souscription et l'affichage des pages ne génèrent aucun rapport.
  Le moteur RS à six parties existant est conservé ; ses fichiers ne sont pas modifiés.
- Le PDF et les archives RS utilisent le stockage privé de l'espace. Les mails
  archivés conservent leurs URL, leur contrôle de propriétaire et leur CSP.

Le programme de mails existant prend ensuite les inscriptions en charge,
selon les dates et les garde-fous déjà configurés. Le nouveau parcours ne
déclenche aucun envoi immédiat. Les essais de mails restent séparés.

## Déploiement puis ouverture PayPal

Le pré-déploiement existant crée trois tables supplémentaires, sans suppression
ni modification de données : `invitations_offre_beta`,
`commandes_abonnements_espace`, `revolutions_solaires_pack_beta`.
Elles utilisent la connexion PostgreSQL par défaut de production, et non le
bind SQLite `journal` du labo. `espace_wsgi.py` remplace le blueprint d'archives
par le blueprint complet de souscription (mêmes endpoints d'archives, pas de doublon).

Configuration Railway inspectée en lecture seule le 20 novembre : les deux
clés Live sont présentes. Aucun secret n'a été affiché ni copié dans le dépôt.
L'identifiant de webhook des abonnements, le mode des abonnements et leur
autorisation d'ouverture ne sont pas encore configurés. Les paiements restent fermés.

Après déploiement, configurer un webhook dans **la même application PayPal Live** :

- URL : `https://lesfousdastro.fr/mon-espace/abonnement/paypal/webhook` ;
- événements : `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`,
  `PAYMENT.CAPTURE.REVERSED` ;
- conserver son identifiant dans `PAYPAL_WEBHOOK_ID_ABONNEMENTS` ;
- définir `PAYPAL_ABONNEMENTS_MODE=live` ;
- idéalement définir `PAYPAL_MERCHANT_ID_ABONNEMENTS` ;
- ouvrir avec `ABONNEMENTS_OUVERTS=1` lorsque Cécile décide de lancer ses essais.

Le webhook est joignable pendant la maintenance ; sa signature est vérifiée
auprès de PayPal avant traitement. Il peut confirmer un achat si le navigateur
est fermé. Un remboursement complet/révocation suspend l'accès lié à cet achat
et les prochains mails ; un remboursement partiel ne le fait pas automatiquement.

Références officielles consultées :
[capture d'une commande](https://developer.paypal.com/api/orders/v2/orders-capture),
[vérification de signature](https://developer.paypal.com/api/webhooks/v1/verify-webhook-signature-post).

## Validation réservée à Cécile

Seules la lecture du code, la vérification de syntaxe Python/Jinja et la lecture
des noms/réglages nécessaires sur Railway ont été effectuées. Aucun serveur,
test fonctionnel, calcul astrologique, paiement, rapport, appel IA ou envoi
n'a été exécuté par l'agent pour cette modification.

Après le push et le déploiement, Cécile vérifie la page, une adresse autorisée
et une adresse non autorisée, la création de compte et le retour depuis le profil.
Elle lance elle-même tout essai de paiement ou de RS. Recharger une page ne doit
jamais débiter ni générer ; un compte déjà inscrit doit voir sa confirmation.
Le paramétrage PayPal et le parcours réel restent à valider avant ouverture aux invités.
