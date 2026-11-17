"""Automatisation des seuls rendez-vous bêta. Aucun traitement n’est lancé à l’import."""
from datetime import datetime, timezone
from html import escape
import json
import os
import re

from utils.mails_evenements import DEBUT_BETA, FIN_BETA, NATURES, TITRES_RL, TITRES_LUNAISON, utc

EN_ATTENTE = ("planifie", "attente_analyse")


def automatique_actif():
    autorise = os.getenv("MAILS_EVENEMENTS_ACTIFS", "0").lower() in {"1", "true", "oui"}
    environnement = bool(os.getenv("RAILWAY_ENVIRONMENT_ID")) or os.getenv("MAILS_EVENEMENTS_AUTORISER_LOCAL", "0") == "1"
    return autorise and environnement


def _transition(mail_id, avant, apres, **valeurs):
    from sqlalchemy import update
    from extensions import db
    from models.espace_personnel import MailEvenementAbonne
    r = db.session.execute(update(MailEvenementAbonne).where(
        MailEvenementAbonne.id == mail_id, MailEvenementAbonne.statut.in_(avant)
    ).values(statut=apres, date_modification=datetime.now(timezone.utc), **valeurs))
    db.session.commit()
    return r.rowcount == 1


def verifier_destinataire(mail, maintenant):
    """Relit droits, inscription, destination et profil avant chaque opération externe."""
    from sqlalchemy import select
    from extensions import db
    from models.espace_personnel import AbonnementEspace, InscriptionMailsBeta, ProfilAstral, UtilisateurEspace
    from utils.acces_abonnement import acces_abonnement
    from utils.mails_evenements import signature_profil
    db.session.expire_all()
    inscription = db.session.get(InscriptionMailsBeta, mail.utilisateur_id)
    utilisateur = db.session.get(UtilisateurEspace, mail.utilisateur_id)
    profil = db.session.get(ProfilAstral, mail.profil_id)
    abonnement = db.session.execute(select(AbonnementEspace).where(AbonnementEspace.utilisateur_id == mail.utilisateur_id)).scalar_one_or_none()
    if not inscription or not inscription.actif or not utilisateur or not utilisateur.actif or not profil:
        raise ValueError("Inscription suspendue, compte ou profil indisponible.")
    if not DEBUT_BETA <= maintenant < FIN_BETA or not utc(inscription.debut) <= maintenant < utc(inscription.fin):
        raise ValueError("En dehors de la période bêta de ce compte.")
    droits = acces_abonnement(abonnement, maintenant=maintenant)
    if not droits["actif"] or droits["code"] != "beta_accompagnement":
        raise ValueError("L’accès bêta n’est plus actif.")
    if profil.utilisateur_id != utilisateur.id or inscription.profil_id != profil.id:
        raise ValueError("Le profil n’appartient pas à cette inscription.")
    if (utilisateur.email or "").strip().lower() != inscription.email_destinataire:
        raise ValueError("L’adresse de réception a changé : vérification administratrice nécessaire.")
    if signature_profil(profil) != mail.signature_profil or inscription.signature_profil != mail.signature_profil:
        raise ValueError("Les données natales ou le lieu des cycles ont changé : vérification nécessaire.")
    return utilisateur, profil, inscription


def _controler(texte, nature):
    titres = TITRES_RL if nature == "rl" else TITRES_LUNAISON
    def normaliser(ligne):
        return ligne.strip().strip("*# ").rstrip(":").replace("’", "'").casefold()
    repertoire = {normaliser(t): t for t in titres}
    trouves = [repertoire[normaliser(l)] for l in texte.splitlines() if normaliser(l) in repertoire]
    if trouves != list(titres):
        raise ValueError("Les trois parties attendues sont manquantes, répétées ou déplacées.")
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    if not lignes or not lignes[0].startswith("OBJET :") or not lignes[0][7:].strip():
        raise ValueError("L’objet du mail est absent.")
    for url in re.findall(r"(?:https?://|www\.)[^\s<>\[\]()\"']+", texte, flags=re.I):
        from urllib.parse import urlsplit
        domaine = (urlsplit(url if "://" in url else "https://"+url).hostname or "").lower()
        if domaine != "lesfousdastro.fr" and not domaine.endswith(".lesfousdastro.fr"):
            raise ValueError("Le mail contient un lien externe interdit.")
    objet = lignes[0].split(":", 1)[1].strip()
    if len(objet) > 250:
        raise ValueError("L’objet du mail dépasse la longueur autorisée.")
    return objet


def _html(texte, nature):
    titres = TITRES_RL if nature == "rl" else TITRES_LUNAISON
    normalises = {t.replace("’", "'").casefold() for t in titres}
    blocs = []
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("OBJET :"):
            continue
        titre = ligne.strip("*# ").rstrip(":")
        contenu = escape(titre if titre.replace("’", "'").casefold() in normalises else ligne)
        contenu = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", contenu)
        contenu = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", contenu)
        contenu = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", contenu)
        balise = "h2" if titre.replace("’", "'").casefold() in normalises else "p"
        blocs.append(f"<{balise}>{contenu}</{balise}>")
    return ('<!doctype html><html lang="fr"><meta charset="utf-8"><body style="max-width:680px;margin:24px auto;padding:20px;color:#33434c;font:17px/1.75 Georgia,serif">'
            + "\n".join(blocs) + '</body></html>')


def presentation_pour_envoi(mail):
    """Même présentation pour un brouillon déjà prêt, sans nouvelle génération."""
    from types import SimpleNamespace
    from utils.mails_evenements import normaliser_presentation_mail
    from utils.journal_mails import ajouter_lien_journal
    texte = normaliser_presentation_mail(mail.contenu_texte, mail)
    objet = _controler(texte, mail.nature)
    copie = SimpleNamespace(id=mail.id, contenu_texte=texte, contenu_html=_html(texte, mail.nature))
    html, texte = ajouter_lien_journal(copie)
    return objet, html, texte


def _tracer(mail, nom, valeur):
    from utils.stockage_espace import racine_privee_espace
    dossier = racine_privee_espace() / "mails_evenements" / mail.id
    dossier.mkdir(mode=0o700, parents=True, exist_ok=True)
    texte = valeur if isinstance(valeur, str) else json.dumps(valeur, ensure_ascii=False, indent=2, default=str)
    with (dossier / nom).open("w", encoding="utf-8") as fichier:
        os.chmod(dossier / nom, 0o600)
        fichier.write(texte)
    print(f"\n[MAIL ÉVÉNEMENT {mail.id}] {nom}\n{texte}", flush=True)


def _verifier_sources(mail, choix, source):
    from utils.confidentialite_journal_mails import lire_choix_journal_mails
    from utils.mails_evenements import source_editoriale
    if lire_choix_journal_mails(mail.utilisateur_id) != choix:
        raise ValueError("Le choix d’utilisation du journal a changé : aucun envoi automatique de cette version.")
    if source_editoriale(mail) != source:
        raise ValueError("La version validée de la lunaison a changé : aucun envoi automatique de cette version.")


def traiter_evenement(mail_id):
    """Une tentative IA et une tentative de remise au transport, jamais relancées automatiquement."""
    from extensions import db
    from models.espace_personnel import MailEvenementAbonne
    from utils.mails_evenements import construire_prompt_evenement, preparer_dossier_evenement, source_editoriale
    from utils.transport_mails_evenements import verifier_transport, envoyer_evenement
    from utils.journal_mails import ajouter_lien_journal, lien_journal_mail
    from utils.dossier_mail_essentiel import verifier_budget_prompt
    if not automatique_actif():
        return "desactive"
    maintenant = datetime.now(timezone.utc)
    if not DEBUT_BETA <= maintenant < FIN_BETA:
        return "hors_periode_beta"
    mail = db.session.get(MailEvenementAbonne, mail_id)
    if mail is None or mail.statut not in (*EN_ATTENTE, "pret"):
        return "ignore"
    if maintenant < utc(mail.date_prevue):
        return "pas_encore_du"
    if maintenant >= utc(mail.expire_le):
        _transition(mail.id, (*EN_ATTENTE, "pret"), "expire", erreur="Créneau dépassé ; aucun rattrapage tardif automatique.")
        return "expire"
    try:
        utilisateur, profil, inscription = verifier_destinataire(mail, maintenant)
        verifier_transport()
        lien_journal_mail(mail.id)  # Configuration contrôlée avant tout appel payant.
    except ValueError as erreur:
        _transition(mail.id, (*EN_ATTENTE, "pret"), "bloque", erreur=str(erreur))
        return "bloque"
    if mail.statut in EN_ATTENTE:
        try:
            if mail.nature != "rl" and source_editoriale(mail) is None:
                _transition(mail.id, EN_ATTENTE, "attente_analyse", erreur="Analyse collective validée attendue ; aucun appel IA.")
                return "attente_analyse"
            dossier, choix, source = preparer_dossier_evenement(mail, profil, maintenant)
            prompt = construire_prompt_evenement(profil.prenom, mail, dossier)
            controle_entree = verifier_budget_prompt(prompt)
            # Lecture de configuration, sans exposer la clé ni appeler le fournisseur.
            from utils.claude_espace import MODEL, preparer_parametres_claude
            parametres = preparer_parametres_claude({"model": os.getenv("ANTHROPIC_MODEL_MAIL_EVENEMENT") or MODEL,
                "messages": [{"role": "user", "content": prompt}], "max_tokens": 6500,
                "stop_sequences": ["<FIN_MAIL>"]})
            if not _transition(mail.id, EN_ATTENTE, "generation_en_cours", dossier_json=json.dumps(dossier, ensure_ascii=False, default=str),
                prompt=prompt, parametres_json=json.dumps(parametres, ensure_ascii=False),
                choix_journal_json=json.dumps(choix), source_lunaison_json=json.dumps(source, ensure_ascii=False), erreur=None):
                return "deja_reclame"
            _tracer(mail, "dossier.json", dossier)
            _tracer(mail, "requete.json", parametres)
            _tracer(mail, "controle_entree.json", controle_entree)
            verifier_destinataire(mail, datetime.now(timezone.utc))
            _verifier_sources(mail, choix, source)
            if not automatique_actif():
                raise ValueError("Automatisation désactivée avant l’appel IA. Aucun appel effectué.")
            if datetime.now(timezone.utc) >= utc(mail.expire_le):
                raise ValueError("Le créneau est terminé. Aucun appel IA effectué.")
            from utils.claude_espace import CLIENT, creer_message_claude, extraire_texte_claude
            reponse = creer_message_claude(client=CLIENT.with_options(max_retries=0, timeout=180.0), **parametres)
            brut = reponse.model_dump_json(indent=2)
            usage = reponse.usage.model_dump(mode="json")
            texte = extraire_texte_claude(reponse).replace("<FIN_MAIL>", "").strip()
            try:
                _tracer(mail, "reponse_brute.json", brut)
                _tracer(mail, "usage.json", usage)
            except OSError:
                print("[MAILS BÊTA] Fichiers indisponibles ; sauvegarde de la réponse en base poursuivie.", flush=True)
            # Conserver la réponse même lorsqu’elle est refusée, sans réécriture payante.
            mail.reponse_brute, mail.usage_json, mail.contenu_texte = brut, json.dumps(usage), texte
            mail.date_generation = datetime.now(timezone.utc)
            db.session.commit()
            if reponse.stop_reason not in {"end_turn", "stop_sequence"} or not texte:
                raise ValueError("Réponse vide, tronquée ou interrompue.")
            from utils.mails_evenements import normaliser_presentation_mail
            texte = normaliser_presentation_mail(texte, mail)
            objet = _controler(texte, mail.nature)
            contenu_html = _html(texte, mail.nature)
            try:
                _tracer(mail, "controles.json", {"structure": "conforme", "liens": "conformes",
                    "reponse_complete": True, "controle_du_fond": "consigne_dans_le_meme_appel_pas_de_second_appel"})
            except OSError:
                print("[MAILS BÊTA] Contrôle structurel conforme ; fichier indisponible.", flush=True)
            if not _transition(mail.id, ("generation_en_cours",), "pret", objet=objet, contenu_texte=texte, contenu_html=contenu_html):
                return "etat_modifie"
        except Exception as erreur:
            db.session.rollback()
            message = str(erreur) if isinstance(erreur, ValueError) else "Échec du fournisseur ou du stockage ; aucune relance automatique (" + type(erreur).__name__ + ")."
            _transition(mail.id, (*EN_ATTENTE, "generation_en_cours"), "generation_echouee", erreur=message)
            return "generation_echouee"
    # Une réponse prête après un redémarrage peut encore être envoyée : aucun nouvel appel IA.
    db.session.refresh(mail)
    if mail.statut != "pret":
        return mail.statut
    try:
        maintenant = datetime.now(timezone.utc)
        utilisateur, profil, inscription = verifier_destinataire(mail, maintenant)
        if maintenant >= utc(mail.expire_le):
            raise ValueError("Le créneau d’envoi est terminé.")
        _verifier_sources(mail, json.loads(mail.choix_journal_json), json.loads(mail.source_lunaison_json))
        if not automatique_actif():
            return "desactive"
        objet_envoi, html_envoi, texte_envoi = presentation_pour_envoi(mail)
    except ValueError as erreur:
        _transition(mail.id, ("pret",), "suspendu", erreur=str(erreur))
        return "suspendu"
    if not _transition(mail.id, ("pret",), "envoi_en_cours", objet=objet_envoi, contenu_html=html_envoi, contenu_texte=texte_envoi):
        return "deja_reclame"
    try:
        db.session.refresh(mail)  # Le transport et l’archive lisent la même version avec le lien.
        if not automatique_actif():
            _transition(mail.id, ("envoi_en_cours",), "pret")
            return "desactive"
        reference = envoyer_evenement(mail, inscription.email_destinataire)
        # Le reçu du fournisseur est conservé avant le statut final. Jamais de retry si ce statut n’est pas écrit.
        try:
            _tracer(mail, "transport.json", {"reference": reference, "accepte_le": datetime.now(timezone.utc).isoformat()})
        except OSError:
            print("[MAILS BÊTA] Reçu du transport conservé en base uniquement.", flush=True)
        _transition(mail.id, ("envoi_en_cours",), "envoye", date_envoi=datetime.now(timezone.utc), reference_transport=reference, erreur=None)
        return "envoye"
    except Exception as erreur:
        db.session.rollback()
        _transition(mail.id, ("envoi_en_cours",), "envoi_incertain", erreur="Remise au transport incertaine ("+type(erreur).__name__+"). Vérifier le fournisseur ; aucun renvoi automatique.")
        return "envoi_incertain"


def passer_automatisation():
    from extensions import db
    from models.espace_personnel import InscriptionMailsBeta, MailEvenementAbonne
    from utils.mails_evenements import planifier_inscription
    resultat = {"planifies": 0, "traitements": []}
    if not automatique_actif():
        return {"statut": "desactive", **resultat}
    maintenant = datetime.now(timezone.utc)
    if maintenant >= FIN_BETA:
        return {"statut": "beta_terminee", **resultat}
    for inscription in InscriptionMailsBeta.query.filter_by(actif=True, date_planification=None).all():
        try:
            nouveaux = planifier_inscription(inscription)
            db.session.commit()
            resultat["planifies"] += nouveaux
        except Exception as erreur:
            db.session.rollback()
            print("[MAILS BÊTA] Planification non effectuée pour le compte", inscription.utilisateur_id, type(erreur).__name__, flush=True)
    if maintenant < DEBUT_BETA:
        return {"statut": "avant_ouverture_aucun_appel", **resultat}
    limite = max(1, min(50, int(os.getenv("MAILS_EVENEMENTS_MAX_PAR_PASSAGE", "10"))))
    from sqlalchemy import case
    priorite = case((MailEvenementAbonne.statut == "pret", 0), (MailEvenementAbonne.statut == "planifie", 1), else_=2)
    mails = MailEvenementAbonne.query.filter(MailEvenementAbonne.statut.in_((*EN_ATTENTE, "pret")),
        MailEvenementAbonne.date_prevue <= maintenant).order_by(priorite, MailEvenementAbonne.date_prevue).limit(limite).all()
    for mail in mails:
        try:
            statut = traiter_evenement(mail.id)
        except Exception as erreur:
            db.session.rollback()
            statut = "incident_" + type(erreur).__name__
        resultat["traitements"].append({"id": mail.id, "statut": statut})
    return {"statut": "termine", **resultat}
