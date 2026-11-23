"""Transfert explicite d’une lecture collective et de sa carte, sans Flask ni IA."""
import argparse
import base64
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import struct

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text


def utc(valeur):
    instant = datetime.fromisoformat(valeur) if isinstance(valeur, str) else valeur
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def lire_publication(chemin):
    with chemin.open('rb') as fichier:
        brut = fichier.read(23 * 1024 * 1024 + 1)
    if len(brut) > 23 * 1024 * 1024:
        raise ValueError('Le paquet de publication est trop volumineux.')
    publication = json.loads(brut)
    if publication.get('format') != 'fda-lunaison-validee-v1':
        raise ValueError('Format de publication incompatible.')
    if publication.get('nature') not in {'nouvelle_lune', 'pleine_lune'}:
        raise ValueError('Type de lunaison invalide.')
    jour = date.fromisoformat(publication['date_utc'])
    if utc(publication['instant_utc']).date() != jour:
        raise ValueError('La date ne correspond pas à l’instant de la lunaison.')
    if not isinstance(publication['titre'], str) or len(publication['titre']) > 200:
        raise ValueError('Titre invalide.')
    if not isinstance(publication['texte'], str) or not publication['texte'].strip():
        raise ValueError('Le texte validé est vide.')
    utc(publication['validee_le'])
    carte = publication['carte']
    if not re.fullmatch(r'[0-9a-f]{64}', carte['id']):
        raise ValueError('Identifiant de carte invalide.')
    contenu = base64.b64decode(carte['png_base64'], validate=True)
    if (len(contenu) > 15 * 1024 * 1024 or not contenu.startswith(b'\x89PNG\r\n\x1a\n')
            or len(contenu) < 24 or contenu[12:16] != b'IHDR'
            or hashlib.sha256(contenu).hexdigest() != carte['sha256']):
        raise ValueError('Le fichier PNG ne correspond pas à son empreinte.')
    dimensions = struct.unpack('>II', contenu[16:24])
    if dimensions != (carte['largeur'], carte['hauteur']) or not all(0 < v <= 2400 for v in dimensions):
        raise ValueError('Dimensions de carte incompatibles.')
    return publication, contenu


def sauvegarder(chemin, analyse, cartes):
    donnees = {'format': 'fda-lunaison-avant-import-v1',
               'sauvegarde_le': datetime.now(timezone.utc).isoformat(),
               'analyse': dict(analyse) if analyse else None, 'cartes': [dict(c) for c in cartes]}
    # Aucun secret de connexion et aucune donnée de compte dans cette sauvegarde.
    def encoder(valeur):
        if isinstance(valeur, (date, datetime)):
            return valeur.isoformat()
        if isinstance(valeur, (bytes, memoryview)):
            return {'base64': base64.b64encode(bytes(valeur)).decode('ascii')}
        raise TypeError('Valeur non sérialisable dans la sauvegarde.')
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, 'w') as fichier:
        json.dump(donnees, fichier, ensure_ascii=False, default=encoder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fichier', type=Path, required=True)
    parser.add_argument('--production', action='store_true', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sauvegarde', type=Path)
    parser.add_argument('--variable-url', default='DATABASE_PUBLIC_URL')
    options = parser.parse_args()
    publication, contenu = lire_publication(options.fichier)
    uri = os.getenv(options.variable_url, '')
    if not uri.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg')):
        raise ValueError('Une connexion PostgreSQL de production est requise. Aucun secret affiché.')
    if options.apply and not options.sauvegarde:
        raise ValueError('Indique un fichier de sauvegarde avant d’appliquer le transfert.')
    moteur = create_engine(uri.replace('postgres://', 'postgresql://', 1), echo=False,
                           hide_parameters=True, connect_args={'connect_timeout': 15})
    try:
        with moteur.begin() as connexion:
            if options.apply:
                connexion.execute(text("SET LOCAL lock_timeout = '15s'"))
                connexion.execute(text("SET LOCAL statement_timeout = '90s'"))
                connexion.execute(text('SELECT pg_advisory_xact_lock(2026112303)'))
            else:
                connexion.execute(text('SET TRANSACTION READ ONLY'))
            metadata = MetaData()
            analyses = Table('analyses_lunaisons', metadata, autoload_with=connexion)
            requete = select(analyses).where(analyses.c.type_lunaison == publication['nature'],
                                             analyses.c.date_utc == publication['date_utc'])
            if options.apply:
                requete = requete.with_for_update()
            actuelle = connexion.execute(requete).mappings().first()
            cartes = Table('cartes_lunaisons', metadata, autoload_with=connexion) if inspect(connexion).has_table('cartes_lunaisons') else None
            presentes = list(connexion.execute(select(cartes).where(
                cartes.c.type_lunaison == publication['nature'], cartes.c.date_utc == publication['date_utc']
            )).mappings()) if cartes is not None else []
            publiee = next((c for c in presentes if c['version_validee']), None)
            brouillon = next((c for c in presentes if c['brouillon_actif']), None)
            identifiant = publication['carte']['id']
            identique = bool(actuelle and actuelle['validee_le'] and actuelle['titre_valide'] == publication['titre']
                             and actuelle['texte_valide'] == publication['texte'])
            if (actuelle and actuelle['validee_le'] and utc(actuelle['validee_le']) > utc(publication['validee_le'])
                    and not identique):
                raise ValueError('Une lecture plus récente existe en production. Aucun remplacement effectué.')
            if publiee and publiee['id'] != identifiant and publiee['publiee_le'] and utc(publiee['publiee_le']) > utc(publication['validee_le']):
                raise ValueError('Une autre carte plus récente est publiée. Aucun remplacement effectué.')
            existante = connexion.execute(select(cartes).where(cartes.c.id == identifiant)).mappings().first() if cartes is not None else None
            if existante and (existante['type_lunaison'] != publication['nature']
                or existante['date_utc'] != publication['date_utc'] or bytes(existante['contenu']) != contenu):
                raise ValueError('L’identifiant de carte existe avec un contenu différent. Aucun remplacement.')
            print('Publication ciblée :', publication['nature'], publication['date_utc'], flush=True)
            print('Carte :', publication['carte']['largeur'], '×', publication['carte']['hauteur'], 'px ;', len(contenu), 'octets.', flush=True)
            if identique and publiee and publiee['id'] == identifiant:
                print('Lecture et carte déjà publiées. Aucune modification.', flush=True)
                return
            if not options.apply:
                print('Transfert à appliquer ; stockage des cartes :', 'présent' if cartes is not None else 'créé par le prochain déploiement.', flush=True)
                return
            if cartes is None:
                raise ValueError('Déploie d’abord la migration du stockage des cartes.')
            sauvegarder(options.sauvegarde, actuelle, presentes)
            maintenant = datetime.now(timezone.utc)
            valeurs = dict(titre_valide=publication['titre'], texte_valide=publication['texte'],
                validee_le=maintenant, revision_validee=(actuelle['revision_validee'] if actuelle else 0) + 1,
                revision=(actuelle['revision'] if actuelle else 0) + 1, date_modification=maintenant)
            # Conserve un éventuel brouillon distinct déjà présent en production.
            if not actuelle or (actuelle['titre'] == (actuelle['titre_valide'] or '') and actuelle['texte'] == (actuelle['texte_valide'] or '')):
                valeurs.update(titre=publication['titre'], texte=publication['texte'])
            if actuelle:
                connexion.execute(analyses.update().where(analyses.c.id == actuelle['id']).values(**valeurs))
            else:
                connexion.execute(analyses.insert().values(type_lunaison=publication['nature'], date_utc=publication['date_utc'],
                    instant_utc=utc(publication['instant_utc']), date_creation=maintenant, **valeurs))
            condition = (cartes.c.type_lunaison == publication['nature']) & (cartes.c.date_utc == publication['date_utc'])
            connexion.execute(cartes.update().where(condition, cartes.c.version_validee.is_(True)).values(version_validee=False))
            reprendre_brouillon = brouillon is None or brouillon['id'] == identifiant or (publiee and brouillon['id'] == publiee['id'])
            if reprendre_brouillon:
                connexion.execute(cartes.update().where(condition, cartes.c.brouillon_actif.is_(True)).values(brouillon_actif=False))
            valeur_carte = dict(version_validee=True, brouillon_actif=bool(reprendre_brouillon),
                                publiee_le=(existante['publiee_le'] if existante else None) or maintenant)
            if existante:
                connexion.execute(cartes.update().where(cartes.c.id == identifiant).values(**valeur_carte))
            else:
                connexion.execute(cartes.insert().values(id=identifiant, type_lunaison=publication['nature'],
                    date_utc=publication['date_utc'], contenu=contenu, largeur=publication['carte']['largeur'],
                    hauteur=publication['carte']['hauteur'], date_creation=maintenant, **valeur_carte))
        print('Lecture et carte publiées en production. Sauvegarde :', options.sauvegarde, flush=True)
        print('Aucun compte modifié, aucun appel IA et aucun mail lancé.', flush=True)
    finally:
        moteur.dispose()


if __name__ == '__main__':
    try:
        main()
    except ValueError as erreur:
        raise SystemExit(str(erreur))
    except Exception:
        raise SystemExit('Transfert interrompu, transaction annulée. Aucun secret de connexion affiché.')
