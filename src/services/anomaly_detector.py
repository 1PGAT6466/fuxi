"""
anomaly_detector.py — 异常检测器（v2.0 新增）

基于历史均值 ± 2倍标准差检测异常（Z-score 方法）。
支持延迟异常、错误率异常、检索质量异常。

检测维度：
- 延迟异常：P95 延迟超过历史均值 + 2σ
- 错误率异常：错误率超过历史均值 + 2σ
- 检索质量异常：平均得分低于历史均值 - 2σ
- 反馈异常：dislike 率突然升高
"""

import json
import time
import logging
import math
from typing import Dict, List, Optional
from pathlib import Path
from collections import deque

from src.config import DATA_DIR

logger = logging.getLogger(__name__)


def _load_recent_values(filepath: Path, key: str, max_items: int = 500) -> List[float]:
    """从 JSONL 文件中加载最近 N 条指标值"""
    values = []
    if not filepath.exists():
        return values
    try:
        lines = filepath.read_text(encoding="utf-8").strip().split("\n")
        for line in lines[-max_items:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                val = entry.get(key)
                if val is not None and isinstance(val, (int, float)):
                    values.append(float(val))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return values


def _zscore_anomaly(
    current: float,
    history: List[float],
    threshold: float = 2.0,
    direction: str = "both",
) -> Optional[Dict]:
    """Z-score 异常检测

    Args:
        current: 当前值
        history: 历史值列表
        threshold: Z-score 阈值（默认 2.0，对应 95% 置信区间）
        direction: 检测方向（"both" / "up" / "down"）

    Returns:
        None if normal, or anomaly dict
    """
    if len(history) < 10:
        return None  # 数据不足，无法判断

    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = math.sqrt(variance) if variance > 0 else 0

    if std == 0:
        # 标准差为 0，所有值相同
        if current != mean:
            return {
                "current": current,
                "baseline": mean,
                "std": 0,
                "zscore": float("inf"),
                "severity": "medium",
                "message": f"值从恒定 {mean} 变为 {current}",
            }
        return None

    zscore = (current - mean) / std

    anomaly = None
    if direction in ("both", "up") and zscore > threshold:
        anomaly = {
            "current": round(current, 3),
            "baseline": round(mean, 3),
            "std": round(std, 3),
            "zscore": round(zscore, 2),
            "severity": "high" if zscore > 3 else "medium",
            "message": f"值 {current:.2f} 显著高于基线 {mean:.2f} (Z={zscore:.1f})",
        }
    elif direction in ("both", "down") and zscore < -threshold:
        anomaly = {
            "current": round(current, 3),
            "baseline": round(mean, 3),
            "std": round(std, 3),
            "zscore": round(zscore, 2),
            "severity": "high" if zscore < -3 else "medium",
            "message": f"值 {current:.2f} 显著低于基线 {mean:.2f} (Z={zscore:.1f})",
        }

    return anomaly


def check_anomalies() -> List[Dict]:
    """检查所有指标的异常情况

    Returns:
        [
            {
                "metric": "latency_ms",
                "current": 500.0,
                "baseline": 120.0,
                "zscore": 3.2,
                "severity": "high",
                "message": "...",
                "recommendation": "..."
            },
            ...
        ]
    """
    anomalies = []

    # 检测配置
    checks = [
        {
            "metric": "latency_ms",
            "file": Path(DATA_DIR) / "request_metrics.jsonl",
            "key": "latency_ms",
            "direction": "up",
            "threshold": 2.0,
            "recommendation": "检查是否有慢查询或 LLM 响应超时",
        },
        {
            "metric": "error_rate",
            "file": Path(DATA_DIR) / "request_metrics.jsonl",
            "key": "error_rate",
            "direction": "up",
            "threshold": 2.0,
            "recommendation": "检查服务健康状态和依赖服务可用性",
        },
        {
            "metric": "search_score",
            "file": Path(DATA_DIR) / "online_eval" / "search_metrics.jsonl",
            "key": "avg_score",
            "direction": "down",
            "threshold": 2.0,
            "recommendation": "检查知识库覆盖率和检索模型状态",
        },
    ]

    for check in checks:
        values = _load_recent_values(check["file"], check["key"])
        if not values:
            continue

        current = values[-1]
        history = values[:-1]  # 用前面的数据作为基线

        result = _zscore_anomaly(
            current, history,
            threshold=check["threshold"],
            direction=check["direction"],
        )

        if result:
            result["metric"] = check["metric"]
            result["recommendation"] = check["recommendation"]
            anomalies.append(result)

    return anomalies


def get_anomaly_summary() -> Dict:
    """获取异常检测摘要"""
    anomalies = check_anomalies()

    high = [a for a in anomalies if a.get("severity") == "high"]
    medium = [a for a in anomalies if a.get("severity") == "medium"]

    return {
        "total": len(anomalies),
        "high_severity": len(high),
        "medium_severity": len(medium),
        "anomalies": anomalies,
        "status": "critical" if high else ("warning" if medium else "normal"),
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
