# 兼容层 - 认证路由
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hashlib
import bcrypt

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$2b$"):
        return bcrypt.checkpw(password.encode(), stored.encode())
    elif "$" in stored:
        salt, h = stored.split("$", 1)
        if hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h:
            return True
    return False

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginRequest):
    from src.api.auth import create_jwt_token
    import json
    from pathlib import Path
    
    users_file = Path("data/users.json")
    if users_file.exists():
        users = json.loads(users_file.read_text(encoding="utf-8"))
    else:
        users = {}
    
    user = users.get(body.username)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    
    stored = user.get("password", "")
    if not _verify_password(body.password, stored):
        raise HTTPException(401, "用户名或密码错误")
    
    if not stored.startswith("$2b$"):
        user["password"] = _hash_password(body.password)
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    
    token = create_jwt_token(body.username, user.get("role", "user"))
    
    return {"token": token, "username": body.username, "role": user.get("role", "user"), "display_name": user.get("display_name", body.username)}

@router.post("/register")
def register(body: LoginRequest):
    import json, time
    from pathlib import Path
    
    users_file = Path("data/users.json")
    if users_file.exists():
        users = json.loads(users_file.read_text(encoding="utf-8"))
    else:
        users = {}
    
    if body.username in users:
        raise HTTPException(400, "用户名已存在")
    
    users[body.username] = {
        "password": _hash_password(body.password),
        "role": "user",
        "display_name": body.username,
        "created_at": time.time()
    }
    
    users_file.parent.mkdir(parents=True, exist_ok=True)
    users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {"ok": True, "username": body.username}
