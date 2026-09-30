"""Comptes, profil, journal, cycles et archives de l'espace personnel."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, Integer, LargeBinary, String, Text, Time, UniqueConstraint

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


class CycleSolaire(db.Model):
    """Révolution solaire active, utilisée comme cadre annuel des cycles."""

    __tablename__ = "cycles_solaires"
    __table_args__ = (
        UniqueConstraint(
            "profil_id",
            "cle_cycle",
            name="uq_cycle_solaire_profil_cle",
        ),
    )

    id = Column(Integer, primary_key=True)
    profil_id = Column(Integer, nullable=False, index=True)
    cle_cycle = Column(String(40), nullable=False)
    annee = Column(Integer, nullable=False, index=True)
    debut_cycle_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    fin_cycle_utc = Column(DateTime(timezone=True), nullable=False)
    ville = Column(String(200), nullable=False)
    fuseau_horaire = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    theme_technique = Column(Text, nullable=False)
    releve_technique = Column(Text, nullable=True)
    rapport_texte = Column(Text, nullable=True)
    rapport_html = Column(Text, nullable=True)
    statut = Column(String(30), nullable=False, default="a_generer")
    date_generation = Column(DateTime(timezone=True), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class AnalysePersonnelle(db.Model):
    """Analyse disponible dans la bibliothèque de l’espace personnel."""

    __tablename__ = "analyses_personnelles"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, index=True)
    type_analyse = Column(String(80), nullable=False, index=True)
    titre = Column(String(160), nullable=False)
    statut = Column(String(30), nullable=False, default="terminee")
    chemin_resultat = Column(Text, nullable=True)
    date_generation = Column(DateTime(timezone=True), nullable=True)
    notes_personnelles = Column(Text, nullable=True)
    entree_journal_id = Column(Integer, nullable=True, index=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class DroitAnalyseAchetee(db.Model):
    """Droit de générer un rapport ponctuel depuis l'espace personnel."""

    __tablename__ = "droits_analyses_achetees"
    __table_args__ = (
        UniqueConstraint("utilisateur_id", "type_analyse", name="uq_droit_analyse_utilisateur_type"),
    )

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, index=True)
    type_analyse = Column(String(80), nullable=False, index=True)
    statut = Column(String(30), nullable=False, default="a_generer", index=True)
    reference_commande = Column(String(120), nullable=True, unique=True)
    analyse_id = Column(Integer, nullable=True, index=True)
    date_achat = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_generation = Column(DateTime(timezone=True), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)



class CommandeAnalyseEspace(db.Model):
    """Commande PayPal liée à un compte de l’espace personnel."""

    __tablename__ = "commandes_analyses_espace"

    id = Column(String(36), primary_key=True)
    utilisateur_id = Column(Integer, nullable=False, index=True)
    type_analyse = Column(String(80), nullable=False, index=True)
    product_key = Column(String(80), nullable=False)
    montant_centimes = Column(Integer, nullable=False)
    devise = Column(String(3), nullable=False, default="EUR")
    fournisseur = Column(String(20), nullable=False, default="paypal")
    fournisseur_commande_id = Column(String(255), nullable=True, unique=True, index=True)
    fournisseur_paiement_id = Column(String(255), nullable=True, unique=True)
    statut = Column(String(30), nullable=False, default="en_attente", index=True)
    sandbox = Column(Boolean, nullable=False, default=True)
    date_paiement = Column(DateTime(timezone=True), nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)



class SectionAnalyse(db.Model):
    """Chapitre structuré conservé avant la transformation d’une analyse en PDF."""

    __tablename__ = "sections_analyse"
    __table_args__ = (
        UniqueConstraint(
            "analyse_id",
            "cle_section",
            name="uq_section_analyse_cle",
        ),
    )

    id = Column(Integer, primary_key=True)
    analyse_id = Column(Integer, nullable=False, index=True)
    cle_section = Column(String(120), nullable=False)
    titre = Column(String(250), nullable=False)
    contenu = Column(Text, nullable=False)
    ordre = Column(Integer, nullable=False, default=0)
    source_format = Column(String(30), nullable=False, default="generation")
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class EnjeuPeriode(db.Model):
    """Grande tendance temporaire extraite d'un rapport de Transits."""

    __tablename__ = "enjeux_periode"
    __table_args__ = (
        UniqueConstraint(
            "analyse_id",
            "ordre",
            name="uq_enjeu_periode_analyse_ordre",
        ),
    )

    id = Column(Integer, primary_key=True)
    analyse_id = Column(Integer, nullable=False, index=True)
    contenu = Column(Text, nullable=False)
    references_astrologiques = Column(Text, nullable=True)
    ordre = Column(Integer, nullable=False)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)



class SuggestionMecanisme(db.Model):
    """Hypothèse proposée par l’IA avant sa validation dans le laboratoire."""

    __tablename__ = "suggestions_mecanisme"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('proposee', 'acceptee', 'rejetee')",
            name="ck_suggestion_mecanisme_statut",
        ),
    )

    id = Column(Integer, primary_key=True)
    analyse_id = Column(Integer, nullable=False, index=True)
    section_id = Column(Integer, nullable=True, index=True)
    titre = Column(String(200), nullable=False)
    hypothese = Column(Text, nullable=False)
    manifestations_possibles = Column(Text, nullable=True)
    extrait_source = Column(Text, nullable=False)
    references_astrologiques = Column(Text, nullable=True)
    priorite = Column(Integer, nullable=False, default=0)
    statut = Column(String(20), nullable=False, default="proposee", index=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class MecanismeExploration(db.Model):
    """Hypothèse issue d’une analyse et travaillée consciemment par la personne."""

    __tablename__ = "mecanismes_exploration"

    id = Column(Integer, primary_key=True)
    analyse_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    titre = Column(String(200), nullable=False)
    extrait_source = Column(Text, nullable=True)
    hypothese = Column(Text, nullable=False)
    effets_possibles = Column(Text, nullable=True)
    ressenti = Column(String(40), nullable=False, default="a_observer")
    statut = Column(String(40), nullable=False, default="a_explorer")
    indices_pour = Column(Text, nullable=True)
    elements_contraires = Column(Text, nullable=True)
    situations_observees = Column(Text, nullable=True)
    piste_experimentation = Column(Text, nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class ObservationMecanisme(db.Model):
    """Épisode daté permettant de suivre un mécanisme dans la durée."""

    __tablename__ = "observations_mecanisme"

    id = Column(Integer, primary_key=True)
    mecanisme_id = Column(Integer, nullable=False, index=True)
    entree_journal_id = Column(Integer, nullable=True, index=True)
    date_observation = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    situation = Column(Text, nullable=False)
    reaction_automatique = Column(Text, nullable=True)
    indice_pour = Column(Text, nullable=True)
    element_contraire = Column(Text, nullable=True)
    reaction_testee = Column(Text, nullable=True)
    resultat_obtenu = Column(Text, nullable=True)
    notes_libres = Column(Text, nullable=True)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )



class EntreeJournal(db.Model):
    """Observation personnelle reliée au contexte astrologique du moment."""

    __tablename__ = "entrees_journal"
    __table_args__ = (
        CheckConstraint(
            "niveau_energie IS NULL OR (niveau_energie >= 1 AND niveau_energie <= 10)",
            name="ck_entree_journal_niveau_energie",
        ),
    )

    id = Column(Integer, primary_key=True)

    utilisateur_id = Column(Integer, nullable=False, index=True)
    cycle_lunaire_id = Column(Integer, nullable=True, index=True)
    enjeu_periode_id = Column(Integer, nullable=True, index=True)

    date_observation = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    niveau_energie = Column(Integer, nullable=True)
    emotions = Column(String(500), nullable=True)
    situation = Column(Text, nullable=True)
    reaction_automatique = Column(Text, nullable=True)
    choix_conscient = Column(Text, nullable=True)
    notes_libres = Column(Text, nullable=True)

    # JSON conservé en texte pour rester compatible avec SQLite en DEV.
    transits_actifs = Column(Text, nullable=True)

    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modification = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class FichierAnalyse(db.Model):
    """PDF privé conservé en base pour ne pas dépendre du disque Railway."""

    __tablename__ = "fichiers_analyses_espace"

    id = Column(Integer, primary_key=True)
    analyse_id = Column(Integer, nullable=False, unique=True, index=True)
    nom_fichier = Column(String(255), nullable=False)
    type_mime = Column(String(100), nullable=False, default="application/pdf")
    contenu = Column(LargeBinary, nullable=False)
    empreinte_sha256 = Column(String(64), nullable=False)
    date_creation = Column(DateTime(timezone=True), default=utcnow, nullable=False)
