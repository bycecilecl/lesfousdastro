"""Copie privée du journal et du Labo. Aucun import d’application ni client IA.

L’export utilise une connexion de lecture ; l’import écrit uniquement dans
le journal SQLite local, avec sauvegarde et transaction avant toute insertion.
"""
from datetime import date, datetime, time, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3

VERSION = 1
MAX_OCTETS = 50 * 1024 * 1024
MAX_LIGNES = 100000
RACINE = Path(__file__).resolve().parents[1]
BASE_LOCALE = RACINE / "instance" / "journal.db"
DOSSIER_PRIVE = RACINE / "instance" / "transferts_espace"
CHAMPS_PROFIL = (
    "prenom", "date_naissance", "heure_naissance", "ville_naissance", "fuseau_horaire",
    "latitude", "longitude", "theme_natal", "date_calcul_theme",
)
CHAMPS = {
    "entrees_journal": (
        "id", "date_observation", "est_periode", "date_fin_periode", "niveau_energie",
        "emotions", "situation", "reaction_automatique", "choix_conscient", "notes_libres",
        "transits_actifs", "date_creation", "date_modification",
    ),
    "analyses_personnelles": (
        "id", "type_analyse", "titre", "statut", "date_generation", "notes_personnelles",
        "entree_journal_id", "date_creation", "date_modification",
    ),
    "mecanismes_exploration": (
        "id", "analyse_id", "titre", "extrait_source", "hypothese", "effets_possibles",
        "ressenti", "statut", "indices_pour", "elements_contraires", "situations_observees",
        "piste_experimentation", "date_creation", "date_modification",
    ),
    "observations_mecanisme": (
        "id", "mecanisme_id", "entree_journal_id", "date_observation", "situation",
        "reaction_automatique", "indice_pour", "element_contraire", "reaction_testee",
        "resultat_obtenu", "notes_libres", "date_creation", "date_modification",
    ),
    "decodages_observations_mecanisme": (
        "id", "observation_id", "reponses", "revision", "date_creation", "date_modification",
    ),
}
LIENS = {
    "analyses_personnelles": {"entree_journal_id": "entrees_journal"},
    "mecanismes_exploration": {"analyse_id": "analyses_personnelles"},
    "observations_mecanisme": {"mecanisme_id": "mecanismes_exploration", "entree_journal_id": "entrees_journal"},
    "decodages_observations_mecanisme": {"observation_id": "observations_mecanisme"},
}


def _json(texte):
    return json.dumps(texte, ensure_ascii=False, sort_keys=True, default=lambda v: v.isoformat())


def _empreinte(valeur):
    return hashlib.sha256(_json(valeur).encode()).hexdigest()


def exporter_compte(utilisateur, origine):
    """Exporte uniquement le propriétaire demandé par la route authentifiée."""
    from sqlalchemy import select
    from extensions import db
    from models.espace_personnel import (
        AnalysePersonnelle, DecodageObservationMecanisme, EntreeJournal,
        MecanismeExploration, ObservationMecanisme, ProfilAstral,
    )
    tables = {m.__tablename__: m.__table__ for m in (
        AnalysePersonnelle, DecodageObservationMecanisme, EntreeJournal,
        MecanismeExploration, ObservationMecanisme,
    )}
    a, m, o = (tables[n] for n in ("analyses_personnelles", "mecanismes_exploration", "observations_mecanisme"))
    moteur = db.session.get_bind(mapper=EntreeJournal)
    with moteur.connect() as connexion:
        if moteur.dialect.name == "postgresql":
            connexion = connexion.execution_options(isolation_level="REPEATABLE READ")
        with connexion.begin():
            if moteur.dialect.name == "postgresql":
                connexion.exec_driver_sql("SET TRANSACTION READ ONLY")
            elif moteur.dialect.name == "sqlite":
                connexion.exec_driver_sql("BEGIN")
            def lignes(nom, requete):
                return [dict(r) for r in connexion.execute(requete.with_only_columns(
                    *(tables[nom].c[c] for c in CHAMPS[nom])
                ).order_by(tables[nom].c.id)).mappings()]
            donnees = {}
            t = tables["entrees_journal"]
            donnees[t.name] = lignes(t.name, select(t).where(t.c.utilisateur_id == utilisateur.id))
            donnees[m.name] = lignes(m.name, select(m).join(a, a.c.id == m.c.analyse_id)
                                    .where(a.c.utilisateur_id == utilisateur.id))
            ids_analyses = {r["analyse_id"] for r in donnees[m.name]}
            donnees[a.name] = lignes(a.name, select(a).where(a.c.utilisateur_id == utilisateur.id, a.c.id.in_(ids_analyses)))
            donnees[o.name] = lignes(o.name, select(o).join(m, m.c.id == o.c.mecanisme_id)
                                    .join(a, a.c.id == m.c.analyse_id).where(a.c.utilisateur_id == utilisateur.id))
            d = tables["decodages_observations_mecanisme"]
            donnees[d.name] = lignes(d.name, select(d).join(o, o.c.id == d.c.observation_id)
                                    .join(m, m.c.id == o.c.mecanisme_id).join(a, a.c.id == m.c.analyse_id)
                                    .where(a.c.utilisateur_id == utilisateur.id))
            profil = ProfilAstral.__table__
            profil = connexion.execute(select(*(profil.c[c] for c in CHAMPS_PROFIL))
                                      .where(profil.c.utilisateur_id == utilisateur.id)).mappings().first()
            paquet = {
                "format": "fda-journal-labo", "version": VERSION,
                "exporte_le": datetime.now(timezone.utc).isoformat(),
                "source": {"origine": origine, "compte_id": utilisateur.id, "email": utilisateur.email},
                "profil_natal": dict(profil) if profil else None, "donnees": donnees,
            }
    # Un épisode ancien peut survivre à la suppression de sa note du journal.
    ids_notes = {r["id"] for r in donnees["entrees_journal"]}
    for nom in ("analyses_personnelles", "observations_mecanisme"):
        for ligne in donnees[nom]:
            if ligne["entree_journal_id"] not in ids_notes:
                ligne["entree_journal_id"] = None
    resultat = _json(paquet).encode("utf-8")
    if len(resultat) > MAX_OCTETS:
        raise ValueError("Cet export dépasse 50 Mo. Aucun fichier partiel n’a été préparé.")
    return resultat


def _id(valeur):
    return type(valeur) is int and valeur > 0


def _valider_ligne(ligne, colonnes):
    if not isinstance(ligne, dict) or set(ligne) != set(colonnes):
        raise ValueError("Structure du fichier incompatible. Utilise l’export du profil.")
    for cle, valeur in ligne.items():
        if valeur is None:
            continue
        if cle == "id" or cle.endswith("_id") or cle == "revision":
            if not _id(valeur):
                raise ValueError("Identifiant ou révision invalide dans le fichier.")
        elif cle.startswith("date_"):
            try:
                (date.fromisoformat if cle in {"date_naissance", "date_fin_periode"} else datetime.fromisoformat)(valeur)
            except (TypeError, ValueError):
                raise ValueError("Date invalide dans le fichier.") from None
        elif cle == "heure_naissance":
            try:
                time.fromisoformat(valeur)
            except (TypeError, ValueError):
                raise ValueError("Heure de naissance invalide.") from None
        elif cle == "est_periode":
            if type(valeur) is not bool:
                raise ValueError("Type de période invalide.")
        elif cle == "niveau_energie":
            if type(valeur) is not int or not 1 <= valeur <= 10:
                raise ValueError("Niveau d’énergie invalide.")
        elif cle in {"latitude", "longitude"}:
            if type(valeur) not in {int, float} or not -180 <= valeur <= 180:
                raise ValueError("Coordonnée invalide.")
        elif not isinstance(valeur, str):
            raise ValueError("Texte invalide dans le fichier.")
        if cle in {"theme_natal", "transits_actifs", "reponses"}:
            try:
                donnees_json = json.loads(valeur)
            except (TypeError, ValueError):
                raise ValueError("Données JSON illisibles.") from None
            if not isinstance(donnees_json, dict):
                raise ValueError("Données JSON incompatibles.")


def lire_export(contenu):
    if not contenu or len(contenu) > MAX_OCTETS:
        raise ValueError("Le fichier est vide ou dépasse 50 Mo.")
    try:
        paquet = json.loads(contenu)
    except (ValueError, UnicodeError):
        raise ValueError("Le fichier n’est pas un export JSON lisible.") from None
    if not isinstance(paquet, dict) or paquet.get("format") != "fda-journal-labo" or paquet.get("version") != VERSION:
        raise ValueError("Format d’export incompatible.")
    source = paquet.get("source")
    if (not isinstance(source, dict) or source.get("origine") not in {"local", "lesfousdastro.fr"}
            or not _id(source.get("compte_id")) or not isinstance(source.get("email"), str) or not source["email"].strip()):
        raise ValueError("Le compte source n’est pas identifiable.")
    donnees = paquet.get("donnees")
    if not isinstance(donnees, dict) or set(donnees) != set(CHAMPS):
        raise ValueError("Le fichier ne contient pas les cinq collections attendues.")
    ids, nombre = {}, 0
    for nom, colonnes in CHAMPS.items():
        lignes = donnees[nom]
        if not isinstance(lignes, list):
            raise ValueError("Collection invalide.")
        nombre += len(lignes)
        if nombre > MAX_LIGNES:
            raise ValueError("L’export contient trop d’éléments.")
        ids[nom] = set()
        for ligne in lignes:
            _valider_ligne(ligne, colonnes)
            if not _id(ligne["id"]) or ligne["id"] in ids[nom]:
                raise ValueError("Identifiant manquant ou répété.")
            ids[nom].add(ligne["id"])
    for nom, liens in LIENS.items():
        for ligne in donnees[nom]:
            for cle, parent in liens.items():
                if ligne[cle] is None and cle == "entree_journal_id":
                    continue
                if ligne[cle] not in ids[parent]:
                    raise ValueError("Un lien entre notes, analyses ou mécanismes est incomplet.")
    observations_decodees = [r["observation_id"] for r in donnees["decodages_observations_mecanisme"]]
    if len(observations_decodees) != len(set(observations_decodees)):
        raise ValueError("Plusieurs décodages pour le même épisode.")
    profil = paquet.get("profil_natal")
    if profil is not None:
        _valider_ligne(profil, CHAMPS_PROFIL)
        if any(not profil[c] for c in ("prenom", "date_naissance", "heure_naissance", "ville_naissance", "fuseau_horaire")):
            raise ValueError("Les données natales sont incomplètes.")
    return paquet


def sauvegarder_local():
    """Sauvegarde SQLite cohérente incluant un éventuel WAL, sans copier le fichier à chaud."""
    if not BASE_LOCALE.is_file():
        raise ValueError("La base locale du journal est introuvable.")
    DOSSIER_PRIVE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(DOSSIER_PRIVE, 0o700)
    cible = DOSSIER_PRIVE / ("journal-avant-import-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
    with closing(sqlite3.connect(BASE_LOCALE.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(cible)) as destination:
            os.chmod(cible, 0o600)
            source.backup(destination)
    return cible


def _valeur_sql(cle, valeur):
    if valeur is not None and cle.startswith("date_") and cle not in {"date_naissance", "date_fin_periode"}:
        instant = datetime.fromisoformat(valeur)
        if instant.tzinfo:
            instant = instant.astimezone(timezone.utc).replace(tzinfo=None)
        return instant.isoformat(sep=" ")
    return valeur


def importer_local(contenu, utilisateur_id=None):
    """Ajoute une copie, sans écraser les épisodes existants ni importer d’authentification."""
    if any(os.getenv(cle) for cle in ("RAILWAY_ENVIRONMENT_ID", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")):
        raise ValueError("L’import est réservé au dossier local, jamais à Railway.")
    paquet = lire_export(contenu)
    if not BASE_LOCALE.is_file():
        raise ValueError("La base locale du journal est introuvable.")
    resultat = {"ajoutes": {}, "deja_importes": {}, "versions_differentes_conservees": {}, "profil_natal_copie": False}
    with closing(sqlite3.connect(BASE_LOCALE.as_uri() + "?mode=rw", uri=True, timeout=20)) as connexion, connexion:
        connexion.row_factory = sqlite3.Row
        connexion.execute("BEGIN IMMEDIATE")
        # Vérification du schéma avant sauvegarde et avant tout changement.
        for nom, colonnes in {**CHAMPS, "profil_astral": CHAMPS_PROFIL}.items():
            presentes = {r["name"] for r in connexion.execute(f'PRAGMA table_info("{nom}")')}
            if not set(colonnes) <= presentes:
                raise ValueError("Le schéma local doit être mis à jour avant l’import : " + nom)
        if utilisateur_id is None:
            compte = connexion.execute("SELECT id, email FROM utilisateurs_espace WHERE lower(trim(email)) = ? AND actif = 1 AND est_administratrice = 1",
                                       (paquet["source"]["email"].strip().lower(),)).fetchone()
        else:
            compte = connexion.execute("SELECT id, email FROM utilisateurs_espace WHERE id = ? AND actif = 1 AND est_administratrice = 1", (utilisateur_id,)).fetchone()
        if not compte or (compte["email"] or "").strip().lower() != paquet["source"]["email"].strip().lower():
            raise ValueError("L’adresse email de l’export doit correspondre à ton compte administratrice local actif.")
        utilisateur_id = compte["id"]
        # La connexion séparée de sauvegarde lit la base pendant que BEGIN IMMEDIATE bloque les autres écritures.
        resultat["sauvegarde"] = str(sauvegarder_local())
        connexion.execute("""CREATE TABLE IF NOT EXISTS imports_espace_liaisons (
            origine TEXT NOT NULL, compte_source INTEGER NOT NULL, compte_local INTEGER NOT NULL,
            entite TEXT NOT NULL, id_source INTEGER NOT NULL, id_local INTEGER NOT NULL, empreinte TEXT NOT NULL,
            PRIMARY KEY (origine, compte_source, compte_local, entite, id_source)
        )""")
        origine, compte_source = paquet["source"]["origine"], paquet["source"]["compte_id"]
        correspondances = {}
        for nom, colonnes in CHAMPS.items():
            correspondances[nom] = {}
            resultat["ajoutes"][nom] = resultat["deja_importes"][nom] = resultat["versions_differentes_conservees"][nom] = 0
            for ligne in paquet["donnees"][nom]:
                cle = (origine, compte_source, utilisateur_id, nom, ligne["id"])
                existant = connexion.execute("SELECT id_local, empreinte FROM imports_espace_liaisons WHERE origine=? AND compte_source=? AND compte_local=? AND entite=? AND id_source=?", cle).fetchone()
                empreinte = _empreinte(ligne)
                if existant:
                    if not connexion.execute(f'SELECT 1 FROM "{nom}" WHERE id=?', (existant["id_local"],)).fetchone():
                        raise ValueError("Une copie précédemment importée a été supprimée en local. Import arrêté sans écrasement.")
                    nouvel_id = existant["id_local"]
                    resultat["deja_importes"][nom] += 1
                    if existant["empreinte"] != empreinte:
                        resultat["versions_differentes_conservees"][nom] += 1
                else:
                    valeurs = {c: _valeur_sql(c, ligne[c]) for c in colonnes if c != "id"}
                    for champ, parent in LIENS.get(nom, {}).items():
                        valeurs[champ] = correspondances[parent][ligne[champ]] if ligne[champ] is not None else None
                    if nom in {"entrees_journal", "analyses_personnelles"}:
                        valeurs["utilisateur_id"] = utilisateur_id
                    if nom == "entrees_journal":
                        valeurs.update(cycle_lunaire_id=None, enjeu_periode_id=None)
                    elif nom == "analyses_personnelles":
                        valeurs.update(cycle_solaire_id=None, chemin_resultat=None)
                    champs = ','.join('"' + c + '"' for c in valeurs)
                    nouvel_id = connexion.execute(f'INSERT INTO "{nom}" ({champs}) VALUES ({",".join("?" for _ in valeurs)})', tuple(valeurs.values())).lastrowid
                    connexion.execute("INSERT INTO imports_espace_liaisons VALUES (?,?,?,?,?,?,?)", (*cle, nouvel_id, empreinte))
                    resultat["ajoutes"][nom] += 1
                correspondances[nom][ligne["id"]] = nouvel_id
        profil = paquet["profil_natal"]
        if profil and profil.get("theme_natal"):
            valeurs = {c: _valeur_sql(c, profil[c]) for c in CHAMPS_PROFIL}
            valeurs["date_modification"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
            present = connexion.execute("SELECT id FROM profil_astral WHERE utilisateur_id=?", (utilisateur_id,)).fetchone()
            if present:
                affectations = ','.join('"' + c + '"=?' for c in valeurs)
                connexion.execute(f'UPDATE profil_astral SET {affectations} WHERE utilisateur_id=?', (*valeurs.values(), utilisateur_id))
            else:
                valeurs.update(utilisateur_id=utilisateur_id, date_creation=valeurs["date_modification"])
                champs = ','.join('"' + c + '"' for c in valeurs)
                connexion.execute(f'INSERT INTO profil_astral ({champs}) VALUES ({",".join("?" for _ in valeurs)})', tuple(valeurs.values()))
            resultat["profil_natal_copie"] = True
        connexion.commit()
    return resultat
