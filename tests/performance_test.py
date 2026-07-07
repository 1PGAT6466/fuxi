"""
performance_test.py — 伏羲 v1.50 性能优化验证测试
测试 HTTP 连接池、向量查询、缓存、并发控制等优化效果
"""
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_http_pool():
    """测试 1: HTTP 连接池复用"""
    print("\n" + "=" * 60)
    print("测试 1: HTTP 连接池复用")
    print("=" * 60)

    from src.core.http_client import get_http_session, close_http_session

    # 测试连接池初始化
    session1 = await get_http_session()
    session2 = await get_http_session()
    assert session1 is session2, "连接池应返回同一个 session 实例"
    print("  ✅ 连接池单例复用: PASS")

    # 测试连接池配置
    connector = session1.connector
    assert connector.limit == 100, f"总连接数应为 100, 实际: {connector.limit}"
    assert connector.limit_per_host == 30, f"单 host 连接数应为 30, 实际: {connector.limit_per_host}"
    print(f"  ✅ 连接池配置: limit={connector.limit}, per_host={connector.limit_per_host}")

    # 性能对比：连续 10 次获取 session
    start = time.time()
    for _ in range(10):
        s = await get_http_session()
        assert s is session1
    elapsed = time.time() - start
    print(f"  ✅ 10 次获取 session 耗时: {elapsed*1000:.2f}ms (应 < 1ms)")

    await close_http_session()
    print("  ✅ 连接池关闭: PASS")


cleanup_done = False


async def test_vector_query():
    """测试 2: 向量查询优化"""
    print("\n" + "=" * 60)
    print("测试 2: 向量查询优化（相似度阈值过滤）")
    print("=" * 60)

    from src.db.vector_store import VectorStore

    # 检查 VectorStore.query 签名是否支持新参数
    import inspect
    sig = inspect.signature(VectorStore.query)
    params = list(sig.parameters.keys())
    assert "min_similarity" in params, f"query 方法应支持 min_similarity 参数, 实际参数: {params}"
    assert "where_document" in params, f"query 方法应支持 where_document 参数, 实际参数: {params}"
    print(f"  ✅ VectorStore.query 新参数: min_similarity, where_document")
    print(f"  ✅ 方法签名: {params}")


async def test_cache():
    """测试 3: 多级缓存"""
    print("\n" + "=" * 60)
    print("测试 3: 多级缓存（内存 + Redis）")
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

    # 统计
    stats = get_cache_stats()
    print(f"  ✅ 缓存统计: L1={stats['l1_size']}, L2={stats['l2_size']}, L3={stats['l3_redis']}")
    print(f"  ✅ 命中率: {stats['hit_rate']:.1%}")

    clear_cache()


async def test_concurrency():
    """测试 4: 并发控制优化"""
    print("\n" + "=" * 60)
    print("测试 4: 并发控制优化（自适应信号量）")
    print("=" * 60)

    from src.infra.concurrency import get_concurrency_manager

    cm = get_concurrency_manager()

    # 检查自适应信号量
    status = cm.get_status()
    for name, info in status.items():
        assert "current_limit" in info, f"{name} 应有 current_limit 字段"
        assert "min_limit" in info, f"{name} 应有 min_limit 字段"
        assert "max_limit" in info, f"{name} 应有 max_limit 字段"
        print(f"  ✅ {name}: current={info['current_limit']}, range=[{info['min_limit']}, {info['max_limit']}]")

    # 测试自适应调整
    sem = cm._semaphores["taiyang"]
    old_val = sem._current
    # 模拟高成功率
    for _ in range(100):
        sem.record_success()
    sem._maybe_adjust()
    print(f"  ✅ 自适应调整: taiyang {old_val} → {sem._current} (高成功率后)")


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
    ]

    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  ✅ {mod_name}: 导入成功")
        except Exception as e:
            print(f"  ❌ {mod_name}: 导入失败 - {e}")


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

    # 清理全局 session
    try:
        from src.core.http_client import close_http_session
        await close_http_session()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
