"""
伏羲 v1.50 — 系统路由模块
=========================
从 server.py 拆分出来的系统级端点:
  - /api/health       → 健康检查
  - /api/system/stats → 系统资源统计
  - /api/cache/stats  → 缓存命中率统计
  - /api/errors/stats → 错误追踪统计

迁移日期: 2026-07-06
原位置: server.py (inline routes, ~L250-L290)
"""

import logging
from fastapi import APIRouter, Request, Depends
from src.api.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


# ============ 审计日志 API ============

@router.get("/api/audit/logs", dependencies=[Depends(require_admin)])
async def audit_logs(
    user: str = None,
    action: str = None,
    days: int = 1,
    limit: int = 100,
):
    """查询审计日志"""
    from src.infra.audit_log import query_audit
    from src.api.response import success
    results = query_audit(user=user, action=action, days=days, limit=limit)
    return success(data={"entries": results, "count": len(results)})


@router.get("/api/audit/stats", dependencies=[Depends(require_admin)])
async def audit_stats(days: int = 7):
    """审计日志统计"""
    from src.infra.audit_log import get_audit_stats
    from src.api.response import success
    return success(data=get_audit_stats(days=days))


# ============ 八卦健康状态获取 ============

async def _get_bagua_health(request: Request) -> dict:
    """v2.1: 获取所有八卦的健康状态

    从 app.state 或运行时实例获取各卦的 health_check() 结果。

    Returns:
        {
            "qian": "healthy",
            "kun": "healthy",
            "zhen": "degraded",
            ...
        }
    """
    bagua_result = {}
    # 英文查找名 → IntentBus 中的注册名映射
    # 乾卦 GUA_NAME="乾"（中文），其他卦 GUA_NAME 为英文
    gua_name_map: dict[str, str] = {
        "qian": "\u4e7e",  # 乾
        "kun": "kun",
        "zhen": "zhen",
        "xun": "xun",
        "kan": "kan",
        "li": "li",
        "gen": "gen",
        "dui": "dui",
    }

    # 尝试从 IntentBus 获取注册表
    intent_bus = getattr(request.app.state, "intent_bus", None)

    for api_name, registered_name in gua_name_map.items():
        try:
            if intent_bus is not None:
                # 通过 IntentBus 检查是否注册
                registered = registered_name in intent_bus.get_registered_guas()
                if registered:
                    bagua_result[api_name] = "healthy"
                else:
                    bagua_result[api_name] = "unregistered"
            else:
                # 无 IntentBus → 尝试直接 call health_check()
                fuxi = getattr(request.app.state, "fuxi", None)
                if fuxi is not None and hasattr(fuxi, "health_check"):
                    health = fuxi.health_check()
                    bagua_result[api_name] = health.get("status", "unknown")
                else:
                    bagua_result[api_name] = "unknown"
        except Exception:  # TODO: Narrow exception type
            bagua_result[api_name] = "error"

    return bagua_result


# ============ 健康检查 ============

@router.get("/api/health")
async def health_check(request: Request):
    """健康检查 — v2.1 扩展响应格式
    
    v1.50 R3 Blue 安全修复: 
    - 未认证用户仅返回基本状态，已认证管理员才返回完整诊断信息
    - 添加速率限制防止滥用

    支持格式参数：
      - format=legacy (默认): 旧格式 {status, checks, timestamp}
      - format=v2:          v2 封装格式 {status, message, data}
      - format=extended:    v2.1 扩展格式 {status, core, bagua, infra, alerts, timestamp}

    Header 方式:
      - X-API-Format: legacy | v2 | extended
    """
    from src.api.response import success, error
    
    # v1.50 R3 Blue: 健康检查端点速率限制 — 每分钟最多30次请求
    # 防止健康检查端点被滥用进行 DoS 攻击
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        from src.infra.rate_limiter import get_global_rate_limiter
        limiter = get_global_rate_limiter("health_check", max_requests=30, window_sec=60)
        if not limiter.acquire():
            return error("健康检查请求过于频繁", status_code=429)
    except Exception:
        pass  # 速率限制失败不阻止健康检查

    # 确定格式
    fmt = request.query_params.get("format", "")
    if not fmt:
        fmt = request.headers.get("X-API-Format", "legacy").lower()

    # v1.50 R3 Blue: 判断用户是否已认证
    is_authenticated = hasattr(request.state, 'user') and request.state.user != 'anonymous'
    is_admin = hasattr(request.state, 'role') and request.state.role == 'admin'

    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()

        if fmt == "extended":
            # v2.1 扩展格式：仅管理员可查看完整信息
            if not is_admin:
                return error("需要管理员权限查看扩展健康信息", status_code=403)
            result = await checker.check_extended()
            return success(data=result, message="扩展健康检查完成")

        # 核心检查
        result = await checker.check_all()

        # v1.50 R3 Blue: 仅对已认证用户附加详细八卦健康状态和系统信息
        # 未认证用户仅能看到基础的 healthy/degraded 状态
        if is_authenticated:
            try:
                bagua_status = await _get_bagua_health(request)
                if bagua_status:
                    result["bagua"] = bagua_status
                    result["engine"] = getattr(request.app.state, "engine", "v2")
                    result["intent_mode"] = getattr(request.app.state, "intent_mode", "rule_based")
            except Exception:  # TODO: Narrow exception type
                pass
        else:
            # v1.50 R3 Blue: 未认证用户 — 移除敏感信息，仅保留基本状态
            # 保留顶层 status，移除 database/vector_store/llm/intent_bus/bagua 等内部架构细节
            sensitive_keys = ["database", "vector_store", "llm", "intent_bus", "bagua", "engine", "intent_mode"]
            for key in sensitive_keys:
                result.pop(key, None)
            # 也移除 checks 中的子组件细节
            checks = result.get("checks", {})
            if isinstance(checks, dict):
                for sk in sensitive_keys:
                    checks.pop(sk, None)

        if fmt == "v2":
            return success(
                data=result,
                message="系统运行正常" if result.get("status") == "healthy" else "部分组件异常"
            )

        # 默认保持旧格式兼容
        return result
    except Exception as e:  # TODO: Narrow exception type
        if fmt in ("v2", "extended"):
            return error("健康检查失败", status_code=500, detail=str(e))
        return {"status": "error", "error": str(e)}


# ============ 八卦健康检查 ============

@router.get("/api/health/bagua", dependencies=[Depends(require_admin)])
async def health_check_bagua(request: Request):
    """八卦级健康检查 — v2.1

    返回每个八卦模块的健康等级、断路器状态和依赖状态。
    """
    from src.api.response import success, error
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        result = await checker.check_bagua()
        return success(data=result, message="八卦健康检查完成")
    except Exception as e:  # TODO: Narrow exception type
        return error("八卦健康检查失败", status_code=500, detail=str(e))


@router.get("/api/health/infra", dependencies=[Depends(require_admin)])
async def health_check_infra(request: Request):
    """基础设施健康检查 — v2.1

    返回连接池、LLM API 等基础设施组件的健康状态。
    """
    from src.api.response import success, error
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        result = await checker.check_infra()
        return success(data=result, message="基础设施健康检查完成")
    except Exception as e:  # TODO: Narrow exception type
        return error("基础设施健康检查失败", status_code=500, detail=str(e))


@router.get("/api/health/alerts", dependencies=[Depends(require_admin)])
async def health_check_alerts(request: Request):
    """告警规则评估 — v2.1

    返回当前触发的告警规则列表。
    """
    from src.api.response import success, error
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        result = await checker.evaluate_alerts()
        return success(data={"alerts": result, "count": len(result)}, message="告警评估完成")
    except Exception as e:  # TODO: Narrow exception type
        return error("告警评估失败", status_code=500, detail=str(e))


@router.get("/api/health/alert-rules", dependencies=[Depends(require_admin)])
async def health_check_alert_rules(request: Request):
    """告警规则列表 — v2.1

    返回所有已配置的告警规则。
    """
    from src.api.response import success
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        return success(data={"rules": checker.get_alert_rules()})
    except Exception as e:  # TODO: Narrow exception type
        return success(data={"rules": [], "error": str(e)})


# ============ 系统资源统计 ============

@router.get("/api/system/stats", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def system_stats(request: Request):
    """系统统计"""
    from src.api.response import success, error
    try:
        from src.infra.system_monitor import get_system_monitor
        result = get_system_monitor().get_system_stats()
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return success(data=result, message="系统统计")
        return result
    except Exception as e:  # TODO: Narrow exception type
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取系统统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============ 缓存统计 ============

@router.get("/api/cache/stats", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def cache_stats(request: Request):
    """缓存统计"""
    from src.api.response import success, error
    try:
        from src.infra.cache_stats import get_cache_stats
        result = get_cache_stats().get_stats()
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return success(data=result, message="缓存统计")
        return result
    except Exception as e:  # TODO: Narrow exception type
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取缓存统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============ 错误追踪统计 ============

@router.get("/api/errors/stats", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def error_stats(request: Request):
    """错误统计"""
    from src.api.response import success, error
    try:
        from src.infra.error_tracker import get_error_tracker
        result = get_error_tracker().get_error_stats()
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return success(data=result, message="错误统计")
        return result
    except Exception as e:  # TODO: Narrow exception type
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取错误统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}
