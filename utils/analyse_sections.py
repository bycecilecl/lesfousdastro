"""Extraction locale des sections présentes dans les rapports PDF historiques."""

from io import BytesIO
from pathlib import Path
import re

import pdfplumber


TITRES_SECTIONS_POINT_ASTRAL = (
    ("personnalite_identite", "Personnalité & Identité"),
    ("lune_monde_interieur", "Lune & Monde intérieur"),
    ("racines_dynamique_familiale", "Racines & dynamique familiale"),
    ("axes_majeurs", "Les Axes Majeurs"),
    ("synthese", "Synthèse"),
)

TITRES_SECTIONS_PROFIL_AMOUREUX = (
    ("maniere_aimer", "Module 1 · Ma manière d'aimer"),
    ("partenaire_ideal", "Module 2 · Partenaire idéal : ce qui t'attire"),
    (
        "couple_dynamique_relationnelle",
        "Module 3 · Couple idéal & dynamique relationnelle",
    ),
    ("intimite_sexualite", "Module 4 · Intimité & sexualité"),
)

TITRES_SECTIONS_ANALYSE_KARMIQUE = (
    ("introduction_karmique", "Introduction karmique"),
    (
        "luminaires_karmiques",
        "Luminaires karmiques : mémoire & incarnation",
    ),
    ("noeuds_lunaires", "Nœuds Lunaires : ta boussole karmique"),
    ("maison_12", "Maison XII — Vie antérieure & karma actif"),
    ("maison_8", "Maison VIII — Vie antérieure & karma actif"),
    ("maison_4", "Maison IV — Racines & mémoire karmique"),
    ("saturne_pluton", "Saturne – Pluton : le noyau karmique"),
    ("lune_noire", "Lune Noire : la mémoire interdite"),
    (
        "axe_portes",
        "Axe des portes — visible, invisible et blessure karmique",
    ),
    ("chiron", "Chiron : la blessure initiatique"),
    ("interceptions", "Interceptions : ce qui tourne en tâche de fond"),
    ("part_fortune", "Part de Fortune : le point de résolution"),
    ("synthese_karmique", "Synthèse karmique : la clé d’incarnation"),
    (
        "ressources_incarnation",
        "Ressources et potentiels d'incarnation",
    ),
)

TITRES_SECTIONS_TRANSITS = (
    ("climat_dominant", "Le climat dominant"),
    ("travail_profond", "Ce qui travaille en profondeur"),
    ("manifestations", "Comment cela peut se manifester"),
    ("rythme", "Le rythme des prochaines semaines"),
    ("vigilance", "Tes points de vigilance"),
    ("utiliser_periode", "Comment utiliser cette période"),
    ("mouvements_principaux", "Les mouvements principaux"),
)

TITRES_SECTIONS_FORCES_DEFIS = (
    ("defis", "Tes Défis"),
    ("potentiels", "Tes Potentiels"),
    ("dynamiques_mixtes", "Dynamiques mixtes"),
    ("synthese", "Synthèse"),
)

LIGNES_TECHNIQUES = {
    "Point Astral - Les Fous d'Astro",
    "Flash Astral - Les Fous d'Astro",
    "© Droits réservés - Les Fous d'Astro",
    "Les Fous d'Astro - Analyse générée automatiquement",
    "lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr",
    "IG : @lesfousdastro • @bycecilecl",
}


def _normaliser_texte(lignes):
    texte = " ".join(ligne.strip() for ligne in lignes if ligne.strip())
    texte = re.sub(r"(\w)-\s+(\w)", r"\1\2", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _est_ligne_technique(ligne):
    return (
        ligne in LIGNES_TECHNIQUES
        or ligne.startswith("© Droits réservés - Les Fous d'Astro")
        or ligne.startswith("© Droits réservés – Les Fous d'Astro")
        or ligne.startswith("lesfousdastro.fr |")
        or ligne.startswith("IG : @lesfousdastro")
    )


def _extraire_sections_par_titres(source_pdf, titres_sections):
    """Découpe un PDF stocké en base ou sur disque à partir de ses titres."""
    if isinstance(source_pdf, bytes):
        if not source_pdf.startswith(b"%PDF-") or len(source_pdf) > 15 * 1024 * 1024:
            raise ValueError("Le rapport PDF est invalide ou dépasse 15 Mo.")
        source = BytesIO(source_pdf)
    else:
        source = Path(source_pdf)
        if not source.is_file():
            raise FileNotFoundError(f"Rapport introuvable : {source}")

    titres_par_texte = {
        titre.casefold(): (cle, titre)
        for cle, titre in titres_sections
    }
    sections = []
    section_courante = None

    with pdfplumber.open(source) as document:
        for numero_page, page in enumerate(document.pages, 1):
            texte_page = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for ligne in texte_page.splitlines():
                ligne = ligne.strip()
                if not ligne or _est_ligne_technique(ligne):
                    continue

                titre_reconnu = titres_par_texte.get(ligne.casefold())
                if titre_reconnu:
                    cle, titre = titre_reconnu
                    section_courante = {
                        "cle_section": cle,
                        "titre": titre,
                        "ordre": len(sections) + 1,
                        "pages": [numero_page],
                        "lignes": [],
                    }
                    sections.append(section_courante)
                    continue

                # La couverture et ses avertissements ne constituent pas une section.
                if section_courante is None:
                    continue

                if numero_page not in section_courante["pages"]:
                    section_courante["pages"].append(numero_page)
                section_courante["lignes"].append(ligne)

    resultat = []
    for section in sections:
        contenu = _normaliser_texte(section.pop("lignes"))
        if contenu:
            resultat.append({**section, "contenu": contenu})
    return resultat


def extraire_sections_point_astral(chemin_pdf):
    """Retourne les sections reconnues d'un rapport Racines familiales."""
    return _extraire_sections_par_titres(
        chemin_pdf,
        TITRES_SECTIONS_POINT_ASTRAL,
    )


def extraire_sections_profil_amoureux(chemin_pdf):
    """Retourne les quatre modules reconnus d'un Profil amoureux."""
    return _extraire_sections_par_titres(
        chemin_pdf,
        TITRES_SECTIONS_PROFIL_AMOUREUX,
    )


def extraire_sections_analyse_karmique(chemin_pdf):
    """Retourne les quatorze chapitres reconnus d'une Analyse karmique."""
    return _extraire_sections_par_titres(
        chemin_pdf,
        TITRES_SECTIONS_ANALYSE_KARMIQUE,
    )


def extraire_sections_transits(chemin_pdf):
    """Retourne les sept parties utiles d'un rapport de Transits."""
    return _extraire_sections_par_titres(
        chemin_pdf,
        TITRES_SECTIONS_TRANSITS,
    )


def extraire_sections_forces_defis(chemin_pdf):
    """Retourne les quatre parties d'un rapport Potentiels & Défis."""
    return _extraire_sections_par_titres(
        chemin_pdf,
        TITRES_SECTIONS_FORCES_DEFIS,
    )
