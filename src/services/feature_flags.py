"""
feature_flags.py — Phase 5.0.3: Feature Flag 服务
支持秒级回滚，不重启切换功能
"""
import json, os, time, logging
from typing import Dict, Any

logger = logging.getLogger("feature_flags")
FLAG_FILE = os.path.join(os.path.dirname(__file__), "../../data/feature_flags.json")

DEFAULT_FLAGS = {
    "graphrag_multi_hop": False,
    "query_planner": False,
    "table_structured_search": False,
    "multimodal_rag": False,
    "sentence_level_compress": False,
    "knowledge_lifecycle": False,
    "siliconflow_rerank": False,
    "self_rag_check": True,
    "crag_rewrite": True,
}

_flags = None
_last_load = 0
_RELOAD_INTERVAL = 10  # 10 秒重新加载

def load_flags() -> Dict[str, bool]:
    global _flags, _last_load
    now = time.time()
    if _flags is not None and now - _last_load < _RELOAD_INTERVAL:
        return _flags
    
    if os.path.exists(FLAG_FILE):
        try:
            with open(FLAG_FILE, 'r') as f:
                saved = json.load(f)
            _flags = {**DEFAULT_FLAGS, **saved}
        except Exception:
            _flags = dict(DEFAULT_FLAGS)
    else:
        _flags = dict(DEFAULT_FLAGS)
        save_flags(_flags)
    
    _last_load = now
    return _flags

def save_flags(flags: Dict[str, bool]):
    os.makedirs(os.path.dirname(FLAG_FILE), exist_ok=True)
    with open(FLAG_FILE, 'w') as f:
        json.dump(flags, f, indent=2)

def is_enabled(feature: str) -> bool:
    flags = load_flags()
    return flags.get(feature, False)

def set_flag(feature: str, enabled: bool) -> bool:
    flags = load_flags()
    flags[feature] = enabled
    save_flags(flags)
    global _flags
    _flags = flags
    _last_load = time.time()
    logger.info(f"[FeatureFlag] {feature} = {enabled}")
    return True

def get_all_flags() -> Dict[str, Any]:
    flags = load_flags()
    return {
        "flags": flags,
        "last_reload": _last_load,
        "reload_interval_sec": _RELOAD_INTERVAL
    }
