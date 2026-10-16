"""Compare un bloc 1 archivé à Sonnet 5.5, sans modifier les autres moteurs."""

from pathlib import Path

from ...archives_generation import lire_json
from .execution import ROOT, lancer_bloc_1


def lancer_comparaison_sonnet_5_5(cas_a_tester, *, source_bloc_1, apercu=False):
    """Un appel maximum, mêmes faits ; seule la règle d'affichage direct est actualisée."""
    source = (ROOT / source_bloc_1).expanduser().resolve()
    demande = lire_json(source, "demande.json")
    plan = lire_json(source, "plan_commun.json")
    if not isinstance(demande, dict) or demande.get("utiliser_bdd") is not False:
        raise ValueError("Choisis un bloc 1 archivé sans BDD. Aucun appel lancé.")
    if not isinstance(plan, dict) or not plan.get("fils"):
        raise ValueError("Plan de référence absent. Aucun nouvel appel de plan ne sera lancé.")
    return lancer_bloc_1(
        cas_a_tester, source_factuel=Path(demande["source_factuel"]), plan=plan,
        utiliser_bdd=False, modele="claude-sonnet-5-5", reflexion="adaptive",
        niveau_effort="medium", max_tokens=10000, reference_comparaison=source, apercu=apercu,
    )
