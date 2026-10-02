# Écrire le blog des Fous d’Astro dans Bludit

## Ce qui est prêt localement

- Le site Flask continue de lire les 40 articles Markdown actuellement en ligne.
- Il peut aussi lire les **articles publiés** d’une installation Bludit distincte, via son API en lecture seule.
- Quand un article Bludit porte le même slug qu’un ancien article, il prend sa place à la **même adresse `/blog/<slug>`**. Un brouillon Bludit ne change rien au site public.
- Les réponses de Bludit sont conservées une minute en mémoire. Si Bludit devient momentanément indisponible, le dernier résultat connu reste utilisable au plus une heure ; les anciens articles Markdown restent disponibles.
- L’importateur prépare les anciens articles comme **brouillons**, avec leur titre, leur slug, leur date, leur description, leur contenu HTML et leur image à la une.
- Un ZIP Bludit 3.22.0 propre est préparé dans `preproduction/fous-blog-edition-test-20261002.zip` (à côté du dépôt). Il ne contient aucune donnée du Journal. Il convertit aussi les nouvelles images JPG/PNG en WebP et interdit l’indexation du domaine d’édition.

## À installer pour l’essai

1. Dans N0C, créer le sous-domaine `fous-edition-test.bycecilecl.com` sur l’hébergement PHP PlanetHoster, distinct du Journal.
2. Envoyer le ZIP dans le dossier **Local** du gestionnaire de fichiers N0C, puis l’extraire **dans Local** : un dossier `fous-blog-edition` est créé. Dans la gestion des domaines, associer uniquement le nouveau sous-domaine à la racine `/fous-blog-edition`, puis activer son certificat HTTPS.
3. Ouvrir le sous-domaine et terminer l’installation Bludit. Garder l’adresse et le mot de passe d’administration hors du dépôt GitHub.
4. Dans Bludit, activer le plugin **API** et créer au moins la catégorie `Astropapote` avec la clé `astropapote`. Les clés prévues sont `bases`, `signe`, `planete`, `maison`, `analyses`, `astropapote`, `carnets`, `vedique`, `uranienne`.
5. Déployer d’abord une version de test du code Flask des Fous d’Astro, puis y configurer `BLUDIT_BLOG_URL` (URL HTTPS du sous-domaine) et `BLUDIT_BLOG_API_TOKEN` (jeton du plugin API utilisé uniquement en lecture par Flask). Aucun jeton ne doit être ajouté à GitHub.
6. Préparer l’article pilote : `python scripts/import_blog_to_bludit.py --slug astrologie-libre-arbitre`. Pour l’importer en brouillon, renseigner temporairement `BLUDIT_BLOG_AUTH_TOKEN` avec le jeton d’authentification administrateur Bludit, puis lancer la même commande avec `--apply`.
7. Ouvrir et retoucher l’article dans Bludit. L’aperçu Bludit permet de vérifier sa mise en forme. Le publier seulement quand il est prêt. Contrôler ensuite `/blog/astrologie-libre-arbitre` sur la version de test de Flask, ainsi que l’image et la description SEO. La version publique sur `lesfousdastro.fr` ne change pas avant le déploiement validé du code Flask.

## Avant la bascule publique

- Répéter avec un article contenant plusieurs images pour vérifier leurs chemins et légendes.
- Vérifier les 40 slugs et les dates. `elements-theme-astral.md` contient actuellement une date invalide (`2022-0602-15`) qui doit être corrigée d’après la date de publication d’origine avant son import.
- Une fois les essais validés, activer les variables sur le site public. Les articles qui ne sont pas encore publiés dans Bludit restent servis depuis leurs fichiers Markdown.
- Le domaine d’édition Bludit est destiné à l’administration ; les lecteurs continuent à utiliser les adresses des Fous d’Astro.
