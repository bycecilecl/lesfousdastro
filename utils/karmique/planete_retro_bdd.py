# utils/karmique/planete_retro_bdd.py
from __future__ import annotations

import csv
import os
import unicodedata
from functools import lru_cache
from typing import Any, Dict, Tuple
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # remonte à la racine projet
DATA_DIR = os.path.join(BASE_DIR, "data", "karmique")
RETRO_CSV = os.path.join(DATA_DIR, "planete_retro.csv")

logger = logging.getLogger(__name__)

def _norm(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.strip().lower()


def _pick(row: Dict[str, Any], *keys: str) -> str:
    """Récupère une valeur de row avec variantes de clés possibles."""
    for k in keys:
        if k in row and row[k] is not None:
            return str(row[k]).strip()
    # fallback: essayer avec normalisation des en-têtes
    norm_map = {_norm(k): k for k in row.keys()}
    for k in keys:
        nk = _norm(k)
        if nk in norm_map:
            v = row.get(norm_map[nk])
            return str(v).strip() if v is not None else ""
    return ""


@lru_cache(maxsize=1)
def _load_retro_table() -> Dict[Tuple[str, str, str], Dict[str, str]]:
    """
    Index:
      (planete, type_donnee, valeur) -> {"vie_actuelle": ..., "vie_anterieure": ...}
    """
    if not os.path.exists(RETRO_CSV):
        logger.warning("[RETRO_BDD] CSV introuvable: %s", RETRO_CSV)
        return {}

    table: Dict[Tuple[str, str, str], Dict[str, str]] = {}

    with open(RETRO_CSV, "r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
        f.seek(0)

        # Excel -> souvent tab ; sinon ; parfois ,
        if "\t" in first_line:
            delim = "\t"
        elif ";" in first_line:
            delim = ";"
        else:
            delim = ","

        reader = csv.DictReader(f, delimiter=delim)

        for row in reader:
            pl = _norm(_pick(row, "PLANÈTE", "PLANETE", "PLANETÉ", "planete", "planète"))
            td = _norm(_pick(row, "TYPE_DONNÉE", "TYPE_DONNEE", "type_donnee", "type donnée"))
            val = _norm(_pick(row, "VALEUR", "valeur"))

            va = _pick(row, "VIE ACTUELLE", "VIE_ACTUELLE", "vie_actuelle")
            vp = _pick(row, "VIE ANTERIEURE", "VIE ANTÉRIEURE", "VIE_ANTERIEURE", "vie_anterieure")

            if not pl or not td:
                continue

            key = (pl, td, val)
            table[key] = {
                "vie_actuelle": va.strip(),
                "vie_anterieure": vp.strip(),
            }

    logger.info(
        "[RETRO_BDD] loaded = %s entries from %s",
        len(table),
        os.path.basename(RETRO_CSV),
    )
    return table


def get_retro_interp(planete: str, type_donnee: str, valeur: str = "") -> Dict[str, str]:
    """
    Retourne {"vie_actuelle": ..., "vie_anterieure": ...}
    """
    table = _load_retro_table()
    key = (_norm(planete), _norm(type_donnee), _norm(valeur))
    return table.get(key, {"vie_actuelle": "", "vie_anterieure": ""})