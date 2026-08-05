"""
成长概览 API — 伏羲 v1.50
============================
提供系统成长指标和四象状态的查询功能。

端点：
  GET /api/growth/overview — 成长概览
"""

import logging

from fastapi import APIRouter, Request
from src.api.response import error, success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["成长概览"])


@router.get("/api/growth/overview")
async def growth_overview(request: Request = None):
    """获取成长概览 — 汇总四象的成长指标

    数据来源：
      - 四象各自的查询次数、平均延迟、平均置信度
      - 最近 7 天的趋势数据
      - SAG 统计
    """
    try:
        from src.taiyin.growth_api import get_growth_overview

        data = get_growth_overview()
        return success(data=data, message="成长概览")
    except ImportError:
        logger.warning("growth_api 模块未加载")
        return success(
            data={
                "symbols": {},
                "summary": {
                    "total_queries": 0,
                    "avg_latency_ms": 0,
                    "avg_confidence": 0,
                    "cache_hit_rate": 0,
                },
            },
            message="成长概览（模块未加载）",
        )
    except Exception as e:
        logger.exception("growth_overview 失败: %s", e)
        return error("获取成长概览失败", status_code=500, detail=str(e))


@router.get("/api/growth/trends")
async def growth_trends(request: Request = None, days: int = 7):
    """获取成长趋势数据

    Args:
        days: 查询天数（默认 7 天）
    """
    try:
        import json
        import os
        import time
        from datetime import datetime, timedelta

        growth_dir = "data/growth"
        symbols = ["shaoyang", "taiyang", "shaoyin", "taiyin"]
        cutoff = time.time() - days * 24 * 3600

        trends = {}
        for symbol in symbols:
            growth_file = os.path.join(growth_dir, f"{symbol}_growth.jsonl")
            if not os.path.exists(growth_file):
                trends[symbol] = []
                continue

            records = []
            try:
                with open(growth_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            r = json.loads(line)
                            if r.get("timestamp", 0) > cutoff:
                                records.append(r)
            except Exception as e:
                logger.warning("读取 %s 成长数据失败: %s", symbol, e)
                records = []

            # 按天聚合
            daily = {}
            for r in records:
                day = datetime.fromtimestamp(r.get("timestamp", 0)).strftime("%Y-%m-%d")
                if day not in daily:
                    daily[day] = {"count": 0, "latency_sum": 0, "confidence_sum": 0}
                daily[day]["count"] += 1
                daily[day]["latency_sum"] += r.get("latency_ms", 0)
                daily[day]["confidence_sum"] += r.get("confidence", 0)

            trend = []
            for day in sorted(daily.keys()):
                d = daily[day]
                trend.append(
                    {
                        "date": day,
                        "query_count": d["count"],
                        "avg_latency_ms": round(d["latency_sum"] / d["count"], 2),
                        "avg_confidence": round(d["confidence_sum"] / d["count"], 4),
                    }
                )
            trends[symbol] = trend

        return success(
            data={"trends": trends, "days": days},
            message="成长趋势",
        )
    except Exception as e:
        logger.exception("growth_trends 失败: %s", e)
        return error("获取成长趋势失败", status_code=500, detail=str(e))
