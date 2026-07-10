"""
伏羲 v1.44 — API 路径别名兼容层
=================================
解决前后端 API 路径不匹配问题。

策略：向后兼容 —— 保留所有现有路径，同时添加别名路由避免前端大规模改动。

已由其他文件覆盖的别名（无需重复注册）：
  - /api/documents ↔ /api/files          → files_alias.py 已处理
  - /api/upload ↔ /api/files/upload      → files_alias.py 已处理
  - /api/download/{hash} ↔ /api/files/{id}/download → files_alias.py 已处理
  - /api/view/{hash} ↔ 文件查看           → files_view.py 已处理
  - /api/admin/status → /api/admin/server-status → admin.py 已处理
  - /api/wiki/pages, /api/wiki/page/{id} → wiki.py 已处理（v1.44 去重）

本文件新增的别名（本模块独有）：
  - GET /api/antenna/search → 联网搜索              (Vue3 前端用 GET 方法)
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["路径别名兼容层"])


# v1.44: Wiki 路径别名已移除 — /api/wiki/pages 和 /api/wiki/page/{id}
# 已在 wiki.py 中定义，保留 wiki.py 作为唯一实现源。


# ============ 联网搜索方法别名（Legacy POST ↔ Vue3 GET）============
# 注意：/api/antenna/search 主路由在 files_view.py 中实现（注册顺序优先）。
# 本路由作为备用兼容层，仅在 files_view.py 路由未注册时生效。

@router.get("/api/antenna/search")
async def antenna_search_get(q: str = "", request: Request = None):
    """备用：GET /api/antenna/search?q=xxx (Vue3 前端使用 GET 方法)

    Legacy 前端 js/chat.js 使用 POST /api/antenna/search，由 files_view.py 处理。
    本路由兼容 Vue3 前端的 GET 请求。
    """
    if not q or not q.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "缺少 q 参数", "detail": "搜索关键词不能为空"}
        )

    try:
        from src.taiyang.retrieval import hybrid_search
        results = await hybrid_search(q, top_k=5)

        return {
            "results": [
                {
                    "title": r.get("title", r.get("source", "")),
                    "snippet": (r.get("text", "") or r.get("snippet", ""))[:200],
                    "url": r.get("url", ""),
                    "score": r.get("score", 0),
                    "source": r.get("_source", "knowledge_base"),
                }
                for r in results
            ],
            "query": q,
            "source": "knowledge_base",
            "message": f"找到 {len(results)} 条相关结果" if results else "未找到相关结果",
        }
    except ImportError:
        return {
            "results": [],
            "query": q,
            "source": "unavailable",
            "message": "搜索服务暂不可用，请稍后重试",
        }
    except (ImportError, OSError, RuntimeError) as e:
        logger.exception(f"antenna_search_get 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "搜索失败", "detail": str(e)},
        )
