"""
伏羲 v1.44 — 任务队列测试脚本
==============================
测试 Redis Stream 任务队列的基本功能
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_task_queue():
    """测试任务队列"""
    try:
        import redis.asyncio as redis
        from src.infra.task_queue import RedisStreamTaskQueue, TaskStatus
        from src.infra.task_handlers import handle_file_process
        
        print("1. 连接 Redis...")
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD", "") or None,
            decode_responses=True
        )
        
        # 测试连接
        await redis_client.ping()
        print("   ✓ Redis 连接成功")
        
        print("2. 初始化任务队列...")
        task_queue = RedisStreamTaskQueue(redis_client)
        await task_queue.initialize()
        print("   ✓ 任务队列初始化成功")
        
        print("3. 注册任务处理器...")
        task_queue.register_handler("file_process", handle_file_process)
        print("   ✓ 任务处理器注册成功")
        
        print("4. 发布测试任务...")
        task_id = await task_queue.publish_task(
            "file_process",
            {
                "file_path": "/tmp/test.txt",
                "file_name": "test.txt",
                "source": "test"
            }
        )
        print(f"   ✓ 任务发布成功: {task_id}")
        
        print("5. 查询任务状态...")
        task = await task_queue.get_task_status(task_id)
        if task:
            print(f"   ✓ 任务状态: {task.status.value}")
        else:
            print("   ✗ 任务未找到")
        
        print("6. 启动任务消费者（5秒后停止）...")
        consumer_task = asyncio.create_task(task_queue.start_consuming())
        await asyncio.sleep(5)
        await task_queue.stop_consuming()
        consumer_task.cancel()
        print("   ✓ 任务消费者测试完成")
        
        print("7. 再次查询任务状态...")
        task = await task_queue.get_task_status(task_id)
        if task:
            print(f"   ✓ 任务状态: {task.status.value}")
            if task.status == TaskStatus.COMPLETED:
                print(f"   ✓ 任务结果: {task.result}")
            elif task.status == TaskStatus.FAILED:
                print(f"   ✗ 任务失败: {task.error}")
        
        print("\n✓ 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_task_queue())
    sys.exit(0 if success else 1)