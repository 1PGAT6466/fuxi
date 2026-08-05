"""
async_queue.py 鈥?寮傛浠诲姟闃熷垪
鏀寔鏂囦欢娓呮礂鐨勫紓姝ラ槦鍒楀鐞嗭紝涓嶉樆濉炵敤鎴锋搷浣?"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """浠诲姟鐘舵€?""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueTask:
    """闃熷垪浠诲姟"""

    task_id: str
    task_type: str  # "clean", "chunk", "index", etc.
    data: Any
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    priority: int = 0  # 0 = 鏅€? 1 = 楂樹紭鍏堢骇

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class AsyncTaskQueue:
    """寮傛浠诲姟闃熷垪"""

    def __init__(self, max_workers: int = 3, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        # 浠诲姟闃熷垪锛堟寜浼樺厛绾ф帓搴忥級
        self._queue: deque = deque()
        self._high_priority_queue: deque = deque()

        # 浠诲姟鐘舵€佽窡韪?        self._tasks: Dict[str, QueueTask] = {}

        # 宸ヤ綔绾跨▼鎺у埗
        self._workers: List[asyncio.Task] = []
        self._is_running = False
        self._processing_count = 0

        # 缁熻淇℃伅
        self._stats = {"total_submitted": 0, "total_completed": 0, "total_failed": 0, "total_cancelled": 0}

    async def start(self):
        """鍚姩闃熷垪澶勭悊"""
        if self._is_running:
            return

        self._is_running = True
        logger.info(f"鍚姩寮傛闃熷垪: 鏈€澶у苟鍙?{self.max_workers}")

        # 鍚姩宸ヤ綔绾跨▼
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

    async def stop(self):
        """鍋滄闃熷垪澶勭悊"""
        self._is_running = False

        # 鍙栨秷鎵€鏈夊伐浣滅嚎绋?        for worker in self._workers:
            worker.cancel()

        # 绛夊緟鎵€鏈夊伐浣滅嚎绋嬬粨鏉?        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("寮傛闃熷垪宸插仠姝?)

    async def submit_task(
        self, task_id: str, task_type: str, data: Any, handler: Callable, priority: int = 0
    ) -> QueueTask:
        """鎻愪氦浠诲姟鍒伴槦鍒?""
        # 妫€鏌ラ槦鍒楁槸鍚﹀凡婊?        if len(self._queue) + len(self._high_priority_queue) >= self.max_queue_size:
            raise Exception(f"闃熷垪宸叉弧 ({self.max_queue_size})")

        # 鍒涘缓浠诲姟
        task = QueueTask(task_id=task_id, task_type=task_type, data=data, priority=priority)

        # 瀛樺偍浠诲姟鍜屽鐞嗗櫒
        self._tasks[task_id] = task
        task._handler = handler  # 瀛樺偍澶勭悊鍣?
        # 鏍规嵁浼樺厛绾ф坊鍔犲埌瀵瑰簲闃熷垪
        if priority > 0:
            self._high_priority_queue.append(task_id)
        else:
            self._queue.append(task_id)

        self._stats["total_submitted"] += 1

        logger.info(f"浠诲姟宸叉彁浜? {task_id} (绫诲瀷: {task_type}, 浼樺厛绾? {priority})")

        return task

    async def _worker(self, worker_name: str):
        """宸ヤ綔绾跨▼"""
        logger.info(f"宸ヤ綔绾跨▼鍚姩: {worker_name}")

        while self._is_running:
            try:
                # 鑾峰彇涓嬩竴涓换鍔?                task_id = await self._get_next_task()

                if task_id is None:
                    # 娌℃湁浠诲姟锛岀瓑寰?                    await asyncio.sleep(0.1)
                    continue

                # 澶勭悊浠诲姟
                await self._process_task(task_id, worker_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"宸ヤ綔绾跨▼寮傚父: {worker_name} - {e}")
                await asyncio.sleep(1)

        logger.info(f"宸ヤ綔绾跨▼鍋滄: {worker_name}")

    async def _get_next_task(self) -> Optional[str]:
        """鑾峰彇涓嬩竴涓緟澶勭悊浠诲姟"""
        # 浼樺厛澶勭悊楂樹紭鍏堢骇浠诲姟
        if self._high_priority_queue:
            return self._high_priority_queue.popleft()

        # 鏅€氫换鍔?        if self._queue:
            return self._queue.popleft()

        return None

    async def _process_task(self, task_id: str, worker_name: str):
        """澶勭悊浠诲姟锛堟敮鎸佹寚鏁伴€€閬块噸璇曪級"""
        task = self._tasks.get(task_id)
        if not task:
            return

        # 鏇存柊鐘舵€?        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        self._processing_count += 1

        max_retries = 3  # 鏈€澶ч噸璇曟鏁?        retry_delay = 1.0  # 鍒濆閲嶈瘯寤惰繜锛堢锛?
        try:
            for attempt in range(max_retries + 1):
                try:
                    # 鎵ц澶勭悊鍣?                    if hasattr(task, "_handler"):
                        result = await task._handler(task.data)
                        task.result = result
                        task.status = TaskStatus.COMPLETED
                        self._stats["total_completed"] += 1
                        if attempt > 0:
                            logger.info(f"浠诲姟瀹屾垚锛堥噸璇晎attempt}娆★級: {task_id} (宸ヤ綔绾跨▼: {worker_name})")
                        else:
                            logger.info(f"浠诲姟瀹屾垚: {task_id} (宸ヤ綔绾跨▼: {worker_name})")
                        return  # 鎴愬姛锛岄€€鍑?                    else:
                        raise Exception("浠诲姟澶勭悊鍣ㄦ湭瀹氫箟")

                except Exception as e:
                    if attempt < max_retries:
                        # 鎸囨暟閫€閬块噸璇?                        delay = retry_delay * (2**attempt)
                        logger.warning(
                            f"浠诲姟澶辫触锛堝皾璇晎attempt+1}/{max_retries+1}锛? {task_id} - {e}锛寋delay:.1f}绉掑悗閲嶈瘯"
                        )
                        await asyncio.sleep(delay)
                    else:
                        # 鏈€缁堝け璐?                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        self._stats["total_failed"] += 1
                        logger.error(f"浠诲姟鏈€缁堝け璐ワ紙宸查噸璇晎max_retries}娆★級: {task_id} - {e}")
        finally:
            task.completed_at = time.time()
            self._processing_count -= 1

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """鑾峰彇浠诲姟鐘舵€?""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Dict]:
        """鑾峰彇鎵€鏈変换鍔＄姸鎬?""
        return [task.to_dict() for task in self._tasks.values()]

    def get_queue_size(self) -> int:
        """鑾峰彇闃熷垪澶у皬"""
        return len(self._queue) + len(self._high_priority_queue)

    def get_processing_count(self) -> int:
        """鑾峰彇姝ｅ湪澶勭悊鐨勪换鍔℃暟"""
        return self._processing_count

    def get_stats(self) -> Dict:
        """鑾峰彇缁熻淇℃伅"""
        return {
            **self._stats,
            "queue_size": self.get_queue_size(),
            "processing_count": self._processing_count,
            "total_tasks": len(self._tasks),
            "is_running": self._is_running,
            "max_workers": self.max_workers,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """鍙栨秷浠诲姟"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            self._stats["total_cancelled"] += 1

            # 浠庨槦鍒椾腑绉婚櫎
            if task_id in self._queue:
                self._queue.remove(task_id)
            elif task_id in self._high_priority_queue:
                self._high_priority_queue.remove(task_id)

            logger.info(f"浠诲姟宸插彇娑? {task_id}")
            return True

        return False

    async def clear_queue(self):
        """娓呯┖闃熷垪"""
        self._queue.clear()
        self._high_priority_queue.clear()
        logger.info("闃熷垪宸叉竻绌?)


# 鍏ㄥ眬瀹炰緥
_task_queue: Optional[AsyncTaskQueue] = None


def get_task_queue() -> AsyncTaskQueue:
    """鑾峰彇鍏ㄥ眬浠诲姟闃熷垪"""
    global _task_queue
    if _task_queue is None:
        _task_queue = AsyncTaskQueue(max_workers=3, max_queue_size=1000)
    return _task_queue


async def submit_cleaning_task(file_path: str, cleaner_func: Callable, priority: int = 0) -> QueueTask:
    """鎻愪氦娓呮礂浠诲姟"""
    queue = get_task_queue()

    # 纭繚闃熷垪宸插惎鍔?    if not queue._is_running:
        await queue.start()

    # 瀹氫箟澶勭悊鍑芥暟
    async def handler(data):
        file_path = data
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, cleaner_func, file_path)

    # 鐢熸垚浠诲姟ID
    import hashlib

    task_id = f"clean_{hashlib.sha256(file_path.encode()).hexdigest()[:8]}"

    return await queue.submit_task(
        task_id=task_id, task_type="clean", data=file_path, handler=handler, priority=priority
    )


async def submit_batch_cleaning_tasks(
    file_paths: List[str], cleaner_func: Callable, priority: int = 0
) -> List[QueueTask]:
    """鎵归噺鎻愪氦娓呮礂浠诲姟"""
    queue = get_task_queue()

    # 纭繚闃熷垪宸插惎鍔?    if not queue._is_running:
        await queue.start()

    tasks = []
    for file_path in file_paths:
        task = await submit_cleaning_task(file_path, cleaner_func, priority)
        tasks.append(task)

    return tasks


def get_queue_stats() -> Dict:
    """鑾峰彇闃熷垪缁熻淇℃伅"""
    queue = get_task_queue()
    return queue.get_stats()
