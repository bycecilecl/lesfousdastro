# ─────────────────────────────────────────────────────────────────────────────
# UTIL : generer_resume_theme_enrichi(data)
# Rôle :
#   - Fabrique un résumé clair du thème à partir de `data` :
#       • Positions planétaires (formatées)
#       • Aspects significatifs (filtrés/formatés)
#       • Maisons angulaires (1/4/7/10) + planètes présentes (avec fallback)
#       • Points forts (dédupliqués, triés, 🌟 priorisés)
#       • Rappel du nakshatra lunaire (si dispo côté védique)
#
# Entrée :
#   - data (dict) : structure complète renvoyée par calcul_theme()
#       attend au minimum :
#         data["planetes"], data["aspects"], data["maisons"],
#         data["planetes_vediques"]["Lune"] (optionnel pour le nakshatra)
#
# Sorties :
#   - (resume: str, points_forts_sorted: list[str])
#       • resume : bloc texte prêt à injecter dans un prompt LLM ou un template
#       • points_forts_sorted : liste nettoyée et triée des points forts
#
# Dépendances :
#   - utils.utils_formatage.formater_positions_planetes
#   - utils.utils_formatage.formater_aspects_significatifs
#   - utils.utils_points_forts.extraire_points_forts
#
# Détails importants :
#   - Fallback maisons angulaires : si data["maisons"]["Maison N"]["planetes"] est vide,
#     on reconstruit la liste depuis data["planetes"][*]["maison"].
#   - Nettoyage points forts : dédoublonnage, tri pour faire remonter ceux marqués "🌟".
#   - Tolère l’absence de certaines clés (retourne des valeurs par défaut lisibles).
#
# Où c’est utilisé :
#   - Préparation de texte “compact et exploitable” pour les prompts LLM (Point Astral).
#   - Peut servir de bloc récapitulatif lisible dans un export ou un email.
# ─────────────────────────────────────────────────────────────────────────────


from utils.utils_points_forts import extraire_points_forts
from utils.formatage import formater_positions_planetes, formater_aspects_significatifs

def generer_resume_theme_enrichi(data):
    """Génère un résumé du thème enrichi avec les données formatées et les points forts optimisés"""
    try:
        positions_str = formater_positions_planetes(data.get("planetes", {}))
        aspects_str = formater_aspects_significatifs(data.get("aspects", []))

        # Points forts (version enrichie)
        points_forts_bruts = extraire_points_forts(data)

        # Nettoyage : suppression des doublons et tri (les 🌟 d'abord)
        points_forts_uniques = list(dict.fromkeys(points_forts_bruts))
        points_forts_sorted = sorted(
            points_forts_uniques,
            key=lambda x: (not x.startswith("🌟"), x)
        )

        # -- Maisons angulaires (supporte "1" et "Maison 1")
                # -- Maisons angulaires (supporte "1", 1 et "Maison 1") + fallback depuis planètes
        maisons = data.get("maisons", {})
        planetes_all = data.get("planetes", {})

        def normaliser_maison(val):
            """Renvoie '1','4','7','10' sous forme str si possible"""
            try:
                return str(int(val))
            except Exception:
                return None

        def planetes_en_maison(numero):
            """Reconstruit la liste des planètes en maison N depuis planètes[*].maison"""
            N = int(numero)
            vraies_planetes = {
                'Soleil','Lune','Mercure','Vénus','Mars','Jupiter','Saturne','Uranus','Neptune','Pluton',
                # ajoute ici si tu veux compter la Lune Noire, Chiron, etc.
                # 'Lune Noire','Chiron'
            }
            out = []
            for nom, infos in planetes_all.items():
                if nom not in vraies_planetes:
                    continue
                m = infos.get('maison')
                try:
                    if m is not None and int(m) == N:
                        out.append(nom)
                except Exception:
                    pass
            return out

        maisons_angulaires = []
        for maison_num in ["1", "4", "7", "10"]:
            # 1) tenter via data['maisons']
            maison_data = (maisons.get(maison_num)
                           or maisons.get(f"Maison {maison_num}")
                           or maisons.get(int(maison_num)) if isinstance(maisons, dict) else None)

            planetes_maison = []
            if maison_data and isinstance(maison_data, dict):
                planetes_maison = maison_data.get("planetes", []) or []

            # 2) fallback si vide : reconstruire depuis data['planetes']
            if not planetes_maison:
                planetes_maison = planetes_en_maison(maison_num)

            if planetes_maison:
                maisons_angulaires.append(f"Maison {maison_num}: {', '.join(planetes_maison)}")

        maisons_angulaires_str = "\n".join(maisons_angulaires) or "Aucune planète dans les maisons angulaires"

        

        # -- Nakshatra védique
        lune_vedique = data.get("planetes_vediques", {}).get("Lune", {})
        nakshatra_info = ""
        if lune_vedique.get("nakshatra"):
            nakshatra_info = (
                f"\n🕉️ NAKSHATRA LUNAIRE :\n"
                f"Lune en {lune_vedique.get('nakshatra')} (pada {lune_vedique.get('pad', '?')})"
            )

        resume = f"""
🔹 POSITIONS PLANÉTAIRES :
{positions_str}

🔹 ASPECTS ASTROLOGIQUES SIGNIFICATIFS :
{aspects_str}

🔹 MAISONS ANGULAIRES (1, 4, 7, 10) :
{maisons_angulaires_str}

🔹 POINTS FORTS ASTROLOGIQUES :
{chr(10).join(f"- {pf}" for pf in points_forts_sorted)}
{nakshatra_info}
"""
        return resume, points_forts_sorted

    except Exception as e:
        print(f"❌ Erreur dans generer_resume_theme_enrichi : {e}")
        return "❌ Erreur dans la génération du résumé", []