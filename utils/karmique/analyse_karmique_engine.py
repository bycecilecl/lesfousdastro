# utils/analyse_karmique_engine.py

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from utils.karmique.karmique_context import build_global_context, build_karmic_context_for_llm
from utils.karmique.chapitres.chiron import build_block_chiron
from utils.karmique.chapitres.resume_karmique_global import (
    build_block_resume_karmique_global,
)
from utils.karmique.chapitres.potentiels_karmiques import (
    build_block_potentiels_karmiques,
)
from utils.karmique.tensions_normalisees import generer_tensions_normalisees


logger = logging.getLogger(__name__)


class KarmicEngine:
    """
    Chef d'orchestre "karmique" :
    - reçoit le theme (calcul_theme)
    - reçoit le score (calculer_poids_karmique)
    - construit une liste de blocs UI/LLM-ready
    """

    def __init__(self, theme_data: Dict[str, Any], score_result: Dict[str, Any], global_ctx: Optional[Dict[str, Any]] = None):
        self.theme = theme_data or {}
        self.score = score_result or {}

        # 1) si on nous donne un global_ctx, on le prend
        # 2) sinon, on le construit
        self.global_ctx = global_ctx or build_global_context(self.theme, self.score)

        # Bonus : on enrichit avec un contexte karmique "prêt à injecter" dans les prompts LLM
        if "karmic_context" not in self.global_ctx:
            self.global_ctx["karmic_context"] = build_karmic_context_for_llm(
                self.theme,
                self.score,
                max_lines=20
            )

        # ✅ Nouveau : contexte narratif pour éviter les répétitions
        self.global_ctx.setdefault("themes_deja_traites", [])
        self.global_ctx.setdefault("axe_karmique_central", "")

        self.blocks: List[Dict[str, Any]] = []

        self.planetes = self.theme.get("planetes") or {}
        self.aspects = self.theme.get("aspects") or []
        self.interceptions = self.theme.get("interceptions") or {}

    def _compute_main_axis(self) -> str:
        breakdown = self.score.get("breakdown", {}) or {}
        if not breakdown:
            return ""

        main_key = max(breakdown.items(), key=lambda x: x[1])[0]

        mapping = {
            "houses_karmic": "poids des mémoires anciennes, repli intérieur, transformation profonde",
            "nodes": "tiraillement entre les automatismes du passé et l’évolution demandée",
            "moon_karmic": "mémoire émotionnelle lourde, hypersensibilité, insécurité intérieure",
            "retrogrades": "blocages intériorisés, énergie retenue, fonctionnement en boucle interne",
            "interceptions": "énergie bloquée, difficulté d’expression, zones psychiques sous pression",
            "anaretic_29": "pression de fin de cycle, urgence intérieure, difficulté à lâcher",
            "amas_signes": "concentration excessive d’énergie sur une même zone psychique",
            "saturn_pluto": "pression, contrôle, dureté intérieure, résistance au changement",
        }

        return mapping.get(main_key, "")

    def _norm_aspect_name(self, x: str) -> str:
        if not x:
            return ""
        x = str(x).strip()
        low = x.lower()
        if low in ("carre", "carré"):
            return "Carré"
        if low == "carre":
            return "Carré"
        if low == "trigone":
            return "Trigone"
        if low == "sextile":
            return "Sextile"
        if low == "opposition":
            return "Opposition"
        if low == "conjonction":
            return "Conjonction"
        return x
    



    # ----------------------------
    # Public
    # ----------------------------
    def run(self) -> List[Dict[str, Any]]:
        logger.debug("STARTING KARMIC ENGINE RUN")
        self.blocks = []

        # ✅ Axe central calculé une seule fois
        self.global_ctx["axe_karmique_central"] = self._compute_main_axis()
        
        self._add_header_block()

        # ✅ D'abord ce qui nourrit l'intro
        self._add_sensitive_points_block()
        #self._add_elements_block()

        # ✅ Ensuite l'intro (qui peut lire ces infos)
        self._add_intro_karmique_block()
        self._add_luminaires_block()
        self._add_nodes_block()
        self._add_maison_12_block()
        self._add_maison_8_block()
        self._add_maison_4_block()
        self._add_saturne_pluton_block()
        self._add_retrogrades_block()
        self._add_lune_noire_block()
        self._add_axe_portes_block()
        self._add_chiron_block()
        self._add_interceptions_block()
        self._add_part_fortune_block()
        self._add_resume_karmique_global_block()
        self._add_synthese_karmique_block()
        self._add_potentiels_karmiques_block()


        # extensible :
        # self._add_lilith_chiron_pof_block()

        logger.debug("META KEYS: %s", list((self.score.get("meta") or {}).keys()))

        for b in self.blocks:
            logger.debug(
                "BLOCK GENERATED | id=%s | title=%s",
                b.get("id"),
                b.get("title")
            )

        logger.debug("KARMIC ENGINE FINISHED | total_blocks=%s", len(self.blocks))

        return self.blocks

    def _add_header_block(self):
        block = {
            "id": "header",
            "title": "Analyse karmique",
            "content": ""
        }
        self.blocks.append(block)

    def _add_intro_karmique_block(self):
        meta = self.score.get("meta", {}) or {}

        # récupérer cuspides Asc/Soleil depuis le bloc sensitive_points
        sensitive = next((b for b in self.blocks if b.get("id") == "sensitive_points"), {}) or {}
        cuspides = (sensitive.get("data", {}) or {}).get("cuspides", []) or []
        cuspides = [c for c in cuspides if c.get("name") in ("Ascendant", "Soleil")]

        vip = (sensitive.get("data", {}) or {}).get("vip", {}) or {}
        points = (sensitive.get("data", {}) or {}).get("points", []) or []

        points_29 = []

        # garder Asc / Soleil en priorité
        for k in ("ascendant_29", "soleil_29"):
            if vip.get(k):
                points_29.append(vip[k])

        # ajouter les autres (Mars etc)
        for p in points:
            if isinstance(p, dict) and p.get("name") not in ("Ascendant", "Soleil"):
                points_29.append(p)

        self.blocks.append({
            "id": "intro_karmique",
            "title": "Introduction karmique",
            "data": {
                "score_total": self.score.get("total"),
                "score_label": self.score.get("label"),
                "dominant_elements": meta.get("dominant_elements") or [],

                "cuspides": cuspides,  # Asc/Soleil seulement
                "points_29": points_29,  # ✅ AJOUT ICI

                "nn_sign": meta.get("nn_sign"),
                "nn_house": meta.get("nn_house"),
                "ns_sign": meta.get("ns_sign"),
                "ns_house": meta.get("ns_house"),

                # contexte global minimal (pas tout le thème brut)
                "theme_context": {
                    "asc": (self.planetes.get("Ascendant") or {}).get("signe"),
                    "sun": (self.planetes.get("Soleil") or {}).get("signe"),
                    "moon": (self.planetes.get("Lune") or {}).get("signe"),
                    "dominant_elements": meta.get("dominant_elements") or [],
                }
            },
            "content": ""  # rempli ensuite
        }) 

    def _add_elements_block(self):
        """
        Calcule l'élément dominant (et éventuelle double dominante)
        en comptant 1 point par planète/angle dans un signe.
        Puis départage : luminaires -> personnelles étendues -> double dominante.
        """
        # 1) mapping signe -> élément
        sign_to_element = {
            "Bélier": "Feu", "Lion": "Feu", "Sagittaire": "Feu",
            "Taureau": "Terre", "Vierge": "Terre", "Capricorne": "Terre",
            "Gémeaux": "Air", "Balance": "Air", "Verseau": "Air",
            "Cancer": "Eau", "Scorpion": "Eau", "Poissons": "Eau",
        }

        ELEMENTS = ["Feu", "Terre", "Air", "Eau"]
        elements_count = {e: 0 for e in ELEMENTS}
        elements_lum = {e: 0 for e in ELEMENTS}
        elements_pers = {e: 0 for e in ELEMENTS}

        PERSONAL_EXTENDED = {"Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne"}
        LUMINAIRES = {"Soleil", "Lune"}

        # 2) candidats : planètes + angles (pas astéroïdes/points fictifs)
        candidates = ["Ascendant", "MC", "Soleil", "Lune", "Mercure", "Vénus", "Mars",
                    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"]

        for p in candidates:
            info = self.planetes.get(p)
            if not isinstance(info, dict):
                continue

            signe = info.get("signe")
            if not signe:
                continue

            el = sign_to_element.get(signe)
            if not el:
                continue

            elements_count[el] += 1

            if p in LUMINAIRES:
                elements_lum[el] += 1

            if p in PERSONAL_EXTENDED:
                elements_pers[el] += 1

        # 3) élément(s) dominant(s) bruts
        max_count = max(elements_count.values()) if elements_count else 0
        dominant = [e for e, v in elements_count.items() if v == max_count and v > 0]

        # 4) départage : luminaires
        if len(dominant) > 1:
            max_lum = max(elements_lum[e] for e in dominant)
            dominant = [e for e in dominant if elements_lum[e] == max_lum]

        # 5) départage : personnelles étendues
        if len(dominant) > 1:
            max_pers = max(elements_pers[e] for e in dominant)
            dominant = [e for e in dominant if elements_pers[e] == max_pers]

        # 6) si encore multiple => double dominante assumée
        dominant = sorted(dominant, key=lambda x: ELEMENTS.index(x))

        # si aucun élément (cas bizarre) -> pas de bloc
        if not dominant:
            return

        # rendre dispo pour le header / résumé
        self.score.setdefault("meta", {})
        self.score["meta"]["dominant_elements"] = dominant
        self.blocks.append({
            "id": "elements",
            "title": "Éléments karmiques : l’énergie globale du thème",
            "data": {
                "elements_count": elements_count,
                "elements_luminaries": elements_lum,
                "elements_personal_extended": elements_pers,
                "dominant_elements": dominant,
            },
            "content": ""
        })
    
    def _add_luminaires_block(self):
        from utils.karmique.chapitres.luminaires_karmiques import build_block_luminaires_karmiques

        block = build_block_luminaires_karmiques(self.theme, self.score, global_ctx=self.global_ctx)
        if block:
            self.blocks.append(block)


    def _add_nodes_block(self):
        from utils.karmique.chapitres.noeuds_lunaires import build_block_lunar_nodes
        
        block = build_block_lunar_nodes(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_saturne_pluton_block(self):
        from utils.karmique.chapitres.saturne_pluton import build_block_saturne_pluton

        block = build_block_saturne_pluton(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_part_fortune_block(self):
        from utils.karmique.chapitres.part_fortune import build_block_part_fortune

        block = build_block_part_fortune(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_resume_karmique_global_block(self):
        block = build_block_resume_karmique_global(
            self.theme,
            self.score,
        )
        if block:
            # On garde ce résumé comme contexte interne,
            # mais on ne l’ajoute plus aux blocs affichés.
            self.global_ctx["theme_brief"] = (block.get("content") or "").strip()

            data = block.get("data", {}) or {}
            self.global_ctx["global_tension_points"] = data.get("global_tension_points", [])
            self.global_ctx["resume_karmique_global_data"] = data

            # ✅ Nouveau : normalisation des tensions en catégories propres
            call_llm = self.global_ctx.get("call_llm")
            theme_brief = self.global_ctx.get("theme_brief", "").strip()
            axe_karmique_central = self.global_ctx.get("axe_karmique_central", "").strip()
            global_tension_points = self.global_ctx.get("global_tension_points", []) or []

            if call_llm and global_tension_points:
                global_tension_types = generer_tensions_normalisees(
                    theme_brief=theme_brief,
                    axe_karmique=axe_karmique_central,
                    tensions_txt="\n".join(global_tension_points),
                    call_llm=call_llm,
                )
                self.global_ctx["global_tension_types"] = global_tension_types
                logger.debug("GLOBAL TENSION TYPES: %s", global_tension_types)
            else:
                self.global_ctx["global_tension_types"] = []
                logger.debug(
                    "Tensions normalisées non générées. call_llm=%s, global_tension_points=%s",
                    bool(call_llm),
                    bool(global_tension_points),
                )

    def _add_potentiels_karmiques_block(self):
        block = build_block_potentiels_karmiques(
            self.theme,
            self.score,
        )
        if block:
            self.blocks.append(block)



    def _add_karmic_houses_block(self):
        karmic_houses = {4, 8, 12}
        active_houses: Dict[int, List[str]] = {}

        for p, d in self.planetes.items():
            if p == "Ascendant":
                continue
            if not isinstance(d, dict):
                continue
            house = d.get("maison")
            if house in karmic_houses:
                active_houses.setdefault(house, []).append(p)

        if not active_houses:
            return

        # bonus : si tu veux trier pour que ça ressemble à un truc "logique"
        for h in active_houses:
            active_houses[h] = sorted(active_houses[h])

        block = {
            "id": "karmic_houses",
            "title": "Maisons karmiques (IV / VIII / XII)",
            "active_houses": active_houses,
            "content": ""
        }
        self.blocks.append(block)


    def _add_maison_12_block(self):
        from utils.karmique.chapitres.maison_12 import build_block_maison_12

        block = build_block_maison_12(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_maison_8_block(self):
        from utils.karmique.chapitres.maison_8 import build_block_maison_8

        block = build_block_maison_8(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_maison_4_block(self):
        from utils.karmique.chapitres.maison_4 import build_block_maison_4

        block = build_block_maison_4(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)


    def _add_interceptions_block(self):
        from utils.karmique.chapitres.interceptions import build_block_interceptions
        
        block = build_block_interceptions(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:  # peut être None si pas d'interceptions
            self.blocks.append(block)


    def _add_retrogrades_block(self):
        from utils.karmique.chapitres.retrogrades import build_block_retrogrades
        
        block = build_block_retrogrades(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:  # peut être None si pas de rétrogrades
              # 🔥 DEBUG
            logger.debug(
                "ENGINE RECEIVED BLOCK | id=%s | content_exists=%s | content_length=%s | text_exists=%s | text_length=%s",
                block.get("id"),
                bool(block.get("content")),
                len(block.get("content", "")),
                bool(block.get("text")),
                len(block.get("text", "")),
            )
            self.blocks.append(block)

    
    def _add_lune_noire_block(self):
        from utils.karmique.chapitres.lune_noire import build_block_lune_noire

        block = build_block_lune_noire(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        logger.debug("LUNE NOIRE IN THEME: %s", self.planetes.get("Lune Noire"))
        logger.debug("LUNE NOIRE BLOCK: %s", block)
        if block:
            self.blocks.append(block)

    def _add_chiron_block(self):
        block = build_block_chiron(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block:
            self.blocks.append(block)

    def _add_axe_portes_block(self):
        from utils.karmique.chapitres.axe_portes import build_block_axe_portes

        block = build_block_axe_portes(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        if block and block.get("content"):
            self.blocks.append(block)


    def _add_karmic_score_block(self):
        from utils.karmique.chapitres.karmic_score import build_block_karmic_score

        block = build_block_karmic_score(
            self.theme,
            self.score,
            global_ctx=self.global_ctx
        )
        logger.debug("KARMIC SCORE BLOCK: %s", block)
        if block:
            self.blocks.append(block)

    def _add_stelliums_sign_block(self):
        meta = self.score.get("meta", {}) or {}
        amas = meta.get("amas_signes") or []

        if not amas:
            return

        block = {
            "id": "amas_signes",
            "title": "Amas en signe : ton énergie en mode “mono-dossier”",
            "data": {
                "amas_signes": amas
            },
            "content": ""
        }
        self.blocks.append(block)

    def _add_sensitive_points_block(self):
        """
        Regroupe les points 'sensibles' faciles à afficher :
        - Ascendant à 29°
        - planètes à 29°
        """
        vip_names = {"Ascendant", "Soleil"}
        hits = []

        # on veut au minimum Ascendant + planètes classiques
        candidates = ["Ascendant", "Soleil", "Lune", "Mercure", "Vénus", "Mars",
                    "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"]

        for p in candidates:
            info = self.planetes.get(p)
            if not isinstance(info, dict):
                continue

            deg = info.get("degre_dans_signe")
            if deg is None:
                continue

            try:
                degf = float(deg)
            except Exception:
                continue

            # seuil : 29.0 inclus (comme ton score)
            if degf >= 29.0:
                hits.append({
                    "name": p,
                    "signe": info.get("signe"),
                    "maison": info.get("maison"),
                    "deg": round(degf, 2),
                    "is_vip": (p in vip_names),
                })

    


        # 🔥 Priorité Ascendant / Soleil
        order = {"Ascendant": 0, "Soleil": 1}
        hits.sort(key=lambda h: (order.get(h["name"], 99), h["name"]))

        if not hits:
            return

        # Extraire les VIP (s'il y en a)
        asc_29 = next((h for h in hits if h["name"] == "Ascendant"), None)
        sun_29 = next((h for h in hits if h["name"] == "Soleil"), None)

        # -------------------------
        # Entre-deux signes (27°–3°)
        # uniquement Ascendant / Soleil
        # -------------------------
        cuspides = []
        cusp_targets = ["Ascendant", "Soleil"]

        signs = [
            "Bélier", "Taureau", "Gémeaux", "Cancer",
            "Lion", "Vierge", "Balance", "Scorpion",
            "Sagittaire", "Capricorne", "Verseau", "Poissons"
        ]

        for p in cusp_targets:
            info = self.planetes.get(p)
            if not isinstance(info, dict):
                continue

            signe = info.get("signe")
            deg = info.get("degre_dans_signe")
            if not signe or deg is None:
                continue

            try:
                degf = float(deg)
            except Exception:
                continue

            position = None
            if degf >= 27.0:
                position = "fin"     # fin de signe
            elif degf <= 3.0:
                position = "debut"   # début de signe

            if not position or signe not in signs:
                continue

            idx = signs.index(signe)

            # logique karmique correcte
            if position == "fin":
                other_sign = signs[(idx + 1) % len(signs)]   # va vers le signe suivant
            else:
                other_sign = signs[idx - 1]                   # vient du signe précédent

            cuspides.append({
                "name": p,
                "current_sign": signe,
                "other_sign": other_sign,
                "position": position,   # "fin" ou "debut"
                "deg": round(degf, 2),
            })

        logger.debug("SENSITIVE POINTS HITS: %s", hits)

        self.blocks.append({
            "id": "sensitive_points",
            "title": "Points sensibles : degrés ‘anarétiques’ (29°)",
            "data": {
                "points": hits,
                "vip": {
                    "ascendant_29": asc_29,
                    "soleil_29": sun_29,
                },
                "cuspides": cuspides,
            },
            "content": ""
        })


    def _add_saturn_pluto_block(self):
        meta = self.score.get("meta", {}) or {}
        on_angles = meta.get("satplu_on_angles") or []
        hard = meta.get("satplu_hard_aspect")

        # si rien à raconter : pas de bloc
        if not on_angles and not hard:
            return

        self.blocks.append({
            "id": "saturn_pluto",
            "title": "Saturne / Pluton : le dossier ‘pression – transformation’",
            "data": {
                "on_angles": on_angles,
                "hard_aspect": hard,
            },
            "content": ""
        })


    def _add_synthese_karmique_block(self):
        meta = self.score.get("meta", {}) or {}
        breakdown = self.score.get("breakdown", {}) or {}

        dom = meta.get("dominant_elements") or []

        nn_sign = meta.get("nn_sign")
        nn_house = meta.get("nn_house")
        if nn_house is None:
            nn_house = (self.planetes.get("Rahu") or {}).get("maison")

        ns_sign = meta.get("ns_sign")
        ns_house = meta.get("ns_house")
        if ns_house is None:
            ns_house = (self.planetes.get("Ketu") or {}).get("maison")

        # Lune depuis theme (robuste)
        lune = self.planetes.get("Lune") if isinstance(self.planetes.get("Lune"), dict) else {}
        moon_sign = meta.get("moon_sign") or lune.get("signe")
        moon_house = meta.get("moon_house")
        if moon_house is None:
            moon_house = lune.get("maison")

        self.blocks.append({
            "id": "synthese_karmique",
            "title": "Synthèse karmique : la clé d’incarnation",
            "data": {
                "dominant_elements": dom,
                "nn_sign": nn_sign, "nn_house": nn_house,
                "ns_sign": ns_sign, "ns_house": ns_house,
                "moon_sign": moon_sign, "moon_house": moon_house,
                "total_score": self.score.get("total"),
                "level_label": self.score.get("label"),
                "top_sources": self.score.get("top_sources", []),
                "breakdown": breakdown,
            },
            "content": ""
        })