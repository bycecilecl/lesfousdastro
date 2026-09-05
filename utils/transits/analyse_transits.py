# utils/transits/analyse_transits.py

from .modeles import ResultatTransits
from .calcul_transits import calculer_positions_transits
from .detecteurs import detecter_aspects
from datetime import datetime, timedelta
from .config import (
    ASPECTS_MAJEURS,
    PLANETES_LENTES,
    IMPORTANCE_MIN_AFFICHAGE,
)
from .selection import est_transit_mars_flash_pertinent, selectionner_transits_flash

from .maisons import extraire_cuspides
from .synthese_brady import THEMES_MAISONS
from .interpretation_brady import interpreter_transit_brady
from .llm_transits import generer_bloc_transits_llm, ErreurGenerationTransits
from collections import Counter
import logging
import re

logger = logging.getLogger(__name__)

ORDRE_NARRATIF_PLANETES = {
    "Pluton": 1,
    "Neptune": 2,
    "Uranus": 3,
    "Saturne": 4,
    "Chiron": 5,
    "Jupiter": 6,
    "Mars": 7,
    "Vénus": 8,
    "Mercure": 9,
    "Lune": 10,
}

MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def formater_date_fr(date: datetime) -> str:
    return f"{date.day} {MOIS_FR[date.month - 1]} {date.year}"


def securiser_precision_temporelle(texte: str) -> str:
    """Neutralise uniquement les fausses promesses d'exactitude du LLM."""
    remplacements = (
        (r"\bexactement opposée? à\b", "en opposition très serrée à"),
        (
            r"\batteint son orbe le plus serré avec\b",
            "présente le plus faible orbe observé avec",
        ),
        (
            r"\batteindre un point culminant\b",
            "entrer dans une phase particulièrement sensible",
        ),
        (r"\bpoint culminant\b", "phase particulièrement sensible"),
    )
    for motif, remplacement in remplacements:
        texte = re.sub(motif, remplacement, texte, flags=re.IGNORECASE)
    return texte


def texte_en_paragraphes_html(texte: str) -> str:
    if not texte:
        return ""

    texte = securiser_precision_temporelle(texte)
    blocs = [b.strip() for b in texte.split("\n\n") if b.strip()]

    elements = []
    for bloc in blocs:
        lignes = bloc.splitlines()
        if lignes[0].startswith("## "):
            elements.append(f"<h3>{lignes[0][3:].strip()}</h3>")
            contenu = " ".join(ligne.strip() for ligne in lignes[1:] if ligne.strip())
            if contenu:
                elements.append(f"<p>{contenu}</p>")
        else:
            elements.append(f"<p>{bloc.replace(chr(10), ' ')}</p>")

    return "\n".join(elements)

def generer_dates_periode(
    date_reference: datetime,
    jours_avant: int = 21,
    jours_apres: int = 21,
    pas: int = 5,
) -> list[datetime]:
    dates = []
    d = date_reference - timedelta(days=jours_avant)
    fin = date_reference + timedelta(days=jours_apres)

    while d <= fin:
        dates.append(d)
        d += timedelta(days=pas)

    return dates

def collecter_transits_sur_periode(
    theme: dict,
    date_reference: datetime,
    jours_avant: int = 21,
    jours_apres: int = 21,
    pas: int = 5,
) -> list:
    dates = generer_dates_periode(
        date_reference=date_reference,
        jours_avant=jours_avant,
        jours_apres=jours_apres,
        pas=pas,
    )

    natal = theme.get("planetes", {})
    cuspides = extraire_cuspides(theme)
    house_rulers_map = theme.get("house_rulers_map", {})
    maitre_ascendant_data = theme.get("maitre_ascendant")
    maitre_ascendant = (
        maitre_ascendant_data.get("nom")
        if isinstance(maitre_ascendant_data, dict)
        else maitre_ascendant_data
    )
    angles_deg = theme.get("angles_deg", {})

    transits_periode = []

    for date in dates:
        transits_data = calculer_positions_transits(date)
        positions_transits = transits_data["positions"]

        aspects = detecter_aspects(
            positions_transits,
            natal,
            cuspides,
            house_rulers_map,
            maitre_ascendant=maitre_ascendant,
            angles_deg=angles_deg,
        )

        for a in aspects:
            a.contexte = a.contexte or {}
            a.contexte["date_detection"] = date.strftime("%d/%m/%Y")
            transits_periode.append(a)

    return transits_periode

def fusionner_transits_periode(transits_periode: list) -> dict:
    """
    Regroupe les transits détectés sur la période par planète transitante.
    Garde, pour chaque événement, le passage le plus serré.
    """

    dynamiques = {}

    for transit in transits_periode:
        planete_t = transit.planete_transit

        if planete_t not in dynamiques:
            dynamiques[planete_t] = {
                "score": 0,
                "evenements": {},
            }

        cle_evenement = (
            transit.aspect,
            transit.planete_natale,
        )

        existant = dynamiques[planete_t]["evenements"].get(cle_evenement)

        if existant is None or transit.orbe < existant["orbe"]:
            dynamiques[planete_t]["evenements"][cle_evenement] = {
                "aspect": transit.aspect,
                "planete_natale": transit.planete_natale,
                "orbe": transit.orbe,
                "importance": transit.importance,
                "date_detection": (transit.contexte or {}).get("date_detection"),
                "conjonctions_associees": getattr(
                    transit,
                    "conjonctions_associees",
                    [],
                ),
            }

    # Calcul du score par planète transitante
    for planete_t, data in dynamiques.items():
        data["score"] = sum(
            evt["importance"]
            for evt in data["evenements"].values()
        )

        data["evenements"] = sorted(
            data["evenements"].values(),
            key=lambda evt: (-evt["importance"], evt["orbe"]),
        )

    return dict(
        sorted(
            dynamiques.items(),
            key=lambda item: -item[1]["score"],
        )
    )


def generer_analyse_transits(
    theme: dict,
    periode: str = "période actuelle",
    date_transit: datetime | None = None,
    genre: str | None = None,
) -> ResultatTransits:
    nom = theme.get("nom", "Analyse Anonyme")

    # 1. récupérer les positions de transits
    transits_data = calculer_positions_transits(date_transit)
    positions_transits = transits_data["positions"]

    # 2. récupérer les positions natales
    natal = theme.get("planetes", {})
    if not natal:
        return ResultatTransits(
            nom=nom,
            periode=periode,
            erreur="Thème natal manquant ou vide.",
            texte_html="<p>Impossible de calculer les transits : thème natal manquant.</p>",
        )

    # 3. préparer le contexte maisons façon Brady
    try:
        cuspides = extraire_cuspides(theme)
    except ValueError as e:
        return ResultatTransits(
            nom=nom,
            periode=periode,
            erreur=str(e),
            texte_html=f"<p>Impossible de calculer les maisons des transits : {e}</p>",
        )

    house_rulers_map = theme.get("house_rulers_map", {})
    if not house_rulers_map:
        logger.warning("house_rulers_map absent du thème de %s", nom)

    maitre_ascendant_data = theme.get("maitre_ascendant")
    maitre_ascendant = (
        maitre_ascendant_data.get("nom")
        if isinstance(maitre_ascendant_data, dict)
        else maitre_ascendant_data
    )

    # 4. détecter les aspects enrichis
    angles_deg = theme.get("angles_deg", {})
    logger.info("ANGLES DEG RECUS = %s", angles_deg)

    aspects = detecter_aspects(
        positions_transits,
        natal,
        cuspides,
        house_rulers_map,
        maitre_ascendant=maitre_ascendant,
        angles_deg=angles_deg,
    )

    # 5. Transits de fond + au plus un déclencheur bref de Mars.
    transits_affiches = selectionner_transits_flash(aspects)

    logger.info("TRANSITS AFFICHES = %s", [
        f"{a.planete_transit} {a.aspect} {a.planete_natale} ({a.importance})"
        for a in transits_affiches
    ])

    transits_periode = collecter_transits_sur_periode(
        theme=theme,
        date_reference=date_transit or datetime.now(),
    )

    transits_periode_filtres = [
        a for a in transits_periode
        if (
            (
                a.planete_transit in PLANETES_LENTES
                and a.aspect in ASPECTS_MAJEURS
            )
            or est_transit_mars_flash_pertinent(a)
        )
        and a.importance >= IMPORTANCE_MIN_AFFICHAGE
    ]

    dynamiques_periode = fusionner_transits_periode(
        transits_periode_filtres
    )
    logger.info("DYNAMIQUES PERIODE = %s", dynamiques_periode)
    date_reference = date_transit or datetime.now()
    date_affichee = formater_date_fr(date_reference)
    date_debut_periode = formater_date_fr(date_reference - timedelta(days=21))
    date_fin_periode = formater_date_fr(date_reference + timedelta(days=21))

    compteur_planetes = Counter(
        a.planete_transit
        for a in transits_affiches
    )

    transits_pour_llm = sorted(
        transits_affiches,
        key=lambda a: (
            -compteur_planetes[a.planete_transit],
            ORDRE_NARRATIF_PLANETES.get(a.planete_transit, 99),
            -a.importance,
            a.orbe,
        )
    )

    interpretations_structurees = [
        interpreter_transit_brady(a)
        for a in transits_pour_llm
    ]

    ascendant_data = theme.get("ascendant", {})
    ascendant_signe = ascendant_data.get("signe") if isinstance(ascendant_data, dict) else None

    bloc_transits = ""
    bloc_transits_html = ""

    if transits_affiches:
        try:
            bloc_transits = generer_bloc_transits_llm(
                transits_pour_llm,
                interpretations_structurees,
                nom=nom,
                ascendant=ascendant_signe,
                dynamiques_periode=dynamiques_periode,
                genre=genre,
            )
        except ErreurGenerationTransits as exc:
            logger.error("Échec de génération du Point Transits : %s", exc)
            return ResultatTransits(
                nom=nom,
                periode=periode,
                transits_actifs=transits_affiches,
                donnees_calcul={
                    "date_reference": transits_data["date_transit"],
                    "positions_transits": positions_transits,
                    "dynamiques_periode": dynamiques_periode,
                },
                erreur=str(exc),
                texte_html=f"""
                    <h2>Ton ciel du moment</h2>
                    <p class="transits-date">Ton Point Transits a été calculé pour le {date_affichee}.</p>
                    <div class="transits-error" role="alert">
                        <p><strong>La génération du Point Transits a rencontré un problème temporaire.</strong></p>
                        <p>Les données astrologiques ont bien été calculées, mais le texte n’a pas pu être généré. Tu pourras relancer l’analyse.</p>
                    </div>
                """,
            )
        bloc_transits_html = texte_en_paragraphes_html(bloc_transits)

    # 6. debug texte simple
    texte = f"""
        <h2>Ton ciel du moment</h2>
        <p class="transits-date">Ton Point Transits a été calculé pour le {date_affichee}.</p>

        <div class="transits-global">
            {bloc_transits_html}
        </div>

        <aside class="transits-methodology">
            <h3>Comment lire ton Point Transits</h3>
            <p>L’analyse part des positions planétaires calculées pour le <strong>{date_affichee}</strong>. Elle observe également leur évolution du <strong>{date_debut_periode}</strong> au <strong>{date_fin_periode}</strong>, par relevés espacés de cinq jours, afin de dégager le rythme général de la période.</p>
            <p>Un aspect est retenu dans les limites suivantes : conjonction et opposition jusqu’à 5° d’orbe, carré et trigone jusqu’à 4°, sextile jusqu’à 3°. Pour Mars, seuls la conjonction, le carré et l’opposition sont retenus, jusqu’à 2° — ou 3° lorsqu’un luminaire ou un angle majeur est touché. Plus l’orbe est faible, plus l’aspect est précis.</p>
            <p><strong>« Conjoint » ne signifie donc pas nécessairement « exactement superposé » :</strong> cela signifie que les deux points se trouvent dans l’orbe admis. Les dates mentionnées indiquent des zones de sensibilité repérées lors des relevés ; elles ne constituent ni des heures d’exactitude astronomique ni la prédiction certaine d’un événement.</p>
        </aside>

        <div class="transits-list">
            <h2>Les mouvements principaux</h2>
            <p>Plus l’orbe est faible, plus le transit est précis et son impact peut être ressenti nettement.</p>
    """

    if not transits_affiches:
        texte += "<p>Aucun transit majeur prioritaire détecté actuellement.</p>"
    else:
        for a in transits_affiches:
            ctx = a.contexte or {}

            maison_transit = ctx.get("maison_transit") or "—"
            orbe_affiche = f"{a.orbe:.1f}".replace(".", ",")
            theme_maison = THEMES_MAISONS.get(
                maison_transit,
                "domaine de vie à préciser",
            )

            texte += f"""
                <div class="transit-card">
                    <h3>{a.planete_transit} {a.aspect} {a.planete_natale} — orbe {orbe_affiche}°</h3>
                    <p><strong>Secteur activé : maison {maison_transit}</strong><br>
                    {theme_maison.capitalize()}.</p>
                </div>
            """

    texte += "</div>"

    return ResultatTransits(
        nom=nom,
        periode=periode,
        transits_actifs=transits_affiches,
        donnees_calcul={
            "date_reference": transits_data["date_transit"],
            "positions_transits": positions_transits,
            "dynamiques_periode": dynamiques_periode,
        },
        texte_html=texte,
    )
