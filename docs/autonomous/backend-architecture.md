# 伏羲自运转系统 — 后端架构设计 v1.0

> 设计日期：2026-07-16
> 作者：帝八
> 状态：方案设计阶段

---

## 一、总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    伏羲自运转系统 (Autonomous Engine)              │
├─────────────┬─────────────┬─────────────┬──────────┬────────────┤
│  Scheduler  │  DataSync   │  Monitor    │SelfHealer│  Reporter  │
│  调度器     │  数据同步    │  监控       │ 自修复   │  报告      │
└──────┬──────┴──────┬──────┴──────┬──────┴────┬─────┴─────┬──────┘
       │             │             │           │           │
       ▼             ▼             ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    经络系统 (Signal Bus)                          │
│  SignalType: HEARTBEAT | ALERT | DATA | COMMAND | SYNC          │
│  Priority:   CRITICAL(0) | HIGH(1) | NORMAL(2) | LOW(3)        │
└──────┬──────────────┬──────────────┬──────────────┬─────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ 少阳·消化  │  │ 太阳·筑基  │  │ 少阴·炼化  │  │ 太阴·显化  │
│ (知识消化) │  │ (检索排序) │  │ (决策合成) │  │ (对外接口) │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
```

### 设计原则

1. **松耦合**：五个模块通过经络系统（信号总线）通信，不直接调用
2. **可插拔**：每个模块独立，可单独启用/禁用
3. **可观测**：所有操作写入审计日志，指标暴露到 Prometheus
4. **自愈优先**：异常先尝试自动修复，修复失败再告警人工介入
5. **低侵入**：作为独立服务运行，不改动现有四象系统核心代码

---

## 二、模块详细设计

### 2.1 调度器模块 (Scheduler)

**职责**：统一管理所有定时任务、周期任务和事件驱动任务。

#### 架构

```
SchedulerEngine
├── JobStore          — 任务持久化（SQLite）
├── PriorityQueue     — 优先级任务队列（Redis ZSET）
├── ExecutorPool      — 线程池执行器
├── RetryPolicy       — 失败重试策略
└── DependencyGraph   — 任务依赖DAG
```

#### 核心类

```python
# src/autonomous/scheduler/engine.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, List, Dict
import asyncio
import uuid


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DISABLED = "disabled"
    SKIPPED = "skipped"       # 依赖未满足，跳过


class TriggerType(Enum):
    INTERVAL = "interval"     # 固定间隔
    CRON = "cron"             # Cron 表达式
    EVENT = "event"           # 事件触发
    ONCE = "once"             # 一次性


class RetryPolicy:
    """重试策略"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_s: float = 10.0,
        max_delay_s: float = 300.0,
        backoff_factor: float = 2.0,
        retry_on: Optional[List[str]] = None,  # 仅在特定异常时重试
    ):
        self.max_retries = max_retries
        self.initial_delay_s = initial_delay_s
        self.max_delay_s = max_delay_s
        self.backoff_factor = backoff_factor
        self.retry_on = retry_on or []

    def get_delay(self, attempt: int) -> float:
        delay = self.initial_delay_s * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay_s)


@dataclass
class JobDefinition:
    """任务定义"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    func_path: str = ""                   # "src.autonomous.monitor.checker:run_health_check"
    trigger_type: TriggerType = TriggerType.INTERVAL
    trigger_config: dict = field(default_factory=dict)  # {"seconds": 300} 或 {"cron": "0 8 * * *"}
    priority: int = 2                     # 0=CRITICAL, 3=LOW
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    depends_on: List[str] = field(default_factory=list)  # 依赖的 job_id 列表
    timeout_s: int = 300
    enabled: bool = True
    tags: List[str] = field(default_factory=list)        # 用于批量管理
    metadata: dict = field(default_factory=dict)


@dataclass
class JobRun:
    """任务执行记录"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    job_id: str = ""
    status: JobStatus = JobStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_s: float = 0.0
    attempt: int = 1
    error: Optional[str] = None
    result_summary: Optional[str] = None
    output_artifacts: List[str] = field(default_factory=list)  # 产出文件路径


class SchedulerEngine:
    """调度器引擎"""

    def __init__(self, signal_bus, db_path: str = "data/autonomous/scheduler.db"):
        self.signal_bus = signal_bus
        self.db_path = db_path
        self._jobs: Dict[str, JobDefinition] = {}
        self._running: Dict[str, asyncio.Task] = {}
        self._executor = None  # ThreadPoolExecutor

    async def register_job(self, job: JobDefinition):
        """注册任务"""
        self._jobs[job.job_id] = job
        self._persist_job(job)
        await self.signal_bus.emit(
            signal_type="COMMAND",
            source="scheduler",
            payload={"action": "job_registered", "job_id": job.job_id}
        )

    async def unregister_job(self, job_id: str):
        """注销任务"""
        self._jobs.pop(job_id, None)
        self._delete_job_from_db(job_id)

    async def trigger_job(self, job_id: str, force: bool = False):
        """手动触发任务"""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if not force and not job.enabled:
            raise ValueError(f"Job {job_id} is disabled")
        await self._execute_job(job)

    async def start(self):
        """启动调度引擎"""
        self._load_jobs_from_db()
        # 启动调度循环
        asyncio.create_task(self._scheduler_loop())

    async def _scheduler_loop(self):
        """主调度循环"""
        while True:
            now = datetime.utcnow()
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                if self._should_run(job, now):
                    # 检查依赖
                    if self._check_dependencies(job):
                        asyncio.create_task(self._execute_job(job))
                    else:
                        await self._record_skip(job, "dependencies not met")
            await asyncio.sleep(1)  # 1秒检查一次

    async def _execute_job(self, job: JobDefinition):
        """执行单个任务（含重试）"""
        run = JobRun(job_id=job.job_id)

        for attempt in range(1, job.retry_policy.max_retries + 1):
            run.attempt = attempt
            run.status = JobStatus.RUNNING
            run.started_at = datetime.utcnow()

            try:
                # 动态导入并执行
                func = self._load_func(job.func_path)
                result = await asyncio.wait_for(
                    func(), timeout=job.timeout_s
                )
                run.status = JobStatus.SUCCESS
                run.result_summary = str(result)[:500] if result else None
                run.finished_at = datetime.utcnow()
                run.duration_s = (run.finished_at - run.started_at).total_seconds()

                await self._persist_run(run)
                await self.signal_bus.emit(
                    signal_type="DATA",
                    source="scheduler",
                    payload={
                        "event": "job_completed",
                        "job_id": job.job_id,
                        "run_id": run.run_id,
                        "duration_s": run.duration_s,
                    }
                )
                return  # 成功，退出重试循环

            except asyncio.TimeoutError:
                run.error = f"Timeout after {job.timeout_s}s"
                run.status = JobStatus.FAILED
            except Exception as e:
                run.error = f"{type(e).__name__}: {str(e)[:300]}"
                run.status = JobStatus.FAILED

            # 判断是否需要重试
            if attempt < job.retry_policy.max_retries:
                if job.retry_policy.retry_on and \
                   not any(t in run.error for t in job.retry_policy.retry_on):
                    break  # 不在重试范围内
                run.status = JobStatus.RETRYING
                delay = job.retry_policy.get_delay(attempt)
                await asyncio.sleep(delay)

        run.finished_at = datetime.utcnow()
        run.duration_s = (run.finished_at - run.started_at).total_seconds()
        await self._persist_run(run)

        # 发出告警
        await self.signal_bus.emit(
            signal_type="ALERT",
            source="scheduler",
            priority="HIGH",
            payload={
                "event": "job_failed",
                "job_id": job.job_id,
                "run_id": run.run_id,
                "error": run.error,
                "attempts": run.attempt,
            }
        )

    def _load_func(self, func_path: str) -> Callable:
        """动态导入函数：'module.path:func_name'"""
        module_path, func_name = func_path.rsplit(":", 1)
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, func_name)

    def _should_run(self, job: JobDefinition, now: datetime) -> bool:
        """判断任务是否应该运行"""
        if job.trigger_type == TriggerType.INTERVAL:
            last_run = self._get_last_run_time(job.job_id)
            if last_run is None:
                return True
            interval_s = job.trigger_config.get("seconds", 3600)
            return (now - last_run).total_seconds() >= interval_s

        elif job.trigger_type == TriggerType.CRON:
            from croniter import croniter
            cron = croniter(job.trigger_config["cron"], now)
            next_run = cron.get_prev(datetime)
            # 判断是否在当前秒内
            return abs((now - next_run).total_seconds()) < 1.5

        elif job.trigger_type == TriggerType.EVENT:
            # 事件驱动任务由信号总线直接触发
            return False

        elif job.trigger_type == TriggerType.ONCE:
            return self._get_last_run_time(job.job_id) is None

        return False

    def _check_dependencies(self, job: JobDefinition) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in job.depends_on:
            dep_status = self._get_last_run_status(dep_id)
            if dep_status != JobStatus.SUCCESS:
                return False
        return True

    # --- 持久化方法（SQLite）---
    def _persist_job(self, job: JobDefinition): ...
    def _delete_job_from_db(self, job_id: str): ...
    def _load_jobs_from_db(self): ...
    def _persist_run(self, run: JobRun): ...
    def _get_last_run_time(self, job_id: str): ...
    def _get_last_run_status(self, job_id: str) -> Optional[JobStatus]: ...
    async def _record_skip(self, job: JobDefinition, reason: str): ...
```

#### 预置任务清单

| job_id | 名称 | 触发方式 | 间隔 | 优先级 |
|--------|------|----------|------|--------|
| `health_check` | 健康检查 | interval | 60s | CRITICAL |
| `metrics_collect` | 指标采集 | interval | 30s | HIGH |
| `plugin_sync` | 插件源同步 | cron | 每天 02:00 | NORMAL |
| `kb_incremental_update` | 知识库增量更新 | cron | 每天 03:00 | NORMAL |
| `cache_refresh` | 缓存刷新 | interval | 3600s | LOW |
| `report_daily` | 日报生成 | cron | 每天 08:00 | NORMAL |
| `report_weekly` | 周报生成 | cron | 每周一 09:00 | NORMAL |
| `log_cleanup` | 日志清理 | cron | 每周日 04:00 | LOW |
| `data_consistency_check` | 数据一致性校验 | cron | 每天 05:00 | NORMAL |
| `self_heal_scan` | 自修复扫描 | interval | 120s | HIGH |

---

### 2.2 数据同步模块 (DataSync)

**职责**：管理插件源数据同步、知识库增量更新、缓存策略和数据一致性。

#### 架构

```
DataSyncManager
├── PluginSourceSync       — 插件源同步（NPM/GitHub/PyPI）
├── KnowledgeSync          — 知识库增量同步
├── CacheStrategy          — 缓存刷新策略
├── ConsistencyChecker     — 数据一致性校验
└── SyncState              — 同步状态跟踪
```

#### 核心类

```python
# src/autonomous/datasync/manager.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib


class SyncStatus(Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功


class DataSourceType(Enum):
    NPM = "npm"
    GITHUB = "github"
    PYPI = "pypi"
    LOCAL = "local"          # 本地文件目录
    API = "api"              # 外部 API


@dataclass
class SyncCheckpoint:
    """同步检查点 — 记录上次同步到哪里"""
    source_id: str = ""
    last_sync_at: Optional[datetime] = None
    last_cursor: Optional[str] = None       # 分页游标 / commit hash / etag
    last_checksum: Optional[str] = None     # 数据校验和
    items_synced: int = 0
    status: SyncStatus = SyncStatus.IDLE


@dataclass
class DataSource:
    """数据源定义"""
    source_id: str = ""
    name: str = ""
    source_type: DataSourceType = DataSourceType.LOCAL
    config: dict = field(default_factory=dict)
    # NPM:  {"registry": "...", "packages": ["pkg1", "pkg2"]}
    # GitHub: {"owner": "...", "repo": "...", "path": "..."}
    # PyPI: {"packages": ["pkg1"]}
    # Local: {"path": "/path/to/watch", "pattern": "*.pdf"}
    sync_interval_s: int = 3600
    enabled: bool = True
    retry_policy: dict = field(default_factory=lambda: {
        "max_retries": 3, "delay_s": 30
    })


class PluginSourceSync:
    """插件源同步器"""

    def __init__(self, signal_bus, state: SyncState):
        self.signal_bus = signal_bus
        self.state = state

    async def sync_npm(self, source: DataSource) -> SyncCheckpoint:
        """同步 NPM 包信息"""
        checkpoint = self.state.get_checkpoint(source.source_id)
        # 1. 调用 NPM registry API 拉取更新
        # 2. 对比 checkpoint.last_cursor 获取增量
        # 3. 更新本地缓存
        # 4. 更新 checkpoint
        return checkpoint

    async def sync_github(self, source: DataSource) -> SyncCheckpoint:
        """同步 GitHub 仓库数据（如 MCP 工具定义）"""
        checkpoint = self.state.get_checkpoint(source.source_id)
        # 1. 调用 GitHub API（支持 If-None-Match / ETag）
        # 2. 对比 commit hash 获取增量
        # 3. 下载变更文件
        # 4. 更新 checkpoint
        return checkpoint

    async def sync_pypi(self, source: DataSource) -> SyncCheckpoint:
        """同步 PyPI 包信息"""
        checkpoint = self.state.get_checkpoint(source.source_id)
        # 1. 调用 PyPI JSON API
        # 2. 对比版本号
        # 3. 更新本地缓存
        return checkpoint


class KnowledgeSync:
    """知识库增量同步器"""

    def __init__(self, signal_bus, state: SyncState):
        self.signal_bus = signal_bus
        self.state = state

    async def incremental_update(self, source_path: str) -> dict:
        """
        增量更新知识库：
        1. 扫描 source_path 下的文件变更（mtime + checksum）
        2. 新增/修改的文件 → 送入少阳·消化系统处理
        3. 删除的文件 → 从知识库中移除
        4. 更新同步状态
        """
        result = {"added": 0, "updated": 0, "deleted": 0, "errors": []}

        # 扫描变更
        changed_files = await self._scan_changes(source_path)

        for file_info in changed_files:
            try:
                if file_info["action"] == "delete":
                    # 通知少阳移除
                    await self.signal_bus.emit(
                        signal_type="DATA",
                        source="datasync",
                        payload={
                            "event": "knowledge_remove",
                            "file_path": file_info["path"],
                        }
                    )
                    result["deleted"] += 1
                else:
                    # 送入消化管线
                    await self.signal_bus.emit(
                        signal_type="DATA",
                        source="datasync",
                        payload={
                            "event": "knowledge_ingest",
                            "file_path": file_info["path"],
                            "is_update": file_info["action"] == "update",
                        }
                    )
                    if file_info["action"] == "add":
                        result["added"] += 1
                    else:
                        result["updated"] += 1
            except Exception as e:
                result["errors"].append(f"{file_info['path']}: {str(e)}")

        return result

    async def _scan_changes(self, source_path: str) -> List[dict]:
        """扫描文件变更（基于 mtime + MD5 校验和）"""
        # 实现略：遍历目录，对比 checkpoint 中记录的 checksum
        return []


class CacheStrategy:
    """缓存刷新策略"""

    def __init__(self):
        self._strategies: Dict[str, dict] = {}

    def register_strategy(self, cache_name: str, config: dict):
        """
        config 示例：
        {
            "ttl_s": 3600,              # 默认 TTL
            "refresh_interval_s": 1800, # 主动刷新间隔
            "max_size": 10000,          # 最大条目数
            "eviction": "lru",          # 淘汰策略
            "preload_keys": [],         # 启动时预热的 key
        }
        """
        self._strategies[cache_name] = config

    async def refresh(self, cache_name: str) -> dict:
        """按策略刷新缓存"""
        strategy = self._strategies.get(cache_name)
        if not strategy:
            return {"error": f"No strategy for {cache_name}"}
        # 实现：根据策略清除过期、预热、压缩等
        return {"cache": cache_name, "refreshed": True}

    async def invalidate_pattern(self, pattern: str) -> int:
        """按模式批量失效缓存"""
        # 例：invalidate_pattern("search:*") 清除所有搜索缓存
        return 0


class ConsistencyChecker:
    """数据一致性校验器"""

    async def check_vector_vs_fts(self) -> dict:
        """
        校验 ChromaDB 向量库 vs SQLite FTS5 的一致性：
        - 向量库有但 FTS 没有 → 数据丢失
        - FTS 有但向量库没有 → 向量化失败
        """
        return {
            "status": "ok",
            "vector_only": [],   # 仅在向量库中的 chunk_id
            "fts_only": [],      # 仅在 FTS 中的 chunk_id
            "mismatch_count": 0,
        }

    async def check_file_vs_index(self) -> dict:
        """校验磁盘文件 vs 索引的一致性"""
        return {
            "status": "ok",
            "unindexed_files": [],   # 有文件但没索引
            "orphaned_indices": [],  # 有索引但文件不存在
            "checksum_mismatches": [],
        }

    async def check_graph_integrity(self) -> dict:
        """校验知识图谱完整性"""
        return {
            "status": "ok",
            "orphan_nodes": 0,       # 无边的孤立节点
            "broken_edges": 0,       # 引用不存在节点的边
            "duplicate_edges": 0,
        }
```

#### 缓存刷新策略矩阵

| 缓存层 | 策略 | TTL | 刷新方式 |
|--------|------|-----|----------|
| 语义缓存（L0） | LRU + TTL | 1800s | 查询触发 + 定时清理 |
| 搜索结果缓存 | LRU | 600s | 数据变更时失效 |
| 知识图谱缓存 | 全量 | 3600s | 增量更新后重建 |
| 插件元数据缓存 | ETag | 7200s | 插件源同步时刷新 |
| 配置缓存 | 事件驱动 | 无 | 配置变更信号触发 |

---

### 2.3 监控模块 (Monitor)

**职责**：全面监控系统健康、性能指标和资源使用，驱动告警和自修复。

#### 架构

```
MonitorEngine
├── HealthChecker          — 健康检查器
│   ├── APIHealthCheck     — API 服务检查
│   ├── DBHealthCheck      — 数据库检查
│   ├── ServiceHealthCheck — 外部服务检查
│   └── ComponentHealthCheck — 四象系统组件检查
├── MetricsCollector       — 指标采集器
│   ├── SystemMetrics      — 系统资源（CPU/内存/磁盘）
│   ├── AppMetrics         — 应用指标（QPS/延迟/错误率）
│   └── BusinessMetrics    — 业务指标（搜索量/反馈率）
├── AlertEngine            — 告警规则引擎
│   ├── RuleEvaluator      — 规则评估器
│   ├── AlertManager       — 告警管理（去重/抑制/升级）
│   └── Notifier           — 通知渠道（信号总线/日志）
└── MetricsStore           — 指标存储（SQLite 时序）
```

#### 核心类

```python
# src/autonomous/monitor/engine.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
import asyncio


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"    # 部分功能受限
    UNHEALTHY = "unhealthy"  # 服务不可用
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthReport:
    """健康报告"""
    component: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0
    details: dict = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str = ""
    name: str = ""
    metric: str = ""              # 指标名称，如 "cpu_percent"
    condition: str = ""           # "> 90", "< 10", "== 0"
    severity: AlertSeverity = AlertSeverity.WARNING
    duration_s: int = 0           # 持续多久才触发（防抖）
    cooldown_s: int = 300         # 告警冷却期（防刷）
    channels: List[str] = field(default_factory=lambda: ["signal_bus"])
    description: str = ""
    auto_heal_action: Optional[str] = None  # 触发的自修复动作


@dataclass
class Alert:
    """告警实例"""
    alert_id: str = ""
    rule_id: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = ""
    message: str = ""
    metric_value: Any = None
    threshold: Any = None
    fired_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    status: str = "firing"        # firing | resolved | suppressed


class HealthChecker:
    """健康检查器"""

    def __init__(self, signal_bus):
        self.signal_bus = signal_bus
        self._checks: List[Callable] = []

    def register_check(self, name: str, check_func: Callable, timeout_s: float = 10.0):
        """注册健康检查项"""
        self._checks.append({
            "name": name,
            "func": check_func,
            "timeout": timeout_s,
        })

    async def run_all_checks(self) -> List[HealthReport]:
        """并行执行所有健康检查"""
        tasks = []
        for check in self._checks:
            tasks.append(self._run_single_check(check))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reports = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                reports.append(HealthReport(
                    component=self._checks[i]["name"],
                    status=HealthStatus.UNKNOWN,
                    message=f"Check exception: {str(result)[:200]}",
                ))
            else:
                reports.append(result)
        return reports

    async def _run_single_check(self, check: dict) -> HealthReport:
        """执行单个健康检查"""
        start = datetime.utcnow()
        try:
            result = await asyncio.wait_for(
                check["func"](), timeout=check["timeout"]
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            return HealthReport(
                component=check["name"],
                status=HealthStatus.HEALTHY if result.get("ok", True) else HealthStatus.UNHEALTHY,
                message=result.get("message", "OK"),
                latency_ms=latency,
                details=result,
            )
        except asyncio.TimeoutError:
            return HealthReport(
                component=check["name"],
                status=HealthStatus.UNHEALTHY,
                message=f"Timeout after {check['timeout']}s",
            )
        except Exception as e:
            return HealthReport(
                component=check["name"],
                status=HealthStatus.UNHEALTHY,
                message=str(e)[:300],
            )


class MetricsCollector:
    """指标采集器"""

    def __init__(self):
        self._collectors: List[Callable] = []

    def register_collector(self, name: str, func: Callable):
        self._collectors.append({"name": name, "func": func})

    async def collect_all(self) -> Dict[str, Any]:
        """采集所有指标"""
        metrics = {}
        for collector in self._collectors:
            try:
                value = await collector["func"]()
                metrics[collector["name"]] = value
            except Exception as e:
                metrics[collector["name"]] = {"error": str(e)}
        return metrics


class AlertEngine:
    """告警规则引擎"""

    def __init__(self, signal_bus):
        self.signal_bus = signal_bus
        self._rules: List[AlertRule] = []
        self._active_alerts: Dict[str, Alert] = {}  # rule_id -> Alert
        self._last_fired: Dict[str, datetime] = {}  # rule_id -> last_fire_time
        self._violation_start: Dict[str, datetime] = {}  # rule_id -> violation start

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)

    async def evaluate(self, metrics: Dict[str, Any]):
        """评估所有规则"""
        for rule in self._rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue

            violated = self._check_condition(value, rule.condition)

            if violated:
                # 记录违规开始时间
                if rule.rule_id not in self._violation_start:
                    self._violation_start[rule.rule_id] = datetime.utcnow()

                # 检查持续时间
                duration = (datetime.utcnow() - self._violation_start[rule.rule_id]).total_seconds()
                if duration < rule.duration_s:
                    continue  # 还没达到持续阈值

                # 检查冷却期
                if rule.rule_id in self._last_fired:
                    cooldown = (datetime.utcnow() - self._last_fired[rule.rule_id]).total_seconds()
                    if cooldown < rule.cooldown_s:
                        continue  # 在冷却期内

                # 触发告警
                await self._fire_alert(rule, value)
            else:
                # 清除违规状态
                self._violation_start.pop(rule.rule_id, None)
                # 如果有活跃告警，标记为已解决
                if rule.rule_id in self._active_alerts:
                    await self._resolve_alert(rule)

    def _check_condition(self, value: Any, condition: str) -> bool:
        """评估条件表达式"""
        # 简单实现：支持 >, <, >=, <=, ==, !=
        try:
            # 安全评估（不用 eval）
            if ">" in condition:
                op, threshold = condition.split(">", 1)
                if ">=" in condition:
                    _, threshold = condition.split(">=", 1)
                    return float(value) >= float(threshold.strip())
                return float(value) > float(threshold.strip())
            elif "<" in condition:
                op, threshold = condition.split("<", 1)
                if "<=" in condition:
                    _, threshold = condition.split("<=", 1)
                    return float(value) <= float(threshold.strip())
                return float(value) < float(threshold.strip())
            elif "==" in condition:
                _, threshold = condition.split("==", 1)
                return str(value) == threshold.strip()
            elif "!=" in condition:
                _, threshold = condition.split("!=", 1)
                return str(value) != threshold.strip()
        except (ValueError, TypeError):
            return False
        return False

    async def _fire_alert(self, rule: AlertRule, metric_value: Any):
        """触发告警"""
        alert = Alert(
            alert_id=f"alert_{rule.rule_id}_{int(datetime.utcnow().timestamp())}",
            rule_id=rule.rule_id,
            severity=rule.severity,
            title=rule.name,
            message=f"{rule.description}: {rule.metric}={metric_value} (condition: {rule.condition})",
            metric_value=metric_value,
            threshold=rule.condition,
        )
        self._active_alerts[rule.rule_id] = alert
        self._last_fired[rule.rule_id] = datetime.utcnow()

        # 发送告警信号
        await self.signal_bus.emit(
            signal_type="ALERT",
            source="monitor",
            priority=rule.severity.value.upper(),
            payload={
                "alert_id": alert.alert_id,
                "rule_id": rule.rule_id,
                "severity": rule.severity.value,
                "title": alert.title,
                "message": alert.message,
                "auto_heal_action": rule.auto_heal_action,
            }
        )

    async def _resolve_alert(self, rule: AlertRule):
        """告警恢复"""
        alert = self._active_alerts.pop(rule.rule_id, None)
        if alert:
            alert.status = "resolved"
            alert.resolved_at = datetime.utcnow()
            await self.signal_bus.emit(
                signal_type="DATA",
                source="monitor",
                payload={
                    "event": "alert_resolved",
                    "alert_id": alert.alert_id,
                    "rule_id": rule.rule_id,
                }
            )
```

#### 预置告警规则

| rule_id | 指标 | 条件 | 持续 | 严重度 | 自修复动作 |
|---------|------|------|------|--------|-----------|
| `cpu_high` | cpu_percent | > 90 | 60s | WARNING | `throttle_requests` |
| `mem_high` | memory_percent | > 85 | 30s | WARNING | `clear_cache` |
| `disk_low` | disk_free_gb | < 5 | 0s | CRITICAL | `cleanup_logs` |
| `api_error_rate` | error_rate_5xx | > 0.1 | 120s | CRITICAL | `restart_service` |
| `api_latency_p99` | latency_p99_ms | > 5000 | 60s | WARNING | `clear_cache` |
| `db_connection_lost` | db_healthy | == 0 | 0s | CRITICAL | `rebuild_pool` |
| `vector_store_empty` | vector_chunks | == 0 | 0s | CRITICAL | `rebuild_vectors` |
| `llm_timeout_rate` | llm_timeout_rate | > 0.3 | 120s | WARNING | `switch_llm_fallback` |
| `queue_backlog` | pending_tasks | > 100 | 300s | WARNING | None |

---

### 2.4 自修复模块 (SelfHealer)

**职责**：接收告警信号，自动执行修复动作，减少人工干预。

#### 架构

```
SelfHealerEngine
├── ActionRegistry         — 修复动作注册表
├── ExecutionHistory       — 执行历史记录
├── SafetyGuard            — 安全守卫（频率限制/回滚）
└── Actions
    ├── restart_service    — 服务重启
    ├── rebuild_pool       — 连接池重建
    ├── clear_cache        — 缓存清理
    ├── cleanup_logs       — 日志清理
    ├── rebuild_vectors    — 向量索引重建
    ├── throttle_requests  — 请求限流
    └── switch_llm_fallback— LLM 降级切换
```

#### 核心类

```python
# src/autonomous/selfhealer/engine.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable, Any
import asyncio


class HealActionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"        # 安全守卫拦截
    ROLLED_BACK = "rolled_back"


@dataclass
class HealAction:
    """修复动作定义"""
    action_id: str = ""
    name: str = ""
    description: str = ""
    handler: str = ""           # "src.autonomous.selfhealer.actions:restart_service"
    params: dict = field(default_factory=dict)
    max_per_hour: int = 5       # 每小时最多执行次数
    cooldown_s: int = 60        # 冷却期
    requires_confirmation: bool = False  # 高危动作需确认
    rollback_action: Optional[str] = None  # 回滚动作
    estimated_duration_s: int = 30


@dataclass
class HealExecution:
    """修复执行记录"""
    execution_id: str = ""
    action_id: str = ""
    status: HealActionStatus = HealActionStatus.PENDING
    trigger: str = ""           # 触发来源（alert_id 或手动）
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    rolled_back: bool = False


class SafetyGuard:
    """安全守卫 — 防止过度自修复"""

    def __init__(self):
        self._execution_counts: Dict[str, List[datetime]] = {}

    def can_execute(self, action: HealAction) -> tuple[bool, str]:
        """检查是否允许执行"""
        now = datetime.utcnow()
        history = self._execution_counts.get(action.action_id, [])

        # 清理过期记录
        history = [t for t in history if (now - t).total_seconds() < 3600]
        self._execution_counts[action.action_id] = history

        # 频率检查
        if len(history) >= action.max_per_hour:
            return False, f"Rate limit: {len(history)}/{action.max_per_hour} per hour"

        # 冷却检查
        if history:
            last = max(history)
            if (now - last).total_seconds() < action.cooldown_s:
                return False, f"Cooldown: {action.cooldown_s}s not elapsed"

        return True, "OK"

    def record_execution(self, action_id: str):
        if action_id not in self._execution_counts:
            self._execution_counts[action_id] = []
        self._execution_counts[action_id].append(datetime.utcnow())


class SelfHealerEngine:
    """自修复引擎"""

    def __init__(self, signal_bus):
        self.signal_bus = signal_bus
        self._actions: Dict[str, HealAction] = {}
        self._safety = SafetyGuard()
        self._history: List[HealExecution] = []

    def register_action(self, action: HealAction):
        """注册修复动作"""
        self._actions[action.action_id] = action

    async def handle_alert(self, alert_payload: dict):
        """处理告警信号，决定是否执行修复"""
        heal_action_id = alert_payload.get("auto_heal_action")
        if not heal_action_id:
            return  # 无自动修复动作

        action = self._actions.get(heal_action_id)
        if not action:
            return

        # 安全检查
        can_run, reason = self._safety.can_execute(action)
        if not can_run:
            execution = HealExecution(
                action_id=heal_action_id,
                status=HealActionStatus.SKIPPED,
                trigger=alert_payload.get("alert_id", "unknown"),
                result=f"Safety guard: {reason}",
            )
            self._history.append(execution)
            return

        # 执行修复
        await self.execute_action(heal_action_id, trigger=alert_payload.get("alert_id"))

    async def execute_action(self, action_id: str, trigger: str = "manual") -> HealExecution:
        """执行修复动作"""
        action = self._actions.get(action_id)
        if not action:
            raise ValueError(f"Action {action_id} not found")

        execution = HealExecution(
            action_id=action_id,
            trigger=trigger,
            status=HealActionStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        self._safety.record_execution(action_id)

        try:
            # 动态导入并执行
            func = self._load_handler(action.handler)
            result = await asyncio.wait_for(
                func(**action.params),
                timeout=action.estimated_duration_s * 2,
            )
            execution.status = HealActionStatus.SUCCESS
            execution.result = str(result)[:500] if result else "OK"
            execution.finished_at = datetime.utcnow()

            # 通知修复成功
            await self.signal_bus.emit(
                signal_type="DATA",
                source="selfhealer",
                payload={
                    "event": "heal_success",
                    "execution_id": execution.execution_id,
                    "action_id": action_id,
                    "trigger": trigger,
                    "duration_s": (execution.finished_at - execution.started_at).total_seconds(),
                }
            )

        except Exception as e:
            execution.status = HealActionStatus.FAILED
            execution.error = str(e)[:500]
            execution.finished_at = datetime.utcnow()

            # 尝试回滚
            if action.rollback_action:
                try:
                    rollback_func = self._load_handler(action.rollback_action)
                    await rollback_func()
                    execution.rolled_back = True
                    execution.status = HealActionStatus.ROLLED_BACK
                except Exception:
                    pass

            # 通知修复失败
            await self.signal_bus.emit(
                signal_type="ALERT",
                source="selfhealer",
                priority="CRITICAL",
                payload={
                    "event": "heal_failed",
                    "execution_id": execution.execution_id,
                    "action_id": action_id,
                    "error": execution.error,
                    "rolled_back": execution.rolled_back,
                }
            )

        self._history.append(execution)
        return execution

    def _load_handler(self, handler_path: str) -> Callable:
        module_path, func_name = handler_path.rsplit(":", 1)
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
```

#### 预置修复动作

| action_id | 名称 | 执行内容 | 频率限制 | 回滚动作 |
|-----------|------|----------|----------|----------|
| `restart_service` | 服务重启 | 通过 systemd/进程管理重启 kb-server | 3次/小时 | 无 |
| `rebuild_pool` | 连接池重建 | 关闭并重建数据库连接池 | 5次/小时 | 无 |
| `clear_cache` | 缓存清理 | 清除语义缓存和搜索缓存 | 10次/小时 | 无 |
| `cleanup_logs` | 日志清理 | 清理 >7天 的日志文件 | 2次/小时 | 无 |
| `rebuild_vectors` | 向量重建 | 触发全量向量重建任务 | 1次/天 | 无 |
| `throttle_requests` | 请求限流 | 临时降低并发上限 50% | 3次/小时 | `restore_throttle` |
| `switch_llm_fallback` | LLM降级 | 切换到备用 LLM 模型 | 3次/小时 | `restore_llm` |
| `restart_redis` | Redis重启 | 重启 Redis 服务 | 3次/小时 | 无 |

---

### 2.5 报告模块 (Reporter)

**职责**：自动生成运维报告、异常汇总和用户行为分析。

#### 架构

```
ReportEngine
├── ReportGenerator        — 报告生成器
│   ├── DailyReporter      — 日报
│   ├── WeeklyReporter     — 周报
│   └── AdHocReporter      — 按需报告
├── DataAggregator         — 数据聚合器
├── TemplateEngine         — 模板引擎（Markdown）
└── ReportStore            — 报告存储
```

#### 核心类

```python
# src/autonomous/reporter/engine.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json


class ReportType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INCIDENT = "incident"      # 事件报告
    ADHOC = "adhoc"


@dataclass
class Report:
    """报告定义"""
    report_id: str = ""
    report_type: ReportType = ReportType.DAILY
    title: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    sections: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    format: str = "markdown"    # markdown | json
    file_path: Optional[str] = None


class DataAggregator:
    """数据聚合器 — 从各模块采集报告所需数据"""

    def __init__(self, signal_bus):
        self.signal_bus = signal_bus

    async def aggregate_health_data(self, start: datetime, end: datetime) -> dict:
        """聚合健康检查数据"""
        return {
            "total_checks": 0,
            "healthy_count": 0,
            "degraded_count": 0,
            "unhealthy_count": 0,
            "uptime_percent": 100.0,
            "components": {},  # component -> {status, avg_latency_ms}
        }

    async def aggregate_performance_data(self, start: datetime, end: datetime) -> dict:
        """聚合性能指标"""
        return {
            "total_requests": 0,
            "avg_latency_ms": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate": 0.0,
            "error_count": 0,
            "qps_peak": 0,
            "qps_avg": 0,
            "top_endpoints": [],  # [{endpoint, count, avg_latency}]
        }

    async def aggregate_search_data(self, start: datetime, end: datetime) -> dict:
        """聚合搜索数据"""
        return {
            "total_searches": 0,
            "unique_queries": 0,
            "avg_results": 0,
            "empty_result_rate": 0.0,
            "cache_hit_rate": 0.0,
            "top_queries": [],       # [{query, count}]
            "search_trend": [],      # [{hour, count}]
        }

    async def aggregate_feedback_data(self, start: datetime, end: datetime) -> dict:
        """聚合反馈数据"""
        return {
            "total_feedbacks": 0,
            "useful_count": 0,
            "useless_count": 0,
            "satisfaction_rate": 0.0,
            "top_issues": [],  # [{issue, count}]
        }

    async def aggregate_heal_data(self, start: datetime, end: datetime) -> dict:
        """聚合自修复数据"""
        return {
            "total_actions": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "top_actions": [],  # [{action_id, count, success_rate}]
        }

    async def aggregate_alert_data(self, start: datetime, end: datetime) -> dict:
        """聚合告警数据"""
        return {
            "total_alerts": 0,
            "by_severity": {"critical": 0, "warning": 0, "info": 0},
            "avg_resolution_time_s": 0,
            "top_rules": [],  # [{rule_id, fire_count}]
        }

    async def aggregate_task_data(self, start: datetime, end: datetime) -> dict:
        """聚合调度任务数据"""
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_duration_s": 0,
            "failed_jobs": [],  # [{job_id, error, count}]
        }


class ReportGenerator:
    """报告生成器"""

    def __init__(self, aggregator: DataAggregator):
        self.aggregator = aggregator

    async def generate_daily(self, date: datetime = None) -> Report:
        """生成日报"""
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start = date
        end = date + timedelta(days=1)

        report = Report(
            report_type=ReportType.DAILY,
            title=f"伏羲运维日报 {date.strftime('%Y-%m-%d')}",
            period_start=start,
            period_end=end,
        )

        # 并行采集各维度数据
        import asyncio
        results = await asyncio.gather(
            self.aggregator.aggregate_health_data(start, end),
            self.aggregator.aggregate_performance_data(start, end),
            self.aggregator.aggregate_search_data(start, end),
            self.aggregator.aggregate_feedback_data(start, end),
            self.aggregator.aggregate_heal_data(start, end),
            self.aggregator.aggregate_alert_data(start, end),
            self.aggregator.aggregate_task_data(start, end),
        )

        report.sections = {
            "health": results[0],
            "performance": results[1],
            "search": results[2],
            "feedback": results[3],
            "self_heal": results[4],
            "alerts": results[5],
            "tasks": results[6],
        }

        report.summary = self._generate_summary(report.sections)
        return report

    async def generate_weekly(self, week_start: datetime = None) -> Report:
        """生成周报"""
        if week_start is None:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

        report = Report(
            report_type=ReportType.WEEKLY,
            title=f"伏羲运维周报 {week_start.strftime('%Y-%m-%d')} ~ {(week_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
            period_start=week_start,
            period_end=week_end,
        )

        # 采集数据（同日报，时间范围不同）
        import asyncio
        results = await asyncio.gather(
            self.aggregator.aggregate_health_data(week_start, week_end),
            self.aggregator.aggregate_performance_data(week_start, week_end),
            self.aggregator.aggregate_search_data(week_start, week_end),
            self.aggregator.aggregate_feedback_data(week_start, week_end),
            self.aggregator.aggregate_heal_data(week_start, week_end),
            self.aggregator.aggregate_alert_data(week_start, week_end),
            self.aggregator.aggregate_task_data(week_start, week_end),
        )

        report.sections = {
            "health": results[0],
            "performance": results[1],
            "search": results[2],
            "feedback": results[3],
            "self_heal": results[4],
            "alerts": results[5],
            "tasks": results[6],
        }

        report.summary = self._generate_weekly_summary(report.sections)
        return report

    def _generate_summary(self, sections: dict) -> str:
        """生成日报摘要"""
        health = sections.get("health", {})
        perf = sections.get("performance", {})
        search = sections.get("search", {})
        alerts = sections.get("alerts", {})
        return (
            f"系统运行 {health.get('uptime_percent', 0):.1f}% 正常，"
            f"处理请求 {perf.get('total_requests', 0)} 次，"
            f"搜索 {search.get('total_searches', 0)} 次，"
            f"触发告警 {alerts.get('total_alerts', 0)} 次。"
        )

    def _generate_weekly_summary(self, sections: dict) -> str:
        """生成周报摘要"""
        # 类似日报，增加周趋势分析
        return self._generate_summary(sections) + " [周趋势待分析]"

    def render_markdown(self, report: Report) -> str:
        """渲染 Markdown 格式"""
        lines = [
            f"# {report.title}",
            f"",
            f"> 生成时间: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 统计周期: {report.period_start.strftime('%Y-%m-%d %H:%M')} ~ {report.period_end.strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## 📊 摘要",
            f"",
            f"{report.summary}",
            f"",
        ]

        # 各章节
        section_templates = {
            "health": ("💚 系统健康", self._render_health),
            "performance": ("⚡ 性能指标", self._render_performance),
            "search": ("🔍 搜索分析", self._render_search),
            "feedback": ("💬 用户反馈", self._render_feedback),
            "self_heal": ("🔧 自修复记录", self._render_heal),
            "alerts": ("🚨 告警统计", self._render_alerts),
            "tasks": ("📋 任务执行", self._render_tasks),
        }

        for key, (title, renderer) in section_templates.items():
            if key in report.sections:
                lines.append(f"## {title}")
                lines.append("")
                lines.append(renderer(report.sections[key]))
                lines.append("")

        return "\n".join(lines)

    # --- 各章节渲染方法 ---
    def _render_health(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 可用率 | {data.get('uptime_percent', 0):.1f}% |\n"
            f"| 总检查次数 | {data.get('total_checks', 0)} |\n"
            f"| 健康 | {data.get('healthy_count', 0)} |\n"
            f"| 降级 | {data.get('degraded_count', 0)} |\n"
            f"| 异常 | {data.get('unhealthy_count', 0)} |\n"
        )

    def _render_performance(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总请求 | {data.get('total_requests', 0)} |\n"
            f"| 平均延迟 | {data.get('avg_latency_ms', 0):.0f}ms |\n"
            f"| P95 延迟 | {data.get('p95_latency_ms', 0):.0f}ms |\n"
            f"| P99 延迟 | {data.get('p99_latency_ms', 0):.0f}ms |\n"
            f"| 错误率 | {data.get('error_rate', 0):.2%} |\n"
            f"| 峰值 QPS | {data.get('qps_peak', 0)} |\n"
        )

    def _render_search(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总搜索次数 | {data.get('total_searches', 0)} |\n"
            f"| 独立查询数 | {data.get('unique_queries', 0)} |\n"
            f"| 平均结果数 | {data.get('avg_results', 0):.1f} |\n"
            f"| 空结果率 | {data.get('empty_result_rate', 0):.1%} |\n"
            f"| 缓存命中率 | {data.get('cache_hit_rate', 0):.1%} |\n"
        )

    def _render_feedback(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总反馈 | {data.get('total_feedbacks', 0)} |\n"
            f"| 有用 | {data.get('useful_count', 0)} |\n"
            f"| 无用 | {data.get('useless_count', 0)} |\n"
            f"| 满意度 | {data.get('satisfaction_rate', 0):.1%} |\n"
        )

    def _render_heal(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总执行次数 | {data.get('total_actions', 0)} |\n"
            f"| 成功 | {data.get('success_count', 0)} |\n"
            f"| 失败 | {data.get('failed_count', 0)} |\n"
            f"| 跳过 | {data.get('skipped_count', 0)} |\n"
        )

    def _render_alerts(self, data: dict) -> str:
        severity = data.get("by_severity", {})
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总告警 | {data.get('total_alerts', 0)} |\n"
            f"| Critical | {severity.get('critical', 0)} |\n"
            f"| Warning | {severity.get('warning', 0)} |\n"
            f"| 平均恢复时间 | {data.get('avg_resolution_time_s', 0):.0f}s |\n"
        )

    def _render_tasks(self, data: dict) -> str:
        return (
            f"| 指标 | 值 |\n"
            f"|------|----|\n"
            f"| 总执行次数 | {data.get('total_runs', 0)} |\n"
            f"| 成功率 | {data.get('success_rate', 0):.1%} |\n"
            f"| 平均耗时 | {data.get('avg_duration_s', 0):.1f}s |\n"
        )
```

---

## 三、经络系统增强

在现有 Signal Bus 基础上增加自运转系统所需的信号类型：

```python
# src/autonomous/signals.py

from enum import Enum


class AutonomousSignalType(Enum):
    """自运转系统信号类型（扩展）"""
    # 继承原有
    HEARTBEAT = "heartbeat"
    ALERT = "alert"
    DATA = "data"
    COMMAND = "command"

    # 新增
    SYNC = "sync"               # 数据同步信号
    HEAL = "heal"               # 自修复信号
    REPORT = "report"           # 报告信号
    METRIC = "metric"           # 指标信号
    SCHEDULE = "schedule"       # 调度信号


# 信号路由规则
SIGNAL_ROUTES = {
    # 告警信号 → 自修复引擎
    "ALERT": ["selfhealer.handle_alert"],
    # 同步信号 → 数据同步模块
    "SYNC": ["datasync.handle_sync_event"],
    # 指标信号 → 告警规则引擎
    "METRIC": ["monitor.alert_engine.evaluate"],
    # 修复信号 → 通知 + 日志
    "HEAL": ["reporter.log_heal_event"],
    # 调度信号 → 调度器
    "SCHEDULE": ["scheduler.handle_schedule_event"],
}
```

---

## 四、数据库设计

### 4.1 SQLite 表结构

```sql
-- ==============================
-- 自运转系统数据库: data/autonomous/autonomous.db
-- ==============================

-- 调度器：任务定义
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    func_path       TEXT NOT NULL,
    trigger_type    TEXT NOT NULL DEFAULT 'interval',
    trigger_config  TEXT NOT NULL DEFAULT '{}',  -- JSON
    priority        INTEGER NOT NULL DEFAULT 2,
    retry_policy    TEXT NOT NULL DEFAULT '{}',  -- JSON
    depends_on      TEXT NOT NULL DEFAULT '[]',  -- JSON array
    timeout_s       INTEGER NOT NULL DEFAULT 300,
    enabled         INTEGER NOT NULL DEFAULT 1,
    tags            TEXT NOT NULL DEFAULT '[]',  -- JSON array
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 调度器：任务执行记录
CREATE TABLE IF NOT EXISTS job_runs (
    run_id          TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TEXT,
    finished_at     TEXT,
    duration_s      REAL DEFAULT 0,
    attempt         INTEGER DEFAULT 1,
    error           TEXT,
    result_summary  TEXT,
    output_artifacts TEXT DEFAULT '[]',  -- JSON array
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
CREATE INDEX idx_job_runs_job_id ON job_runs(job_id);
CREATE INDEX idx_job_runs_status ON job_runs(status);
CREATE INDEX idx_job_runs_created ON job_runs(created_at);

-- 数据同步：同步检查点
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    source_id       TEXT PRIMARY KEY,
    source_name     TEXT,
    source_type     TEXT NOT NULL,
    config          TEXT NOT NULL DEFAULT '{}',  -- JSON
    last_sync_at    TEXT,
    last_cursor     TEXT,
    last_checksum   TEXT,
    items_synced    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'idle',
    enabled         INTEGER DEFAULT 1,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 监控：健康检查记录
CREATE TABLE IF NOT EXISTS health_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    component       TEXT NOT NULL,
    status          TEXT NOT NULL,
    message         TEXT,
    latency_ms      REAL DEFAULT 0,
    details         TEXT DEFAULT '{}',  -- JSON
    checked_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_health_component ON health_reports(component);
CREATE INDEX idx_health_checked ON health_reports(checked_at);

-- 监控：告警记录
CREATE TABLE IF NOT EXISTS alerts (
    alert_id        TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    severity        TEXT NOT NULL,
    title           TEXT NOT NULL,
    message         TEXT,
    metric_value    TEXT,
    threshold       TEXT,
    fired_at        TEXT NOT NULL,
    resolved_at     TEXT,
    status          TEXT DEFAULT 'firing',  -- firing | resolved | suppressed
    auto_heal_action TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_fired ON alerts(fired_at);

-- 自修复：执行记录
CREATE TABLE IF NOT EXISTS heal_executions (
    execution_id    TEXT PRIMARY KEY,
    action_id       TEXT NOT NULL,
    status          TEXT NOT NULL,
    trigger         TEXT,
    started_at      TEXT,
    finished_at     TEXT,
    result          TEXT,
    error           TEXT,
    rolled_back     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_heal_action ON heal_executions(action_id);
CREATE INDEX idx_heal_created ON heal_executions(created_at);

-- 报告：报告存储
CREATE TABLE IF NOT EXISTS reports (
    report_id       TEXT PRIMARY KEY,
    report_type     TEXT NOT NULL,
    title           TEXT NOT NULL,
    period_start    TEXT,
    period_end      TEXT,
    generated_at    TEXT NOT NULL,
    sections        TEXT NOT NULL DEFAULT '{}',  -- JSON
    summary         TEXT,
    format          TEXT DEFAULT 'markdown',
    file_path       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_generated ON reports(generated_at);

-- 指标时序数据（轻量级，替代完整 TSDB）
CREATE TABLE IF NOT EXISTS metrics_timeseries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name     TEXT NOT NULL,
    value           REAL NOT NULL,
    labels          TEXT DEFAULT '{}',  -- JSON
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_metrics_name ON metrics_timeseries(metric_name);
CREATE INDEX idx_metrics_recorded ON metrics_timeseries(recorded_at);

-- 事件日志（统一事件流）
CREATE TABLE IF NOT EXISTS event_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,       -- signal_type
    source          TEXT NOT NULL,       -- 模块名
    priority        TEXT DEFAULT 'NORMAL',
    payload         TEXT NOT NULL DEFAULT '{}',  -- JSON
    processed       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_events_type ON event_log(event_type);
CREATE INDEX idx_events_created ON event_log(created_at);
CREATE INDEX idx_events_processed ON event_log(processed);
```

---

## 五、配置文件设计

### 5.1 主配置文件

```yaml
# config/autonomous.yaml

# ==============================
# 伏羲自运转系统配置
# ==============================

# 全局开关
autonomous:
  enabled: true
  log_level: INFO
  db_path: data/autonomous/autonomous.db
  event_retention_days: 30      # 事件日志保留天数
  health_report_retention_days: 90

# 调度器配置
scheduler:
  enabled: true
  check_interval_s: 1           # 调度检查间隔
  max_concurrent_jobs: 5        # 最大并发任务数
  default_timeout_s: 300
  default_retry:
    max_retries: 3
    initial_delay_s: 10
    backoff_factor: 2.0

  # 预置任务
  jobs:
    - job_id: health_check
      name: 系统健康检查
      func_path: src.autonomous.monitor.checker:run_health_check
      trigger: { type: interval, seconds: 60 }
      priority: 0  # CRITICAL
      timeout_s: 30

    - job_id: metrics_collect
      name: 指标采集
      func_path: src.autonomous.monitor.collector:collect_metrics
      trigger: { type: interval, seconds: 30 }
      priority: 1  # HIGH

    - job_id: plugin_sync
      name: 插件源同步
      func_path: src.autonomous.datasync.sync:sync_all_plugins
      trigger: { type: cron, cron: "0 2 * * *" }
      priority: 2  # NORMAL
      timeout_s: 600
      retry: { max_retries: 2, initial_delay_s: 60 }

    - job_id: kb_incremental_update
      name: 知识库增量更新
      func_path: src.autonomous.datasync.sync:incremental_kb_update
      trigger: { type: cron, cron: "0 3 * * *" }
      priority: 2
      timeout_s: 1800
      depends_on: [plugin_sync]

    - job_id: cache_refresh
      name: 缓存刷新
      func_path: src.autonomous.datasync.cache:refresh_all_caches
      trigger: { type: interval, seconds: 3600 }
      priority: 3  # LOW

    - job_id: data_consistency_check
      name: 数据一致性校验
      func_path: src.autonomous.datasync.consistency:run_full_check
      trigger: { type: cron, cron: "0 5 * * *" }
      priority: 2
      timeout_s: 900

    - job_id: self_heal_scan
      name: 自修复扫描
      func_path: src.autonomous.selfhealer.scanner:scan_and_heal
      trigger: { type: interval, seconds: 120 }
      priority: 1

    - job_id: report_daily
      name: 日报生成
      func_path: src.autonomous.reporter.generator:generate_daily_report
      trigger: { type: cron, cron: "0 8 * * *" }
      priority: 2

    - job_id: report_weekly
      name: 周报生成
      func_path: src.autonomous.reporter.generator:generate_weekly_report
      trigger: { type: cron, cron: "0 9 * * 1" }
      priority: 2

    - job_id: log_cleanup
      name: 日志清理
      func_path: src.autonomous.selfhealer.actions:cleanup_old_logs
      trigger: { type: cron, cron: "0 4 * * 0" }
      priority: 3
      params: { max_age_days: 7 }

# 数据同步配置
datasync:
  enabled: true
  sources:
    - source_id: local_docs
      name: 本地文档目录
      type: local
      config:
        path: "F:\\公司知识平台\\传入数据\\原始文件"
        pattern: "*.*"
        watch_mode: false  # false = 定时扫描，true = 文件监控
      sync_interval_s: 3600

    - source_id: mcp_tools_github
      name: MCP 工具仓库
      type: github
      config:
        owner: "your-org"
        repo: "mcp-tools"
        path: "tools/"
        token_env: "GITHUB_TOKEN"  # 从环境变量读取
      sync_interval_s: 86400

  cache_strategies:
    semantic_cache:
      ttl_s: 1800
      refresh_interval_s: 900
      max_size: 10000
      eviction: lru
    search_cache:
      ttl_s: 600
      refresh_interval_s: 300
      max_size: 5000
    graph_cache:
      ttl_s: 3600
      refresh_interval_s: 1800
    plugin_metadata:
      ttl_s: 7200
      refresh_interval_s: 3600

# 监控配置
monitor:
  enabled: true

  # 健康检查目标
  health_checks:
    - name: kb_server
      type: http
      url: http://localhost:8080/api/health
      timeout_s: 10
      expected_status: 200

    - name: chromadb
      type: http
      url: http://localhost:8000/api/v1/heartbeat
      timeout_s: 10

    - name: redis
      type: tcp
      host: localhost
      port: 6379
      timeout_s: 5

    - name: ollama
      type: http
      url: http://172.25.30.200:11434/api/tags
      timeout_s: 10

    - name: embedder_server
      type: http
      url: http://172.25.30.200:8081/health
      timeout_s: 10

    - name: rerank_proxy
      type: http
      url: http://172.25.30.16:8091/health
      timeout_s: 10

    - name: disk_space
      type: disk
      path: /
      min_free_gb: 5

  # 告警规则
  alert_rules:
    - rule_id: cpu_high
      name: CPU 使用率过高
      metric: cpu_percent
      condition: "> 90"
      duration_s: 60
      severity: warning
      cooldown_s: 300
      auto_heal_action: throttle_requests

    - rule_id: mem_high
      name: 内存使用率过高
      metric: memory_percent
      condition: "> 85"
      duration_s: 30
      severity: warning
      cooldown_s: 300
      auto_heal_action: clear_cache

    - rule_id: disk_low
      name: 磁盘空间不足
      metric: disk_free_gb
      condition: "< 5"
      duration_s: 0
      severity: critical
      cooldown_s: 600
      auto_heal_action: cleanup_logs

    - rule_id: api_error_rate
      name: API 5xx 错误率过高
      metric: error_rate_5xx
      condition: "> 0.1"
      duration_s: 120
      severity: critical
      cooldown_s: 600
      auto_heal_action: restart_service

    - rule_id: api_latency_p99
      name: API P99 延迟过高
      metric: latency_p99_ms
      condition: "> 5000"
      duration_s: 60
      severity: warning
      cooldown_s: 300
      auto_heal_action: clear_cache

    - rule_id: db_connection_lost
      name: 数据库连接丢失
      metric: db_healthy
      condition: "== 0"
      duration_s: 0
      severity: critical
      cooldown_s: 300
      auto_heal_action: rebuild_pool

    - rule_id: vector_store_empty
      name: 向量库为空
      metric: vector_chunks
      condition: "== 0"
      duration_s: 0
      severity: critical
      cooldown_s: 3600
      auto_heal_action: rebuild_vectors

    - rule_id: llm_timeout_rate
      name: LLM 超时率过高
      metric: llm_timeout_rate
      condition: "> 0.3"
      duration_s: 120
      severity: warning
      cooldown_s: 600
      auto_heal_action: switch_llm_fallback

# 自修复配置
selfhealer:
  enabled: true
  max_concurrent_heals: 3

  actions:
    - action_id: restart_service
      name: 服务重启
      handler: src.autonomous.selfhealer.actions:restart_kb_server
      max_per_hour: 3
      cooldown_s: 120
      estimated_duration_s: 30

    - action_id: rebuild_pool
      name: 连接池重建
      handler: src.autonomous.selfhealer.actions:rebuild_db_pool
      max_per_hour: 5
      cooldown_s: 60

    - action_id: clear_cache
      name: 缓存清理
      handler: src.autonomous.selfhealer.actions:clear_all_caches
      max_per_hour: 10
      cooldown_s: 30

    - action_id: cleanup_logs
      name: 日志清理
      handler: src.autonomous.selfhealer.actions:cleanup_old_logs
      max_per_hour: 2
      cooldown_s: 3600
      params: { max_age_days: 7 }

    - action_id: rebuild_vectors
      name: 向量索引重建
      handler: src.autonomous.selfhealer.actions:trigger_vector_rebuild
      max_per_hour: 1
      cooldown_s: 3600
      requires_confirmation: false  # 自动执行

    - action_id: throttle_requests
      name: 请求限流
      handler: src.autonomous.selfhealer.actions:throttle_requests
      max_per_hour: 3
      cooldown_s: 300
      params: { reduction_percent: 50 }
      rollback_action: src.autonomous.selfhealer.actions:restore_throttle

    - action_id: switch_llm_fallback
      name: LLM 降级切换
      handler: src.autonomous.selfhealer.actions:switch_to_fallback_llm
      max_per_hour: 3
      cooldown_s: 600
      rollback_action: src.autonomous.selfhealer.actions:restore_primary_llm

# 报告配置
reporter:
  enabled: true
  output_dir: data/autonomous/reports
  format: markdown  # markdown | json

  daily:
    enabled: true
    cron: "0 8 * * *"    # 每天 08:00
    timezone: Asia/Shanghai

  weekly:
    enabled: true
    cron: "0 9 * * 1"    # 每周一 09:00
    timezone: Asia/Shanghai

  # 报告推送（可选）
  notify:
    enabled: false
    channel: signal_bus    # signal_bus | file | webhook
    webhook_url: ""        # webhook 模式下的回调地址
```

---

## 六、目录结构

```
src/autonomous/
├── __init__.py
├── engine.py                   # 自运转引擎入口
├── signals.py                  # 信号类型和路由定义
│
├── scheduler/                  # 调度器模块
│   ├── __init__.py
│   ├── engine.py               # SchedulerEngine
│   ├── store.py                # JobStore (SQLite 持久化)
│   └── executor.py             # 任务执行器
│
├── datasync/                   # 数据同步模块
│   ├── __init__.py
│   ├── manager.py              # DataSyncManager
│   ├── plugin_sync.py          # 插件源同步
│   ├── knowledge_sync.py       # 知识库增量同步
│   ├── cache_strategy.py       # 缓存策略
│   └── consistency.py          # 一致性校验
│
├── monitor/                    # 监控模块
│   ├── __init__.py
│   ├── engine.py               # MonitorEngine
│   ├── checker.py              # HealthChecker
│   ├── collector.py            # MetricsCollector
│   ├── alert_engine.py         # AlertEngine
│   └── alert_rules.py          # 预置告警规则
│
├── selfhealer/                 # 自修复模块
│   ├── __init__.py
│   ├── engine.py               # SelfHealerEngine
│   ├── safety.py               # SafetyGuard
│   ├── scanner.py              # 主动扫描
│   └── actions/                # 修复动作实现
│       ├── __init__.py
│       ├── service.py          # 服务重启/限流
│       ├── cache.py            # 缓存操作
│       ├── database.py         # 数据库操作
│       └── llm.py              # LLM 切换
│
└── reporter/                   # 报告模块
    ├── __init__.py
    ├── engine.py               # ReportEngine
    ├── generator.py            # ReportGenerator
    ├── aggregator.py           # DataAggregator
    └── templates/              # 报告模板
        ├── daily.md
        └── weekly.md

config/
└── autonomous.yaml             # 自运转系统配置

data/autonomous/
├── autonomous.db               # SQLite 数据库
└── reports/                    # 生成的报告
```

---

## 七、部署方案

### 7.1 集成方式：内嵌式（推荐）

自运转系统作为 kb-server 的子模块运行，不增加额外服务。

```
┌──────────────────────────────────────────┐
│              kb-server (:8080)            │
│                                          │
│  ┌─────────────────────────────────────┐ │
│  │         FastAPI App                  │ │
│  │  ┌──────────┐  ┌───────────────┐   │ │
│  │  │ API层    │  │ Autonomous    │   │ │
│  │  │ (现有)   │  │ Engine (新)   │   │ │
│  │  └──────────┘  └───────┬───────┘   │ │
│  │                        │            │ │
│  │  ┌─────────────────────┼──────────┐ │ │
│  │  │     经络系统 (Signal Bus)       │ │ │
│  │  └─────────────────────┼──────────┘ │ │
│  │                        │            │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ │ │
│  │  │Scheduler│ │Monitor │ │Healer  │ │ │
│  │  └────────┘ └────────┘ └────────┘ │ │
│  │  ┌────────┐ ┌────────┐            │ │
│  │  │DataSync│ │Reporter│            │ │
│  │  └────────┘ └────────┘            │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

#### 启动集成

```python
# src/core/startup.py 中添加

async def init_autonomous_engine(app):
    """初始化自运转引擎"""
    from src.autonomous.engine import AutonomousEngine

    engine = AutonomousEngine(config_path="config/autonomous.yaml")
    await engine.initialize()
    await engine.start()

    # 挂载到 app state
    app.state.autonomous_engine = engine

    # 注册清理钩子
    @app.on_event("shutdown")
    async def shutdown_autonomous():
        await engine.stop()

    logger.info("[Startup] 自运转引擎已启动")
```

#### 新增 API 端点

```python
# src/autonomous/api.py

# 自运转系统 API
GET  /api/autonomous/status          — 系统状态概览
GET  /api/autonomous/health          — 健康检查详情
GET  /api/autonomous/metrics         — 实时指标
GET  /api/autonomous/alerts          — 告警列表
POST /api/autonomous/alerts/{id}/ack — 确认告警
GET  /api/autonomous/jobs            — 任务列表
POST /api/autonomous/jobs/{id}/run   — 手动触发任务
GET  /api/autonomous/jobs/{id}/runs  — 任务执行历史
GET  /api/autonomous/heal/history    — 修复历史
POST /api/autonomous/heal/{action_id}— 手动触发修复
GET  /api/autonomous/reports         — 报告列表
GET  /api/autonomous/reports/{id}    — 报告详情
POST /api/autonomous/reports/generate— 手动生成报告
GET  /api/autonomous/sync/status     — 同步状态
POST /api/autonomous/sync/{source_id}— 手动触发同步
```

### 7.2 Docker Compose 扩展

在现有 `docker-compose.yml` 中无需新增容器。自运转系统内嵌在 fuxi-server 中，只需挂载配置：

```yaml
# docker-compose.yml 追加

  fuxi-server:
    # ... 现有配置 ...
    volumes:
      - fuxi-data:/app/data
      - ./config/autonomous.yaml:/app/config/autonomous.yaml:ro  # 新增
    environment:
      # ... 现有环境变量 ...
      - FUXI_AUTONOMOUS_ENABLED=${FUXI_AUTONOMOUS_ENABLED:-true}  # 新增
```

### 7.3 三台机器分工

| 机器 | 自运转组件 | 说明 |
|------|-----------|------|
| 172.25.30.200 (服务器) | 全部 5 个模块 | 主运行环境，与 kb-server 一起 |
| 172.25.30.16 (装载机) | 健康检查代理 | 监控 local_receiver/kb_daemon/rerank_proxy |
| 172.25.30.10 (本机) | 报告推送接收 | 接收日报/周报推送 |

---

## 八、实施路线图

### Phase 1：基础框架（1-2 周）
- [ ] 搭建 `src/autonomous/` 目录结构
- [ ] 实现 SchedulerEngine + SQLite 持久化
- [ ] 实现经络系统信号扩展
- [ ] 配置文件加载
- [ ] 集成到 kb-server 启动流程

### Phase 2：监控与告警（1-2 周）
- [ ] 实现 HealthChecker（HTTP/TCP/Disk 检查）
- [ ] 实现 MetricsCollector（系统 + 应用指标）
- [ ] 实现 AlertEngine（规则评估 + 告警触发）
- [ ] 接入现有 Prometheus 指标

### Phase 3：自修复（1 周）
- [ ] 实现 SelfHealerEngine + SafetyGuard
- [ ] 实现核心修复动作（缓存清理、连接池重建等）
- [ ] 与告警引擎联动

### Phase 4：数据同步（1-2 周）
- [ ] 实现 KnowledgeSync（文件变更扫描 + 增量入库）
- [ ] 实现 CacheStrategy
- [ ] 实现 ConsistencyChecker
- [ ] 插件源同步（按需）

### Phase 5：报告系统（1 周）
- [ ] 实现 DataAggregator
- [ ] 实现 ReportGenerator（日报 + 周报）
- [ ] Markdown 渲染 + 文件输出
- [ ] API 端点

### Phase 6：管理界面（可选，2 周）
- [ ] 自运转仪表盘（前端页面）
- [ ] 告警可视化
- [ ] 任务管理界面

---

## 九、与现有系统的集成点

| 现有模块 | 集成方式 | 说明 |
|----------|----------|------|
| `taiyin/metrics.py` | 数据源 | 监控模块读取现有 Prometheus 指标 |
| `taiyin/monitor.py` | 扩展 | 在现有错误处理基础上增加告警 |
| `taiyin/audit.py` | 数据源 | 报告模块聚合审计日志 |
| 经络系统 | 扩展 | 新增信号类型和路由规则 |
| `core/startup.py` | 集成 | 在启动流程中初始化自运转引擎 |
| ChromaDB | 监控目标 | 一致性校验 + 健康检查 |
| Redis | 缓存策略 | 缓存刷新 + 任务队列 |
| SQLite FTS | 一致性校验 | 向量库 vs FTS 数据对齐 |

---

*文档结束。下一步：确认方案后进入 Phase 1 实施。*
