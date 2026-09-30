"""Premières tables persistantes de l'espace personnel.

Les autres objets du labo (profil, journal, rapports) seront ajoutés par étapes.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String

from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class UtilisateurEspace(db.Model):
    __tablename__ = "utilisateurs_espace"
    __table_args__ = (
        CheckConstraint("actif IN (0, 1)", name="ck_utilisateurs_espace_actif"),
    )

    id = Column(Integer, primary_key=True)
    prenom = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, unique=True)
    actif = Column(Integer, nullable=False, default=1)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class LienConnexionEspace(db.Model):
    __tablename__ = "liens_connexion_espace"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, index=True)
    empreinte_jeton = Column(String(64), nullable=False, unique=True, index=True)
    expire_le = Column(DateTime(timezone=True), nullable=False, index=True)
    utilise_le = Column(DateTime(timezone=True), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
