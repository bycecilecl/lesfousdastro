# Export privé du journal et du Labo

Mon profil → Copier mes données en local → Télécharger mes données.
Le bouton et la nouvelle route POST sont réservés à l’administratrice
authentifiée ; CSRF obligatoire. L’export porte uniquement sur le compte
connecté, sans paramètre permettant de choisir un autre utilisateur.

Le fichier JSON contient les notes, périodes et anciens ressentis, les
mécanismes, leurs épisodes, les réponses de décodage, les métadonnées des
analyses associées et les données de naissance avec le thème natal calculé.
Il ne contient pas les PDF, mots de passe, jetons, abonnements, consentements,
emails générés, cycles ou données de situation du profil. Les liens sont
conservés pour un remappage des identifiants lors de l’import local.

La connexion PostgreSQL d’export utilise une transaction REPEATABLE READ /
READ ONLY. La réponse téléchargeable est privée, sans stockage du fichier
sur le serveur et sans appel IA. Les tables métier ne sont pas modifiées.

Le module partagé comprend aussi les fonctions SQLite de l’import local,
mais aucune route d’import n’est enregistrée dans cette version de production.
Le formulaire d’import est explicitement désactivé dans le gabarit de profil.
Les fonctions locales refusent en outre un environnement Railway. L’import
et les sauvegardes se font dans `WEBSITE_FDA_LAST`, avec le parcours préparé
en local ; aucune connexion de production n’est utilisée pour importer.

Report de la préparation locale. Inspection statique de la syntaxe, des
inclusions, des garde-fous et du périmètre du diff uniquement. Aucun test,
export réel, import, migration, envoi ou appel IA exécuté par l’agent.
