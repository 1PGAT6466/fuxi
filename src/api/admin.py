# 兼容层 - 管理路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["管理"])


# ============ 内部辅助函数 ============

def _get_chunks_stats():
    """获取文档块统计信息"""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        total_chunks = len(chunks)
        categories = {}
        for c in chunks:
            cat = c.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1
        unique_files = len(set(c.get("file_hash", "") for c in chunks))
        return {
            "total_chunks": total_chunks,
            "unique_files": unique_files,
            "categories": categories,
        }
    except Exception as e:
        logger.warning(f"_get_chunks_stats 失败: {e}")
        return {"total_chunks": 0, "unique_files": 0, "categories": {}}


def _load_users():
    """加载用户列表"""
    try:
        from pathlib import Path
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            raw = json.loads(users_file.read_text(encoding="utf-8"))
            users = []
            for username, info in raw.items():
                users.append({
                    "username": username,
                    "role": info.get("role", "user"),
                    "display_name": info.get("display_name", username),
                    "created_at": info.get("created_at", 0),
                })
            return users
        return []
    except Exception as e:
        logger.warning(f"_load_users 失败: {e}")
        return []


# ============ 路由端点 ============

@router.get("/api/admin/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_stats(request: Request = None):
    """管理统计"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "chunks": 0, "categories": {}}, message="管理统计")
        return {"ok": True, "chunks": 0, "categories": {}}
    except Exception as e:
        logger.exception(f"admin_stats 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/admin/server-status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def server_status(request: Request = None):
    """服务器状态"""
    try:
        import time
        from src.config import START_TIME
        uptime = time.time() - START_TIME
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "uptime_seconds": round(uptime), "uptime_hours": round(uptime/3600, 1)}, message="服务器状态")
        return {"ok": True, "uptime_seconds": round(uptime), "uptime_hours": round(uptime/3600, 1)}
    except Exception as e:
        logger.exception(f"server_status 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ── 任务 A.1: /api/admin/status 别名 → /api/admin/server-status ──
@router.get("/api/admin/status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_status_alias(request: Request = None):
    """前端调用的 /api/admin/status — 代理到 server-status"""
    return await server_status(request)

# ── 任务 A.2: /api/admin/documents 文档统计 ──
@router.get("/api/admin/documents")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_documents(request: Request = None):
    """管理面板：文档统计"""
    try:
        stats = _get_chunks_stats()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "documents": stats}, message="文档统计")
        return {"ok": True, "documents": stats}
    except Exception as e:
        logger.exception(f"admin_documents 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ── 任务 A.3: /api/admin/evaluations 和 /api/admin/evaluations/run ──
@router.get("/api/admin/evaluations")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_evaluations(request: Request = None):
    """管理面板：评测列表 — 代理到 evaluation API"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        history = await automation.get_eval_history()
        report = await automation.get_latest_report()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={
                "ok": True,
                "evaluations": history,
                "latest_report": report or {"message": "暂无评测报告"},
            }, message="评测列表")
        return {
            "ok": True,
            "evaluations": history,
            "latest_report": report or {"message": "暂无评测报告"},
        }
    except Exception as e:
        logger.exception(f"admin_evaluations 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.post("/api/admin/evaluations/run")
async def admin_evaluations_run():
    """管理面板：触发评测运行"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        result = await automation.run_daily_eval()
        return {"ok": True, "result": result}
    except Exception as e:
        logger.exception(f"admin_evaluations_run 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ── 任务 A.4: /api/admin/users 用户列表 ──
@router.get("/api/admin/users")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_users(request: Request = None):
    """管理面板：用户列表"""
    try:
        users = _load_users()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "users": users, "total": len(users)}, message="用户列表")
        return {"ok": True, "users": users, "total": len(users)}
    except Exception as e:
        logger.exception(f"admin_users 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
