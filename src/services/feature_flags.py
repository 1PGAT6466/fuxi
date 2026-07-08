"""
feature_flags.py — Phase 5.0.3: Feature Flag 服务
支持秒级回滚，不重启切换功能
"""
import json, time, logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("feature_flags")

from src.config import DATA_DIR
FLAG_FILE = Path(DATA_DIR) / "feature_flags.json"

DEFAULT_FLAGS = {
    # 核心Flag（必须独立控制）
    "shaoyang_sag_extract": True,        # SAG式事件/实体提取（已默认开启）
    "taiyang_multi_hop": True,           # SAG式多跳检索（已默认开启）
    "taiyang_seed_score": True,          # SAG式 seed_score 融合（已默认开启）

    # Phase B 新增 Flag（伏羲检索架构融合）
    "taiyang_sag_pipeline": True,        # SAG 三阶段管线总开关（ADR-001，任务 3）
    "taiyang_path_a": True,              # Path A: 实体引导召回（ADR-002，任务 2）
    "taiyang_event_search": True,        # Event 粒度检索（ADR-003，任务 1）
    "taiyang_sql_multi_hop": True,       # SQL JOIN 多跳扩展 H=1（任务 3）

    # 增强Flag（一键控制）
    "enhanced_pipeline": False,          # 包含：query_rewrite/hyde/self_check/crag/context_compress

    # 基础Flag
    "graphrag_multi_hop": False,
    "query_planner": False,
    "table_structured_search": False,
    "multimodal_rag": False,
    "sentence_level_compress": False,
    "knowledge_lifecycle": False,
    "siliconflow_rerank": False,
    "self_rag_check": True,              # 以 services/feature_flags.py 为准（原 taiyin 为 False）
    "crag_rewrite": True,                # 以 services/feature_flags.py 为准（原 taiyin 为 False）
    "query_rewrite": False,
    "hyde": False,
    "wiki_search": False,
    "table_view": False,
    "session_memory": False,
}

_flags = None
_last_load = 0
_RELOAD_INTERVAL = 10  # 10 秒重新加载

def load_flags() -> Dict[str, bool]:
    global _flags, _last_load
    now = time.time()
    if _flags is not None and now - _last_load < _RELOAD_INTERVAL:
        return _flags
    
    if FLAG_FILE.exists():
        try:
            saved = json.loads(FLAG_FILE.read_text(encoding="utf-8"))
            _flags = {**DEFAULT_FLAGS, **saved}
        except Exception as e:
            logger.warning("加载 feature flags 失败: %s", e, exc_info=True)
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

    # v2.1: 通过 WebSocket 广播变更事件
    _broadcast_change(feature, old_value, enabled)

    return True


def _broadcast_change(flag_name: str, old_value, new_value: bool):
    """广播 flag 变更到 WebSocket 客户端"""
    try:
        from src.api.feature_flags_ws import broadcast_flag_change
        import asyncio
        # 尝试在现有事件循环中运行
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_flag_change(flag_name, old_value, new_value))
        except RuntimeError:
            # 没有运行中的事件循环（同步调用时）
            pass
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"[FeatureFlag] WebSocket 广播失败: {e}")

def get_all_flags() -> Dict[str, Any]:
    flags = load_flags()
    return {
        "flags": flags,
        "last_reload": _last_load,
        "reload_interval_sec": _RELOAD_INTERVAL
    }
