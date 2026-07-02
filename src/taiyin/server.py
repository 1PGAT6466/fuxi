"""
server.py — 太阴·显化 对外接口中枢
合并皮肤(屏障)+三焦(通道)的能力

职责：
1. 统一 HTTP 入口（FastAPI 路由）
2. 认证 + 限流
3. 请求分发到四象
4. 响应格式化
"""
import logging
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("taiyin.server")


class TaiyinServer(SymbolBase):
    """太阴·显化 — 对外接口中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="taiyin",
            name="太阴·显化",
            emoji="🌑",
            description="对外接口中枢：一个入口，一个出口"
        )
        self._request_count = 0
        self._error_count = 0
        self._start_time = time.time()

    def _get_metrics(self) -> dict:
        """返回接口指标"""
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "uptime_seconds": time.time() - self._start_time,
        }

    def register_routes(self, app: FastAPI):
        """注册所有路由到 FastAPI 应用"""
        
        @app.get("/api/symbols/status")
        async def symbols_status():
            """四象状态查询"""
            return {
                "symbols": {
                    "shaoyang": self.meridian.get_symbol_status("shaoyang"),
                    "taiyang": self.meridian.get_symbol_status("taiyang"),
                    "shaoyin": self.meridian.get_symbol_status("shaoyin"),
                    "taiyin": self.meridian.get_symbol_status("taiyin"),
                }
            }

        @app.post("/api/chat")
        async def chat(request: Request):
            """统一对话入口"""
            self._request_count += 1
            try:
                body = await request.json()
                query = body.get("query", "")
                
                # 分发到少阴·炼化
                shaoyin = self.meridian.get_symbol("shaoyin")
                if shaoyin:
                    result = await shaoyin.think(query)
                    return result
                
                return {"answer": "系统未就绪", "confidence": 0}
            except Exception as e:
                self._error_count += 1
                logger.error(f"对话失败: {e}")
                raise HTTPException(500, str(e))

        @app.post("/api/search")
        async def search(request: Request):
            """统一搜索入口"""
            self._request_count += 1
            try:
                body = await request.json()
                query = body.get("query", "")
                top_k = body.get("top_k", 15)
                
                # 分发到太阳·筑基
                taiyang = self.meridian.get_symbol("taiyang")
                if taiyang:
                    results = await taiyang.refine(query, top_k=top_k)
                    return {"results": results, "count": len(results)}
                
                return {"results": [], "count": 0}
            except Exception as e:
                self._error_count += 1
                logger.error(f"搜索失败: {e}")
                raise HTTPException(500, str(e))

        @app.post("/api/documents/upload")
        async def upload_document(request: Request):
            """文档上传入口"""
            self._request_count += 1
            try:
                # 分发到少阳·消化
                shaoyang = self.meridian.get_symbol("shaoyang")
                if shaoyang:
                    # TODO: 实现文件上传逻辑
                    return {"status": "ok", "message": "文档上传成功"}
                
                return {"status": "error", "message": "系统未就绪"}
            except Exception as e:
                self._error_count += 1
                logger.error(f"上传失败: {e}")
                raise HTTPException(500, str(e))

        @app.get("/api/growth/overview")
        async def growth_overview():
            """成长指标查询"""
            try:
                from src.growth.engine import GrowthEngine
                engine = GrowthEngine()
                stats = engine.get_stats()
                return {"growth": stats}
            except Exception as e:
                logger.error(f"成长指标查询失败: {e}")
                return {"growth": {}}

        @app.get("/api/health")
        async def health():
            """健康检查"""
            return {
                "status": "ok",
                "version": "1.44",
                "symbols": {
                    "shaoyang": self.meridian.is_alive("shaoyang"),
                    "taiyang": self.meridian.is_alive("taiyang"),
                    "shaoyin": self.meridian.is_alive("shaoyin"),
                    "taiyin": self.meridian.is_alive("taiyin"),
                }
            }

        logger.info("[太阴] 路由注册完成")
