import re
from utils.llm_client import ask_llm
from textwrap import dedent
from typing import Dict, List, Any
from utils.selection_donnees import exclure_aspects_aux_noeuds

# --- Normalisations (aspects & corps) ---
CANON_ASPECT = {
    "carré": "Carré", "carre": "Carré", "square": "Carré",
    "opposition": "Opposition", "opp": "Opposition",
    "conjonction": "Conjonction", "conj": "Conjonction",
    "trigone": "Trigone", "trine": "Trigone",
    "sextile": "Sextile",
}

POINT_ALIASES = {
    # angles
    "mc": "MC",
    "m.c.": "MC",
    "milieu du ciel": "MC",
    "milieu-du-ciel": "MC",
    "midheaven": "MC",
    "ic": "IC",
    "f.c.": "IC",
    "fc": "IC",               # <— ⚠️ alias FC → IC
    "fond du ciel": "IC",
    "fond-du-ciel": "IC",
    # noeuds
    "noeud nord": "Rahu",
    "nœud nord": "Rahu",
    "noeud sud": "Ketu",
    "nœud sud": "Ketu",
    # lilith
    "lilith": "Lune Noire",
}

def _normalize_aspect(name: str) -> str:
    if not name: return ""
    key = name.strip().lower()
    return CANON_ASPECT.get(key, name.strip().capitalize())

def _normalize_body(name: str) -> str:
    if not name: return ""
    key = name.strip().lower()
    return POINT_ALIASES.get(key, name.strip())

ASPECTS_DURS = {"Carré", "Opposition", "Conjonction"}
ASPECTS_MOUS = {"Trigone", "Sextile"}
ORBE_MAX_LUNE = 5.0
ORBE_MAX_IC   = 3.0  # si tu as l’IC comme point calculé

RULERS = {
    "Bélier":"Mars","Taureau":"Vénus","Gémeaux":"Mercure","Cancer":"Lune",
    "Lion":"Soleil","Vierge":"Mercure","Balance":"Vénus","Scorpion":"Pluton",
    "Sagittaire":"Jupiter","Capricorne":"Saturne","Verseau":"Uranus","Poissons":"Neptune",
}




def _orbe(a): 
    try: return float(str(a.get("orbe", 99)).replace(",", "."))
    except: return 99.0

def _is_to(target, a):
    t = _normalize_body(target)
    p1 = _normalize_body(a.get("planete1"))
    p2 = _normalize_body(a.get("planete2"))
    return p1 == t or p2 == t

def _fmt_aspect(a):
    asp = _normalize_aspect(a.get("aspect"))
    p1  = _normalize_body(a.get("planete1"))
    p2  = _normalize_body(a.get("planete2"))
    return f"{p1} {asp} {p2} (orbe {a.get('orbe')}°)"

def _pick(aspects, keep_fn, max_orbe, whitelist=None):
    out = []
    for a in aspects or []:
        # --- Fallback pour structures d’aspects alternatives ---
        if a.get("planete1") is None and a.get("p1") is not None:
            a["planete1"] = a.get("p1")
        if a.get("planete2") is None and a.get("p2") is not None:
            a["planete2"] = a.get("p2")

        # --- Normalisations canoniques (aspect & corps/points) ---
        a["aspect"]   = _normalize_aspect(a.get("aspect"))
        a["planete1"] = _normalize_body(a.get("planete1"))
        a["planete2"] = _normalize_body(a.get("planete2"))

        if keep_fn(a) and _orbe(a) <= max_orbe and ((whitelist is None) or a["aspect"] in whitelist):
            out.append(a)

    out.sort(key=_orbe)
    return out

def _phase_lunaire_deg(sol_deg, lune_deg):
    # si tu as les degrés écliptiques absolus ; sinon mets None
    if sol_deg is None or lune_deg is None: return None
    d = (lune_deg - sol_deg) % 360
    return d  # 0=Nouvelle, ~90=Premier quartier, 180=Pleine, ~270=Dernier


def _delta_cercle(a: float, b: float) -> float:
    """Distance angulaire minimale sur le cercle [0..180]."""
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d

def _points_sur_cuspide(theme: Dict, angle: str, max_orbe: float = 1.5,
                        candidats: tuple = ("Chiron", "Lune Noire")) -> list[tuple[str, float]]:
    """
    Retourne [(nom, écart_deg)] pour les 'candidats' situés à <= max_orbe° de la cuspide 'angle' (ex: 'MC', 'IC').
    Requiert que calcul_theme fournisse theme['angles_deg'] et theme['planetes_deg'].
    """
    angles = (theme.get("angles_deg") or {})
    plan_deg = (theme.get("planetes_deg") or {})
    if angle not in angles:
        return []

    a_deg = float(angles[angle])
    out = []
    for nom in candidats:
        if nom in plan_deg:
            ecart = _delta_cercle(float(plan_deg[nom]), a_deg)
            if ecart <= max_orbe:
                out.append((nom, ecart))
    # tri par écart croissant
    out.sort(key=lambda t: t[1])
    return out

def build_resume_bloc2(theme: Dict, contexte: Dict) -> Dict[str, str]:
    planetes = theme.get("planetes", {})
    aspects  = theme.get("aspects", [])

    L = planetes.get("Lune", {}) or {}
    lune_sign  = L.get("signe", "N/A")
    lune_house = L.get("maison", "N/A")

    # Aspects forts à la Lune
    lune_aspects = _pick(aspects, lambda a: _is_to("Lune", a), ORBE_MAX_LUNE, ASPECTS_DURS | ASPECTS_MOUS)

    # Maître de la Lune (dispositor)
    lune_ruler = RULERS.get(lune_sign, None)
    ruler_obj  = planetes.get(lune_ruler, {}) if lune_ruler else {}
    ruler_sign  = ruler_obj.get("signe", "N/A")
    ruler_house = ruler_obj.get("maison", "N/A")
    ruler_aspects = _pick(aspects, lambda a: _is_to(lune_ruler, a), ORBE_MAX_LUNE, ASPECTS_DURS | ASPECTS_MOUS) if lune_ruler else []

    # --- Maison IV / IC (gérer alias FC) ---
    M4_planetes = [p for p, d in planetes.items() if d.get("maison")==4 and _normalize_body(p) not in ("Rahu","Ketu","Ascendant","MC","IC")]
    # On considère IC présent si "IC" ou "FC" est dans planetes
    ic_obj = planetes.get("IC") or planetes.get("FC") or {}
    # aspects vers IC **et** FC (au cas où la liste d'aspects ne soit pas uniformisée)
    ic_aspects = []
    ic_aspects += _pick(aspects, lambda a: _is_to("IC", a), ORBE_MAX_IC, ASPECTS_DURS | ASPECTS_MOUS)
    ic_aspects += _pick(aspects, lambda a: _is_to("FC", a), ORBE_MAX_IC, ASPECTS_DURS | ASPECTS_MOUS)
    # dédup simple
    seen = set(); _ic_aspects = []
    for a in ic_aspects:
        k = (a["planete1"], a["aspect"], a["planete2"], f"{_orbe(a):.2f}")
        if k not in seen:
            seen.add(k); _ic_aspects.append(a)
    ic_aspects = sorted(_ic_aspects, key=_orbe)

    # Nœuds, Lilith, Chiron vers Lune
    special_targets = {"Rahu","Ketu","Lune Noire","Chiron"}
    lune_special = [a for a in lune_aspects if set((a["planete1"],a["planete2"])) & special_targets]
    lune_special.sort(key=_orbe)

    # Phase lunaire (si degrés absolus dispo)
    sol_abs = planetes.get("Soleil", {}).get("degre_abs")
    lun_abs = planetes.get("Lune", {}).get("degre_abs")
    phase_deg = _phase_lunaire_deg(sol_abs, lun_abs)

     # === PÔLE PÈRE / AUTORITÉ : Soleil, Saturne, Maison X / MC ===
    S = planetes.get("Soleil", {}) or {}
    soleil_sign  = S.get("signe", "N/A")
    soleil_house = S.get("maison", "N/A")
    soleil_aspects = _pick(aspects, lambda a: _is_to("Soleil", a), ORBE_MAX_LUNE, ASPECTS_DURS | ASPECTS_MOUS)

    Sa = planetes.get("Saturne", {}) or {}
    saturne_sign  = Sa.get("signe", "N/A")
    saturne_house = Sa.get("maison", "N/A")
    saturne_aspects = _pick(aspects, lambda a: _is_to("Saturne", a), ORBE_MAX_LUNE, ASPECTS_DURS | ASPECTS_MOUS)

    # --- Maison X / MC ---
    M10_planetes = [p for p, d in planetes.items() if d.get("maison")==10 and _normalize_body(p) not in ("Rahu","Ketu","Ascendant","MC","IC")]
    mc_aspects = _pick(aspects, lambda a: _is_to("MC", a), ORBE_MAX_IC, ASPECTS_DURS | ASPECTS_MOUS)
    points_mc = _points_sur_cuspide(theme, "MC", max_orbe=1.5, candidats=("Chiron", "Lune Noire"))
    points_mc_str = ", ".join(f"{nom} (écart {ecart:.2f}°)" for nom, ecart in points_mc) or "Aucun"
    points_ic = _points_sur_cuspide(theme, "FC", max_orbe=1.5, candidats=("Jupiter", "Chiron", "Lune Noire"))
    points_ic_str = ", ".join(f"{nom} (écart {ecart:.2f}°)" for nom, ecart in points_ic) or "Aucun"

    # Aspects directs Lune ↔ Soleil / Saturne
    lune_soleil = [a for a in lune_aspects if {"Lune","Soleil"} == {a.get("planete1"), a.get("planete2")}]
    lune_saturne = [a for a in lune_aspects if {"Lune","Saturne"} == {a.get("planete1"), a.get("planete2")}]

    # Formats
    #lune_aspects_str  = "\n".join(_fmt_aspect(a) for a in lune_aspects) or "—"
    # lune_aspects_filtrés = exclure_aspects_aux_noeuds(lune_aspects)
    # lune_aspects_str     = "\n".join(_fmt_aspect(a) for a in lune_aspects_filtrés) or "—"
    # ruler_aspects_str = "\n".join(_fmt_aspect(a) for a in ruler_aspects) or "—"
    # ic_aspects_str    = "\n".join(_fmt_aspect(a) for a in ic_aspects) or "—"
    # m4_str            = ", ".join(M4_planetes) if M4_planetes else "Aucune"
    # lun_special_str   = "\n".join(_fmt_aspect(a) for a in lune_special) or "—"

# Formats - AVEC FILTRAGE DES NŒUDS pour toutes les planètes importantes
    lune_aspects_filtrés = exclure_aspects_aux_noeuds(lune_aspects)
    lune_aspects_str     = "\n".join(_fmt_aspect(a) for a in lune_aspects_filtrés) or "—"
    
    # ✅ CORRECTION : Filtrer aussi les aspects aux nœuds pour le maître de la Lune
    ruler_aspects_filtrés = exclure_aspects_aux_noeuds(ruler_aspects)
    ruler_aspects_str = "\n".join(_fmt_aspect(a) for a in ruler_aspects_filtrés) or "—"
    
    ic_aspects_str    = "\n".join(_fmt_aspect(a) for a in ic_aspects) or "—"
    m4_str            = ", ".join(M4_planetes) if M4_planetes else "Aucune"
    lun_special_str   = "\n".join(_fmt_aspect(a) for a in lune_special) or "—"


    resume = f"""\
Lune : {lune_sign} — Maison {lune_house}
Aspects forts à la Lune (≤{ORBE_MAX_LUNE}°) :
{lune_aspects_str}

Maître de la Lune : {lune_ruler or 'N/A'} en {ruler_sign} — Maison {ruler_house}
Aspects forts du Maître de la Lune :
{ruler_aspects_str}

Maison IV : planètes en IV → {m4_str}
Aspects forts à l’IC (si présent) :
{ic_aspects_str}

Conjonctions exactes IC :
{(contexte.get("conjonctions_ic") or "—")}

Conjonctions exactes MC :
{(contexte.get("conjonctions_mc") or "—")}

Aspects Lune ↔︎ Nœuds/Lilith/Chiron :
{lun_special_str}

Soleil (père/autorité) : {soleil_sign} — Maison {soleil_house}
Aspects forts au Soleil :
{ "\n".join(_fmt_aspect(a) for a in exclure_aspects_aux_noeuds(soleil_aspects)) or "—" }

Saturne (structure/autorité intériorisée) : {saturne_sign} — Maison {saturne_house}
Aspects forts à Saturne :
{ "\n".join(_fmt_aspect(a) for a in exclure_aspects_aux_noeuds(saturne_aspects)) or "—" }

Maison X : planètes en X → {", ".join(M10_planetes) if M10_planetes else "Aucune"}
Aspects forts au MC (si présent) :
{ "\n".join(_fmt_aspect(a) for a in mc_aspects) or "—" }

Points sur la cuspide du MC (≤1.5°) :
{points_mc_str}

""".strip()

    # Points prioritaires pour guider le texte (top 4)
    def weight(a):
        s = {a["planete1"], a["planete2"]}
        score = 0
        if "Saturne" in s or "Pluton" in s: score -= 3
        if "Uranus" in s or "Mars" in s:   score -= 2
        if "Jupiter" in s:                 score += 1
        return (score, _orbe(a))

    durs = [a for a in lune_aspects if a["aspect"] in ASPECTS_DURS]
    durs.sort(key=weight)
    priolist = [ _fmt_aspect(a) for a in durs[:3] ]

    if lune_ruler and ruler_aspects:
        # ajoute le 1er aspect le plus “parlant” du maître
        priolist.append(_fmt_aspect(sorted(ruler_aspects, key=weight)[0]))

    # 👉 Prioriser explicitement les liens Lune↔Soleil / Lune↔Saturne et le MC
    durs_lune_soleil = [a for a in lune_soleil if a.get("aspect") in ASPECTS_DURS]
    durs_lune_soleil.sort(key=_orbe)
    if durs_lune_soleil:
        # on le met en tête (lien mère–père/volonté très structurant)
        priolist.insert(0, _fmt_aspect(durs_lune_soleil[0]))

    durs_lune_saturne = [a for a in lune_saturne if a.get("aspect") in ASPECTS_DURS]
    durs_lune_saturne.sort(key=_orbe)
    if durs_lune_saturne:
        priolist.append(_fmt_aspect(durs_lune_saturne[0]))

    if mc_aspects:
        # ajoute l’aspect au MC le plus serré
        priolist.append(_fmt_aspect(sorted(mc_aspects, key=_orbe)[0]))

    points_prioritaires = "\n".join(dict.fromkeys(priolist)) or "—"

    return {
        "resume_bloc2": resume,
        "points_prioritaires_bloc2": points_prioritaires
    }

def _val(v, default: str = "non précisé ici") -> str:
    v = (v or "").strip()
    return v if v else default

def _extract_nakshatra_lune(contexte: dict) -> str:
    """
    Retourne le nakshatra de la Lune à partir de plusieurs emplacements possibles.
    Priorité:
      1) contexte["nakshatra_lune"] si déjà injecté par l'orchestrateur
      2) contexte[planetes_vediques|placements_vediques|resultats_vediques]["Lune"]["nakshatra"]
      3) contexte["theme"][... mêmes clés ...]
      4) NOUVEAU : extraction depuis placements_str avec regex
    Sinon: "non précisé ici"
    """
    # 1) Direct si déjà fourni
    direct = (contexte.get("nakshatra_lune") or "").strip()
    if direct:
        return direct

    # 2) Recherche dans le contexte direct puis dans contexte["theme"]
    for scope in (contexte, (contexte.get("theme") or {})):
        if not isinstance(scope, dict):
            continue
        for key in ("planetes_vediques", "placements_vediques", "resultats_vediques"):
            ved = scope.get(key) or {}
            if isinstance(ved, dict):
                lune = ved.get("Lune") or ved.get("lune") or {}
                nk = (lune.get("nakshatra") or lune.get("nakshatra_lune") or "").strip()
                if nk:
                    return nk

    # 3) NOUVEAU : Extraction depuis placements_str avec regex
    placements_str = contexte.get("placements_str", "")
    if placements_str:
        # Cherche le pattern "Lune — Nakshatra : NomDuNakshatra"
        pattern = r"Lune\s*[—-]\s*Nakshatra\s*:\s*(\w+)"
        match = re.search(pattern, placements_str, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern alternatif au cas où le format serait différent
        pattern2 = r"Lune.*?Nakshatra.*?:\s*(\w+)"
        match2 = re.search(pattern2, placements_str, re.IGNORECASE | re.DOTALL)
        if match2:
            return match2.group(1).strip()

    return "non précisé ici"


def generer_bloc_2(contexte: Dict[str, Any], max_tokens: int = 1200) -> str:
    # alias local pour calmer l'IDE dans les f-strings
    ctx: Dict[str, Any] = contexte
    """
    Génère la section Trinité (Ascendant / Soleil / Lune).
    Version enrichie avec placements_str complet et axes majeurs.
    """

    # ✅ Récupérer le thème
    theme = contexte.get("theme") or contexte.get("data_theme")
    if not theme:
        return "❌ Contexte invalide : 'theme' manquant pour le Bloc 2."

    # ✅ Construire le mini-résumé ciblé (Lune/IV/etc.)
    meta = build_resume_bloc2(theme, contexte)
    resume_bloc2 = meta["resume_bloc2"]
    priorites_2 = meta["points_prioritaires_bloc2"]

    # Balises « angles » injectées par l’orchestrateur
    conj_ic = (ctx.get("conjonctions_ic") or "").strip()
    conj_mc = (ctx.get("conjonctions_mc") or "").strip()

 
    # ✅ AMÉLIORATION : Utiliser les données enrichies
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    )
    if (not placements_str or len(placements_str) < 50) and theme.get("planetes"):
        try:
            from utils.formatage import formater_positions_planetes
            placements_str = formater_positions_planetes(theme["planetes"])
            print("ℹ️ Bloc 2: placements_str reconstruit depuis theme")
        except Exception as e:
            print("⚠️ Bloc 2: impossible de reconstruire placements_str:", e)

    # ✅ NOUVEAU : Récupérer les axes majeurs (conservé si besoin plus tard)
    axes_majeurs = contexte.get("axes_majeurs_str", "")
    tonalite = contexte.get("tonalite", "tu")
    genre_label = contexte.get("genre", "femme")  # ou 'homme'

    # 🔹 NEW — RAG : on récupère et on condense
    rag_snippets = contexte.get("rag_snippets") or ""
    if rag_snippets:
        # déduplication simple + cap ~2500 chars pour ne pas noyer le LLM
        lines, seen = [], set()
        for ln in rag_snippets.splitlines():
            k = ln.strip()
            if not k:
                continue
            key = k.lower()
            if key not in seen:
                seen.add(key)
                lines.append(k)
        rag_short = "\n".join(lines)[:2500]
    else:
        rag_short = ""

    # 🔹 NEW — Accords de genre (cohérence rédaction)
    if genre_label == "femme":
        genre_txt = "C'est une femme : adapte rigoureusement tes formulations au féminin."
    else:
        genre_txt = "C'est un homme : adapte rigoureusement tes formulations au masculin."

    # 🔹 Récupération robuste du nakshatra Lune (CORRIGÉE)
    nakshatra_lune = _extract_nakshatra_lune(contexte)

    print("📌 Bloc 2 - Données reçues:")
    print(f"   placements_str: {len(placements_str)} chars")
    print(f"   axes_majeurs: {len(axes_majeurs)} chars")
    print(f"   Aperçu placements: {placements_str[:200]}...")
    print(f"   Nakshatra Lune: {nakshatra_lune}")

    LONGUEUR_MIN, LONGUEUR_MAX = 400, 600  # mots (référence interne, non utilisée dans le prompt)

    # ✅ AMÉLIORATION : Prompt enrichi
    prompt = f"""
    Tu es une astrologue expérimentée, plein d'humour, à la plume fine, directe, drôle, lucide, sarcastique.
    Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
    Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
    Ton style est vivant mais jamais niais,  jamais pompeux. Pas de poésie. Tu évites les clichés astrologiques.
    Tu ne parles pas *de* la personne, tu lui parles *directement*.
    Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

    {genre_txt}

   SECTION 2 : La Lune — Monde intérieur, émotions, besoins, enfance, mère

    # Contexte à traiter en premier (monde intérieur)
    {resume_bloc2}


    # Points prioritaires (obligatoires en tête d'analyse)
    {priorites_2}


    Contexte védique (nakshatra lunaire) :
    {nakshatra_lune}


    # Données factuelles (référence)
    {placements_str}


  Instructions :
    - Écris une lecture globale, cohérente et incarnée du :
         monde intérieur, de l'intimité, des dynamiques émotionnelles, des besoins , des schémas passés, de l'enfance/relation éventuelle à la mère.
    - Traite aussi le pôle père/autorité via le Soleil (père/volonté), Saturne (structure, peurs/loyautés), et Maison X / MC si pertinent — toujours en lien avec la Lune et la dynamique familiale.
    - Ne commente pas les positions une par une.
    - Parle vrai, cash, pas besoin de brosser dans le sens du poil. Pas de "Ton thème est un véritable patchwork, un cocktail explosif, fascinant etc). Pas de phrases bateaux, poétiques. Sois aussi profond que drôle et sarcastique !
    - Repère les tensions internes (les dissonances, les contradictions).
    - Parle des dynamiques psychologiques sous-jacentes.
    - Mets en lumière les ressources intérieures.
    - Appuie-toi sur des repères de psychologie jungienne (Persona / Ombre, Anima-Animus, processus d’individuation, fonctions psychologiques) pour proposer des axes d’intégration concrets adaptés au profil.
    - Ose montrer les tiraillements, les paradoxes, les excès ou inhibitions.
    - Tu peux ajouter un regard existentiel si pertinent.
    - Donne des exemples concrets.
    - Utilise le Nakshatra de la Lune. Développe 1 paragraphe approfondi sur {nakshatra_lune}. La divinité associée et ses caractéristiques. Explique les forces et les défis psychologiques concrets que ce Nakshatra amène dans le vécu émotionnel.
    - Terminer par 2–3 pistes d'intégration pratiques et une transition vers les axes majeurs du thème.
    - Pas de coaching générique à l'eau de rose "écris un journal, explore tes zones d'ombre, tes émotions sans jugement", ça n'aide en rien.
    - ⚠️ N'INVENTE AUCUN PLACEMENT. Tout ce que tu cites doit se trouver dans la liste des placements.
    
    Format de sortie attendu :
    4–5 paragraphes TRES APPROFONDIS en français, texte continu (pas de listes), respectant les contraintes ci-dessus. Utilise le tutoiement.
    """

    print(prompt)

    resultat = ask_llm(
        prompt,
        max_tokens=max_tokens,
        temperature=0.9,
    )

    print("===== RÉSULTAT BLOC 2 =====")
    print(resultat[:2000])  # éviter le spam en console
    print("===== FIN RÉSULTAT BLOC 2 =====")

    return resultat