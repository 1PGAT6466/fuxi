"""
feature_flags.py 鈥?Phase 5.0.3: Feature Flag 鏈嶅姟
鏀寔绉掔骇鍥炴粴锛屼笉閲嶅惎鍒囨崲鍔熻兘
"""
import json, time, logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("feature_flags")

from src.config import DATA_DIR
FLAG_FILE = Path(DATA_DIR) / "feature_flags.json"

DEFAULT_FLAGS = {
    # 鏍稿績Flag锛堝繀椤荤嫭绔嬫帶鍒讹級
    "shaoyang_sag_extract": True,        # SAG寮忎簨浠?瀹炰綋鎻愬彇锛堝凡榛樿寮€鍚級
    "taiyang_multi_hop": True,           # SAG寮忓璺虫绱紙宸查粯璁ゅ紑鍚級
    "taiyang_seed_score": True,          # SAG寮?seed_score 铻嶅悎锛堝凡榛樿寮€鍚級

    # Phase B 鏂板 Flag锛堜紡缇叉绱㈡灦鏋勮瀺鍚堬級
    "taiyang_sag_pipeline": True,        # SAG 涓夐樁娈电绾挎€诲紑鍏筹紙ADR-001锛屼换鍔?3锛?
    "taiyang_path_a": True,              # Path A: 瀹炰綋寮曞鍙洖锛圓DR-002锛屼换鍔?2锛?
    "taiyang_event_search": True,        # Event 绮掑害妫€绱紙ADR-003锛屼换鍔?1锛?
    "taiyang_sql_multi_hop": True,       # SQL JOIN 澶氳烦鎵╁睍 H=1锛堜换鍔?3锛?

    # 澧炲己Flag锛堜竴閿帶鍒讹級
    "enhanced_pipeline": False,          # 鍖呭惈锛歲uery_rewrite/hyde/self_check/crag/context_compress

    # 鍩虹Flag
    "graphrag_multi_hop": False,
    "query_planner": False,
    "table_structured_search": False,
    "multimodal_rag": False,
    "sentence_level_compress": False,
    "knowledge_lifecycle": False,
    "siliconflow_rerank": False,
    "self_rag_check": True,              # 浠?services/feature_flags.py 涓哄噯锛堝師 taiyin 涓?False锛?
    "crag_rewrite": True,                # 浠?services/feature_flags.py 涓哄噯锛堝師 taiyin 涓?False锛?
    "query_rewrite": True,
    "hyde": False,
    "wiki_search": False,
    "table_view": False,
    "session_memory": False,

    # v1.50 Phase C: Dream Cycle
    "enable_dream_cycle_notifications": False,  # 鏃ユ姤閫氱煡鎺ㄩ€侊紙榛樿鍏抽棴锛屽悗缁帴鍏ラ涔?浼佸井鍚庡紑鍚級
    "enable_gap_llm": False,                    # gap_scan LLM 澧炲己锛堥粯璁ゅ叧闂紝闆?LLM 璁捐锛?
}

_flags = None
_last_load = 0
_RELOAD_INTERVAL = 10  # 10 绉掗噸鏂板姞杞?

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
            logger.warning("鍔犺浇 feature flags 澶辫触: %s", e, exc_info=True)
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

    # v2.1: 閫氳繃 WebSocket 骞挎挱鍙樻洿浜嬩欢
    _broadcast_change(feature, old_value, enabled)

    return True


def _broadcast_change(flag_name: str, old_value, new_value: bool):
    """骞挎挱 flag 鍙樻洿鍒?WebSocket 瀹㈡埛绔?""
    try:
        from src.api.feature_flags_ws import broadcast_flag_change
        import asyncio
        # 灏濊瘯鍦ㄧ幇鏈変簨浠跺惊鐜腑杩愯
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_flag_change(flag_name, old_value, new_value))
        except RuntimeError:
            # 娌℃湁杩愯涓殑浜嬩欢寰幆锛堝悓姝ヨ皟鐢ㄦ椂锛?
            pass
    except ImportError:
        pass
    except Exception as e:  # TODO: Narrow exception type
        logger.debug(f"[FeatureFlag] WebSocket 骞挎挱澶辫触: {e}")

def get_all_flags() -> Dict[str, Any]:
    flags = load_flags()
    return {
        "flags": flags,
        "last_reload": _last_load,
        "reload_interval_sec": _RELOAD_INTERVAL
    }








