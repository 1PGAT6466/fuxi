"""
auth_routes.py — /api/auth/login + /api/auth/register
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth", tags=["认证"])

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=4)
    display_name: str = Field("", max_length=64)


@router.post("/login")
def login(body: LoginRequest):
    """用户登录，返回 JWT Token"""
    from src.api.auth import authenticate_user, _make_token
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = _make_token(user["username"], user.get("role", "user"))
    return {
        "token": token,
        "username": user["username"],
        "role": user.get("role", "user"),
        "display_name": user.get("display_name", user["username"]),
    }


@router.post("/register")
def register(body: RegisterRequest):
    """用户注册"""
    from src.api.auth import register_user
    result = register_user(body.username, body.password, role="user", display_name=body.display_name)
    if "error" in result:
        raise HTTPException(400, result["error"])
    if not result.get("ok"):
        raise HTTPException(500, "注册失败")
    return {
        "ok": True,
        "username": result.get("username", body.username),
        "message": "注册成功",
    }
