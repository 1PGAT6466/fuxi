"""
trend_analyzer.py — 趋势分析引擎（v2.0 新增）

从 JSONL 日志中提取时间序列，计算趋势方向和变化率。
支持按小时/天/周聚合，移动平均，趋势检测。

数据来源：
- request_metrics: 请求延迟、QPS、错误率
- online_eval: 检索质量指标
- feedback_store: 用户反馈统计
- evaluation: 评测结果
"""

import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

TREND_DIR = Path(DATA_DIR) / "trends"
TREND_DIR.mkdir(parents=True, exist_ok=True)


def _read_jsonl(filepath: Path, days: int = 7) -> List[Dict]:
    """读取 JSONL 文件最近 N 天的数据"""
    entries = []
    if not filepath.exists():
        return entries
    cutoff = time.time() - days * 86400
    try:
        for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("timestamp", 0) >= cutoff:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return entries


def _aggregate_by_period(
    entries: List[Dict],
    value_key: str,
    period: str = "hour",
) -> List[Tuple[str, float, int]]:
    """按时间段聚合数据

    Returns:
        [(period_label, avg_value, count), ...]
    """
    buckets = defaultdict(list)
    for e in entries:
        ts = e.get("timestamp", 0)
        val = e.get(value_key)
        if val is None or not isinstance(val, (int, float)):
            continue
        dt = datetime.fromtimestamp(ts)
        if period == "hour":
            label = dt.strftime("%Y-%m-%d %H:00")
        elif period == "day":
            label = dt.strftime("%Y-%m-%d")
        elif period == "week":
            label = dt.strftime("%Y-W%W")
        else:
            label = dt.strftime("%Y-%m-%d %H:00")
        buckets[label].append(val)

    result = []
    for label in sorted(buckets.keys()):
        vals = buckets[label]
        avg = sum(vals) / len(vals)
        result.append((label, round(avg, 3), len(vals)))
    return result


def _moving_average(values: List[float], window: int = 3) -> List[float]:
    """计算移动平均"""
    if len(values) < window:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        avg = sum(values[start:i + 1]) / (i - start + 1)
        result.append(round(avg, 3))
    return result


def _detect_direction(values: List[float]) -> str:
    """检测趋势方向：up / down / flat"""
    if len(values) < 2:
        return "flat"
    # 用最后 30% 的数据判断趋势
    n = max(2, len(values) // 3)
    recent = values[-n:]
    if len(recent) < 2:
        return "flat"
    # 线性回归斜率
    x = list(range(len(recent)))
    x_mean = sum(x) / len(x)
    y_mean = sum(recent) / len(recent)
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, recent))
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    if denominator == 0:
        return "flat"
    slope = numerator / denominator
    # 斜率相对于均值的比例
    if y_mean == 0:
        return "flat"
    relative_slope = abs(slope) / abs(y_mean)
    if relative_slope < 0.05:
        return "flat"
    return "up" if slope > 0 else "down"


def _compute_change_pct(values: List[float]) -> float:
    """计算变化百分比（最近值 vs 最早值）"""
    if len(values) < 2:
        return 0.0
    first = values[0]
    last = values[-1]
    if first == 0:
        return 0.0
    return round((last - first) / abs(first) * 100, 1)


def get_trend(metric_name: str, days: int = 7, period: str = "hour") -> Dict:
    """获取指定指标的趋势数据

    Args:
        metric_name: 指标名（latency_ms / error_rate / qps / search_score / feedback_count）
        days: 回溯天数
        period: 聚合粒度（hour / day / week）

    Returns:
        {
            "metric": metric_name,
            "period": period,
            "values": [{"time": "...", "value": ..., "count": ...}, ...],
            "direction": "up/down/flat",
            "change_pct": 12.5,
            "moving_avg": [...],
            "current": 最新值,
            "baseline": 历史均值,
        }
    """
    # 确定数据源
    source_files = {
        "latency_ms": Path(DATA_DIR) / "request_metrics.jsonl",
        "error_rate": Path(DATA_DIR) / "request_metrics.jsonl",
        "qps": Path(DATA_DIR) / "request_metrics.jsonl",
        "search_score": Path(DATA_DIR) / "online_eval" / "search_metrics.jsonl",
        "feedback_count": Path(DATA_DIR) / "feedback_data" / "feedback_log.jsonl",
    }

    filepath = source_files.get(metric_name)
    if not filepath:
        return {"metric": metric_name, "error": f"未知指标: {metric_name}"}

    entries = _read_jsonl(filepath, days)
    if not entries:
        # 无历史数据，返回空
        return {
            "metric": metric_name,
            "period": period,
            "values": [],
            "direction": "flat",
            "change_pct": 0.0,
            "moving_avg": [],
            "current": 0,
            "baseline": 0,
        }

    # 聚合
    aggregated = _aggregate_by_period(entries, metric_name, period)
    values = [v for _, v, _ in aggregated]
    times = [t for t, _, _ in aggregated]
    counts = [c for _, _, c in aggregated]

    # 趋势分析
    direction = _detect_direction(values)
    change_pct = _compute_change_pct(values)
    ma = _moving_average(values, window=3)

    # 保存趋势快照
    _save_trend_snapshot(metric_name, {
        "timestamp": time.time(),
        "metric": metric_name,
        "direction": direction,
        "change_pct": change_pct,
        "current": values[-1] if values else 0,
        "baseline": sum(values) / len(values) if values else 0,
    })

    return {
        "metric": metric_name,
        "period": period,
        "values": [{"time": t, "value": v, "count": c} for t, v, c in aggregated],
        "direction": direction,
        "change_pct": change_pct,
        "moving_avg": ma,
        "current": values[-1] if values else 0,
        "baseline": round(sum(values) / len(values), 3) if values else 0,
    }


def get_all_trends(days: int = 7) -> Dict:
    """获取所有指标的趋势概览"""
    metrics = ["latency_ms", "error_rate", "qps", "search_score", "feedback_count"]
    trends = {}
    for m in metrics:
        trends[m] = get_trend(m, days)
    return trends


def _save_trend_snapshot(metric_name: str, data: Dict):
    """保存趋势快照（用于历史对比）"""
    snapshot_file = TREND_DIR / f"{metric_name}_snapshots.jsonl"
    try:
        with open(snapshot_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except OSError:
        pass
