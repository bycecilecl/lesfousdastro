# orchestration/point_astral_blocs.py - VERSION BLOCS (sans affinage)

from typing import List, Dict
import re
from typing import Optional


from blocs.bloc_1 import generer_bloc_1
from blocs.bloc_2 import generer_bloc_2
from blocs.bloc_3 import generer_bloc_3
from blocs.bloc_5 import generer_bloc_5

# ⛔️ supprimé: from blocs.bloc_final_affinage import generer_bloc_final_affine

from utils.selection_donnees import (
    extraire_axes_majeurs_payload,
    aspects_maitre_ascendant,
    construire_axes_conj_maitre_ascendant,
    construire_axes_majeurs_global,
    axes_payload_items,
    axes_payload_to_str,
    filtrer_items_pour_bloc3,
)

from utils.rag_utils_optimized import (
    selectionner_snippets_par_topic,
    digest_pour_bloc,
)

TOPIC_PATTERNS = [
    ("Ascendant",   re.compile(r"\basc(endant)?\b", re.I)),
    ("Maison I",    re.compile(r"\b(maison\s*1|maison\s*i)\b", re.I)),
    ("MaîtreAsc",   re.compile(r"\b(ma[iî]tre.*asc|r[eé]genteur.*asc)\b", re.I)),
    ("Soleil",      re.compile(r"\bsoleil\b", re.I)),
    ("Lune",        re.compile(r"\blune\b", re.I)),
    ("Vénus",       re.compile(r"\bv[eé]nus\b", re.I)),
    ("Mars",        re.compile(r"\bmars\b", re.I)),
    ("Jupiter",     re.compile(r"\bjupiter\b", re.I)),
    ("Saturne",     re.compile(r"\bsaturne\b", re.I)),
    ("Uranus",      re.compile(r"\buranus\b", re.I)),
    ("Neptune",     re.compile(r"\bneptune\b", re.I)),
    ("Pluton",      re.compile(r"\bpluton\b", re.I)),
    ("Amas",        re.compile(r"\bamas\b", re.I)),
    ("Angles",      re.compile(r"\b(angle|asc|mc|fc|dc)\b", re.I)),
    ("Dominantes",  re.compile(r"\bdominante(s)?\b", re.I)),
    ("Nakshatra",   re.compile(r"\bnakshatra\b", re.I)),
]

SEPARATEUR = "\n\n---\n\n"

# --- Bloc 3 : helpers d'exclusion ---
_FC_PATTERNS = (" FC", " Fond du Ciel", " Imum Coeli")

ALLOW_AMAS_NEUTRES = True


def est_exclu_bloc3(item: str) -> bool:
    """
    Exclut du Bloc 3 tout ce qui a déjà été traité en amont :
    - lignes contenant Ascendant, Soleil, Lune
    - Conjonctions au FC (mais pas 'Maison IV très habitée')
    """
    t = item.lower()
    if "ascendant" in t or "soleil" in t:
        return True
    # exclure la Lune … sauf Lune Noire
    if "lune" in t and "lune noire" not in t:
        return True
    if "conjonction" in t and any(pat.lower() in t for pat in _FC_PATTERNS):
        return True
    return False

def neutraliser_amas(item: str) -> Optional[str]:
    """
    Si 'item' est un amas qui mentionne Lune/Soleil,
    on les retire de la liste pour éviter les redites.
    Retourne la ligne réécrite, ou None si rien d'utile ne reste.
    """
    t = item.strip()
    if "amas" not in t.lower():
        return None

    # On essaye d'identifier la parenthèse "(...)" listant les planètes
    # et de retirer Lune/Soleil de cette liste.
    import re
    m = re.search(r"\(([^)]+)\)", t)
    if not m:
        # pas de parenthèses -> on laisse tel quel (ou None si tu préfères)
        return t

    contenu = m.group(1)
    # split naïf par virgule
    noms = [x.strip() for x in contenu.split(",")]
    # on retire Lune / Soleil (insensible à la casse)
    filtres = [n for n in noms if n.lower() not in ("lune", "soleil")]

    if not filtres:
        # il ne restait que Lune/Soleil -> on ne garde pas l'amas
        return None

    # réécriture
    contenu_neutre = ", ".join(filtres)
    # exemple: "Amas en Scorpion (Lune, Mercure, Mars)" -> "Amas en Scorpion (planètes : Mercure, Mars)"
    t_neutre = re.sub(r"\([^)]+\)", f"(planètes : {contenu_neutre})", t)
    return t_neutre

def _build_faits_autorises(data_theme: dict, placements_str: str) -> str:
    occ = (data_theme.get("planetes") 
           or data_theme.get("placements_occidentaux") 
           or data_theme.get("resultats_tropical") 
           or {})
    lignes = []
    for nom, d in (occ or {}).items():
        try:
            s = d.get("signe")
            m = d.get("maison")
            if s: lignes.append(f"{nom} en {s}")
            if m: lignes.append(f"{nom} en maison {m}")
        except Exception:
            pass
    angles_deg = data_theme.get("angles_deg") or {}
    for angle in ("Ascendant","MC","Descendant","FC"):
        if angle in angles_deg:
            lignes.append(f"{angle} défini")
    for a in (data_theme.get("aspects") or []):
        p1 = a.get("p1") or a.get("planete1")
        p2 = a.get("p2") or a.get("planete2")
        asp = (a.get("aspect") or "").capitalize()
        if asp in ("Conjonction","Opposition","Carré"):
            lignes.append(f"{p1} {asp} {p2}")
    pf = (data_theme.get("points_forts_compacts") 
          or data_theme.get("points_forts") 
          or "")
    if isinstance(pf, str) and pf.strip():
        for l in pf.splitlines():
            l = l.strip(" -•\t")
            if l:
                lignes.append(l)
    seen, out = set(), []
    for l in lignes:
        k = l.lower()
        if k not in seen:
            seen.add(k); out.append(l)
    return "\n".join(out)

def rag_string_to_snippets(rag_text: str) -> List[Dict]:
    if not rag_text:
        return []
    chunks = re.split(r"\n{2,}|[•\-]\s+|;\s+(?=[A-ZÉÈÀ])", rag_text)
    out: List[Dict] = []
    for raw in chunks:
        t = (raw or "").strip()
        if len(t) < 40:
            continue
        topic = "general"
        for name, pat in TOPIC_PATTERNS:
            if pat.search(t):
                topic = name; break
        out.append({"texte": t, "source": "rag", "score": 0.5, "topic": topic})
    return out

def _mini_apercu_bloc_1(texte: str, max_chars: int = 600) -> str:
    if not texte:
        return ""
    cut = texte[:max_chars]
    last_dot = cut.rfind(".")
    if last_dot > 100:
        cut = cut[:last_dot+1]
    return cut.strip()

def _assert_placements_ok(contexte: dict):
    p = (contexte.get("placements_str") or contexte.get("placements") or "").strip()
    if len(p) < 40 or "Ascendant" not in p:
        raise ValueError("PLACEMENTS_VIDES_OU_INCOMPLETS")

def nettoyer_bloc(contenu_bloc: str) -> str:
    return re.sub(r'^##\s*Bloc\s*\d+\s*[–-].*?\n', '', (contenu_bloc or "").strip(), flags=re.MULTILINE).strip()

def _normalize_maitre_nom(maitre):
    if isinstance(maitre, dict):
        nom = maitre.get("planete") or maitre.get("nom") or ""
    else:
        nom = str(maitre or "").strip()
        if nom:
            nom = nom.split()[0]
    return nom.capitalize()

# ⛔️ supprimé: toute la partie “Affinage final” (fonction produire_analyse_finale)

def generer_point_astral_blocs(contexte: dict) -> str:
    """
    Génère le flash astral par blocs et retourne l’assemblage brut,
    sans aucune étape d’affinage.
    """
    print("🔵 ORCH: clés dispo :", list(contexte.keys()))
    print("🔵 ORCH: len(placements_str) =", len(contexte.get("placements_str","")))


    # 🔑 RÉCUPÉRER LE THEME ICI
    theme = contexte.get("data_theme") or contexte.get("theme")
    if not theme:
        raise ValueError("ORCH: 'theme' manquant (ni 'data_theme' ni 'theme' dans le contexte)")

    # Assurer que placements_str et aspects sont présents dans le contexte
    from utils.formatage import formater_positions_planetes
    if not contexte.get("placements_str"):
        try:
            contexte["placements_str"] = formater_positions_planetes(theme["planetes"])
            print("✅ ORCH: placements_str construit depuis theme")
        except Exception as e:
            print("⚠️ ORCH: impossible de construire placements_str:", e)

    # garder theme dispo partout
    contexte["theme"] = theme

    ps = contexte.get("placements_str", "")
    if "### Spécificités védiques utiles" in ps:
        bloc = ps.split("### Spécificités védiques utiles", 1)[1].split("###", 1)[0]
        apercu_vedique = "\n".join(bloc.splitlines()[:12])
        print("🔵 ORCH: extrait védique transmis:\n", apercu_vedique)
    else:
        print("🔵 ORCH: pas de bloc védique détecté dans placements_str")

    print("🎬 ORCH: Début génération 4 blocs...")

    _assert_placements_ok(contexte)

    rag_par_topic = contexte.get("rag_par_topic")
    if not rag_par_topic:
        rag_list = contexte.get("rag_list")
        if isinstance(rag_list, list):
            print(f"🔧 ORCH: RAG en liste détecté ({len(rag_list)} items)")
            rag_par_topic = selectionner_snippets_par_topic(
                rag_list, top_k_par_topic=6, min_score=0.35, max_chars_par_snippet=350
            )
        else:
            rag_text = contexte.get("rag_snippets") or contexte.get("corpus_rag") or ""
            if isinstance(rag_text, str) and rag_text.strip():
                print(f"🔧 ORCH: RAG texte détecté ({len(rag_text)} chars) → conversion en snippets")
                snippets = rag_string_to_snippets(rag_text)
                print(f"   → {len(snippets)} snippets construits")
                rag_par_topic = selectionner_snippets_par_topic(
                    snippets, top_k_par_topic=6, min_score=0.35, max_chars_par_snippet=350
                )
            else:
                rag_par_topic = {}

    rag_bloc1 = digest_pour_bloc(rag_par_topic, ["Ascendant","Maison I","MaîtreAsc","Soleil"], max_chars=1500) if rag_par_topic else ""
    rag_bloc2 = digest_pour_bloc(rag_par_topic, ["Lune","Nakshatra"], max_chars=1500) if rag_par_topic else ""
    rag_bloc3 = digest_pour_bloc(rag_par_topic, ["Amas","Conjonctions","Dominantes","Angles"], max_chars=1500) if rag_par_topic else ""
    rag_bloc5 = digest_pour_bloc(rag_par_topic, ["Dominantes","Ascendant","Soleil","Lune"], max_chars=1500) if rag_par_topic else ""

    print("🔎 ORCH: RAG digests chars:", len(rag_bloc1), len(rag_bloc2), len(rag_bloc3), len(rag_bloc5))

    faits_aut = _build_faits_autorises(contexte.get("data_theme", {}), contexte.get("placements_str", ""))
    contexte["faits_autorises"] = faits_aut
    print("📋 ORCH: faits_autorises construits (chars):", len(faits_aut))

    RULER_MODERNE = {
        "Bélier":"Mars","Taureau":"Vénus","Gémeaux":"Mercure","Cancer":"Lune",
        "Lion":"Soleil","Vierge":"Mercure","Balance":"Vénus","Scorpion":"Pluton",
        "Sagittaire":"Jupiter","Capricorne":"Saturne","Verseau":"Uranus","Poissons":"Neptune",
    }
    ASC_SIGN_PAT = re.compile(r"Ascendant\s*:\s*[\d\.,]+\s*°\s*en\s+([A-Za-zÉÈÊÙÂÔÎäëïöüéèêàç\-]+)", re.I)

    if not contexte.get("maitre_ascendant"):
        m = ASC_SIGN_PAT.search(ps) or re.search(r"Ascendant\s*:\s*(\w+)", ps)
        if m:
            signe = m.group(1).capitalize()
            maitre = RULER_MODERNE.get(signe)
            if maitre:
                contexte["maitre_ascendant"] = maitre
                print(f"Maître déduit: {signe} -> {maitre}")

    maitre_raw = contexte.get("maitre_ascendant")
    maitre_nom = _normalize_maitre_nom(maitre_raw)
    print("🐛 DEBUG/ORCH — maitre_ascendant (raw)  :", maitre_raw)
    print("🐛 DEBUG/ORCH — maitre_ascendant (norm) :", maitre_nom)

    aspects_dbg = contexte.get("aspects", [])
    print(f"🐛 DEBUG/ORCH — nb aspects : {len(aspects_dbg)}")
    for a in aspects_dbg[:5]:
        print("   • sample aspect:", a)

    try:
        maitre_asc = contexte.get("maitre_ascendant")
        aspects = contexte.get("aspects", [])
        contexte["conj_maitre_asc"] = aspects_maitre_ascendant(maitre_asc, aspects)
        print(f"🔎 ORCH: Conjonctions maître Ascendant trouvées: {contexte['conj_maitre_asc']}")
    except Exception as e:
        print(f"⚠️ ORCH: Erreur détection conjonctions maître Ascendant: {e}")
        contexte["conj_maitre_asc"] = []

    if contexte.get("conj_maitre_asc"):
        try:
            contexte["conj_maitre_asc_str"] = "\n".join(
                f"- {str(a.get('p1'))} conjoint {str(a.get('p2'))} (orbe {float(str(a.get('orbe')).replace(',', '.')):.1f}°)"
                for a in contexte["conj_maitre_asc"]
            )
        except Exception:
            contexte["conj_maitre_asc_str"] = ""
    else:
        contexte["conj_maitre_asc_str"] = ""

    try:
        maitre_asc = contexte.get("maitre_ascendant")
        conj_list = contexte.get("conj_maitre_asc", [])
        axes_existants = contexte.get("axes_majeurs_list", [])
        axes_conj = construire_axes_conj_maitre_ascendant(maitre_asc, conj_list, max_items=3)
        axes_tous = (axes_existants or []) + axes_conj
        contexte["axes_majeurs_list"] = axes_tous

        try:
            from utils.selection_donnees import formater_axes_majeurs
            contexte["axes_majeurs_str"] = formater_axes_majeurs(axes_tous)
        except Exception:
            contexte["axes_majeurs_str"] = "\n".join(f"- {ax.get('titre')}: {ax.get('resume')}" for ax in axes_tous)

        print(f"🔎 ORCH: Axes majeurs MAJ (maître Asc): +{len(axes_conj)} entrée(s)")
    except Exception as e:
        print(f"⚠️ ORCH: Erreur intégration axes maître Asc: {e}")

    axes_global = construire_axes_majeurs_global(contexte)
    contexte["axes_majeurs_global"] = axes_global
    print("🔗 ORCH: axes_majeurs_global length:", len(axes_global))

    contexte_base = dict(contexte)


    # ➜ construire placements_str comme dans l'analyse gratuite
    placements_str = contexte["placements_str"]

    ctx_b1 = {
        **contexte_base,
        "theme": theme,                     # 👈 INDISPENSABLE pour build_resume_bloc1()
        "placements_str": placements_str,   # 👈 base factuelle du prompt (comme la gratuite)
        "rag_snippets": digest_pour_bloc(
            rag_par_topic,
            ["Ascendant", "Maison I", "MaîtreAsc", "Soleil"],
            max_chars=1500
        ) if rag_par_topic else "",
        "faits_autorises": contexte_base.get("faits_autorises", ""),
        # (optionnel mais utile)
        "genre": contexte_base.get("genre", "non précisé"),
        "tonalite": "tu",
    }

    # traçage utile
    print("🔎 ORCH: theme ok ?", bool(ctx_b1.get("theme")))
    print("🔎 ORCH: len(placements_str) =", len(placements_str))

    b1 = generer_bloc_1(ctx_b1)
    print("✅ Bloc 1 généré (len):", len(b1))
    apercu_b1 = _mini_apercu_bloc_1(nettoyer_bloc(b1))

    print("🔧 Génération Bloc 2...")

    # 1) S'assurer que placements_str est dispo (sinon on le reconstruit depuis theme)
    placements_str_b2 = contexte_base.get("placements_str", "")
    if (not placements_str_b2 or len(placements_str_b2) < 50) and theme.get("planetes"):
        try:
            from utils.formatage import formater_positions_planetes
            placements_str_b2 = formater_positions_planetes(theme["planetes"])
            print("ℹ️ ORCH: Bloc 2 — placements_str reconstruit depuis theme")
        except Exception as e:
            print("⚠️ ORCH: Bloc 2 — reconstruction placements_str impossible:", e)
            placements_str_b2 = contexte_base.get("placements_str", "") or ""

    # 2) S'assurer que les aspects sont bien présents (certains helpers en ont besoin)
    if not contexte_base.get("aspects") and theme.get("aspects"):
        contexte_base["aspects"] = theme["aspects"]
        print(f"✅ ORCH: Bloc 2 — aspects injectés ({len(theme['aspects'])})")

    # 3) RAG ciblé pour le monde intérieur + pôle père/autorité
    rag_topics_b2 = ["Lune", "Nakshatra", "Maison IV", "IC", "Soleil", "Saturne", "Maison X", "MC"]
    rag_b2 = digest_pour_bloc(rag_par_topic, rag_topics_b2, max_chars=1500) if rag_par_topic else ""

    # === ANGLES → PROMPTS (pour Bloc 2 / IC) =======================
    from utils.selection_donnees import _get_points_forts_str, construire_conjonctions_angles_pour_prompts

    # 1) S'assurer que theme possède bien planetes_deg / angles_deg (side-effects)
    try:
        _ = _get_points_forts_str(theme)  # remplit theme["planetes_deg"] et theme["angles_deg"]
    except Exception as e:
        print("⚠️ ORCH: _get_points_forts_str(theme) a échoué (deg angles):", e)

    # 2) Construire les blocs texte par angle et injecter dans le contexte
    try:
        angles_blocks_b2 = construire_conjonctions_angles_pour_prompts(theme, orb_max=5.0)
        contexte_base["conjonctions_ic"]  = (angles_blocks_b2.get("conjonctions_ic")  or "").strip()
        contexte_base["conjonctions_mc"]  = (angles_blocks_b2.get("conjonctions_mc")  or "").strip()
        # optionnel :
        contexte_base["conjonctions_asc"] = (angles_blocks_b2.get("conjonctions_asc") or "").strip()
        contexte_base["conjonctions_dsc"] = (angles_blocks_b2.get("conjonctions_dsc") or "").strip()

        # debug lisible
        print("=== DEBUG B2 <conjonctions_ic> ===")
        print(contexte_base["conjonctions_ic"] or "—")
        print("=== DEBUG B2 <conjonctions_mc> ===")
        print(contexte_base["conjonctions_mc"] or "—")
    except Exception as e:
        print("⚠️ ORCH: construction conjonctions d’angles (B2) impossible:", e)

    # 4) Construire le contexte Bloc 2 (⚠️ 'theme' et 'placements_str' sont indispensables)
    ctx_b2 = {
        **contexte_base,
        "theme": theme,                      # requis par build_resume_bloc2()
        "placements_str": placements_str_b2, # base factuelle
        "rag_snippets": rag_b2,
        "genre": contexte_base.get("genre", "femme"),
        "tonalite": contexte_base.get("tonalite", "tu"),
    }

    # 5) Générer Bloc 2
    b2 = generer_bloc_2(ctx_b2)
    print("✅ Bloc 2 généré (len):", len(b2))
    apercu_b2 = _mini_apercu_bloc_1(nettoyer_bloc(b2))

    # 6) Préparer les axes majeurs pour le bloc suivant

    # ⬇️ 1) Récupérer et injecter les Points forts AVANT d’extraire le payload
    from utils.selection_donnees import _get_points_forts_str
    try:
        pf_md = _get_points_forts_str(theme)
        if pf_md and pf_md.strip():
            contexte["points_forts"] = pf_md
            print("✅ ORCH: points_forts injectés (chars)", len(pf_md))
        else:
            print("ℹ️ ORCH: pas de points_forts MD disponible")
    except Exception as e:
        print("⚠️ ORCH: _get_points_forts_str(theme) a échoué:", e)

    # ⬇️ 2) Maintenant on construit le payload puis on filtre pour le Bloc 3
    axes_payload = extraire_axes_majeurs_payload(contexte)  # ← APRES injection
    axes_all_items = axes_payload_items(axes_payload)


    
    # print("=== DEBUG PAYLOAD COMPLET ===")
    # for section, items in axes_payload.items():
    #     print(f"Section '{section}': {len(items)} items")
    #     for item in items:
    #         print(f"  - {item}")

    # print(f"\n=== ITEMS AVANT FILTRAGE ({len(axes_all_items)}) ===")
    
    # for i, item in enumerate(axes_all_items):
    #     print(f"{i}: {item}")
    
    #axes_items = filtrer_items_pour_bloc3(axes_all_items) 
    # axes_str   = "\n".join(f"- {it}" for it in axes_items)
    # contexte["axes_items"]         = axes_items
    # contexte["axes_majeurs_input"] = axes_str

    # # (optionnel) filet de sécurité : s'il n'y a aucun "maison angulaire", on en force un
    # if not any("maison angulaire" in it.lower() for it in axes_items):
    #     for it in axes_all_items:
    #         if "maison angulaire" in it.lower():
    #             axes_items.insert(0, it)
    #             print("🛟 ORCH: 'maison angulaire' forcée dans axes_items:", it)
    #             break

    # axes_str = "\n".join(f"- {it}" for it in axes_items)
    # contexte["axes_items"] = axes_items
    # contexte["axes_majeurs_input"] = axes_str

    # 2) Filtrage générique demandé
    axes_items = [it for it in axes_all_items if not est_exclu_bloc3(it)]

    # (Option) sauver un amas neutre si on en a exclu un à cause de Lune/Soleil
    if ALLOW_AMAS_NEUTRES:
        for it in axes_all_items:
            ti = it.lower()
            # on cible les amas qui auraient été exclus à cause de Lune/Soleil
            if "amas" in ti and ("lune" in ti or "soleil" in ti):
                # si la version neutre existe et qu'elle n'est pas déjà présente, on l'ajoute en queue
                it_neutre = neutraliser_amas(it)
                if it_neutre and it_neutre.lower() not in [x.lower() for x in axes_items]:
                    axes_items.append(it_neutre)
                # on peut s'arrêter au 1er amas trouvé (ou continuer si tu veux en insérer plusieurs)
                break


    # 3) (optionnel) filet de sécu 'maison angulaire' : on garde ta logique existante
    if not any("maison angulaire" in it.lower() for it in axes_items):
        for it in axes_all_items:
            if "maison angulaire" in it.lower():
                axes_items.insert(0, it)
                print("🛟 ORCH: 'maison angulaire' forcée dans axes_items:", it)
                break

    # 4) Mise en contexte (inchangé)
    axes_str = "\n".join(f"- {it}" for it in axes_items)
    contexte["axes_items"] = axes_items
    contexte["axes_majeurs_input"] = axes_str

    print("🔧 Génération Bloc 3...")
    ctx_b3 = {
        **contexte_base,
        "rag_snippets": digest_pour_bloc(
            rag_par_topic, ["Amas","Conjonctions","Dominantes","Angles"], max_chars=1500
        ) if rag_par_topic else "",
        "axes_items": axes_items,
        "axes_majeurs_input": axes_str,
        "faits_autorises": contexte_base.get("faits_autorises", ""),
        "apercu_bloc_2": apercu_b2,
    }
    b3 = generer_bloc_3(ctx_b3)

    print("🔧 Génération Bloc 5...")
    ctx_b5 = {
        **contexte_base,
        "rag_snippets": digest_pour_bloc(rag_par_topic, ["Dominantes","Ascendant","Soleil","Lune"], max_chars=1500) if rag_par_topic else "",
    }
    b5 = generer_bloc_5(ctx_b5)

    print("🧹 Nettoyage des blocs...")
    b1_clean = nettoyer_bloc(b1)
    b2_clean = nettoyer_bloc(b2)
    b3_clean = nettoyer_bloc(b3)
    b5_clean = nettoyer_bloc(b5)

    SEPARATEUR = "\n\n---\n\n"
    assemblage_brut = SEPARATEUR.join([
        "## Personnalité & Identité\n" + b1_clean,
        "## Lune & Monde intérieur\n" + b2_clean,
        "## Les Axes Majeurs\n" + b3_clean,
        "## Synthèse\n" + b5_clean,
    ]).strip()


    
    # ✅ Pas d’affinage : on retourne directement l’assemblage des blocs
    return assemblage_brut