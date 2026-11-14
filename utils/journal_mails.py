"""Lien entre un mail envoyé et une note libre, sans analyse IA supplémentaire."""
from html import escape
import json
import os
import re
from urllib.parse import urlencode, urlsplit


LIBELLE = "Écrire dans mon journal à partir de ce mail"


def lien_journal_mail(mail_id):
    origine = (os.getenv("ESPACE_URL_PUBLIQUE") or os.getenv("ESPACE_PUBLIC_ORIGIN") or "https://lesfousdastro.fr").strip().rstrip("/")
    url = urlsplit(origine)
    domaine = (url.hostname or "").lower()
    if (url.scheme != "https" or (domaine != "lesfousdastro.fr" and not domaine.endswith(".lesfousdastro.fr"))
            or url.username or url.password or url.path or url.query or url.fragment):
        raise ValueError("L’origine publique des mails doit être une adresse HTTPS des Fous d’Astro, sans chemin.")
    return origine + "/mon-espace/journal?" + urlencode({"mail_source": mail_id})


def ajouter_lien_journal(mail):
    """Ajoute le même lien aux deux formats, sans toucher au texte d’analyse."""
    lien = lien_journal_mail(mail.id)
    marque = "<!-- journal-mail:" + mail.id + " -->"
    html, texte = mail.contenu_html or "", mail.contenu_texte or ""
    if marque not in html:
        bloc = (marque + '<div style="margin-top:32px;padding:20px;border-top:1px solid #d8e8e6">'
            '<p>Qu’est-ce que ce mail te donne envie de noter ?</p>'
            f'<p><a href="{escape(lien, quote=True)}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:12px 18px;'
            f'background:#1f628e;color:#ffffff;text-decoration:none;border-radius:20px">{LIBELLE}</a></p></div>')
        fermeture = re.search(r"</body\s*>", html, flags=re.I)
        html = html[:fermeture.start()] + bloc + html[fermeture.start():] if fermeture else html + bloc
    if lien not in texte:
        texte = texte.rstrip() + "\n\n" + LIBELLE + "\n" + lien
    return html, texte


def reference_mail(mail):
    return {"id": mail.id, "objet": mail.objet or "Mon mail astrologique", "nature": mail.nature,
            "date_envoi": mail.date_envoi.isoformat() if mail.date_envoi else None,
            "disponible": True}


def mail_envoye_du_membre(mail_id, utilisateur_id):
    from models.espace_personnel import MailEvenementAbonne
    return MailEvenementAbonne.query.filter_by(id=mail_id, utilisateur_id=utilisateur_id, statut="envoye").first_or_404()


def reference_entree(entree):
    """La copie d’un titre survit à un import ; son lien n’ouvre jamais le mail d’autrui."""
    if not entree or not entree.transits_actifs:
        return None
    try:
        source = json.loads(entree.transits_actifs).get("mail_journal")
    except (ValueError, TypeError, AttributeError):
        return None
    if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not 1 <= len(source["id"]) <= 80:
        return None
    from sqlalchemy import inspect
    from extensions import db
    from models.espace_personnel import MailEvenementAbonne
    mail = None
    if inspect(db.session.get_bind(mapper=MailEvenementAbonne)).has_table("mails_evenements_abonnes"):
        mail = MailEvenementAbonne.query.filter_by(id=source["id"], utilisateur_id=entree.utilisateur_id, statut="envoye").first()
    if mail:
        return reference_mail(mail)
    return {"id": None, "objet": source.get("objet") or "Mon mail astrologique", "disponible": False}


def notes_du_mail(mail):
    from models.espace_personnel import EntreeJournal
    notes = EntreeJournal.query.filter(EntreeJournal.utilisateur_id == mail.utilisateur_id,
        EntreeJournal.transits_actifs.contains(mail.id)).order_by(EntreeJournal.date_observation.desc()).all()
    resultat = []
    for note in notes:
        try:
            source = (json.loads(note.transits_actifs).get("mail_journal") or {})
            if isinstance(source, dict) and source.get("id") == mail.id:
                resultat.append(note)
        except (ValueError, TypeError, AttributeError):
            continue
    return resultat
