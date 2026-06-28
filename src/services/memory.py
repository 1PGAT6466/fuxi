"""P3.5: 记忆系统 — 自动记录 + 30d TTL + 操作经验积累"""
import json, os, time
from datetime import datetime, timedelta
from pathlib import Path

from src.config import DATA_DIR
import logging; logger = logging.getLogger(__name__)

MEMORY_DIR = str(DATA_DIR / "memory")
TTL_DAYS = 30  # 操作记忆保留天数

def init_memory():
    """初始化记忆目录"""
    Path(MEMORY_DIR).mkdir(parents=True, exist_ok=True)
    # 确保 memory.json 存在
    mem_file = os.path.join(MEMORY_DIR, 'memory.json')
    if not os.path.exists(mem_file):
        with open(mem_file, 'w', encoding='utf-8') as f:
            json.dump({"experiences": [], "preferences": {}, "stats": {}}, f, ensure_ascii=False)

def record_experience(action: str, detail: str, outcome: str = "ok", tags: list = None):
    """P3.5: 记录操作经验"""
    init_memory()
    mem_file = os.path.join(MEMORY_DIR, 'memory.json')
    
    try:
        with open(mem_file, 'r', encoding='utf-8') as f:
            mem = json.load(f)
    except Exception:
        mem = {"experiences": [], "preferences": {}, "stats": {}}
    
    mem["experiences"].append({
        "action": action,
        "detail": detail[:500],
        "outcome": outcome,
        "tags": tags or [],
        "timestamp": datetime.now().isoformat(),
        "ttl_days": TTL_DAYS,
    })
    
    # 限制最多 1000 条
    if len(mem["experiences"]) > 1000:
        mem["experiences"] = mem["experiences"][-1000:]
    
    with open(mem_file, 'w', encoding='utf-8') as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def cleanup_expired():
    """P3.5: 清理过期记忆（超过 TTL_DAYS 天）"""
    init_memory()
    mem_file = os.path.join(MEMORY_DIR, 'memory.json')
    
    try:
        with open(mem_file, 'r', encoding='utf-8') as f:
            mem = json.load(f)
    except Exception:
        return 0
    
    cutoff = datetime.now() - timedelta(days=TTL_DAYS)
    old_count = len(mem.get("experiences", []))
    
    mem["experiences"] = [
        e for e in mem.get("experiences", [])
        if datetime.fromisoformat(e.get("timestamp", "2000-01-01")) > cutoff
    ]
    
    removed = old_count - len(mem["experiences"])
    if removed > 0:
        with open(mem_file, 'w', encoding='utf-8') as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    
    return removed

def get_recent_experiences(limit: int = 10, action_filter: str = None) -> list:
    """P3.5: 获取最近经验"""
    init_memory()
    mem_file = os.path.join(MEMORY_DIR, 'memory.json')
    
    try:
        with open(mem_file, 'r', encoding='utf-8') as f:
            mem = json.load(f)
    except Exception:
        return []
    
    exps = mem.get("experiences", [])
    if action_filter:
        exps = [e for e in exps if action_filter.lower() in e.get("action", "").lower()]
    
    return sorted(exps, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

def get_memory_stats() -> dict:
    """P3.5: 记忆统计"""
    init_memory()
    mem_file = os.path.join(MEMORY_DIR, 'memory.json')
    
    try:
        with open(mem_file, 'r', encoding='utf-8') as f:
            mem = json.load(f)
    except Exception:
        return {"total": 0, "health": "unknown"}
    
    exps = mem.get("experiences", [])
    from collections import Counter
    actions = Counter(e.get("action", "?") for e in exps)
    
    return {
        "total_experiences": len(exps),
        "top_actions": dict(actions.most_common(5)),
        "oldest": exps[0].get("timestamp", "N/A") if exps else "N/A",
        "newest": exps[-1].get("timestamp", "N/A") if exps else "N/A",
        "ttl_days": TTL_DAYS,
    }


# 初始化
init_memory()

# 记录一条 Phase 2 完成的经验
record_experience(
    action="phase2_complete",
    detail="P2.1 Qdrant + P2.2 Redis + P2.3 分层存储 + P2.4 评测 + P2.5 Agent工具链 + P2.6 多模态转录 全部完成",
    outcome="ok",
    tags=["phase2", "infrastructure", "milestone"]
)

stats = get_memory_stats()
print(f"P3.5 记忆系统已初始化")
print(f"  记忆条数: {stats['total_experiences']}")
print(f"  TTL: {stats['ttl_days']}天")
