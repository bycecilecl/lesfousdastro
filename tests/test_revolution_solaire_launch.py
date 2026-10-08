"""Vérifie l'ouverture de la vente RS sans paiement ni appel IA."""

import os
import unittest
from datetime import datetime
from unittest.mock import patch

from config import revolution_solaire_launch as launch


class DateSimulee:
    valeur = None

    @classmethod
    def now(cls, tz):
        return datetime.fromisoformat(cls.valeur).replace(tzinfo=tz)


class OuvertureRevolutionSolaireTest(unittest.TestCase):
    def test_ouverture_a_minuit_heure_de_paris_si_drapeau_actif(self):
        scenarios = (
            ("2026-10-08T23:59:00", "1", False),
            ("2026-10-09T00:00:00", "1", True),
            ("2026-10-09T00:00:00", "0", False),
        )
        with patch.object(launch, "datetime", DateSimulee):
            for instant, drapeau, attendu in scenarios:
                with self.subTest(instant=instant, drapeau=drapeau):
                    DateSimulee.valeur = instant
                    with patch.dict(os.environ, {"REVOLUTION_SOLAIRE_SALES_ENABLED": drapeau,
                                               "APP_MAINTENANCE": "0", "PAYMENTS_SANDBOX": "0"}):
                        self.assertEqual(launch.ventes_ouvertes(), attendu)

    def test_essai_anticipe_seulement_en_maintenance_et_sandbox(self):
        with patch.object(launch, "datetime", DateSimulee):
            DateSimulee.valeur = "2026-10-08T16:00:00"
            for maintenance, sandbox, attendu in (
                ("1", "1", True), ("0", "1", False), ("1", "0", False),
            ):
                with self.subTest(maintenance=maintenance, sandbox=sandbox):
                    with patch.dict(os.environ, {
                        "REVOLUTION_SOLAIRE_SALES_ENABLED": "1",
                        "APP_MAINTENANCE": maintenance,
                        "PAYMENTS_SANDBOX": sandbox,
                    }):
                        self.assertEqual(launch.ventes_ouvertes(), attendu)


if __name__ == "__main__":
    unittest.main()
