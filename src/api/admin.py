# 鍏煎灞?- 绠＄悊璺敱
# v1.44 Phase 1 Fix: 绉婚櫎 require_admin 渚濊禆锛堝皻鏈疄鐜帮級, 浣跨敤 request.state 鍒ゆ柇瑙掕壊
# v1.50 Phase E: 鏂板鍥㈤槦绠＄悊 API锛圕ompany Brain 鏉冮檺闅旂锛?
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
# v1.44 Phase 1: 浣跨敤 RBAC require_role 鏇夸唬鏃х増 require_admin
from src.auth.rbac import require_role
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["绠＄悊"])


# ============ 鍐呴儴杈呭姪鍑芥暟 ============

def _get_chunks_stats():
    """鑾峰彇鏂囨。鍧楃粺璁′俊鎭?""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        total_chunks = len(chunks)
        categories = {}
        for c in chunks:
            cat = c.get("category", "鏈垎绫?)
            categories[cat] = categories.get(cat, 0) + 1
        unique_files = len(set(c.get("file_hash", "") for c in chunks))
        return {
            "total_chunks": total_chunks,
            "unique_files": unique_files,
            "categories": categories,
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"_get_chunks_stats 澶辫触: {e}")
        return {"total_chunks": 0, "unique_files": 0, "categories": {}}


def _load_users():
    """鍔犺浇鐢ㄦ埛鍒楄〃"""
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
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"_load_users 澶辫触: {e}")
        return []


# ============ 璺敱绔偣 ============

@router.get("/api/admin/stats", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_stats(request: Request = None):
    """绠＄悊缁熻 鈥?浠庢暟鎹簱鏌ヨ鐪熷疄缁熻鏁版嵁"""
    try:
        stats = _get_chunks_stats()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "chunks": stats["total_chunks"], "categories": stats["categories"], "unique_files": stats["unique_files"]}, message="绠＄悊缁熻")
        return {"ok": True, "chunks": stats["total_chunks"], "categories": stats["categories"], "unique_files": stats["unique_files"]}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_stats 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/admin/server-status", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def server_status(request: Request = None):
    """鏈嶅姟鍣ㄧ姸鎬?""
    try:
        import time
        from src.config import START_TIME
        uptime = time.time() - START_TIME
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "uptime_seconds": round(uptime), "uptime_hours": round(uptime/3600, 1)}, message="鏈嶅姟鍣ㄧ姸鎬?)
        return {"ok": True, "uptime_seconds": round(uptime), "uptime_hours": round(uptime/3600, 1)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"server_status 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# 鈹€鈹€ 浠诲姟 A.1: /api/admin/status 鍒悕 鈫?/api/admin/server-status 鈹€鈹€
@router.get("/api/admin/status", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_status_alias(request: Request = None):
    """鍓嶇璋冪敤鐨?/api/admin/status 鈥?浠ｇ悊鍒?server-status"""
    return await server_status(request)

# 鈹€鈹€ 浠诲姟 A.2: /api/admin/documents 鏂囨。缁熻 鈹€鈹€
@router.get("/api/admin/documents", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_documents(request: Request = None):
    """绠＄悊闈㈡澘锛氭枃妗ｇ粺璁?""
    try:
        stats = _get_chunks_stats()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "documents": stats}, message="鏂囨。缁熻")
        return {"ok": True, "documents": stats}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_documents 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# 鈹€鈹€ 浠诲姟 A.3: /api/admin/evaluations 鍜?/api/admin/evaluations/run 鈹€鈹€
@router.get("/api/admin/evaluations", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_evaluations(request: Request = None):
    """绠＄悊闈㈡澘锛氳瘎娴嬪垪琛?鈥?浠ｇ悊鍒?evaluation API"""
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
                "latest_report": report or {"message": "鏆傛棤璇勬祴鎶ュ憡"},
            }, message="璇勬祴鍒楄〃")
        return {
            "ok": True,
            "evaluations": history,
            "latest_report": report or {"message": "鏆傛棤璇勬祴鎶ュ憡"},
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_evaluations 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.post("/api/admin/evaluations/run", dependencies=[Depends(require_role("admin"))])
async def admin_evaluations_run():
    """绠＄悊闈㈡澘锛氳Е鍙戣瘎娴嬭繍琛?""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        result = await automation.run_daily_eval()
        return {"ok": True, "result": result}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_evaluations_run 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# 鈹€鈹€ 浠诲姟 A.4: /api/admin/users 鐢ㄦ埛鍒楄〃 鈹€鈹€
@router.get("/api/admin/users", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_users(request: Request = None):
    """绠＄悊闈㈡澘锛氱敤鎴峰垪琛?""
    try:
        users = _load_users()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "users": users, "total": len(users)}, message="鐢ㄦ埛鍒楄〃")
        return {"ok": True, "users": users, "total": len(users)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_users 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ v1.44 Phase 1 Fix: /api/admin/users 鐢ㄦ埛 CRUD 鈹€鈹€

@router.post("/api/admin/users", dependencies=[Depends(require_role("admin"))])
async def admin_create_user(request: Request):
    """绠＄悊闈㈡澘锛氬垱寤虹敤鎴?""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        display_name = body.get("display_name", username)
        role = body.get("role", "user")

        if not username or not password:
            return JSONResponse(
                status_code=400,
                content={"error": "鍙傛暟閿欒", "detail": "鐢ㄦ埛鍚嶅拰瀵嗙爜涓嶈兘涓虹┖"}
            )

        # v1.50 R3 Blue: 绠＄悊鍛樺垱寤虹敤鎴锋椂涔熼渶鏍￠獙瀵嗙爜澶嶆潅搴?
        from src.api.auth_routes import _validate_password_strength
        valid_pw, pw_msg = _validate_password_strength(password)
        if not valid_pw:
            return JSONResponse(
                status_code=400,
                content={"error": "瀵嗙爜寮哄害涓嶈冻", "detail": pw_msg}
            )

        from pathlib import Path
        import time
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        users = json.loads(users_file.read_text(encoding="utf-8")) if users_file.exists() else {}

        if username in users:
            return JSONResponse(
                status_code=400,
                content={"error": "鍙傛暟閿欒", "detail": "鐢ㄦ埛鍚嶅凡瀛樺湪"}
            )

        from src.api.auth_routes import _hash_password
        users[username] = {
            "password": _hash_password(password),  # 鍒涘缓鏃跺嵆浣跨敤 bcrypt 鍝堝笇瀛樺偍
            "role": role,
            "display_name": display_name,
            "created_at": time.time(),
        }

        users_file.parent.mkdir(parents=True, exist_ok=True)
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"username": username, "role": role, "display_name": display_name}, message="鐢ㄦ埛鍒涘缓鎴愬姛")
        return {"ok": True, "username": username, "role": role, "display_name": display_name}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_create_user 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.put("/api/admin/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def admin_update_user(user_id: str, request: Request):
    """绠＄悊闈㈡澘锛氭洿鏂扮敤鎴?""
    try:
        body = await request.json()

        from pathlib import Path
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if not users_file.exists():
            return JSONResponse(status_code=404, content={"error": "鐢ㄦ埛鏈壘鍒?})

        users = json.loads(users_file.read_text(encoding="utf-8"))
        if user_id not in users:
            return JSONResponse(status_code=404, content={"error": "鐢ㄦ埛鏈壘鍒?, "detail": f"鐢ㄦ埛 {user_id} 涓嶅瓨鍦?})

        for key in ("display_name", "role"):
            if key in body:
                users[user_id][key] = body[key]
        if "password" in body:
            # v1.50 R3 Blue: 绠＄悊鍛樻洿鏂板瘑鐮佹椂涔熼渶鏍￠獙澶嶆潅搴?
            from src.api.auth_routes import _validate_password_strength
            new_pw = body["password"]
            valid_pw, pw_msg = _validate_password_strength(new_pw)
            if not valid_pw:
                return JSONResponse(
                    status_code=400,
                    content={"error": "瀵嗙爜寮哄害涓嶈冻", "detail": pw_msg}
                )
            from src.api.auth_routes import _hash_password
            users[user_id]["password"] = _hash_password(new_pw)

        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        if _wants_v2:
            from src.api.response import success
            return success(data={"username": user_id, **users[user_id]}, message="鐢ㄦ埛鏇存柊鎴愬姛")
        return {"ok": True, "username": user_id}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_update_user 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_delete_user(user_id: str, request: Request = None):
    """绠＄悊闈㈡澘锛氬垹闄ょ敤鎴?""
    try:
        from pathlib import Path
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if not users_file.exists():
            return JSONResponse(status_code=404, content={"error": "鐢ㄦ埛鏈壘鍒?})

        users = json.loads(users_file.read_text(encoding="utf-8"))
        if user_id not in users:
            return JSONResponse(status_code=404, content={"error": "鐢ㄦ埛鏈壘鍒?, "detail": f"鐢ㄦ埛 {user_id} 涓嶅瓨鍦?})

        del users[user_id]
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=None, message=f"鐢ㄦ埛 {user_id} 宸插垹闄?)
        return {"ok": True, "message": f"鐢ㄦ埛 {user_id} 宸插垹闄?}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_delete_user 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ============================================================================
# v1.50 Phase E: Company Brain 鏉冮檺闅旂 鈥?鍥㈤槦绠＄悊 API
# ============================================================================

# 鈹€鈹€ GET /api/admin/teams 鈥?鍥㈤槦鍒楄〃 鈹€鈹€

@router.get("/api/admin/teams", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_teams_list(request: Request = None):
    """绠＄悊闈㈡澘锛氬洟闃熷垪琛?

    杩斿洖鎵€鏈夊凡娉ㄥ唽鍥㈤槦鐨勫垪琛紝鍖呮嫭榛樿 public 鍥㈤槦銆?
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()
        teams = pm.list_teams()

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"teams": teams, "total": len(teams)}, message="鍥㈤槦鍒楄〃")
        return {"ok": True, "teams": teams, "total": len(teams)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_teams_list 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ POST /api/admin/teams 鈥?鍒涘缓鍥㈤槦 鈹€鈹€

@router.post("/api/admin/teams", dependencies=[Depends(require_role("admin"))])
async def admin_create_team(request: Request):
    """绠＄悊闈㈡澘锛氬垱寤哄洟闃?

    璇锋眰浣?
        {
            "team_id": "team-eng",      // 鍥㈤槦鍞竴鏍囪瘑锛堝繀濉級
            "name": "宸ョ▼閮?,            // 鍥㈤槦鍚嶇О锛堝繀濉級
            "description": "宸ョ▼閮ㄥ洟闃?,  // 鍥㈤槦鎻忚堪锛堝彲閫夛級
            "member_ids": ["alice", "bob"] // 鍒濆鎴愬憳鍒楄〃锛堝彲閫夛級
        }

    鍒涘缓鑰呰嚜鍔ㄦ垚涓哄洟闃?owner 骞跺姞鍏ュ洟闃熴€?
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
                content={"error": "鍙傛暟閿欒", "detail": "team_id 鍜?name 涓嶈兘涓虹┖"}
            )

        # 鑾峰彇褰撳墠鐢ㄦ埛浣滀负 owner
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
            return success(data=team.to_dict(), message=f"鍥㈤槦 {name} 鍒涘缓鎴愬姛")
        return {"ok": True, "team": team.to_dict()}

    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "鍙傛暟閿欒", "detail": str(e)})
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_create_team 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ GET /api/admin/teams/{team_id} 鈥?鍥㈤槦璇︽儏 鈹€鈹€

@router.get("/api/admin/teams/{team_id}", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_get_team(team_id: str, request: Request = None):
    """绠＄悊闈㈡澘锛氬洟闃熻鎯?""
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()
        team = pm.get_team(team_id)

        if not team:
            return JSONResponse(status_code=404, content={"error": "鍥㈤槦鏈壘鍒?, "detail": f"鍥㈤槦 {team_id} 涓嶅瓨鍦?})

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict(), message="鍥㈤槦璇︽儏")
        return {"ok": True, "team": team.to_dict()}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_get_team 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ DELETE /api/admin/teams/{team_id} 鈥?鍒犻櫎鍥㈤槦 鈹€鈹€

@router.delete("/api/admin/teams/{team_id}", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_delete_team(team_id: str, request: Request = None):
    """绠＄悊闈㈡澘锛氬垹闄ゅ洟闃?

    涓嶅厑璁稿垹闄?'public' 榛樿鍥㈤槦銆?
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        success = pm.delete_team(team_id)
        if not success:
            return JSONResponse(status_code=400, content={"error": "鏃犳硶鍒犻櫎鍥㈤槦", "detail": "鍥㈤槦涓嶅瓨鍦ㄦ垨涓?public 榛樿鍥㈤槦"})

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success as resp_success
            return resp_success(data=None, message=f"鍥㈤槦 {team_id} 宸插垹闄?)
        return {"ok": True, "message": f"鍥㈤槦 {team_id} 宸插垹闄?}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_delete_team 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ POST /api/admin/teams/{team_id}/members 鈥?娣诲姞鍥㈤槦鎴愬憳 鈹€鈹€

@router.post("/api/admin/teams/{team_id}/members", dependencies=[Depends(require_role("admin"))])
async def admin_add_team_member(team_id: str, request: Request):
    """绠＄悊闈㈡澘锛氬悜鍥㈤槦娣诲姞鎴愬憳

    璇锋眰浣?
        {
            "user_id": "alice"    // 瑕佹坊鍔犵殑鐢ㄦ埛 ID锛堝繀濉級
        }
    """
    try:
        body = await request.json()
        user_id = body.get("user_id", "").strip()

        if not user_id:
            return JSONResponse(status_code=400, content={"error": "鍙傛暟閿欒", "detail": "user_id 涓嶈兘涓虹┖"})

        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        ok = pm.add_member(team_id, user_id)
        if not ok:
            return JSONResponse(status_code=404, content={"error": "鍥㈤槦鏈壘鍒?, "detail": f"鍥㈤槦 {team_id} 涓嶅瓨鍦?})

        team = pm.get_team(team_id)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict() if team else {}, message=f"鐢ㄦ埛 {user_id} 宸插姞鍏ュ洟闃?{team_id}")
        return {"ok": True, "team": team.to_dict() if team else {}, "message": f"鐢ㄦ埛 {user_id} 宸插姞鍏ュ洟闃?}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_add_team_member 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ DELETE /api/admin/teams/{team_id}/members/{user_id} 鈥?绉婚櫎鍥㈤槦鎴愬憳 鈹€鈹€

@router.delete("/api/admin/teams/{team_id}/members/{user_id}", dependencies=[Depends(require_role("admin"))])
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def admin_remove_team_member(team_id: str, user_id: str, request: Request = None):
    """绠＄悊闈㈡澘锛氫粠鍥㈤槦绉婚櫎鎴愬憳

    涓嶅厑璁哥Щ闄ゅ洟闃熺殑 owner銆?
    """
    try:
        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        ok = pm.remove_member(team_id, user_id)
        if not ok:
            return JSONResponse(status_code=400, content={"error": "鏃犳硶绉婚櫎鎴愬憳", "detail": "鏃犳硶绉婚櫎鍥㈤槦鎵€鏈夎€呮垨鎴愬憳涓嶅瓨鍦?})

        team = pm.get_team(team_id)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=team.to_dict() if team else {}, message=f"鐢ㄦ埛 {user_id} 宸蹭粠鍥㈤槦 {team_id} 绉婚櫎")
        return {"ok": True, "team": team.to_dict() if team else {}, "message": f"鐢ㄦ埛 {user_id} 宸蹭粠鍥㈤槦绉婚櫎"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"admin_remove_team_member 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# 鈹€鈹€ GET /api/user/teams 鈥?褰撳墠鐢ㄦ埛鎵€灞炲洟闃熷垪琛?鈹€鈹€

@router.get("/api/user/teams")
# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def user_teams(request: Request = None):
    """鑾峰彇褰撳墠鐢ㄦ埛鎵€灞炵殑鍥㈤槦鍒楄〃"""
    try:
        user_id = getattr(request.state, "user", "anonymous") if request else "anonymous"

        from src.api.permissions import get_permission_manager
        pm = get_permission_manager()

        teams = pm.get_user_teams(user_id)
        team_list = [t.to_dict() for t in teams]

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"teams": team_list, "user_id": user_id}, message="鐢ㄦ埛鍥㈤槦鍒楄〃")
        return {"ok": True, "teams": team_list, "user_id": user_id}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"user_teams 澶辫触: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

