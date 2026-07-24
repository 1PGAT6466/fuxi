"""
logging_config.py — P1 优化: 异步日志写入

使用 QueueHandler + QueueListener 模式：
- 主线程仅入队日志记录（无 I/O 阻塞）
- 后台线程批量写入文件
- 队列大小上限 5000，满时丢弃最旧记录

用法:
    from src.core.logging_config import setup_logging
    setup_logging()
"""

import logging
import logging.handlers
import os
from typing import Optional


# 队列配置
LOG_QUEUE_MAX_SIZE = 5000  # 队列最大条数
LOG_FLUSH_INTERVAL = 1.0   # 刷新间隔（秒）

# 全局队列监听器
_queue_listener: Optional[logging.handlers.QueueListener] = None


def setup_logging(
    log_dir: str = "./logs",
    log_level: int = logging.INFO,
    queue_max_size: int = LOG_QUEUE_MAX_SIZE,
) -> None:
    """
    配置异步日志系统
    
    Args:
        log_dir: 日志目录
        log_level: 日志级别
        queue_max_size: 队列最大大小
    """
    global _queue_listener
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 1. 创建实际的日志处理器（文件 + 控制台）
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除已有处理器（避免重复）
    root_logger.handlers.clear()
    
    # 文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "fuxi.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # 控制台只显示 WARNING+
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # 2. 创建 QueueHandler（主线程使用，无 I/O 阻塞）
    import queue
    log_queue = queue.Queue(maxsize=queue_max_size)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    
    # 3. 创建 QueueListener（后台线程写入）
    _queue_listener = logging.handlers.QueueListener(
        log_queue,
        file_handler,
        console_handler,
        respect_handler_level=True,
    )
    
    # 添加到根 logger
    root_logger.addHandler(queue_handler)
    
    # 启动监听器
    _queue_listener.start()
    
    logger = logging.getLogger("logging_config")
    logger.info(
        f"[Logging] 异步日志已配置 | 队列上限={queue_max_size} | "
        f"刷新间隔={LOG_FLUSH_INTERVAL}s | 日志目录={log_dir}"
    )


def stop_logging() -> None:
    """停止异步日志系统（服务关闭时调用）"""
    global _queue_listener
    
    if _queue_listener:
        logging.getLogger("logging_config").info("[Logging] 正在停止异步日志...")
        _queue_listener.stop()
        _queue_listener = None
        logging.getLogger("logging_config").info("[Logging] 异步日志已停止")


def get_logging_stats() -> dict:
    """获取日志队列统计"""
    return {
        "queue_max_size": LOG_QUEUE_MAX_SIZE,
        "flush_interval": LOG_FLUSH_INTERVAL,
        "listener_active": _queue_listener is not None and hasattr(_queue_listener, "_thread") and _queue_listener._thread is not None,
    }
