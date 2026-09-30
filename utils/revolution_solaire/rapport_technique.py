"""Rapport technique lisible d'une révolution solaire, sans interprétation."""

from __future__ import annotations

import json
from pathlib import Path

from utils.configurations_astrologiques import formater_configurations_majeures
from .presentation import nom_affiche


METHOD_PATH = Path(__file__).with_name("methode_v0_3.json")
POINTS_SPECIAUX = {"Lune Noire", "Part de Fortune", "Rahu", "Ketu"}
TYPES_FIGURES_MAJEURES = {"stellium", "t_carre", "grand_trigone", "grand_carre", "diamant"}


def charger_methode(chemin: Path = METHOD_PATH) -> dict:
    """Charge la méthode versionnée plutôt que de disperser ses règles dans le code."""
    return json.loads(chemin.read_text(encoding="utf-8"))


def _format_point(nom: str, point: dict | None, *, maison_reference: str = "RS") -> str:
    if not point:
        return f"- {nom} : donnée indisponible"
    signe = point.get("signe")
    degre = point.get("degre_dans_signe")
    position = f"{signe} {degre:.2f}°" if signe is not None and degre is not None else f"{point.get('degre', 0):.2f}°"
    maisons = []
    if point.get("maison"):
        maisons.append(f"M{point['maison']} {maison_reference}")
    if point.get("maison_natale"):
        maisons.append(f"M{point['maison_natale']} natale")
    suffixe = f" — {', '.join(maisons)}" if maisons else ""
    mouvement = " — rétrograde" if point.get("retrograde") is True else ""
    return f"- {nom} : {position}{suffixe}{mouvement}"


def _orbe_interne(aspect: dict, methode: dict) -> float:
    points = {aspect.get("planete1"), aspect.get("planete2")}
    orbes = methode["orbes"]
    if points & POINTS_SPECIAUX:
        return float(orbes["aspect_interne_point_symbolique"])
    if points & {"Soleil", "Lune"}:
        return float(orbes["aspect_interne_luminaire"])
    return float(orbes["aspect_interne_planete"])


def _format_configurations(configurations: list[dict]) -> list[str]:
    if not configurations:
        return ["- Aucune configuration structurante retenue dans l'orbe indiqué."]
    return [
        f"- {nom_affiche(item['planete1'])} {item['aspect'].lower()} {nom_affiche(item['planete2'])} — orbe {item['orbe']:.2f}°"
        for item in configurations
    ]


def _format_maisons_interceptees(maisons: list[dict]) -> str:
    return ", ".join(
        f"M{item['maison']} ({item['signe']} intercepté)" for item in maisons
    )


def generer_rapport_technique(
    donnees: dict,
    retour_local,
    *,
    methode: dict | None = None,
) -> str:
    """Présente d'abord la RS, puis les résonances natales, sans interprétation."""
    methode = methode or charger_methode()
    placements = donnees["placements_rs"]
    portrait = donnees.get("portrait_natal") or {}
    maitre = donnees.get("maitre_ascendant_rs") or {}
    lignes = [
        "# Révolution solaire — relevé technique",
        "",
        f"- Méthode : v{methode['version']} ({methode['statut']})",
        f"- Retour solaire : {retour_local.strftime('%d/%m/%Y à %H:%M:%S %Z')}",
        f"- Lune Noire : {donnees['parametres']['lune_noire']}",
        "",
        "## La dynamique propre de la révolution solaire",
        _format_point("Ascendant RS", donnees.get("ascendant_rs")),
        _format_point("Soleil RS", placements.get("Soleil")),
        _format_point("Lune RS", placements.get("Lune")),
        "",
        "## Secteurs mis en avant dans la RS",
    ]
    maitres_ascendant = donnees.get("maitres_ascendant_rs") or []
    if maitres_ascendant:
        for index, fiche in enumerate(maitres_ascendant):
            etiquette = "Maître d'Ascendant RS" if len(maitres_ascendant) == 1 else (
                "Maître principal d'Ascendant RS" if index == 0 else "Second maître d'Ascendant RS"
            )
            lignes.insert(8 + index, _format_point(f"{etiquette} ({fiche['nom']})", fiche))
    else:
        lignes.insert(8, _format_point(f"Maître d'Ascendant RS ({maitre.get('nom', 'inconnu')})", maitre))
    angularites = donnees.get("points_angulaires_rs") or []
    if angularites:
        lignes.extend(
            f"- {item['point']} à {item['orbe']:.2f}° de {item['angle']}"
            for item in angularites
        )
    else:
        lignes.append("- Aucun point retenu dans l'orbe angulaire de la méthode.")
    for maison, points in donnees.get("maisons_rs_occupees", {}).items():
        lignes.append(f"- Maison {maison} RS : {', '.join(nom_affiche(point) for point in points)}")

    lignes += ["", "## Positions RS — signes, maisons et rétrogradations"]
    for nom, point in placements.items():
        lignes.append(_format_point(f"{nom_affiche(nom)} RS", point))

    lignes += ["", "## Thèmes prioritaires calculés"]
    themes_prioritaires = donnees.get("themes_prioritaires") or []
    if themes_prioritaires:
        lignes.append("- Un thème est retenu à partir de trois convergences indépendantes.")
        for theme in themes_prioritaires:
            lignes.append(f"- {theme.get('libelle')} — {theme.get('repetitions')} répétitions :")
            lignes.extend(f"  - {preuve.get('texte')}" for preuve in theme.get("preuves") or [])
    else:
        lignes.append("- Aucun thème n'atteint le seuil de trois convergences indépendantes.")

    interceptions = (donnees.get("interceptions_rs") or {}).get("maisons_interceptées") or {}
    lignes += ["", "## Interceptions de la RS"]
    if interceptions:
        for signe, maison in interceptions.items():
            numero = str(maison).split()[-1]
            planetes = [nom_affiche(nom) for nom, point in placements.items() if point.get("signe") == signe]
            maitres = [
                nom_affiche(nom) for nom, point in placements.items()
                if any(
                    item.get("signe") == signe
                    for item in point.get("maisons_gouvernees_interceptees_rs") or []
                )
            ]
            supplement = []
            if planetes:
                supplement.append("planète(s) dans le signe : " + ", ".join(planetes))
            if maitres:
                supplement.append("maître(s) : " + ", ".join(maitres))
            lignes.append(
                f"- {signe} intercepté en M{numero} RS"
                + (" — " + "; ".join(supplement) if supplement else ".")
            )
    else:
        lignes.append("- Aucun signe intercepté dans la RS.")

    lignes += ["", "## Planètes contextuelles de la RS"]
    for contexte in (donnees.get("facteurs_directeurs_rs") or {}).get("planetes_contextuelles", []):
        point = contexte.get("placement_rs") or {}
        lignes.append(_format_point(contexte.get("planete", "Planète"), point))
        for aspect in contexte.get("aspects_internes_rs") or []:
            lignes.append(
                f"  - {nom_affiche(aspect['planete1'])} {aspect['aspect'].lower()} {nom_affiche(aspect['planete2'])} "
                f"— orbe {aspect['orbe']:.2f}°"
            )
        gouvernees_interceptees = point.get("maisons_gouvernees_interceptees_rs") or []
        if gouvernees_interceptees:
            lignes.append(
                "  - Gouverne aussi " + _format_maisons_interceptees(gouvernees_interceptees) + "."
            )

    lignes += ["", "## Maisons transportées par les planètes directrices"]
    for facteur in (donnees.get("facteurs_directeurs_rs") or {}).get("gouvernance_directeurs", []):
        gouvernees_rs = facteur.get("maisons_gouvernees_rs") or []
        gouvernees_interceptees = facteur.get("maisons_gouvernees_interceptees_rs") or []
        precisions = [
            "maîtrise de cuspide : " + (", ".join(f"M{maison}" for maison in gouvernees_rs) or "aucune")
        ]
        if gouvernees_interceptees:
            precisions.append(
                "maîtrise secondaire par interception : "
                + _format_maisons_interceptees(gouvernees_interceptees)
            )
        lignes.append(
            f"- {facteur['planete']} : placé en M{facteur.get('maison_placement_rs')} RS, "
            + "; ".join(precisions) + "."
        )

    figures = [
        configuration
        for configuration in donnees.get("configurations_majeures_rs", [])
        if configuration.get("type") in TYPES_FIGURES_MAJEURES
    ]
    lignes += ["", "## Figures majeures de la révolution solaire"]
    if figures:
        lignes += formater_configurations_majeures(figures).splitlines()
    else:
        lignes.append("- Aucune figure majeure détectée.")

    lignes += ["", "## Aspects internes RS retenus"]
    aspects = [
        aspect for aspect in donnees.get("aspects_internes_rs", [])
        if float(aspect.get("orbe", 999)) <= _orbe_interne(aspect, methode)
    ]
    if aspects:
        lignes.extend(
            f"- {nom_affiche(aspect['planete1'])} {aspect['aspect'].lower()} {nom_affiche(aspect['planete2'])} — orbe {aspect['orbe']:.2f}°"
            for aspect in aspects
        )
    else:
        lignes.append("- Aucun aspect interne ne correspond aux orbes de la méthode.")

    profection = donnees.get("profection_annuelle")
    if profection:
        asc_profecte = profection["ascendant_profecte"]
        maitre_annee = profection["maitre_annee"]
        lignes += [
            "",
            "## Le maître de l'année",
            f"- Profection annuelle : {profection['age']} ans, cycle {profection['cycle']}.",
            (
                f"- Ascendant profecté : {asc_profecte['signe']} "
                f"{asc_profecte['degre_dans_signe']:.2f}° — M{asc_profecte['maison_rs']} RS"
            ),
            f"- Maître traditionnel de l'année : {maitre_annee['nom']}",
            _format_point(f"{maitre_annee['nom']} natal", maitre_annee.get("natal"), maison_reference="natale"),
            _format_point(f"{maitre_annee['nom']} RS", maitre_annee.get("rs")),
            "- Diviseur et participant : à calculer après ajout des directions primaires et des termes égyptiens.",
        ]

    lignes += ["", "## Les résonances avec le thème natal"]
    lignes.append("### Inventaire natal vérifié — positions de naissance")
    for nom, natal in (donnees.get("placements_natals_verifies") or {}).items():
        lignes.append(_format_point(f"{nom_affiche(nom)} natal", natal, maison_reference="natale"))

    lignes.append("### Superpositions RS → natal — ce ne sont pas des placements natals")
    for nom, point in placements.items():
        lignes.append(
            f"- {nom_affiche(nom)} RS tombe en M{point['maison_natale']} natale"
        )

    lignes.append("### Passage des maîtres RS dans le thème natal")
    for facteur in (donnees.get("facteurs_directeurs_rs") or {}).get("gouvernance_directeurs", []):
        gouvernees_natales = facteur.get("maisons_gouvernees_natales") or []
        gouvernees_interceptees_natales = facteur.get("maisons_gouvernees_interceptees_natales") or []
        precisions = [
            "maîtrise de cuspide : " + (", ".join(f"M{maison}" for maison in gouvernees_natales) or "aucune")
        ]
        if gouvernees_interceptees_natales:
            precisions.append(
                "maîtrise secondaire par interception : "
                + _format_maisons_interceptees(gouvernees_interceptees_natales)
            )
        lignes.append(
            f"- {facteur['planete']} : placé en M{facteur.get('maison_placement_natale')} natale, "
            + "; ".join(precisions) + " dans le natal."
        )
    lignes.append(_format_point("Ascendant natal", portrait.get("ascendant"), maison_reference="natale"))
    lignes.append(
        _format_point(
            f"Maître d'Ascendant natal ({(portrait.get('maitre_ascendant') or {}).get('nom', 'inconnu')})",
            portrait.get("maitre_ascendant"),
            maison_reference="natale",
        )
    )
    maisons_gouvernees = (portrait.get("maitre_ascendant") or {}).get("maisons_gouvernees") or []
    if maisons_gouvernees:
        lignes.append("- Maisons gouvernées par ce maître : " + ", ".join(f"M{maison}" for maison in maisons_gouvernees))
    for nom, point in (portrait.get("luminaires") or {}).items():
        lignes.append(_format_point(f"{nom} natal", point, maison_reference="natale"))
    for nom, point in (portrait.get("planetes_personnelles") or {}).items():
        lignes.append(_format_point(f"{nom} natal", point, maison_reference="natale"))
    lignes.append("- Configurations natales structurantes :")
    lignes += _format_configurations(portrait.get("configurations_structurantes") or [])

    resonances = (donnees.get("facteurs_directeurs_rs") or {}).get("resonances_natales") or {}
    lignes.append("### Résonances RS–natal prioritaires")
    contacts_prioritaires = resonances.get("contacts_prioritaires") or []
    if contacts_prioritaires:
        lignes.extend(
            f"- {nom_affiche(item['point_rs'])} RS {item['aspect']} {nom_affiche(item['point_natal'])} natal — orbe {item['orbe']:.2f}°"
            for item in contacts_prioritaires
        )
    else:
        lignes.append("- Aucune résonance prioritaire retenue.")
    lignes.append("### Configurations natales réactivées")
    for reactivation in resonances.get("configurations_natales_reactivees") or []:
        configuration = reactivation["configuration_natale"]
        activations = ", ".join(
            f"{nom_affiche(item['point_rs'])} RS {item['aspect']} {nom_affiche(item['point_natal'])} natal ({item['orbe']:.2f}°)"
            for item in reactivation["contacts_rs_natal"]
        )
        lignes.append(
            f"- Natal : {configuration['planete1']} {configuration['aspect'].lower()} "
            f"{configuration['planete2']} — activé par {activations}."
        )

    contacts = donnees.get("aspects_rs_natal") or []
    lignes.append(
        "- Contacts RS–natal retenus "
        f"(orbe ≤ {donnees['parametres']['orbe_rs_natal']}° ; "
        f"angles RS–natal ≤ {donnees['parametres']['orbe_rs_natal_angles']}°) : {len(contacts)}"
    )
    lignes.extend(
        f"  - {nom_affiche(item['point_rs'])} RS {item['aspect']} {nom_affiche(item['point_natal'])} natal — orbe {item['orbe']:.2f}°"
        for item in contacts
    )

    lignes += ["", "## Points symboliques complémentaires"]
    for nom in ("Rahu", "Ketu", "Lune Noire", "Part de Fortune"):
        lignes.append(_format_point(nom_affiche(nom), placements.get(nom)))
    lignes += ["", "_Ce relevé expose des positions et aspects calculés. Il ne constitue pas encore une interprétation._"]
    return "\n".join(lignes)
