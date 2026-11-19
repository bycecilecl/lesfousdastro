"""Calendrier et exécution des mails bêta. Sans option : suivi en lecture seule."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choix = parser.add_mutually_exclusive_group()
    choix.add_argument("--planifier", action="store_true", help="Calcule seulement les dates des comptes inscrits, sans IA ni envoi.")
    choix.add_argument("--executer", action="store_true", help="Traite les mails dus si l’activation et la période bêta le permettent.")
    options = parser.parse_args()
    from utils.application_mails_evenements import creer_application
    from extensions import db
    from sqlalchemy import func, inspect, select
    from models.espace_personnel import InscriptionMailsBeta, MailEvenementAbonne
    app = creer_application()
    with app.app_context():
        try:
            moteur = db.session.get_bind(mapper=InscriptionMailsBeta)
            if not all(inspect(moteur).has_table(n) for n in ("inscriptions_mails_beta", "mails_evenements_abonnes")):
                raise ValueError("Stockage absent : applique d’abord script/migrate_mails_evenements.py --apply.")
            if options.executer:
                from utils.automatisation_mails_evenements import passer_automatisation
                resultat = passer_automatisation()
            elif options.planifier:
                from utils.mails_evenements import planifier_inscription
                total = 0
                for inscription in InscriptionMailsBeta.query.filter_by(actif=True).all():
                    total += planifier_inscription(inscription)
                db.session.commit()
                resultat = {"rendez_vous_ajoutes": total, "appels_IA": 0, "envois": 0}
            else:
                compte = db.session.execute(select(func.count()).select_from(InscriptionMailsBeta)).scalar_one()
                etats = db.session.execute(select(MailEvenementAbonne.statut, func.count()).group_by(MailEvenementAbonne.statut)).all()
                resultat = {"lecture_seule": True, "inscriptions": compte, "mails_par_etat": dict(etats)}
            print(json.dumps(resultat, ensure_ascii=False, indent=2), flush=True)
        finally:
            db.session.remove()
            for moteur in db.engines.values():
                moteur.dispose()


if __name__ == "__main__":
    main()
