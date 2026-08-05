"""
feature_flags.py - Phase 5.0.3: Feature Flag Service
Supports instant rollback without restart
"""
import json, time, logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("feature_flags")

from src.config import DATA_DIR
FLAG_FILE = Path(DATA_DIR) / "feature_flags.json"

DEFAULT_FLAGS = {
    # Core Flags (must be independently controlled)
    "shaoyang_sag_extract": True,        # SAG-style event/entity extraction (default enabled)
    "taiyang_multi_hop": True,           # SAG-style multi-hop search (default enabled)
    "taiyang_seed_score": True,          # SAG seed_score fusion (default enabled)

    # Phase B New Flags (Fuxi search architecture fusion)
    "taiyang_sag_pipeline": True,        # SAG three-stage pipeline master switch (ADR-001, task #3)
    "taiyang_path_a": True,              # Path A: Entity-guided fallback (ADR-002, task #2)
    "taiyang_event_search": True,        # Event granularity search (ADR-003, task #1)
    "taiyang_sql_multi_hop": True,       # SQL JOIN multi-hop expansion H=1 (task #3)

    # Enhancement Flags (one-click control)
    "enhanced_pipeline": False,          # Contains: query_rewrite/hyde/self_check/crag/context_compress

    # Basic Flags
    "graphrag_multi_hop": False,
    "query_planner": False,
    "table_structured_search": False,
    "multimodal_rag": False,
    "sentence_level_compress": False,
    "knowledge_lifecycle": False,
    "siliconflow_rerank": True,
    "self_rag_check": True,              # From services/feature_flags.py (originally taiyin was False)
    "crag_rewrite": True,                # From services/feature_flags.py (originally taiyin was False)
    "query_rewrite": True,
    "hyde": False,
    "wiki_search": False,
    "table_view": False,
    "session_memory": False,

    # v1.50 Phase C: Dream Cycle
    "enable_dream_cycle_notifications": False,  # Daily report notification push (default off, enable after connecting to enterprise WeChat)
    "enable_gap_llm": False,                    # gap_scan LLM enhancement (default off, zero LLM design)
}

_flags = None
_last_load = 0
_RELOAD_INTERVAL = 10  # 10 seconds reload

def load_flags() -> Dict[str, bool]:
    global _flags, _last_load
    now = time.time()
    if _flags is not None and now - _last_load < _RELOAD_INTERVAL:
        return _flags
    
    if FLAG_FILE.exists():
        try:
            saved = json.loads(FLAG_FILE.read_text(encoding="utf-8"))
            _flags = {**DEFAULT_FLAGS, **saved}
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("Failed to load feature flags: %s", e, exc_info=True)
            _flags = dict(DEFAULT_FLAGS)
    else:
        _flags = dict(DEFAULT_FLAGS)
        save_flags(_flags)
    
    _last_load = now
    return _flags

def save_flags(flags: Dict[str, bool]) -> None:
    FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FLAG_FILE.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")

def is_enabled(feature: str) -> bool:
    flags = load_flags()
    return flags.get(feature, False)

def set_flag(feature: str, enabled: bool) -> bool:
    flags = load_flags()
    old_value = flags.get(feature, None)
    flags[feature] = enabled
    save_flags(flags)
    global _flags
    _flags = flags
    _last_load = time.time()
    logger.info(f"[FeatureFlag] {feature} = {enabled}")

    # v2.1: Broadcast change event via WebSocket
    _broadcast_change(feature, old_value, enabled)

    return True


def _broadcast_change(flag_name: str, old_value, new_value: bool):
    """Broadcast flag change to WebSocket clients."""
    try:
        from src.api.feature_flags_ws import broadcast_flag_change
        import asyncio
        # Try to run in existing event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_flag_change(flag_name, old_value, new_value))
        except RuntimeError:
            # No running event loop (when called synchronously)
            pass
    except ImportError:
        pass
    except Exception as e:  # TODO: Narrow exception type
        logger.debug(f"[FeatureFlag] WebSocket broadcast failed: {e}")

def get_all_flags() -> Dict[str, Any]:
    flags = load_flags()
    return {
        "flags": flags,
        "last_reload": _last_load,
        "reload_interval_sec": _RELOAD_INTERVAL
    }
