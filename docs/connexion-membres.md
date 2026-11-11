# Connexion membre par mot de passe

Portage du parcours validé par Cécile dans WEBSITE_FDA_LAST : e-mail/mot de
passe, minimum choisi de huit caractères, création initiale, récupération et
changement. Les comptes sont retrouvés par leur adresse existante ; aucun
profil, journal, rapport ni abonnement n'est remplacé.

Les inscriptions restent soumises aux invitations et à
`ESPACE_INSCRIPTION_OUVERTE`. Les comptes actifs déjà présents peuvent définir
leur mot de passe, même si leur adresse n'est plus dans la liste d'invitations.
Les droits bêta existants sont conservés et leur activation reste limitée aux
adresses explicitement configurées. Turnstile reste requis pour la connexion
et les demandes publiques de définition/récupération.

## Schéma PostgreSQL

`scripts/init_espace_auth.py` crée les deux tables d'authentification et ajoute
les trois colonnes manquantes à `utilisateurs_espace`. Migration additive et
transactionnelle, sérialisée par le verrou PostgreSQL déjà utilisé au démarrage.
Les comptes existants commencent avec un mot de passe vide, qu'ils définissent
eux-mêmes via leur boîte e-mail. Les anciennes sessions sont invalidées.

Railway lance ce script en pré-déploiement : en cas d'échec, la nouvelle version
ne démarre pas. Le démarrage existant le relance de façon idempotente. Le service
isolé `blog-test` conserve sa configuration sans base de données.

## Configuration conservée

- `DATABASE_URL` existante ; aucune base locale n'est copiée.
- `SECRET_KEY` existante, stable, sans rotation lors de cette mise en ligne.
- Cookies HTTPS existants et durée de session de production de 14 jours.
- Expéditeur et fournisseur d'e-mail existants, y compris Brevo.
- Origine des liens : `ESPACE_URL_PUBLIQUE`, sinon `ESPACE_PUBLIC_ORIGIN`, sinon
  `https://lesfousdastro.fr`. Aucun lien de récupération ne dépend du Host fourni
  par le visiteur.

Les pages de définition de mot de passe n'utilisent pas de script tiers et
retournent `no-store` et `no-referrer`. Seules les empreintes des mots de passe
et des jetons sont stockées. Les limites de tentatives sont partagées en base.

## Validation

Parcours SQLite validé manuellement par Cécile. Adaptation PostgreSQL relue
statiquement ; aucun test d'application, génération IA ni e-mail d'essai lancé
par Codex. Après mise en ligne, chaque membre utilise « Définis ton mot de
passe » avec son adresse habituelle, puis se connecte directement. Aucun e-mail
de récupération n'est envoyé automatiquement lors du déploiement.
