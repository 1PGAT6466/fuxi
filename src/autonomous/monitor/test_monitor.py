"""
健康监控模块测试脚本
"""

import asyncio
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.autonomous.monitor import AlertEngine, HealthChecker, MetricsCollector, MonitorConfig


async def test_health_checker():
    """测试健康检查器"""
    print("=" * 50)
    print("测试健康检查器")
    print("=" * 50)

    checker = HealthChecker()
    health = await checker.check_all()

    print(f"整体状态: {health.status.value}")
    print(f"检查耗时: {health.duration:.3f}s")
    print(f"服务数量: {len(health.services)}")

    for service in health.services:
        print(f"  - {service.name}: {service.status.value} ({service.message})")

    print()


async def test_metrics_collector():
    """测试指标采集器"""
    print("=" * 50)
    print("测试指标采集器")
    print("=" * 50)

    collector = MetricsCollector()
    metrics = await collector.collect_all()

    print(f"采集指标数量: {len(metrics)}")
    for name, value in list(metrics.items())[:10]:
        print(f"  - {name}: {value:.2f}")

    print()


async def test_alert_engine():
    """测试告警引擎"""
    print("=" * 50)
    print("测试告警引擎")
    print("=" * 50)

    engine = AlertEngine()
    rules = engine.get_rules()

    print(f"告警规则数量: {len(rules)}")
    for rule in rules:
        print(f"  - {rule.id}: {rule.name} ({rule.level.name})")

    # 模拟指标触发告警
    test_metrics = {
        "system.cpu.percent": 90.0,
        "system.memory.percent": 88.0,
        "system.disk.percent": 95.0,
        "business.latency_avg": 6.0,
        "business.error_rate": 8.0,
    }

    alerts = await engine.evaluate(test_metrics)
    print(f"\n触发告警数量: {len(alerts)}")
    for alert in alerts:
        print(f"  - [{alert.level.name}] {alert.message}")

    print()


async def main():
    """主测试函数"""
    print("伏羲健康监控模块测试")
    print("=" * 50)

    await test_health_checker()
    await test_metrics_collector()
    await test_alert_engine()

    print("=" * 50)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
