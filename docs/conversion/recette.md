# Tunnel gratuit → achat : changements locaux, pas de déploiement

## Ce qui est modifié

- Noms publics résiduels harmonisés. Le guide et le catalogue étaient déjà à 25 € avant ce chantier. Les clés, noms de fichiers historiques et imports sont conservés.
- Bouton après le gratuit → panier + récapitulatif existant. Aucun appel Stripe avant confirmation. Un panier contenant un pack, Racines familiales ou Point Transits est conservé et signalé plutôt que remplacé.
- Une recommandation principale : Point Astral Essentiel. Contenu, pages indicatives, délai indicatif, exemple et témoignage historique explicitement identifié.
- Plus tard ferme le résultat puis propose une question facultative. Pas de champ libre. La fermeture extérieure reste possible.
- Email immédiat enrichi. Relances séparées dans `emails-a-valider.md`, non programmées.
- Événements dans `static/conversion.js`, collecte filtrée dans `routes/conversion.py`. Achat accessible uniquement pour une commande appartenant à la session et réellement marquée payée par les vérifications existantes.

## Statistiques locales

Définir `CONVERSION_DB` sur un volume persistant avant déploiement ; par défaut `instance/conversion.sqlite3`. Cette collecte SQLite convient à une seule instance utilisant un même disque, pas à plusieurs serveurs avec disques séparés. Aucune base de production n’a été créée ou migrée pendant ce chantier.

Sur la machine contenant cette base :

```sh
python scripts/conversion_report.py --database /chemin/persistant/conversion.sqlite3 --start 2026-09-21 --end 2026-09-30 --output /tmp/conversion.html
```

Le rapport est un fichier HTML privé, sans nouvelle page d’administration publique. Il affiche sessions par étape, taux de parcours, commandes distinctes et freins. Les achats sandbox sont exclus. Les données brutes ne contiennent ni informations de naissance, ni nom, ni email. L’identifiant aléatoire reste un identifiant de suivi et ne constitue pas une garantie juridique d’anonymat.

## Recette à réaliser avant publication

1. Vérifier les tarifs effectivement configurés dans l’environnement et Stripe : le catalogue peut être surchargé par des variables d’environnement. Les cartes actuelles affichent des tarifs fixes.
2. Ouvrir une session de test et saisir `sessionStorage.setItem('fda_debug','1')` dans la console, puis recharger. Les événements manuels incluront `debug_mode`.
3. GA4 DebugView : vérifier start → success, clic → add_to_cart → begin_checkout. Le quota gratuit produit une erreur `quota`, jamais un succès. Vérifier aussi échec API, fermeture pendant chargement et réponse facultative.
4. Pour Stripe, une session est créée uniquement après confirmation du récapitulatif. Vérifier un vrai paiement **en mode test** puis rafraîchir la page : même `transaction_id`, une seule commande dans le stockage local. GA4 déduplique également les achats par identifiant. Un achat sandbox n’est transmis à GA4 qu’avec le debug local activé ; utiliser de préférence une propriété de test et son filtre développeur.
5. Vérifier les paramètres dans les requêtes : les événements ajoutés filtrent les données par listes fermées. Les UTM inconnus deviennent `other` ; ne jamais autoriser une valeur libre contenant un email. L’identifiant personnalisé GA4 est `funnel_session_id`.
6. **Audit GTM/GA4 restant** : le site charge aussi le conteneur GTM existant. Ses règles et les mesures améliorées configurées dans GA4 ne sont pas accessibles depuis ce dépôt. Vérifier qu’elles n’envoient pas de champs de formulaire, titres personnalisés, URL sensibles ou événements en double. La protection des événements ajoutés ne prouve pas l’innocuité de toutes les balises externes.
7. Faire un essai complet de géocodage, génération réelle, livraison email, Stripe et retour, sur ordinateur et téléphone, dans un environnement de test. Les tests locaux utilisent des fournisseurs simulés et ne valident pas ces services externes.
8. Valider les textes, les captures et la cadence des emails. Déployer seulement après accord de Cécile.

## Limites explicites

- DebugView et un véritable paiement Stripe test n’ont pas été vérifiés dans cette session.
- Le suivi d’achat navigateur exige un retour sur `/traiter-analyses`. Les achats payés sans retour navigateur ne sont pas encore remontés. Une intégration serveur via webhook/Measurement Protocol avec attribution persistante sera nécessaire pour cette couverture ; elle n’a pas été ajoutée au webhook déjà modifié par un autre chantier.
- Le stockage local déduplique par contrainte unique sur l’identifiant de commande. Dans GA4 : protection de rechargement dans sessionStorage + même identifiant de transaction pour la déduplication Google. Pas de promesse de livraison exactement une fois sur un réseau défaillant.
- Les erreurs Stripe HTTP sont enregistrées localement ; une réponse d’erreur non HTML ne permet pas un envoi navigateur à GA4. PayPal émet aussi l’événement navigateur.
- L’offre B n’est pas activée. Comparer d’abord la référence A avec des données réelles ; la dimension d’offre et le rapport préparent la comparaison ultérieure, sans prétendre qu’un test A/B est en cours.
- Le rapport décrit des sessions ayant les étapes sur la période, sans imposer un ordre strict ni attribuer un achat sur un autre appareil. Il ne remplace pas les comptes Stripe.
- La durée de conservation et la configuration du consentement doivent être intégrées à celles du site avant déploiement de cette nouvelle collecte.

Références Google : [événements e-commerce](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce), [validation DebugView](https://developers.google.com/analytics/devguides/collection/ga4/validate-ecommerce), [déduplication par transaction](https://support.google.com/analytics/answer/12313109?hl=fr).

## Résultats locaux du 21 septembre 2026

- 34 tests Python réussis : collecte, filtrage, refus des commandes non payées, déduplication, sécurité existante des commandes et routes de paiement simulées. Exécutés avec la version Stripe du projet : 12.5.1.
- Navigateur hors ligne à 390 × 844 et 1280 × 900 : résultat fictif → clic → récapitulatif de 25 €, fermeture facultative, erreurs et quota. Aucun débordement horizontal du récapitulatif observé.
- Événements observés : visite, début, succès, exposition de l’offre, clic, fermeture, ajout panier, réponse facultative et erreur. Quota/erreur ne produisent pas de succès.
- Les services externes étaient bloqués. Les erreurs Fancybox dues au blocage de sa bibliothèque externe ne constituent pas une vérification de la galerie en ligne.
- Captures `apres-gratuit-390.png`, `recapitulatif-390.png` et versions 1280 : données fictives, PayPal masqué pour le test. Elles ne prouvent pas un paiement réel ni la réception d’un email.
- Aucun déploiement, aucune relance envoyée, aucun achat réel.
