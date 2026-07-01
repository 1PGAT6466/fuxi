# 兼容层 - 认证中间件
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os, json, hashlib, secrets, time, logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("FUXI_JWT_SECRET", "fuxi-default-secret-change-in-production")
JWT_EXPIRE_HOURS = 24

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 白名单路径
        whitelist = ["/api/health", "/api/auth/login", "/api/auth/register", "/", "/login"]
        if path in whitelist or not path.startswith("/api/"):
            return await call_next(request)
        # 静态资源
        if path.startswith("/static/"):
            return await call_next(request)
        # Token 验证
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        if not token:
            raise HTTPException(401, "未登录")
        return await call_next(request)

class InputLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)
