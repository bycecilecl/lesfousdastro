"""Notifications privées issues des comptes et paiements enregistrés. Aucun envoi."""
from datetime import datetime, timezone

from sqlalchemy import Integer, String, and_, cast, func, inspect, literal, select, union_all

from extensions import db
from models.espace_personnel import CommandeAbonnementEspace, NotificationAdminLue, UtilisateurEspace


def stockage_pret():
    moteur = db.session.get_bind(mapper=NotificationAdminLue)
    return inspect(moteur).has_table(NotificationAdminLue.__tablename__)


def _requete(administratrice_id):
    # Les sources existantes restent la vérité : aucune écriture ajoutée au paiement.
    comptes = select(
        literal("compte_cree").label("nature"),
        (cast(UtilisateurEspace.id, String(20)) + literal(":")
         + cast(UtilisateurEspace.date_creation, String(50))).label("source_id"),
        UtilisateurEspace.prenom.label("prenom"), UtilisateurEspace.email.label("email"),
        UtilisateurEspace.date_creation.label("date_evenement"),
        cast(literal(None), Integer).label("montant_centimes"),
        cast(literal(None), String(3)).label("devise"),
        cast(literal(None), String(40)).label("statut_paiement"),
    ).where(UtilisateurEspace.est_administratrice.is_(False))
    paiements = select(
        literal("paiement_confirme").label("nature"),
        CommandeAbonnementEspace.id.label("source_id"),
        UtilisateurEspace.prenom, UtilisateurEspace.email,
        CommandeAbonnementEspace.date_paiement.label("date_evenement"),
        CommandeAbonnementEspace.montant_centimes, CommandeAbonnementEspace.devise,
        CommandeAbonnementEspace.statut.label("statut_paiement"),
    ).select_from(CommandeAbonnementEspace).join(
        UtilisateurEspace, UtilisateurEspace.id == CommandeAbonnementEspace.utilisateur_id,
    ).where(
        CommandeAbonnementEspace.sandbox.is_(False),
        CommandeAbonnementEspace.date_paiement.isnot(None),
        CommandeAbonnementEspace.fournisseur_paiement_id.isnot(None),
        CommandeAbonnementEspace.fournisseur_paiement_id != "",
        CommandeAbonnementEspace.statut.in_(("payee", "active", "rembourse", "revoque")),
    )
    sources = union_all(comptes, paiements).subquery("notifications_sources")
    jointure = sources.outerjoin(NotificationAdminLue, and_(
        NotificationAdminLue.administratrice_id == administratrice_id,
        NotificationAdminLue.nature == sources.c.nature,
        NotificationAdminLue.source_id == sources.c.source_id,
    ))
    return select(*sources.c, NotificationAdminLue.lue_le).select_from(jointure)


def _executer(requete):
    return db.session.execute(requete, bind_arguments={"mapper": UtilisateurEspace})


def nombre_non_lues(administratrice_id):
    if not stockage_pret():
        return 0
    requete = _requete(administratrice_id).where(NotificationAdminLue.lue_le.is_(None))
    return _executer(select(func.count()).select_from(requete.subquery())).scalar_one()


def lister(administratrice_id, page=1, non_lues=False):
    requete = _requete(administratrice_id)
    if non_lues:
        requete = requete.where(NotificationAdminLue.lue_le.is_(None))
    nombre = _executer(select(func.count()).select_from(requete.subquery())).scalar_one()
    pages = max(1, (nombre + 29) // 30)
    page = min(pages, max(1, page))
    lignes = _executer(requete.order_by(
        requete.selected_columns.date_evenement.desc(),
        requete.selected_columns.nature, requete.selected_columns.source_id.desc(),
    ).offset((page - 1) * 30).limit(30)).mappings().all()
    return lignes, nombre, page, pages


def marquer_lues(administratrice_id, *, nature=None, source_id=None):
    """Marque seulement les événements présents à la demande, sans toucher aux sources."""
    requete = _requete(administratrice_id).where(NotificationAdminLue.lue_le.is_(None))
    if nature is not None:
        if nature not in {"compte_cree", "paiement_confirme"} or not source_id or len(source_id) > 100:
            return
        requete = requete.where(
            requete.selected_columns.nature == nature,
            requete.selected_columns.source_id == source_id,
        )
    evenements = _executer(requete).mappings().all()
    if not evenements:
        return
    dialecte = db.session.get_bind(mapper=NotificationAdminLue).dialect.name
    if dialecte == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialecte == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError("Stockage des notifications non pris en charge.")
    maintenant = datetime.now(timezone.utc)
    for evenement in evenements:
        db.session.execute(insert(NotificationAdminLue).values(
            administratrice_id=administratrice_id, nature=evenement["nature"],
            source_id=evenement["source_id"], lue_le=maintenant,
        ).on_conflict_do_nothing(index_elements=("administratrice_id", "nature", "source_id")))
    db.session.commit()
