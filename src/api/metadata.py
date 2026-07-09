"""
伏羲 v1.50 — 元数据路由（真实数据版）
数据来源：系统版本 + 文档统计 + 矢量库统计
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["元数据"])


@router.get("/api/metadata")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def metadata(request: Request = None):
    """元数据 — v1.50 真实数据版

    返回系统元信息：
      - 版本号
      - 数据统计（文档数、向量数、wiki 页面数）
      - 引擎版本
      - 系统启动时间
    """
    try:
        from src.config import VERSION

        metadata_items = []

        # 1. 系统版本
        metadata_items.append({"key": "version", "value": VERSION, "label": "系统版本"})

        # 2. 引擎版本
        engine = getattr(request.app.state, "engine", "v2") if request else "v2"
        metadata_items.append({"key": "engine", "value": engine, "label": "引擎版本"})
        intent_mode = getattr(request.app.state, "intent_mode", "rule_based") if request else "rule_based"
        metadata_items.append({"key": "intent_mode", "value": intent_mode, "label": "意图模式"})

        # 3. 数据统计
        try:
            from src.db.data_store import load_chunks
            from src.db.vector_store import get_vector_store
            chunks = load_chunks() or []
            vs = get_vector_store()
            vector_count = 0
            if vs:
                try:
                    vector_count = vs.count
                    if vector_count < 0:
                        vector_count = 0
                except Exception:
                    pass

            metadata_items.append({"key": "total_chunks", "value": len(chunks), "label": "文档块数"})
            metadata_items.append({"key": "vector_count", "value": vector_count, "label": "向量数"})

            unique_files = len(set(c.get("file_name", "") for c in chunks if c.get("file_name")))
            metadata_items.append({"key": "unique_files", "value": unique_files, "label": "唯一文件数"})
        except ImportError:
            metadata_items.append({"key": "data_status", "value": "unavailable", "label": "数据状态"})

        # 4. Wiki 统计
        try:
            from src.taiyang.wiki import get_wiki_engine
            engine = get_wiki_engine()
            pages = engine.list_pages() or []
            metadata_items.append({"key": "wiki_pages", "value": len(pages), "label": "Wiki 页面数"})
        except ImportError:
            pass
        except Exception:
            pass

        # 5. 系统运行时间
        born_at = getattr(request.app.state, "fuxi_born_at", None) if request else None
        if born_at:
            uptime = time.time() - born_at
            metadata_items.append({"key": "uptime_seconds", "value": round(uptime, 1), "label": "运行时间(秒)"})

        data = {"metadata": metadata_items, "total": len(metadata_items)}

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="元数据")
        return data
    except Exception as e:
        logger.exception(f"metadata 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
