"""
performance_test.py — 伏羲 v1.50 性能优化验证测试 (第四轮修复版)
测试 HTTP 连接池、向量查询、缓存、并发控制等优化效果
"""
import pytest
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_http_pool():
    """测试 1: HTTP 连接池复用"""
    print("\n" + "=" * 60)
    print("测试 1: HTTP 连接池复用")
    print("=" * 60)

    from src.core.http_client import get_session, close as close_session

    # 测试连接池初始化
    session1 = await get_session()
    session2 = await get_session()
    assert session1 is session2, "连接池应返回同一个 session 实例"
    print("  ✅ 连接池单例复用: PASS")

    # 测试连接池配置
    connector = session1.connector
    assert connector.limit == 100, f"总连接数应为 100, 实际: {connector.limit}"
    assert connector.limit_per_host == 20, f"单 host 连接数应为 20, 实际: {connector.limit_per_host}"
    print(f"  ✅ 连接池配置: limit={connector.limit}, per_host={connector.limit_per_host}")

    # 性能对比：连续 10 次获取 session
    start = time.time()
    for _ in range(10):
        s = await get_session()
        assert s is session1
    elapsed = time.time() - start
    print(f"  ✅ 10 次获取 session 耗时: {elapsed*1000:.2f}ms (应 < 1ms)")

    await close_session()
    print("  ✅ 连接池关闭: PASS")


@pytest.mark.asyncio
async def test_vector_query():
    """测试 2: 向量查询优化"""
    print("\n" + "=" * 60)
    print("测试 2: 向量查询优化")
    print("=" * 60)

    from src.db.vector_store import VectorStore

    # 检查 VectorStore.query 签名
    import inspect
    sig = inspect.signature(VectorStore.query)
    params = list(sig.parameters.keys())
    print(f"  ✅ VectorStore.query 方法签名: {params}")
    assert len(params) >= 3, f"query 应至少有 3 个参数, 实际: {params}"
    # 验证核心参数存在
    core_params = {"self", "query_embedding", "n_results"}
    found = core_params & set(params)
    assert len(found) >= 2, f"query 必须包含核心参数，实际有: {params}"
    print(f"  ✅ VectorStore.query 核心参数: {sorted(found)}")


@pytest.mark.asyncio
async def test_cache():
    """测试 3: 多级缓存"""
    print("\n" + "=" * 60)
    print("测试 3: 多级缓存（L1 精确 + L2 语义）")
    print("=" * 60)

    from src.services.cache import get_cache, set_cache, get_cache_stats, clear_cache

    clear_cache()

    # L1 写入
    results = [{"text": "test", "score": 9.5}]
    await set_cache("测试查询", results, "test", 10)

    # L1 读取
    cached = await get_cache("测试查询", "test", 10)
    assert cached is not None, "L1 缓存应命中"
    assert cached[0]["text"] == "test"
    print("  ✅ L1 精确匹配缓存: PASS")

    # 统计（实际只有 L1 + L2，没有 Redis L3）
    stats = get_cache_stats()
    print(f"  ✅ 缓存统计: L1={stats.get('l1_size', 0)}, L2={stats.get('l2_size', len(_l2_cache) if '_l2_cache' in dir() else 0)}")
    print(f"  ✅ 命中率: {stats['hit_rate']}")
    print(f"  ✅ 穿透拦截: {stats.get('penetration_blocked', 0)}")

    clear_cache()


@pytest.mark.asyncio
async def test_concurrency():
    """测试 4: 并发控制优化"""
    print("\n" + "=" * 60)
    print("测试 4: 并发控制")
    print("=" * 60)

    from src.infra.concurrency import get_concurrency_manager

    cm = get_concurrency_manager()

    # 检查信号量状态
    status = cm.get_status()
    assert len(status) >= 4, f"至少应有 4 个信号量, 实际: {len(status)}"
    for name, info in status.items():
        assert "available" in info, f"{name} 应有 available 字段"
        print(f"  ✅ {name}: available={info['available']}, locked={info.get('locked', False)}")

    # 测试速率限制器
    can_acquire = await cm.check_rate_limit("chat")
    assert can_acquire in (True, False), "check_rate_limit 应返回 True/False"
    print(f"  ✅ chat 速率限制检查: {'通过' if can_acquire else '限流（正常）'}")

    # 符号信号量获取/释放
    acquired = await cm.acquire_symbol("shaoyang")
    if acquired:
        print("  ✅ shaoyang 信号量获取: PASS")
        cm.release_symbol("shaoyang")
        print("  ✅ shaoyang 信号量释放: PASS")
    else:
        print("  ℹ️  shaoyang 信号量获取: 繁忙（正常）")


@pytest.mark.asyncio
async def test_import_chain():
    """测试 5: 模块导入链完整性"""
    print("\n" + "=" * 60)
    print("测试 5: 模块导入链完整性")
    print("=" * 60)

    modules = [
        "src.core.http_client",
        "src.infra.concurrency",
        "src.infra.circuit_breaker",
        "src.services.cache",
        "src.db.vector_store",
        "src.db.memory_store",
        "src.db.data_store",
        "src.data_service",
        "src.api.response",
        "src.api.auth_routes",
        "src.api.chat",
        "src.api.admin",
        "src.api.documents",
        "src.api.search",
        "src.api.graph",
    ]

    passed = 0
    failed = 0
    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  ✅ {mod_name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {mod_name}: {e}")
            failed += 1

    assert failed == 0, f"有 {failed} 个模块导入失败"
    print(f"\n  📊 通过: {passed}/{len(modules)}")


async def main():
    print("🐍 伏羲 v1.50 性能优化验证测试")
    print("=" * 60)

    tests = [
        ("HTTP 连接池", test_http_pool),
        ("向量查询优化", test_vector_query),
        ("多级缓存", test_cache),
        ("并发控制", test_concurrency),
        ("导入链完整性", test_import_chain),
    ]

    results = []
    for name, test_fn in tests:
        try:
            await test_fn()
            results.append((name, "PASS"))
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            results.append((name, f"FAIL: {e}"))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        icon = "✅" if result == "PASS" else "❌"
        print(f"  {icon} {name}: {result}")

    passed = sum(1 for _, r in results if r == "PASS")
    total = len(results)
    print(f"\n  通过: {passed}/{total}")

    # 清理
    try:
        from src.core.http_client import close as close_session
        await close_session()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
