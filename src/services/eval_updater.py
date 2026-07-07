"""
eval_updater.py — 评估集自动更新（P3-5）
每周从搜索日志中抽取高频查询，自动生成/更新 ragas 测试用例。

策略：
  1. 从 search logs 提取最近 7 天的查询
  2. 计算每个查询的频率，降序排列
  3. 优先选取"零结果查询"（反馈差的）作为新测试用例
  4. 合并已有手动测试用例，不去重
"""
import json, time
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

from src.config import LOG_DIR, DATA_DIR

EVAL_CASES_FILE = DATA_DIR / "evaluation" / "ragas_test_cases.json"
MAX_AUTO_CASES = 30  # 最多保留 30 条自动生成用例
UPDATE_INTERVAL_DAYS = 7


def _load_search_logs(days: int = 7) -> list:
    """读取搜索日志（复用 feedback.py 的逻辑）"""
    logs = []
    cutoff = datetime.now() - timedelta(days=days)
    if not LOG_DIR.exists():
        return logs
    for fn in sorted(LOG_DIR.glob("search_*.jsonl"), reverse=True):
        try:
            date_str = fn.stem.replace("search_", "")
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff.replace(hour=0, minute=0, second=0):
                continue
        except ValueError as e:
            logger.warning("ValueError 失败: %s", e, exc_info=True)
        try:
            with open(fn, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        logs.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning("json.JSONDecodeError 失败: %s", e, exc_info=True)
        except Exception as e:
            logger.warning("_load_search_logs 操作失败: %s", e, exc_info=True)
    return logs


def _extract_zero_result_queries(logs: list) -> Counter:
    """从日志提取零结果查询（result_count=0）"""
    c = Counter()
    for entry in logs:
        if entry.get("results", entry.get("result_count", 1)) == 0:
            q = (entry.get("query", "") or "").strip()
            if q and len(q) >= 2:
                c[q] += 1
    return c


def _extract_top_queries(logs: list, top_n: int = 50) -> Counter:
    """从日志提取所有查询频率"""
    c = Counter()
    for entry in logs:
        q = (entry.get("query", "") or "").strip()
        if q and len(q) >= 2:
            c[q] += 1
    return Counter(dict(c.most_common(top_n)))


def generate_test_cases() -> list:
    """生成新的自动测试用例"""
    logs = _load_search_logs(days=UPDATE_INTERVAL_DAYS)
    if not logs:
        logger.info("[eval_updater] No search logs found, skipping auto-update")
        return []
    
    zero_queries = _extract_zero_result_queries(logs)
    top_queries = _extract_top_queries(logs, 50)
    
    new_cases = []
    seen_q = set()
    
    # Priority 1: 零结果查询（差评）
    for q, cnt in zero_queries.most_common(10):
        if q not in seen_q:
            new_cases.append({
                "query": q,
                "source": "auto-zero-result",
                "frequency": cnt,
                "generated_at": datetime.now().isoformat(),
                "tags": ["zero_result"]
            })
            seen_q.add(q)
    
    # Priority 2: 高频查询
    for q, cnt in top_queries.most_common(MAX_AUTO_CASES):
        if q not in seen_q:
            new_cases.append({
                "query": q,
                "source": "auto-high-frequency",
                "frequency": cnt,
                "generated_at": datetime.now().isoformat(),
                "tags": ["high_freq"]
            })
            seen_q.add(q)
    
    # 限制总数
    new_cases = new_cases[:MAX_AUTO_CASES]
    logger.info(f"[eval_updater] Generated {len(new_cases)} test cases from {len(logs)} log entries")
    return new_cases


def update_eval_set() -> dict:
    """更新评估集文件 — 合并手动 + 自动用例"""
    EVAL_CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 加载已有用例
    existing = []
    if EVAL_CASES_FILE.exists():
        try:
            existing = json.loads(EVAL_CASES_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception as e:
            logger.warning("加载评估用例文件失败: %s", e, exc_info=True)
            existing = []
    
    # 保留手动用例（非 auto- 开头的 source）
    manual = [c for c in existing if not c.get("source", "").startswith("auto-")]
    
    # 生成新的自动用例
    auto = generate_test_cases()
    
    # 合并
    merged = manual + auto
    
    # 写入
    EVAL_CASES_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "total": len(merged),
        "manual": len(manual),
        "auto": len(auto),
        "updated_at": datetime.now().isoformat(),
        "file": str(EVAL_CASES_FILE)
    }


def should_update() -> bool:
    """检查是否需要更新（距上次更新 >= 7 天）"""
    if not EVAL_CASES_FILE.exists():
        return True
    try:
        existing = json.loads(EVAL_CASES_FILE.read_text(encoding="utf-8"))
        if not existing:
            return True
        # 检查最新一条 auto case 的时间
        auto_cases = [c for c in existing if c.get("source", "").startswith("auto-")]
        if not auto_cases:
            return True
        latest = max(c.get("generated_at", "") for c in auto_cases)
        if not latest:
            return True
        last_update = datetime.fromisoformat(latest)
        return (datetime.now() - last_update).days >= UPDATE_INTERVAL_DAYS
    except Exception as e:
        logger.warning("should_update 检查失败: %s", e, exc_info=True)
        return True


# ============ CLI ============
if __name__ == "__main__":
    result = update_eval_set()
    print(json.dumps(result, indent=2, ensure_ascii=False))
