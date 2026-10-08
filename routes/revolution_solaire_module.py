"""Livraison de la Révolution solaire achetée sur le formulaire principal."""
import json
import hashlib
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, abort, current_app, redirect, url_for

from services.analysis_orders import owned_order
from utils.client_pdf_storage import private_pdf_path, upload_client_pdf
from utils.pdf_utils import html_to_pdf
from utils.revolution_solaire.rapport_pdf import habiller_rapport_pdf
from utils.revolution_solaire.relances import retenter


revolution_solaire_module = Blueprint(
    "revolution_solaire_module", __name__, url_prefix="/revolution-solaire"
)

CHAMPS_CONTEXTE = {
    "travail", "amour", "foyer_famille", "enfants", "argent", "sante", "preoccupation"
}


def generer_rapport_revolution_solaire(**demande):
    """Charge le moteur seulement lors d'une génération RS achetée."""
    from utils.revolution_solaire.service import generer_rapport_revolution_solaire as generer
    return generer(**demande)


def _demande_depuis_commande(infos: dict) -> dict:
    """Reprend uniquement les données liées à la commande payée."""
    try:
        annee = int(infos["annee_rs"])
        lat = float(infos["lat"])
        lon = float(infos["lon"])
        lat_rs = float(infos["lat_rs"])
        lon_rs = float(infos["lon_rs"])
        ZoneInfo(infos["tzid"])
        ZoneInfo(infos["tzid_rs"])
        contexte_brut = infos.get("contexte_rs_json") or "{}"
        if len(contexte_brut) > 2800:
            raise ValueError("Les repères facultatifs sont trop longs.")
        contexte = json.loads(contexte_brut)
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError("Données de Révolution solaire incomplètes.") from error
    if (
        not 1900 <= annee <= 2100
        or not -90 <= lat <= 90 or not -90 <= lat_rs <= 90
        or not -180 <= lon <= 180 or not -180 <= lon_rs <= 180
        or not isinstance(contexte, dict)
        or any(key not in CHAMPS_CONTEXTE or not isinstance(value, str) or len(value) > 300
               for key, value in contexte.items())
        or not all(infos.get(champ) for champ in
                   ("nom", "date_naissance", "heure_naissance", "lieu_naissance", "lieu_rs"))
    ):
        raise ValueError("Données de Révolution solaire invalides.")
    return {
        "personne": {
            "nom": infos["nom"], "date": infos["date_naissance"],
            "heure": infos["heure_naissance"], "lieu": infos["lieu_naissance"],
            "lat": lat, "lon": lon, "tzid": infos["tzid"],
            "genre": infos.get("gender") or infos.get("genre") or "",
        },
        "lieu_rs": {
            "lieu": infos["lieu_rs"], "lat": lat_rs, "lon": lon_rs,
            "tzid": infos["tzid_rs"],
        },
        "annee": annee,
        "contexte_client": {
            key: value.strip()
            for key, value in contexte.items()
            if key in CHAMPS_CONTEXTE and isinstance(value, str) and value.strip()
        },
    }


def generer_revolution_solaire_pdf_s3(infos: dict, *, commande_id: str | None = None) -> dict:
    """Un rapport, un PDF privé et un lien de livraison pour la commande."""
    demande = _demande_depuis_commande(infos)
    # Une commande payée retrouve ses réponses Claude après un échec PDF/S3
    # ou une relance du worker. Les trois tentatives IA restent séparées.
    cle = hashlib.sha256(commande_id.encode()).hexdigest() if commande_id else uuid4().hex
    racine = Path(current_app.instance_path) / "generations_rs" / cle

    def signaler(etape):
        def journaliser(numero, essais, erreur):
            current_app.logger.warning(
                "RS %s : tentative %s/%s échouée (%s)",
                etape, numero, essais, type(erreur).__name__, exc_info=True,
            )
        return journaliser

    # Une réponse tronquée ou un contrôle factuel refusé doit aboutir à une
    # nouvelle génération. Chaque tentative garde ses propres archives.
    rapport = retenter(
        lambda numero: generer_rapport_revolution_solaire(
            **demande, stockage_dir=racine / f"tentative_{numero}",
        ),
        signaler=signaler("rapport"),
    )
    html_pdf = habiller_rapport_pdf(
        rapport.html, personne=demande["personne"], lieu_rs=demande["lieu_rs"],
        annee=demande["annee"],
    )

    def creer_pdf(_numero):
        pdf_path = private_pdf_path()
        if not html_to_pdf(
            html_pdf, pdf_path,
            page_header=f"Révolution solaire {demande['annee']} - Les Fous d'Astro",
        ):
            raise RuntimeError("Le PDF n'a pas pu être créé.")
        return pdf_path

    pdf_path = retenter(creer_pdf, signaler=signaler("PDF"))
    pdf_url = retenter(
        lambda _numero: upload_client_pdf(
            pdf_path,
            key_prefix="revolution_solaire",
            download_filename=f"Revolution_Solaire_{demande['annee']}.pdf",
        ),
        signaler=signaler("stockage"),
    )
    return {
        "product_id": "revolution_solaire",
        "label": "Ma Révolution Solaire",
        "pdf_url": pdf_url,
        "rapport_html": rapport.html,
        "s3_ready": True,
    }


@revolution_solaire_module.route("/rapport")
def resultat():
    order = owned_order(paid=True)
    if "revolution_solaire" not in order.products:
        abort(403)
    return redirect(url_for("checkout_bp.analyse_resultat", product_id="revolution_solaire"))
