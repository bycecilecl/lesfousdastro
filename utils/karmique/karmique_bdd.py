from __future__ import annotations

from pathlib import Path
import csv
import logging
import unicodedata
from functools import lru_cache
from typing import Dict, Optional, Tuple, Iterable

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "karmique"


def _norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()

    # enlève les accents
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # normalise espaces
    s = " ".join(s.split())

    return s


def _iter_csv_files(data_dir: Path) -> Iterable[Path]:
    return sorted([p for p in data_dir.glob("*.csv") if p.is_file()])


def _detect_dialect(sample: str) -> csv.Dialect:
    # Essaye sniffer, sinon fallback TAB (Excel) puis ;
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t;,\u0001|")
    except Exception:
        class TabDialect(csv.Dialect):
            delimiter = "\t"
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return TabDialect()


def _clean_fieldnames(fieldnames):
    # Supprime espaces, BOM, casse, etc.
    out = []
    for f in (fieldnames or []):
        f = (f or "").replace("\ufeff", "")  # BOM
        f = f.strip()
        out.append(f)
    return out


@lru_cache(maxsize=1)
def _load_karmique_folder(data_dir_str: str) -> Dict[Tuple[str, str, str], str]:
    data_dir = Path(data_dir_str)
    db: Dict[Tuple[str, str, str], str] = {}

    csv_files = list(_iter_csv_files(data_dir))
    logger.info("[KARMIQUE_BDD] folder = %s", data_dir)
    logger.info("[KARMIQUE_BDD] files  = %s", [p.name for p in csv_files])

    for path in csv_files:
        # Lire un échantillon pour détecter le séparateur
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        sample = raw[:5000]
        dialect = _detect_dialect(sample)

        # Re-parser proprement avec le dialect détecté
        rows_added = 0
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, dialect=dialect)

            # Nettoyer les noms de colonnes (ex: "DONNEE " -> "DONNEE")
            reader.fieldnames = _clean_fieldnames(reader.fieldnames)

            for row in reader:
                # Astuce : certaines lignes peuvent avoir des clés avec espaces aussi
                # => on remappe les clés propres
                clean_row = { (k or "").strip(): v for k, v in row.items() }

                astre = _norm(clean_row.get("ASTRE"))
                donnee = _norm(clean_row.get("DONNEE"))
                valeur = _norm(clean_row.get("VALEUR"))
                interp = (clean_row.get("INTERPRETATION") or "").strip()

                if not (astre and donnee and valeur and interp):
                    continue

                db[(astre, donnee, valeur)] = interp
                rows_added += 1

        logger.info(
            "[KARMIQUE_BDD] +%s from %s (delim=%r)",
            rows_added,
            path.name,
            getattr(dialect, "delimiter", "?"),
        )

    logger.info("[KARMIQUE_BDD] entries = %s", len(db))
    return db


def get_karmique_interp(astre: str, donnee: str, valeur: str, data_dir: Optional[str] = None) -> Optional[str]:
    db = _load_karmique_folder(str(Path(data_dir) if data_dir else DATA_DIR))
    txt = db.get((_norm(astre), _norm(donnee), _norm(valeur)))

    if isinstance(txt, str):
        txt = txt.replace('""', '"')

    return txt


def reload_karmique_bdd() -> None:
    _load_karmique_folder.cache_clear()