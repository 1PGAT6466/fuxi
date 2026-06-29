"""
services/error_handler.py — 统一异常体系
设计原则：
  - 所有 伏羲·内世界 异常继承 KbError
  - 子类细化语义（超时/不可用/解析失败等）
  - FastAPI exception_handler 统一捕获 → 结构化 JSON 响应
  - 禁止静默吞错——所有异常必须记录日志
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class KbError(Exception):
    """知识库异常基类"""
    code: str = "KB_ERROR"
    status: int = 500
    message: str = "知识库服务内部错误"

    def __init__(self, message: str = None, detail: dict = None):
        self.message = message or self.message
        self.detail = detail or {}
        super().__init__(self.message)

    def to_response(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
            }
        }


class SearchTimeoutError(KbError):
    code = "SEARCH_TIMEOUT"
    status = 504
    message = "搜索超时，请简化查询重试"


class EmbedderUnavailableError(KbError):
    code = "EMBEDDER_DOWN"
    status = 503
    message = "向量服务不可用"


class RerankerUnavailableError(KbError):
    code = "RERANKER_DOWN"
    status = 503
    message = "精排服务不可用"


class LlmUnavailableError(KbError):
    code = "LLM_DOWN"
    status = 503
    message = "AI 服务不可用"


class ParseError(KbError):
    code = "PARSE_ERROR"
    status = 400
    message = "文档解析失败"


class DuplicateFileError(KbError):
    code = "DUPLICATE_FILE"
    status = 409
    message = "文件内容未变化，已存在"


class VectorStoreError(KbError):
    code = "VECTOR_STORE_ERROR"
    status = 500
    message = "向量存储操作失败"


class IndexingTimeoutError(KbError):
    code = "INDEXING_TIMEOUT"
    status = 504
    message = "文档索引超时"


class InvalidQueryError(KbError):
    code = "INVALID_QUERY"
    status = 400
    message = "查询参数无效"


class GraphUnavailableError(KbError):
    code = "GRAPH_DOWN"
    status = 503
    message = "知识图谱不可用"


def setup_error_handlers(app):
    """向 FastAPI app 注册统一异常处理器"""

    @app.exception_handler(KbError)
    async def kb_error_handler(request: Request, exc: KbError):
        logger.error(f"[{exc.code}] {exc.message} | {exc.detail}")
        return JSONResponse(
            status_code=exc.status,
            content=exc.to_response(),
        )

    @app.exception_handler(Exception)
    async def catch_all_handler(request: Request, exc: Exception):
        """兜底：未知异常统一格式"""
        # FastAPI HTTPException 保持原始状态码
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}},
            )
        logger.error(f"[UNHANDLED] {type(exc).__name__}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务内部错误",
                    "detail": {"type": type(exc).__name__},
                }
            },
        )
