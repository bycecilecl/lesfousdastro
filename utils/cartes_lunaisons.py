"""Images communes des lunaisons : import, publication et ajout aux mails, sans IA."""
from datetime import timezone
from html import escape
from io import BytesIO
import json
import re
from secrets import token_hex

from sqlalchemy import inspect

from extensions import db
from models.espace_personnel import CarteLunaison, utcnow

TAILLE_MAX = 15 * 1024 * 1024
MESSAGE_STOCKAGE = "Le stockage des cartes de lunaisons doit être préparé avant d’ajouter une carte."


def stockage_pret():
    return inspect(db.session.get_bind(mapper=CarteLunaison)).has_table(CarteLunaison.__tablename__)


def cartes_de_la_fiche(nature, date_utc):
    if not stockage_pret():
        return None, None
    cartes = CarteLunaison.query.filter_by(type_lunaison=nature, date_utc=date_utc)
    return (cartes.filter_by(brouillon_actif=True).first(),
            cartes.filter_by(version_validee=True).first())


def preparer_import(fichier):
    """Valide et normalise en PNG, sans métadonnées ni déformation."""
    if fichier is None or not fichier.filename:
        return None
    contenu = fichier.stream.read(TAILLE_MAX + 1)
    if not contenu or len(contenu) > TAILLE_MAX:
        raise ValueError("Choisis une carte de 15 Mo maximum.")
    from utils.images_cartes_natales import image_de_travail
    image, _ = image_de_travail(contenu, page=1)
    image.thumbnail((2400, 2400))
    image.info.clear()
    sortie = BytesIO()
    image.save(sortie, format="PNG", optimize=True)
    contenu = sortie.getvalue()
    if len(contenu) > TAILLE_MAX:
        raise ValueError("L’image convertie dépasse 15 Mo. Réduis sa taille avant de l’ajouter.")
    return {"contenu": contenu, "largeur": image.width, "hauteur": image.height}


def enregistrer_carte(nature, date_utc, action, *, nouvel_import=None, retirer=False):
    """Même transaction et verrou de révision que le texte de la fiche."""
    if not stockage_pret():
        if nouvel_import or retirer:
            raise ValueError(MESSAGE_STOCKAGE)
        return
    cartes = CarteLunaison.query.filter_by(type_lunaison=nature, date_utc=date_utc)
    if retirer or nouvel_import:
        cartes.filter_by(brouillon_actif=True).update({"brouillon_actif": False}, synchronize_session="fetch")
    if nouvel_import:
        db.session.add(CarteLunaison(id=token_hex(32), type_lunaison=nature,
            date_utc=date_utc, brouillon_actif=True, version_validee=False, **nouvel_import))
        db.session.flush()
    if action in {"valider", "retirer"}:
        cartes.filter_by(version_validee=True).update({"version_validee": False}, synchronize_session="fetch")
        if action == "valider":
            actuelle = cartes.filter_by(brouillon_actif=True).first()
            if actuelle is not None:
                actuelle.version_validee = True
                actuelle.publiee_le = actuelle.publiee_le or utcnow()


def reference_carte(nature, date_utc):
    if not stockage_pret():
        return None
    carte = CarteLunaison.query.filter_by(type_lunaison=nature, date_utc=date_utc,
                                         version_validee=True).first()
    return {"id": carte.id, "largeur": carte.largeur, "hauteur": carte.hauteur} if carte else None


def origine_publique():
    # Même contrôle de domaine et même configuration que les liens des mails.
    from utils.journal_mails import lien_journal_mail
    return lien_journal_mail("origine").split("/mon-espace/", 1)[0]


def ajouter_carte_au_mail(mail, html, texte, *, pour_envoi=True):
    """Utilise la carte figée avec la source du mail, jamais le brouillon courant."""
    if mail.nature not in {"nouvelle_lune", "pleine_lune"}:
        return html, texte
    try:
        source = json.loads(mail.source_lunaison_json or "null") or {}
        carte = source.get("carte") or {}
        identifiant = carte.get("id", "")
    except (TypeError, ValueError, AttributeError):
        raise ValueError("La référence de la carte du mail est illisible.") from None
    if not identifiant:
        return html, texte
    if not isinstance(identifiant, str) or not re.fullmatch(r"[0-9a-f]{64}", identifiant):
        raise ValueError("La référence de la carte du mail est invalide.")
    instant = mail.instant_evenement
    instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)
    image = db.session.get(CarteLunaison, identifiant)
    if (image is None or image.publiee_le is None or image.type_lunaison != mail.nature
            or image.date_utc != instant.date().isoformat()):
        raise ValueError("La carte validée de ce mail n’est plus disponible.")
    origine = origine_publique() if pour_envoi else ""
    url = origine + "/cartes-lunaisons/" + identifiant + ".png"
    espace = origine + "/mon-espace/lunaisons/" + mail.nature + "/" + image.date_utc
    libelle = "Nouvelle Lune" if mail.nature == "nouvelle_lune" else "Pleine Lune"
    titre = "Carte de la " + libelle + " du " + instant.strftime("%d.%m.%Y")
    marque = "<!-- carte-lunaison:" + identifiant + " -->"
    bloc = (marque + '<figure style="margin:28px 0;text-align:center">'
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{escape(url, quote=True)}" alt="{escape(titre, quote=True)}" width="640" '
            'style="display:block;width:100%;max-width:640px;height:auto;margin:0 auto;border:0"></a>'
            f'<figcaption style="font:15px/1.6 Arial,sans-serif;margin-top:12px">{escape(titre)}'
            f' · <a href="{escape(espace, quote=True)}">Retrouver la lunaison dans mon espace</a>'
            '</figcaption></figure>')
    if marque not in html:
        ouverture = re.search(r"<body\b[^>]*>", html, flags=re.I)
        html = html[:ouverture.end()] + bloc + html[ouverture.end():] if ouverture else bloc + html
    if url not in texte:
        texte = texte.rstrip() + "\n\n" + titre + "\n" + url + "\nDans mon espace : " + espace
    return html, texte
