from datetime import date, datetime, time, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
)

from extensions import db

from models.commandes import (
    Acceptation,
    Beneficiaire,
    Commande,
    CreneauDisponible,
    StatutCommande,
    hasher_token,
)

from utils.email_sender import (
    envoyer_notification_formulaire_commande_admin,
)


commande_formulaire_bp = Blueprint(
    "commande_formulaire_bp",
    __name__,
)


@commande_formulaire_bp.route(
    "/commande/<token>",
    methods=["GET", "POST"],
)
def afficher_formulaire_commande(token):
    token_hash = hasher_token(token)

    commande = Commande.query.filter_by(
        token_hash=token_hash,
    ).first()

    if not commande:
        abort(404)

    maintenant = datetime.now(timezone.utc)
    date_minimum_creneau = maintenant.date() + timedelta(days=10)

    if (
        commande.date_limite_lien
        and commande.date_limite_lien < maintenant
    ):
        abort(410)

    if commande.statut == StatutCommande.INFOS_RECUES:
        return render_template(
            "commande/confirmation.html",
            commande=commande,
        )

    # ---------------------------------------------------------
    # Affichage du formulaire
    # ---------------------------------------------------------

    if request.method == "GET":
        creneaux_disponibles = (
            CreneauDisponible.query
            .filter(
                CreneauDisponible.disponible.is_(True),
                CreneauDisponible.date_creneau >= date_minimum_creneau,
            )
            .order_by(
                CreneauDisponible.date_creneau.asc(),
                CreneauDisponible.heure_creneau.asc(),
            )
            .all()
        )

        return render_template(
            "commande/formulaire.html",
            commande=commande,
            token=token,
            creneaux_disponibles=creneaux_disponibles,
        )

    # ---------------------------------------------------------
    # Lecture du formulaire
    # ---------------------------------------------------------

    beneficiaire_prenom = request.form.get(
        "beneficiaire_prenom",
        "",
    ).strip()

    beneficiaire_nom = request.form.get(
        "beneficiaire_nom",
        "",
    ).strip()

    date_naissance_str = request.form.get(
        "date_naissance",
        "",
    ).strip()

    heure_naissance_str = request.form.get(
        "heure_naissance",
        "",
    ).strip()

    lieu_naissance = request.form.get(
        "lieu_naissance",
        "",
    ).strip()

    creneau_realisation = request.form.get(
        "creneau_realisation",
        "",
    ).strip()

    questionnaire_attentes = request.form.get(
        "questionnaire_attentes",
        "",
    ).strip()

    questionnaire_approfondir = request.form.get(
        "questionnaire_approfondir",
        "",
    ).strip()

    informations_exactes = (
        request.form.get("informations_exactes") == "1"
    )

    acceptation_cgv = (
        request.form.get("acceptation_cgv") == "1"
    )

    acceptation_confidentialite = (
        request.form.get("acceptation_confidentialite") == "1"
    )

    # ---------------------------------------------------------
    # Vérification des champs obligatoires
    # ---------------------------------------------------------

    champs_obligatoires_valides = all(
        [
            beneficiaire_prenom,
            beneficiaire_nom,
            date_naissance_str,
            heure_naissance_str,
            lieu_naissance,
            creneau_realisation,
            informations_exactes,
            acceptation_cgv,
            acceptation_confidentialite,
        ]
    )

    if not champs_obligatoires_valides:
        return render_template(
            "commande/formulaire.html",
            commande=commande,
            token=token,
            erreur=(
                "Merci de remplir tous les champs obligatoires "
                "et de cocher les trois cases de validation."
            ),
        ), 400

    try:
        date_naissance = date.fromisoformat(
            date_naissance_str
        )

        heure_naissance = time.fromisoformat(
            heure_naissance_str
        )

    except ValueError:
        return render_template(
            "commande/formulaire.html",
            commande=commande,
            token=token,
            erreur=(
                "La date ou l’heure de naissance "
                "n’est pas valide."
            ),
        ), 400

    # ---------------------------------------------------------
    # Enregistrement dans Railway
    # ---------------------------------------------------------

    try:
        beneficiaire = commande.beneficiaire

        if not beneficiaire:
            beneficiaire = Beneficiaire()

            db.session.add(beneficiaire)
            db.session.flush()

            commande.beneficiaire_id = beneficiaire.id

        beneficiaire.prenom = beneficiaire_prenom
        beneficiaire.nom = beneficiaire_nom
        beneficiaire.date_naissance = date_naissance
        beneficiaire.heure_naissance = heure_naissance
        beneficiaire.heure_naissance_connue = True
        beneficiaire.heure_naissance_approximative = False
        beneficiaire.lieu_naissance = lieu_naissance
        beneficiaire.infos_completes = True

        if creneau_realisation == "a_planifier":
            commande.creneau_realisation = "a_planifier"

        else:
            try:
                creneau_id = int(creneau_realisation)
            except ValueError:
                db.session.rollback()

                return render_template(
                    "commande/formulaire.html",
                    commande=commande,
                    token=token,
                    erreur="Le créneau sélectionné n’est pas valide.",
                    creneaux_disponibles=(
                        CreneauDisponible.query
                        .filter(
                            CreneauDisponible.disponible.is_(True),
                            CreneauDisponible.date_creneau
                            >= date_minimum_creneau,
                        )
                        .order_by(
                            CreneauDisponible.date_creneau.asc(),
                            CreneauDisponible.heure_creneau.asc(),
                        )
                        .all()
                    ),
                ), 400

            creneau_choisi = (
                CreneauDisponible.query
                .filter(
                    CreneauDisponible.id == creneau_id,
                    CreneauDisponible.disponible.is_(True),
                    CreneauDisponible.date_creneau
                    >= date_minimum_creneau,
                )
                .with_for_update()
                .first()
            )

            if not creneau_choisi:
                db.session.rollback()

                return render_template(
                    "commande/formulaire.html",
                    commande=commande,
                    token=token,
                    erreur=(
                        "Ce créneau vient d’être réservé. "
                        "Merci d’en choisir un autre."
                    ),
                    creneaux_disponibles=(
                        CreneauDisponible.query
                        .filter(
                            CreneauDisponible.disponible.is_(True),
                            CreneauDisponible.date_creneau
                            >= date_minimum_creneau,
                        )
                        .order_by(
                            CreneauDisponible.date_creneau.asc(),
                            CreneauDisponible.heure_creneau.asc(),
                        )
                        .all()
                    ),
                ), 409

            creneaux_du_jour = (
                CreneauDisponible.query
                .filter_by(
                    date_creneau=creneau_choisi.date_creneau,
                    disponible=True,
                )
                .with_for_update()
                .all()
            )

            for creneau in creneaux_du_jour:
                creneau.disponible = False

            creneau_choisi.commande_id = commande.id
            creneau_choisi.date_reservation = maintenant

            commande.creneau_realisation = (
                f"{creneau_choisi.date_creneau.isoformat()} "
                f"à {creneau_choisi.heure_creneau.strftime('%H:%M')}"
            )
        
        commande.questionnaire_attentes = (
            questionnaire_attentes or None
        )
        commande.questionnaire_approfondir = (
            questionnaire_approfondir or None
        )
        commande.statut = StatutCommande.INFOS_RECUES

        acceptation = commande.acceptation

        if not acceptation:
            acceptation = Acceptation(
                commande_id=commande.id,
            )

            db.session.add(acceptation)

        acceptation.informations_exactes_attestees = True
        acceptation.informations_exactes_texte = (
            "Je confirme que les informations renseignées "
            "sont exactes."
        )
        acceptation.date_attestation_exactitude = maintenant

        acceptation.cgv_acceptees = True
        acceptation.cgv_case_texte = (
            "J’accepte les Conditions Générales de Vente."
        )
        acceptation.date_acceptation_cgv = maintenant

        acceptation.politique_presentee = True
        acceptation.politique_information_texte = (
            "J’ai pris connaissance de la "
            "Politique de confidentialité."
        )
        acceptation.date_information_politique = maintenant

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Erreur pendant l’enregistrement du formulaire "
            "de la commande %s.",
            commande.reference,
        )

        return render_template(
            "commande/formulaire.html",
            commande=commande,
            token=token,
            erreur=(
                "Une erreur est survenue pendant "
                "l’enregistrement. Merci de réessayer."
            ),
        ), 500

    try:
        envoyer_notification_formulaire_commande_admin(
            reference_commande=commande.reference,
            nom=beneficiaire_nom,
            prenom=beneficiaire_prenom,
            email_client=commande.client.email,
            date_naissance=date_naissance.strftime("%d/%m/%Y"),
            heure_naissance=heure_naissance.strftime("%H:%M"),
            lieu_naissance=lieu_naissance,
            creneau_realisation=commande.creneau_realisation,
            attentes=questionnaire_attentes,
            approfondir=questionnaire_approfondir,
        )

    except Exception:
        current_app.logger.exception(
            "Le formulaire de la commande %s a été enregistré, "
            "mais la notification administrateur n’a pas pu être envoyée.",
            commande.reference,
        )

    return render_template(
        "commande/confirmation.html",
        commande=commande,
    )