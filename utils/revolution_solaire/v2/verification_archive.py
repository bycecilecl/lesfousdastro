"""Vérification locale d'une réponse enregistrée : lecture seule des archives.

Ce module ne fournit aucun appel IA ni recalcul astrologique. Les diagnostics
sont enregistrés séparément, sans réécrire la réponse ou son ancien contrôle.
"""

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .analyse import construire_entree_etape, parser_json_reponse
from .controle import AnalyseRSInvalide, controler_etape
from .controle_superpositions import decrire_contradictions
from .releve_rs import retablir_references_rs

ROOT = Path(__file__).resolve().parents[3]


def _changements_references(brut, normalise):
    modifications = []
    for avant, apres in zip(brut.get("enjeux", []), normalise.get("enjeux", [])):
        listes = [("preuves", avant.get("preuves", []), apres.get("preuves", []))]
        listes += [(f"exemple {i}", a.get("preuves", []), b.get("preuves", []))
                   for i, (a, b) in enumerate(zip(avant.get("exemples", []), apres.get("exemples", [])), 1)]
        for champ, refs_avant, refs_apres in listes:
            for initiale, reconnue in zip(refs_avant, refs_apres):
                if initiale != reconnue:
                    modifications.append({"enjeu": avant.get("id"), "champ": champ,
                                          "reference_initiale": initiale, "reference_reconnue": reconnue})
    return modifications


def verifier_analyse4_archive(source):
    """Relit uniquement l'appel 4 choisi ; renvoie 1 si son nouveau contrôle bloque."""
    source = (ROOT / source).expanduser().resolve()
    racine_sorties = ROOT / "rapports_test/revolution_solaire_v2/verifications_locales"
    session = racine_sorties / datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y%m%d_%H%M%S_%f")
    session.mkdir(parents=True, exist_ok=False)
    lignes = []

    def afficher(texte):
        lignes.append(str(texte))
        print(texte, flush=True)

    def lire(nom):
        return json.loads((source / nom).read_text(encoding="utf-8"))

    diagnostic = {"source": str(source), "mode": "verification_locale_sans_IA",
                  "archives_originales_modifiees": False}
    code = 2
    try:
        afficher("VÉRIFICATION LOCALE — APPEL 4 ENREGISTRÉ")
        afficher(f"Source : {source}")
        afficher("Aucun appel Claude, aucun recalcul. Archives d'origine conservées.")
        factuel = lire("dossier_factuel.json")
        historique = lire("historique_utilise.json")
        brut = parser_json_reponse(lire("superpositions_maisons/reponse.json")["texte"])
        entree = construire_entree_etape("superpositions_maisons", factuel, historique)
        resultat = retablir_references_rs(brut, entree)
        changements = _changements_references(brut, resultat)
        diagnostic["references_reconnues"] = changements
        afficher(f"\nRéférences converties vers les identifiants des faits : {len(changements)}")
        for changement in changements:
            afficher(f"  {changement['enjeu']} / {changement['champ']} : "
                     f"{changement['reference_initiale']} → {changement['reference_reconnue']}")
        try:
            controle = controler_etape("superpositions_maisons", resultat, entree)
        except AnalyseRSInvalide as exc:
            diagnostic["controle"] = {"statut": "bloque", "raison": str(exc)}
            projections = getattr(exc, "diagnostic_superpositions", None)
            if projections is not None:
                diagnostic["controle_superpositions"] = projections
                afficher(f"\nCONTRADICTIONS RECONNUES : {len(projections['erreurs'])}")
                afficher(decrire_contradictions(projections))
                for erreur in projections["erreurs"]:
                    afficher(f"\nExtrait ({erreur['enjeu']} / {erreur['champ']}) : {erreur['extrait']}")
            else:
                afficher("\nCONTRÔLE BLOQUÉ : " + str(exc))
                afficher("Le contrôle des maisons n'a pas été atteint si une erreur de structure ou de références précède.")
            afficher("\nLa réponse reste à revoir. Aucun passage n'a été corrigé automatiquement.")
            code = 1
        else:
            diagnostic["controle"] = controle
            afficher("\nAucune contradiction reconnue par ces contrôles. Ce résultat ne certifie pas chaque phrase.")
            code = 0
    except (OSError, ValueError, KeyError, TypeError, AnalyseRSInvalide) as exc:
        diagnostic["erreur_verification"] = {"type": type(exc).__name__, "raison": str(exc)}
        afficher(f"\nVÉRIFICATION INTERROMPUE : {type(exc).__name__} — {exc}")
    finally:
        afficher(f"\nDiagnostic : {session / 'diagnostic.json'}")
        afficher(f"Journal : {session / 'terminal.log'}")
        (session / "diagnostic.json").write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
        (session / "terminal.log").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return code
