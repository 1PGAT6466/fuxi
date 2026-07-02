"""
knowledge_lifecycle.py — 知识生命周期管理
实体未找到/同义词未关联/图谱缺失关系
"""
import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("services.knowledge_lifecycle")

LIFECYCLE_DIR = Path("data/knowledge_lifecycle")


class KnowledgeLifecycle:
    """知识生命周期管理"""

    TRIGGER_CONDITIONS = {
        "entity_not_found": {"threshold": 10, "period_days": 7},
        "synonym_variant": {"threshold": 5, "period_days": 7},
        "missing_relation": {"threshold": 3, "period_days": 7},
        "empty_result": {"threshold": 20, "period_days": 7},
        "user_doubt": {"threshold": 5, "period_days": 7},
    }

    CONFIDENCE_LEVELS = {
        "high": {"min": 0.9, "action": "auto_add"},
        "medium": {"min": 0.7, "action": "pending_queue"},
        "low": {"min": 0.0, "action": "ignore"},
    }

    def __init__(self):
        LIFECYCLE_DIR.mkdir(parents=True, exist_ok=True)
        self._events: List[Dict] = []

    async def record_event(self, event_type: str, data: Dict):
        """记录知识生命周期事件"""
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
        }

        self._events.append(event)

        # 写入日志
        try:
            log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[Lifecycle] 写入失败: {e}")

    async def check_triggers(self) -> List[Dict]:
        """检查触发条件"""
        triggers = []

        for event_type, config in self.TRIGGER_CONDITIONS.items():
            count = await self._count_events(event_type, config["period_days"])
            if count >= config["threshold"]:
                triggers.append({
                    "event_type": event_type,
                    "count": count,
                    "threshold": config["threshold"],
                    "period_days": config["period_days"],
                })

        return triggers

    async def get_candidates(self, event_type: str) -> List[Dict]:
        """获取候选知识"""
        log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"

        if not log_file.exists():
            return []

        candidates = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        candidates.append(event.get("data", {}))
                    except:
                        pass
        except Exception:
            pass

        return candidates

    async def _count_events(self, event_type: str, period_days: int) -> int:
        """统计事件数量"""
        log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"

        if not log_file.exists():
            return 0

        count = 0
        cutoff = time.time() - period_days * 86400

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        if event.get("timestamp", 0) > cutoff:
                            count += 1
                    except:
                        pass
        except Exception:
            pass

        return count

    def classify_confidence(self, confidence: float) -> str:
        """分类置信度"""
        if confidence >= self.CONFIDENCE_LEVELS["high"]["min"]:
            return "high"
        elif confidence >= self.CONFIDENCE_LEVELS["medium"]["min"]:
            return "medium"
        else:
            return "low"


# 全局实例
_lifecycle: Optional[KnowledgeLifecycle] = None


def get_knowledge_lifecycle() -> KnowledgeLifecycle:
    """获取全局知识生命周期实例"""
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = KnowledgeLifecycle()
    return _lifecycle
