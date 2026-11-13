"""Préparation du PDF et protection des demandes explicites de mécanismes."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import os

from extensions import db
from models.espace_personnel import SectionAnalyse
from utils.analyse_sections import (
    extraire_sections_analyse_karmique,
    extraire_sections_forces_defis,
    extraire_sections_point_astral,
    extraire_sections_profil_amoureux,
    extraire_sections_transits,
)
from utils.stockage_espace import racine_privee_espace


EXTRACTEURS_MECANISMES = {
    "analyse_karmique": extraire_sections_analyse_karmique,
    "racines_familiales": extraire_sections_point_astral,
    "profil_amoureux": extraire_sections_profil_amoureux,
    "transits": extraire_sections_transits,
    "forces_defis": extraire_sections_forces_defis,
}


class ExtractionMecanismesEnCours(ValueError):
    pass


@contextmanager
def verrou_mecanismes(analyse_id):
    """Un double clic ne doit pas démarrer deux appels payants concurrents."""
    dossier = racine_privee_espace() / "extractions_mecanismes"
    dossier.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(dossier / f"analyse-{int(analyse_id)}.lock",
                          os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descripteur, "a") as verrou:
        try:
            fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erreur:
            raise ExtractionMecanismesEnCours(
                "Une extraction est déjà en cours pour ce rapport. Aucun autre appel IA n’a été lancé."
            ) from erreur
        try:
            yield
        finally:
            fcntl.flock(verrou, fcntl.LOCK_UN)


def preparer_sections_mecanismes(analyse, obtenir_chemin_pdf):
    """Réutilise le texte existant ou le prépare, sans aucun appel IA.

    Le chemin est obtenu seulement si nécessaire : le stockage des PDF peut
    ainsi rester propre à chaque environnement. Appeler sous verrou_mecanismes.
    """
    extracteur = EXTRACTEURS_MECANISMES.get(analyse.type_analyse)
    if extracteur is None:
        raise ValueError("Ce type de rapport ne permet pas cette extraction.")
    sections = (SectionAnalyse.query.filter_by(analyse_id=analyse.id)
                .order_by(SectionAnalyse.ordre.asc()).all())
    if sections:
        if not any(section.contenu and section.contenu.strip() for section in sections):
            raise ValueError("Le texte de ce rapport n’est pas lisible.")
        print(f"[Mécanismes] Rapport {analyse.id} : texte déjà disponible ({len(sections)} sections).", flush=True)
        return sections

    print(f"[Mécanismes] Rapport {analyse.id} : lecture du PDF, sans appel IA.", flush=True)
    extraites = extracteur(obtenir_chemin_pdf())
    if not extraites or not any(section.get("contenu", "").strip() for section in extraites):
        raise ValueError("Aucun texte exploitable dans ce PDF. Utilise une version avec du texte sélectionnable.")
    maintenant = datetime.now(timezone.utc)
    sections = [SectionAnalyse(
        analyse_id=analyse.id, cle_section=section["cle_section"],
        titre=section["titre"], contenu=section["contenu"], ordre=section["ordre"],
        source_format="pdf_importe", date_creation=maintenant,
        date_modification=maintenant,
    ) for section in extraites]
    db.session.add_all(sections)
    db.session.commit()
    print(f"[Mécanismes] Rapport {analyse.id} : texte enregistré ({len(sections)} sections).", flush=True)
    return sections
