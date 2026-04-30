from utils.llm_client import ask_llm
from textwrap import dedent
from typing import Dict, List
import re  
from utils.selection_donnees import filtrer_aspects_ascendant
from utils.selection_donnees import filtrer_planetes_maison_occidentale
from utils.selection_donnees import exclure_aspects_aux_noeuds

ASPECTS_DURS = {"Carré", "Opposition", "Conjonction"}
ASPECTS_MOUS = {"Trigone", "Sextile"}
ORBE_MAX_ASC = 5.5
ORBE_MAX_KEY = 5.0

POINT_ASTRAL_EXCLUS = {
    "Junon",
    "Chiron",
    #"Lune Noire",
    "Part de Fortune",
    "Cérès",
    "Pallas",
    "Vesta",
}

def _fmt_aspect(a: Dict) -> str:
    return f"{a['planete1']} {a['aspect']} {a['planete2']} (orbe {a['orbe']}°)"

def _is_to(target: str, a: Dict) -> bool:
    return a["planete1"] == target or a["planete2"] == target

def _is_between(p1: str, p2: str, a: Dict) -> bool:
    s = {a["planete1"], a["planete2"]}
    return p1 in s and p2 in s

def _orbe(a: Dict) -> float:
    try:
        return float(a.get("orbe", 99))
    except:
        return 99
    
def _is_excluded_point(nom: str) -> bool:
    return str(nom).strip() in POINT_ASTRAL_EXCLUS


def filtrer_aspects_point_astral(aspects: List[Dict]) -> List[Dict]:
    return [
        a for a in aspects
        if not _is_excluded_point(a.get("planete1"))
        and not _is_excluded_point(a.get("planete2"))
    ]


def filtrer_planetes_point_astral(planetes: Dict) -> Dict:
    return {
        nom: obj for nom, obj in planetes.items()
        if not _is_excluded_point(nom)
    }

def _strong(a: Dict, max_orbe: float) -> bool:
    return _orbe(a) <= max_orbe

def _pick(aspects: List[Dict], keep_fn, max_orbe, whitelist=None):
    out = []
    for a in aspects:
        if keep_fn(a) and _strong(a, max_orbe):
            if (whitelist is None) or (a["aspect"] in whitelist):
                out.append(a)
    # trier par orbe croissante
    out.sort(key=_orbe)
    return out

def planets_in_house(planetes: Dict, house_num: int) -> List[str]:
    out = []
    for nom, obj in planetes.items():
        if nom in ("Ascendant", "MC", "Rahu", "Ketu") or _is_excluded_point(nom):
            continue
        m = obj.get("maison")
        if m == house_num or str(m) == str(house_num):
            out.append(nom)
    return out

def master_of_asc(sign_asc: str) -> str:
    # Règles classiques tropicales
    rulers = {
        "Bélier": "Mars", "Taureau": "Vénus", "Gémeaux": "Mercure", "Cancer": "Lune",
        "Lion": "Soleil", "Vierge": "Mercure", "Balance": "Vénus", "Scorpion": "Mars",
        "Sagittaire": "Jupiter", "Capricorne": "Saturne", "Verseau": "Saturne",
        "Poissons": "Jupiter"
    }
    return rulers.get(sign_asc, "Mercure")


_ROMAN = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12}

def _roman_or_int_to_num(tok: str) -> int | None:
    if not tok: 
        return None
    t = str(tok).strip().upper()
    if t.isdigit():
        try: return int(t)
        except: return None
    return _ROMAN.get(t)

def planets_in_house_from_text(placements_str: str, house_num: int) -> list[str]:
    """
    Fallback hyper simple : scanne placements_str et extrait
    'Planète ... Maison X' ou 'Planète en maison X'
    """
    if not placements_str:
        return []
    out = set()
    # exemples acceptés :
    # "Vénus — Maison I" | "Vénus — Maison 1" | "Vénus en maison 1"
    # "Vénus : ... Maison I"
    pattern = re.compile(
        r"^\s*([A-Za-zÉÈÊÀÂÎÔÛÇéèêàâîôûç\- ]+?)\s*(?:[:\-–—]|)\s*.*?\bMaison\s+([IVX]+|\d+)\b",
        re.IGNORECASE | re.MULTILINE
    )
    for m in pattern.finditer(placements_str):
        plan = m.group(1).strip().capitalize()
        hraw = m.group(2)
        hnum = _roman_or_int_to_num(hraw)
        if hnum == house_num:
            # filtre : on veut des planètes/points “classiques”
            if plan.lower() not in {"ascendant","mc","ic","descendant"}:
                out.add(plan)
    # autre format : "Vénus en maison 1"
    pattern2 = re.compile(
        r"\b([A-Za-zÉÈÊÀÂÎÔÛÇéèêàâîôûç\- ]+?)\s+en\s+maison\s+([IVX]+|\d+)\b",
        re.IGNORECASE
    )
    for m in pattern2.finditer(placements_str):
        plan = m.group(1).strip().capitalize()
        hraw = m.group(2)
        hnum = _roman_or_int_to_num(hraw)
        if hnum == house_num and plan.lower() not in {"ascendant","mc","ic","descendant"}:
            out.add(plan)
    return sorted(out)

def planets_in_house_from_text(placements_str: str, house_num: int = 1) -> list[str]:
    """
    Fallback ultra simple : détecte les planètes en Maison `house_num` à partir de placements_str.
    Gère :
      - lignes du type "Vénus — Maison I" ou "Vénus en maison 1"
      - "Planètes en Maison I : Vénus, Mars"
    Évite d'inclure les angles (Ascendant/MC/IC/Descendant) et les nœuds.
    """
    if not placements_str:
        return []
    out = set()

    # 1) Lignes individuelles (ex: "Vénus — Maison I" ou "Vénus en maison 1")
    roman = "I" * house_num  # pour 1 -> "I", 2 -> "II", etc. (au cas où)
    pat_line = re.compile(
        rf"^([A-Za-zÉÈÀÂÊÎÔÛÄËÏÖÜÇéèàâêîôûäëïöüç\- ]+?).*?\bmaison\b\s*(?:{roman}|{house_num})\b",
        flags=re.IGNORECASE
    )
    for line in placements_str.splitlines():
        m = pat_line.search(line.strip())
        if m:
            nom = m.group(1).strip(" —:-•")
            nom_low = nom.lower()
            if nom_low not in ("ascendant", "mc", "ic", "descendant", "rahu", "ketu", "lune noire"):
                out.add(nom)

    # 2) Ligne récap (ex: "Planètes en Maison I : Vénus, Mars")
    pat_list = re.compile(
        rf"Planètes?\s+en\s+Maison\s+(?:{roman}|{house_num})\s*[:\-]\s*(.+)",
        flags=re.IGNORECASE
    )
    m2 = pat_list.search(placements_str)
    if m2:
        for p in re.split(r"\s*,\s*", m2.group(1)):
            p = p.strip(" .;:•")
            if p and p.lower() not in ("ascendant", "mc", "ic", "descendant", "rahu", "ketu", "lune noire"):
                out.add(p)

    return sorted(out)


def build_resume_bloc1(theme: Dict, placements_str: str | None = None) -> Dict[str, str]:
    """
    Bloc 1 : Ascendant / Maître d'Ascendant / Maison I / Soleil
    Avec fallback texte pour les planètes en Maison I si le dict 'theme' ne les renseigne pas.
    """
    planetes = filtrer_planetes_point_astral(theme["planetes"])
    aspects = filtrer_aspects_point_astral(theme["aspects"])
    asc = planetes.get("Ascendant", {}) or {}
    asc_sign = asc.get("signe", "N/A")
    asc_deg  = asc.get("degre", "N/A")

    # 1) Conjonctions & aspects vers l’Ascendant
    asc_conj = _pick(aspects, lambda a: _is_to("Ascendant", a), ORBE_MAX_ASC, {"Conjonction"})
    asc_aspects = _pick(aspects, lambda a: _is_to("Ascendant", a), ORBE_MAX_ASC, ASPECTS_DURS | ASPECTS_MOUS)

    # 2) Planètes en Maison I (dict -> puis fallback texte)
    maison1_planetes = planets_in_house(planetes, 1)
    if not maison1_planetes and placements_str:
        placements_str = filtrer_texte_point_astral(placements_str)
        maison1_planetes = planets_in_house_from_text(placements_str, 1)

    # 3) Maître d’Ascendant
    maitre = master_of_asc(asc_sign)
    maitre_obj = planetes.get(maitre, {}) or {}
    maitre_sign  = maitre_obj.get("signe", "N/A")
    maitre_house = maitre_obj.get("maison", "N/A")
    aspects_maitre = _pick(
        aspects, lambda a: _is_to(maitre, a), ORBE_MAX_KEY, ASPECTS_DURS | ASPECTS_MOUS
    )

    # 4) Soleil
    sun = planetes.get("Soleil", {}) or {}
    sun_sign  = sun.get("signe", "N/A")
    sun_house = sun.get("maison", "N/A")
    sun_aspects = _pick(
        aspects, lambda a: _is_to("Soleil", a), ORBE_MAX_KEY, ASPECTS_DURS | ASPECTS_MOUS
    )

    # Strings
    asc_conj_str       = "\n".join(_fmt_aspect(a) for a in asc_conj) or "—"
    #asc_aspects_str    = "\n".join(_fmt_aspect(a) for a in asc_aspects) or "—"
    asc_aspects_filtrés = filtrer_aspects_ascendant(asc_aspects, orb_max=ORBE_MAX_ASC)
    asc_aspects_str     = "\n".join(_fmt_aspect(a) for a in asc_aspects_filtrés) or "—"
    #maison1_str        = ", ".join(maison1_planetes) if maison1_planetes else "Aucune"
    # Nettoyage : enlever K/Rahu/Ketu et normaliser Vénus
    maison1_nettoyees  = filtrer_planetes_maison_occidentale(maison1_planetes)
    maison1_str        = ", ".join(maison1_nettoyees) if maison1_nettoyees else "Aucune"
    aspects_maitre_str = "\n".join(_fmt_aspect(a) for a in aspects_maitre) or "—"
    #sun_aspects_str    = "\n".join(_fmt_aspect(a) for a in sun_aspects) or "—"
    sun_aspects_filtrés = exclure_aspects_aux_noeuds(sun_aspects)
    sun_aspects_str     = "\n".join(_fmt_aspect(a) for a in sun_aspects_filtrés) or "—"

    resume = f"""\
Ascendant : {asc_sign} {asc_deg}° — Maison I
Conjonctions à l’Ascendant (≤{ORBE_MAX_ASC}°) :
{asc_conj_str}

Aspects forts à l’Ascendant (≤{ORBE_MAX_ASC}°) :
{asc_aspects_str}

Planètes en Maison I :
{maison1_str}

Maître d’Ascendant : {maitre} en {maitre_sign} — Maison {maitre_house}
Aspects forts du Maître d’Ascendant (≤{ORBE_MAX_KEY}°) :
{aspects_maitre_str}

Soleil : {sun_sign} — Maison {sun_house}
Aspects forts du Soleil (≤{ORBE_MAX_KEY}°) :
{sun_aspects_str}
""".strip()

    # Points prioritaires (top 3–5)
    priolist = []
    priolist += [_fmt_aspect(a) for a in asc_conj[:2]]
    #priolist += [_fmt_aspect(a) for a in asc_aspects if a["aspect"] in ASPECTS_DURS][:2]

    durs_asc_sans_opposition = [a for a in asc_aspects_filtrés if a["aspect"] in ASPECTS_DURS and a["aspect"] != "Opposition"]
    priolist += [_fmt_aspect(a) for a in durs_asc_sans_opposition[:2]]



    durs_sun = [a for a in sun_aspects if a["aspect"] in ASPECTS_DURS]

    def weight(a):
        s = {a["planete1"], a["planete2"]}
        score = 0
        if "Saturne" in s: score -= 2
        if "Pluton" in s:  score -= 2
        return (score, float(str(a.get("orbe","99")).replace(",", ".")))

    durs_sun.sort(key=weight)
    priolist += [_fmt_aspect(a) for a in durs_sun[:2]]

    points_prioritaires = "\n".join(dict.fromkeys(priolist)) or "—"

    return {
        "resume_bloc1": resume,
        "points_prioritaires_bloc1": points_prioritaires,
    }
def filtrer_texte_point_astral(text: str) -> str:
    if not text:
        return ""

    lignes = []
    for line in text.splitlines():
        if any(point.lower() in line.lower() for point in POINT_ASTRAL_EXCLUS):
            continue
        lignes.append(line)

    return "\n".join(lignes)

def generer_bloc_1(contexte: dict, max_tokens: int = 1400) -> str:
    """
    Section 1 : Ascendant & Maître d'Ascendant.
    Branchée sur RAG + tonalité + genre.
    """

    theme = contexte.get("theme")
    if not theme:
        return "❌ Contexte invalide : 'theme' manquant pour le Bloc 1."

    # ✅ DÉFINIR placements_str AVANT de l'utiliser (et garder une seule version)
    placements_str = (
        contexte.get("placements_str")
        or contexte.get("placements")
        or ""
    )
    placements_str = filtrer_texte_point_astral(placements_str)
    if (not placements_str or len(placements_str) < 50) and theme.get("planetes"):
        try:
            from utils.formatage import formater_positions_planetes
            placements_str = formater_positions_planetes(theme["planetes"])
            print("ℹ️ Bloc 1: placements_str reconstruit depuis theme")
        except Exception as e:
            print("⚠️ Bloc 1: impossible de reconstruire placements_str:", e)

    # 👉 construire le mini-résumé (on passe placements_str pour le fallback texte “Maison I”)
    meta = build_resume_bloc1(theme, placements_str)
    resume_bloc1 = meta["resume_bloc1"]
    priorites_1  = meta["points_prioritaires_bloc1"]

    axes_majeurs = contexte.get("axes_majeurs_str", "")
    rag_snippets = contexte.get("rag_snippets", "") or ""


    # ✅ AJOUT : Récupération des conjonctions À L'ASCENDANT (depuis points forts)
    conj_ascendant_str = (
        contexte.get("conjonctions_ascendant") 
        or contexte.get("conj_ascendant_str")
        or contexte.get("conj_asc_str")
        or ""
    )

    # ✅ AJOUT : Récupération du maître d'Ascendant
    maitre_asc_str = (
        contexte.get("maitre_asc_str") 
        or contexte.get("maitre_ascendant")
        or contexte.get("maitre_asc")
        or ""
    )

    # --- Préférences style & genre (VENANT DE L’ORCHESTRATEUR) ---
    tonalite = (contexte.get("tonalite") or "tu").strip().lower()   # "tu" | "vous"
    g_raw = (contexte.get("genre") or "").strip().lower()
    # tolère f/w/femme ; m/h/homme ; sinon neutre -> on force un label pour l’accord
    if g_raw.startswith(("f", "w")):
        genre_label = "femme"
    elif g_raw.startswith(("m", "h")) or g_raw in ("male", "homme"):
        genre_label = "homme"
    else:
        genre_label = "homme"  # valeur sûre si inconnu (évite le neutre bancal en FR)

    # 👀 DEBUG : loguer ce qu’on reçoit
    print("===== DEBUG BLOC 1 =====")
    print("🔹 contexte keys:", list(contexte.keys()))
    print("🔹 tonalite brute:", contexte.get("tonalite"))
    print("🔹 genre brut:", contexte.get("genre"))
    print("🔹 tonalite normalisée:", tonalite)
    print("🔹 genre normalisé:", genre_label)
    print("🔹 placements_str chars:", len(placements_str))
    print("🔹 axes_majeurs chars:", len(axes_majeurs))
    print("🔹 len(rag_snippets):", len(rag_snippets))
    print("========================")

    if not placements_str or len(placements_str) < 50:
        return "❌ Données insuffisantes pour analyser l'Ascendant et son maître."

    # ---- RAG : récupération + nettoyage + limite taille ----
    if rag_snippets:
        # déduplication de lignes très proches (simple), trimming et cap ~3.5k
        lines = []
        seen = set()
        for ln in rag_snippets.splitlines():
            k = ln.strip()
            if k and k.lower() not in seen:
                seen.add(k.lower())
                lines.append(k)
        rag_snippets = "\n".join(lines)[:3500]

    # cap tokens pour ce bloc (standard ~4 pages total)
    max_tokens = min(max_tokens, 1500)

    # --- Instruction d’accords de genre pour guider le modèle ---
    if genre_label == "femme":
        genre_txt = "C'est une femme : adapte rigoureusement tes formulations au féminin."
    else:
        genre_txt = "C'est un homme : adapte rigoureusement tes formulations au masculin."

    faits_autorises = (contexte.get("faits_autorises") or "").strip()
    LONGUEUR_MIN, LONGUEUR_MAX = 400, 600  # mots

    # ----- PROMPT utilisateur (avec RAG injecté) -----
    prompt = dedent(f"""



Tu es une astrologue expérimentée, plein d'humour, à la plume fine, directe, drôle, lucide, sarcastique.
Tu proposes des analyses psychologiques profondes, qui vont à l'essentiel.
Tu parles à la personne avec respect, sans flatterie, ni fioriture inutile, ni phrases creuses.
Ton style est vivant mais jamais niais, jamais pompeux. Pas de poésie.. Tu évites les clichés astrologiques.
Tu ne parles pas *de* la personne, tu lui parles *directement*.
Tu aides la personne à prendre conscience de ses forces et défis intérieurs.

Voici les données du thème de {theme['nom']} :
{genre_txt}

# Contexte narratif ciblé (à traiter en premier)
{resume_bloc1}


# Points prioritaires (obligatoires en tête d'analyse)
{priorites_1}


# Données astrologiques COMPLÈTES (référence)
{placements_str}


Section 1 : Identité & Corps (Ascendant, Maître d'Ascendant, Maison I, Soleil)

Instruction :
Écris une lecture globale, cohérente et incarnée de la section 1.
- Evite de commencer directement "Avec ton Ascendant"...
- Ne commente pas les positions une par une.
- Repère les tensions internes (les dissonances, les contradictions) avec le reste du thème. 
- Parle des dynamiques psychologiques sous-jacentes.
- Mets en lumière les ressources intérieures.
- Parle vrai, cash, pas besoin de brosser dans le sens du poil. Pas de "Ton thème est un véritable patchwork, un cocktail explosif, fascinant etc). Pas de phrases bateaux, poétiques. Sois aussi profond que drôle et sarcastique !
- Ose montrer les tiraillements, les paradoxes, les excès ou inhibitions.
- Tu peux ajouter un regard existentiel si pertinent.
- Donne des exemples concrets.
- Appuie-toi sur des repères de psychologie jungienne (Persona / Ombre, Anima-Animus, processus d’individuation, fonctions psychologiques) pour proposer des axes d’intégration concrets adaptés au profil.
- Pas de coaching générique à l'eau de rose "écris un journal, explore tes zones d'ombre, tes émotions sans jugement", ça n'aide en rien.
- Conclure par une phrase de transition ouvrant vers la Lune et le monde intérieur, sans résumer.
- ⚠️ N'INVENTE AUCUN PLACEMENT. Tout ce que tu cites doit se trouver dans la liste des placements.

Format de sortie attendu :
4–5 paragraphes en français, texte continu (pas de listes), respectant les contraintes ci-dessus. Utilise le tutoiement.


    """)

    print(prompt)

    resultat = ask_llm(
        prompt,
        #system=system,                # ← utilise le system dynamique
        max_tokens=max_tokens,
        temperature=0.7,
    )

    # DEBUG utile : garder le résultat (on n'affiche plus le prompt)
    print("===== RÉSULTAT BLOC 1 =====")
    print(resultat[:4000])  # éviter le spam en console
    print("===== FIN RÉSULTAT BLOC 1 =====")

    return resultat