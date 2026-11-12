# Fusion de l'espace personnel — préparation du 12 novembre 2026

## Base de production actualisée

La fusion a été reprise sur le commit `aeea5f09` (11 novembre 2026), dont le
message correspond au déploiement actif montré par Cécile. La récupération
GitHub a confirmé que main local avait un commit de retard. Le SHA Railway
n'a pas été consulté directement. Les changements de mots de passe, Turnstile,
invitations, activation bêta, initialisation du schéma et délai SMTP de cette
version sont conservés. Les mots de passe déjà définis restent valables :
aucune réinitialisation générale n'est demandée. L'environnement blog-test
conserve son étape de pré-déploiement vide.

## Périmètre

Fusion préparée depuis WEBSITE_FDA_LAST, puis reportée dans le dépôt de
déploiement. Aucun commit, push, migration distante ou déploiement exécuté.
Aucun test applicatif, calcul de rapport ou appel IA lancé par l'agent.

Ajouts : connexion avec mot de passe, récupération, périodes du journal,
avatars, autorisation du journal, rôle administratrice, exploration des
rapports et sélection des enjeux annuels, lectures collectives des lunaisons,
préparation des mails du 1er et du 15 et consultation de leurs journaux.

Conservés depuis la production : navigation, ciel collectif et calendrier,
stockage des PDF dans `fichiers_analyses_espace`, bibliothèque et remplacement
des analyses, anciens imports, commandes et paiements réels, blog et commentaires.
Les anciennes URLs du journal restent valables. Les formulaires anciens et
nouveaux gardent leurs contrôles CSRF. Les PDF sont matérialisés temporairement
uniquement au clic d'extraction, puis retirés en fin de requête.

Exclus : main.py, Dockerfile, routes et services de vente/génération des rapports,
code et prompts du moteur de Révolution Solaire, worker et client Claude partagé.
Le nouveau `utils/claude_espace.py` isole les réglages des mails et extractions.
Le service d'e-mails de production est conservé ; la récupération respecte le
choix Brevo ou SMTP. Le paiement Sandbox du local n'est pas importé.

## Structure de base

`scripts/migrate_espace_prod.py` cible exclusivement PostgreSQL via DATABASE_URL.
Il n'importe pas main, Flask, les routes ou les moteurs de rapports.

Ajouts aux tables existantes :

- `utilisateurs_espace` : champs de mot de passe et version d'authentification,
  autorisation du journal et date du choix, avatar, droit administratrice.
- `entrees_journal` : `est_periode`, `date_fin_periode`.
- `emails_cycles_abonnement` : `cle_creneau`, `date_prevue`, `fin_periode`.
- `analyses_personnelles` : `cycle_solaire_id`.

Tables nouvelles : `liens_mot_de_passe_espace`, `limites_acces_espace`,
`analyses_lunaisons`, `enjeux_annuels`.

Index uniques : une seule administratrice et un mail par profil/créneau.
Les champs existants ne sont pas réécrits ; les nouvelles autorisations sont
fausses par défaut. Aucun compte ni mot de passe n'est créé automatiquement.
Aucune suppression, fusion de doublons, copie de base, génération ou envoi.
Si un doublon interdit est rencontré, toute la transaction est annulée.
Les anciennes entrées restent des journées ; les anciens mails restent intacts.

## Avant déploiement

1. Faire une sauvegarde PostgreSQL depuis l'environnement de production.
2. Conserver SECRET_KEY, DATABASE_URL, les réglages de paiement et d'e-mail.
3. Prévoir un répertoire privé persistant pour les prompts, contrôles et
   journaux : `ESPACE_DOSSIER_PRIVE`, chemin absolu sur un volume, hors static.
   Les PDF des membres restent en base. Aucun fichier privé local n'est transféré.
4. Conserver `ESPACE_URL_PUBLIQUE=https://lesfousdastro.fr` et les cookies HTTPS.
5. Conserver les réglages d'invitation (`ESPACE_INVITE_EMAILS`,
   `ESPACE_INSCRIPTION_OUVERTE`) : cette fusion n'ouvre pas les inscriptions
   à toutes les adresses par défaut.

Inventaire du schéma, à lancer explicitement dans l'environnement production :

```sh
python scripts/migrate_espace_prod.py
```

Le fichier Railway prépare la migration `--apply` comme étape avant déploiement.
Elle ne sera exécutée qu'au lancement d'un déploiement. Le démarrage utilise
`--check` et refuse un schéma incomplet ; il ne masque plus un échec de migration.
Les redémarrages ne recalculent ni rapports ni mails.
Le worker RS déjà présent reste lancé exactement comme avant cette fusion.

## Compte administratrice

Les sessions anciennes sans version d'authentification sont refusées. Les
comptes et données restent conservés : chaque membre peut définir son mot de
passe avec son adresse existante. Aucun mail n'est envoyé automatiquement par
la migration. La demande d'un lien doit être explicite.

Pour Cécile, après définition de son mot de passe sur la production :

```sh
python scripts/configurer_admin_espace.py --database-url-env DATABASE_URL --email cecilecl@gmail.com --apply
```

Cette commande est séparée de la migration de structure : elle attribue
explicitement le droit à ce seul compte et invalide ses anciennes sessions.
Elle n'a pas été exécutée en production. Se reconnecter ensuite normalement.

Les listes, brouillons, prompts et journaux de mails sont réservés à
l'administratrice, y compris par URL directe. Les journaux techniques
d'extraction des PDF sont également réservés à l'administratrice.
Le contrôle du propriétaire du profil reste appliqué : les outils de mails
portent actuellement sur son propre profil, sans accès aux journaux des autres.

## Vérifications de Cécile après déploiement

- Connexion/récupération avec un compte existant ; données et PDF retrouvés.
- Avatar, retrait de l'avatar et conservation du choix après reconnexion.
- Journal : journée, période terminée, période toujours en cours, modification.
- Calendrier, ciel collectif, notes et navigation préexistants conservés.
- Import/remplacement d'un PDF, lecture et exploration ; rapport annuel existant
  inchangé. Toute extraction IA reste une action explicite.
- Autorisation du journal enregistrée ; filtrage du prompt comparé Non/Oui/Non
  depuis le compte admin avant toute génération payante.
- Membre non admin : aucune liste, fiche de brouillon, prompt ni journal
  technique accessible ; les URLs directes et POST renvoient 404.
- Les commandes et le parcours de paiement habituels restent disponibles.

Les inspections de syntaxe, noms et liens sont statiques. Elles ne valident ni
le rendu, ni la compatibilité réelle de la base distante, ni la génération IA.
La validation fonctionnelle et la décision de déployer appartiennent à Cécile.
