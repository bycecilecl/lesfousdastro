from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Date,
    Time,
)

from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class ParticipationTest(db.Model):
    __tablename__ = "participations_tests"

    id = Column(Integer, primary_key=True)

    type_test = Column(String(100), nullable=False, index=True)

    prenom = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)

    date_naissance = Column(Date, nullable=True)
    heure_naissance = Column(Time, nullable=True)
    ville_naissance = Column(String(255), nullable=True)
    genre = Column(String(30), nullable=True)

    fratrie = Column(Text, nullable=True)
    enfance = Column(Text, nullable=True)

    acceptation_cgv = Column(Boolean, nullable=False, default=False)
    acceptation_confidentialite = Column(
        Boolean,
        nullable=False,
        default=False,
    )
    acceptation_test = Column(Boolean, nullable=False, default=False)
    consentement_recherche = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    donnees_complementaires = Column(Text, nullable=True)

    paiement_effectue = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    date_paiement = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    point_astral_envoye = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    date_envoi_point_astral = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    date_creation = Column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )