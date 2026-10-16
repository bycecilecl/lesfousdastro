"""Présentation locale des calculs et de l'analyse RS seule, sans appel IA."""

from html import escape
import json
from pathlib import Path

from .analyse import construire_entree_etape
from .controle import controler_etape, AnalyseRSInvalide
from ..rapport_html import generer_rapport_html
from ..presentation import nom_affiche


def _position(point):
    return f"{point['signe']} {point['degre_dans_signe']:.2f}°"


def formater_preuve_rs(identifiant, fait):
    valeur, objet, categorie = fait["valeur"], fait.get("objet"), fait["type"]
    if categorie == "positions":
        retro = " — rétrograde" if valeur.get("retrograde") else ""
        texte = f"{nom_affiche(objet)} RS : {_position(valeur)}, maison {valeur['maison']} RS{retro}"
    elif categorie == "angles":
        texte = f"{objet} RS : {_position(valeur)}"
    elif categorie == "cuspides":
        texte = f"Cuspide de maison {objet} RS : {_position(valeur)}"
    elif categorie == "maitrises":
        texte = f"Maison {objet} RS en {valeur['signe']} : maîtres {', '.join(valeur['maitres'])}"
    elif categorie == "aspects":
        texte = (f"{nom_affiche(valeur['planete1'])} RS {valeur['aspect'].lower()} "
                 f"{nom_affiche(valeur['planete2'])} RS — orbe {valeur['orbe']:.2f}°")
    elif categorie == "angularites":
        texte = f"{nom_affiche(valeur['point'])} RS près de {valeur['angle']} RS — orbe {valeur['orbe']:.2f}°"
    else:
        texte = json.dumps(valeur, ensure_ascii=False)
    return f"{texte} (`{identifiant}`)"


def generer_relecture_rs_seule(dossier, resultat, chemin, *, nom="", relecture_non_validee=False, notes=None):
    """Rend le résultat validé avec ses preuves et l'inventaire RS en annexe."""
    entree = construire_entree_etape("rs_seule", dossier, {})
    erreurs = []
    try:
        controler_etape("rs_seule", resultat, entree)
    except AnalyseRSInvalide as exc:
        if not relecture_non_validee:
            raise
        erreurs.append(str(exc))
    parties = [f"# Révolution solaire {dossier['cycle']['annee']} — RS seule",
               f"Retour solaire local : **{dossier['cycle']['retour_local']}**.",
               "## Ambiance générale\n\n" + resultat["ambiance"]]
    if erreurs or notes:
        remarques = erreurs + list(notes or [])
        parties.insert(2, "## Lecture de test à corriger\n\n" + "\n".join("- " + note for note in remarques)
                       + "\n\nLe texte reçu est conservé pour relecture ; ce résultat n'est pas validé pour livraison.")
    for enjeu in resultat["enjeux"]:
        parties.append(f"## {enjeu['titre']}\n\n{enjeu['lecture']}")
        preuves = [formater_preuve_rs(cle, dossier["faits"][cle]) for cle in enjeu["preuves"]]
        parties.append("### Faits calculés cités\n\n" + "\n".join("- " + preuve for preuve in preuves))
    parties.append("## Inventaire des positions RS\n\n| Point | Position | Maison RS | Mouvement |\n| --- | --- | --- | --- |")
    for point, position in dossier["rs"]["positions"].items():
        mouvement = "Rétrograde" if position["retrograde"] else "Direct" if position["retrograde"] is False else "—"
        parties.append(f"| {nom_affiche(point)} | {_position(position)} | {position['maison']} | {mouvement} |")
    for point, position in dossier["rs"]["angles"].items():
        parties.append(f"| {point} | {_position(position)} | — | — |")
    parties.append("\n## Les douze maisons RS\n\n| Maison | Cuspide | Maîtres |\n| --- | --- | --- |")
    for numero, cuspide in dossier["rs"]["cuspides"].items():
        maitres = ", ".join(dossier["rs"]["maitrises"][numero]["maitres"])
        parties.append(f"| {numero} | {_position(cuspide)} | {maitres} |")
    chemin = Path(chemin)
    return generer_rapport_html(escape("\n\n".join(parties[:3]) + "\n\n" + _assembler_suite(parties[3:]), quote=False),
                               chemin, nom=escape(nom), annee=dossier["cycle"]["annee"])


def _assembler_suite(parties):
    # Les lignes d'un tableau doivent rester contiguës pour le rendu Markdown.
    texte = ""
    for partie in parties:
        texte += ("\n" if partie.startswith("|") else "\n\n") + partie
    return texte
