"""Affichage manuel de la préparation du plan ; aucun fournisseur IA importé."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import uuid

from .convergence import preparer_donnees_plan


ROOT = Path(__file__).resolve().parents[4]


def afficher_preparation_plan(source_factuel):
    source = Path(source_factuel).expanduser()
    if not source.is_absolute():
        source = ROOT / source
    if source.is_dir():
        source = source / "dossier_factuel.json"
    brut = source.read_bytes()
    dossier = json.loads(brut)
    resultat = preparer_donnees_plan(dossier)
    identifiant = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    sortie = ROOT / "rapports_test/revolution_solaire_v2/preparation_plan" / identifiant
    sortie.mkdir(parents=True, exist_ok=False)
    references = {cle for e in resultat["candidats"] for cle in e["cles"]}
    fichiers = {
        "preparation_plan.json": resultat,
        "faits_sources.json": {cle: f for cle, f in dossier["faits"].items() if cle in references},
        "source.json": {"chemin": str(source.resolve()), "sha256": hashlib.sha256(brut).hexdigest(),
                        "appels_ia": 0, "theme_recalcule": False},
    }
    for nom, contenu in fichiers.items():
        (sortie / nom).write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    versions = sortie / "versions_code"
    versions.mkdir()
    for nom in ("convergence.py", "filtrage_transits.py", "execution_convergence.py"):
        (versions / nom).write_bytes(Path(__file__).with_name(nom).read_bytes())
    lignes = ["PRÉPARATION DU PLAN — AUCUN APPEL IA", f"Calculs archivés : {source}",
              "Ce classement compte les familles de faits. Il ne mesure pas leur force astrologique.",
              "Le plan général n'est pas encore rédigé ni transmis aux blocs."]
    for e in resultat["candidats"]:
        lignes.append(f"\n{e['point']} — {e['score']} familles ; {e['faits_independants']} groupes de faits")
        lignes.append("Familles : " + ", ".join(e["familles"]))
        lignes.append("Références : " + ", ".join(e["cles"]))
        for t in e["transits"]:
            contacts = t["contacts_calcules"]
            premier = contacts[0]
            lignes.append(f"  {premier['planete']} / {premier['aspect']} / {premier['cadre_cible']}:{premier['cible']} : "
                          + f"{t['passages']} passages exacts archivés — " + ", ".join(t["dates"]))
    lignes.append("\nMAISONS — HORS SCORE\n" + json.dumps(resultat["contexte_maisons"], ensure_ascii=False, indent=2))
    lignes.append("\nÉLÉMENTS ÉCARTÉS OU À RELIRE\n" + json.dumps(resultat["diagnostic"], ensure_ascii=False, indent=2))
    lignes.extend([f"\nDonnées : {sortie / 'preparation_plan.json'}", f"Faits d'origine : {sortie / 'faits_sources.json'}",
                   "Aucun appel Claude ; aucun rapport généré."])
    journal = "\n".join(lignes) + "\n"
    (sortie / "terminal.log").write_text(journal, encoding="utf-8")
    print(journal, end="")
    return 0
