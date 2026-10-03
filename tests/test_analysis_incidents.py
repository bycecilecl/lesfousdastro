"""La cliente reste informée même si l'alerte administrative échoue."""

import os
import unittest
from unittest.mock import patch

from services.analysis_incidents import notifier_generation_interrompue


class NotificationIncidentTest(unittest.TestCase):
    def test_administratrice_et_cliente_sont_prevenues(self):
        messages = []

        def sender(**message):
            messages.append(message)
            return True

        with patch.dict(os.environ, {"EMAIL_ADMIN": "admin@example.test"}):
            resultat = notifier_generation_interrompue(
                commande_id="commande-test", produit="forces_defis",
                email_client="cliente@example.test", nom_client="Alice", sender=sender,
            )

        self.assertEqual(resultat, {"admin": True, "client": True})
        self.assertEqual([m["destinataire"] for m in messages],
                         ["admin@example.test", "cliente@example.test"])
        self.assertIn("commande-test", messages[0]["contenu_txt"])
        self.assertIn("rien à repayer", messages[1]["contenu_txt"])

    def test_echec_admin_ne_bloque_pas_avis_cliente(self):
        destinataires = []

        def sender(**message):
            destinataires.append(message["destinataire"])
            if len(destinataires) == 1:
                raise RuntimeError("Service mail temporairement indisponible")
            return True

        with patch.dict(os.environ, {"EMAIL_ADMIN": "admin@example.test"}):
            resultat = notifier_generation_interrompue(
                commande_id="commande-test", produit="revolution_solaire",
                email_client="cliente@example.test", nom_client="Alice", sender=sender,
            )

        self.assertEqual(resultat, {"admin": False, "client": True})
        self.assertEqual(destinataires, ["admin@example.test", "cliente@example.test"])


if __name__ == "__main__":
    unittest.main()
