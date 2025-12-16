# config/gift_codes.py
import csv
import os
from datetime import datetime
from typing import Optional, Dict, List

# Chemin vers gift_codes.csv à la racine du projet Flask
GIFT_CODES_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gift_codes.csv")

# On standardise : ton CSV est en ; (format courant FR)
CSV_DELIMITER = ";"


def _ensure_file_exists() -> None:
    """
    S'assure que le fichier CSV existe avec le bon header.
    Ne crée rien si le fichier existe déjà.
    """
    if os.path.exists(GIFT_CODES_CSV):
        return

    os.makedirs(os.path.dirname(GIFT_CODES_CSV), exist_ok=True)
    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code", "product_key", "used_by", "used_at", "notes"],
            delimiter=CSV_DELIMITER,
        )
        writer.writeheader()


def load_gift_codes() -> List[Dict[str, str]]:
    """
    Charge tous les codes cadeaux depuis le CSV.

    Colonnes attendues :
    - code
    - product_key
    - used_by
    - used_at
    - notes

    Important : le fichier est en ;, donc DictReader(delimiter=';').
    """
    _ensure_file_exists()

    rows: List[Dict[str, str]] = []
    fieldnames = ["code", "product_key", "used_by", "used_at", "notes"]

    with open(GIFT_CODES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        for row in reader:
            clean = {k: (row.get(k) or "") for k in fieldnames}
            clean["code"] = (clean.get("code") or "").strip().upper()
            clean["product_key"] = (clean.get("product_key") or "").strip()
            clean["used_by"] = (clean.get("used_by") or "").strip()
            clean["used_at"] = (clean.get("used_at") or "").strip()
            clean["notes"] = (clean.get("notes") or "").strip()
            rows.append(clean)

    return rows


def get_gift_code(code: str) -> Optional[Dict[str, str]]:
    """
    Récupère un code cadeau précis (insensible à la casse).
    """
    code = (code or "").strip().upper()
    if not code:
        return None

    for row in load_gift_codes():
        if row.get("code") == code:
            return row
    return None


def is_code_used(code_row: Dict[str, str]) -> bool:
    """
    True si le code a déjà été utilisé (used_at non vide).
    """
    return bool((code_row.get("used_at") or "").strip())


def get_unused_code_for_product(product_key: str) -> Optional[Dict[str, str]]:
    """
    Retourne le premier code NON UTILISÉ pour un product_key donné.
    None si plus de stock.
    """
    product_key = (product_key or "").strip()
    if not product_key:
        return None

    for row in load_gift_codes():
        if row.get("product_key") == product_key and not is_code_used(row):
            return row

    return None


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
        if row.get("code") == code:
            # used_by : on garde ce qu'on reçoit, sinon on conserve l'existant
            row["used_by"] = (used_by or row.get("used_by") or "").strip()
            row["used_at"] = datetime.utcnow().isoformat()
            updated = True
            break

    if not updated:
        return False

    fieldnames = ["code", "product_key", "used_by", "used_at", "notes"]

    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=CSV_DELIMITER)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    return True


def create_gift_code(code: str, product_key: str, notes: str = "") -> Dict[str, str]:
    """
    Ajoute un nouveau code dans le CSV (sans vérif de doublon).
    """
    _ensure_file_exists()

    code = (code or "").strip().upper()
    product_key = (product_key or "").strip()
    notes = (notes or "").strip()

    new_row = {
        "code": code,
        "product_key": product_key,
        "used_by": "",
        "used_at": "",
        "notes": notes,
    }

    rows = load_gift_codes()
    rows.append(new_row)

    with open(GIFT_CODES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code", "product_key", "used_by", "used_at", "notes"],
            delimiter=CSV_DELIMITER,
        )
        writer.writeheader()
        writer.writerows(rows)

    return new_row