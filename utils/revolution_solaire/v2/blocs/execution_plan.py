"""Plan avant le bloc 1 : un appel maximum, archivage et aperçu sans envoi."""

import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import sys

from ...archives_generation import ecrire_json, lire_json, verrou_demande
from ..service import _etape_archivee, _fournisseur_borne, options_claude_v2
from ..terminal import JournalTerminal, Tee, afficher_requete
from .execution import _source
from . import plan_initial


ROOT = Path(__file__).resolve().parents[4]
SORTIES = ROOT / "rapports_test/revolution_solaire_v2/par_blocs/plan_initial"


class JournalPlan(JournalTerminal):
    """Le plan n'appartient pas à l'ancien parcours séquentiel à huit étapes."""

    def __call__(self, evenement, **details):
        if evenement == "etape":
            self.partie = Path(details["dossier"])
            print("\nPLAN INITIAL — grands sujets de l'année")
            print("Archives :", self.partie)
            return
        super().__call__(evenement, **details)


def lancer_plan(cas_a_tester, *, source_factuel, modele="claude-sonnet-5", apercu=False, sur_dossier=None):
    if len(cas_a_tester) != 1:
        raise ValueError("Le plan attend un profil unique.")
    cas = cas_a_tester[0]
    factuel, source = _source(cas, source_factuel)
    prompt, entree, preparation = plan_initial.construire_prompt_plan(factuel)
    demande = {"mode": plan_initial.VERSION, "modele": modele,
               "profil": {k: cas[k] for k in ("personne", "lieu_rs", "annee")},
               "source_factuel": str(source),
               "empreinte_faits": hashlib.sha256((source / "dossier_factuel.json").read_bytes()).hexdigest(),
               "empreinte_prompt": hashlib.sha256(prompt.encode()).hexdigest()}
    with verrou_demande(demande, SORTIES) as dossier:
        if sur_dossier is not None:
            sur_dossier(Path(dossier))
        for nom, donnees in (("demande.json", demande), ("donnees_envoyees_plan.json", entree),
                             ("preparation_plan.json", preparation)):
            ecrire_json(dossier, nom, donnees)
        (dossier / "prompt_complet_plan.txt").write_text(prompt, encoding="utf-8")
        sources = [Path(__file__), Path(plan_initial.__file__), plan_initial.PROMPT_PATH,
                   Path(__file__).with_name("convergence.py"), Path(__file__).with_name("filtrage_transits.py"),
                   ROOT / "utils/revolution_solaire/v2/filtrage_aspects.py",
                   ROOT / "utils/revolution_solaire/v2/memoire_redaction.py"]
        cle = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()[:16]
        snapshots = dossier / "versions_code" / cle
        snapshots.mkdir(parents=True, exist_ok=True)
        for path in sources:
            if not (snapshots / path.name).exists():
                shutil.copy2(path, snapshots / path.name)
        with (dossier / "terminal.log").open("a", encoding="utf-8") as log:
            with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
                print("PLAN COMMUN — avant les cinq blocs. Aucun contexte personnel envoyé.")
                print("Archives :", dossier)
                if apercu:
                    options = options_claude_v2(modele, {"max_tokens": plan_initial.MAX_TOKENS, "temperature": 0.5,
                        "reflexion": "disabled", "niveau_effort": "low", "schema_sortie": plan_initial.schema_plan()})
                    afficher_requete(modele, prompt, options, apercu=True)
                    print("APERÇU DU PLAN — aucun appel Claude.")
                    return 0
                journal = JournalPlan(modele=modele)
                appel = _fournisseur_borne(dossier, modele, 1, journal=journal)
                try:
                    resultat = _etape_archivee(dossier, "plan_initial", lambda appeler:
                        plan_initial.generer_plan(factuel, appeler=appeler), appel, journal=journal)
                    ecrire_json(dossier, "plan_commun.json", resultat["plan"])
                    ecrire_json(dossier, "diagnostic_plan.json", resultat["diagnostic"])
                    print("Plan reçu :", json.dumps(resultat["plan"], ensure_ascii=False, indent=2))
                    print("Diagnostic :", json.dumps(resultat["diagnostic"], ensure_ascii=False, indent=2))
                    if not resultat["plan"]["fils"]:
                        print("Aucun sujet utilisable reçu : réponse conservée, aucun appel de rédaction ni relance automatique.")
                        return 1
                    return 0
                except KeyboardInterrupt:
                    print("Arrêt manuel : les éléments reçus restent archivés.")
                    return 130
                except Exception as exc:
                    print("ARRÊT DU PLAN :", type(exc).__name__, "—", exc)
                    print("Réponse reçue conservée si disponible ; aucun appel suivant ni relance.")
                    return 1
