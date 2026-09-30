"""Restaure un export privé du labo dans le compte connecté, avec remappage des IDs."""

import base64
from datetime import datetime
import hashlib
from pathlib import Path

from sqlalchemy import DateTime

from extensions import db
from models.espace_personnel import (
    AnalysePersonnelle, CycleLunaire, CycleSolaire, DroitAnalyseAchetee,
    EmailCycleAbonnement, EnjeuPeriode, EntreeJournal, FichierAnalyse,
    MecanismeExploration, ObservationMecanisme, SectionAnalyse,
    SuggestionMecanisme,
)


TABLES = {
    "cycles_solaires": CycleSolaire,
    "cycles_lunaires": CycleLunaire,
    "emails_cycles_abonnement": EmailCycleAbonnement,
    "analyses_personnelles": AnalysePersonnelle,
    "droits_analyses_achetees": DroitAnalyseAchetee,
    "entrees_journal": EntreeJournal,
    "sections_analyse": SectionAnalyse,
    "enjeux_periode": EnjeuPeriode,
    "suggestions_mecanisme": SuggestionMecanisme,
    "mecanismes_exploration": MecanismeExploration,
    "observations_mecanisme": ObservationMecanisme,
}


def _date(valeur):
    return datetime.fromisoformat(valeur) if valeur else None


def _nouvel_objet(modele, source, remplacements):
    donnees = {}
    for colonne in modele.__table__.columns:
        nom = colonne.name
        if nom == "id" or nom not in source:
            continue
        valeur = source[nom]
        if isinstance(colonne.type, DateTime) and valeur is not None:
            valeur = _date(valeur)
        donnees[nom] = valeur
    donnees.update(remplacements)
    objet = modele(**donnees)
    db.session.add(objet)
    db.session.flush()
    return objet


def _identifiant(mappage, ancien, libelle):
    if ancien is None:
        return None
    if ancien not in mappage:
        raise ValueError(f"Référence {libelle} absente de cet export.")
    return mappage[ancien]


def importer_archives(paquet, *, email, utilisateur_id, profil_id):
    """Importe dans une transaction ; appelant responsable du commit/rollback."""
    if paquet.get("version") != 1 or paquet.get("email", "").strip().lower() != email.lower():
        raise ValueError("Ce fichier ne correspond pas au compte connecté.")
    donnees = paquet.get("donnees")
    pdfs = paquet.get("pdfs")
    if not isinstance(donnees, dict) or not isinstance(pdfs, dict):
        raise ValueError("Export incomplet.")
    for nom in TABLES:
        if not isinstance(donnees.get(nom), list) or len(donnees[nom]) > 500:
            raise ValueError("Une section de l’export est absente ou trop volumineuse.")
    if AnalysePersonnelle.query.filter_by(utilisateur_id=utilisateur_id).first() is not None:
        raise ValueError("Des analyses sont déjà présentes ; cet import complet ne doit pas les écraser.")
    if EntreeJournal.query.filter_by(utilisateur_id=utilisateur_id).first() is not None:
        raise ValueError("Le journal contient déjà des notes ; cet import complet ne doit pas les écraser.")

    solar, lunar, analyses, sections, enjeux, mecanismes, entrees = {}, {}, {}, {}, {}, {}, {}
    for ligne in donnees["cycles_solaires"]:
        existant = CycleSolaire.query.filter_by(profil_id=profil_id, cle_cycle=ligne["cle_cycle"]).first()
        objet = existant or _nouvel_objet(CycleSolaire, ligne, {"profil_id": profil_id})
        solar[ligne["id"]] = objet.id
    for ligne in donnees["cycles_lunaires"]:
        existant = CycleLunaire.query.filter_by(profil_id=profil_id, cle_cycle=ligne["cle_cycle"]).first()
        nouvelle_rs = _identifiant(solar, ligne.get("cycle_solaire_id"), "RS")
        objet = existant or _nouvel_objet(CycleLunaire, ligne, {
            "profil_id": profil_id, "cycle_solaire_id": nouvelle_rs,
        })
        if existant and existant.cycle_solaire_id is None:
            existant.cycle_solaire_id = nouvelle_rs
        lunar[ligne["id"]] = objet.id

    analyses_journal = []
    for ligne in donnees["analyses_personnelles"]:
        objet = _nouvel_objet(AnalysePersonnelle, ligne, {
            "utilisateur_id": utilisateur_id, "entree_journal_id": None,
        })
        analyses[ligne["id"]] = objet.id
        if ligne.get("entree_journal_id") is not None:
            analyses_journal.append((objet, ligne["entree_journal_id"]))
    for ligne in donnees["sections_analyse"]:
        objet = _nouvel_objet(SectionAnalyse, ligne, {
            "analyse_id": _identifiant(analyses, ligne["analyse_id"], "analyse"),
        })
        sections[ligne["id"]] = objet.id
    for ligne in donnees["enjeux_periode"]:
        objet = _nouvel_objet(EnjeuPeriode, ligne, {
            "analyse_id": _identifiant(analyses, ligne["analyse_id"], "analyse"),
        })
        enjeux[ligne["id"]] = objet.id
    for ligne in donnees["mecanismes_exploration"]:
        objet = _nouvel_objet(MecanismeExploration, ligne, {
            "analyse_id": _identifiant(analyses, ligne["analyse_id"], "analyse"),
        })
        mecanismes[ligne["id"]] = objet.id
    for ligne in donnees["suggestions_mecanisme"]:
        _nouvel_objet(SuggestionMecanisme, ligne, {
            "analyse_id": _identifiant(analyses, ligne["analyse_id"], "analyse"),
            "section_id": _identifiant(sections, ligne.get("section_id"), "section"),
        })
    for ligne in donnees["entrees_journal"]:
        objet = _nouvel_objet(EntreeJournal, ligne, {
            "utilisateur_id": utilisateur_id,
            "cycle_lunaire_id": _identifiant(lunar, ligne.get("cycle_lunaire_id"), "RL"),
            "enjeu_periode_id": _identifiant(enjeux, ligne.get("enjeu_periode_id"), "enjeu"),
        })
        entrees[ligne["id"]] = objet.id
    for analyse, ancien_id in analyses_journal:
        analyse.entree_journal_id = entrees.get(ancien_id)
    for ligne in donnees["observations_mecanisme"]:
        _nouvel_objet(ObservationMecanisme, ligne, {
            "mecanisme_id": _identifiant(mecanismes, ligne["mecanisme_id"], "mécanisme"),
            "entree_journal_id": entrees.get(ligne.get("entree_journal_id")),
        })
    for ligne in donnees["droits_analyses_achetees"]:
        _nouvel_objet(DroitAnalyseAchetee, ligne, {
            "utilisateur_id": utilisateur_id,
            "analyse_id": _identifiant(analyses, ligne.get("analyse_id"), "analyse"),
        })
    for ligne in donnees["emails_cycles_abonnement"]:
        cycle_id = _identifiant(lunar, ligne.get("cycle_lunaire_id"), "RL")
        existant = EmailCycleAbonnement.query.filter_by(
            profil_id=profil_id, cycle_lunaire_id=cycle_id, type_email=ligne["type_email"],
        ).first()
        if existant is None:
            _nouvel_objet(EmailCycleAbonnement, ligne, {
                "profil_id": profil_id, "cycle_lunaire_id": cycle_id,
            })

    if {str(ancien) for ancien in analyses} != set(pdfs):
        raise ValueError("Les PDF ne correspondent pas aux analyses de l’export.")
    for ancien_id, nouveau_id in analyses.items():
        pdf = pdfs[str(ancien_id)]
        nom = pdf["nom"]
        contenu = base64.b64decode(pdf["base64"], validate=True)
        if (
            not isinstance(nom, str) or len(nom) > 255
            or Path(nom).name != nom or any(caractere in nom for caractere in '\r\n"')
            or not nom.lower().endswith(".pdf") or len(contenu) > 15 * 1024 * 1024
            or not contenu.startswith(b"%PDF-")
            or hashlib.sha256(contenu).hexdigest() != pdf["sha256"]
        ):
            raise ValueError("Un PDF de l’export est invalide.")
        db.session.add(FichierAnalyse(
            analyse_id=nouveau_id, nom_fichier=nom,
            type_mime="application/pdf", contenu=contenu,
            empreinte_sha256=pdf["sha256"],
        ))
    db.session.flush()
    return {"rs": len(solar), "rl": len(lunar), "analyses": len(analyses), "journal": len(entrees)}
