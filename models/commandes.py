import hashlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, Time,
    ForeignKey, Numeric, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def enum_column(enum_class, name):
    """Persiste les .value des enums Python plutôt que leurs noms."""
    return SAEnum(
        enum_class,
        values_callable=lambda cls: [item.value for item in cls],
        native_enum=False,
        validate_strings=True,
        name=name,
    )


def generer_token():
    return secrets.token_urlsafe(32)


def hasher_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def generer_reference_commande() -> str:
    """
    Génère une référence publique difficile à deviner.

    Exemple :
    CMD-2026-A3F91C
    """
    annee = datetime.now(timezone.utc).year
    code_aleatoire = secrets.token_hex(3).upper()

    return f"CMD-{annee}-{code_aleatoire}"


# ---------- ENUMS ----------

class StatutCommande(str, Enum):
    EN_ATTENTE_INFOS = "en_attente_infos"
    INFOS_RECUES = "infos_recues"
    EN_ATTENTE_PAIEMENT = "en_attente_paiement"
    PAIEMENT_RECU = "paiement_recu"
    ANALYSE_EN_COURS = "analyse_en_cours"
    TERMINEE = "terminee"
    ANNULEE = "annulee"
    REMBOURSEE_LITIGE = "remboursee_litige"


class SituationBeneficiaire(str, Enum):
    POUR_MOI = "pour_moi"
    TIERS_INFORME = "tiers_informe"
    CADEAU_A_COMPLETER = "cadeau_a_completer"


class TypeClient(str, Enum):
    PARTICULIER = "particulier"
    PROFESSIONNEL = "professionnel"


class StatutPaiement(str, Enum):
    EN_ATTENTE = "en_attente"
    REUSSI = "reussi"
    ECHOUE = "echoue"
    REMBOURSE_TOTAL = "rembourse_total"
    REMBOURSE_PARTIEL = "rembourse_partiel"


class TypeDocument(str, Enum):
    CGV = "cgv"
    POLITIQUE_CONFIDENTIALITE = "politique_confidentialite"


# ---------- CLIENTS ----------

class Client(db.Model):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    nom = Column(String(120), nullable=False)
    prenom = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    telephone = Column(String(30), nullable=True)

    type_client = Column(
        enum_column(TypeClient, "type_client"),
        nullable=False,
        default=TypeClient.PARTICULIER,
    )
    raison_sociale = Column(String(255), nullable=True)
    siren = Column(String(9), nullable=True)

    adresse_facturation = Column(Text, nullable=True)
    oppose_affichage_adresse = Column(Boolean, nullable=False, default=False)

    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    commandes = relationship("Commande", back_populates="client")


# ---------- BENEFICIAIRES ----------

class Beneficiaire(db.Model):
    __tablename__ = "beneficiaires"

    id = Column(Integer, primary_key=True)
    nom = Column(String(120), nullable=True)
    prenom = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True)  # uniquement si lien cadeau propre

    date_naissance = Column(Date, nullable=True)
    heure_naissance = Column(Time, nullable=True)
    heure_naissance_connue = Column(Boolean, nullable=False, default=True)
    heure_naissance_approximative = Column(Boolean, nullable=False, default=False)
    lieu_naissance = Column(String(255), nullable=True)

    infos_completes = Column(Boolean, nullable=False, default=False)

    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # un bénéficiaire peut avoir plusieurs commandes au fil du temps
    commandes = relationship("Commande", back_populates="beneficiaire")


# ---------- VERSIONS DOCUMENTS ----------

class VersionDocument(db.Model):
    __tablename__ = "versions_documents"
    __table_args__ = (
        UniqueConstraint("type_document", "numero_version", name="uq_document_type_version"),
    )

    id = Column(Integer, primary_key=True)
    type_document = Column(enum_column(TypeDocument, "type_document"), nullable=False)
    numero_version = Column(String(20), nullable=False)  # ex: "2026-08"
    texte = Column(Text, nullable=False)
    date_publication = Column(DateTime(timezone=True), nullable=False)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# ---------- COMMANDES ----------

class Commande(db.Model):
    __tablename__ = "commandes"

    id = Column(Integer, primary_key=True)
    reference = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
        default=generer_reference_commande,
    )
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # jamais le token en clair

    prestation = Column(String(120), nullable=False)
    devise = Column(String(3), nullable=False, default="EUR")
    prix_normal = Column(Numeric(10, 2), nullable=False)
    montant_remise = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    prix_convenu = Column(Numeric(10, 2), nullable=False)

    delai_annonce = Column(String(120), nullable=True)
    creneau_realisation = Column(
        String(120),
        nullable=True,
    )
    statut = Column(
        enum_column(StatutCommande, "statut_commande"),
        nullable=False,
        default=StatutCommande.EN_ATTENTE_INFOS,
    )

    situation_beneficiaire = Column(
        enum_column(SituationBeneficiaire, "situation_beneficiaire"),
        nullable=True,
    )

    questionnaire_attentes = Column(Text, nullable=True)
    questionnaire_approfondir = Column(Text, nullable=True)

    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    date_limite_lien = Column(DateTime(timezone=True), nullable=True)

    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    beneficiaire_id = Column(Integer, ForeignKey("beneficiaires.id", ondelete="SET NULL"), nullable=True, index=True)

    client = relationship("Client", back_populates="commandes")
    beneficiaire = relationship("Beneficiaire", back_populates="commandes")

    lignes = relationship(
        "LigneCommande",
        back_populates="commande",
        cascade="all, delete-orphan",
        order_by="LigneCommande.id",
    )

    acceptation = relationship(
        "Acceptation", back_populates="commande", uselist=False, cascade="all, delete-orphan"
    )
    paiements = relationship(
        "Paiement", back_populates="commande", cascade="all, delete-orphan"
    )
    facture = relationship(
        "Facture", back_populates="commande", uselist=False, cascade="all, delete-orphan"
    )
    livraison = relationship(
        "Livraison", back_populates="commande", uselist=False, cascade="all, delete-orphan"
    )

    def definir_token(self):
        """Génère un token, le hash pour stockage, et renvoie le token en clair (à envoyer une seule fois)."""
        token = generer_token()
        self.token_hash = hasher_token(token)
        return token

# ---------- LIGNES DE COMMANDE ----------

class LigneCommande(db.Model):
    __tablename__ = "lignes_commande"

    id = Column(Integer, primary_key=True)

    commande_id = Column(
        Integer,
        ForeignKey("commandes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code_produit = Column(String(80), nullable=False)
    libelle = Column(String(255), nullable=False)

    quantite = Column(Integer, nullable=False, default=1)

    prix_unitaire = Column(Numeric(10, 2), nullable=False)
    montant_remise = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    montant_total = Column(Numeric(10, 2), nullable=False)

    date_creation = Column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    commande = relationship(
        "Commande",
        back_populates="lignes",
    )


# ---------- ACCEPTATION (une seule ligne par commande) ----------

class Acceptation(db.Model):
    __tablename__ = "acceptations"

    id = Column(Integer, primary_key=True)
    commande_id = Column(
        Integer, ForeignKey("commandes.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    cgv_acceptees = Column(Boolean, nullable=False, default=False)
    cgv_version_id = Column(Integer, ForeignKey("versions_documents.id"), nullable=True)
    cgv_case_texte = Column(Text, nullable=True)  # libellé exact affiché à côté de la case
    date_acceptation_cgv = Column(DateTime(timezone=True), nullable=True)

    politique_presentee = Column(Boolean, nullable=False, default=False)
    politique_version_id = Column(Integer, ForeignKey("versions_documents.id"), nullable=True)
    politique_information_texte = Column(Text, nullable=True)
    date_information_politique = Column(DateTime(timezone=True), nullable=True)

    informations_exactes_attestees = Column(Boolean, nullable=False, default=False)
    informations_exactes_texte = Column(Text, nullable=True)
    date_attestation_exactitude = Column(DateTime(timezone=True), nullable=True)

    declaration_tiers_informe_texte = Column(Text, nullable=True)
    date_declaration_tiers = Column(DateTime(timezone=True), nullable=True)

    demarrage_anticipe_demande = Column(Boolean, nullable=False, default=False)
    demarrage_anticipe_texte = Column(Text, nullable=True)
    date_demande_demarrage = Column(DateTime(timezone=True), nullable=True)

    renoncement_retractation_reconnu = Column(Boolean, nullable=False, default=False)

    commande = relationship("Commande", back_populates="acceptation")
    cgv_version = relationship("VersionDocument", foreign_keys=[cgv_version_id])
    politique_version = relationship("VersionDocument", foreign_keys=[politique_version_id])


# ---------- PAIEMENTS (plusieurs par commande) ----------

class Paiement(db.Model):
    __tablename__ = "paiements"
    __table_args__ = (
        UniqueConstraint("moyen_paiement", "reference_transaction", name="uq_paiement_fournisseur_reference"),
    )

    id = Column(Integer, primary_key=True)

    prestataire = Column(
        String(30),
        nullable=False,
        default="stripe",
    )

    reference_externe = Column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    commande_id = Column(
        Integer, ForeignKey("commandes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    devise = Column(String(3), nullable=False, default="EUR")
    montant = Column(Numeric(10, 2), nullable=False)
    moyen_paiement = Column(String(50), nullable=True)  # paypal / stripe / wero / virement
    reference_transaction = Column(String(120), nullable=True)
    statut = Column(
        enum_column(StatutPaiement, "statut_paiement"),
        nullable=False,
        default=StatutPaiement.EN_ATTENTE,
    )
    date_paiement = Column(DateTime(timezone=True), nullable=True)

    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    commande = relationship("Commande", back_populates="paiements")


# ---------- FACTURE (Indy) ----------

class Facture(db.Model):
    __tablename__ = "factures"

    id = Column(Integer, primary_key=True)
    commande_id = Column(
        Integer, ForeignKey("commandes.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    numero_indy = Column(String(50), unique=True, nullable=False)
    date_facturation = Column(DateTime(timezone=True), nullable=False)
    montant = Column(Numeric(10, 2), nullable=False)
    devise = Column(String(3), nullable=False, default="EUR")
    statut = Column(String(30), nullable=False, default="emise")

    commande = relationship("Commande", back_populates="facture")


# ---------- LIVRAISON ----------

class Livraison(db.Model):
    __tablename__ = "livraisons"

    id = Column(Integer, primary_key=True)
    commande_id = Column(
        Integer, ForeignKey("commandes.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    identifiant_fichier = Column(String(120), nullable=True)  # clé interne S3, jamais d'URL publique
    date_generation = Column(DateTime(timezone=True), nullable=True)
    date_envoi = Column(DateTime(timezone=True), nullable=True)
    destinataire_envoi = Column(String(255), nullable=True)
    date_expiration_lien = Column(DateTime(timezone=True), nullable=True)

    commande = relationship("Commande", back_populates="livraison")