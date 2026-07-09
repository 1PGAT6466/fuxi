# 兼容层 - 管理路由
# v1.44 Phase 1 Fix: 移除 require_admin 依赖（尚未实现）, 使用 request.state 判断角色
# v1.50 Phase E: 新增团队管理 API（Company Brain 权限隔离）
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from src.api.auth import require_admin
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

@router.get("/api/admin/stats", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_stats(request: Request = None):
    """管理统计 — 从数据库查询真实统计数据"""
    try:
        stats = _get_chunks_stats()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "chunks": stats["total_chunks"], "categories": stats["categories"], "unique_files": stats["unique_files"]}, message="管理统计")
        return {"ok": True, "chunks": stats["total_chunks"], "categories": stats["categories"], "unique_files": stats["unique_files"]}
    except Exception as e:
        logger.exception(f"admin_stats 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/admin/server-status", dependencies=[Depends(require_admin)])
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
@router.get("/api/admin/status", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_status_alias(request: Request = None):
    """前端调用的 /api/admin/status — 代理到 server-status"""
    return await server_status(request)

# ── 任务 A.2: /api/admin/documents 文档统计 ──
@router.get("/api/admin/documents", dependencies=[Depends(require_admin)])
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
@router.get("/api/admin/evaluations", dependencies=[Depends(require_admin)])
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

@router.post("/api/admin/evaluations/run", dependencies=[Depends(require_admin)])
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
@router.get("/api/admin/users", dependencies=[Depends(require_admin)])
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


# ── v1.44 Phase 1 Fix: /api/admin/users 用户 CRUD ──

@router.post("/api/admin/users", dependencies=[Depends(require_admin)])
async def admin_create_user(request: Request):
    """管理面板：创建用户"""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        display_name = body.get("display_name", username)
        role = body.get("role", "user")

        if not username or not password:
            return JSONResponse(
                status_code=400,
                content={"error": "参数错误", "detail": "用户名和密码不能为空"}
            )

        from pathlib import Path
        import time
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        users = json.loads(users_file.read_text(encoding="utf-8")) if users_file.exists() else {}

        if username in users:
            return JSONResponse(
                status_code=400,
                content={"error": "参数错误", "detail": "用户名已存在"}
            )

        from src.api.auth_routes import _hash_password
        users[username] = {
            "password": _hash_password(password),  # 创建时即使用 bcrypt 哈希存储
            "role": role,
            "display_name": display_name,
            "created_at": time.time(),
        }

        users_file.parent.mkdir(parents=True, exist_ok=True)
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"username": username, "role": role, "display_name": display_name}, message="用户创建成功")
        return {"ok": True, "username": username, "role": role, "display_name": display_name}
    except Exception as e:
        logger.exception(f"admin_create_user 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.put("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def admin_update_user(user_id: str, request: Request):
    """管理面板：更新用户"""
    try:
        body = await request.json()

        from pathlib import Path
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if not users_file.exists():
            return JSONResponse(status_code=404, content={"error": "用户未找到"})

        users = json.loads(users_file.read_text(encoding="utf-8"))
        if user_id not in users:
            return JSONResponse(status_code=404, content={"error": "用户未找到", "detail": f"用户 {user_id} 不存在"})

        for key in ("display_name", "role"):
            if key in body:
                users[user_id][key] = body[key]
        if "password" in body:
            from src.api.auth_routes import _hash_password
            users[user_id]["password"] = _hash_password(body["password"])

        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        if _wants_v2:
            from src.api.response import success
            return success(data={"username": user_id, **users[user_id]}, message="用户更新成功")
        return {"ok": True, "username": user_id}
    except Exception as e:
        logger.exception(f"admin_update_user 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_delete_user(user_id: str, request: Request = None):
    """管理面板：删除用户"""
    try:
        from pathlib import Path
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if not users_file.exists():
            return JSONResponse(status_code=404, content={"error": "用户未找到"})

        users = json.loads(users_file.read_text(encoding="utf-8"))
        if user_id not in users:
            return JSONResponse(status_code=404, content={"error": "用户未找到", "detail": f"用户 {user_id} 不存在"})

        del users[user_id]
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=None, message=f"用户 {user_id} 已删除")
        return {"ok": True, "message": f"用户 {user_id} 已删除"}
    except Exception as e:
        logger.exception(f"admin_delete_user 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ============================================================================
# v1.50 Phase E: Company Brain 权限隔离 — 团队管理 API
# ============================================================================

# ── GET /api/admin/teams — 团队列表 ──

@router.get("/api/admin/teams", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_teams_list(request: Request = None):
    """管理面板：团队列表

    返回所有已注册团队的列表，包括默认 public 团队。
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()
        teams = pm.list_teams()

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"teams": teams, "total": len(teams)}, message="团队列表")
        return {"ok": True, "teams": teams, "total": len(teams)}
    except Exception as e:
        logger.exception(f"admin_teams_list 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── POST /api/admin/teams — 创建团队 ──

@router.post("/api/admin/teams", dependencies=[Depends(require_admin)])
async def admin_create_team(request: Request):
    """管理面板：创建团队

    请求体:
        {
            "team_id": "team-eng",      // 团队唯一标识（必填）
            "name": "工程部",            // 团队名称（必填）
            "description": "工程部团队",  // 团队描述（可选）
            "member_ids": ["alice", "bob"] // 初始成员列表（可选）
        }

    创建者自动成为团队 owner 并加入团队。
    """
    try:
        body = await request.json()
        team_id = body.get("team_id", "").strip()
        name = body.get("name", "").strip()
        description = body.get("description", "")
        member_ids = body.get("member_ids", [])

        if not team_id or not name:
            return JSONResponse(
                status_code=400,
                content={"error": "参数错误", "detail": "team_id 和 name 不能为空"}
            )

        # 获取当前用户作为 owner
        owner_id = getattr(request.state, "user", "admin") if request else "admin"

        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        team = pm.create_team(
            team_id=team_id,
            name=name,
            owner_id=owner_id,
            description=description,
            member_ids=member_ids,
        )

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict(), message=f"团队 {name} 创建成功")
        return {"ok": True, "team": team.to_dict()}

    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "参数错误", "detail": str(e)})
    except Exception as e:
        logger.exception(f"admin_create_team 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── GET /api/admin/teams/{team_id} — 团队详情 ──

@router.get("/api/admin/teams/{team_id}", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_get_team(team_id: str, request: Request = None):
    """管理面板：团队详情"""
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()
        team = pm.get_team(team_id)

        if not team:
            return JSONResponse(status_code=404, content={"error": "团队未找到", "detail": f"团队 {team_id} 不存在"})

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict(), message="团队详情")
        return {"ok": True, "team": team.to_dict()}
    except Exception as e:
        logger.exception(f"admin_get_team 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── DELETE /api/admin/teams/{team_id} — 删除团队 ──

@router.delete("/api/admin/teams/{team_id}", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_delete_team(team_id: str, request: Request = None):
    """管理面板：删除团队

    不允许删除 'public' 默认团队。
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        success = pm.delete_team(team_id)
        if not success:
            return JSONResponse(status_code=400, content={"error": "无法删除团队", "detail": "团队不存在或为 public 默认团队"})

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success as resp_success
            return resp_success(data=None, message=f"团队 {team_id} 已删除")
        return {"ok": True, "message": f"团队 {team_id} 已删除"}
    except Exception as e:
        logger.exception(f"admin_delete_team 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── POST /api/admin/teams/{team_id}/members — 添加团队成员 ──

@router.post("/api/admin/teams/{team_id}/members", dependencies=[Depends(require_admin)])
async def admin_add_team_member(team_id: str, request: Request):
    """管理面板：向团队添加成员

    请求体:
        {
            "user_id": "alice"    // 要添加的用户 ID（必填）
        }
    """
    try:
        body = await request.json()
        user_id = body.get("user_id", "").strip()

        if not user_id:
            return JSONResponse(status_code=400, content={"error": "参数错误", "detail": "user_id 不能为空"})

        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        ok = pm.add_member(team_id, user_id)
        if not ok:
            return JSONResponse(status_code=404, content={"error": "团队未找到", "detail": f"团队 {team_id} 不存在"})

        team = pm.get_team(team_id)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict() if team else {}, message=f"用户 {user_id} 已加入团队 {team_id}")
        return {"ok": True, "team": team.to_dict() if team else {}, "message": f"用户 {user_id} 已加入团队"}
    except Exception as e:
        logger.exception(f"admin_add_team_member 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── DELETE /api/admin/teams/{team_id}/members/{user_id} — 移除团队成员 ──

@router.delete("/api/admin/teams/{team_id}/members/{user_id}", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_remove_team_member(team_id: str, user_id: str, request: Request = None):
    """管理面板：从团队移除成员

    不允许移除团队的 owner。
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        ok = pm.remove_member(team_id, user_id)
        if not ok:
            return JSONResponse(status_code=400, content={"error": "无法移除成员", "detail": "无法移除团队所有者或成员不存在"})

        team = pm.get_team(team_id)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict() if team else {}, message=f"用户 {user_id} 已从团队 {team_id} 移除")
        return {"ok": True, "team": team.to_dict() if team else {}, "message": f"用户 {user_id} 已从团队移除"}
    except Exception as e:
        logger.exception(f"admin_remove_team_member 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── GET /api/user/teams — 当前用户所属团队列表 ──

@router.get("/api/user/teams")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def user_teams(request: Request = None):
    """获取当前用户所属的团队列表"""
    try:
        user_id = getattr(request.state, "user", "anonymous") if request else "anonymous"

        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        teams = pm.get_user_teams(user_id)
        team_list = [t.to_dict() for t in teams]

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"teams": team_list, "user_id": user_id}, message="用户团队列表")
        return {"ok": True, "teams": team_list, "user_id": user_id}
    except Exception as e:
        logger.exception(f"user_teams 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
