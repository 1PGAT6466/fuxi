"""
伏羲 v1.44 — 任务队列监控脚本
==============================
监控 Redis Stream 任务队列的状态
"""
import asyncio
import sys
import os
import time
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def monitor_queue():
    """监控任务队列"""
    try:
        import redis.asyncio as redis
        from src.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_STREAM_NAME, REDIS_GROUP_NAME
        
        print("=== 伏羲 v1.44 任务队列监控 ===")
        print(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        print(f"Stream: {REDIS_STREAM_NAME}")
        print(f"Group: {REDIS_GROUP_NAME}")
        print()
        
        # 连接 Redis
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True
        )
        
        # 测试连接
        await redis_client.ping()
        print("✓ Redis 连接成功")
        print()
        
        # 监控循环
        print("开始监控... (按 Ctrl+C 停止)")
        print()
        
        while True:
            try:
                # 获取 Stream 信息
                stream_info = await redis_client.xinfo_stream(REDIS_STREAM_NAME)
                
                # 获取消费者组信息
                groups_info = await redis_client.xinfo_groups(REDIS_STREAM_NAME)
                
                # 获取待处理消息
                pending_info = await redis_client.xpending(REDIS_STREAM_NAME, REDIS_GROUP_NAME)
                
                # 清屏
                os.system('cls' if os.name == 'nt' else 'clear')
                
                print("=== 伏羲 v1.44 任务队列监控 ===")
                print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
                # Stream 信息
                print("Stream 信息:")
                print(f"  长度: {stream_info.get('length', 0)}")
                print(f"  第一条消息: {stream_info.get('first-entry', 'N/A')}")
                print(f"  最后一条消息: {stream_info.get('last-entry', 'N/A')}")
                print()
                
                # 消费者组信息
                print("消费者组:")
                for group in groups_info:
                    print(f"  {group['name']}:")
                    print(f"    消费者数量: {group['consumers']}")
                    print(f"    待处理消息: {group['pending']}")
                    print(f"    最后传递ID: {group['last-delivered-id']}")
                print()
                
                # 待处理消息详情
                if pending_info:
                    print("待处理消息:")
                    print(f"  总数: {pending_info.get('pending', 0)}")
                    print(f"  最小ID: {pending_info.get('min', 'N/A')}")
                    print(f"  最大ID: {pending_info.get('max', 'N/A')}")
                    
                    # 获取具体的待处理消息
                    if pending_info.get('pending', 0) > 0:
                        pending_messages = await redis_client.xpending_range(
                            REDIS_STREAM_NAME,
                            REDIS_GROUP_NAME,
                            min='-',
                            max='+',
                            count=10
                        )
                        
                        print("  最近待处理消息:")
                        for msg in pending_messages:
                            print(f"    ID: {msg['message_id']}")
                            print(f"    消费者: {msg['consumer']}")
                            print(f"    空闲时间: {msg['time_since_delivered']}ms")
                            print(f"    传递次数: {msg['times_delivered']}")
                            print()
                
                # 任务状态统计
                print("任务状态统计:")
                task_keys = await redis_client.keys("task:status:*")
                
                status_counts = {
                    "pending": 0,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0
                }
                
                for key in task_keys[:100]:  # 限制检查数量
                    task_data = await redis_client.hgetall(key)
                    status = task_data.get("status", "unknown")
                    if status in status_counts:
                        status_counts[status] += 1
                
                for status, count in status_counts.items():
                    print(f"  {status}: {count}")
                
                print()
                print("按 Ctrl+C 停止监控")
                
                # 等待 5 秒
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                print("\n监控已停止")
                break
            except Exception as e:
                print(f"监控错误: {e}")
                await asyncio.sleep(5)
        
        await redis_client.close()
        return True
        
    except Exception as e:
        print(f"\n监控失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(monitor_queue())
    sys.exit(0 if success else 1)