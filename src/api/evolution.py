"""
routers/evolution.py — 进化中心 API (v2.0 — 接入 lib.db)
"""
import json
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path
from fastapi import APIRouter, Query
from src.core.db import connect, count_worldtree
import logging; logger = logging.getLogger(__name__)

router = APIRouter(tags=["进化中心"])

FEEDBACK_DIR = Path(__file__).parent.parent / "data" / "feedback"
LOG_DIR = Path(__file__).parent.parent / "logs"

@router.get("/api/evolution/overview")
async def evolution_overview(days: int = Query(30, ge=7, le=365)):
    wiki = _wiki_stats()
    graph = _graph_stats()
    feedback = _feedback_stats(days)
    return {
        "wiki": wiki, "graph": graph, "feedback": feedback,
        "generated_at": datetime.now().isoformat(),
    }

def _wiki_stats() -> dict:
    try:
        stats = count_worldtree()
        total = stats["wiki_pages"]
        
        with connect("worldtree") as db:
            stale = db.execute(
                "SELECT COUNT(*) FROM wiki_pages WHERE updated_at < date('now','-30 days')"
            ).fetchone()[0]
            recent = db.execute(
                "SELECT COUNT(*) FROM wiki_pages WHERE updated_at > date('now','-7 days')"
            ).fetchone()[0]
            low_q = db.execute(
                "SELECT COUNT(*) FROM wiki_pages WHERE quality_score < 0.5"
            ).fetchone()[0]
            cats = db.execute(
                "SELECT category_path, COUNT(*) as cnt FROM wiki_pages GROUP BY category_path ORDER BY cnt DESC"
            ).fetchall()
        
        return {
            "available": True,
            "total_pages": total,
            "recently_updated": recent,
            "stale_pages": stale,
            "low_quality_pages": low_q,
            "health_score": round((1 - stale/max(total,1)) * (1 - low_q/max(total,1)) * 100, 1),
            "top_categories": [{"name": c, "count": n} for c, n in cats[:8]],
            "actions": (
                (["update_stale"] if stale > 0 else []) +
                (["improve_low_quality"] if low_q > 0 else [])
            ),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

def _graph_stats() -> dict:
    try:
        gf = Path(__file__).parent.parent / "data" / "knowledge_graph.json"
        if not gf.exists():
            from src.core.db import get_knowledge_graph
            g = get_knowledge_graph()
        else:
            with open(gf, encoding='utf-8') as f:
                g = json.load(f)
        
        nodes = g.get("nodes", {})
        edges = g.get("edges", [])
        type_dist = Counter()
        for n in nodes.values():
            if isinstance(n, dict):
                type_dist[n.get("type", "unknown")] += 1
        
        return {
            "available": True,
            "total_entities": len(nodes),
            "total_edges": len(edges),
            "entity_types": dict(type_dist.most_common(15)),
        }
    except Exception:
        return {"available": False}

def _feedback_stats(days: int) -> dict:
    try:
        cutoff = datetime.now() - timedelta(days=days)
        fb_dir = FEEDBACK_DIR
        if not fb_dir.exists():
            from pathlib import Path as P
            fb_dir = P(__file__).parent.parent / "feedback_data"
        
        total, positive, negative = 0, 0, 0
        if fb_dir.exists():
            for f in fb_dir.glob("*.json"):
                try:
                    with open(f) as fh:
                        data = json.load(fh)
                    if isinstance(data, list):
                        for item in data:
                            ts = item.get("timestamp") or item.get("created_at")
                            if ts:
                                dt = datetime.fromisoformat(str(ts).replace("Z", ""))
                                if dt >= cutoff:
                                    total += 1
                                    if item.get("rating", 0) >= 4:
                                        positive += 1
                                    elif item.get("rating", 0) <= 2:
                                        negative += 1
                except Exception:
                    logger.warning(f"[evolution] suppressed exception", exc_info=True)
                    pass
        
        return {
            "total": total, "positive": positive, "negative": negative,
            "satisfaction": round(positive/max(total,1)*100, 1)
        }
    except Exception:
        return {"total": 0}
