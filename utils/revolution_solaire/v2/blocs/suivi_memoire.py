"""Repérage conservateur de citations ; aucune validation astrologique ou IA.

Un extrait ambigu reste non repéré. Une concordance de mots et de cadres ne
certifie ni leur relation grammaticale ni l'interprétation : Cécile relit.
"""

import re
import unicodedata


ALIASES = {
    "Rahu": ("rahu", "noeud nord", "noeuds"), "Ketu": ("ketu", "noeud sud", "noeuds"),
    "MC": ("mc", "milieu du ciel"), "FC": ("fc", "fond du ciel"),
}
ASPECTS = {
    "conjonction": r"\b(?:conjonctions?|conjoint(?:e|s|es)?)\b",
    "opposition": r"\b(?:oppositions?|oppose(?:e|s|es)?)\b",
    "carre": r"(?<!semi-)(?<!semi )\bcarre(?:e|s|es)?\b",
    "trigone": r"\btrigones?\b", "sextile": r"(?<!semi-)(?<!semi )\bsextiles?\b",
    "quinconce": r"\bquinconces?\b", "semi-sextile": r"\bsemi[- ]sextiles?\b",
    "semi-carre": r"\bsemi[- ]carres?\b", "sesquicarre": r"\bsesquicarres?\b",
}
MARQUEURS = {
    "rs": r"(?:rs|revolution solaire)",
    "natal": r"(?:natal(?:e|s|es)?|theme natal)",
}
LIAISON = r"\W+(?:(?:de|du|en|dans|la|le|ta|ton|sa|son)\W+){0,3}"


def normaliser_texte(texte):
    texte = (texte.replace("œ", "oe").replace("Œ", "OE")
             .replace("’", "'").replace("‘", "'"))
    # Conserver les séparateurs avant le passage en ASCII : RS–Vénus ne
    # doit pas devenir RSVenus et perdre son marqueur de cadre.
    texte = re.sub(r"[‐‑‒–—−]", "-", texte)
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", texte).strip()


def motif_point(point):
    noms = ALIASES.get(point, (normaliser_texte(point),))
    return r"\b(?:" + "|".join(re.escape(nom) for nom in noms) + r")\b"


def reperer_configurations_developpees(faits, textes):
    """Repérage éditorial des figures explicitement nommées dans les archives.

    Le type et tous les participants calculés doivent apparaître dans un même
    paragraphe. L'extrait reste consultable ; aucune validation astrologique,
    aucune nouvelle figure calculée et aucune réécriture du texte source.
    """
    motifs = {
        "t_carre": r"\b(?:t[- ]carre|carre en t)\b",
        "triangle_mineur": r"\btriangle mineur\b",
        "grand_trigone": r"\b(?:grand trigone|grand triangle)\b",
        "grande_croix": r"\b(?:grande croix|grand carre)\b",
        "cerf_volant": r"\bcerf[- ]volant\b",
        "diamant": r"\bdiamant\b",
        "yod": r"\byod\b",
    }
    reperes = {}
    for source in textes:
        for paragraphe in re.split(r"\n\s*\n", source["texte"]):
            zone = normaliser_texte(paragraphe)
            for cle, fait in faits.items():
                if cle in reperes or fait["source"] != "rs" or fait["type"] != "configurations":
                    continue
                v = fait["valeur"]
                motif = motifs.get(v["type"])
                noms = v.get("planetes", [])
                if motif and len(noms) >= 3 and re.search(motif, zone) and all(
                        re.search(motif_point(nom), zone) for nom in noms):
                    reperes[cle] = {"bloc": source["bloc"], "source": source["source"],
                                    "extrait": paragraphe.strip(),
                                    "nature": "Repérage lexical éditorial, pas validation astrologique."}
    return reperes


def fenetres(texte):
    """Chaque phrase, avec la précédente du même paragraphe."""
    sortie = []
    for paragraphe in re.split(r"\n\s*\n", texte or ""):
        phrases = [p for p in re.split(
            r"(?<=[.!?])\s+", normaliser_texte(paragraphe)) if p]
        for i, phrase in enumerate(phrases):
            sortie.append((phrase, phrases[i - 1] if i else ""))
    return sortie


def marque(zone, point, cadre):
    return bool(re.search(
        motif_point(point) + LIAISON + MARQUEURS[cadre] + r"\b", zone))


def verifier_cadre(zone, points):
    implicites = []
    for point, cadre in points:
        autre = "natal" if cadre == "rs" else "rs"
        if marque(zone, point, cadre):
            continue
        if marque(zone, point, autre):
            return False, ("Contradiction de cadre : " + point + " est rattaché au cadre " + autre.upper()
                           + " au lieu de " + cadre.upper() + ".")
        implicites.append(point)
    cadres = {c for _, c in points}
    if len(cadres) == 1 and implicites:
        cadre = next(iter(cadres))
        autre = "natal" if cadre == "rs" else "rs"
        if (re.search(r"\b" + MARQUEURS[autre] + r"\b", zone)
                and not re.search(r"\b" + MARQUEURS[cadre] + r"\b", zone)):
            return False, ("Contradiction de cadre : cadre " + autre.upper() + " mentionné, cadre "
                           + cadre.upper() + " absent.")
    if implicites:
        return True, "cadre non marqué sur " + ", ".join(implicites)
    return True, "cadres explicites"


def decouper(phrase):
    """Tête héritée et un segment par aspect, jusqu'au suivant."""
    reperes = sorted((m.start(), nom) for nom, motif in ASPECTS.items()
                     for m in re.finditer(motif, phrase))
    if not reperes:
        return phrase, []
    segments = []
    for i, (debut, nom) in enumerate(reperes):
        fin = reperes[i + 1][0] if i + 1 < len(reperes) else len(phrase)
        segments.append((nom, phrase[debut:fin]))
    return phrase[:reperes[0][0]], segments


def reperer_citation(texte, fait, extrait=None):
    """Repérage par segment ; les sujets implicites restent à relire.

    Un retour True avec une raison « À relire » indique un repérage partiel,
    sans validation. L'extrait n'est pas une ancre obligatoire. Les mots ne
    certifient ni le lien grammatical ni l'interprétation astrologique.
    """
    valeur = fait["valeur"]
    if fait["type"] == "contact":
        points = ((valeur["point_rs"], "rs"), (valeur["point_natal"], "natal"))
    elif fait["type"] == "aspects" and fait["source"] in {"rs", "natal"}:
        points = ((valeur["planete1"], fait["source"]), (valeur["planete2"], fait["source"]))
    else:
        return False, "La liste faits_cites est réservée aux aspects et contacts explicites."
    attendu = normaliser_texte(valeur["aspect"])
    # Une citation littérale explicite prime sur un autre passage partiel.
    # Un extrait reformulé ne suffit jamais à prouver une contradiction.
    citation = normaliser_texte(extrait) if isinstance(extrait, str) else ""
    if citation and citation in normaliser_texte(texte) and all(
            re.search(motif_point(p), citation) for p, _ in points):
        cites = {n for n, motif in ASPECTS.items() if re.search(motif, citation)}
        if len(cites) == 1:
            cadres_ok, detail = verifier_cadre(citation, points)
            if not cadres_ok:
                return False, detail
            if attendu not in cites:
                return False, "Contradiction d'aspect : " + next(iter(cites)) + " cité, " + attendu + " attendu."
    contradictions, partiel = [], None
    for phrase, precedente in fenetres(texte):
        tete, segments = decouper(phrase)
        for nom, segment in segments:
            if nom != attendu:
                continue
            local = tete + " " + segment
            # Un aspect sans aucun point du fait dans le segment ou sa tête
            # ne devient pas un candidat par le seul voisinage d'une phrase.
            if not any(re.search(motif_point(p), local) for p, _ in points):
                continue
            # Une paire nommée dans ce segment n'hérite pas des cadres d'une
            # phrase précédente traitant, par exemple, de Mars natal.
            zone = local if all(re.search(motif_point(p), local) for p, _ in points) else precedente + " " + local
            nommes = [p for p, _ in points if re.search(motif_point(p), zone)]
            ok, detail = verifier_cadre(zone, tuple(
                (p, cadre) for p, cadre in points if p in nommes))
            if not ok:
                contradictions.append(detail)
                continue
            if len(nommes) < 2:
                partiel = partiel or ("À relire : aspect " + attendu
                    + " trouvé, seul " + nommes[0] + " est nommé (autre point implicite).")
                continue
            # Le pluriel générique désigne l'axe, pas un nœud identifié.
            generiques = [p for p, _ in points if p in {"Rahu", "Ketu"}
                          and not re.search(r"\b(?:" + "|".join(
                              re.escape(n) for n in ALIASES[p] if n != "noeuds") + r")\b", zone)]
            if generiques:
                partiel = partiel or "À relire : axe des Nœuds nommé, nœud individuel implicite."
                continue
            if points[0][0] == points[1][0] and not all(
                    marque(zone, p, cadre) for p, cadre in points):
                partiel = partiel or "À relire : même point RS/natal, deux cadres non identifiés."
                continue
            return True, "Repérage lexical seulement ; " + detail
    if contradictions:
        return False, contradictions[0]
    if partiel:
        return True, partiel
    return False, "À relire : aucune attribution suffisamment explicite de l'aspect " + attendu + "."
