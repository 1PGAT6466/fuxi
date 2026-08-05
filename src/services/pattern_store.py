"""
pattern_store.py — 语义模式库（v2.0 新增）

基于 self-improving-agent 的多记忆架构：
- 语义记忆：可复用的知识模式（跨上下文）
- 情景记忆：具体经历和结果
- 工作记忆：当前会话上下文

灵感来源：
- SimpleMem: Efficient Lifelong Memory for LLM Agents
- Multi-Memory Survey (ACM 2025)
- Evo-Memory: DeepMind's Benchmark
"""

import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

PATTERNS_DIR = Path(DATA_DIR) / "patterns"
PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

# ── 语义模式库（抽象知识，跨上下文可复用）──
SEMANTIC_FILE = PATTERNS_DIR / "semantic_patterns.json"

# ── 情景记忆库（具体经历，带时间戳和结果）──
EPISODIC_DIR = PATTERNS_DIR / "episodic"
EPISODIC_DIR.mkdir(parents=True, exist_ok=True)

# ── 进化日志（可追溯的变更记录）──
EVOLUTION_LOG = PATTERNS_DIR / "evolution_log.jsonl"

# ── 模式置信度阈值 ──
CONFIDENCE_THRESHOLD = 0.6  # 低于此值的模式不推荐
AUTO_ADD_THRESHOLD = 0.9    # 高于此值的模式自动应用

_pattern_lock = threading.Lock()


def _load_semantic() -> Dict:
    """加载语义模式库"""
    if SEMANTIC_FILE.exists():
        try:
            return json.loads(SEMANTIC_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[PatternStore] 加载语义模式失败: {e}")
    return {"patterns": {}, "version": "2.0", "updated": time.time()}


def _save_semantic(data: Dict):
    """保存语义模式库"""
    data["updated"] = time.time()
    SEMANTIC_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_pattern(
    name: str,
    category: str,
    pattern: str,
    solution: str,
    source: str = "implementation",
    confidence: float = 0.8,
    target_skills: Optional[List[str]] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """记录一个新发现的语义模式

    Args:
        name: 模式名称（简短描述）
        category: 分类（retrieval/generation/security/performance/ux）
        pattern: 问题模式描述
        solution: 解决方案
        source: 来源（user_feedback/implementation_review/retrospective/error_fix）
        confidence: 初始置信度（0-1）
        target_skills: 适用的技能/模块列表
        metadata: 附加元数据

    Returns:
        模式记录
    """
    import hashlib
    pat_id = hashlib.md5(f"{name}{category}{time.time()}".encode()).hexdigest()[:12]
    pat_id = f"pat-{time.strftime('%Y%m%d')}-{pat_id}"

    entry = {
        "id": pat_id,
        "name": name,
        "category": category,
        "pattern": pattern,
        "solution": solution,
        "source": source,
        "confidence": confidence,
        "applications": 0,
        "successes": 0,
        "failures": 0,
        "created": time.strftime("%Y-%m-%d"),
        "last_used": None,
        "target_skills": target_skills or [],
        "metadata": metadata or {},
    }

    with _pattern_lock:
        data = _load_semantic()
        data["patterns"][pat_id] = entry
        _save_semantic(data)

    # 记录进化日志
    _log_evolution("pattern_created", pat_id, entry)

    logger.info(f"[PatternStore] 新模式: {pat_id} ({name})")
    return entry


def apply_pattern(pat_id: str, success: bool = True):
    """记录模式的应用结果，更新置信度"""
    with _pattern_lock:
        data = _load_semantic()
        pat = data["patterns"].get(pat_id)
        if not pat:
            return

        pat["applications"] += 1
        pat["last_used"] = time.strftime("%Y-%m-%d")

        if success:
            pat["successes"] += 1
            # 置信度贝叶斯更新：成功时微增
            pat["confidence"] = min(1.0, pat["confidence"] + 0.02)
        else:
            pat["failures"] += 1
            # 失败时降低置信度
            pat["confidence"] = max(0.0, pat["confidence"] - 0.05)

        _save_semantic(data)


def get_patterns(
    category: Optional[str] = None,
    min_confidence: float = CONFIDENCE_THRESHOLD,
    limit: int = 20,
) -> List[Dict]:
    """获取推荐的语义模式"""
    data = _load_semantic()
    patterns = list(data.get("patterns", {}).values())

    # 过滤
    if category:
        patterns = [p for p in patterns if p.get("category") == category]
    patterns = [p for p in patterns if p.get("confidence", 0) >= min_confidence]

    # 排序：置信度 × 应用次数
    patterns.sort(
        key=lambda p: p.get("confidence", 0) * (1 + p.get("applications", 0) * 0.1),
        reverse=True,
    )

    return patterns[:limit]


def get_pattern_by_id(pat_id: str) -> Optional[Dict]:
    """获取单个模式"""
    data = _load_semantic()
    return data.get("patterns", {}).get(pat_id)


def search_patterns(query: str, limit: int = 5) -> List[Dict]:
    """搜索相关模式（关键词匹配 + 置信度排序）"""
    data = _load_semantic()
    patterns = list(data.get("patterns", {}).values())

    # 关键词匹配
    query_lower = query.lower()
    scored = []
    for pat in patterns:
        score = 0
        text = f"{pat.get('name', '')} {pat.get('pattern', '')} {pat.get('solution', '')}".lower()
        for word in query_lower.split():
            if len(word) >= 2 and word in text:
                score += 1
        if score > 0:
            scored.append((score, pat))

    scored.sort(key=lambda x: (x[0], x[1].get("confidence", 0)), reverse=True)
    return [p for _, p in scored[:limit]]


# ── 情景记忆 ──

def record_episode(
    skill: str,
    situation: str,
    action: str,
    outcome: str,
    lesson: str,
    related_pattern: Optional[str] = None,
    user_feedback: Optional[Dict] = None,
) -> Dict:
    """记录一次具体经历（情景记忆）"""
    episode = {
        "id": f"ep-{time.strftime('%Y%m%d-%H%M%S')}",
        "timestamp": time.time(),
        "skill": skill,
        "situation": situation,
        "action": action,
        "outcome": outcome,
        "lesson": lesson,
        "related_pattern": related_pattern,
        "user_feedback": user_feedback,
    }

    # 写入按日期分文件
    date_str = time.strftime("%Y-%m-%d")
    ep_file = EPISODIC_DIR / f"{date_str}.jsonl"
    with open(ep_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(episode, ensure_ascii=False) + "\n")

    # 记录进化日志
    _log_evolution("episode_recorded", episode["id"], {
        "skill": skill, "outcome": outcome, "lesson": lesson
    })

    logger.info(f"[PatternStore] 情景记录: {episode['id']} ({skill})")
    return episode


def get_recent_episodes(days: int = 7, skill: Optional[str] = None) -> List[Dict]:
    """获取最近 N 天的情景记忆"""
    episodes = []
    for i in range(days):
        date_str = (time.time() - i * 86400)
        date_str = time.strftime("%Y-%m-%d", time.localtime(date_str))
        ep_file = EPISODIC_DIR / f"{date_str}.jsonl"
        if ep_file.exists():
            for line in ep_file.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        ep = json.loads(line)
                        if skill and ep.get("skill") != skill:
                            continue
                        episodes.append(ep)
                    except json.JSONDecodeError:
                        continue
    return episodes


# ── 进化日志 ──

def _log_evolution(event_type: str, target_id: str, details: Dict):
    """记录进化事件（可追溯）"""
    entry = {
        "timestamp": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event_type,
        "target": target_id,
        "details": details,
    }
    with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_evolution_log(limit: int = 50) -> List[Dict]:
    """获取进化日志"""
    if not EVOLUTION_LOG.exists():
        return []
    lines = EVOLUTION_LOG.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in lines[-limit:]:
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


# ── 统计 ──

def get_pattern_stats() -> Dict:
    """获取模式库统计"""
    data = _load_semantic()
    patterns = list(data.get("patterns", {}).values())

    categories = defaultdict(int)
    total_apps = 0
    total_confidence = 0
    for p in patterns:
        categories[p.get("category", "unknown")] += 1
        total_apps += p.get("applications", 0)
        total_confidence += p.get("confidence", 0)

    avg_confidence = total_confidence / len(patterns) if patterns else 0

    return {
        "total_patterns": len(patterns),
        "categories": dict(categories),
        "total_applications": total_apps,
        "average_confidence": round(avg_confidence, 3),
        "high_confidence": len([p for p in patterns if p.get("confidence", 0) >= AUTO_ADD_THRESHOLD]),
    }
