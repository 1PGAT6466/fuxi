"""
伏羲 v1.44 — Redis Stream 任务队列
===================================
基于 Redis Stream 实现异步任务队列，支持：
- 任务发布（XADD）
- 任务消费（XREADGROUP）
- 任务状态追踪（pending/processing/completed/failed）
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

# 任务状态枚举
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 任务数据类
@dataclass
class Task:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = None
    updated_at: str = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

class RedisStreamTaskQueue:
    """Redis Stream 任务队列实现"""
    
    def __init__(self, redis_client, stream_name: str = "fuxi:tasks", group_name: str = "fuxi:workers"):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = f"worker:{id(self)}"
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}
        self._running = False
        
    async def initialize(self):
        """初始化消费者组"""
        try:
            # 创建消费者组（如果不存在）
            await self.redis.xgroup_create(
                self.stream_name, 
                self.group_name, 
                id="0", 
                mkstream=True
            )
            logger.info(f"消费者组 {self.group_name} 创建成功")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"消费者组 {self.group_name} 已存在")
            else:
                logger.error(f"创建消费者组失败: {e}")
                raise
    
    def register_handler(self, task_type: str, handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]):
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"注册任务处理器: {task_type}")
    
    async def publish_task(self, task_type: str, payload: Dict[str, Any]) -> str:
        """发布任务到队列"""
        task_id = f"task:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        task_data = {
            "task_id": task_id,
            "task_type": task_type,
            "payload": json.dumps(payload),
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 使用 XADD 发布任务
        message_id = await self.redis.xadd(self.stream_name, task_data)
        logger.info(f"任务发布成功: {task_id}, 消息ID: {message_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        # 从 Redis 获取任务状态
        task_key = f"task:status:{task_id}"
        task_data = await self.redis.hgetall(task_key)
        
        if not task_data:
            return None
        
        return Task(
            task_id=task_data["task_id"],
            task_type=task_data["task_type"],
            payload=json.loads(task_data["payload"]),
            status=TaskStatus(task_data["status"]),
            created_at=task_data["created_at"],
            updated_at=task_data["updated_at"],
            result=json.loads(task_data["result"]) if task_data.get("result") else None,
            error=task_data.get("error")
        )
    
    async def _update_task_status(self, task_id: str, status: TaskStatus, 
                                 result: Optional[Dict[str, Any]] = None, 
                                 error: Optional[str] = None):
        """更新任务状态"""
        task_key = f"task:status:{task_id}"
        update_data = {
            "status": status.value,
            "updated_at": datetime.now().isoformat()
        }
        
        if result is not None:
            update_data["result"] = json.dumps(result)
        if error is not None:
            update_data["error"] = error
        
        await self.redis.hset(task_key, mapping=update_data)
    
    async def _process_message(self, message: Dict[str, Any]):
        """处理单个消息"""
        task_id = message["task_id"]
        task_type = message["task_type"]
        payload = json.loads(message["payload"])
        
        # 更新状态为处理中
        await self._update_task_status(task_id, TaskStatus.PROCESSING)
        
        try:
            # 查找并执行处理器
            if task_type not in self._handlers:
                raise ValueError(f"未注册的任务类型: {task_type}")
            
            handler = self._handlers[task_type]
            result = await handler(payload)
            
            # 更新状态为完成
            await self._update_task_status(task_id, TaskStatus.COMPLETED, result=result)
            logger.info(f"任务完成: {task_id}")
            
        except Exception as e:
            # 更新状态为失败
            await self._update_task_status(task_id, TaskStatus.FAILED, error=str(e))
            logger.error(f"任务失败: {task_id}, 错误: {e}")
    
    async def start_consuming(self):
        """开始消费任务"""
        self._running = True
        logger.info(f"开始消费任务，消费者: {self.consumer_name}")
        
        while self._running:
            try:
                # 使用 XREADGROUP 读取消息
                messages = await self.redis.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=10,
                    block=5000  # 5秒超时
                )
                
                if messages:
                    for stream, message_list in messages:
                        for message_id, message_data in message_list:
                            try:
                                await self._process_message(message_data)
                                # 确认消息处理完成
                                await self.redis.xack(
                                    self.stream_name, 
                                    self.group_name, 
                                    message_id
                                )
                            except Exception as e:
                                logger.error(f"处理消息失败: {message_id}, 错误: {e}")
                
            except Exception as e:
                logger.error(f"消费任务异常: {e}")
                await asyncio.sleep(1)  # 避免快速循环
    
    async def stop_consuming(self):
        """停止消费任务"""
        self._running = False
        logger.info("停止消费任务")

# 全局任务队列实例
_task_queue: Optional[RedisStreamTaskQueue] = None

async def get_task_queue() -> RedisStreamTaskQueue:
    """获取全局任务队列实例"""
    global _task_queue
    if _task_queue is None:
        # 这里需要从配置获取 Redis 连接
        # 暂时使用占位实现，实际需要集成 Redis 连接
        raise RuntimeError("任务队列未初始化，请先调用 initialize_task_queue()")
    return _task_queue

async def initialize_task_queue(redis_client) -> RedisStreamTaskQueue:
    """初始化全局任务队列"""
    global _task_queue
    _task_queue = RedisStreamTaskQueue(redis_client)
    await _task_queue.initialize()
    return _task_queue

# 任务类型常量
TASK_FILE_PROCESS = "file_process"
TASK_EVAL_RUN = "eval_run"
TASK_KB_UPDATE = "kb_update"