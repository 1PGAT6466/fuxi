# 兼容层 - 认证路由
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["认证"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginRequest):
    from src.api.auth import create_jwt_token
    import hashlib, json
    from pathlib import Path
    
    users_file = Path("data/users.json")
    if users_file.exists():
        users = json.loads(users_file.read_text(encoding="utf-8"))
    else:
        users = {}
    
    user = users.get(body.username)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    
    # 验证密码
    stored = user.get("password", "")
    if "$" in stored:
        salt, h = stored.split("$", 1)
        if hashlib.sha256(f"{salt}:{body.password}".encode()).hexdigest() != h:
            raise HTTPException(401, "用户名或密码错误")
    
    # 生成标准JWT token
    token = create_jwt_token(body.username, user.get("role", "user"))
    
    return {"token": token, "username": body.username, "role": user.get("role", "user"), "display_name": user.get("display_name", body.username)}

@router.post("/register")
def register(body: LoginRequest):
    import json, time, hashlib, secrets
    from pathlib import Path
    
    users_file = Path("data/users.json")
    if users_file.exists():
        users = json.loads(users_file.read_text(encoding="utf-8"))
    else:
        users = {}
    
    if body.username in users:
        raise HTTPException(400, "用户名已存在")
    
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{body.password}".encode()).hexdigest()
    users[body.username] = {
        "password": f"{salt}${h}",
        "role": "user",
        "display_name": body.username,
        "created_at": time.time()
    }
    
    users_file.parent.mkdir(parents=True, exist_ok=True)
    users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {"ok": True, "username": body.username}
