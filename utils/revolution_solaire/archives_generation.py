"""Archivage privé et verrou interprocessus des générations RS locales."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import hashlib
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[2] / 'instance' / 'generations_rs'


class GenerationEnCours(RuntimeError):
    pass


class GenerationARevoir(RuntimeError):
    pass


class GenerationAbsente(RuntimeError):
    pass


def identifiant_demande(demande):
    contenu = json.dumps(demande, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(contenu.encode()).hexdigest()


def ecrire_json(dossier, nom, valeur):
    """Écriture atomique : une interruption ne laisse pas de JSON partiel."""
    dossier = Path(dossier)
    fd, temporaire = tempfile.mkstemp(prefix='.archive-', dir=dossier)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fichier:
            json.dump(valeur, fichier, ensure_ascii=False, indent=2, allow_nan=False)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, dossier / nom)
    finally:
        if os.path.exists(temporaire):
            os.unlink(temporaire)


def lire_json(dossier, nom):
    chemin = Path(dossier) / nom
    return json.loads(chemin.read_text()) if chemin.exists() else None


@contextmanager
def verrou_demande(demande, racine=None):
    cle = identifiant_demande(demande)
    racine = Path(racine) if racine is not None else ROOT
    racine.mkdir(parents=True, exist_ok=True, mode=0o700)
    dossier = racine / cle
    dossier.mkdir(exist_ok=True, mode=0o700)
    fd = os.open(dossier / 'verrou', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'a') as verrou:
        try:
            fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GenerationEnCours('Cette révolution solaire est déjà en cours. Aucun nouvel appel IA lancé.') from error
        try:
            yield dossier
        finally:
            fcntl.flock(verrou, fcntl.LOCK_UN)


def texte_archive(dossier, prompt, appel, erreur_troncature):
    reponse = lire_json(dossier, 'reponse.json')
    if reponse is not None:
        return reponse['texte']
    etat = lire_json(dossier, 'appel.json')
    if etat is not None:
        raise GenerationARevoir(
            'La tentative précédente nécessite une vérification (réponse tronquée ou résultat incertain). '
            'Aucun nouvel appel IA n’a été lancé. Les éléments reçus sont archivés.'
        )
    # Marquer AVANT le réseau : après un arrêt du processus, ne pas refacturer.
    ecrire_json(dossier, 'appel.json', {'statut': 'en_cours'})
    try:
        texte = appel(prompt)
        if not texte or not texte.strip():
            raise ValueError('Réponse IA vide.')
        ecrire_json(dossier, 'reponse.json', {'texte': texte})
    except erreur_troncature as error:
        ecrire_json(dossier, 'reponse_partielle.json', {'texte': error.texte_partiel})
        ecrire_json(dossier, 'appel.json', {'statut': 'tronque'})
        raise GenerationARevoir('La réponse tronquée est sauvegardée. Aucune relance automatique.') from error
    except Exception as error:
        # Ne pas archiver str(error), qui peut contenir des informations sensibles.
        ecrire_json(dossier, 'appel.json', {'statut': 'a_verifier', 'type_erreur': type(error).__name__})
        raise
    ecrire_json(dossier, 'appel.json', {'statut': 'recu'})
    return texte
