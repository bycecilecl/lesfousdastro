import json
import os
import hashlib
from typing import Any, Dict, List, Optional


def _ensure_parent_dir(filepath: str) -> None:
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)


def get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _normalize_piece(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def build_checkpoint_id(
    nom: str = "",
    date: str = "",
    heure: str = "",
    lieu: str = "",
) -> str:
    """
    Construit un identifiant stable pour UNE analyse karmique.
    On utilise les infos de naissance pour isoler le cache par personne/analyse.
    """
    raw = "|".join([
        _normalize_piece(nom),
        _normalize_piece(date),
        _normalize_piece(heure),
        _normalize_piece(lieu),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_checkpoint_path_for_analysis(checkpoint_id: str) -> str:
    return os.path.join(
        get_project_root(),
        "tmp",
        "karmique_checkpoints",
        f"{checkpoint_id}.json",
    )


def get_blocks_dir_for_analysis(checkpoint_id: str) -> str:
    return os.path.join(
        get_project_root(),
        "tmp",
        "karmique_blocks",
        checkpoint_id,
    )


def get_default_checkpoint_path() -> str:
    """
    Fallback ancien format.
    À éviter pour les nouvelles analyses.
    """
    return os.path.join(get_project_root(), "tmp", "karmique_checkpoint.json")


def get_default_blocks_dir() -> str:
    """
    Fallback ancien format.
    À éviter pour les nouvelles analyses.
    """
    return os.path.join(get_project_root(), "tmp", "karmique_blocks")


def save_checkpoint(filepath: str, payload: Dict[str, Any]) -> None:
    _ensure_parent_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_checkpoint(filepath: str) -> Dict[str, Any]:
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def reset_checkpoint(filepath: str) -> None:
    if os.path.exists(filepath):
        os.remove(filepath)


def get_cached_block(checkpoint: Dict[str, Any], block_key: str) -> Optional[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = checkpoint.get("blocks", []) or []
    for block in blocks:
        if (block.get("id") or block.get("key")) == block_key:
            return block
    return None


def upsert_block_in_checkpoint(
    filepath: str,
    block_data: Dict[str, Any],
    error_on_block: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    checkpoint = load_checkpoint(filepath)
    blocks = checkpoint.get("blocks", []) or []

    current_key = block_data.get("id") or block_data.get("key")
    if not current_key:
        save_checkpoint(filepath, checkpoint)
        return

    replaced = False
    for i, existing in enumerate(blocks):
        existing_key = existing.get("id") or existing.get("key")
        if existing_key == current_key:
            blocks[i] = block_data
            replaced = True
            break

    if not replaced:
        blocks.append(block_data)

    checkpoint["blocks"] = blocks

    if error_on_block is not None:
        checkpoint["error_on_block"] = error_on_block
    else:
        checkpoint.pop("error_on_block", None)

    if error_message is not None:
        checkpoint["error_message"] = error_message
    else:
        checkpoint.pop("error_message", None)

    save_checkpoint(filepath, checkpoint)


def save_block_txt(block_key: str, text: str, base_dir: Optional[str] = None) -> None:
    if not block_key:
        return

    if base_dir is None:
        base_dir = get_default_blocks_dir()

    os.makedirs(base_dir, exist_ok=True)
    filepath = os.path.join(base_dir, f"{block_key}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text or "")