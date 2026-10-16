"""Plafond explicite des requêtes Claude, conservé entre les reprises."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import os

from ..archives_generation import GenerationAbsente, ecrire_json, lire_json


class BudgetAppelsIA:
    def __init__(self, dossier, limite=0):
        if isinstance(limite, bool) or not isinstance(limite, int) or limite < 0:
            raise ValueError("Le plafond d'appels IA doit être un entier positif ou nul.")
        self.dossier = Path(dossier)
        self.limite = limite

    @contextmanager
    def _journal(self):
        fd = os.open(self.dossier / "verrou_budget_ia", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a") as fichier:
            fcntl.flock(fichier.fileno(), fcntl.LOCK_EX)
            try:
                journal = lire_json(self.dossier, "budget_ia.json")
                if journal is None:
                    # Les tentatives anciennes comptent aussi : changer le
                    # plafond ne remet jamais le compteur à zéro.
                    journal = {"tentatives_anterieures": len(list(self.dossier.rglob("appel.json"))),
                               "appels": []}
                yield journal
            finally:
                fcntl.flock(fichier.fileno(), fcntl.LOCK_UN)

    def _verifier(self, journal):
        nombre = journal["tentatives_anterieures"] + len(journal["appels"])
        if nombre >= self.limite:
            raise GenerationAbsente(
                f"Appel Claude bloqué : {nombre} tentative(s) enregistrée(s), "
                f"plafond explicite {self.limite}. Aucun appel réseau lancé.")

    def verifier_disponible(self):
        with self._journal() as journal:
            # Figer le compteur avant que texte_archive crée son marqueur.
            ecrire_json(self.dossier, "budget_ia.json", journal)
            self._verifier(journal)

    def reserver(self, modele, prompt, max_tokens):
        with self._journal() as journal:
            self._verifier(journal)
            numero = len(journal["appels"])
            journal["appels"].append({
                "modele": modele, "debut_utc": datetime.now(timezone.utc).isoformat(),
                "caracteres_entree": len(prompt), "max_tokens_sortie": max_tokens,
                "statut": "reserve_avant_reseau",
            })
            ecrire_json(self.dossier, "budget_ia.json", journal)
            return numero

    def terminer(self, numero, *, statut, usage=None):
        with self._journal() as journal:
            journal["appels"][numero]["statut"] = statut
            if usage is not None:
                journal["appels"][numero]["usage_tokens"] = usage
            ecrire_json(self.dossier, "budget_ia.json", journal)
