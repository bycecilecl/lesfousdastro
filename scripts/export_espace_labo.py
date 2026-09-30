"""Exporte les archives privées d'un compte du labo, PDF inclus, hors du dépôt Git."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


def _lignes(connexion, table, colonne, valeurs):
    if not valeurs:
        return []
    marqueurs = ",".join("?" for _ in valeurs)
    requete = f"SELECT * FROM {table} WHERE {colonne} IN ({marqueurs}) ORDER BY id"
    return [dict(ligne) for ligne in connexion.execute(requete, tuple(valeurs))]


def exporter(source: Path, email: str, sortie: Path) -> None:
    email = email.strip().lower()
    with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as connexion:
        connexion.row_factory = sqlite3.Row
        compte = connexion.execute(
            "SELECT id FROM utilisateurs_espace WHERE lower(email) = ?", (email,)
        ).fetchone()
        if compte is None:
            raise ValueError("Compte introuvable dans le labo.")
        profil = connexion.execute(
            "SELECT id FROM profil_astral WHERE utilisateur_id = ?", (compte["id"],)
        ).fetchone()
        if profil is None:
            raise ValueError("Profil astral introuvable dans le labo.")
        utilisateur_id, profil_id = compte["id"], profil["id"]
        donnees = {
            "cycles_solaires": _lignes(connexion, "cycles_solaires", "profil_id", [profil_id]),
            "cycles_lunaires": _lignes(connexion, "cycles_lunaires", "profil_id", [profil_id]),
            "emails_cycles_abonnement": _lignes(connexion, "emails_cycles_abonnement", "profil_id", [profil_id]),
            "analyses_personnelles": _lignes(connexion, "analyses_personnelles", "utilisateur_id", [utilisateur_id]),
            "droits_analyses_achetees": _lignes(connexion, "droits_analyses_achetees", "utilisateur_id", [utilisateur_id]),
            "entrees_journal": _lignes(connexion, "entrees_journal", "utilisateur_id", [utilisateur_id]),
        }
        analyse_ids = [ligne["id"] for ligne in donnees["analyses_personnelles"]]
        mecanismes = _lignes(connexion, "mecanismes_exploration", "analyse_id", analyse_ids)
        donnees.update({
            "sections_analyse": _lignes(connexion, "sections_analyse", "analyse_id", analyse_ids),
            "enjeux_periode": _lignes(connexion, "enjeux_periode", "analyse_id", analyse_ids),
            "suggestions_mecanisme": _lignes(connexion, "suggestions_mecanisme", "analyse_id", analyse_ids),
            "mecanismes_exploration": mecanismes,
            "observations_mecanisme": _lignes(
                connexion, "observations_mecanisme", "mecanisme_id",
                [ligne["id"] for ligne in mecanismes],
            ),
        })
    dossier_pdf = source.parent / "analyses_uploads"
    pdfs = {}
    for analyse in donnees["analyses_personnelles"]:
        nom = Path(analyse["chemin_resultat"] or "").name
        if not nom or nom != analyse["chemin_resultat"] or not nom.lower().endswith(".pdf"):
            raise ValueError("Chemin de rapport invalide dans le labo.")
        chemin = dossier_pdf / nom
        contenu = chemin.read_bytes()
        if not contenu.startswith(b"%PDF-") or len(contenu) > 15 * 1024 * 1024:
            raise ValueError("Rapport PDF invalide ou trop volumineux dans le labo.")
        pdfs[str(analyse["id"])] = {
            "nom": nom,
            "sha256": hashlib.sha256(contenu).hexdigest(),
            "base64": base64.b64encode(contenu).decode("ascii"),
        }
    paquet = {"version": 1, "email": email, "donnees": donnees, "pdfs": pdfs}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=sortie.parent,
        prefix=".espace-", suffix=".tmp", delete=False,
    ) as temporaire:
        os.chmod(temporaire.name, 0o600)
        json.dump(paquet, temporaire, ensure_ascii=False, separators=(",", ":"))
        temporaire_chemin = Path(temporaire.name)
    temporaire_chemin.replace(sortie)
    print(f"Archives privées exportées vers {sortie} ({sortie.stat().st_size} octets).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()
    exporter(args.source, args.email, args.sortie)
