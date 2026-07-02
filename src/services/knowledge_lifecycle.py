"""
knowledge_lifecycle.py — Phase 8.7: 知识生命周期管理
知识入库 → 活跃 → 衰退 → 反刍/淘汰
"""
import json, os, time, logging
from typing import List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger("knowledge_lifecycle")
LIFECYCLE_FILE = os.path.join(os.path.dirname(__file__), "../../data/knowledge_lifecycle.json")

STAGES = ["incubating", "active", "stable", "declining", "archived", "reborn"]

def load_lifecycle() -> dict:
    if os.path.exists(LIFECYCLE_FILE):
        with open(LIFECYCLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"entries": []}

def save_lifecycle(data: dict):
    os.makedirs(os.path.dirname(LIFECYCLE_FILE), exist_ok=True)
    with open(LIFECYCLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_knowledge(entity_id: str, source: str, confidence: float = 0.5) -> Dict:
    """注册新知识"""
    lc = load_lifecycle()
    entry = {
        "entity_id": entity_id,
        "source": source,
        "confidence": confidence,
        "stage": "incubating",
        "created_at": datetime.now().isoformat(),
        "last_accessed": datetime.now().isoformat(),
        "access_count": 0,
        "utility_score": 0.5,
    }
    lc["entries"].append(entry)
    save_lifecycle(lc)
    logger.info(f"[Lifecycle] 新知识入库: {entity_id}")
    return entry

def access_knowledge(entity_id: str) -> Dict:
    """记录知识被访问"""
    lc = load_lifecycle()
    for e in lc["entries"]:
        if e["entity_id"] == entity_id:
            e["access_count"] += 1
            e["last_accessed"] = datetime.now().isoformat()
            # 活跃度提升
            if e["stage"] == "incubating" and e["access_count"] >= 3:
                e["stage"] = "active"
            elif e["stage"] == "declining":
                e["stage"] = "reborn"
            save_lifecycle(lc)
            return e
    return register_knowledge(entity_id, "auto", 0.3)

def decay_check() -> List[Dict]:
    """检查衰退知识（30 天未访问）"""
    lc = load_lifecycle()
    threshold = datetime.now() - timedelta(days=30)
    decaying = []
    
    for e in lc["entries"]:
        if e["stage"] in ("active", "stable"):
            last = datetime.fromisoformat(e["last_accessed"])
            if last < threshold:
                e["stage"] = "declining"
                decaying.append(e)
                logger.info(f"[Lifecycle] 知识衰退: {e['entity_id']}")
    
    if decaying:
        save_lifecycle(lc)
    return decaying

def get_lifecycle_stats() -> Dict:
    """生命周期统计"""
    lc = load_lifecycle()
    stats = {s: 0 for s in STAGES}
    for e in lc["entries"]:
        stats[e["stage"]] = stats.get(e["stage"], 0) + 1
    stats["total"] = len(lc["entries"])
    return stats
