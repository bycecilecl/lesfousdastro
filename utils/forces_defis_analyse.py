# utils/forces_defis_analyse.py
from __future__ import annotations

from utils.selection_donnees import construire_selection_point_astral
from utils.openai_utils import interroger_llm
from utils.convert_markdown_light import md_light_to_html
from utils.fd_inject import build_unified_priorities
# >>> FD inject facultatif
# try:
#     from utils.fd_inject import build_markdown_blocks  # type: ignore
# except Exception:
#     def build_markdown_blocks(*args, **kwargs) -> str:
#         # fallback inoffensif : rien à injecter
#         return ""

# --- Disclaimer (HTML) appliqué à la fin du rendu ---

DISCLAIMER_FORCES_DEFIS_HTML = r"""
<div class="disclaimer" style="background:#f8f9fa;border:1px solid #dee2e6;
    padding:16px;margin:24px 0;border-radius:8px;font-size:13px;line-height:1.5;">

  <p style="margin:0 0 10px 0;">
    <strong>⚠️ À propos du module « Mes Potentiels et mes Défis »</strong><br>
    Cette lecture met en lumière les <u>dynamismes intérieurs</u> de ton thème natal : 
    ce qui te soutient, te bloque, ou t’invite à grandir.  
    Elle s’appuie sur les aspects planétaires et les maisons clés pour traduire 
    les <em>forces</em> et <em>tensions formatrices</em> qui colorent ton chemin.
  </p>

  <p style="margin:0 0 10px 0;">
    <strong>❗️Important :</strong> Ce texte est une lecture automatisée générée 
    à partir de ton thème, non une interprétation manuelle.  
    <u>Rien n’est figé :</u> chaque potentiel peut être endormi, intégré ou en 
    transformation selon ton histoire, ta conscience et ton vécu.  
    Si certains passages ne résonnent pas, c’est ok !  
    L’astrologie se lit toujours dans la <em>globalité du thème</em> : un même aspect 
    peut s’exprimer de multiples façons selon les autres placements, ton parcours 
    ou ton niveau d’intégration.  
    Ce texte n’a donc pas vocation à enfermer, mais à t’offrir des pistes de réflexion 
    à explorer à ton rythme.
    </p>    

  <p style="margin:0 0 10px 0;">
    <strong>🌗 Perspective :</strong> L’astrologie ici n’impose rien ; elle 
    décrit des <em>mouvements intérieurs</em>.  
    Les défis sont des terrains d’évolution, les forces des appuis à incarner.  
    Ce texte t’invite à observer, pas à te juger.
  </p>

  <p style="margin:0 0 10px 0;">
    <strong>♻️ Note technique :</strong> Cette analyse est générée automatiquement 
    et peut comporter de légères répétitions.  
    Elle reste un support de réflexion ; rien ne remplace un échange 
    ou une exploration plus personnelle pour aller en profondeur.
  </p>

  <p style="margin:0;">
    <strong>💫 Pour aller plus loin :</strong>
    Réserve une consultation personnalisée sur 
    <a href="https://bycecilecl.com" target="_blank" style="color:#1f628e; text-decoration:none;">
      www.bycecilecl.com
    </a>
  </p>
</div>
"""

# ───────── Imports robustes avec fallbacks (module-level) ─────────
try:
    from utils.forces_defis import generer_forces_defis as _GENERER_FORCES_DEFIS  # type: ignore
except Exception:
    _GENERER_FORCES_DEFIS = None

try:
    from utils.forces_defis import extraire_forces_defis_par_maisons  # type: ignore
except Exception:
    def extraire_forces_defis_par_maisons(_):
        return None  # fallback neutre

def _build_bloc_theme_occidental_depuis_selector(theme: dict) -> str:
    """
    Reprend EXACTEMENT la construction des placements comme dans point_astral_blocs.py,
    via construire_selection_point_astral(...). On ne filtre rien, on renvoie le bloc tel quel.
    """
    try:
        bloc = construire_selection_point_astral(theme, max_orbe=5.0)
        return bloc if isinstance(bloc, str) else ""
    except Exception:
        return ""
    

# --- Helpers extraction aspects (placé au-dessus de _build_contexte_compact) ---
def _coerce_name(x):
    """Convertit id/dict/label -> nom lisible ; sinon renvoie la valeur brute."""
    if x is None:
        return None
    if isinstance(x, dict):
        # noms possibles
        for k in ("name", "nom", "label", "planet", "body", "point"):
            if x.get(k):
                return str(x[k])
        # id brut
        for k in ("id", "key", "code"):
            if x.get(k):
                return str(x[k])
        return None
    if isinstance(x, (str, int)):
        return str(x)
    return None

def _extract_names_types_orb(a):
    """Extrait p1, type, p2, orbe d'un aspect (gère formats très variés)."""
    # 1) Si string → parser "Soleil Sextile Lune"
    if isinstance(a, str):
        import re
        m = re.search(
            r"([A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)\s+"
            r"(Conjonction|Sextile|Trigone|Carr[ée]?|Opposition|Quinconce|"
            r"Conjunction|Trine|Square|Opposition|Quincunx)"
            r"\s+([A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)",
            a, flags=re.I
        )
        # orbe éventuel dans le texte
        orb = None
        m_orb = re.search(r"orbe\s*([0-9]+(?:\.[0-9]+)?)", a, flags=re.I)
        if m_orb:
            try:
                orb = float(m_orb.group(1))
            except Exception:
                pass

        if m:
            return m.group(1), m.group(2), m.group(3), orb
        return "?", "?", "?", orb

    if not isinstance(a, dict):
        return "?", "?", "?", None

    # 2) Type
    t = (a.get("type") or a.get("aspect") or a.get("relation") or 
         a.get("aspect_type") or a.get("kind") or "?")

    # 3) P1/P2 : grand tour d’alias
    p1 = (a.get("p1") or a.get("planet1") or a.get("A") or a.get("a") or 
          a.get("body1") or a.get("point1") or a.get("planete1") or
          a.get("from") or a.get("source"))
    p2 = (a.get("p2") or a.get("planet2") or a.get("B") or a.get("b") or 
          a.get("body2") or a.get("point2") or a.get("planete2") or
          a.get("to") or a.get("target"))

    # 3b) Si dicts imbriqués
    if isinstance(p1, dict): p1 = _coerce_name(p1)
    if isinstance(p2, dict): p2 = _coerce_name(p2)

    # 3c) Listes ["Soleil","Lune"] ou ["sun","moon"]
    if not p1 or not p2:
        planets_list = a.get("planets") or a.get("p") or a.get("bodies") or a.get("points") or a.get("pair") or []
        if isinstance(planets_list, (list, tuple)) and len(planets_list) >= 2:
            p1 = p1 or _coerce_name(planets_list[0])
            p2 = p2 or _coerce_name(planets_list[1])

    # 3d) Dernier recours : label libre
    if (not p1 or not p2) and (a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text")):
        label = a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text")
        import re
        m = re.search(
            r"([A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)\s+"
            r"(Conjonction|Sextile|Trigone|Carr[ée]?|Opposition|Quinconce|"
            r"Conjunction|Trine|Square|Opposition|Quincunx)"
            r"\s+([A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)",
            label, flags=re.I
        )
        if m:
            p1 = p1 or m.group(1)
            t  = t  if t != "?" else m.group(2)
            p2 = p2 or m.group(3)

    # 4) Orbe
    orb = a.get("orb") or a.get("orbe") or a.get("delta") or a.get("d")
    try:
        orb = float(orb) if orb is not None else None
    except Exception:
        orb = None

    # Normalisation type en FR
    t_low = (t or "").lower()
    MAP = {"conjunction": "Conjonction", "trine": "Trigone", "square": "Carré"}
    if t_low in MAP: t = MAP[t_low]
    elif t == "?":   t = "?"

    p1 = p1 or "?"
    p2 = p2 or "?"

    # DEBUG utile
    if p1 == "?" or p2 == "?":
        try:
            print("⚠️ Aspect non parsé correctement :", a)
            if isinstance(a, dict):
                print("   Clés disponibles :", list(a.keys()))
        except Exception:
            pass

    return p1, t, p2, orb


# ───────── Fallback local si pas de générateur dispo ─────────
def _fallback_generer_forces_defis(data_theme: dict) -> dict:
    forces, defis = [], []
    synthese = ""

    aspects = data_theme.get("aspects") or []
    if isinstance(aspects, list):
        for a in aspects[:40]:
            try:
                a_type = (a.get("type") or a.get("aspect") or "").lower()
                p1 = a.get("p1") or a.get("planet1") or a.get("A") or "Planète A"
                p2 = a.get("p2") or a.get("planet2") or a.get("B") or "Planète B"
                orb = a.get("orb") or a.get("orbe") or ""
                label = f"{p1} {a_type} {p2}".strip()
                if a_type in ("trigone", "sextile", "conjonction", "conjunction"):
                    forces.append(f"• {label} (orbe {orb}) : soutien naturel à mobiliser au quotidien.")
                elif a_type in ("carré", "carre", "opposition", "quincunx", "quinconce"):
                    defis.append(f"• {label} (orbe {orb}) : tension formatrice à intégrer avec méthode.")
            except Exception:
                continue

    for k in ("chiron", "Chiron"):
        if k in data_theme:
            defis.append("• Chiron actif : travail de guérison/réconciliation sur un axe clé.")
            break

    for k in ("lune_noire", "Lune Noire", "black_moon", "lilith"):
        if k in data_theme:
            defis.append("• Lune Noire présente : zones de radicalité ou de tabou à apprivoiser.")
            break

    noeuds = data_theme.get("noeuds") or data_theme.get("noeuds_lunaires") or {}
    if isinstance(noeuds, dict) and any(noeuds.values()):
        defis.append("• Nœuds lunaires marqués : trajectoire karmique/évolutive à harmoniser.")

    if forces or defis:
        synthese = "Potentiels identifiés à activer et tensions structurantes à transmuter."

    return {"forces": forces, "defis": defis, "synthese_courte": synthese}

def _normalize_aspect_type(t: str) -> str:
    """Ramène le type d’aspect à un libellé FR canonique (minuscule)."""
    if not t:
        return "?"
    if not isinstance(t, str):
        t = str(t)  # ← IMPORTANT: évite AttributeError .strip() sur dict
    tl = t.strip().lower()
    mapping = {
        "conjunction": "conjonction",
        "conjonction": "conjonction",
        "trine": "trigone",
        "trigone": "trigone",
        "sextile": "sextile",
        "square": "carré",
        "carre": "carré",
        "carré": "carré",
        "opposition": "opposition",
        "quinconce": "quinconce",
        "quincunx": "quinconce",
    }
    return mapping.get(tl, tl)

def _filtrer_aspects_par_type(aspects_all, max_aspects=None):
    """
    Garde les aspects selon des orbes dynamiques :
      - Conjonction ≤ 9°
      - Carré / Opposition ≤ 7°
      - Trigone / Sextile ≤ 5°
    Puis trie par 'utilité' (durs>souples, luminaires/angles, orbe serré).
    Retourne une liste de lignes déjà formatées pour le prompt.
    """
    ORB_LIMITS = {
        "conjonction": 9.0,
        "carré": 7.0,
        "opposition": 7.0,
        "trigone": 5.0,
        "sextile": 5.0,
        # (optionnel) "quinconce": 3.0,
    }

    focus = {"soleil", "lune", "mars", "saturne", "pluton", "vénus", "venus", "mercure", "ascendant", "rahu", "ketu", "noeud nord", "nœud nord", "noeud sud", "nœud sud"}
    hard = {"carré", "opposition"}         # quinconce si tu veux
    soft = {"trigone", "sextile", "conjonction"}

    keep = []

    for a in (aspects_all or []):
        # Extraction robuste
        p1, t, p2, orb = _extract_names_types_orb(a if isinstance(a, dict) else {"label": str(a)})
        typ = _normalize_aspect_type(t)

        # Essaie aussi de lire l’orbe dans un label si orb manquant
        if orb is None and isinstance(a, dict):
            label = a.get("label") or a.get("description") or a.get("name") or a.get("title") or a.get("text") or ""
            import re
            m = re.search(r"orbe\s*([0-9]+(?:\.[0-9]+)?)", label, flags=re.I)
            if m:
                try:
                    orb = float(m.group(1))
                except Exception:
                    pass

                
        # On ne garde que si on a un type connu et un orb numérique
        if typ not in ORB_LIMITS or not isinstance(orb, (int, float)):
            continue

        if float(orb) > ORB_LIMITS[typ]:
            continue

        # Score utilité (plus haut = plus prioritaire)
        tlow = typ.lower()
        w = 0
        if tlow in hard: w += 3
        if tlow in soft: w += 2

        p1l = (p1 or "").lower()
        p2l = (p2 or "").lower()
        if p1l in focus: w += 2
        if p2l in focus: w += 2

        try:
            w += max(0, int(ORB_LIMITS[typ]) - int(round(float(orb))))  # orbe serré → mieux
        except Exception:
            pass

        keep.append({
            "a": a,
            "p1": p1 or "?",
            "p2": p2 or "?",
            "typ": typ,     # déjà normalisé
            "orb": float(orb),
            "w": w
        })

    # Tri par utilité puis orbe (le plus serré d’abord)
    keep.sort(key=lambda x: (-x["w"], x["orb"]))
    if isinstance(max_aspects, int) and max_aspects > 0:
        keep = keep[:max_aspects]

    # Formatage final
    def _fmt(row):
        o = f"{row['orb']:.2f}"
        # Capitaliser la 1ère lettre du type pour l’affichage
        typ_disp = row["typ"].capitalize()
        return f"{row['p1']} {typ_disp} {row['p2']} (orbe {o}°)"

    return [f"- {_fmt(r)}" for r in keep]

# --- Contexte compact pour Forces & Défis ---
def _build_contexte_compact(theme: dict, max_aspects=20) -> dict:
    """
    Rassemble UNIQUEMENT la matière utile :
    - Axes/signes interceptés + maisons (prioritaires)
    - Soleil/Lune : signe + maison (+ exil/chute utiles)
    - Maisons VIII et XII : planètes présentes
    - Planètes angulaires (I/X)
    - Rétrogrades clés
    - Aspects (orbes dynamiques : ≤5° trigone/sextile, ≤7° carré/opposition, ≤9° conjonction)
    - Amas (stelliums) s’ils existent
    (AUCUNE donnée védique, pas de dominances globales, pas de nakshatra ici)
    """

    # 1) Interceptions
    interceptions = theme.get("interceptions", {})
    inter_lines = []
    if isinstance(interceptions, dict) and interceptions:
        for axe, data in interceptions.items():
            if isinstance(data, dict):
                signes  = data.get("signes") or data.get("signs") or []
                maisonA = data.get("maisonA") or data.get("houseA")
                maisonB = data.get("maisonB") or data.get("houseB")
                if signes:
                    inter_lines.append(
                        f"- Axe {axe} intercepté : {', '.join(signes)} (Maisons {maisonA} / {maisonB})"
                    )

    # 2) Soleil / Lune
    def _fmt_placement(nom):
        obj = (theme.get("planetes") or {}).get(nom) or theme.get(nom.lower()) or {}
        signe = obj.get("signe") or obj.get("sign") or obj.get("zodiaque")
        maison = obj.get("maison") or obj.get("house")
        return f"{nom} : {signe or '?'} (Maison {maison or '?'})"
    sol_line  = _fmt_placement("Soleil")
    lune_line = _fmt_placement("Lune")

    # 3) Maisons VIII & XII : qui s’y trouve ?
    def _planetes_en_maison(num):
        out = []
        for nom, p in (theme.get("planetes") or {}).items():
            h = p.get("maison") or p.get("house")
            try:
                if int(h) == num:
                    out.append(nom)
            except Exception:
                pass
        return out
    m8  = _planetes_en_maison(8)
    m12 = _planetes_en_maison(12)

    # 4) Angulaires (I / X)
    ang = []
    for nom, p in (theme.get("planetes") or {}).items():
        h = p.get("maison") or p.get("house")
        if str(h) in ("1", "10"):
            ang.append(f"{nom} (M{h})")

    # 5) Rétrogrades (liste courte)
    retro = []
    for nom, p in (theme.get("planetes") or {}).items():
        if p.get("retro") or p.get("r") or (isinstance(p.get("flags"), list) and "retro" in p["flags"]):
            retro.append(nom)

    # 6) Aspects — orbes dynamiques + tri utile
    aspects_lines = []

    # 7) Amas / stelliums (si dispo)
    amas_lines = []
    amas = theme.get("amas") or []
    if isinstance(amas, list):
        for a in amas[:3]:
            try:
                signe = a.get("signe") or a.get("sign")
                pls   = ", ".join(a.get("planetes") or [])
                amas_lines.append(f"- Amas en {signe}: {pls}")
            except Exception:
                continue

    # 8) Dignités ciblées utiles ici (ex: Lune en Capricorne, Vénus en Scorpion)
    dignites_lines = []
    lune  = (theme.get("planetes") or {}).get("Lune")  or {}
    venus = (theme.get("planetes") or {}).get("Vénus") or (theme.get("planetes") or {}).get("Venus") or {}
    if (lune.get("signe") or "").lower().startswith("capri"):
        dignites_lines.append("- Lune en Capricorne (exil) → froideur/maîtrise émotionnelle à travailler.")
    if (venus.get("signe") or "").lower().startswith("scorp"):
        dignites_lines.append("- Vénus en Scorpion (exil) → intensité relationnelle / enjeux de confiance/pouvoir.")

    # — Contexte final compact, ordonné —
    ctx_lines = []

    # Interceptions en premier si présentes
    if inter_lines:
        ctx_lines += ["### Axes interceptés (PRIORITAIRES)"] + inter_lines

    # Clés rapides
    ctx_lines += ["### Clés rapides",
                  f"- {sol_line}",
                  f"- {lune_line}"]

    # # VIII / XII / Angulaires / Rétrogrades
    # if m8:
    #     ctx_lines.append(f"- Maison VIII : {', '.join(m8)}")
    # if m12:
    #     ctx_lines.append(f"- Maison XII : {', '.join(m12)}")
    # if ang:
    #     ctx_lines.append(f"- Planètes angulaires (I/X) : {', '.join(ang)}")
    # if retro:
    #     ctx_lines.append(f"- Rétrogrades : {', '.join(retro)}")

    # Aspects (un seul titre, bon libellé)
    # if aspects_lines:
    #     ctx_lines += ["### Aspects (orbes dynamiques — triés utiles)"] + aspects_lines

    # Amas / Dignités
    if amas_lines:
        ctx_lines += ["### Amas (si pertinents)"] + amas_lines
    if dignites_lines:
        ctx_lines += ["### Dignités ciblées (utile ici)"] + dignites_lines

    return {
        "placements_compacts": "\n".join(ctx_lines).strip()
    }


# ───────── Contexte global (même base que Flash) ─────────
def _build_contexte_global(data_theme) -> dict:
    # 1) Bloc compact (Clés rapides, Aspects triés, etc.)
    ctx_compact = _build_contexte_compact(data_theme)
    placements_compacts = ctx_compact.get("placements_compacts", "")

    # 2) Bloc global complet (toutes les positions/maisons)
    try:
        sel = construire_selection_point_astral(data_theme) or {}
        contexte_global = (
            sel.get("contexte_global")
            or sel.get("resume_global")
            or sel.get("axes_majeurs")
            or ""
        )
        if not isinstance(contexte_global, str):
            contexte_global = str(contexte_global)
    except Exception:
        contexte_global = ""

    # 3) Concat : compact + contexte global (si disponible)
    if contexte_global.strip():
        placements_str = f"{placements_compacts}\n\n### Contexte global\n{contexte_global.strip()}"
    else:
        placements_str = placements_compacts

    return {
        "placements_str": placements_str,
        "axes_majeurs_str": "",
        "rag_snippets": ""
    }


# Ligne ~280 environ (après _build_contexte_global)

def _construire_configurations(data_theme: dict) -> str:
    """Construit le bloc configurations majeures : amas, rétrogrades, angulaires, etc."""
    lines = []
    
    # 1. Détecter les VRAIS amas (3+ planètes en conjonction, dont 2+ perso/sociales)
    planetes = data_theme.get("planetes", {})
    
    # Planètes avec leur longitude
    planetes_long = []
    personnelles_sociales = ["Soleil", "Lune", "Mercure", "Vénus", "Venus", "Mars", "Jupiter", "Saturne"]
    
    for nom, p in planetes.items():
        if nom in ["Ascendant", "Milieu du Ciel", "MC"]:
            continue
        lon = p.get("longitude") or p.get("lon") or p.get("ecliptic_longitude")
        signe = p.get("signe") or p.get("sign")
        maison = p.get("maison") or p.get("house")
        if lon is not None:
            try:
                planetes_long.append({
                    "nom": nom,
                    "lon": float(lon),
                    "signe": signe,
                    "maison": maison,
                    "est_perso_sociale": nom in personnelles_sociales
                })
            except:
                continue
    
    # Trier par longitude
    planetes_long.sort(key=lambda x: x["lon"])
    
    # Chercher des groupes de conjonction (écart < 10°)
    amas_trouves = []
    i = 0
    while i < len(planetes_long):
        groupe = [planetes_long[i]]
        j = i + 1
        
        # Ajouter toutes les planètes à < 10° de la première du groupe
        while j < len(planetes_long):
            ecart = planetes_long[j]["lon"] - groupe[0]["lon"]
            # Gérer le passage 0°/360°
            if ecart > 180:
                ecart = 360 - ecart
            
            if ecart <= 10:
                groupe.append(planetes_long[j])
                j += 1
            else:
                break
        
        # Vérifier critères amas : 3+ planètes dont 2+ perso/sociales
        if len(groupe) >= 3:
            nb_perso_sociale = sum(1 for p in groupe if p["est_perso_sociale"])
            if nb_perso_sociale >= 2:
                amas_trouves.append(groupe)
        
        i = j if j > i + 1 else i + 1
    
    # Formater les amas trouvés
    for amas in amas_trouves:
        noms = ", ".join([p["nom"] for p in amas])
        signe = amas[0]["signe"]
        maison = amas[0]["maison"]
        
        if maison:
            lines.append(f"- Amas en {signe} maison {maison} ({noms})")
        else:
            lines.append(f"- Amas en {signe} ({noms})")
    
    # 1b. Stelliums par signe (3+ planètes, même si pas en conjonction stricte)
    par_signe = {}
    for nom, p in planetes.items():
        if nom in ["Ascendant", "Milieu du Ciel", "MC"]:
            continue
        signe = p.get("signe") or p.get("sign")
        maison = p.get("maison") or p.get("house")
        if signe:
            if signe not in par_signe:
                par_signe[signe] = {"planetes": [], "maison": maison}
            par_signe[signe]["planetes"].append(nom)
    
    # Afficher si 3+ planètes dans le même signe (et pas déjà détecté comme amas)
    for signe, data in par_signe.items():
        if len(data["planetes"]) >= 3:
            noms = ", ".join(data["planetes"])
            maison = data["maison"]
            # Vérifier si déjà affiché comme amas
            deja_affiche = any(signe in line for line in lines)
            if not deja_affiche:
                if maison:
                    lines.append(f"- Stellium en {signe} maison {maison} ({noms})")
                else:
                    lines.append(f"- Stellium en {signe} ({noms})")
    
    # 2. Planètes rétrogrades (seulement personnelles + Saturne)
    retros = []
    for nom in ["Mercure", "Vénus", "Venus", "Mars", "Saturne"]:
        p = planetes.get(nom)
        if p and (p.get("retro") or p.get("r") or ("retro" in (p.get("flags") or []))):
            retros.append(nom)
    
    if retros:
        lines.append(f"- Planètes rétrogrades : {', '.join(retros)}")
    
    # 3. Planètes angulaires (maisons I et X)
    angulaires = []
    for nom, p in planetes.items():
        maison = p.get("maison") or p.get("house")
        if str(maison) in ("1", "10"):
            angulaires.append(f"{nom} (M{maison})")
    
    if angulaires:
        lines.append(f"- Planètes angulaires : {', '.join(angulaires)}")
    
    # 4. Maison XII
    m12 = []
    for nom, p in planetes.items():
        maison = p.get("maison") or p.get("house")
        if str(maison) == "12":
            m12.append(nom)
    
    if m12:
        lines.append(f"- Maison XII : {', '.join(m12)}")

    # 5. Maison VIII (AJOUTÉ)
    m8 = []
    for nom, p in planetes.items():
        maison = p.get("maison") or p.get("house")
        if str(maison) == "8":
            m8.append(nom)

    if m8:
        lines.append(f"- Maison VIII : {', '.join(m8)}")
    
    # 5. Stellium maison I (si 2+ planètes hors Ascendant)
    m1 = []
    for nom, p in planetes.items():
        if nom == "Ascendant":
            continue
        maison = p.get("maison") or p.get("house")
        if str(maison) == "1":
            m1.append(nom)
    
    if len(m1) >= 2:
        lines.append(f"- Stellium en maison I : {', '.join(m1)}")
    
    return "\n".join(lines) if lines else "Aucune configuration majeure détectée."

# ───────── Directives de genre ─────────
def _genre_directives(meta: dict) -> str:
    genre = (meta or {}).get("genre", "neutre")
    if genre == "femme":
        return ("- Prends en compte une réception lunaire/Vénus possiblement plus sensible.\n"
                "- Évite les injonctions dures ; privilégie l’accompagnement et la nuance.")
    if genre == "homme":
        return ("- Prends en compte un axe solaire/Mars possiblement plus saillant.\n"
                "- Évite les stéréotypes ; parle d’alignement et de responsabilité.")
    return "- Reste neutre, inclusif et respectueux des nuances individuelles."



# ───────── Entrée principale ─────────
def analyse_forces_defis(data_theme, meta=None) -> str:
    html_final = ""  # filet de sécurité
    print(">>> ENTER analyse_forces_defis")

    """
    Génère une analyse 1–2 pages, structurée :
    - Intro brève
    - Inventaire FORCES (bullet points)
    - Inventaire DÉFIS (bullet points)
    - Conclusion actionnable
    """
    meta = meta or {"tonalite": "tu", "genre": "neutre"}
    ctx = _build_contexte_global(data_theme)
    placements_str = ctx["placements_str"]
    axes_majeurs_str = ctx["axes_majeurs_str"]
    rag_snippets = ctx["rag_snippets"]

    # AJOUTE :
    try:
        sel = construire_selection_point_astral(data_theme) or {}
        ctx_global = (
            sel.get("contexte_global")
            or sel.get("axes_majeurs")
            or sel.get("resume_global")
            or ""
        )
        if not isinstance(ctx_global, str):
            ctx_global = ""
    except Exception:
        ctx_global = ""

    bloc_contexte = placements_str if isinstance(placements_str, str) else str(placements_str)
    if ctx_global.strip():
        bloc_contexte = f"{bloc_contexte}\n\n### Contexte global\n{ctx_global.strip()}"


    # Après avoir construit bloc_contexte (et éventuellement ajouté "### Contexte global")
    # >>> INJECTION DES CSV (FORCES / DÉFIS / ÉTAT PLANÈTES) <<<
    try:
        print(">>> DÉBUT TEST FD_INJECT")
        print(">>> data_theme keys:", data_theme.keys())
        print(">>> aspects:", data_theme.get("aspects") or data_theme.get("aspects_significatifs"))
        # Dans votre code, juste avant build_markdown_blocks()
        print(">>> Aspects dans le thème:", data_theme.get("aspects", [])[:3])  # montre 3 premiers
        priorities_md = build_unified_priorities(
            data_theme,
            min_score=3.0,   # Garde tout à partir de score 3
            limit=30         # Top 30 éléments
        )
        if priorities_md:
            bloc_contexte = f"{bloc_contexte}\n\n{priorities_md}"
    except Exception as e:
        print("[FD_INJECT] ignoré (non bloquant):", e)
    
    # === Bloc "thème entier" (identique à la route) ===
    bloc_theme_occ = _build_bloc_theme_occidental_depuis_selector(data_theme)

    if not placements_str or len(placements_str) < 40:
        raise ValueError("placements_str insuffisant pour générer l’analyse Forces & Défis.")

    # Matière première (règles locales ou fallback)
    if callable(_GENERER_FORCES_DEFIS):
        fd = _GENERER_FORCES_DEFIS(data_theme)  # type: ignore[misc]
    else:
        fd = _fallback_generer_forces_defis(data_theme)

    # 🔎 Ajout maisons (VIII, XII, IV, X…) si dispo, sans casser si absent
    try:
        fd_maisons = extraire_forces_defis_par_maisons(data_theme)
        if isinstance(fd_maisons, dict):
            fd["forces"] = (fd.get("forces") or []) + (fd_maisons.get("forces") or [])
            fd["defis"]  = (fd.get("defis")  or []) + (fd_maisons.get("defis")  or [])
    except Exception:
        pass

    forces_txt = "\n".join(fd.get("forces", [])) or "Aucune force marquante détectée."
    defis_txt  = "\n".join(fd.get("defis",  [])) or "Aucun défi majeur détecté."
    synthese   = fd.get("synthese_courte", "")

    genre_rules = _genre_directives(meta)

    bloc_placements_simple = f"""
- Ascendant : {data_theme['ascendant']['signe']}
- Soleil : {data_theme['planetes']['Soleil']['signe']} (Maison {data_theme['planetes']['Soleil']['maison']})
- Lune : {data_theme['planetes']['Lune']['signe']} (Maison {data_theme['planetes']['Lune']['maison']})
- Mercure : {data_theme['planetes']['Mercure']['signe']} (Maison {data_theme['planetes']['Mercure']['maison']})
- Vénus : {data_theme['planetes']['Vénus']['signe']} (Maison {data_theme['planetes']['Vénus']['maison']})
- Mars : {data_theme['planetes']['Mars']['signe']} (Maison {data_theme['planetes']['Mars']['maison']})
- Jupiter : {data_theme['planetes']['Jupiter']['signe']} (Maison {data_theme['planetes']['Jupiter']['maison']})
- Saturne : {data_theme['planetes']['Saturne']['signe']} (Maison {data_theme['planetes']['Saturne']['maison']})
- Uranus : {data_theme['planetes']['Uranus']['signe']} (Maison {data_theme['planetes']['Uranus']['maison']})
- Neptune : {data_theme['planetes']['Neptune']['signe']} (Maison {data_theme['planetes']['Neptune']['maison']})
- Pluton : {data_theme['planetes']['Pluton']['signe']} (Maison {data_theme['planetes']['Pluton']['maison']})
"""

# Bloc configurations (amas, stelliums)
    bloc_configurations = _construire_configurations(data_theme)


    prompt = f"""

Tu es une astrologue-psychologue experte (20+ ans), spécialisée en astrologie psychologique (Jung, Alice Bailey).

ANALYSE PAYANTE - Thème : {meta.get("prenom", "la personne")}
Objectif : Révéler les dynamiques profondes du thème via FORCES et DÉFIS concrets.

═══ CONTEXTE MINIMAL DU THÈME ═══

**Placements de base :**
{bloc_placements_simple}

**Configurations majeures :**
{bloc_configurations}

---

{bloc_contexte}

---

**CONSIGNES STRICTES POUR L'ANALYSE :**

1. ✅ Analyse UNIQUEMENT les éléments numérotés dans la section ci-dessus
2. ❌ NE PAS analyser d'autres aspects, même s'ils existent dans le thème
3. ✅ Traite-les TOUS sans exception (chaque élément doit apparaître dans ton analyse)
4. ✅ Respecte l'ordre d'importance (commence par les scores les plus élevés)
5. ❌ NE PAS mentionner Chiron, nœuds lunaires (sauf si listés), ou d'autres éléments non prioritaires

**Exemples de ce qu'il NE faut PAS faire :**
❌ "Mercure carré Rahu crée..." (si pas dans la liste des priorités)
❌ "On peut aussi noter que..." (seulement les éléments listés !)

═══ STRUCTURE DE SORTIE ═══

**Introduction** (1 paragraphe, 80-100 mots)
Accroche personnalisée basée sur les **Configurations majeures** (amas, stelliums, planètes angulaires) pour poser le décor du thème.

**## DÉFIS**
7 à 10 puces basées UNIQUEMENT sur les éléments marqués [DÉFI] ou [DEFIS] dans la liste ci-dessus
Format : - **Aspect/Placement précis** : Description (200 mots minimum)

**## FORCES**  
7 à 10 puces basées UNIQUEMENT sur les éléments marqués [FORCE] dans la liste ci-dessus
Format : - **Aspect/Placement précis** : Description (200 mots minimum)

**Conclusion** (1 paragraphe, 80-100 mots)
Synthèse intégrative, perspective d'évolution.

═══ STYLE D'ÉCRITURE ═══

✓ Ton : Lucide, direct, bienveillant mais sans complaisance
✓ Profondeur : Psychologie jungienne, symbolisme archétypal
✓ Concret : Exemples de vie, situations tangibles
✓ Humour : Subtil, naît de l'observation juste (pas de blagues forcées)
✓ Empathie : Reconnaître la difficulté sans dramatiser

✗ À ÉVITER :
- Phrases vides type "tu es unique", "le cosmos t'appelle"
- Images farfelues gratuites (pizza cosmique, GPS karmique...)
- Psychologie de comptoir
- Prédictions, jugements moraux
- Ton professoral ou condescendant

Chaque phrase doit servir la compréhension de soi. Pas de remplissage.

Métadonnées :
- Tonalité: {meta.get("tonalite","tu")}
- Genre: {meta.get("genre","neutre")}

"""
    
     # 🛠 Voir le prompt entier dans la console
    print("\n=== PROMPT FORCES & DEFIS ===\n")
    print(prompt)
    print("\n=== FIN PROMPT ===\n")

    # Toujours initialiser
    texte = ""
    html_core = ""
    html_final = ""

    try:
        # 1) Appel LLM
        resultat_llm = interroger_llm(prompt)

        # 2) Normalisation du retour (dict ou str)
        if isinstance(resultat_llm, dict):
            texte = (
                resultat_llm.get("content")
                or resultat_llm.get("text")
                or resultat_llm.get("message")
                or resultat_llm.get("response")
                or str(resultat_llm)
            )
        else:
            texte = str(resultat_llm)

        # 3) Preview debug
        print("\n" + "="*60)
        print("TEXTE EXTRAIT DU LLM (1000 premiers caractères):")
        print("="*60)
        print((texte or "")[:1000])
        print("="*60 + "\n")

        # 4) Markdown -> HTML (avec filet de sécurité)
        try:
            html_core = md_light_to_html(texte or "")
        except Exception as conv_err:
            print(f"[FD] Erreur conversion md_light_to_html: {conv_err}")
            # fallback : on affiche le texte brut
            html_core = f"<pre style='white-space:pre-wrap'>{(texte or '')}</pre>"

    except Exception as gen_err:
        # Fallback total : au moins afficher le prompt pour diagnostiquer
        print("[FD] ERREUR pendant génération LLM/HTML:", gen_err)
        html_core = (
            "<div class='error' style='border:1px solid #e00;padding:8px;margin:8px 0'>"
            "<strong>Erreur de génération</strong> — affichage du prompt pour diagnostic :</div>"
            f"<pre style='white-space:pre-wrap'>{prompt}</pre>"
        )

    # 5) Ajout du disclaimer et assignation AVANT le print de sortie
    html_final = f"{html_core}\n{DISCLAIMER_FORCES_DEFIS_HTML}"

    # 6) Debug sortie
    print(">>> EXIT analyse_forces_defis (len html):", len(html_final))

    return html_final