"""Compte, connexion et profil persistants de l'espace personnel.

Le journal, les cycles et les rapports du labo seront ajoutés par étapes.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, Integer, String, Text, Time, UniqueConstraint

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


class ProfilAstral(db.Model):
    """Profil privé, compatible avec la structure déjà utilisée dans le labo."""

    __tablename__ = "profil_astral"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, unique=True, index=True)
    prenom = Column(String(100), nullable=False)
    date_naissance = Column(Date, nullable=False)
    heure_naissance = Column(Time, nullable=False)
    ville_naissance = Column(String(200), nullable=False)
    fuseau_horaire = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    ville_cycles = Column(String(200), nullable=True)
    fuseau_cycles = Column(String(100), nullable=True)
    latitude_cycles = Column(Float, nullable=True)
    longitude_cycles = Column(Float, nullable=True)
    theme_natal = Column(Text, nullable=True)
    date_calcul_theme = Column(DateTime(timezone=True), nullable=True)
    situation_foyer = Column(Text, nullable=True)
    situation_amour = Column(Text, nullable=True)
    situation_travail = Column(Text, nullable=True)
    situation_enfants = Column(Text, nullable=True)
    situation_sante = Column(Text, nullable=True)
    preoccupation_actuelle = Column(Text, nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False,
    )


class AbonnementEspace(db.Model):
    """Droits de test ou formule payante, séparés du compte gratuit."""

    __tablename__ = "abonnements_espace"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, unique=True, index=True)
    formule = Column(String(40), nullable=False, default="accompagnement_astral")
    statut = Column(String(30), nullable=False, default="inactif", index=True)
    date_debut = Column(DateTime(timezone=True), nullable=True)
    date_fin = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(80), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CycleLunaire(db.Model):
    """Cycle mensuel conservé pour les brouillons et leur historique."""

    __tablename__ = "cycles_lunaires"
    __table_args__ = (UniqueConstraint("profil_id", "cle_cycle", name="uq_cycle_lunaire_profil_cle"),)

    id = Column(Integer, primary_key=True)
    profil_id = Column(Integer, nullable=False, index=True)
    cycle_solaire_id = Column(Integer, nullable=True, index=True)
    cle_cycle = Column(String(40), nullable=False)
    debut_cycle_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    fin_cycle_utc = Column(DateTime(timezone=True), nullable=False)
    ville = Column(String(200), nullable=False)
    fuseau_horaire = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    theme_technique = Column(Text, nullable=False)
    interpretation = Column(Text, nullable=True)
    tokens_entree = Column(Integer, nullable=True)
    tokens_sortie = Column(Integer, nullable=True)
    statut = Column(String(30), nullable=False, default="a_generer")
    date_generation = Column(DateTime(timezone=True), nullable=True)
    date_envoi = Column(DateTime(timezone=True), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EmailCycleAbonnement(db.Model):
    """Brouillon de mail et trace d'envoi ; une ligne par cycle et type."""

    __tablename__ = "emails_cycles_abonnement"
    __table_args__ = (
        UniqueConstraint("profil_id", "cycle_lunaire_id", "type_email", name="uq_email_cycle_profil_cycle_type"),
    )

    id = Column(Integer, primary_key=True)
    profil_id = Column(Integer, nullable=False, index=True)
    cycle_lunaire_id = Column(Integer, nullable=True, index=True)
    type_email = Column(String(40), nullable=False, index=True)
    statut = Column(String(30), nullable=False, default="prepare")
    objet = Column(String(250), nullable=True)
    contenu_texte = Column(Text, nullable=True)
    contenu_html = Column(Text, nullable=True)
    declencheur_factuel = Column(Text, nullable=True)
    points_abordes = Column(Text, nullable=True)
    question_journal = Column(Text, nullable=True)
    date_generation = Column(DateTime(timezone=True), nullable=True)
    date_envoi = Column(DateTime(timezone=True), nullable=True, index=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
