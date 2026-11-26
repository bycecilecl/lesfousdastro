"""Remise du 26 au 29 novembre 2026 ; aucun appel réseau ni génération."""
from datetime import datetime
from zoneinfo import ZoneInfo


PARIS = ZoneInfo("Europe/Paris")
START = datetime(2026, 11, 26, tzinfo=PARIS)
END = datetime(2026, 11, 30, tzinfo=PARIS)  # Borne exclue.
ANALYSES = frozenset({
    "flash_astral", "point_astral_famille", "forces_defis", "profil_amoureux",
    "analyse_karmique", "flash_transits", "revolution_solaire",
})
PACK_CONTENTS = {
    "pack_essence": ("flash_astral", "forces_defis", "profil_amoureux"),
    "pack_origines": ("point_astral_famille", "analyse_karmique"),
    "pack_integral": ("point_astral_famille", "analyse_karmique", "profil_amoureux", "forces_defis"),
}


def promotion_active(now=None):
    instant = now if now is not None else datetime.now(PARIS)
    if instant.tzinfo is None:
        raise ValueError("La date doit avoir un fuseau horaire.")
    return START <= instant < END


def apply_analysis_promotion(key, product, now=None):
    """Retourne une copie remisée ; le catalogue de référence reste intact."""
    if product is None or key not in ANALYSES or not promotion_active(now):
        return product
    cents = product["price_cents"]
    return {**product, "price_cents": (cents * 80 + 50) // 100}


def euros_label(cents):
    euros, remainder = divmod(cents, 100)
    return f"{euros},{remainder:02d}" if remainder else str(euros)


def promotion_context(catalogue):
    """Même instant pour tous les prix affichés, y compris les comparaisons packs."""
    now = datetime.now(PARIS)
    reference = {key: item["price_cents"] for key, item in catalogue.items()}
    prices = {key: apply_analysis_promotion(key, item, now)["price_cents"]
              for key, item in catalogue.items()}
    # Les packs ne sont pas vendus par le lanceur local. Leur affichage conserve
    # les tarifs habituels ; le catalogue de déploiement fournit ses vrais prix.
    for key, cents in {"pack_essence": 4900, "pack_origines": 8300, "pack_integral": 10900}.items():
        prices.setdefault(key, cents)
    totals = {key: sum(prices[part] for part in parts)
              for key, parts in PACK_CONTENTS.items()
              if all(part in prices for part in parts)}
    return {
        "analysis_promo_active": promotion_active(now),
        "analysis_promo_remaining_ms": max(0, int((END - now).total_seconds() * 1000)),
        "analysis_prices": {key: cents / 100 for key, cents in prices.items()},
        "analysis_price_labels": {key: euros_label(cents) for key, cents in prices.items()},
        "analysis_reference_labels": {key: euros_label(cents) for key, cents in reference.items()},
        "pack_total_labels": {key: euros_label(cents) for key, cents in totals.items()},
        "pack_saving_labels": {key: euros_label(cents - prices[key]) for key, cents in totals.items()},
    }
