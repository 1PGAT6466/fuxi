"""
api/v2_routes.py — 伏羲 v1.41 经络路由

提供 /api/v2/status（八卦全图体征）和 /api/v2/search（已有）
"""
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v2-bagua"])

# 八卦 → 器官映射（先天八卦排列）
BAGUA_ORGAN_MAP = [
    {"trigram": "qian",  "symbol": "☰", "natural": "天", "organ_id": "brain",    "organ_name": "乾·统领",    "position": "northwest"},
    {"trigram": "kun",   "symbol": "☷", "natural": "地", "organ_id": "spleen",   "organ_name": "坤·存储",    "position": "southwest"},
    {"trigram": "li",    "symbol": "☲", "natural": "火", "organ_id": "heart",    "organ_name": "离·路由",    "position": "south"},
    {"trigram": "kan",   "symbol": "☵", "natural": "水", "organ_id": "kidney",   "organ_name": "坎·精炼",    "position": "north"},
    {"trigram": "zhen",  "symbol": "☳", "natural": "雷", "organ_id": "liver",    "organ_name": "震·过滤",    "position": "east"},
    {"trigram": "dui",   "symbol": "☱", "natural": "泽", "organ_id": "nose",     "organ_name": "兑·嗅探",    "position": "west"},
    {"trigram": "xun",   "symbol": "☴", "natural": "风", "organ_id": "lung",     "organ_name": "巽·生成",    "position": "southeast"},
    {"trigram": "gen",   "symbol": "☶", "natural": "山", "organ_id": "skin",     "organ_name": "艮·屏障",    "position": "northeast"},
]

# 额外器官（不在八卦图中但活跃的）
EXTRA_ORGANS = [
    {"organ_id": "stomach",  "organ_name": "中宫·消化", "emoji": "⊕"},
    {"organ_id": "small_intestine", "organ_name": "小肠·分清", "emoji": "🫒"},
    {"organ_id": "skeleton", "organ_name": "骨骼·图谱", "emoji": "🦴"},
    {"organ_id": "limbs",    "organ_name": "四肢·执行", "emoji": "💪"},
    {"organ_id": "gallbladder", "organ_name": "胆·决断", "emoji": "🫀"},
    {"organ_id": "sanjiao",  "organ_name": "三焦·通道", "emoji": "🌊"},
]

@router.get("/api/v2/status")
async def bagua_status(request: Request):
    """伏羲 v1.41 八卦全图体征
    
    返回：
    - 八卦图：8 个卦位对应器官的实时状态
    - 经络统计：信号数、心跳数
    - 数据体征：chunks 数、wiki 数、整体健康分
    """
    try:
        meridian = request.app.state.meridian
        _fuxi = request.app.state.fuxi
    except AttributeError:
        try:
            from src.server import _fuxi_instance as _fuxi
            if _fuxi is None:
                return {"ok": False, "error": "伏羲生命体尚未苏醒"}
            meridian = _fuxi.meridian
        except:
            return {"ok": False, "error": "伏羲生命体尚未苏醒"}
        from src.db.data_store import load_chunks
    except Exception as e:
        return {"ok": False, "error": f"经络未初始化: {e}"}
    
    # 1. 八卦图器官状态
    bagua = []
    alive_count = 0
    for bg in BAGUA_ORGAN_MAP:
        oid = bg["organ_id"]
        try:
            is_alive = meridian.is_alive(oid)
            organ_info = meridian.get_organ(oid)
            last_hb = round(time.time() - organ_info.last_heartbeat, 1) if organ_info else -1
        except:
            is_alive = False
            last_hb = -1
        
        # 尝试获取器官 stats
        organ_stats = {}
        try:
            from src.hypothalamus.organs import get_organ_stats
            organ_stats = get_organ_stats(oid)
        except:
            pass
        
        status = "healthy" if is_alive else "dead"
        bagua.append({
            **bg,
            "alive": is_alive,
            "status": status,
            "last_heartbeat_ago": last_hb,
            "stats": organ_stats,
        })
        if is_alive:
            alive_count += 1
    
    # 2. 额外器官
    extra = []
    for ext in EXTRA_ORGANS:
        oid = ext["organ_id"]
        try:
            is_alive = meridian.is_alive(oid)
            organ_info = meridian.get_organ(oid)
            last_hb = round(time.time() - organ_info.last_heartbeat, 1) if organ_info else -1
        except:
            is_alive = False
            last_hb = -1
        
        extra.append({
            **ext,
            "alive": is_alive,
            "status": "healthy" if is_alive else "dead",
            "last_heartbeat_ago": last_hb,
        })
        if is_alive:
            alive_count += 1
    
    # 3. 经络统计
    meridian_stats = meridian.stats() if hasattr(meridian, 'stats') else {}
    
    # 4. 数据体征
    try:
        chunks = load_chunks()
        chunk_count = len(chunks) if chunks else 0
    except:
        chunk_count = 0
    
    # 5. 整体健康分
    total_organs = len(bagua) + len(extra)
    if total_organs > 0:
        health_score = round(alive_count / total_organs * 100)
    else:
        health_score = 0
    
    # v1.42: balance stats
    balance_stats = {}
    try:
        if hasattr(_fuxi, "five_elements"):
            balance_stats["five_elements"] = _fuxi.five_elements.stats()
        if hasattr(_fuxi, "stem_scheduler"):
            balance_stats["stem_scheduler"] = _fuxi.stem_scheduler.stats()
        if hasattr(_fuxi, "rhythm"):
            balance_stats["meridian_rhythm"] = _fuxi.rhythm.stats()
    except:
        pass

    return {
        "ok": True,
        "name": "伏羲",
        "version": "4.3",

        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health_score": health_score,
        "alive_organs": alive_count,
        "total_organs_inner": total_organs,
        "bagua": bagua,
        "extra_organs": extra,
        "meridian": meridian_stats,
        "balance": balance_stats,
        "data": {
            "chunks": chunk_count,
        },
    }
