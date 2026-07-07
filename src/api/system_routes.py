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
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


# ============ 审计日志 API ============

@router.get("/api/audit/logs")
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


@router.get("/api/audit/stats")
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
    gua_names = ["qian", "kun", "zhen", "xun", "kan", "li", "gen", "dui"]

    # 尝试从 IntentBus 获取注册表
    intent_bus = getattr(request.app.state, "intent_bus", None)

    for name in gua_names:
        try:
            if intent_bus is not None:
                # 通过 IntentBus 检查是否注册
                registered = name in intent_bus.get_registered_guas()
                if registered:
                    bagua_result[name] = "healthy"
                else:
                    bagua_result[name] = "unregistered"
            else:
                # 无 IntentBus → 尝试直接 call health_check()
                fuxi = getattr(request.app.state, "fuxi", None)
                if fuxi is not None and hasattr(fuxi, "health_check"):
                    health = fuxi.health_check()
                    bagua_result[name] = health.get("status", "unknown")
                else:
                    bagua_result[name] = "unknown"
        except Exception:
            bagua_result[name] = "error"

    return bagua_result


# ============ 健康检查 ============

@router.get("/api/health")
async def health_check(request: Request):
    """健康检查 — v2.1 扩展响应格式

    支持格式参数：
      - format=legacy (默认): 旧格式 {status, checks, timestamp}
      - format=v2:          v2 封装格式 {status, message, data}
      - format=extended:    v2.1 扩展格式 {status, core, bagua, infra, alerts, timestamp}

    Header 方式:
      - X-API-Format: legacy | v2 | extended
    """
    from src.api.response import success, error

    # 确定格式
    fmt = request.query_params.get("format", "")
    if not fmt:
        fmt = request.headers.get("X-API-Format", "legacy").lower()

    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()

        if fmt == "extended":
            # v2.1 扩展格式：八卦 + 基础设施
            result = await checker.check_extended()
            return success(data=result, message="扩展健康检查完成")

        # 核心检查
        result = await checker.check_all()

        # v2.1: 总是尝试附加八卦健康状态
        try:
            bagua_status = await _get_bagua_health(request)
            if bagua_status:
                result["bagua"] = bagua_status
                result["engine"] = getattr(request.app.state, "engine", "v2")
                result["intent_mode"] = getattr(request.app.state, "intent_mode", "rule_based")
        except Exception:
            pass

        if fmt == "v2":
            return success(
                data=result,
                message="系统运行正常" if result.get("status") == "healthy" else "部分组件异常"
            )

        # 默认保持旧格式兼容
        return result
    except Exception as e:
        if fmt in ("v2", "extended"):
            return error("健康检查失败", status_code=500, detail=str(e))
        return {"status": "error", "error": str(e)}


# ============ 八卦健康检查 ============

@router.get("/api/health/bagua")
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
    except Exception as e:
        return error("八卦健康检查失败", status_code=500, detail=str(e))


@router.get("/api/health/infra")
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
    except Exception as e:
        return error("基础设施健康检查失败", status_code=500, detail=str(e))


@router.get("/api/health/alerts")
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
    except Exception as e:
        return error("告警评估失败", status_code=500, detail=str(e))


@router.get("/api/health/alert-rules")
async def health_check_alert_rules(request: Request):
    """告警规则列表 — v2.1

    返回所有已配置的告警规则。
    """
    from src.api.response import success
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        return success(data={"rules": checker.get_alert_rules()})
    except Exception as e:
        return success(data={"rules": [], "error": str(e)})


# ============ 系统资源统计 ============

@router.get("/api/system/stats")
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
    except Exception as e:
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取系统统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============ 缓存统计 ============

@router.get("/api/cache/stats")
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
    except Exception as e:
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取缓存统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============ 错误追踪统计 ============

@router.get("/api/errors/stats")
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
    except Exception as e:
        if request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2":
            return error("获取错误统计失败", status_code=500, detail=str(e))
        return {"error": str(e)}
