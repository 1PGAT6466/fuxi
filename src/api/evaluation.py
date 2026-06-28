"""
routers/evaluation.py — 评测中心 API (v2.0 — 接入 lib.evaluation)
"""
import json, time, asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from fastapi import APIRouter, Query

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.evaluation import load_test_cases, run_evaluation, save_test_cases
from src.core.db import connect
import logging; logger = logging.getLogger(__name__)

router = APIRouter(tags=["评测中心"])

LOG_DIR = Path(__file__).parent.parent / "logs"

@router.get("/api/evaluation/overview")
async def evaluation_overview(days: int = Query(7, ge=1, le=90)):
    """评测总览"""
    # 搜索统计
    search_stats = _search_stats(days)
    
    # 评测数据 (仅返回测试集信息，实际运行请调用 /api/evaluation/ragas)
    test_cases = load_test_cases()
    
    return {
        "search_stats": search_stats,
        "rag_eval": {"available": True, "test_cases": len(test_cases), "hint": "POST /api/evaluation/ragas to run full eval"},
        "test_cases_count": len(test_cases),
        "generated_at": datetime.now().isoformat(),
    }

@router.get("/api/evaluation/ragas")
async def ragas_eval():
    """RAGAS 风格评测"""
    return _run_rag_eval()

@router.get("/api/evaluation/health")
async def eval_health():
    return {"status": "ok", "test_cases": len(load_test_cases())}

@router.post("/api/evaluation/test-cases")
async def update_test_cases(data: dict):
    """更新测试集"""
    cases = data.get("cases", [])
    if cases:
        save_test_cases(cases)
        return {"ok": True, "count": len(cases)}
    return {"ok": False, "error": "no cases provided"}


@router.post("/api/evaluation/auto-update")
async def auto_update_eval_set():
    """P3-5: 从搜索日志自动生成 ragas 测试用例"""
    try:
        from src.services.eval_updater import update_eval_set
        result = update_eval_set()
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _search_stats(days: int) -> dict:
    """从日志提取搜索统计"""
    stats = {"total_searches": 0, "avg_results": 0.0, "zero_result_rate": 0.0,
             "avg_latency_ms": 0.0, "p50_latency_ms": 0.0, "p95_latency_ms": 0.0}
    
    if not LOG_DIR.exists():
        return stats
    
    cutoff = datetime.now() - timedelta(days=days)
    all_queries = []
    latencies = []
    zero_count = 0
    
    for f in sorted(LOG_DIR.glob("search_*.jsonl")):
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                        ts = rec.get("timestamp") or rec.get("time")
                        if ts:
                            dt = datetime.fromisoformat(ts.replace("Z","").split("+")[0])
                            if dt < cutoff:
                                continue
                        all_queries.append(rec)
                        lat = rec.get("latency_ms", 0)
                        if lat > 0:
                            latencies.append(lat)
                        if rec.get("results", 0) == 0:
                            zero_count += 1
                    except Exception:
                        logger.warning(f"[evaluation] suppressed exception", exc_info=True)
                        pass
        except Exception:
            logger.warning(f"[evaluation] suppressed exception", exc_info=True)
            pass
    
    if all_queries:
        total = len(all_queries)
        stats["total_searches"] = total
        stats["zero_result_rate"] = round(zero_count / total * 100, 1)
        if latencies:
            latencies.sort()
            stats["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
            stats["p50_latency_ms"] = latencies[len(latencies) // 2]
            stats["p95_latency_ms"] = latencies[int(len(latencies) * 0.95)]
    
    return stats

def _run_rag_eval() -> dict:
    """运行 RAG 评测"""
    test_cases = load_test_cases()
    if not test_cases:
        return {"available": False, "message": "无测试集"}
    
    # 通过 HTTP 调用本地搜索 API
    import urllib.request
    def search_fn(query, top_k=10):
        url = f"http://localhost:8080/api/search?q={urllib.parse.quote(query)}&top_k={top_k}"
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read())
            return data.get("results", [])
        except Exception:
            return []
    
    return run_evaluation(search_fn, test_cases)
