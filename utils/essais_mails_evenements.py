"""Essais explicites et séparés : aperçu, un appel IA, puis remise à soi-même."""
from datetime import datetime, timezone
import json
import math
import os
from uuid import uuid4

from extensions import db
from models.espace_personnel import AnalyseLunaison, MailEvenementAbonne, ProfilAstral
from utils.mails_evenements import (
    construire_prompt_evenement, horaire_envoi, preparer_dossier_evenement,
    signature_profil, source_editoriale, utc,
)

PREFIXE = "essai-local:"
DATE_PLEINE_LUNE = "2026-11-24"


def analyse_validee():
    return AnalyseLunaison.query.filter_by(type_lunaison="pleine_lune", date_utc=DATE_PLEINE_LUNE).filter(
        AnalyseLunaison.validee_le.isnot(None), AnalyseLunaison.texte_valide.isnot(None)).first()


def _parametres(prompt):
    from utils.parametres_claude_espace import MODEL, preparer_parametres_claude
    return preparer_parametres_claude({
        "model": os.getenv("ANTHROPIC_MODEL_MAIL_EVENEMENT") or MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 6500, "stop_sequences": ["<FIN_MAIL>"],
    })


def budget(prompt):
    from utils.dossier_mail_essentiel import LIMITE_PROMPT_CARACTERES
    longueur = len(prompt or "")
    return {"caracteres": longueur, "limite_caracteres": LIMITE_PROMPT_CARACTERES,
        "tokens_estimes": math.ceil(longueur / 3.5), "estimation_seulement": True,
        "conforme": longueur <= LIMITE_PROMPT_CARACTERES}


def _trace(mail, nom, valeur):
    from utils.automatisation_mails_evenements import _tracer
    _tracer(mail, nom, valeur)


def _transition(mail, avant, apres, **valeurs):
    from sqlalchemy import update
    resultat = db.session.execute(update(MailEvenementAbonne).where(
        MailEvenementAbonne.id == mail.id,
        MailEvenementAbonne.utilisateur_id == mail.utilisateur_id,
        MailEvenementAbonne.cle_evenement.startswith(PREFIXE),
        MailEvenementAbonne.statut.in_(avant),
    ).values(statut=apres, date_modification=datetime.now(timezone.utc), **valeurs))
    db.session.commit()
    if resultat.rowcount != 1:
        raise ValueError("Cette action a déjà été engagée ou l’état du mail a changé. Aucun nouvel appel ni envoi lancé.")
    db.session.refresh(mail)


def _profil(utilisateur):
    profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
    if profil is None:
        raise ValueError("Enregistre d’abord ton profil et la ville de tes cycles dans Mon profil.")
    return profil


def preparer(utilisateur, nature="pleine_lune"):
    """Appelé uniquement sur le clic de préparation ; aucun client IA importé."""
    if nature not in {"rl", "pleine_lune"}:
        raise ValueError("Choisis la Révolution Lunaire ou la Pleine Lune du 24 novembre.")
    print(f"[ESSAI MAIL] 1. Lecture du profil pour {nature}.", flush=True)
    profil = _profil(utilisateur)
    maintenant = datetime.now(timezone.utc)
    # La fonction de dossier conserve les mêmes contrôles de profil que le moteur normal.
    fuseau = profil.fuseau_cycles or profil.fuseau_horaire or "Europe/Paris"
    if nature == "rl":
        from utils.mails_evenements import _donnees_profil, _rl_active
        natal, _ = _donnees_profil(profil)
        instant, expiration = _rl_active(natal["planetes"]["Lune"]["longitude"], maintenant)
        # Essai du cycle actuel avec les notes à jour, sans antidater l’envoi.
        date_prevue = maintenant
    else:
        analyse = analyse_validee()
        if analyse is None or not (analyse.texte_valide or "").strip():
            raise ValueError("Valide d’abord ton analyse de la Pleine Lune du 24 novembre 2026.")
        instant = utc(analyse.instant_utc)
        if instant.date().isoformat() != DATE_PLEINE_LUNE:
            raise ValueError("La date de l’analyse validée ne correspond pas à la Pleine Lune choisie.")
        expiration = instant
        date_prevue = horaire_envoi(nature, instant, fuseau)
    identifiant = str(uuid4())
    mail = MailEvenementAbonne(id=identifiant, utilisateur_id=utilisateur.id, profil_id=profil.id,
        nature=nature, cle_evenement=PREFIXE + identifiant,
        instant_evenement=instant, date_prevue=date_prevue,
        expire_le=expiration, signature_profil=signature_profil(profil), statut="essai_prepare")
    print("[ESSAI MAIL] 2. Calcul des données et lecture des notes connues au moment de la préparation.", flush=True)
    dossier, choix, source = preparer_dossier_evenement(mail, profil, maintenant)
    prompt = construire_prompt_evenement(profil.prenom, mail, dossier)
    mail.dossier_json = json.dumps(dossier, ensure_ascii=False, default=str)
    mail.choix_journal_json = json.dumps(choix)
    mail.source_lunaison_json = json.dumps(source, ensure_ascii=False)
    mail.prompt = prompt
    mail.parametres_json = json.dumps(_parametres(prompt), ensure_ascii=False)
    db.session.add(mail)
    db.session.commit()
    for nom, valeur in (("dossier.json", dossier), ("prompt.txt", prompt),
                        ("requete.json", json.loads(mail.parametres_json)), ("controle_entree.json", budget(prompt))):
        try:
            _trace(mail, nom, valeur)
        except OSError:
            print("[ESSAI MAIL] Fichier indisponible ; copie conservée en base :", nom, flush=True)
    print("[ESSAI MAIL] Aperçu préparé. Appels IA : 0. Envois : 0.", flush=True)
    return mail


def verifier_actualite(mail, utilisateur):
    if mail.utilisateur_id != utilisateur.id or not mail.cle_evenement.startswith(PREFIXE):
        raise ValueError("Ce mail n’appartient pas à ton écran d’essai.")
    db.session.expire_all()
    profil = _profil(utilisateur)
    if profil.id != mail.profil_id or signature_profil(profil) != mail.signature_profil:
        raise ValueError("Ton profil a changé. Prépare un nouvel aperçu avant de poursuivre.")
    dossier, choix, source = preparer_dossier_evenement(mail, profil, datetime.now(timezone.utc))
    if (choix != json.loads(mail.choix_journal_json) or source != json.loads(mail.source_lunaison_json)
            or construire_prompt_evenement(profil.prenom, mail, dossier) != mail.prompt):
        raise ValueError("Les consignes, le journal, le profil, l’historique ou l’analyse validée ont changé. Prépare un nouvel aperçu ; aucun nouvel appel ni envoi n’a été lancé.")
    return profil


def generer(mail, utilisateur):
    """Une seule tentative payante par aperçu, jamais d’envoi dans cette fonction."""
    if mail.statut != "essai_prepare":
        raise ValueError("Cet aperçu a déjà fait l’objet d’une tentative. Le résultat est conservé ; aucun nouvel appel automatique.")
    verifier_actualite(mail, utilisateur)
    from utils.dossier_mail_essentiel import verifier_budget_prompt
    verifier_budget_prompt(mail.prompt)
    parametres = json.loads(mail.parametres_json)
    _transition(mail, ("essai_prepare",), "essai_generation_en_cours", erreur=None)
    try:
        print("[ESSAI MAIL] 3. Un seul appel Claude, sans relance automatique et sans envoi.", flush=True)
        _trace(mail, "requete.json", parametres)
        from utils.claude_espace import CLIENT, creer_message_claude, extraire_texte_claude
        reponse = creer_message_claude(client=CLIENT.with_options(max_retries=0, timeout=180.0), **parametres)
        brut = reponse.model_dump_json(indent=2)
        usage = reponse.usage.model_dump(mode="json")
        texte = extraire_texte_claude(reponse).replace("<FIN_MAIL>", "").strip()
        # Sauvegarde avant les contrôles : même une réponse refusée reste consultable.
        mail.reponse_brute, mail.usage_json, mail.contenu_texte = brut, json.dumps(usage), texte
        mail.date_generation = datetime.now(timezone.utc)
        db.session.commit()
        for nom, valeur in (("reponse_brute.json", brut), ("usage.json", usage)):
            try:
                _trace(mail, nom, valeur)
            except OSError:
                print("[ESSAI MAIL] Réponse conservée en base ; fichier indisponible :", nom, flush=True)
        if reponse.stop_reason not in {"end_turn", "stop_sequence"} or not texte:
            raise ValueError("Réponse vide ou interrompue. Le résultat est conservé sans relance.")
        from utils.automatisation_mails_evenements import _controler, _html
        from utils.mails_evenements import normaliser_presentation_mail
        texte = normaliser_presentation_mail(texte, mail)
        objet = _controler(texte, mail.nature)
        html = _html(texte, mail.nature, mail=mail)
        _transition(mail, ("essai_generation_en_cours",), "essai_brouillon", objet=objet, contenu_texte=texte, contenu_html=html)
        for nom, valeur in (("brouillon.txt", texte), ("brouillon.html", html),
                           ("controles.json", {"structure": "conforme", "liens": "conformes", "fond": "à relire par Cécile"})):
            try:
                _trace(mail, nom, valeur)
            except OSError:
                print("[ESSAI MAIL] Brouillon conservé en base ; fichier indisponible :", nom, flush=True)
        print("[ESSAI MAIL] Brouillon disponible pour relecture. Envois : 0.", flush=True)
    except Exception as erreur:
        db.session.rollback()
        message = str(erreur) if isinstance(erreur, ValueError) else "Échec de génération ou de sauvegarde (" + type(erreur).__name__ + "). Aucune relance automatique."
        _transition(mail, ("essai_generation_en_cours",), "essai_generation_echouee", erreur=message)
        raise ValueError(message) from None


def envoyer_a_soi(mail, utilisateur):
    """Remise explicite d’un brouillon relu, à l’adresse du seul compte administrateur."""
    if mail.utilisateur_id != utilisateur.id or not mail.cle_evenement.startswith(PREFIXE):
        raise ValueError("Ce mail n’appartient pas à ton écran d’essai.")
    db.session.refresh(mail)
    if mail.statut != "essai_brouillon":
        raise ValueError("Seul un brouillon généré et non envoyé peut être remis au transport.")
    # L'envoi à soi porte sur le brouillon enregistré et explicitement relu.
    # Les sources et le prompt actuels ne doivent pas imposer une nouvelle
    # génération payante. Leur actualité reste contrôlée avant generer().
    if not (mail.contenu_texte or "").strip() or not (mail.contenu_html or "").strip():
        raise ValueError("Le brouillon enregistré est incomplet ; aucun envoi lancé.")
    from utils.automatisation_mails_evenements import _controler
    _controler(mail.contenu_texte, mail.nature)
    destinataire = (utilisateur.email or "").strip()
    if not destinataire or "@" not in destinataire:
        raise ValueError("Ton compte doit avoir une adresse e-mail avant cet essai d’envoi.")
    from utils.transport_mails_evenements import verifier_transport, envoyer_evenement
    from utils.automatisation_mails_evenements import presentation_pour_envoi
    verifier_transport()
    objet, html, texte = presentation_pour_envoi(mail)
    # En local, le lien suit le serveur local ; en production, garder l’origine
    # publique vérifiée plutôt que dépendre de l’en-tête Host de la requête.
    from flask import url_for
    from routes.espace_personnel import _acces_dev_sur_machine_locale
    from html import escape
    from utils.journal_mails import lien_journal_mail
    lien_public = lien_journal_mail(mail.id)
    if _acces_dev_sur_machine_locale():
        lien_local = url_for("espace_personnel.journal", mail_source=mail.id, _external=True)
        html = html.replace(escape(lien_public, quote=True), escape(lien_local, quote=True))
        texte = texte.replace(lien_public, lien_local)
    _transition(mail, ("essai_brouillon",), "essai_envoi_en_cours", objet=objet, contenu_html=html, contenu_texte=texte, erreur=None)
    try:
        print("[ESSAI MAIL] 4. Une remise au transport, uniquement à l’adresse de ton compte.", flush=True)
        reference = envoyer_evenement(mail, destinataire)
        try:
            _trace(mail, "transport.json", {"reference": reference, "accepte_le": datetime.now(timezone.utc).isoformat()})
        except OSError:
            print("[ESSAI MAIL] Reçu transport sauvegardé en base ; fichier indisponible.", flush=True)
        _transition(mail, ("essai_envoi_en_cours",), "envoye", reference_transport=reference, date_envoi=datetime.now(timezone.utc))
        print("[ESSAI MAIL] Remis au transport et archivé. Aucun autre destinataire traité.", flush=True)
    except Exception as erreur:
        db.session.rollback()
        _transition(mail, ("essai_envoi_en_cours",), "essai_envoi_incertain",
            erreur="Remise au transport non confirmée (" + type(erreur).__name__ + "). Vérifie ta boîte et les traces ; aucun nouvel envoi automatique.")
        raise ValueError("Envoi non confirmé : vérifie ta boîte et les traces avant toute autre action. Aucun renvoi automatique.") from None
