"""
dedup.py — DXF文件去重
基于几何哈希进行文件去重，避免重复存储相同几何内容的文件
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.services.dxf_viewer.parser import extract_dxf

logger = logging.getLogger("services.dxf-viewer.dedup")

DEFAULT_HASH_INDEX = "data/services/dxf-viewer/hash_index.json"


def _load_hash_index(index_path: str) -> Dict[str, str]:
    path = Path(index_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load hash index: {e}")
        return {}


def _save_hash_index(index_path: str, index: Dict[str, str]) -> None:
    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        logger.error(f"Failed to save hash index: {e}")
        raise


def check_duplicate(
    file_path: str,
    data_dir: str = "data/services/dxf-viewer",
) -> Dict[str, Any]:
    """
    检查DXF文件是否已存在（基于几何哈希）

    返回:
        {
            "is_duplicate": bool,
            "existing_hash": str or None,
            "hash_value": str,
        }
    """
    index_path = str(Path(data_dir) / "hash_index.json")

    try:
        parsed = extract_dxf(file_path)
    except (ValueError, ImportError) as e:
        logger.error(f"Failed to parse DXF for dedup check: {e}")
        return {
            "is_duplicate": False,
            "existing_hash": None,
            "hash_value": "",
        }

    hash_value = parsed["geometry_hash"]
    index = _load_hash_index(index_path)

    if hash_value in index:
        return {
            "is_duplicate": True,
            "existing_hash": index[hash_value],
            "hash_value": hash_value,
        }

    return {
        "is_duplicate": False,
        "existing_hash": None,
        "hash_value": hash_value,
    }


def register_hash(
    hash_value: str,
    file_id: str,
    data_dir: str = "data/services/dxf-viewer",
) -> None:
    """注册新的哈希值到索引"""
    index_path = str(Path(data_dir) / "hash_index.json")
    index = _load_hash_index(index_path)
    index[hash_value] = file_id
    _save_hash_index(index_path, index)
