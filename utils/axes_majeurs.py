# utils/axes_majeurs.py
import re

PERSONNELLES = {"Soleil", "Lune", "Mercure", "Vénus", "Mars"}
LOURDES = {"Mars", "Saturne", "Uranus", "Neptune", "Pluton"}  # Mars à cheval, mais utile pour tensions
NOEUDS = {"Rahu", "Ketu"}

# ────────────────────────────────────────────────
# FONCTION : _orbe_ok
# Objectif : Vérifie si l'orbe d'un aspect est inférieur ou égal à un seuil donné.
# - Cherche dans la chaîne de texte `ligne` une mention "orbe X.X"
# - Convertit cette valeur en float (gestion des virgules)
# - Retourne True si aucun orbe trouvé (on garde par défaut) ou si l'orbe ≤ seuil
# - Retourne False sinon
# Utilité : Sert à filtrer les aspects en fonction de leur précision, notamment pour
#           les tensions aux luminaires avec les Nœuds.
# ────────────────────────────────────────────────

def _orbe_ok(ligne: str, seuil=3.0) -> bool:
    m = re.search(r"orbe\s+([\d.,]+)", ligne, flags=re.IGNORECASE)
    if not m:
        return True  # si pas d’info, on garde par défaut
    val = float(m.group(1).replace(",", "."))
    return val <= seuil


# ────────────────────────────────────────────────
# FONCTION : organiser_points_forts
# Objectif : Classer les "points forts" astrologiques dans des catégories clés.
# Processus :
#   1) Recherche de mots-clés ou de motifs précis dans chaque point fort.
#   2) Range les éléments dans les catégories suivantes :
#        - amas : regroupements planétaires
#        - angulaires_perso : planètes personnelles ou maître d’Ascendant en maison I ou X
#        - tensions_luminaires : aspects tendus Soleil/Lune avec lourdes ou Nœuds (orbe ≤ 3°)
#        - dignites_ou_chutes : dignités et chutes pour Soleil → Mars / Maître d’Ascendant
#        - dominances : dominances planétaires marquées
#        - angles_signes : placements sur les axes cardinaux (Asc, Desc, MC, FC)
#        - autres : tout ce qui ne correspond pas aux critères ci-dessus
# Utilité : Facilite l’organisation et la hiérarchisation des points forts
#           avant intégration dans l’analyse.
# ────────────────────────────────────────────────

def organiser_points_forts(points_forts: list[str]) -> dict:
    """Range les éléments dans 5 catégories Axes Majeurs."""
    axes = {
        "amas": [],
        "angulaires_perso": [],
        "tensions_luminaires": [],
        "dignites_ou_chutes": [],
        "dominances": [],
        "autres": []
    }

    for raw in points_forts:
        ligne = raw.strip()
        ligne_norm = ligne.lower().replace("’", "'").replace("maître", "maitre")

        # 1) AMAS
        if re.search(r"\bAmas\b", ligne, flags=re.IGNORECASE):
            axes["amas"].append(ligne)
            continue

        # 2) PLANÈTES ANGULAIRES (toutes planètes + maître d’Asc angulaire)
        if (
            ("maison angulaire" in ligne_norm and re.search(r"\((?:1|10)\)", ligne))
            or ("maitre d'ascendant" in ligne_norm and "angulaire" in ligne_norm)
        ):
            axes.setdefault("angulaires_perso", []).append(ligne)
            continue

        # 3) TENSIONS AUX LUMINAIRES (Soleil/Lune) avec lourdes ou Nœuds (Rahu/Ketu ≤ 3°)
        if any(lum in ligne for lum in ("Soleil", "Lune")) and \
           re.search(r"(Conjonction|Opposition|Carr[ée])", ligne, flags=re.IGNORECASE):

            # a) avec planètes lourdes
            if any(p in ligne for p in LOURDES):
                axes["tensions_luminaires"].append(ligne)
                continue

            # b) avec Nœuds — on ne garde que si orbe ≤ 3°
            if any(n in ligne for n in NOEUDS):
                if _orbe_ok(ligne, seuil=3.0):
                    axes["tensions_luminaires"].append(ligne)
                    continue
                else:
                    axes["autres"].append(ligne)
                    continue

        # 4) DIGNITÉS / CHUTES : Soleil, Lune, Maître d’Ascendant
        # 4) DIGNITÉS / CHUTES : élargi aux personnelles + Maître d’Ascendant
        if re.search(r"(exaltation|domicile|chute|exil)", ligne, flags=re.IGNORECASE) and \
        any(p in ligne for p in ("Soleil","Lune","Mercure","Vénus","Mars","Maître d’Ascendant","Maitre d'Ascendant")):
            axes["dignites_ou_chutes"].append(ligne)
            continue

        # 5) DOMINANCES
        if ligne.startswith("Dominance"):
            axes["dominances"].append(ligne)
            continue

        # Axes cardinaux (signes)
        if re.search(r"^(Ascendant|Descendant|Milieu du Ciel|Fond du Ciel) en ", ligne):
            axes.setdefault("angles_signes", []).append(ligne)
            continue

        # Le reste
        axes["autres"].append(ligne)

    return axes

# ────────────────────────────────────────────────
# FONCTION : formater_axes_majeurs
# Objectif : Transformer le dictionnaire des axes majeurs en texte structuré.
# Processus :
#   1) Parcourt chaque catégorie d’axes majeurs (amas, angulaires, tensions, etc.).
#   2) Crée un bloc de texte avec titre + liste à puces pour chaque catégorie non vide.
#   3) Suit un ordre de présentation prédéfini :
#        - Amas
#        - Planètes angulaires (I/X)
#        - Tensions majeures aux luminaires
#        - Dignités / chutes (Soleil → Mars / Maître d’Ascendant)
#        - Dominances fortes
#        - Axes cardinaux (signes)
#   4) Retourne le texte prêt à injecter dans l’analyse.
# Utilité : Facilite l’intégration lisible et hiérarchisée des axes majeurs
#           dans le corps du Point Astral.
# ────────────────────────────────────────────────

def formater_axes_majeurs(axes: dict) -> str:
    """Produit un bloc texte prêt à injecter (ordre décidé)."""
    sections = []

    def bloc(titre, items):
        if not items: 
            return ""
        bullet = "\n".join(f"- {it}" for it in items)
        return f"### {titre}\n{bullet}"

    # Ordre conseillé
    sections.append(bloc("Amas", axes.get("amas", [])))
    sections.append(bloc("Planètes angulaires (I/X)", axes.get("angulaires_perso", [])))
    sections.append(bloc("Tensions majeures aux luminaires", axes.get("tensions_luminaires", [])))
    sections.append(bloc("Dignités / chutes (Soleil → Mars / Maître d’Asc.)", axes.get("dignites_ou_chutes", [])))
    sections.append(bloc("Dominances fortes", axes.get("dominances", [])))
    sections.append(bloc("Axes cardinaux (signes)", axes.get("angles_signes", [])))

    # Filtre sections vides et joint
    return "\n\n".join(s for s in sections if s)