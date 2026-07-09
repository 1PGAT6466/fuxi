"""
伏羲 v1.50 — 统一 API 响应格式

所有 API 端点返回的 JSON 遵循统一的三段式结构:

成功:
  {"status": "success", "message": "ok", "data": { ... }}

分页:
  {"status": "success", "message": "ok", "data": { "items": [...], "total": N, "page": P, "page_size": S }}

错误:
  {"status": "error", "message": "错误描述", "detail": "可选详情"}

兼容模式 (默认开启):
  # 默认将 data 字段展开到顶层，保持前端对旧格式的兼容性
  # 通过 ?format=v2 或 X-API-Format: v2 请求头可切换到新格式

使用示例:
  from src.api.response import success, error, paginated

  @router.get("/api/foo")
  async def foo():
      return success({"name": "伏羲"})

  @router.post("/api/bar")
  async def bar():
      return error("参数错误", status_code=400, detail="name 字段不能为空")

  @router.get("/api/list")
  async def list_items():
      return paginated(items=[...], total=100, page=1, page_size=20)
"""


import functools
import logging
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("api.response")

# —— 公共常量 ——
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

# —— 核心响应函数 ——

def success(
    data: Any = None,
    message: str = "ok",
    status_code: int = 200,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    构建统一成功响应。

    Args:
        data:   业务数据，可以是 dict / list / 基本类型 / None
        message: 提示信息
        status_code: HTTP 状态码
        extra:   附加的顶层字段 (会合并到响应中)

    Returns:
        JSONResponse 实例

    Example:
        >>> success({"user": "fuxi"})
        {"status": "success", "message": "ok", "data": {"user": "fuxi"}}
    """
    body: Dict[str, Any] = {
        "status": STATUS_SUCCESS,
        "message": message,
        "data": data,
    }
    if extra:
        # 防止 extra 覆盖核心字段 (status, message, data)
        for k, v in extra.items():
            if k not in ("status", "message", "data"):
                body[k] = v

    return JSONResponse(content=body, status_code=status_code)


def paginated(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20,
    *,
    message: str = "ok",
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    构建统一分页响应。

    Args:
        items:     当前页数据列表
        total:     总记录数
        page:      当前页码 (从 1 开始)
        page_size: 每页大小
        message:   提示信息
        extra:     附加字段

    Returns:
        JSONResponse

    Example:
        >>> paginated(items=[...], total=100, page=1, page_size=20)
        {
          "status": "success", "message": "ok",
          "data": {
            "items": [...], "total": 100, "page": 1, "page_size": 20,
            "total_pages": 5
          }
        }
    """
    total_pages = max(1, -(-total // page_size)) if page_size > 0 else 1  # ceiling division

    body: Dict[str, Any] = {
        "status": STATUS_SUCCESS,
        "message": message,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }
    if extra:
        for k, v in extra.items():
            if k not in ("status", "message", "data"):
                body[k] = v

    return JSONResponse(content=body, status_code=200)


def error(
    message: str,
    status_code: int = 400,
    *,
    detail: Optional[str] = None,
    data: Any = None,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    构建统一错误响应。

    Args:
        message:     用户可读的错误描述
        status_code: HTTP 状态码 (4xx / 5xx)
        detail:      可选的详细错误信息 (含调试/排障细节)
        data:        可选的附加数据 (如验证错误列表)
        extra:       附加字段

    Returns:
        JSONResponse

    Example:
        >>> error("认证失败", status_code=401, detail="token has expired")
        {"status": "error", "message": "认证失败", "detail": "token has expired"}
    """
    body: Dict[str, Any] = {
        "status": STATUS_ERROR,
        "message": message,
    }
    if detail is not None:
        body["detail"] = detail
    if data is not None:
        body["data"] = data
    if extra:
        for k, v in extra.items():
            if k not in ("status", "message", "detail", "data"):
                body[k] = v

    return JSONResponse(content=body, status_code=status_code)


# —— 向后兼容装饰器 ——
#
# 规则:
#   - 默认行为: 保持现有格式不变 (前端的 api-client.js 期待直接访问 d.answer / d.results 等顶层字段)
#   - 调用方可通过 ?format=v2 参数或 X-API-Format: v2 请求头明确切换到新格式
#   - 第二步迁移时再统一切到新格式

def _client_wants_v2(request: Optional[Request]) -> bool:
    """检测客户端是否请求 v2 格式"""
    if request is None:
        return False
    # 1. 查询参数
    if request.query_params.get("format") == "v2":
        return True
    # 2. 请求头
    if request.headers.get("X-API-Format", "").lower() == "v2":
        return True
    return False


def backward_compatible(
    data_field: Optional[str] = None,
    *,
    wrap_message: str = "ok",
):
    """
    向后兼容装饰器 — 将函数返回的普通 dict 包装成统一响应。

    当客户端未请求 v2 格式时，保持原始返回不变 (旧格式兼容)。
    当客户端请求 v2 格式 (format=v2 或 X-API-Format: v2)，包装为统一响应。

    用法:
        @backward_compatible(data_field="results")
        async def my_endpoint(request: Request):
            return {"results": [...], "total": 50}

        # 旧客户端 -> {"results": [...], "total": 50}
        # v2 客户端 -> {"status": "success", "message": "ok", "data": {"results": [...], "total": 50}}

    如果函数返回 JSONResponse, 则原样返回。
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数里提取 Request 对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            try:
                result = await func(*args, **kwargs)
            except Exception:  # TODO: Narrow exception type
                raise

            # 如果已经是 JSONResponse，直接返回
            if isinstance(result, JSONResponse):
                return result

            # 不是 v2 请求 → 按原样返回
            if not _client_wants_v2(request):
                return result

            # v2 请求 → 包装为统一响应
            if data_field is not None and isinstance(result, dict) and data_field in result:
                return success(result, message=wrap_message)
            return success(result, message=wrap_message)

        return wrapper
    return decorator


# —— 便捷别名 ——

def ok(
    data: Any = None,
    message: str = "ok",
    **kwargs,
) -> JSONResponse:
    """success() 的别名, 方便已有代码迁移"""
    return success(data=data, message=message, **kwargs)


def not_found(
    message: str = "资源未找到",
    detail: Optional[str] = None,
) -> JSONResponse:
    """404 错误便捷方法"""
    return error(message=message, status_code=404, detail=detail)


def unauthorized(
    message: str = "未登录或认证已过期",
    detail: Optional[str] = None,
) -> JSONResponse:
    """401 错误便捷方法"""
    return error(message=message, status_code=401, detail=detail)


def forbidden(
    message: str = "没有权限",
    detail: Optional[str] = None,
) -> JSONResponse:
    """403 错误便捷方法"""
    return error(message=message, status_code=403, detail=detail)


def bad_request(
    message: str = "请求参数错误",
    detail: Optional[str] = None,
) -> JSONResponse:
    """400 错误便捷方法"""
    return error(message=message, status_code=400, detail=detail)


def server_error(
    message: str = "服务器内部错误",
    detail: Optional[str] = None,
) -> JSONResponse:
    """500 错误便捷方法"""
    return error(message=message, status_code=500, detail=detail)
