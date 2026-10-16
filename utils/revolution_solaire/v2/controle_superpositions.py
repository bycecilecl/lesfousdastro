"""Compare des projections explicitement annoncées aux maisons déjà calculées.

Contrôle textuel limité : axes ordonnés, points/cuspides nommés, groupes de deux
points et luminaires. Les formulations ambiguës ne sont pas interprétées.
Aucun calcul astrologique ni réécriture du texte.
"""

import re
import unicodedata

ROMAINS = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
NOMBRE = r"(?:12|11|10|[1-9]|xii|viii|vii|iii|xi|ix|vi|iv|ii|x|v|i)"
THEME = r"(?:rs|natal(?:e)?s?)"
ALIASES = {"milieu du ciel": "mc", "fond du ciel": "fc",
           "noeud nord": "rahu", "noeud sud": "ketu"}


def _normaliser(texte):
    texte = unicodedata.normalize("NFD", texte.lower().replace("œ", "oe"))
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def _maison(texte):
    return int(texte) if texte.isdigit() else ROMAINS.index(texte.upper())


def _theme(texte):
    return "rs" if texte == "rs" else "natal"


def controler_superpositions(resultat, faits):
    projections = {}
    noms = set()
    for cle, fait in faits.items():
        if not cle.startswith("SUPERPOSITION."):
            continue
        _, sens, categorie, nom = cle.split(".", 3)
        source = "rs" if sens == "rs_vers_natal" else "natal"
        projections[(source, categorie, _normaliser(nom))] = (cle, fait["valeur"]["maison_cible"])
        if categorie == "points":
            noms.add(_normaliser(nom))
    if not projections:
        return {"erreurs": [], "portee": "Aucune superposition calculée disponible."}

    noms.update(alias for alias, nom in ALIASES.items() if nom in noms)
    points = "|".join(re.escape(nom) for nom in sorted(noms, key=len, reverse=True))
    objet = rf"(?:cuspide\s+(?:de\s+la\s+maison\s+)?{NOMBRE}|{points})"
    sujet = re.compile(rf"\b(?P<objet>{objet})\s+(?P<source>{THEME})\b")
    maison = re.compile(rf"\bmaisons?\s+(?P<nombres>{NOMBRE}(?:\s*(?:et|/|,|–|-)\s*"
                        rf"(?:maison\s+)?{NOMBRE})?)\s+(?P<cible>{THEME})\b")
    axe = re.compile(rf"\baxe\s+(?P<a>{NOMBRE})\s*[–—/-]\s*(?P<b>{NOMBRE})\s+"
                     rf"(?P<source>{THEME})\b[^.!?;\n:]{{0,100}}?\baxe\s+"
                     rf"(?P<c>{NOMBRE})\s*[–—/-]\s*(?P<d>{NOMBRE})\s+(?P<cible>{THEME})\b")
    groupe = re.compile(rf"\b(?P<a>{objet})(?:\s+(?P<source_a>{THEME}))?\s+et\s+"
                        rf"(?:(?:le|la|les|l['’])\s*)?(?P<b>{objet})\s+(?P<source>{THEME})\b")
    luminaires = re.compile(rf"\bluminaires\s+(?P<source>{THEME})\b")
    lieu = re.compile(rf"\bmaison\s+(?P<n>{NOMBRE})\s+(?P<cible>{THEME})\b"
                      rf"(?:(?!\bmaison\b)[^.!?;\n]){{0,140}}?\bou\s+se\s+(?:trouve(?:nt)?|situe(?:nt)?)\s+"
                      rf"(?:aussi\s+)?(?:(?:le|la|les|l['’])\s*)?"
                      rf"(?P<objet>{objet})\s+(?P<source>{THEME})\b")

    def repere(nom):
        if nom.startswith("cuspide "):
            return "cuspides", str(_maison(nom.split()[-1]))
        return "points", ALIASES.get(nom, nom)

    erreurs, deja = [], set()

    def verifier(source, cible, objets, annonces, contexte, *, ordonne=False):
        source, cible = _theme(source), _theme(cible)
        if source == cible:
            return
        attendus = [projections.get((source, *repere(nom))) for nom in objets]
        if any(v is None for v in attendus):
            return
        calcules = [v[1] for v in attendus]
        correct = (calcules == annonces if ordonne else
                   all(n == annonces[0] for n in calcules) if len(annonces) == 1 else
                   set(calcules) == set(annonces))
        if correct:
            return
        cle = (contexte["enjeu"], contexte["champ"], source, tuple(objets), tuple(annonces))
        if cle in deja:
            return
        deja.add(cle)
        erreurs.append({**contexte, "points": objets, "theme_source": source,
                        "theme_cible": cible, "maisons_annoncees": annonces,
                        "maisons_calculees": calcules, "references": [v[0] for v in attendus]})

    for enjeu in resultat.get("enjeux", []):
        textes = [("titre", enjeu.get("titre", "")), ("lecture", enjeu.get("lecture", ""))]
        textes += [(f"exemple {i}", ex.get("texte", "")) for i, ex in enumerate(enjeu.get("exemples", []), 1)]
        for champ, texte in textes:
            for phrase in re.split(r"(?<=[.!?;])\s+|\n", texte):
                normalise = _normaliser(phrase)
                # Ne pas traiter une négation ou hypothèse comme une assertion technique.
                if re.search(r"\b(?:pas|non|jamais|aucun|aucune|si|serait|seraient)\b", normalise):
                    continue
                contexte = {"enjeu": enjeu["id"], "champ": champ, "extrait": phrase}
                for match in axe.finditer(normalise):
                    verifier(match["source"], match["cible"],
                             ["cuspide " + match["a"], "cuspide " + match["b"]],
                             [_maison(match["c"]), _maison(match["d"])], contexte, ordonne=True)
                for match in sujet.finditer(normalise):
                    suite = normalise[match.end():match.end() + 220]
                    suivant = sujet.search(suite)
                    if suivant:
                        suite = suite[:suivant.start()]
                    for destination in maison.finditer(suite):
                        annonces = [_maison(n.group()) for n in re.finditer(rf"\b{NOMBRE}\b", destination["nombres"])]
                        if len(annonces) == 1:
                            verifier(match["source"], destination["cible"], [match["objet"]], annonces, contexte)
                for match in groupe.finditer(normalise):
                    if match["source_a"] and _theme(match["source_a"]) != _theme(match["source"]):
                        continue
                    suite = normalise[match.end():match.end() + 220]
                    suivant = sujet.search(suite)
                    if suivant:
                        suite = suite[:suivant.start()]
                    for destination in maison.finditer(suite):
                        annonces = [_maison(n.group()) for n in re.finditer(rf"\b{NOMBRE}\b", destination["nombres"])]
                        verifier(match["source"], destination["cible"], [match["a"], match["b"]], annonces,
                                 contexte, ordonne=len(annonces) == 2 and "respectivement" in suite[:destination.end()])
                for match in luminaires.finditer(normalise):
                    suite = normalise[match.end():match.end() + 100]
                    suivant = sujet.search(suite)
                    if suivant:
                        suite = suite[:suivant.start()]
                    for destination in maison.finditer(suite):
                        annonces = [_maison(n.group()) for n in re.finditer(rf"\b{NOMBRE}\b", destination["nombres"])]
                        verifier(match["source"], destination["cible"], ["soleil", "lune"], annonces, contexte)
                for match in lieu.finditer(normalise):
                    verifier(match["source"], match["cible"], [match["objet"]], [_maison(match["n"])], contexte)
    return {"erreurs": erreurs,
            "portee": "Projections explicites dans titres, lectures et exemples ; pas une certification de chaque phrase."}


def decrire_contradictions(controle):
    lignes = []
    for erreur in controle["erreurs"]:
        chiffres = lambda valeurs: "–".join(ROMAINS[n] for n in valeurs)
        origine = "RS" if erreur["theme_source"] == "rs" else "natal"
        cible = "RS" if erreur["theme_cible"] == "rs" else "natale"
        lignes.append(f"{erreur['enjeu']} / {erreur['champ']} : {', '.join(erreur['points'])} {origine}"
                      f" → maison(s) {chiffres(erreur['maisons_annoncees'])} {cible} annoncée(s) ;"
                      f" calcul : {chiffres(erreur['maisons_calculees'])} {cible}.")
    return "\n".join(lignes)
