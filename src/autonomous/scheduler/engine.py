"""
调度引擎核心 (Scheduler Engine)
===============================
伏羲自运转的核心引擎：任务编排、重试、依赖、持久化。
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobEvent,
    JobExecutionEvent,
)
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.autonomous.scheduler.config import (
    DB_PATH,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    DEFAULT_RETRY_MULTIPLIER,
    JOB_DEFAULTS,
    MAX_HISTORY_PER_JOB,
    PRIORITY_NORMAL,
)

logger = logging.getLogger("fuxi.scheduler")


# ───────────────────────────────────────────────────
# 数据模型
# ───────────────────────────────────────────────────
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DISABLED = "disabled"


@dataclass
class JobSpec:
    """任务规格定义"""

    job_id: str
    name: str
    description: str = ""
    trigger_type: str = "interval"  # interval | cron
    trigger_kwargs: dict = field(default_factory=dict)
    priority: int = PRIORITY_NORMAL
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY
    retry_multiplier: float = DEFAULT_RETRY_MULTIPLIER
    depends_on: List[str] = field(default_factory=list)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class JobRunRecord:
    """单次执行记录"""

    run_id: int = 0
    job_id: str = ""
    status: str = "success"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: float = 0.0
    attempt: int = 1
    error: str = ""
    result: str = ""


# ───────────────────────────────────────────────────
# SQLite 持久化层
# ───────────────────────────────────────────────────
class SchedulerStore:
    """任务状态与执行历史的 SQLite 持久化"""

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> Any:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT DEFAULT 'pending',
                trigger_type    TEXT DEFAULT 'interval',
                trigger_kwargs  TEXT DEFAULT '{}',
                priority        INTEGER DEFAULT 50,
                max_retries     INTEGER DEFAULT 3,
                retry_base_delay    REAL DEFAULT 5.0,
                retry_max_delay     REAL DEFAULT 300.0,
                retry_multiplier    REAL DEFAULT 2.0,
                depends_on      TEXT DEFAULT '[]',
                enabled         INTEGER DEFAULT 1,
                tags            TEXT DEFAULT '[]',
                last_run_at     TEXT,
                last_status     TEXT,
                run_count       INTEGER DEFAULT 0,
                error_count     INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS job_history (
                run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                status      TEXT NOT NULL,
                started_at  TEXT,
                finished_at TEXT,
                duration_ms REAL DEFAULT 0.0,
                attempt     INTEGER DEFAULT 1,
                error       TEXT DEFAULT '',
                result      TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            CREATE INDEX IF NOT EXISTS idx_history_job_id
                ON job_history(job_id, created_at DESC);
        """)
        conn.commit()

    # ── Jobs CRUD ──
    def upsert_job(self, spec: JobSpec) -> Any:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO jobs (job_id, name, description, trigger_type, trigger_kwargs,
                priority, max_retries, retry_base_delay, retry_max_delay,
                retry_multiplier, depends_on, enabled, tags, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(job_id) DO UPDATE SET
                name=excluded.name, description=excluded.description,
                trigger_type=excluded.trigger_type, trigger_kwargs=excluded.trigger_kwargs,
                priority=excluded.priority, max_retries=excluded.max_retries,
                retry_base_delay=excluded.retry_base_delay,
                retry_max_delay=excluded.retry_max_delay,
                retry_multiplier=excluded.retry_multiplier,
                depends_on=excluded.depends_on, enabled=excluded.enabled,
                tags=excluded.tags, updated_at=datetime('now')
        """,
            (
                spec.job_id,
                spec.name,
                spec.description,
                spec.trigger_type,
                json.dumps(spec.trigger_kwargs),
                spec.priority,
                spec.max_retries,
                spec.retry_base_delay,
                spec.retry_max_delay,
                spec.retry_multiplier,
                json.dumps(spec.depends_on),
                int(spec.enabled),
                json.dumps(spec.tags),
            ),
        )
        conn.commit()

    def get_job(self, job_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_all_jobs(self) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM jobs ORDER BY priority, job_id").fetchall()
        return [dict(r) for r in rows]

    def update_job_status(
        self,
        job_id: str,
        status: str,
        last_run_at: Optional[str] = None,
        increment_run: bool = False,
        increment_error: bool = False,
    ):
        conn = self._get_conn()
        sets = ["status=?", "last_status=?", "updated_at=datetime('now')"]
        params: list = [status, status]
        if last_run_at:
            sets.append("last_run_at=?")
            params.append(last_run_at)
        if increment_run:
            sets.append("run_count=run_count+1")
        if increment_error:
            sets.append("error_count=error_count+1")
        params.append(job_id)
        conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", params)
        conn.commit()

    def set_job_enabled(self, job_id: str, enabled: bool) -> Any:
        conn = self._get_conn()
        conn.execute("UPDATE jobs SET enabled=?, updated_at=datetime('now') WHERE job_id=?", (int(enabled), job_id))
        conn.commit()

    # ── History ──
    def add_history(self, record: JobRunRecord) -> Any:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO job_history (job_id, status, started_at, finished_at,
                duration_ms, attempt, error, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.job_id,
                record.status,
                record.started_at,
                record.finished_at,
                record.duration_ms,
                record.attempt,
                record.error,
                record.result,
            ),
        )
        conn.commit()
        # 裁剪过量历史
        self._trim_history(record.job_id)

    def get_history(self, job_id: str, limit: int = 50) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM job_history WHERE job_id=? ORDER BY created_at DESC LIMIT ?", (job_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def _trim_history(self, job_id: str) -> Any:
        conn = self._get_conn()
        conn.execute(
            f"""
            DELETE FROM job_history WHERE job_id=?
            AND run_id NOT IN (
                SELECT run_id FROM job_history WHERE job_id=?
                ORDER BY created_at DESC LIMIT ?
            )
        """,
            (job_id, job_id, MAX_HISTORY_PER_JOB),
        )
        conn.commit()

    def close(self) -> Any:
        if self._conn:
            self._conn.close()
            self._conn = None


# ───────────────────────────────────────────────────
# 调度引擎
# ───────────────────────────────────────────────────
class FuxiScheduler:
    """
    伏羲调度引擎
    基于 APScheduler 的异步任务编排器。
    """

    def __init__(self):
        self._store = SchedulerStore()
        self._scheduler = AsyncIOScheduler(jobstores={"default": MemoryJobStore()})
        self._scheduler.configure(job_defaults=JOB_DEFAULTS)
        self._handlers: Dict[str, Callable] = {}  # job_id → async callable
        self._specs: Dict[str, JobSpec] = {}  # job_id → spec
        self._running: Set[str] = set()  # 正在执行的 job_id
        self._retry_counts: Dict[str, int] = {}  # job_id → 当前重试次数
        self._started = False

        # 注册 APScheduler 事件监听
        self._scheduler.add_listener(self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)

    # ── 生命周期 ──
    def start(self) -> Any:
        """启动调度引擎"""
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        logger.info("[Scheduler] 调度引擎已启动 ⏰")

    def stop(self, wait: bool = True) -> Any:
        """停止调度引擎"""
        if not self._started:
            return
        self._scheduler.shutdown(wait=wait)
        self._started = False
        self._store.close()
        logger.info("[Scheduler] 调度引擎已停止")

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def store(self) -> SchedulerStore:
        return self._store

    # ── 任务注册 ──
    def register_job(self, spec: JobSpec, handler: Callable) -> Any:
        """
        注册一个任务。
        handler 签名: async def handler(**context) -> Any
        """
        self._specs[spec.job_id] = spec
        self._handlers[spec.job_id] = handler
        self._store.upsert_job(spec)
        logger.info(f"[Scheduler] 已注册任务: {spec.job_id} ({spec.name})")

    def schedule_registered_jobs(self) -> Any:
        """将所有已注册且启用的任务加入 APScheduler 调度"""
        for job_id, spec in self._specs.items():
            if not spec.enabled:
                continue
            self._add_to_scheduler(spec)
        logger.info(f"[Scheduler] 已调度 {len(self._specs)} 个任务")

    def _add_to_scheduler(self, spec: JobSpec) -> Any:
        """根据 spec 创建 trigger 并添加到 APScheduler"""
        if spec.trigger_type == "interval":
            trigger = IntervalTrigger(**spec.trigger_kwargs)
        elif spec.trigger_type == "cron":
            trigger = CronTrigger(**spec.trigger_kwargs)
        else:
            logger.error(f"[Scheduler] 未知触发器类型: {spec.trigger_type}")
            return

        self._scheduler.add_job(
            self._execute_job,
            trigger=trigger,
            id=spec.job_id,
            name=spec.name,
            replace_existing=True,
            kwargs={"job_id": spec.job_id},
        )

    # ── 执行引擎 ──
    async def _execute_job(self, job_id: str) -> Any:
        """
        核心执行入口：依赖检查 → 优先级排队 → 执行 → 重试。
        """
        spec = self._specs.get(job_id)
        handler = self._handlers.get(job_id)
        if not spec or not handler:
            logger.warning(f"[Scheduler] 任务 {job_id} 未注册或无处理器")
            return

        # 依赖检查
        if spec.depends_on:
            unresolved = self._check_dependencies(spec.depends_on)
            if unresolved:
                logger.info(f"[Scheduler] {job_id} 依赖未满足，跳过: {unresolved}")
                return

        # 防重入
        if job_id in self._running:
            logger.debug(f"[Scheduler] {job_id} 正在执行，跳过本次")
            return

        self._running.add(job_id)
        attempt = self._retry_counts.get(job_id, 0) + 1
        started_at = datetime.now(timezone.utc).isoformat()
        started_ts = time.monotonic()

        try:
            logger.info(f"[Scheduler] ▶ 执行 {job_id} (第{attempt}次)")
            self._store.update_job_status(job_id, JobStatus.RUNNING.value, started_at)

            # 执行处理器（支持同步和异步）
            if asyncio.iscoroutinefunction(handler):
                result = await handler()
            else:
                result = handler()

            duration_ms = (time.monotonic() - started_ts) * 1000
            finished_at = datetime.now(timezone.utc).isoformat()

            # 成功
            self._retry_counts.pop(job_id, None)
            self._store.update_job_status(job_id, JobStatus.SUCCESS.value, finished_at, increment_run=True)
            self._store.add_history(
                JobRunRecord(
                    job_id=job_id,
                    status="success",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=round(duration_ms, 2),
                    attempt=attempt,
                    result=str(result)[:2000] if result else "",
                )
            )
            logger.info(f"[Scheduler] ✓ {job_id} 完成 ({duration_ms:.0f}ms)")

        except Exception as exc:
            duration_ms = (time.monotonic() - started_ts) * 1000
            finished_at = datetime.now(timezone.utc).isoformat()
            error_msg = f"{type(exc).__name__}: {exc}"

            logger.error(f"[Scheduler] ✗ {job_id} 失败 (第{attempt}次): {error_msg}")
            logger.debug(traceback.format_exc())

            self._store.update_job_status(
                job_id, JobStatus.FAILED.value, finished_at, increment_run=True, increment_error=True
            )
            self._store.add_history(
                JobRunRecord(
                    job_id=job_id,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=round(duration_ms, 2),
                    attempt=attempt,
                    error=error_msg,
                )
            )

            # 指数退避重试
            await self._handle_retry(job_id, spec, attempt, exc)

        finally:
            self._running.discard(job_id)

    async def _handle_retry(self, job_id: str, spec: JobSpec, attempt: int, exc: Exception) -> Any:
        """指数退避重试逻辑"""
        if attempt >= spec.max_retries:
            logger.warning(f"[Scheduler] {job_id} 达到最大重试次数 ({spec.max_retries})，放弃")
            self._retry_counts.pop(job_id, None)
            return

        delay = min(
            spec.retry_base_delay * (spec.retry_multiplier ** (attempt - 1)),
            spec.retry_max_delay,
        )
        self._retry_counts[job_id] = attempt
        self._store.update_job_status(job_id, JobStatus.RETRYING.value)
        logger.info(f"[Scheduler] {job_id} 将在 {delay:.1f}s 后重试 (第{attempt + 1}次)")

        await asyncio.sleep(delay)
        # 触发重试
        asyncio.create_task(self._execute_job(job_id))

    def _check_dependencies(self, depends_on: List[str]) -> List[str]:
        """检查依赖任务是否已完成（最近一次状态为 success）"""
        unresolved = []
        for dep_id in depends_on:
            job_info = self._store.get_job(dep_id)
            if not job_info or job_info.get("last_status") != "success":
                unresolved.append(dep_id)
        return unresolved

    # ── 事件监听 ──
    def _on_job_event(self, event: JobEvent) -> Any:
        """APScheduler 事件回调"""
        if isinstance(event, JobExecutionEvent):
            if event.exception:
                logger.warning(f"[Scheduler] APScheduler 事件: {event.job_id} 异常: {event.exception}")
            else:
                logger.debug(f"[Scheduler] APScheduler 事件: {event.job_id} 执行完成")

    # ── API 支持 ──
    def list_jobs(self) -> List[dict]:
        """获取所有任务列表（带实时状态）"""
        jobs = self._store.get_all_jobs()
        for job in jobs:
            # 解析 JSON 字段
            for field_name in ("trigger_kwargs", "depends_on", "tags"):
                val = job.get(field_name)
                if isinstance(val, str):
                    try:
                        job[field_name] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            # 补充实时信息
            job["is_running"] = job["job_id"] in self._running
            job["retry_count"] = self._retry_counts.get(job["job_id"], 0)
        return jobs

    def get_job_detail(self, job_id: str) -> Optional[dict]:
        """获取单个任务详情"""
        job = self._store.get_job(job_id)
        if not job:
            return None
        for field_name in ("trigger_kwargs", "depends_on", "tags"):
            val = job.get(field_name)
            if isinstance(val, str):
                try:
                    job[field_name] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        job["is_running"] = job_id in self._running
        job["retry_count"] = self._retry_counts.get(job_id, 0)
        return job

    def get_job_history(self, job_id: str, limit: int = 50) -> List[dict]:
        """获取任务执行历史"""
        return self._store.get_history(job_id, limit)

    async def trigger_job(self, job_id: str) -> dict:
        """手动触发任务执行"""
        spec = self._specs.get(job_id)
        if not spec:
            return {"status": "error", "message": f"任务 {job_id} 未注册"}
        if job_id in self._running:
            return {"status": "error", "message": f"任务 {job_id} 正在执行中"}

        # 异步触发，不阻塞
        asyncio.create_task(self._execute_job(job_id))
        return {"status": "ok", "message": f"任务 {job_id} 已触发"}

    def set_job_enabled(self, job_id: str, enabled: bool) -> Any:
        """启用/禁用任务"""
        spec = self._specs.get(job_id)
        if not spec:
            return
        spec.enabled = enabled
        self._store.set_job_enabled(job_id, enabled)
        if enabled:
            self._add_to_scheduler(spec)
            logger.info(f"[Scheduler] 任务 {job_id} 已启用")
        else:
            try:
                self._scheduler.remove_job(job_id)
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass
            logger.info(f"[Scheduler] 任务 {job_id} 已禁用")
