# utils/forces_defis.py
from typing import Dict, Any, List, Tuple

FORCES_MAX = 8
DEFIS_MAX = 8

def _score_angularite(maisons: Dict[str, Any]) -> List[str]:
    """Repère des placements en maisons 1/4/7/10 -> tendance 'Force' (visibilité, ancrage, impact)."""
    forces = []
    angles = {"1": "Maison I (Identité/élan)", "4": "Maison IV (Racines)", "7": "Maison VII (Relationnel)", "10": "Maison X (Carrière/Statut)"}
    for planete, info in maisons.items():
        m = str(info.get("maison") or info.get("house") or "")
        if m in angles:
            forces.append(f"{planete} en {angles[m]} : présence et effet de levier naturels sur ce domaine.")
    return forces

def _score_aspects_luminaires(aspects: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """
    Priorise les aspects majeurs aux luminaires avec planètes lourdes.
    -> Conjonction/trigone/sextile = plutôt Force (selon planète)
    -> Carré/opposition = plutôt Défi (intégration à travailler)
    """
    lourdes = {"Saturne", "Uranus", "Neptune", "Pluton"}
    forces, defis = [], []
    for a in aspects:
        p1, p2 = a.get("p1"), a.get("p2")
        type_aspect = (a.get("type") or a.get("aspect") or "").lower()  # "conjonction", "carré", "opposition", "trigone", "sextile"
        orbe = a.get("orbe") or a.get("orb")
        couple = {p1, p2}
        if not ({"Soleil", "Lune"} & couple):
            continue
        autre = (couple - {"Soleil", "Lune"}).pop() if len(couple - {"Soleil", "Lune"}) == 1 else None
        if autre in lourdes:
            label = f"{p1}-{p2} ({type_aspect}, orbe {orbe}°)"
            if type_aspect in {"trigone", "sextile", "conjonction"} and autre != "Saturne":
                forces.append(f"Luminaires ↔ {autre} : {label} → soutien profond, intuition/densité bien canalisée.")
            elif type_aspect in {"carré", "opposition", "conjonction"}:
                defis.append(f"Luminaires ↔ {autre} : {label} → tension formatrice, maturation nécessaire.")
    return forces, defis

def _score_amas(amas: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Un amas = Force de concentration + risque de mono-thème (Défi)."""
    forces, defis = [], []
    for cluster in amas:
        zone = cluster.get("zone") or cluster.get("signe") or cluster.get("maison")
        nb = cluster.get("nb") or len(cluster.get("planetes", []))
        if nb and nb >= 3:
            forces.append(f"Amas ({nb}) en {zone} : focus, puissance de développement.")
            defis.append(f"Amas ({nb}) en {zone} : angle mort potentiel (besoin d’équilibrer).")
    return forces, defis

def _score_interceptions(interceptions) -> Tuple[List[str], List[str]]:
    """Axes interceptés = thème récurrent de 'déverrouillage' (Défi) puis Force quand activé."""
    forces, defis = [], []
    if not interceptions:
        return forces, defis

    # Cas 1 : liste brute
    if isinstance(interceptions, list):
        signes = interceptions
        if signes:
            defis.append(f"Axe intercepté ({', '.join(signes)}) : talents en dormance → demande un protocole d'activation.")
            forces.append(f"Axe intercepté : une fois déverrouillé, montée en gamme rapide sur ce spectre.")
        return forces, defis

    # Cas 2 : dict (normal)
    for axe, data in interceptions.items():
        # 🔧 FIX : Vérifier que data est bien un dict avant d'appeler .get()
        if not isinstance(data, dict):
            continue
            
        signes = (data.get("signes") or data.get("signs") or [])
        if signes:
            defis.append(f"Axe intercepté {axe} ({', '.join(signes)}) : talents en dormance → demande un protocole d'activation.")
            forces.append(f"Axe intercepté {axe} : une fois déverrouillé, montée en gamme rapide sur ce spectre.")

    return forces, defis

def _score_points_speciaux(planetes: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Chiron, Lune Noire, Nœuds : Défis de base (sensibilités) mais Forces de lucidité/maîtrise.
    """
    forces, defis = [], []
    if "Chiron" in planetes:
        pos = planetes["Chiron"]
        forces.append(f"Chiron en {pos.get('signe')} maison {pos.get('maison')} : capacité de mentorat par l’expérience.")
        defis.append(f"Chiron : vieille cicatrice à apprivoiser (auto-compassion, pédagogie).")
    if "Lune Noire" in planetes:
        pos = planetes["Lune Noire"]
        defis.append(f"Lune Noire conjointe à un angle/astre personnel ? → zones taboues à clarifier.")
    if "Nœud Nord" in planetes or "Noeud Nord" in planetes:
        nn = planetes.get("Nœud Nord") or planetes.get("Noeud Nord")
        forces.append(f"Nœud Nord en {nn.get('signe')} maison {nn.get('maison')} : boussole évolutive.")
    return forces, defis

def _dedupe_cap(items: List[str], limit: int) -> List[str]:
    seen, out = set(), []
    for s in items:
        k = s.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
        if len(out) >= limit:
            break
    return out

def generer_forces_defis(theme: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entrée attendue (extraits) :
    {
      'planetes': { 'Soleil': {...}, 'Lune': {...}, 'Chiron': {...}, 'Lune Noire': {...}, 'Nœud Nord': {...}, ... },
      'maisons_par_planete': { 'Soleil': {'maison': 10}, ... },
      'aspects_significatifs': [ {'p1':'Soleil','p2':'Pluton','type':'carré','orbe':3.2}, ... ],
      'amas': [ {'zone':'Vierge', 'nb':3, 'planetes':['Soleil','Mercure','Jupiter']} ],
      'interceptions': { 'V/ XI': {'signes':['Sagittaire','Gémeaux']} }
    }
    Sortie :
    {
      'forces': [str, ...],
      'defis': [str, ...],
      'synthese_courte': str
    }
    """
    planetes = theme.get('planetes', {})
    maisons_par_planete = theme.get('maisons_par_planete', {})
    aspects = theme.get('aspects_significatifs', []) or theme.get('aspects', [])
    amas = theme.get('amas', [])
    interceptions = theme.get('interceptions', {})

    # 🔒 Normalisation pour éviter l'AttributeError
    # - si c'est une liste → on l'emballe dans {"signes": [...]}
    # - si c'est autre chose → dict vide
    if isinstance(interceptions, list):
        interceptions = {"signes": interceptions}
    elif not isinstance(interceptions, dict):
        interceptions = {}

    forces, defis = [], []

    # 1) Angles/maisons fortes
    forces += _score_angularite(maisons_par_planete)

    # 2) Luminaires ↔ lourdes
    f2, d2 = _score_aspects_luminaires(aspects)
    forces += f2; defis += d2

    # 3) Amas
    f3, d3 = _score_amas(amas)
    forces += f3; defis += d3

    # 4) Interceptions
    f4, d4 = _score_interceptions(interceptions)
    forces += f4; defis += d4

    # 5) Points spéciaux
    f5, d5 = _score_points_speciaux(planetes)
    forces += f5; defis += d5

    # Nettoyage + cap
    forces = _dedupe_cap(forces, FORCES_MAX)
    defis = _dedupe_cap(defis, DEFIS_MAX)

    # Mini-synthèse (2 lignes max)
    s_forces = ", ".join([f.split(":")[0] for f in forces[:3]]) or "Atouts en construction"
    s_defis = ", ".join([d.split(":")[0] for d in defis[:3]]) or "Défis en cours d’identification"
    synthese = f"Forces clés : {s_forces}. Défis actifs : {s_defis}."

    return {
        "forces": forces,
        "defis": defis,
        "synthese_courte": synthese
    }

def extraire_forces_defis_par_maisons(theme: dict) -> dict:
    """Ajoute des forces/défis spécifiques selon la présence planétaire dans certaines maisons."""
    forces, defis = [], []

    maisons = theme.get("maisons_planetes", {})  # <- clé à adapter selon ton `calcul_theme`
    if not maisons:
        return {"forces": [], "defis": []}

    for planete, maison in maisons.items():
        # Maison VIII : puissance transformatrice mais confrontations
        if maison == 8:
            forces.append(f"{planete} en Maison VIII : grande capacité de régénération, intuition profonde, potentiel de transformation.")
            defis.append(f"{planete} en Maison VIII : confrontations avec les pertes, crises ou attachements qui demandent à être transcendés.")

        # Maison XII : vie intérieure, mais isolements possibles
        elif maison == 12:
            forces.append(f"{planete} en Maison XII : ouverture au spirituel, grande empathie, accès à l’inconscient.")
            defis.append(f"{planete} en Maison XII : tendance à l’isolement, aux sacrifices ou aux illusions si mal intégrée.")

        # Maison VI : service, santé
        elif maison == 6:
            forces.append(f"{planete} en Maison VI : sens du service, rigueur dans le quotidien, orientation vers l’amélioration.")
            defis.append(f"{planete} en Maison VI : vulnérabilité aux excès de travail, perfectionnisme, tensions liées à la santé.")

    return {"forces": forces, "defis": defis}