"""Bilan privé tous les 30 jours, pour les seuls abonnés actifs. Aucun e-mail."""
import json
import os
from uuid import uuid4


def automatique_actif():
    return bool(os.getenv("RAILWAY_ENVIRONMENT_ID")) and os.getenv("BILANS_JOURNAL_ACTIFS", "0") == "1"


def _conserver_sans_appel(utilisateur, periode, preparation, statut, message):
    from sqlalchemy.exc import IntegrityError
    from extensions import db
    from models.espace_personnel import BilanJournal30Jours
    bilan = BilanJournal30Jours(id=str(uuid4()), utilisateur_id=utilisateur.id,
        debut=periode["debut"], fin=periode["fin"], fuseau=periode["fuseau"], statut=statut,
        dossier_json=json.dumps(preparation["dossier"], ensure_ascii=False), prompt="",
        erreur=json.dumps({"message": message, "appel_ia": False}, ensure_ascii=False))
    db.session.add(bilan)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def passer_bilans():
    if not automatique_actif():
        return {"statut": "desactive"}
    from sqlalchemy import inspect
    from extensions import db
    from models.espace_personnel import AbonnementEspace, BilanJournal30Jours, ProfilAstral, UtilisateurEspace
    from utils.acces_abonnement import droits_pour_compte
    from utils.suivi_journal import periode_suivi, preparer_bilan_journal
    from utils.generation_bilan_journal import generer_bilan_journal
    if not inspect(db.session.get_bind(mapper=BilanJournal30Jours)).has_table(BilanJournal30Jours.__tablename__):
        return {"statut": "stockage_absent"}
    comptes = (UtilisateurEspace.query.join(AbonnementEspace, AbonnementEspace.utilisateur_id == UtilisateurEspace.id)
               .filter(UtilisateurEspace.actif == 1, AbonnementEspace.statut.in_(("actif", "test"))).all())
    resultat = {"statut": "actif", "generes": 0, "sans_appel": 0}
    for utilisateur in comptes:
        if not automatique_actif():
            break
        if not droits_pour_compte(utilisateur.id).get("bilan_journal_30j"):
            continue
        profil = ProfilAstral.query.filter_by(utilisateur_id=utilisateur.id).first()
        if not profil:
            continue
        try:
            periode = periode_suivi(utilisateur, profil.fuseau_cycles or "Europe/Paris")
            if not periode["due"] or periode["existant"]:
                continue
            preparation = preparer_bilan_journal(utilisateur, periode)
            if not preparation["minimum_atteint"]:
                _conserver_sans_appel(utilisateur, periode, preparation, "sans_notes",
                    "Moins de cinq notes dans cette période : aucun bilan IA demandé.")
                resultat["sans_appel"] += 1
                continue
            if not preparation["taille_ok"]:
                _conserver_sans_appel(utilisateur, periode, preparation, "echec",
                    "La période dépasse le budget prévu. Aucun appel IA demandé ; vérification nécessaire.")
                resultat["sans_appel"] += 1
                continue
            if not automatique_actif() or not droits_pour_compte(utilisateur.id).get("bilan_journal_30j"):
                continue
            bilan, nouveau = generer_bilan_journal(utilisateur, periode, preparation)
            resultat["generes"] += int(nouveau and bilan.statut == "genere")
        except Exception:
            db.session.rollback()
            from flask import current_app
            current_app.logger.exception("[BILAN JOURNAL] Passage interrompu pour un compte ; aucune tentative engagée relancée")
    return resultat
