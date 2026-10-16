"""Préparation locale par défaut ; génération IA uniquement avec --generer."""

import argparse
import json
from pathlib import Path

from .service import generer_rapport_rs_v2
from .analyse import ETAPES


def main():
    parser = argparse.ArgumentParser(description="Nouvelle Révolution solaire V2 séquentielle")
    parser.add_argument("demande", type=Path, help="JSON : personne, lieu_rs, annee, contexte_client facultatif")
    parser.add_argument("--sortie", type=Path, required=True, help="Dossier privé des étapes sauvegardées")
    parser.add_argument("--generer", action="store_true", help="Reprend les étapes ; les nouveaux appels nécessitent un plafond explicite")
    parser.add_argument("--appels-max", type=int, default=0,
                        help="Plafond TOTAL de requêtes Claude pour ce dossier, reprises comprises (défaut : 0)")
    parser.add_argument("--sans-raffinement", action="store_true", help="Garde seulement les fenêtres quotidiennes")
    parser.add_argument("--etape", choices=ETAPES, help="Avec --generer, s'arrête après cette analyse")
    parser.add_argument("--modele", help="Identifiant API Claude pour cette génération uniquement")
    parser.add_argument("--config-env", type=Path, help="Fichier de configuration existant à charger pour ce processus")
    args = parser.parse_args()
    if args.config_env:
        from dotenv import load_dotenv
        if not args.config_env.is_file():
            parser.error("Le fichier de configuration indiqué n'existe pas.")
        load_dotenv(args.config_env, override=False)
    demande = json.loads(args.demande.read_text(encoding="utf-8"))
    resultat = generer_rapport_rs_v2(
        personne=demande["personne"], lieu_rs=demande["lieu_rs"], annee=demande["annee"],
        contexte_client=demande.get("contexte_client"), stockage_dir=args.sortie,
        preparation_seule=not args.generer, autoriser_generation=args.generer,
        raffiner_transits=not args.sans_raffinement, arreter_apres=args.etape, modele=args.modele,
        limite_appels_ia=args.appels_max)
    if args.generer and args.etape:
        print(f"Étape {resultat['etape']} sauvegardée : {resultat['dossier']}")
    elif args.generer:
        print(f"Rapport sauvegardé : {resultat.dossier_generation}")
    else:
        print(f"Dossier factuel sauvegardé : {resultat['dossier']}")
        print(f"Faits inventoriés : {resultat['controle']['nombre_faits']} ; aucun appel IA.")


if __name__ == "__main__":
    main()
