"""Contrôles factuels déterministes d'un rapport de révolution solaire.

Ce module ne modifie jamais le texte de Claude et n'appelle aucun LLM. Il
signale les affirmations techniques qu'il arrive à identifier sans ambiguïté.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import re
import unicodedata


AFFICHAGE_VERS_INTERNE = {
    "soleil": "Soleil", "lune": "Lune", "mercure": "Mercure", "venus": "Vénus",
    "mars": "Mars", "jupiter": "Jupiter", "saturne": "Saturne", "uranus": "Uranus",
    "neptune": "Neptune", "pluton": "Pluton", "chiron": "Chiron",
    "lune noire": "Lune Noire", "part de fortune": "Part de Fortune",
    "noeud nord": "Rahu", "noeud sud": "Ketu", "ascendant": "Ascendant",
    "descendant": "Descendant", "mc": "MC", "fc": "FC",
}
ROMAINS = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(char for char in texte if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", texte).strip()


def _maison(nombre: str) -> int | None:
    valeur = _normaliser(nombre).replace("maison", "").strip()
    if valeur.isdigit():
        return int(valeur)
    return ROMAINS.get(valeur)


def _affichage(nom: str) -> str:
    return {
        "Rahu": "Nœud Nord", "Ketu": "Nœud Sud",
    }.get(nom, nom)


def _faits_aspects(donnees: dict) -> set[tuple[str, str, str]]:
    faits = set()
    for aspect in donnees.get("aspects_internes_rs") or []:
        p1, p2 = aspect.get("planete1"), aspect.get("planete2")
        if p1 and p2:
            faits.add(("rs", *sorted((p1, p2)), _normaliser(aspect.get("aspect", ""))))
    for aspect in donnees.get("aspects_rs_natal") or []:
        p_rs, p_natal = aspect.get("point_rs"), aspect.get("point_natal")
        if p_rs and p_natal:
            faits.add(("rs_natal", p_rs, p_natal, _normaliser(aspect.get("aspect", ""))))
    return faits


def _aspect_mentionne(phrase: str) -> str | None:
    correspondances = {
        "conjonction": ("conjonction", "conjoint", "conjointe"),
        "opposition": ("opposition", "oppose", "opposee"),
        "carré": ("carre",),
        "trigone": ("trigone",),
        "sextile": ("sextile",),
        "quinconce": ("quinconce",),
    }
    normalise = _normaliser(phrase)
    for canonique, mots in correspondances.items():
        if any(re.search(rf"\b{mot}\b", normalise) for mot in mots):
            return _normaliser(canonique)
    return None


def _points_qualifies(phrase: str) -> list[tuple[str, str]]:
    normalise = _normaliser(phrase)
    trouves = []
    for affiche, interne in AFFICHAGE_VERS_INTERNE.items():
        motif = rf"\b{re.escape(affiche)}\s+(rs|natal(?:e)?)\b"
        for match in re.finditer(motif, normalise):
            nature = "rs" if match.group(1) == "rs" else "natal"
            trouves.append((interne, nature))
    return list(dict.fromkeys(trouves))


def _planete_mentionnee(texte: str) -> str | None:
    """Retrouve une planète dans une formulation de maîtrise non ambiguë."""
    normalise = _normaliser(texte)
    for affiche, interne in AFFICHAGE_VERS_INTERNE.items():
        if interne in {"Ascendant", "Descendant", "MC", "FC"}:
            continue
        if re.search(rf"\b{re.escape(affiche)}\b", normalise):
            return interne
    return None


def _doublons(texte: str) -> list[str]:
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    cles = []
    originaux = {}
    for phrase in phrases:
        cle = _normaliser(phrase)
        if len(cle) < 70 or cle.startswith("#"):
            continue
        cles.append(cle)
        originaux.setdefault(cle, phrase.strip())
    compte = Counter(cles)
    return [originaux[cle] for cle, occurrences in compte.items() if occurrences > 1]


def _phrases(texte: str) -> list[str]:
    phrases = []
    for paragraphe in re.split(r"\n\s*\n", texte):
        for phrase in re.split(r"(?<=[.!?])\s+", paragraphe):
            phrase = phrase.strip()
            if phrase and not phrase.startswith("#"):
                phrases.append(phrase)
    return phrases


def _maitrises_affirmees(phrase: str):
    """Ne lit que l'objet de « gouverne / maître de », jamais le placement."""
    normalisee = _normaliser(phrase)
    for affiche, interne in AFFICHAGE_VERS_INTERNE.items():
        if interne in {"Ascendant", "Descendant", "MC", "FC"}:
            continue
        nom = re.escape(affiche)
        motifs = (
            rf"\b{nom}(?:\s+rs)?\s+gouverne(?:\s+aussi)?\s+"
            rf"(?:ta|tes|la|les|une|un|ma|mes)?\s*maison\s+([ivx]+|\d+)\s+(rs|natale?)\b",
            rf"\b{nom}(?:\s+rs)?\s+(?:est\s+)?maitre(?:sse)?\s+"
            rf"(?:de\s+)?(?:ta|tes|la|les)?\s*maison\s+([ivx]+|\d+)\s+(rs|natale?)\b",
        )
        for motif in motifs:
            for match in re.finditer(motif, normalisee):
                yield interne, _maison(match.group(1)), match.group(2)


def _controle_angularites(texte: str, donnees: dict) -> list[str]:
    alertes = []
    angularites = {
        (item.get("point"), item.get("angle")): float(item.get("orbe", 99))
        for item in donnees.get("points_angulaires_rs") or []
    }
    for phrase in _phrases(texte):
        normale = _normaliser(phrase)
        if "transit" in normale:
            continue
        match = re.search(
            r"\b(pile sur|exactement sur|conjonction (?:exacte|serree)|quasi conjoints?)\b"
            r"[^.!?]{0,70}?\b(?:l'|au |a l'|a )?(ascendant|descendant|mc|fc)\s+(?:rs|natal)\b",
            normale,
        )
        if not match or match.group(2) not in {"ascendant", "descendant", "mc", "fc"}:
            continue
        angle = AFFICHAGE_VERS_INTERNE[match.group(2)]
        portion = normale[:match.start()]
        # « Mars et Pluton ... pile sur l'Ascendant » attribue le contact aux deux.
        noms = [
            interne for affiche, interne in AFFICHAGE_VERS_INTERNE.items()
            if interne not in {"Ascendant", "Descendant", "MC", "FC"}
            and re.search(rf"\b{re.escape(affiche)}\b", portion)
        ]
        if not noms or "natal" in match.group(0):
            continue
        for nom in dict.fromkeys(noms):
            orbe = angularites.get((nom, angle))
            limite = 4.0 if match.group(1).startswith("quasi") else 1.0
            if orbe is None or orbe > limite:
                detail = "aucun contact angulaire retenu" if orbe is None else f"orbe calculé {orbe:.2f}°"
                alertes.append(
                    f"Proximité à {angle} RS exagérée pour {_affichage(nom)} ({detail}) : « {phrase} »"
                )
    return alertes


def _controle_contacts_rs_natal(texte: str, donnees: dict) -> list[str]:
    alertes = []
    faits = {
        (item.get("point_rs"), item.get("point_natal"), _normaliser(item.get("aspect", "")))
        for item in donnees.get("aspects_rs_natal") or []
    }
    for phrase in _phrases(texte):
        normale = _normaliser(phrase)
        if "transit" in normale:
            continue
        for match in re.finditer(
            r"\bconjonction(?:\s+(?:exacte|serree))?\s+(?:a |au |avec )?(?:ton |ta |l'|le )?"
            r"(ascendant|descendant|mc|fc)\s+natal\b",
            normale,
        ):
            cible = AFFICHAGE_VERS_INTERNE[match.group(1)]
            mentions = []
            for affiche, nom in AFFICHAGE_VERS_INTERNE.items():
                if nom in {"Ascendant", "Descendant", "MC", "FC"}:
                    continue
                mentions.extend(
                    (trouve.start(), nom)
                    for trouve in re.finditer(rf"\b{re.escape(affiche)}(?:\s+rs)?\b", normale[:match.start()])
                )
            if not mentions:
                continue
            nom = max(mentions)[1]
            if (nom, cible, "conjonction") not in faits:
                alertes.append(
                    f"Conjonction RS–natal absente du calcul ({_affichage(nom)} RS / {cible} natal) : « {phrase} »"
                )
    return alertes


def _controle_profection(texte: str, donnees: dict) -> list[str]:
    profection = donnees.get("profection_annuelle") or {}
    asc_profecte = profection.get("ascendant_profecte") or {}
    maison_rs = asc_profecte.get("maison_rs")
    if not maison_rs:
        return []
    alertes = []
    for phrase in _phrases(texte):
        normale = _normaliser(phrase)
        if "profection" not in normale and "maitre de l'annee" not in normale:
            continue
        if re.search(r"\bmaison\s+([ivx]+|\d+)\s+natale\b", normale):
            alertes.append(
                f"Maison de profection présentée comme natale ; le relevé donne M{maison_rs} RS : « {phrase} »"
            )
    return alertes


def _controle_transits(texte: str, transits_directeurs: list[dict]) -> list[str]:
    if not transits_directeurs:
        return []
    faits = {
        (_normaliser(str(item.get("planete_transit", ""))),
         _normaliser(str(item.get("cible", ""))),
         _normaliser(str(item.get("reference", ""))),
         _normaliser(str(item.get("aspect", ""))))
        for item in transits_directeurs
    }
    alertes = []
    planetes = r"soleil|lune|mercure|venus|mars|jupiter|saturne|uranus|neptune|pluton"
    for paragraphe in re.split(r"\n\s*\n", texte):
        if "transit" not in _normaliser(paragraphe):
            continue
        for phrase in _phrases(paragraphe):
            normale = _normaliser(phrase)
            for match in re.finditer(
                rf"\b({planetes})(?:\s+en\s+transit)?\s+sur\s+(?:ta|ton|la|le)?\s*"
                rf"({planetes})(?:\s+(rs|natal(?:e)?))?\b",
                normale,
            ):
                mobile, cible, reference = match.groups()
                references = {"rs" if reference == "rs" else "natal"} if reference else {
                    fait[2] for fait in faits if fait[0] == mobile and fait[1] == cible
                }
                if not references or not any(
                    (mobile, cible, ref, "conjonction") in faits for ref in references
                ):
                    alertes.append(
                        f"« Sur » suggère une conjonction de transit non calculée ({mobile} / {cible}) : « {phrase} »"
                    )
    return alertes


def verifier_rapport_revolution_solaire(
    texte: str, donnees: dict, transits_directeurs: list[dict] | None = None,
) -> str:
    """Retourne un relevé de contrôles, sans modifier ``texte``."""
    alertes: list[str] = []
    normalise = _normaliser(texte)
    placements_natals = donnees.get("placements_natals_verifies") or {}
    placements_rs = donnees.get("placements_rs") or {}

    # Le rapport final ne doit jamais montrer le raisonnement incertain du
    # modèle (« orbe non fourni », « je ne peux pas l'affirmer »). Il doit soit
    # s'appuyer sur un fait calculé, soit ne pas mentionner la configuration.
    for phrase in re.split(r"(?<=[.!?])\s+", texte):
        phrase_normalisee = _normaliser(phrase)
        if any(
            marqueur in phrase_normalisee
            for marqueur in ("orbe non fourni", "je ne peux pas l'affirmer", "je ne peux pas affirmer")
        ):
            alertes.append(
                f"Raisonnement incertain affiché dans le rapport : « {phrase.strip()} »"
            )

    # Les affirmations de placement natal sont comparées au thème natal réel.
    for affiche, interne in AFFICHAGE_VERS_INTERNE.items():
        if interne not in placements_natals:
            continue
        motif = rf"\b{re.escape(affiche)}\s+natal(?:e)?[^.\n]{{0,100}}?\bmaison\s+([ivx]+|\d+)"
        for match in re.finditer(motif, normalise):
            annoncee = _maison(match.group(1))
            attendue = placements_natals[interne].get("maison")
            if annoncee and attendue and annoncee != attendue:
                alertes.append(
                    f"{_affichage(interne)} natal annoncé en M{annoncee}, "
                    f"calculé en M{attendue}."
                )

        # Une phrase de superposition doit correspondre à la maison natale où
        # tombe le point RS, pas à la maison natale du point de naissance.
        if interne not in placements_rs:
            continue
        motif = (
            rf"\b{re.escape(affiche)}\s+rs[^.\n]{{0,160}}?"
            rf"(?:dans|superpose[^.\n]{{0,30}}?a)\s+(?:ta\s+)?maison\s+([ivx]+|\d+)\s+natale"
        )
        for match in re.finditer(motif, normalise):
            annoncee = _maison(match.group(1))
            attendue = placements_rs[interne].get("maison_natale")
            if annoncee and attendue and annoncee != attendue:
                alertes.append(
                    f"Superposition de {_affichage(interne)} RS annoncée en M{annoncee} natale, "
                    f"calculée en M{attendue} natale."
                )

    # On contrôle la maison explicitement gouvernée, sans confondre avec la
    # maison où la planète est placée dans la suite de la phrase.
    for phrase in _phrases(texte):
        for planete, maison, referentiel in _maitrises_affirmees(phrase):
            if not maison:
                continue
            point = placements_rs.get(planete) or {}
            if referentiel == "rs":
                maisons = set(point.get("maisons_gouvernees_rs") or [])
                maisons |= {
                    item.get("maison")
                    for item in point.get("maisons_gouvernees_interceptees_rs") or []
                }
                etiquette = "RS"
            else:
                maisons = set(point.get("maisons_gouvernees_natales") or [])
                maisons |= {
                    item.get("maison")
                    for item in point.get("maisons_gouvernees_interceptees_natales") or []
                }
                etiquette = "natale"
            if maison not in maisons:
                alertes.append(
                    f"Maîtrise de {_affichage(planete)} annoncée sur M{maison} {etiquette}, "
                    f"absente du relevé : « {phrase.strip()} »"
                )

    # Le modèle confond parfois une maison gouvernée et la maison natale où
    # tombe le point RS, sous des formules floues comme « tient les clés ».
    # Cette construction n'est jamais suffisamment vérifiable ni précise pour
    # être remise telle quelle à la cliente.
    for phrase in re.split(r"(?<=[.!?])\s+", texte):
        normalisee = _normaliser(phrase)
        if not _planete_mentionnee(phrase):
            continue
        if "maison" not in normalisee or "natale" not in normalisee:
            continue
        if any(
            expression in normalisee
            for expression in (
                "tient les cles",
                "tient les clefs",
                "les cles de",
                "les clefs de",
                "porte la maison",
                "transporte la maison",
            )
        ):
            alertes.append(
                "Formulation ambiguë entre maîtrise et superposition RS–natal : "
                f"« {phrase.strip()} »"
            )

    # Contrôle prudent : seulement les phrases qui ne citent que deux points
    # nommés RS/natal autour d'un aspect.
    faits_aspects = _faits_aspects(donnees)
    for phrase in re.split(r"(?<=[.!?])\s+", texte):
        # Les transits sont vérifiés par leur propre relevé. Ici, on contrôle
        # seulement un aspect RS / natal lorsque son premier point est écrit,
        # afin de ne pas déduire un référent à partir de « il » ou « elle ».
        if "transit" in _normaliser(phrase):
            continue
        aspect = _aspect_mentionne(phrase)
        points = _points_qualifies(phrase)
        debut_explicit = re.search(
            r"^\s*(?:le |la |l')?(?:soleil|lune|mercure|venus|mars|jupiter|saturne|uranus|neptune|pluton|chiron|lune noire|part de fortune|noeud nord|noeud sud|ascendant|descendant|mc|fc)\s+(?:rs|natal(?:e)?)\b",
            _normaliser(phrase),
        )
        if not aspect or len(points) != 2 or not debut_explicit:
            continue
        (p1, nature1), (p2, nature2) = points
        if nature1 == nature2 == "rs":
            fait = ("rs", *sorted((p1, p2)), aspect)
        elif nature1 != nature2:
            p_rs = p1 if nature1 == "rs" else p2
            p_natal = p1 if nature1 == "natal" else p2
            fait = ("rs_natal", p_rs, p_natal, aspect)
        else:
            continue
        if fait not in faits_aspects:
            alertes.append(
                f"Aspect non retrouvé dans le relevé : « {phrase.strip()} »"
            )

    # Une comparaison « axe inversé par rapport au natal » est vérifiable pour
    # les Nœuds : l'axe RS doit réellement être l'opposé de l'axe natal.
    if "axe est inverse par rapport au natal" in normalise:
        nn_natal = placements_natals.get("Rahu", {}).get("maison")
        ns_natal = placements_natals.get("Ketu", {}).get("maison")
        nn_rs = placements_rs.get("Rahu", {}).get("maison")
        ns_rs = placements_rs.get("Ketu", {}).get("maison")
        oppose = lambda maison: ((int(maison) + 5) % 12) + 1
        if all((nn_natal, ns_natal, nn_rs, ns_rs)) and not (nn_rs == oppose(nn_natal) and ns_rs == oppose(ns_natal)):
            alertes.append(
                f"Axe nodal RS présenté comme inversé du natal, alors que natal M{nn_natal}/M{ns_natal} et RS M{nn_rs}/M{ns_rs} ne sont pas opposés."
            )

    # Une affirmation explicite « dans la même maison » peut être contrôlée
    # sans interpréter les pronoms ou la prose autour.
    noms_points = list(AFFICHAGE_VERS_INTERNE.items())
    for (affiche_1, interne_1), (affiche_2, interne_2) in combinations(noms_points, 2):
        if interne_1 not in placements_rs or interne_2 not in placements_rs:
            continue
        motif = rf"\b{re.escape(affiche_1)}\s+rs[^.\n]{{0,180}}?\b{re.escape(affiche_2)}\s+rs[^.\n]{{0,180}}?meme maison"
        if re.search(motif, normalise):
            maison_1 = placements_rs[interne_1].get("maison")
            maison_2 = placements_rs[interne_2].get("maison")
            if maison_1 != maison_2:
                alertes.append(
                    f"{_affichage(interne_1)} RS et {_affichage(interne_2)} RS annoncés dans la même maison, calculés respectivement en M{maison_1} et M{maison_2}."
                )

    # Si un « grand trigone d'eau » cite des planètes RS dans des signes non
    # aquatiques, l'étiquette élémentaire est nécessairement erronée.
    for phrase in re.split(r"(?<=[.!?])\s+", texte):
        if "grand trigone d'eau" not in _normaliser(phrase):
            continue
        # Dans une phrase de figure RS, les planètes non qualifiées sont
        # aussi des facteurs RS, sauf indication explicite « natal ».
        noms_cites = []
        phrase_normalisee = _normaliser(phrase)
        for affiche, interne in AFFICHAGE_VERS_INTERNE.items():
            if interne in placements_rs and re.search(rf"\b{re.escape(affiche)}\b", phrase_normalisee):
                if not re.search(rf"\b{re.escape(affiche)}\s+natale?\b", phrase_normalisee):
                    noms_cites.append(interne)
        elements_eau = {"cancer", "scorpion", "poissons"}
        hors_eau = [
            _affichage(nom) for nom in dict.fromkeys(noms_cites)
            if _normaliser(str(placements_rs.get(nom, {}).get("signe", ""))) not in elements_eau
        ]
        if hors_eau:
            alertes.append(
                "Grand trigone qualifié « d'eau » alors que le passage cite aussi : " + ", ".join(hors_eau) + "."
            )

    # Une figure annoncée doit au moins figurer parmi les figures calculées.
    figures = donnees.get("configurations_majeures_rs") or []
    types = {_normaliser(str(figure.get("type", "")).replace("_", " ")) for figure in figures}
    for terme, type_attendu in (("t-carre", "t carre"), ("grand trigone", "grand trigone"),
                                ("grand carre", "grand carre"), ("stellium", "stellium"),
                                ("diamant", "diamant"), ("cerf-volant", "diamant")):
        if terme in normalise and type_attendu not in types:
            alertes.append(f"Figure « {terme} » citée mais absente des figures calculées.")

    alertes.extend(_controle_angularites(texte, donnees))
    alertes.extend(_controle_contacts_rs_natal(texte, donnees))
    alertes.extend(_controle_profection(texte, donnees))
    alertes.extend(_controle_transits(texte, transits_directeurs or []))

    for doublon in _doublons(texte):
        alertes.append(f"Phrase répétée à l'identique : « {doublon} »")

    # Évite d'afficher dix fois une même alerte.
    alertes = list(dict.fromkeys(alertes))
    lignes = ["# Contrôle factuel automatique", ""]
    lignes.append("Ce contrôle n'interprète pas le rapport et ne le modifie pas.")
    lignes.append("Il signale seulement les affirmations techniques identifiables mécaniquement.")
    lignes.append("")
    if alertes:
        lignes.append(f"## Alertes détectées ({len(alertes)})")
        lignes.extend(f"- {alerte}" for alerte in alertes)
    else:
        lignes.append("## Aucun écart détecté par les règles automatiques")
        lignes.append("Cela ne remplace pas une relecture astrologique : seules les formulations identifiables sont contrôlées.")
    return "\n".join(lignes) + "\n"
