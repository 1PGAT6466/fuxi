"""
auth.py — API 认证中间件 (v1.43)
Bearer Token 认证，保护所有 /api/* 端点
白名单：/api/health, /api/metrics, /api/v2/status（监控用）
"""
import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# 认证 Token（从环境变量读取，默认值用于开发）
API_TOKEN = os.getenv("FUXI_API_TOKEN", "")

# 白名单路径（不需要认证）
WHITELIST = {
    "/api/health",
    "/api/metrics",
    "/api/v2/status",
    "/",
    "/favicon.ico",
    "/api/documents",
    "/index.html",
    "/admin",
}




class InputLimitMiddleware(BaseHTTPMiddleware):
    """输入长度限制：防止超长 prompt 攻击"""
    MAX_BODY_SIZE = 200_000_000  # 100KB
    MAX_QUERY_LEN = 5000

    async def dispatch(self, request: Request, call_next):
        # 限制 query 参数长度
        for key, val in request.query_params.items():
            if len(val) > self.MAX_QUERY_LEN:
                raise HTTPException(status_code=400, detail=f"参数 {key} 超过最大长度 {self.MAX_QUERY_LEN}")

        # 限制 body 大小
        if request.method in ("POST", "PUT"):
            body = await request.body()
            if len(body) > self.MAX_BODY_SIZE:
                raise HTTPException(status_code=413, detail="请求体超过最大长度 100KB")

        return await call_next(request)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 白名单跳过
        if path in WHITELIST or path.startswith("/static/"):
            return await call_next(request)

        # 非 API 路径跳过（前端页面）
        if not path.startswith("/api/"):
            return await call_next(request)

        # 检查 Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token == API_TOKEN:
                return await call_next(request)

        # 也支持 query 参数（方便前端）
        token_param = request.query_params.get("token", "")
        if token_param == API_TOKEN:
            return await call_next(request)

        raise HTTPException(status_code=401, detail="Unauthorized: 无效的认证凭据")
