# Écrire le blog des Fous d’Astro dans Bludit

## Ce qui est prêt localement

- Le site Flask continue de lire les 42 articles Markdown actuellement en ligne.
- Il peut aussi lire les **articles publiés** d’une installation Bludit distincte, via son API en lecture seule.
- Quand un article Bludit porte le même slug qu’un ancien article, il prend sa place à la **même adresse `/blog/<slug>`**. Un brouillon Bludit ne change rien au site public.
- Les images téléversées dans Bludit passent par `/blog/media/...` sur Les Fous d’Astro, pour rester sur le domaine public du blog. Les anciennes images déjà hébergées sur Les Fous d’Astro restent à leur adresse actuelle.
- Les réponses de Bludit sont conservées une minute en mémoire. Si Bludit devient momentanément indisponible, le dernier résultat connu reste utilisable au plus une heure ; les anciens articles Markdown restent disponibles.
- L’importateur prépare les 42 anciens articles comme **brouillons**, avec leur titre, leur slug, leur date, leur description, leur contenu HTML et leur image à la une. Les catégories multiples deviennent une catégorie principale et une étiquette secondaire.
- Un ZIP Bludit 3.22.0 propre est préparé dans `preproduction/fous-blog-edition-test-20261002.zip` (à côté du dépôt). Il ne contient aucune donnée du Journal. Il convertit aussi les nouvelles images JPG/PNG en WebP et interdit l’indexation du domaine d’édition.

## À installer pour l’essai

1. Dans N0C, créer le sous-domaine `fous-edition-test.bycecilecl.com` sur l’hébergement PHP PlanetHoster, distinct du Journal.
2. Envoyer le ZIP dans le dossier **Local** du gestionnaire de fichiers N0C, puis l’extraire **dans Local** : un dossier `fous-blog-edition` est créé. Dans la gestion des domaines, associer uniquement le nouveau sous-domaine à la racine `/fous-blog-edition`, puis activer son certificat HTTPS.
3. Ouvrir le sous-domaine et terminer l’installation Bludit. Garder l’adresse et le mot de passe d’administration hors du dépôt GitHub.
4. Dans Bludit, activer le plugin **API** et créer au moins la catégorie `Astropapote` avec la clé `astropapote`. Les clés prévues sont `bases`, `signe`, `planete`, `maison`, `analyses`, `astropapote`, `carnets`, `vedique`, `uranienne`.
5. Déployer d’abord une version de test du code Flask des Fous d’Astro, puis y configurer `BLUDIT_BLOG_URL` (URL HTTPS du sous-domaine) et `BLUDIT_BLOG_API_TOKEN` (jeton du plugin API utilisé uniquement en lecture par Flask). Aucun jeton ne doit être ajouté à GitHub.
6. Pour rapatrier les anciens articles sans communiquer de jeton, générer `preproduction/fous-blog-import-brouillons-20261003.zip` avec `python -m tools.prepare_bludit_import_bundle`. Dans N0C, envoyer l’archive dans la racine du Bludit d’édition (`/fous-blog-edition`) et l’y extraire. Cela ajoute uniquement `bl-plugins/fous-blog-import`. Dans Bludit, activer **Import des anciens articles**, ouvrir **Importer les anciens articles** dans le menu d’administration et cliquer **Importer les brouillons**. L’opération ignore les articles déjà présents et peut être relancée après une interruption.
7. Ouvrir et retoucher l’article dans Bludit. L’aperçu Bludit permet de vérifier sa mise en forme. Le publier seulement quand il est prêt. Contrôler ensuite `/blog/astrologie-libre-arbitre` sur la version de test de Flask, ainsi que l’image et la description SEO. La version publique sur `lesfousdastro.fr` ne change pas avant le déploiement validé du code Flask.

## Avant la bascule publique

- Répéter avec un article contenant plusieurs images pour vérifier leurs chemins et légendes.
- Vérifier les 42 slugs et les dates. `elements-theme-astral.md` contient une date invalide (`2022-0602-15`) également visible sur la page publique. Son brouillon reçoit provisoirement `2022-06-15` et doit être vérifié avant publication.
- Une fois les essais validés, activer les variables sur le site public. Les articles qui ne sont pas encore publiés dans Bludit restent servis depuis leurs fichiers Markdown.
- Le domaine d’édition Bludit est destiné à l’administration ; les lecteurs continuent à utiliser les adresses des Fous d’Astro.
