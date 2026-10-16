"""Relevés natals et RS lisibles ; les calculs précis restent dans le dossier."""

import json
import re

from copy import deepcopy
from .connaissances import formater_reperes_rs
from .filtrage_aspects import fait_autorise, filtrer_historique
from .releve_transits import transit_compact

ROMAINS = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
ASPECTS = {"Carre": "Carré", "carre": "Carré"}
FIGURES = {
    "conjonction": "Conjonction", "stellium": "Stellium", "t_carre": "T-carré",
    "grand_trigone": "Grand trigone", "grand_carre": "Grand carré",
    "diamant": "Diamant (cerf-volant)", "triangle_mineur": "Triangle mineur",
}


def degres_minutes(valeur):
    minutes = int(round(float(valeur) * 60))
    return f"{minutes // 60}°{minutes % 60:02d}′"


def nom_aspect(valeur):
    return ASPECTS.get(valeur, str(valeur).capitalize())


def position_compacte(nom, position, signes_interceptes):
    """Champs utiles uniquement ; ne touche pas aux valeurs du calculateur."""
    resultat = {
        "planete": nom,
        "signe": position["signe"],
        "degre": degres_minutes(position["degre_dans_signe"]),
        "maison": position["maison"],
    }
    if isinstance(position.get("retrograde"), bool):
        resultat["retrograde"] = position["retrograde"]
    dignite = position.get("dignite_essentielle")
    if dignite and dignite != "neutre":
        resultat["dignite"] = dignite
    if position["signe"] in signes_interceptes:
        resultat["intercepte"] = True
    return resultat


def references_lisibles(entree):
    """Les libellés du relevé remplacent les identifiants techniques côté Claude."""
    references = {}
    for cle, fait in entree["faits"].items():
        valeur, categorie = fait["valeur"], fait["type"]
        objet = str(fait.get("objet", ""))
        if categorie in {"positions", "angles"}:
            libelle = objet
        elif categorie == "cuspides":
            libelle = "Cuspide " + ROMAINS[int(objet)]
        elif categorie == "maitrises":
            libelle = "Maîtrise " + ROMAINS[int(objet)]
        elif categorie == "aspects":
            libelle = f"{nom_aspect(valeur['aspect'])} {valeur['planete1']}–{valeur['planete2']}"
        elif categorie == "configurations":
            libelle = "Figure " + objet
        elif categorie == "interceptions":
            libelle = "Interceptions"
        elif categorie == "repartition":
            libelle = {"planetes_par_mode": "Modes des planètes",
                       "planetes_par_element": "Éléments des planètes",
                       "cuspides_par_mode": "Modes des cuspides"}[objet]
        elif categorie == "angularites":
            libelle = f"Angularité {valeur['point']}–{valeur['angle']}"
        else:
            raise ValueError("Catégorie RS non prévue dans le relevé : " + categorie)
        if libelle in references.values():
            raise ValueError("Deux faits RS portent le même libellé : " + libelle)
        references[cle] = libelle
    return references


def formater_releve_rs(entree, *, reference="rs", preciser_theme=False):
    faits = {cle: fait for cle, fait in entree["faits"].items() if fait_autorise(fait)}
    refs = references_lisibles({"faits": faits})
    if preciser_theme:
        theme = "Natal" if reference == "natal" else "RS"
        refs = {cle: f"{theme} / {libelle}" for cle, libelle in refs.items()}
    positions = {f["objet"]: f["valeur"] for f in faits.values() if f["type"] == "positions"}
    angles = {f["objet"]: f["valeur"] for f in faits.values() if f["type"] == "angles"}
    interceptions = next((f["valeur"] for f in faits.values() if f["type"] == "interceptions"), {})
    signes_interceptes = set(interceptions.get("signes_interceptes", []))

    def situation(nom, *, degre=False, etat=False):
        p = positions.get(nom, angles.get(nom, {}))
        morceaux = [nom]
        if degre:
            morceaux.append(degres_minutes(p["degre_dans_signe"]))
        morceaux.append(p["signe"])
        if p["signe"] in signes_interceptes:
            morceaux.append("intercepté")
        if etat and nom in positions:
            if p.get("retrograde") is True:
                morceaux.append("rétrograde")
            elif p.get("retrograde") is False:
                morceaux.append("direct")
            dignite = p.get("dignite_essentielle")
            if dignite and dignite != "neutre":
                morceaux.append("en " + dignite)
        if p.get("maison"):
            morceaux.append("maison " + ROMAINS[int(p["maison"])])
        return ", ".join(morceaux)

    aspects_par_point = {nom: [] for nom in (*positions, *angles)}
    for cle, fait in faits.items():
        if fait["type"] != "aspects":
            continue
        a = fait["valeur"]
        p1, p2 = a["planete1"], a["planete2"]
        porteur = p1 if p1 in angles or p2 not in angles else p2
        autre = p2 if porteur == p1 else p1
        aspects_par_point.setdefault(porteur, []).append(
            f"{refs[cle]} (orbe {degres_minutes(a['orbe'])})")

    titre_theme = "THÈME NATAL" if reference == "natal" else ("RÉVOLUTION SOLAIRE" if preciser_theme else "RS SEULE")
    lignes = [titre_theme, "", "POSITIONS PLANÉTAIRES"]
    cle_positions = "positions_natales" if reference == "natal" else "positions_rs"
    lignes.append('{"' + cle_positions + '": [')
    entrees = [position_compacte(nom, p, signes_interceptes) for nom, p in positions.items()]
    lignes.extend("  " + json.dumps(p, ensure_ascii=False) + ("," if i < len(entrees) - 1 else "")
                  for i, p in enumerate(entrees))
    lignes.append("]}")
    lignes.extend(("", "ASPECTS INTERNES"))
    for nom, aspects in aspects_par_point.items():
        if nom not in angles:
            lignes.extend("- " + aspect for aspect in aspects)
    lignes.extend(("", "ANGLES ET ASPECTS"))
    for nom in angles:
        cle = f"{reference.upper()}.angles.{nom}"
        lignes.append(f"- {refs[cle]} : {situation(nom, degre=True)}")
        lignes.extend("  — " + aspect for aspect in aspects_par_point[nom])
    lignes.extend(("", "MAISONS"))
    for numero in range(1, 13):
        cle = f"{reference.upper()}.cuspides.{numero}"
        maitrise = f"{reference.upper()}.maitrises.{numero}"
        if cle not in faits and maitrise not in faits:
            continue
        occupants = [nom for nom, position in positions.items() if position.get("maison") == numero]
        if cle in faits:
            p = faits[cle]["valeur"]
            lignes.append(f"- {refs[cle]} : {p['signe']} {degres_minutes(p['degre_dans_signe'])}")
        if maitrise in faits:
            maitres = faits[maitrise]["valeur"]["maitres"]
            lignes.append(f"  {refs[maitrise]} : {', '.join(maitres)}")
    lignes.extend(("", "INTERCEPTIONS"))
    maisons_interceptees = interceptions.get("maisons_interceptées", {})
    for cle, fait in faits.items():
        if fait["type"] == "interceptions":
            lignes.append(f"- {refs[cle]} : " + (" ; ".join(
                f"{signe} en {maison}" for signe, maison in maisons_interceptees.items()) or "aucune"))
    lignes.extend(("", "FIGURES ASTROLOGIQUES"))
    for cle, fait in faits.items():
        if fait["type"] != "configurations":
            continue
        figure = fait["valeur"]
        noms = figure.get("planetes", [])
        description = f"{FIGURES.get(figure['type'], figure['type'])} : {'–'.join(noms)}"
        if figure.get("planete_focale"):
            description += "; planète focale : " + figure["planete_focale"]
        if figure.get("planetes_en_opposition"):
            description += "; opposition : " + "–".join(figure["planetes_en_opposition"])
        lignes.append(f"- {refs[cle]} — {description}")
        # Réutilise les aspects calculés entre les participants, sans recalcul.
        for a in faits.values():
            v = a["valeur"]
            if a["type"] == "aspects" and v["planete1"] in noms and v["planete2"] in noms:
                lignes.append(f"  {v['planete1']} {nom_aspect(v['aspect']).lower()} {v['planete2']}"
                              f" (orbe {degres_minutes(v['orbe'])})")
    lignes.extend(("", "RÉPARTITIONS CALCULÉES"))
    for cle, fait in faits.items():
        if fait["type"] == "repartition":
            lignes.append(f"- {refs[cle]} : " + ", ".join(f"{k} {v}" for k, v in fait["valeur"].items()))
        elif fait["type"] == "angularites":
            lignes.append(f"- {refs[cle]} : orbe {degres_minutes(fait['valeur']['orbe'])}")
    lignes.extend(("", "FAITS INCONTOURNABLES : " + ", ".join(refs[c] for c in entree["faits_incontournables"] if c in refs)))
    return "\n".join(lignes)


def references_prompt(entree):
    """Distingue les mêmes noms dans les deux thèmes sans modifier les faits."""
    if entree.get("etape") == "rs_seule":
        return references_lisibles(entree)
    refs = {}
    for reference, nom in (("natal", "Natal"), ("rs", "RS")):
        faits = {cle: fait for cle, fait in entree["faits"].items()
                 if cle.startswith(reference.upper() + ".")}
        refs.update({cle: f"{nom} / {libelle}" for cle, libelle
                     in references_lisibles({"faits": faits}).items()})
    for cle, fait in entree["faits"].items():
        if cle.startswith("SUPERPOSITION."):
            refs[cle] = f"{fait['source']}.{fait['type']}.{fait['objet']}"
        elif cle == "PROFECTION.annuelle":
            refs[cle] = "profection"
    return refs


def superpositions_compactes(faits):
    """Point/cuspide → maison d'arrivée, sans recopier les longitudes."""
    resultat = {}
    for cle, fait in faits.items():
        if not cle.startswith("SUPERPOSITION."):
            continue
        sens, categorie, nom = fait["source"], fait["type"], fait["objet"]
        if sens not in {"rs_vers_natal", "natal_vers_rs"} or categorie not in {"points", "cuspides"}:
            raise ValueError("Superposition inconnue : " + cle)
        projection = resultat.setdefault(sens, {"points": {}, "cuspides": {}})
        projection[categorie][nom] = fait["valeur"]["maison_cible"]
    return resultat


def formater_superpositions(projections):
    """Explicite chaque projection calculée et sa référence, sans recalcul."""
    lignes = ["SUPERPOSITIONS CALCULÉES"]
    for sens, categories in projections.items():
        source, cible = ("RS", "natale") if sens == "rs_vers_natal" else ("natal", "RS")
        for categorie, objets in categories.items():
            for nom, maison in objets.items():
                objet = "Cuspide " + ROMAINS[int(nom)] if categorie == "cuspides" else nom
                lignes.append(f"- {objet} {source} → maison {ROMAINS[maison]} {cible}"
                              f" [{sens}.{categorie}.{nom}]")
    return "\n".join(lignes)


def profection_compacte(profection):
    """Informations annuelles, sans recopier les positions du maître."""
    ascendant = profection["ascendant_profecte"]
    return {
        "age": profection["age"],
        "maison_annuelle": profection["maison_annuelle"],
        "signe": ascendant["signe"],
        "maitre_annee": profection["maitre_annee"]["nom"],
        "ascendant_profecte": {
            "maison_natale": ascendant["maison_natale"],
            "maison_rs": ascendant["maison_rs"],
        },
    }


def extrait_court(texte, limite=600):
    """Extrait le début du texte existant ; aucune reformulation ni génération."""
    texte = " ".join(texte.split())
    if len(texte) <= limite:
        return texte
    debut = texte[:limite - 1]
    fin_phrase = max(debut.rfind(". "), debut.rfind("! "), debut.rfind("? "))
    if fin_phrase >= limite // 2:
        return debut[:fin_phrase + 1] + "…"
    return debut.rsplit(" ", 1)[0] + "…"


def historique_compact(analyses, *, limite=600, memo=False):
    """Résumés par extraction pour les étapes intermédiaires, sans toucher aux archives."""
    resultat = {}
    for etape, precedente in analyses.items():
        resume = {"enjeux": []}
        if "ambiance" in precedente:
            resume["ambiance_resume"] = extrait_court(precedente["ambiance"], 400)
        for enjeu in precedente["enjeux"]:
            champs = ("id", "titre", "importance") if memo else ("id", "titre", "importance", "preuves", "liens", "effet")
            compact = {champ: deepcopy(enjeu[champ]) for champ in champs}
            compact["resume"] = extrait_court(enjeu["lecture"], limite)
            if "periodes" in enjeu:
                compact["periodes"] = deepcopy(enjeu["periodes"])
            resume["enjeux"].append(compact)
        resultat[etape] = resume
    return resultat


def formater_donnees_prompt(entree):
    """Les relevés sont identiques dans les analyses, le corps et la conclusion."""
    if entree.get("etape") == "rs_seule":
        releve = formater_releve_rs(entree)
        if "reperes_interpretatifs" in entree:
            releve += "\n\n" + formater_reperes_rs(entree["reperes_interpretatifs"], references_prompt(entree))
        return releve
    refs = references_prompt(entree)
    blocs = []
    for reference in ("natal", "rs"):
        faits = {cle: fait for cle, fait in entree["faits"].items()
                 if cle.startswith(reference.upper() + ".")}
        if faits:
            incontournables = [cle for cle in entree.get("faits_incontournables", []) if cle in faits]
            blocs.append(formater_releve_rs({"faits": faits, "faits_incontournables": incontournables},
                                           reference=reference, preciser_theme=True))
    projections = superpositions_compactes(entree["faits"])
    if projections:
        blocs.append(formater_superpositions(projections))
    if "PROFECTION.annuelle" in entree["faits"]:
        profection = profection_compacte(entree["faits"]["PROFECTION.annuelle"]["valeur"])
        blocs.append("PROFECTION\n" + json.dumps({"profection": profection}, ensure_ascii=False, indent=2))
    autres = deepcopy(entree)
    autres.pop("faits_a_examiner", None)
    for champ in ("analyses_precedentes", "analyses"):
        if champ in autres:
            autres[champ] = filtrer_historique(autres[champ], entree["faits"])
            for precedente in autres[champ].values():
                for ancien_suivi in ("couverture", "references_consolidees", "equivalences_couverture"):
                    precedente.pop(ancien_suivi, None)
            if champ == "analyses_precedentes":
                annuel = entree.get("etape") == "activations_annuelles"
                autres[champ] = historique_compact(autres[champ], limite=150 if annuel else 300 if entree.get("etape") == "profection" else 600,
                                                  memo=annuel)
    autres["faits"] = {cle: fait for cle, fait in autres["faits"].items() if cle not in refs}
    if entree.get("etape") == "activations_annuelles" or entree.get("calendrier_compact"):
        autres["faits"] = {cle: transit_compact(fait["valeur"]) if cle.startswith("TRANSIT.") else fait
                           for cle, fait in autres["faits"].items()}
        autres["presentation_transits"] = ("Dates au jour en UTC ; horaires précis archivés. exacts=[] : aucun passage exact calculé ; "
                                           "exacts=null : dates exactes non disponibles. minimum est fourni sans passage exact daté. "
                                           "Les changements de sens sont indiqués dans phases. Dans complements, les champs listés dans "
                                           "identiques_au_contact_principal reprennent exactement les valeurs "
                                           "du contact principal de la même fenêtre TRANSIT.")
        if "cycle" in autres:
            cycle = autres["cycle"]
            autres["cycle"] = {"debut_utc": cycle["debut_utc"].split("T", 1)[0],
                                "fin_utc": cycle["fin_utc"].split("T", 1)[0], "annee": cycle["annee"], "age": cycle["age"]}
        autres.pop("calendrier_compact", None)
    for champ in ("faits_incontournables",):
        if champ in autres:
            autres[champ] = [refs.get(cle, cle) for cle in autres[champ]]
    blocs.append("AUTRES DONNÉES\n" + json.dumps(autres, ensure_ascii=False, separators=(",", ":")))
    return "\n\n".join(blocs)


def retablir_references_rs(resultat, entree):
    """Conserve les contrôles existants sans exposer leurs clés dans le relevé."""
    def cle_reference(libelle):
        return re.sub(r"\s*/\s*", "/", libelle.strip())
    correspondance = {cle_reference(libelle): cle for cle, libelle in references_prompt(entree).items()}
    resultat = deepcopy(resultat)
    def convertir(objet, champ):
        if isinstance(objet, dict) and isinstance(objet.get(champ), list):
            objet[champ] = [correspondance.get(cle_reference(ref), ref) if isinstance(ref, str) else ref
                           for ref in objet[champ]]
    for enjeu in resultat.get("enjeux", []):
        # Analyses : fiches d'enjeux. Conclusion : identifiants textuels.
        # Les ids de la conclusion sont conservés et vérifiés par le contrôle.
        if not isinstance(enjeu, dict):
            continue
        convertir(enjeu, "preuves")
        for exemple in enjeu.get("exemples", []):
            convertir(exemple, "preuves")
    for ligne in resultat.get("couverture", []):
        convertir(ligne, "faits")
    for section in resultat.get("sections", []):
        convertir(section, "preuves")
    convertir(resultat, "preuves")
    return resultat
