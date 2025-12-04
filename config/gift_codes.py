# config/gift_codes.py
import csv
import os
from datetime import datetime
from typing import Optional, Dict, List

GIFT_CODES_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gift_codes.csv")
# ↑ remonte d'un cran depuis /config vers la racine, puis gift_codes.csv


def _ensure_file_exists():
    """
    S'assure que le fichier CSV existe avec le bon header.
    Ne crée rien si le fichier existe déjà.
    """
    if os.path.exists(GIFT_CODES_CSV):
        return
    
    os.makedirs(os.path.dirname(GIFT_CODES_CSV), exist_ok=True)
    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "product_key", "used_by", "used_at", "notes"])
        writer.writeheader()


def load_gift_codes() -> List[Dict[str, str]]:
    """
    Charge tous les codes cadeaux depuis le CSV.
    Ne garde que les colonnes officielles (code, product_key, used_by, used_at, notes),
    pour éviter les vieilles colonnes type 'used'.
    """
    _ensure_file_exists()
    rows: List[Dict[str, str]] = []
    fieldnames = ["code", "product_key", "used_by", "used_at", "notes"]

    with open(GIFT_CODES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k: (row.get(k) or "") for k in fieldnames}
            clean["code"] = (clean.get("code") or "").strip().upper()
            clean["product_key"] = (clean.get("product_key") or "").strip()
            rows.append(clean)
    return rows


def get_gift_code(code: str) -> Optional[Dict[str, str]]:
    """
    Récupère un code cadeau précis (insensible à la casse).
    Retourne le dict complet ou None si introuvable.
    """
    if not code:
        return None
    code = code.strip().upper()
    for row in load_gift_codes():
        if row["code"] == code:
            return row
    return None

def get_unused_code_for_product(product_key: str) -> Optional[Dict[str, str]]:
    """
    Retourne le premier code NON UTILISÉ pour un product_key donné.
    None si plus de stock.
    """
    if not product_key:
        return None
    product_key = product_key.strip()

    for row in load_gift_codes():
        if row["product_key"] == product_key and not is_code_used(row):
            return row

    return None


def is_code_used(code_row: Dict[str, str]) -> bool:
    """
    True si le code a déjà été utilisé (used_at non vide).
    """
    return bool((code_row.get("used_at") or "").strip())


def mark_code_as_used(code: str, used_by: str = "") -> bool:
    """
    Marque un code comme utilisé dans le CSV.
    Retourne True si OK, False si le code n'a pas été trouvé.
    """
    code = (code or "").strip().upper()
    if not code:
        return False

    _ensure_file_exists()
    rows = load_gift_codes()
    updated = False

    for row in rows:
        if row["code"] == code:
            row["used_by"] = (used_by or row.get("used_by") or "").strip()
            row["used_at"] = datetime.utcnow().isoformat()
            updated = True

    if not updated:
        return False

    fieldnames = ["code", "product_key", "used_by", "used_at", "notes"]

    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # On ne garde que les bonnes colonnes
            clean = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean)

    return True


def create_gift_code(code: str, product_key: str, notes: str = "") -> Dict[str, str]:
    """
    Ajoute un nouveau code dans le CSV (sans vérif de doublon).
    Utile pour un petit script d'admin plus tard.
    """
    _ensure_file_exists()
    code = code.strip().upper()
    product_key = product_key.strip()

    new_row = {
        "code": code,
        "product_key": product_key,
        "used_by": "",
        "used_at": "",
        "notes": notes or "",
    }

    rows = load_gift_codes()
    rows.append(new_row)

    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "product_key", "used_by", "used_at", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    return new_row


def get_unused_code_for_product(product_key: str) -> Optional[Dict[str, str]]:
    """
    Retourne le premier code NON UTILISÉ pour un produit donné.
    Format résultat identique à get_gift_code().
    """
    product_key = (product_key or "").strip()
    if not product_key:
        return None

    rows = load_gift_codes()
    for row in rows:
        if row.get("product_key") == product_key and not (row.get("used_at") or "").strip():
            return row

    return None