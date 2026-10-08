"""Plan éditorial déterministe du corps d'une révolution solaire.

Le plan organise des faits déjà calculés. Il ne crée ni aspects, ni scénarios,
ni dates ; la chronologie reste dans les activations annuelles séparées.
"""
from __future__ import annotations


PLANETES_STRUCTURANTES = {"Saturne", "Uranus", "Neptune", "Pluton", "Jupiter"}
FIGURES_DEVELOPPEES = {"t_carre", "grand_trigone", "grand_carre", "cerf_volant", "yod", "diamant"}


def construire_plan_chapitres(donnees: dict) -> list[dict]:
    """Sépare les dynamiques fortes sans imposer les placements d'un thème donné."""
    placements = donnees.get("placements_rs") or {}
    figures = donnees.get("configurations_majeures_rs") or []
    themes = donnees.get("themes_prioritaires") or []
    maisons = donnees.get("maisons_rs_occupees") or {}
    plan: list[dict] = [{
        "titre": "Ascendant RS, ses maîtres et les luminaires",
        "angle": "Ouverture obligatoire ; nommer le mouvement propre des maîtres sans absorber les autres chapitres.",
    }]

    for figure in figures:
        if figure.get("type") not in FIGURES_DEVELOPPEES or figure.get("etat") == "invalide":
            continue
        membres = [str(n) for n in figure.get("planetes") or []]
        if len(membres) < 3:
            continue
        nom = str(figure.get("type")).replace("_", " ")
        focale = figure.get("planete_focale")
        titre = f"{nom.capitalize()} : {', '.join(membres)}"
        if focale:
            titre += f" ; foyer {focale}"
        plan.append({"titre": titre, "angle": "Lire la figure, ses tensions et sa portée ; ne pas absorber les autres placements majeurs."})
        if sum(" : " in item["titre"] for item in plan) >= 2:
            break

    chapitres_placement = 0
    for planete, position in placements.items():
        maison = position.get("maison")
        if planete not in PLANETES_STRUCTURANTES or maison not in (5, 7):
            continue
        if any(planete in (f.get("planetes") or []) for f in figures if f.get("type") in FIGURES_DEVELOPPEES):
            continue
        plan.append({
            "titre": f"{planete} RS en maison {maison}",
            "angle": "Développement distinct : enjeux propres, contact natal vérifié s'il existe, contradiction et exemple concret différent.",
        })
        chapitres_placement += 1
        if chapitres_placement == 2:
            break

    relation_deja_deployee = chapitres_placement >= 1 and any(
        f.get("type") in FIGURES_DEVELOPPEES for f in figures
    )
    for theme in themes:
        code = theme.get("code")
        if code == "relation" and relation_deja_deployee:
            continue
        libelle = theme.get("libelle")
        if libelle:
            plan.append({
                "titre": str(libelle),
                "angle": "Relier au moins deux preuves calculées, avec une nuance ou un exemple nouveau ; éviter l'inventaire.",
            })

    for maison, noms in maisons.items():
        if str(maison) not in {"8", "10", "12"}:
            continue
        planetes = [nom for nom in noms if nom in placements and nom not in {"Rahu", "Ketu"}]
        if len(planetes) < 2:
            continue
        if any(str(maison) in item["titre"] for item in plan):
            continue
        plan.append({
            "titre": f"Maison {maison} RS : {', '.join(planetes)}",
            "angle": "Distinguer l'effet de chaque planète, leurs maîtrises et leurs liens natals ; ne pas répéter une figure déjà expliquée.",
        })
        break

    contacts_serres = [
        item for item in donnees.get("aspects_rs_natal") or []
        if item.get("orbe") is not None and float(item["orbe"]) <= 2.5
    ]
    if len(contacts_serres) >= 2:
        plan.append({
            "titre": "Résonances RS–natal les plus serrées",
            "angle": "Expliquer ce que chaque contact majeur ajoute ou modifie ; respecter le sens RS vers natal.",
        })
    if donnees.get("profection_annuelle"):
        plan.append({
            "titre": "Maître de l'année par profection",
            "angle": "Relier la profection aux enjeux précédents sans reprendre leur interprétation.",
        })
    return plan
