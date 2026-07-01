"""
flags.py — 太阴·Feature Flag 管理 (3+1)
核心Flag必须独立控制，增强Flag一键控制
"""
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("taiyin.flags")

FLAGS_FILE = Path("data/feature_flags.json")

DEFAULT_FLAGS = {
    # 核心Flag（必须独立控制）
    "shaoyang_sag_extract": False,    # SAG式事件/实体提取（风险最高）
    "taiyang_multi_hop": False,       # SAG式多跳检索
    "taiyang_seed_score": False,      # SAG式seed_score融合

    # 增强Flag（一键控制）
    "enhanced_pipeline": False,       # 包含：query_rewrite/hyde/self_check/crag/context_compress

    # 基础Flag（保留兼容）
    "query_rewrite": False,
    "hyde": False,
    "self_rag_check": False,
    "crag_rewrite": False,
    "siliconflow_rerank": False,
    "graphrag_multi_hop": False,
    "wiki_search": False,
    "table_view": False,
    "session_memory": False,
}


def load_flags() -> Dict:
    """加载Feature Flags"""
    if FLAGS_FILE.exists():
        try:
            return json.loads(FLAGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_FLAGS)


def save_flags(flags: Dict):
    """保存Feature Flags"""
    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FLAGS_FILE.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")


def set_flag(name: str, value: bool):
    """设置单个Flag"""
    flags = load_flags()
    flags[name] = value
    save_flags(flags)
    logger.info(f"[Flag] {name} = {value}")


def is_enabled(name: str) -> bool:
    """检查Flag是否启用"""
    return load_flags().get(name, DEFAULT_FLAGS.get(name, False))


def get_all_flags() -> Dict:
    """获取所有Flag"""
    return load_flags()
