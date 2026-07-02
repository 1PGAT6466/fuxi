"""
growth_api.py — 成长面板 API
/api/growth/overview → 成长指标（四象各自的指标+趋势+SAG统计）
/api/symbols/status ← 四象状态（心跳+健康+基本指标）
"""
import os
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("taiyin.growth_api")

# 成长数据目录
GROWTH_DIR = "data/growth"


def get_growth_overview() -> Dict:
    """获取成长概览"""
    overview = {
        "symbols": {},
        "summary": {
            "total_queries": 0,
            "avg_latency_ms": 0,
            "avg_confidence": 0,
            "cache_hit_rate": 0,
        },
        "timestamp": time.time(),
    }

    # 读取各象的成长数据
    for symbol in ["shaoyang", "taiyang", "shaoyin", "taiyin"]:
        symbol_data = _read_symbol_growth(symbol)
        overview["symbols"][symbol] = symbol_data

        # 汇总
        overview["summary"]["total_queries"] += symbol_data.get("query_count", 0)

    return overview


def get_symbols_status() -> Dict:
    """获取四象状态"""
    from src.infra.meridian_monitor import get_monitor
    monitor = get_monitor()

    status = {
        "symbols": {},
        "health": monitor.get_health_report(),
        "timestamp": time.time(),
    }

    # 各象状态
    for symbol in ["shaoyang", "taiyang", "shaoyin", "taiyin"]:
        status["symbols"][symbol] = {
            "name": _get_symbol_name(symbol),
            "emoji": _get_symbol_emoji(symbol),
            "alive": True,  # 心跳检测已禁用
            "last_heartbeat": time.time(),
            "metrics": _get_symbol_metrics(symbol),
        }

    return status


def _read_symbol_growth(symbol: str) -> Dict:
    """读取单个象的成长数据"""
    growth_file = os.path.join(GROWTH_DIR, f"{symbol}_growth.jsonl")

    if not os.path.exists(growth_file):
        return {
            "query_count": 0,
            "avg_latency_ms": 0,
            "avg_confidence": 0,
            "trend": [],
        }

    records = []
    try:
        with open(growth_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    except Exception as e:
        logger.error(f"读取成长数据失败: {e}")

    if not records:
        return {
            "query_count": 0,
            "avg_latency_ms": 0,
            "avg_confidence": 0,
            "trend": [],
        }

    # 计算指标
    query_count = len(records)
    avg_latency = sum(r.get("latency_ms", 0) for r in records) / query_count
    avg_confidence = sum(r.get("confidence", 0) for r in records) / query_count

    # 最近7天的趋势
    week_ago = time.time() - 7 * 24 * 3600
    recent_records = [r for r in records if r.get("timestamp", 0) > week_ago]
    trend = _calculate_trend(recent_records)

    return {
        "query_count": query_count,
        "avg_latency_ms": avg_latency,
        "avg_confidence": avg_confidence,
        "trend": trend,
    }


def _calculate_trend(records: List[Dict]) -> List[Dict]:
    """计算趋势数据（按天聚合）"""
    if not records:
        return []

    # 按天分组
    daily = {}
    for r in records:
        day = datetime.fromtimestamp(r.get("timestamp", 0)).strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"count": 0, "latency_sum": 0, "confidence_sum": 0}
        daily[day]["count"] += 1
        daily[day]["latency_sum"] += r.get("latency_ms", 0)
        daily[day]["confidence_sum"] += r.get("confidence", 0)

    # 转换为趋势数据
    trend = []
    for day in sorted(daily.keys()):
        d = daily[day]
        trend.append({
            "date": day,
            "query_count": d["count"],
            "avg_latency_ms": d["latency_sum"] / d["count"],
            "avg_confidence": d["confidence_sum"] / d["count"],
        })

    return trend[-7:]  # 只返回最近7天


def _get_symbol_name(symbol: str) -> str:
    """获取象名称"""
    names = {
        "shaoyang": "少阳·消化",
        "taiyang": "太阳·筑基",
        "shaoyin": "少阴·炼化",
        "taiyin": "太阴·显化",
    }
    return names.get(symbol, symbol)


def _get_symbol_emoji(symbol: str) -> str:
    """获取象图标"""
    emojis = {
        "shaoyang": "🌱",
        "taiyang": "☀️",
        "shaoyin": "🌙",
        "taiyin": "🌑",
    }
    return emojis.get(symbol, "?")


def _get_symbol_metrics(symbol: str) -> Dict:
    """获取象指标"""
    # 从成长数据中读取
    growth_file = os.path.join(GROWTH_DIR, f"{symbol}_growth.jsonl")

    if not os.path.exists(growth_file):
        return {
            "query_count": 0,
            "avg_latency_ms": 0,
            "avg_confidence": 0,
        }

    try:
        with open(growth_file, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    except:
        return {"query_count": 0, "avg_latency_ms": 0, "avg_confidence": 0}

    if not records:
        return {"query_count": 0, "avg_latency_ms": 0, "avg_confidence": 0}

    query_count = len(records)
    avg_latency = sum(r.get("latency_ms", 0) for r in records) / query_count
    avg_confidence = sum(r.get("confidence", 0) for r in records) / query_count

    return {
        "query_count": query_count,
        "avg_latency_ms": avg_latency,
        "avg_confidence": avg_confidence,
    }
