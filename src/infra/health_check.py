"""
health_check.py — 健康检查（v2.1 扩展版）
系统状态 + 组件状态 + 八卦级健康 + 基础设施 + 告警规则
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("infra.health_check")


# ============================================================================
# 告警规则配置
# ============================================================================

@dataclass
class AlertRule:
    """告警规则定义"""
    name: str
    description: str
    severity: str  # critical / warning / info
    condition_fn_name: str  # 检查函数名
    threshold: Any
    enabled: bool = True


# 告警规则配置表
ALERT_RULES: List[AlertRule] = [
    AlertRule(
        name="llm_failure_rate_high",
        description="LLM 调用失败率超过 5%",
        severity="critical",
        condition_fn_name="check_llm_failure_rate",
        threshold=0.05,
    ),
    AlertRule(
        name="gua_consecutive_failures",
        description="某卦连续 5 次执行失败",
        severity="critical",
        condition_fn_name="check_gua_consecutive_failures",
        threshold=5,
    ),
    AlertRule(
        name="circuit_breaker_open_long",
        description="断路器 OPEN 状态超过 2 分钟",
        severity="warning",
        condition_fn_name="check_circuit_open_duration",
        threshold=120.0,  # 秒
    ),
    AlertRule(
        name="connection_pool_high_usage",
        description="连接池使用率超过 80%",
        severity="warning",
        condition_fn_name="check_connection_pool_usage",
        threshold=0.80,
    ),
]


# ============================================================================
# 八卦健康等级
# ============================================================================

class GuaHealthLevel(Enum):
    """八卦健康等级"""
    FULL = "full"           # 全功能正常
    DEGRADED = "degraded"   # 降级运行
    MINIMAL = "minimal"     # 最低限度
    OFF = "off"             # 完全关闭


# ============================================================================
# HealthChecker 扩展版
# ============================================================================

class HealthChecker:
    """健康检查器（v2.1 扩展）"""

    def __init__(self):
        self._checks: Dict[str, Any] = {}
        self._bagua_checks: Dict[str, Any] = {}
        self._infra_checks: Dict[str, Any] = {}
        self._alert_rules: List[AlertRule] = list(ALERT_RULES)

    # ---- 注册 ----

    def register_check(self, name: str, check_func):
        """注册通用检查项"""
        self._checks[name] = check_func

    def register_bagua_check(self, name: str, check_func):
        """注册八卦级检查项"""
        self._bagua_checks[name] = check_func

    def register_infra_check(self, name: str, check_func):
        """注册基础设施检查项"""
        self._infra_checks[name] = check_func

    # ---- 核心检查 ----

    async def check_all(self) -> Dict:
        """执行所有检查（保持向后兼容的旧格式）"""
        results = {}
        all_healthy = True

        for name, check_func in self._checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": time.time(),
                }
                if not result:
                    all_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                }
                all_healthy = False

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time(),
        }

    async def check_bagua(self) -> Dict:
        """八卦级健康检查

        Returns:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "gua_states": {
                    "qian": {"health": "full", "circuit": {...}, "deps": {...}},
                    ...
                },
                "summary": {"full": N, "degraded": N, "minimal": N, "off": N},
                "timestamp": float
            }
        """
        gua_states = {}
        summary = {"full": 0, "degraded": 0, "minimal": 0, "off": 0}

        for name, check_func in self._bagua_checks.items():
            try:
                state = await check_func()
                gua_states[name] = state
                health = state.get("health", "off")
                if health in summary:
                    summary[health] += 1
            except Exception as e:
                gua_states[name] = {
                    "health": "off",
                    "error": str(e),
                    "timestamp": time.time(),
                }
                summary["off"] += 1

        # 综合状态判断
        if summary["off"] > 0:
            overall = "unhealthy"
        elif summary["degraded"] > 0 or summary["minimal"] > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "gua_states": gua_states,
            "summary": summary,
            "timestamp": time.time(),
        }

    async def check_infra(self) -> Dict:
        """基础设施组件健康检查

        Returns:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "components": {
                    "connection_pool": {...},
                    "llm_api": {...},
                },
                "timestamp": float
            }
        """
        components = {}
        all_healthy = True

        for name, check_func in self._infra_checks.items():
            try:
                result = await check_func()
                components[name] = result
                if not result.get("healthy", False):
                    all_healthy = False
            except Exception as e:
                components[name] = {
                    "healthy": False,
                    "error": str(e),
                    "timestamp": time.time(),
                }
                all_healthy = False

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "components": components,
            "timestamp": time.time(),
        }

    async def check_extended(self) -> Dict:
        """扩展健康检查（v2.1 完整格式）

        合并：核心检查 + 八卦检查 + 基础设施检查 + 告警评估

        Returns:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "core": {...},        # 原有核心组件
                "bagua": {...},       # 八卦级健康
                "infra": {...},       # 基础设施
                "alerts": [...],      # 告警规则评估
                "timestamp": float
            }
        """
        core_result = await self.check_all()
        bagua_result = await self.check_bagua()
        infra_result = await self.check_infra()
        alerts_result = await self.evaluate_alerts()

        # 综合状态
        statuses = [
            core_result.get("status"),
            bagua_result.get("status"),
            infra_result.get("status"),
        ]
        if "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "core": core_result,
            "bagua": bagua_result,
            "infra": infra_result,
            "alerts": alerts_result,
            "timestamp": time.time(),
        }

    # ---- 告警评估 ----

    async def evaluate_alerts(self) -> List[Dict]:
        """评估所有告警规则并返回触发结果

        Returns:
            触发的告警列表
        """
        triggered = []

        for rule in self._alert_rules:
            if not rule.enabled:
                continue

            try:
                triggered_flag, context = await self._evaluate_rule(rule)
                if triggered_flag:
                    triggered.append({
                        "rule": rule.name,
                        "severity": rule.severity,
                        "description": rule.description,
                        "threshold": rule.threshold,
                        "context": context,
                        "timestamp": time.time(),
                    })
            except Exception as e:
                logger.warning("告警规则 [%s] 评估失败: %s", rule.name, e)

        return triggered

    async def _evaluate_rule(self, rule: AlertRule) -> tuple:
        """评估单条告警规则"""
        if rule.condition_fn_name == "check_llm_failure_rate":
            return await _check_llm_failure_rate_alert(rule.threshold)
        elif rule.condition_fn_name == "check_gua_consecutive_failures":
            return await _check_gua_failures_alert(rule.threshold)
        elif rule.condition_fn_name == "check_circuit_open_duration":
            return await _check_circuit_open_alert(rule.threshold)
        elif rule.condition_fn_name == "check_connection_pool_usage":
            return await _check_conn_pool_usage_alert(rule.threshold)
        return False, {}

    def add_alert_rule(self, rule: AlertRule) -> None:
        """动态添加告警规则"""
        self._alert_rules.append(rule)
        logger.info("添加告警规则: %s", rule.name)

    def get_alert_rules(self) -> List[Dict]:
        """获取所有告警规则"""
        return [
            {
                "name": r.name,
                "description": r.description,
                "severity": r.severity,
                "threshold": r.threshold,
                "enabled": r.enabled,
            }
            for r in self._alert_rules
        ]


# ============================================================================
# 告警规则实现函数
# ============================================================================


# 全局 LLM 失败计数器（供 llm 调用模块更新）
_llm_stats: Dict[str, Any] = {
    "total_calls": 0,
    "failures": 0,
    "last_check_time": 0.0,
}


def record_llm_call(success: bool) -> None:
    """记录 LLM 调用结果（供外部模块调用）"""
    _llm_stats["total_calls"] += 1
    if not success:
        _llm_stats["failures"] += 1


# 八卦连续失败计数器
_gua_failure_counters: Dict[str, int] = {}


def record_gua_failure(gua_name: str) -> None:
    """记录八卦执行失败"""
    _gua_failure_counters[gua_name] = _gua_failure_counters.get(gua_name, 0) + 1


def record_gua_success(gua_name: str) -> None:
    """记录八卦执行成功（重置计数器）"""
    _gua_failure_counters[gua_name] = 0


# 断路器 OPEN 时间记录
_circuit_open_times: Dict[str, float] = {}


def record_circuit_open(circuit_name: str) -> None:
    """记录断路器打开时间"""
    if circuit_name not in _circuit_open_times:
        _circuit_open_times[circuit_name] = time.time()


def record_circuit_close(circuit_name: str) -> None:
    """清除断路器打开时间"""
    _circuit_open_times.pop(circuit_name, None)


async def _check_llm_failure_rate_alert(threshold: float) -> tuple:
    """检查 LLM 失败率"""
    total = _llm_stats["total_calls"]
    if total == 0:
        return False, {"message": "暂无 LLM 调用记录"}
    rate = _llm_stats["failures"] / total
    triggered = rate > threshold
    return triggered, {
        "total_calls": total,
        "failures": _llm_stats["failures"],
        "failure_rate": round(rate, 4),
        "threshold": threshold,
    }
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def _check_gua_failures_alert(threshold: int) -> tuple:
    """检查八卦连续失败"""
    triggered_gua = []
    for gua_name, count in _gua_failure_counters.items():
        if count >= threshold:
            triggered_gua.append({"gua": gua_name, "consecutive_failures": count})
    return len(triggered_gua) > 0, {
        "triggered_gua": triggered_gua,
        "threshold": threshold,
    }
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def _check_circuit_open_alert(threshold: float) -> tuple:
    """检查断路器 OPEN 持续时长"""
    now = time.time()
    long_open = []
    for name, open_time in list(_circuit_open_times.items()):
        duration = now - open_time
        if duration > threshold:
            long_open.append({"circuit": name, "open_duration_sec": round(duration, 1)})
    return len(long_open) > 0, {
        "long_open_circuits": long_open,
        "threshold_sec": threshold,
    }
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def _check_conn_pool_usage_alert(threshold: float) -> tuple:
    """检查连接池使用率"""
    try:
        from src.infra.connection_pool import get_connection_pool
        pool = get_connection_pool()
        usage = pool._active_connections / pool.max_connections if pool.max_connections > 0 else 0
        triggered = usage > threshold
        return triggered, {
            "active_connections": pool._active_connections,
            "max_connections": pool.max_connections,
            "usage_rate": round(usage, 4),
            "threshold": threshold,
        }
    except Exception as e:
        return False, {"error": str(e)}
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


# ============================================================================
# 具体检查函数（扩展版）
# ============================================================================


async def check_database() -> bool:
    """检查数据库"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        store._db_conn.execute("SELECT 1")
        return True
    except Exception:
        return False
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def check_vector_store() -> bool:
    """检查向量存储"""
    try:
        from src.db.vector_store import get_vector_store
        vs = get_vector_store()
        return vs is not None
    except Exception:
        return False
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def check_llm() -> bool:
    """检查 LLM 服务"""
    try:
        from src.infra.llm import call_llm
        return True
    except Exception:
        return False
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def check_bagua_overall() -> Dict:
    """八卦整体健康检查

    尝试导入 bagua 模块，检查各卦状态。
    返回各卦的健康等级、断路器状态、依赖状态。
    """
    result = {
        "health": "full",
        "guas": {},
        "timestamp": time.time(),
    }

    try:
        from src.bagua.base_gua import GuaBase, HealthLevel, CircuitState

        # 尝试获取所有已实例化的卦
        # 通过全局注册表（如果有）或模块导入方式
        gua_instances = _get_gua_instances()

        if not gua_instances:
            result["health"] = "off"
            result["message"] = "暂无八卦实例"
            return result

        for name, gua in gua_instances.items():
            try:
                summary = gua.health_summary()
                result["guas"][name] = {
                    "health": summary.get("health", "off"),
                    "emoji": summary.get("emoji", "◉"),
                    "uptime_sec": summary.get("uptime_sec", 0),
                    "dependencies": summary.get("dependencies", {}),
                    "circuit_states": {
                        dep_name: dep_info.get("circuit", "unknown")
                        for dep_name, dep_info in summary.get("dependencies", {}).items()
                    },
                }
            except Exception as e:
                result["guas"][name] = {
                    "health": "off",
                    "error": str(e),
                }

        # 综合等级
        levels = [g.get("health", "off") for g in result["guas"].values()]
        if "off" in levels:
            result["health"] = "degraded"
        elif "degraded" in levels or "minimal" in levels:
            result["health"] = "degraded"

    except ImportError:
        result["health"] = "off"
        result["message"] = "bagua 模块未安装"
    except Exception as e:
        result["health"] = "off"
        result["error"] = str(e)

    return result
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def check_connection_pool() -> Dict:
    """检查数据库连接池使用率"""
    try:
        from src.infra.connection_pool import get_connection_pool
        pool = get_connection_pool()
        active = pool._active_connections
        max_conn = pool.max_connections
        usage = active / max_conn if max_conn > 0 else 0

        return {
            "healthy": usage < 0.80,
            "active_connections": active,
            "max_connections": max_conn,
            "usage_rate": round(usage, 4),
            "status": "healthy" if usage < 0.80 else ("warning" if usage < 0.95 else "critical"),
            "timestamp": time.time(),
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": time.time(),
        }
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def check_llm_api_reachable() -> Dict:
    """检查 LLM API 可达性

    使用配置的 LLM 端点进行轻量健康探测。
    """
    try:
        from src.config import MIMO_API_KEY, MIMO_BASE_URL
        if not MIMO_API_KEY or not MIMO_BASE_URL:
            return {
                "healthy": True,
                "status": "not_configured",
                "message": "LLM API 未配置，跳过检查",
                "timestamp": time.time(),
            }

        import aiohttp
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {MIMO_API_KEY}",
                "Content-Type": "application/json",
            }
            async with session.get(
                f"{MIMO_BASE_URL}/models",
                headers=headers,
            ) as resp:
                is_ok = resp.status < 500
                return {
                    "healthy": is_ok,
                    "status_code": resp.status,
                    "endpoint": MIMO_BASE_URL,
                    "timestamp": time.time(),
                }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "endpoint": MIMO_BASE_URL if "MIMO_BASE_URL" in dir() else "unknown",
            "timestamp": time.time(),
        }


async def check_intent_bus() -> Dict:
    """检查 IntentBus 状态"""
    try:
        from src.bagua.intent_bus import get_intent_bus
        intent_bus = get_intent_bus()
        return {
            "healthy": True,
            "engine": "v2",
            "registered_guas": len(intent_bus._guas) if hasattr(intent_bus, '_guas') else 0,
            "circuit_breakers": len(intent_bus._circuit_breakers) if hasattr(intent_bus, '_circuit_breakers') else 0,
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
        }
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


# ============================================================================
# 八卦实例获取辅助
# ============================================================================

# 全局八卦注册表
_gua_registry: Dict[str, Any] = {}


def register_gua_instance(name: str, gua_instance: Any) -> None:
    """注册八卦实例到全局注册表"""
    _gua_registry[name] = gua_instance
    logger.debug("注册八卦实例: %s", name)


def unregister_gua_instance(name: str) -> None:
    """从全局注册表移除八卦实例"""
    _gua_registry.pop(name, None)


def _get_gua_instances() -> Dict[str, Any]:
    """获取所有已注册的八卦实例"""
    if _gua_registry:
        return dict(_gua_registry)

    # 尝试从 bagua 模块中自动发现八卦实例
    result = {}
    try:
        # 尝试导入各卦模块并获取其单例
        gua_modules = [
            ("qian", "src.bagua.qian_gua"),
            ("kun", "src.bagua.kun_gua"),
            ("zhen", "src.bagua.zhen_gua"),
            ("xun", "src.bagua.xun_gua"),
            ("kan", "src.bagua.kan_gua"),
            ("li", "src.bagua.li_gua"),
            ("gen", "src.bagua.gen_gua"),
            ("dui", "src.bagua.dui_gua"),
        ]
        for name, mod_path in gua_modules:
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                # 查找 GuaBase 子类实例
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if hasattr(attr, "health_summary"):
                        result[name] = attr
                        break
            except ImportError:
                pass
    except Exception:
        pass

    return result


# ============================================================================
# 全局实例
# ============================================================================

_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器（v2.1 扩展版）"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        # -- 核心检查 --
        _health_checker.register_check("database", check_database)
        _health_checker.register_check("vector_store", check_vector_store)
        _health_checker.register_check("llm", check_llm)
        _health_checker.register_check("intent_bus", check_intent_bus)
        # -- 八卦级检查 --
        _health_checker.register_bagua_check("bagua_overall", check_bagua_overall)
        # -- 基础设施检查 --
        _health_checker.register_infra_check("connection_pool", check_connection_pool)
        _health_checker.register_infra_check("llm_api", check_llm_api_reachable)
    return _health_checker
