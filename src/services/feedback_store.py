"""
feedback_store.py — 反馈闭环服务（v1.50 新增）
负责：
  1. 用户反馈去重（基于 MD5 签名）
  2. 批量学习触发（buffer 满时自动调用 learner）
  3. 反馈统计
  4. P1 优化：批量写入缓冲 + 定时 flush
"""
import hashlib
import time
import asyncio
import logging
import threading
from typing import Dict, List, Optional
from collections import deque

try:
    from cachetools import TTLCache
except ImportError:
    TTLCache = None  # fallback to manual dict LRU

logger = logging.getLogger(__name__)

# 去重窗口（秒）：同一个用户同一条查询的反馈 300 秒内只记录一次
DEDUP_WINDOW = 300
# 批量学习阈值：buffer 积累到多少条时触发学习
LEARN_BUFFER_SIZE = 20
# 最大去重缓存大小（简单 LRU）
MAX_DEDUP_CACHE = 2000
# 批量失败最大重试次数
MAX_RETRY = 3

# ── P1: 批量写入缓冲 ──
_WRITE_BUFFER_MAX_SIZE = 100     # 最大缓冲条数
_WRITE_BUFFER_FLUSH_INTERVAL = 5.0  # 每5秒 flush
_write_buffer: List[Dict] = []
_write_buffer_lock = threading.Lock()
_flush_task: Optional[asyncio.Task] = None

# 模块级去重缓存（TTLCache 自动过期 + maxsize 限制，threadsafe）
if TTLCache is not None:
    _feedback_dedup = TTLCache(maxsize=MAX_DEDUP_CACHE, ttl=DEDUP_WINDOW)
    _use_ttl_cache = True
else:
    _feedback_dedup: Dict[str, float] = {}  # fallback
    _use_ttl_cache = False
_feedback_dedup_lock = threading.Lock()
_learn_buffer: deque = deque()
_learn_buffer_lock = threading.Lock()


# ── P1: 批量写入缓冲 ──

async def _start_flush_scheduler():
    """启动定时 flush 调度器"""
    global _flush_task
    if _flush_task is not None:
        return
    
    async def _scheduler():
        while True:
            try:
                await asyncio.sleep(_WRITE_BUFFER_FLUSH_INTERVAL)
                await _flush_write_buffer()
            except asyncio.CancelledError:
                logger.info("[反馈闭环] 定时 flush 调度器已停止")
                break
            except Exception as e:
                logger.error(f"[反馈闭环] 定时 flush 异常: {e}", exc_info=True)
    
    _flush_task = asyncio.create_task(_scheduler())
    logger.info(
        f"[反馈闭环] 批量写入缓冲已启动 "
        f"(max_buffer={_WRITE_BUFFER_MAX_SIZE}, flush_interval={_WRITE_BUFFER_FLUSH_INTERVAL}s)"
    )


async def _stop_flush_scheduler():
    """停止定时 flush 调度器"""
    global _flush_task
    if _flush_task:
        # 最终 flush
        await _flush_write_buffer()
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None


async def _flush_write_buffer():
    """将缓冲区中的条目批量写入文件"""
    global _write_buffer
    with _write_buffer_lock:
        if not _write_buffer:
            return
        batch = _write_buffer[:]
        _write_buffer.clear()
    
    if not batch:
        return
    
    try:
        import json, os
        from src.config import FEEDBACK_DIR
        
        # 按日期分组
        entries_by_day: Dict[str, list] = {}
        for entry in batch:
            day = time.strftime("%Y-%m-%d", time.localtime(entry.get("timestamp", time.time())))
            if day not in entries_by_day:
                entries_by_day[day] = []
            entries_by_day[day].append({
                "user_id": entry["user_id"],
                "query": entry["query"],
                "action": entry["action"],
                "timestamp": entry["timestamp"],
                "results_count": len(entry.get("results", [])),
                "metadata": entry.get("metadata"),
            })
        
        # 批量写入
        for day, day_entries in entries_by_day.items():
            os.makedirs(FEEDBACK_DIR, exist_ok=True)
            log_path = os.path.join(FEEDBACK_DIR, f"feedback_{day}.jsonl")
            with open(log_path, 'a', encoding='utf-8') as f:
                for entry in day_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        logger.debug(f"[反馈闭环] 批量写入 {len(batch)} 条反馈")
    except Exception as e:
        logger.warning(f"[反馈闭环] 批量写入失败: {e}", exc_info=True)
        # 失败时放回缓冲区（最多重试）
        with _write_buffer_lock:
            for entry in batch:
                entry["_write_retry"] = entry.get("_write_retry", 0) + 1
            still_retry = [e for e in batch if e.get("_write_retry", 0) < MAX_RETRY]
            _write_buffer = still_retry + _write_buffer


def _add_to_write_buffer(user_id: str, query: str, action: str,
                         results: Optional[List], metadata: Optional[Dict],
                         timestamp: float):
    """添加条目到写入缓冲区（P1: 批量缓冲替代直接写入）"""
    with _write_buffer_lock:
        _write_buffer.append({
            "user_id": user_id,
            "query": query,
            "action": action,
            "results": results,
            "metadata": metadata,
            "timestamp": timestamp,
        })
        
        buffer_size = len(_write_buffer)
    
    # 如果缓冲区满，触发异步 flush
    if buffer_size >= _WRITE_BUFFER_MAX_SIZE:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_flush_write_buffer())
        except RuntimeError:
            pass  # 事件循环未运行，下次定时 flush 时写入


def _make_feedback_key(user_id: str, query: str, action: str) -> str:
    """生成反馈去重 key"""
    raw = f"{user_id}|{query}|{action}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def log_feedback_unified(user_id: str, query: str, action: str,
                               results: Optional[List] = None,
                               metadata: Optional[Dict] = None) -> Dict:
    """
    统一反馈记录入口
    返回: {"ok": True, "dedup": bool, "learn_triggered": bool}
    """
    now = time.time()

    # 1. 去重检查（threadsafe）
    key = _make_feedback_key(user_id, query, action)
    is_dup = False
    with _feedback_dedup_lock:
        if _use_ttl_cache:
            # TTLCache 自动处理过期和 maxsize，只需 set
            if key in _feedback_dedup:
                is_dup = True
            else:
                _feedback_dedup[key] = now
        else:
            # fallback: 手动检查过期 + LRU
            if key in _feedback_dedup and now - _feedback_dedup[key] < DEDUP_WINDOW:
                is_dup = True
            else:
                _feedback_dedup[key] = now
                # LRU 淘汰
                if len(_feedback_dedup) > MAX_DEDUP_CACHE:
                    sorted_keys = sorted(_feedback_dedup.items(), key=lambda x: x[1])
                    for old_key, _ in sorted_keys[:len(_feedback_dedup) // 2]:
                        del _feedback_dedup[old_key]

    if is_dup:
        return {"ok": True, "dedup": True, "learn_triggered": False}

    # 2. 写入反馈缓冲区（P1: 批量缓冲替代直接写入）
    try:
        _add_to_write_buffer(user_id, query, action, results, metadata, now)
    except Exception:
        logger.warning("添加反馈到缓冲区失败", exc_info=True)

    # 3. 积累学习 buffer
    learn_triggered = False
    with _learn_buffer_lock:
        _learn_buffer.append({
            "user_id": user_id,
            "query": query,
            "action": action,
            "results": results,
            "timestamp": now,
        })

        # 4. buffer 满了触发学习
        if len(_learn_buffer) >= LEARN_BUFFER_SIZE:
            asyncio.create_task(_maybe_learn_batch())
            learn_triggered = True

    return {"ok": True, "dedup": False, "learn_triggered": learn_triggered}


def _write_feedback_log(user_id: str, query: str, action: str,
                        results: Optional[List], metadata: Optional[Dict],
                        timestamp: float):
    """将反馈写入日志文件"""
    import json, os
    from src.config import FEEDBACK_DIR

    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.localtime(timestamp))
    log_path = os.path.join(FEEDBACK_DIR, f"feedback_{day}.jsonl")

    entry = {
        "user_id": user_id,
        "query": query,
        "action": action,
        "timestamp": timestamp,
        "results_count": len(results) if results else 0,
        "metadata": metadata,
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


async def _maybe_learn_batch():
    """批量学习：从 buffer 中提取正负样本，调用 learner"""
    global _learn_buffer
    with _learn_buffer_lock:
        if len(_learn_buffer) < LEARN_BUFFER_SIZE:
            return
        batch = list(_learn_buffer)
        _learn_buffer.clear()

    try:
        from src.services.learner import learn_from_feedback
        await learn_from_feedback(batch)
        logger.info(f"[反馈闭环] 学习完成: {len(batch)} 条反馈")
    except ImportError:
        logger.debug("[反馈闭环] learner 模块不存在，跳过批量学习")
    except Exception:  # TODO: Narrow exception type
        logger.warning("[反馈闭环] 学习失败", exc_info=True)
        # 失败时放回 buffer（最多重试 MAX_RETRY 次）
        for item in batch:
            item["_retry_count"] = item.get("_retry_count", 0) + 1
        still_retry = [i for i in batch if i.get("_retry_count", 0) < MAX_RETRY]
        with _learn_buffer_lock:
            _learn_buffer.extendleft(still_retry[::-1])


def get_feedback_stats() -> Dict:
    """获取反馈统计"""
    with _feedback_dedup_lock:
        dedup_size = len(_feedback_dedup)
    with _learn_buffer_lock:
        buffer_size = len(_learn_buffer)
    return {
        "dedup_cache_size": dedup_size,
        "learn_buffer_size": buffer_size,
        "learn_buffer_threshold": LEARN_BUFFER_SIZE,
    }


def clear_feedback_cache():
    """清空去重缓存"""
    global _feedback_dedup
    with _feedback_dedup_lock:
        if _use_ttl_cache:
            _feedback_dedup.clear()
        else:
            _feedback_dedup = {}
    logger.info("[反馈闭环] 去重缓存已清空")
