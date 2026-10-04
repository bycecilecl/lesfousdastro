"""Relances bornées des étapes de livraison d'une RS déjà payée."""

from time import sleep


def retenter(operation, *, essais=3, pause=None, signaler=None):
    """Retente une étape échouée et renvoie son premier résultat valide.

    L'appelant choisit une archive distincte pour chaque nouvel appel IA. Les
    étapes PDF et stockage peuvent être relancées sans redemander le rapport.
    """
    if pause is None:
        pause = sleep
    for numero in range(1, essais + 1):
        try:
            return operation(numero)
        except Exception as erreur:
            if signaler is not None:
                signaler(numero, essais, erreur)
            if numero == essais:
                raise
            pause(min(2 ** (numero - 1), 8))
