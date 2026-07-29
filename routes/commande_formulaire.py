from datetime import datetime, timezone

from flask import Blueprint, abort, render_template

from models.commandes import Commande, hasher_token


commande_formulaire_bp = Blueprint(
    "commande_formulaire_bp",
    __name__,
)


@commande_formulaire_bp.route("/commande/<token>", methods=["GET"])
def afficher_formulaire_commande(token):
    token_hash = hasher_token(token)

    commande = Commande.query.filter_by(
        token_hash=token_hash,
    ).first()

    if not commande:
        abort(404)

    if (
        commande.date_limite_lien
        and commande.date_limite_lien < datetime.now(timezone.utc)
    ):
        abort(410)

    return render_template(
        "commande/formulaire.html",
        commande=commande,
        token=token,
    )