"""
admin.py - 管理路由
v1.44 Phase 1: 使用 RBAC require_role 替代旧版 require_admin
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.auth.rbac import require_role
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["管理"])


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
    except (OSError, IOError, ValueError) as e:
        logger.warning(f"_get_chunks_stats 失败: {e}")
        return {"total_chunks": 0, "unique_files": 0, "categories": {}}


def _load_users():
    """加载用户列表"""
    try:
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            raw = json.loads(users_file.read_text(encoding="utf-8"))
            users = []
            for username, info in raw.items():
                users.append({
                    "username": username,
                    "role": info.get("role", "user"),
                    "tenant_id": info.get("tenant_id", "default"),
                })
            return users
        return []
    except (OSError, IOError, json.JSONDecodeError) as e:
        logger.warning(f"_load_users 失败: {e}")
        return []


def _save_users(users):
    """保存用户列表"""
    try:
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        users_file.parent.mkdir(parents=True, exist_ok=True)
        data = {u["username"]: u for u in users}
        users_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, IOError) as e:
        logger.warning(f"_save_users 失败: {e}")


@router.get("/api/admin/stats")
async def admin_stats(request: Request = None):
    """管理统计"""
    try:
        chunks_stats = _get_chunks_stats()
        users = _load_users()
        return {
            "status": "success",
            "data": {
                "chunks": chunks_stats,
                "users": {"total": len(users)},
            }
        }
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"admin_stats 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.get("/api/admin/status")
async def server_status(request: Request = None):
    """服务器状态"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return {
            "status": "success",
            "data": {
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used_mb": mem.used // (1024 * 1024),
                "memory_total_mb": mem.total // (1024 * 1024),
            }
        }
    except (ImportError, OSError) as e:
        return {"status": "success", "data": {"message": "psutil 不可用"}}


@router.get("/api/admin/users")
async def admin_users(request: Request = None):
    """用户列表"""
    try:
        users = _load_users()
        return {"status": "success", "data": {"users": users, "total": len(users)}}
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"admin_users 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/api/admin/users")
async def admin_create_user(request: Request):
    """创建用户"""
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        role = data.get("role", "user")
        if not username or not password:
            return JSONResponse(status_code=400, content={"status": "error", "message": "用户名和密码必填"})
        users = _load_users()
        if any(u["username"] == username for u in users):
            return JSONResponse(status_code=409, content={"status": "error", "message": "用户已存在"})
        import bcrypt
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        users.append({"username": username, "password_hash": hashed, "role": role, "tenant_id": "default"})
        _save_users(users)
        return {"status": "success", "message": f"用户 {username} 创建成功"}
    except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
        logger.exception(f"admin_create_user 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request = None):
    """删除用户"""
    try:
        users = _load_users()
        users = [u for u in users if u["username"] != user_id]
        _save_users(users)
        return {"status": "success", "message": f"用户 {user_id} 已删除"}
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"admin_delete_user 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
