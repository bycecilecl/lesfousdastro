 # config/products.py
import os

def _bool_env(name, default=""):
    return (os.getenv(name, default) or "").strip().lower() in {"1","true","on","yes"}

def _int_env(name, default):
    try:
        val = (os.getenv(name) or "").strip()
        return int(val) if val else default
    except (ValueError, TypeError):
        print(f"⚠️ ENV {name} invalide, fallback sur {default}")
        return default

DEFAULT_PRODUCT = "flash_astral"

def load_products():
    """
    products[product_key] = {
      label, price_id?, price_cents, success_route (endpoint Flask), enabled
    }
    """
    return {
        "flash_astral": {
            "label": "Flash Astral complet",
            "price_id": os.getenv("FLASH_ASTRAL_PRICE_ID", "").strip(),
            "price_cents": _int_env("FLASH_ASTRAL_PRICE_CENTS", 2900),
            "success_route": "point_astral_blocs.point_astral_blocs_complet",
            "enabled": _bool_env("FLASH_ASTRAL_ENABLED", "1"),
        },

        "point_astral_famille": {
            "label": "Point Astral – Racines familiales",
            "price_id": os.getenv("POINT_ASTRAL_FAMILLE_PRICE_ID", "").strip(),
            "price_cents": _int_env("POINT_ASTRAL_FAMILLE_PRICE_CENTS", 3500),
            "success_route": "point_astral_famille.point_astral_famille_complet",
            "enabled": _bool_env("POINT_ASTRAL_FAMILLE_ENABLED", "1"),
        },
        "flash_transits": {
            "label": "Point Transits",
            "price_id": os.getenv("FLASH_TRANSITS_PRICE_ID", "").strip(),
            "price_cents": _int_env("FLASH_TRANSITS_PRICE_CENTS", 1200),
            "success_route": "transits.transits_complet",
            "enabled": _bool_env("FLASH_TRANSITS_ENABLED", "1"),
        },
        "forces_defis": {
            "label": "Mes Potentiels et Défis",
            "price_id": os.getenv("FORCES_DEFIS_PRICE_ID", "").strip(),
            "price_cents": _int_env("FORCES_DEFIS_PRICE_CENTS", 1500),
            "success_route": "forces_defis_module.forces_defis_complet",
            "enabled": _bool_env("FORCES_DEFIS_ENABLED", "1"),
        },
    
        "profil_amoureux": {
            "label": "Analyse Amoureuse complète",
            "price_id": os.getenv("ANALYSE_AMOUR_PRICE_ID", "").strip(),
            "price_cents": _int_env("ANALYSE_AMOUR_PRICE_CENTS", 2500),
            "success_route": "profil_amoureux_module.profil_amoureux_complet",
            "enabled": _bool_env("ANALYSE_AMOUR_ENABLED", "1"),
        },

        "analyse_karmique": {
            "label": "Analyse karmique",
            "price_id": os.getenv("ANALYSE_KARMIQUE_PRICE_ID", "").strip(),
            "price_cents": _int_env("ANALYSE_KARMIQUE_PRICE_CENTS", 6900),
            "success_route": "analyse_karmique.analyse_karmique_complete",
            "enabled": _bool_env("ANALYSE_KARMIQUE_ENABLED", "1"),
        },

        "clarification_questions": {
            "label": "Option 3 questions de clarification",
            "price_id": os.getenv("CLARIFICATION_QUESTIONS_PRICE_ID", "").strip(),
            "price_cents": _int_env("CLARIFICATION_QUESTIONS_PRICE_CENTS", 2500),
            "success_route": None,
            "enabled": _bool_env("CLARIFICATION_QUESTIONS_ENABLED", "1"),
        },

        "pack_essence": {
            "label": "Pack Essence (3 analyses)",
            "price_cents": _int_env("PACK_ESSENCE_PRICE_CENTS", 4900),
            "included_products": [
                "flash_astral",
                "forces_defis",
                "profil_amoureux",
            ],
        },

        "pack_origines": {
            "label": "Pack Origines",
            "price_cents": _int_env("PACK_ORIGINES_PRICE_CENTS", 8300),
            "included_products": [
                "point_astral_famille",
                "analyse_karmique",
            ],
            "enabled": _bool_env("PACK_ORIGINES_ENABLED", "1"),
        },

        "pack_integral": {
            "label": "Pack Intégral",
            "price_cents": _int_env("PACK_INTEGRAL_PRICE_CENTS", 10900),
            "included_products": [
                "point_astral_famille",
                "analyse_karmique",
                "profil_amoureux",
                "forces_defis",
            ],
            "enabled": _bool_env("PACK_INTEGRAL_ENABLED", "1"),
        },
    }

try:
    PRODUCTS = {k:v for k,v in load_products().items() if v.get("enabled", True)}
    print(f"✅ {len(PRODUCTS)} produit(s) chargés: {list(PRODUCTS.keys())}")
except Exception as e:
    print(f"❌ Erreur chargement produits: {e}")
    PRODUCTS = {}

__all__ = ["PRODUCTS", "DEFAULT_PRODUCT"]
