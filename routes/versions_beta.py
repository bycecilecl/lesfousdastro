from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for

from extensions import db
from models.participations_beta import ParticipationTest


versions_beta_bp = Blueprint(
    "versions_beta",
    __name__,
)


@versions_beta_bp.route(
    "/test-point-astral",
    methods=["GET", "POST"],
)

def point_astral():

    if request.method == "POST":

        prenom = request.form.get("prenom")
        email = request.form.get("email")

        date_naissance = request.form.get("date_naissance")
        heure_naissance = request.form.get("heure_naissance")
        ville_naissance = request.form.get("ville_naissance")
        genre = request.form.get("genre")

        fratrie = request.form.get("fratrie")
        enfance = request.form.get("enfance")

        acceptation_cgv = bool(
            request.form.get("acceptation_cgv")
        )
        acceptation_confidentialite = bool(
            request.form.get("acceptation_confidentialite")
        )
        acceptation_beta = bool(
            request.form.get("acceptation_beta")
        )
        acceptation_recherche = bool(
            request.form.get("acceptation_recherche")
        )

        if not (
            acceptation_cgv
            and acceptation_confidentialite
        ):
            return (
                "Les consentements obligatoires doivent être acceptés.",
                400,
            )

        try:
            date_naissance_obj = datetime.strptime(
                date_naissance,
                "%Y-%m-%d",
            ).date()

            heure_naissance_obj = datetime.strptime(
                heure_naissance,
                "%H:%M",
            ).time()

        except (TypeError, ValueError):
            return (
                "La date ou l’heure de naissance est invalide.",
                400,
            )

        participation = ParticipationTest(
            type_test="point_astral_beta",

            prenom=prenom.strip(),
            email=email.strip().lower(),

            date_naissance=date_naissance_obj,

            heure_naissance=heure_naissance_obj,

            ville_naissance=ville_naissance.strip(),
            genre=genre,

            fratrie=fratrie.strip() if fratrie else None,
            enfance=enfance.strip() if enfance else None,

            acceptation_cgv=acceptation_cgv,
            acceptation_confidentialite=(
                acceptation_confidentialite
            ),
            acceptation_test=True,
            consentement_recherche=acceptation_recherche,
        )

        db.session.add(participation)
        db.session.commit()

        return redirect(
            url_for("versions_beta.confirmation_point_astral")
        )

    return render_template(
        "versions_beta/point_astral.html"
    )

@versions_beta_bp.route(
    "/test-point-astral/confirmation",
    methods=["GET"],
)

def confirmation_point_astral():
    return render_template(
        "versions_beta/confirmation_point_astral_beta.html"
    )