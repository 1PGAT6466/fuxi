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
    """加载用户列表 — v1.50 R3: 保留 password 字段防止数据丢失"""
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
                    "password": info.get("password", ""),
                    "display_name": info.get("display_name", username),
                    "email": info.get("email", ""),
                })
            return users
        return []
    except (OSError, IOError, json.JSONDecodeError) as e:
        logger.warning(f"_load_users 失败: {e}")
        return []

# v1.50 R4: 进程内文件级锁，防止 users.json 并发 read-modify-write 引发数据丢失
import threading as _threading
_users_file_lock = _threading.Lock()

def _load_users_locked():
    """带锁加载用户列表，与 _save_users 配对使用以保证原子 read-modify-write"""
    with _users_file_lock:
        return _load_users()

def _save_users(users):
    """保存用户列表 — v1.50 R3-4: 文件锁 + 原子写入"""
    import os as _os
    import tempfile as _tempfile
    try:
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        users_file.parent.mkdir(parents=True, exist_ok=True)
        with _users_file_lock:
            data = {u["username"]: u for u in users}
            # v1.50 R3: 原子写入（先写临时文件再 rename）
            fd, tmp_path = _tempfile.mkstemp(suffix=".json", dir=str(users_file.parent))
            try:
                _os.write(fd, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            finally:
                _os.close(fd)
            _os.replace(tmp_path, str(users_file))
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
    """创建用户 — v1.50 R3: 安全性修复
    
    - 密码长度验证
    - 敏感用户名黑名单检查
    - 合法 role 值验证
    - 使用 dict 格式保存，防止数据丢失
    - 写入审计日志
    """
    from src.api.response import success, error
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        role = data.get("role", "user")
        
        # v1.50 R3: 输入验证
        if not username or len(username) < 1 or len(username) > 64:
            return JSONResponse(status_code=400, content={"status": "error", "message": "用户名长度必须在1-64字符之间"})
        if not password or len(password) < 8:
            return JSONResponse(status_code=400, content={"status": "error", "message": "密码长度至少需要8个字符"})
        if role not in ("user", "admin", "viewer"):
            return JSONResponse(status_code=400, content={"status": "error", "message": "无效的角色值"})
        
        # v1.50 R3: 敏感用户名检查（与 auth_routes 保持一致）
        from src.api.auth_routes import _is_username_blocked
        if _is_username_blocked(username):
            return JSONResponse(status_code=400, content={"status": "error", "message": "该用户名不可用，请选择其他用户名"})
        
        # v1.50 R3: 合并到 dict 格式
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            raw = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            raw = {}
        
        if username in raw:
            return JSONResponse(status_code=409, content={"status": "error", "message": "用户已存在"})
        
        import bcrypt
        import time
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        raw[username] = {
            "password": hashed,
            "role": role,
            "tenant_id": "default",
            "display_name": username,
            "email": "",
            "created_at": time.time(),
        }
        
        # v1.50 R5: 原子写入 — 使用全局文件锁防止并发覆盖
        import os as _os, tempfile as _tempfile
        with _users_file_lock:
            fd, tmp_path = _tempfile.mkstemp(suffix=".json", dir=str(users_file.parent))
            try:
                _os.write(fd, json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8"))
            finally:
                _os.close(fd)
            _os.replace(tmp_path, str(users_file))
        
        # v1.50 R3: 审计日志
        try:
            from src.data_service import log_audit
            log_audit({
                "event_type": "user_created",
                "user_id": getattr(request.state, "user", "admin") if request else "admin",
                "ip": request.client.host if request and request.client else "-",
                "details": {"target_user": username, "role": role},
            })
        except Exception:
            pass
        
        return {"status": "success", "message": f"用户 {username} 创建成功"}
    except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
        logger.exception(f"admin_create_user 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "创建用户服务异常"})


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request = None):
    """删除用户 — v1.50 R3: 防止删除自己，添加审计日志"""
    try:
        # v1.50 R3: 防止管理员删除自己
        current_user = getattr(request.state, "user", "") if request else ""
        if current_user and current_user == user_id:
            return JSONResponse(status_code=400, content={"status": "error", "message": "不能删除自己的账号"})
        
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            raw = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            raw = {}
        
        if user_id not in raw:
            return JSONResponse(status_code=404, content={"status": "error", "message": "用户不存在"})
        
        del raw[user_id]
        
        # v1.50 R5: 原子写入 — 使用全局文件锁防止并发覆盖
        import os as _os, tempfile as _tempfile
        with _users_file_lock:
            fd, tmp_path = _tempfile.mkstemp(suffix=".json", dir=str(users_file.parent))
            try:
                _os.write(fd, json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8"))
            finally:
                _os.close(fd)
            _os.replace(tmp_path, str(users_file))
        
        # v1.50 R3: 审计日志
        try:
            from src.data_service import log_audit
            log_audit({
                "event_type": "user_deleted",
                "user_id": current_user or "admin",
                "ip": request.client.host if request and request.client else "-",
                "details": {"target_user": user_id},
            })
        except Exception:
            pass
        
        return {"status": "success", "message": f"用户 {user_id} 已删除"}
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"admin_delete_user 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "删除用户服务异常"})
