# Administration des bêta-testeurs — 23 novembre 2026

À la demande de Cécile, les invitations et les paiements sont regroupés dans
**Administration → Bêta-testeurs**, à `/admin/beta-testeurs`.

L’écran propose les adresses autorisées (avec le grand champ de saisie),
le lien public de l’offre, l’état d’ouverture du paiement, les 100 dernières
commandes de la bêta, les inscriptions et un lien vers les retours bêta.
Les paiements sont associés au prénom et à l’adresse du compte concerné.
Les essais Sandbox restent identifiés comme des paiements fictifs.

**Envois automatiques** conserve les destinataires des mails, les rendez-vous,
les états d’envoi et la suspension des envois. Un lien mène à la nouvelle
gestion bêta. Il n’affiche plus la saisie des invitations ni les commandes.

Les modèles et tables sont inchangés. Les adresses déjà enregistrées et les
paiements sont relus depuis le stockage existant, sans transfert de données.
La nouvelle route garde le contrôle d’administratrice et le CSRF au POST.
L’ancien POST `/admin/envois-automatiques/invitations` redirige en 307 vers
la nouvelle action pour préserver un formulaire déjà ouvert, sans traiter
deux fois la demande. Une adresse retirée ne supprime pas un abonnement payé.

Aucun réglage PayPal, prix, abonnement, droit offert, moteur de rapport ou
programme de génération n’est modifié. Aucun e-mail n’est envoyé lors de
l’ajout d’adresses. Aucun test fonctionnel, paiement ou appel IA n’est lancé
par Codex ; inspection statique uniquement.

Le report de production enregistre `admin_beta_bp` dans `espace_wsgi.py`,
sans recopier le point d’entrée local. Le footer compact est conservé et la
rubrique de navigation est réservée à l’administratrice.
