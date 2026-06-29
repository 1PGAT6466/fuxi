"""
synonym_loader.py — Phase 0.4.2: 统一同义词加载器
"""
import yaml, logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

SYNONYMS_PATH = Path(__file__).parent.parent / "config" / "synonyms.yaml"

_synonyms_cache: Dict[str, list] = None


def load_synonyms() -> Dict[str, list]:
    """加载同义词映射表（惰性加载 + 缓存）"""
    global _synonyms_cache
    if _synonyms_cache is not None:
        return _synonyms_cache
    
    try:
        if SYNONYMS_PATH.exists():
            with open(SYNONYMS_PATH, encoding='utf-8') as f:
                data = yaml.safe_load(f)
            _synonyms_cache = data.get('synonyms', {})
            logger.info(f"[Synonyms] Loaded {len(_synonyms_cache)} synonym groups")
        else:
            _synonyms_cache = {}
            logger.warning(f"[Synonyms] File not found: {SYNONYMS_PATH}")
    except Exception as e:
        _synonyms_cache = {}
        logger.warning(f"[Synonyms] Load failed: {e}")
    
    return _synonyms_cache


def expand_query_with_synonyms(query: str) -> str:
    """用同义词扩展查询词"""
    synonyms = load_synonyms()
    q_lower = query.lower()
    expanded = query
    for canonical, aliases in synonyms.items():
        for alias in aliases:
            if alias.lower() in q_lower and canonical not in q_lower:
                expanded += f" {canonical}"
                break
    return expanded.strip()


def normalize_entity(name: str) -> str:
    """实体名称归一化"""
    synonyms = load_synonyms()
    name_lower = name.lower()
    for canonical, aliases in synonyms.items():
        if name_lower == canonical.lower() or name_lower in [a.lower() for a in aliases]:
            return canonical
    return name.upper()
