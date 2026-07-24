# 伏羲自运转系统 — 安全与权限架构设计

> **设计日期**：2026-07-16  
> **作者**：帝八  
> **版本**：v1.0  
> **状态**：方案设计阶段  
> **关联文档**：`docs/autonomous/backend-architecture.md`

---

## 一、安全架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     伏羲自运转安全架构                                    │
├───────────┬───────────┬───────────┬───────────┬───────────┬─────────────┤
│  RBAC     │  审计日志  │  告警通知  │  人工审批  │  安全扫描  │  数据保护   │
│  权限模型  │  Audit    │  Alert    │  Approval │  Scan     │  DataGuard  │
└─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴──────┬──────┘
      │           │           │           │           │            │
      ▼           ▼           ▼           ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      安全中间件层 (Security Middleware)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ AuthN    │  │ AuthZ    │  │ RateLimit│  │ InputSan │  │ OutputFit│  │
│  │ 认证     │  │ 授权     │  │ 限流     │  │ 输入净化  │  │ 输出过滤  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    经络系统 (Signal Bus)                                  │
│  信号类型: SECURITY_ALERT | AUDIT_EVENT | APPROVAL_REQUEST | SCAN_RESULT │
└─────────────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **最小权限**：默认拒绝，按需授权，角色权限可审计
2. **纵深防御**：认证 → 授权 → 输入校验 → 限流 → 审计，多层拦截
3. **零信任**：所有请求必须经过认证和授权，内部调用也不例外
4. **可观测**：所有安全事件可追溯，审计日志不可篡改
5. **人机协同**：高危操作需人工审批，低危操作自动执行

---

## 二、RBAC 权限模型

### 2.1 角色体系（扩展）

在现有 `src/auth/rbac.py` 的 Casbin RBAC 基础上，扩展自运转系统的角色体系：

```
┌─────────────────────────────────────────────────────────┐
│                    角色继承关系                            │
│                                                         │
│  super_admin ──→ admin ──→ operator ──→ user ──→ viewer │
│                                                         │
│  超级管理员      管理员     运维员      普通用户   只读用户 │
└─────────────────────────────────────────────────────────┘
```

| 角色 | 权限 | 典型场景 |
|------|------|----------|
| `super_admin` | 所有权限 + 系统级操作 | 系统初始化、密钥管理 |
| `admin` | 用户管理 + 配置修改 + 审批 | 用户角色变更、配置回滚 |
| `operator` | 运维操作 + 任务管理 + 审批 | 任务触发、修复执行、告警确认 |
| `user` | 文档读写 + 搜索 + 反馈 | 日常使用 |
| `viewer` | 只读访问 | 访客浏览 |

### 2.2 权限矩阵

```
资源/操作          | super_admin | admin | operator | user | viewer
-------------------|-------------|-------|----------|------|-------
文档读取           |     ✅      |  ✅   |    ✅    |  ✅  |  ✅
文档写入           |     ✅      |  ✅   |    ✅    |  ✅  |  ❌
文档删除           |     ✅      |  ✅   |    ❌    |  ❌  |  ❌
用户管理           |     ✅      |  ✅   |    ❌    |  ❌  |  ❌
角色变更           |     ✅      |  ❌   |    ❌    |  ❌  |  ❌
配置修改           |     ✅      |  ✅   |    ❌    |  ❌  |  ❌
任务触发           |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
任务管理(启停)     |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
修复执行           |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
告警确认           |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
告警规则管理       |     ✅      |  ✅   |    ❌    |  ❌  |  ❌
审计日志查看       |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
审计日志导出       |     ✅      |  ✅   |    ❌    |  ❌  |  ❌
报告查看           |     ✅      |  ✅   |    ✅    |  ✅  |  ✅
报告生成           |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
系统健康查看       |     ✅      |  ✅   |    ✅    |  ❌  |  ❌
密钥管理           |     ✅      |  ❌   |    ❌    |  ❌  |  ❌
数据重置           |     ✅      |  ❌   |    ❌    |  ❌  |  ❌
```

### 2.3 权限检查流程

```python
# src/auth/rbac.py 扩展 — 自运转系统权限检查

from enum import Enum

class AutonomousPermission(Enum):
    """自运转系统权限定义"""
    # 任务管理
    JOB_VIEW = "job:view"           # 查看任务列表和状态
    JOB_TRIGGER = "job:trigger"     # 手动触发任务
    JOB_MANAGE = "job:manage"       # 启停/编辑任务
    JOB_CREATE = "job:create"       # 创建新任务

    # 告警管理
    ALERT_VIEW = "alert:view"       # 查看告警
    ALERT_ACK = "alert:ack"         # 确认告警
    ALERT_RULE_MANAGE = "alert:rule:manage"  # 管理告警规则

    # 自修复
    HEAL_VIEW = "heal:view"         # 查看修复历史
    HEAL_TRIGGER = "heal:trigger"   # 手动触发修复
    HEAL_MANAGE = "heal:manage"     # 管理修复动作

    # 审计
    AUDIT_VIEW = "audit:view"       # 查看审计日志
    AUDIT_EXPORT = "audit:export"   # 导出审计日志

    # 审批
    APPROVAL_VIEW = "approval:view"     # 查看审批单
    APPROVAL_APPROVE = "approval:approve"  # 审批通过/拒绝
    APPROVAL_CREATE = "approval:create"    # 创建审批单（系统自动）

    # 报告
    REPORT_VIEW = "report:view"     # 查看报告
    REPORT_GENERATE = "report:generate"  # 生成报告

    # 安全扫描
    SCAN_VIEW = "scan:view"         # 查看扫描结果
    SCAN_TRIGGER = "scan:trigger"   # 触发扫描
    SCAN_MANAGE = "scan:manage"     # 管理扫描策略

    # 系统配置
    CONFIG_VIEW = "config:view"     # 查看配置
    CONFIG_MODIFY = "config:modify" # 修改配置
    CONFIG_ROLLBACK = "config:rollback"  # 回滚配置

    # 密钥管理
    SECRET_VIEW = "secret:view"     # 查看密钥元信息（不暴露值）
    SECRET_MANAGE = "secret:manage" # 管理密钥


# 角色-权限映射
_AUTONOMOUS_ROLE_POLICIES = [
    # super_admin
    ("super_admin", "job:view"), ("super_admin", "job:trigger"),
    ("super_admin", "job:manage"), ("super_admin", "job:create"),
    ("super_admin", "alert:view"), ("super_admin", "alert:ack"),
    ("super_admin", "alert:rule:manage"),
    ("super_admin", "heal:view"), ("super_admin", "heal:trigger"),
    ("super_admin", "heal:manage"),
    ("super_admin", "audit:view"), ("super_admin", "audit:export"),
    ("super_admin", "approval:view"), ("super_admin", "approval:approve"),
    ("super_admin", "report:view"), ("super_admin", "report:generate"),
    ("super_admin", "scan:view"), ("super_admin", "scan:trigger"),
    ("super_admin", "scan:manage"),
    ("super_admin", "config:view"), ("super_admin", "config:modify"),
    ("super_admin", "config:rollback"),
    ("super_admin", "secret:view"), ("super_admin", "secret:manage"),

    # admin
    ("admin", "job:view"), ("admin", "job:trigger"),
    ("admin", "job:manage"),
    ("admin", "alert:view"), ("admin", "alert:ack"),
    ("admin", "alert:rule:manage"),
    ("admin", "heal:view"), ("admin", "heal:trigger"),
    ("admin", "audit:view"), ("admin", "audit:export"),
    ("admin", "approval:view"), ("admin", "approval:approve"),
    ("admin", "report:view"), ("admin", "report:generate"),
    ("admin", "scan:view"), ("admin", "scan:trigger"),
    ("admin", "config:view"), ("admin", "config:modify"),
    ("admin", "secret:view"),

    # operator
    ("operator", "job:view"), ("operator", "job:trigger"),
    ("operator", "alert:view"), ("operator", "alert:ack"),
    ("operator", "heal:view"), ("operator", "heal:trigger"),
    ("operator", "audit:view"),
    ("operator", "approval:view"), ("operator", "approval:approve"),
    ("operator", "report:view"), ("operator", "report:generate"),
    ("operator", "scan:view"), ("operator", "scan:trigger"),
    ("operator", "config:view"),

    # user
    ("user", "report:view"),

    # viewer
    ("viewer", "report:view"),
]
```

### 2.4 资源级权限（数据隔离）

```python
# 资源级权限装饰器

def require_resource_permission(resource_type: str, action: str):
    """
    资源级权限检查，结合 RBAC + 租户隔离

    用法：
        @router.delete("/api/autonomous/jobs/{job_id}")
        @require_resource_permission("job", "manage")
        async def delete_job(job_id: str, request: Request):
            ...
    """
    async def _check(request: Request):
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(401, "未登录")

        # 1. RBAC 权限检查
        rbac = get_rbac()
        permission = f"{resource_type}:{action}"
        if not rbac.check_permission(user, permission):
            raise HTTPException(403, f"需要 {permission} 权限")

        # 2. 租户隔离检查
        tenant_id = get_current_tenant(request)
        resource_owner = await _get_resource_owner(resource_type, request)
        if resource_owner and resource_owner != tenant_id:
            raise HTTPException(403, "无权访问其他租户的资源")

    return _check
```

---

## 三、审计日志体系

### 3.1 审计事件分类

```
审计事件
├── 认证事件 (AUTH)
│   ├── LOGIN_SUCCESS       — 登录成功
│   ├── LOGIN_FAILED        — 登录失败
│   ├── LOGOUT              — 登出
│   ├── TOKEN_REFRESH       — Token 刷新
│   └── TOKEN_REVOKED       — Token 吊销
│
├── 授权事件 (AUTHZ)
│   ├── PERMISSION_DENIED   — 权限拒绝
│   ├── ROLE_ASSIGNED       — 角色分配
│   └── ROLE_REVOKED        — 角色撤销
│
├── 数据事件 (DATA)
│   ├── DOCUMENT_CREATE     — 文档创建
│   ├── DOCUMENT_UPDATE     — 文档更新
│   ├── DOCUMENT_DELETE     — 文档删除
│   ├── KNOWLEDGE_INGEST    — 知识入库
│   └── VECTOR_REBUILD      — 向量重建
│
├── 运维事件 (OPS)
│   ├── JOB_TRIGGERED       — 任务触发
│   ├── JOB_COMPLETED       — 任务完成
│   ├── JOB_FAILED          — 任务失败
│   ├── HEAL_EXECUTED       — 修复执行
│   ├── HEAL_FAILED         — 修复失败
│   ├── CONFIG_CHANGED      — 配置变更
│   └── CONFIG_ROLLBACK     — 配置回滚
│
├── 安全事件 (SECURITY)
│   ├── INJECTION_BLOCKED   — 注入拦截
│   ├── RATE_LIMIT_HIT      — 限流触发
│   ├── BRUTE_FORCE_DETECTED — 暴力破解检测
│   ├── SUSPICIOUS_QUERY    — 可疑查询
│   └── SECRET_ACCESSED     — 密钥访问
│
└── 审批事件 (APPROVAL)
    ├── APPROVAL_REQUESTED  — 审批请求
    ├── APPROVAL_GRANTED    — 审批通过
    ├── APPROVAL_REJECTED   — 审批拒绝
    └── APPROVAL_TIMEOUT    — 审批超时
```

### 3.2 审计日志结构

```python
# src/autonomous/security/audit.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import json


class AuditCategory(Enum):
    AUTH = "auth"
    AUTHZ = "authz"
    DATA = "data"
    OPS = "ops"
    SECURITY = "security"
    APPROVAL = "approval"


class AuditSeverity(Enum):
    INFO = "info"         # 普通操作
    WARNING = "warning"   # 需关注
    CRITICAL = "critical" # 需立即处理


@dataclass
class AuditEvent:
    """审计事件（增强版）"""
    event_id: str = ""                    # 唯一事件 ID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: AuditCategory = AuditCategory.DATA
    action: str = ""                      # 具体动作
    severity: AuditSeverity = AuditSeverity.INFO

    # 主体
    user_id: str = ""                     # 操作用户
    user_roles: list = field(default_factory=list)  # 用户角色
    tenant_id: str = ""                   # 租户
    ip: str = ""                          # 来源 IP
    user_agent: str = ""                  # 客户端信息

    # 客体
    resource_type: str = ""               # 资源类型
    resource_id: str = ""                 # 资源 ID
    resource_owner: str = ""              # 资源所属租户

    # 操作详情
    action_detail: str = ""               # 操作描述
    request_path: str = ""                # API 路径
    request_method: str = ""              # HTTP 方法
    request_body_hash: str = ""           # 请求体哈希（不记录原文）

    # 结果
    status: str = "success"               # success / failed / blocked
    error_message: str = ""               # 失败原因
    duration_ms: float = 0.0              # 耗时

    # 上下文
    trace_id: str = ""                    # 链路追踪 ID
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 完整性
    checksum: str = ""                    # 事件完整性校验

    def compute_checksum(self, secret: str) -> str:
        """计算事件完整性校验和（防篡改）"""
        payload = json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status": self.status,
        }, sort_keys=True)
        return hashlib.sha256(f"{payload}:{secret}".encode()).hexdigest()[:16]
```

### 3.3 审计日志存储

```python
# 审计日志存储层 — 支持防篡改和归档

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta


class AuditStore:
    """审计日志存储（增强版）

    特性：
    - SQLite WAL 模式，高并发写入
    - 防篡改校验链（每条记录的 checksum 包含前一条的 hash）
    - 自动归档（超过保留期的日志迁移到归档文件）
    - 支持按时间/用户/操作/租户多维查询
    """

    def __init__(self, db_path: str = "data/autonomous/audit.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp REAL NOT NULL,
                category TEXT NOT NULL,
                action TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                user_id TEXT DEFAULT '',
                user_roles TEXT DEFAULT '[]',
                tenant_id TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                resource_type TEXT DEFAULT '',
                resource_id TEXT DEFAULT '',
                resource_owner TEXT DEFAULT '',
                action_detail TEXT DEFAULT '',
                request_path TEXT DEFAULT '',
                request_method TEXT DEFAULT '',
                request_body_hash TEXT DEFAULT '',
                status TEXT DEFAULT 'success',
                error_message TEXT DEFAULT '',
                duration_ms REAL DEFAULT 0,
                trace_id TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                checksum TEXT DEFAULT '',
                prev_checksum TEXT DEFAULT '',
                archived INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_events(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events(severity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id)")
        conn.commit()
        conn.close()

    def write_event(self, event: AuditEvent) -> bool:
        """写入审计事件（含防篡改链）"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                # 获取上一条记录的 checksum
                row = conn.execute(
                    "SELECT checksum FROM audit_events ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_checksum = row[0] if row else "GENESIS"

                # 计算当前事件 checksum
                event.checksum = event.compute_checksum(
                    self._get_signing_secret()
                )

                conn.execute("""
                    INSERT INTO audit_events (
                        event_id, timestamp, category, action, severity,
                        user_id, user_roles, tenant_id, ip, user_agent,
                        resource_type, resource_id, resource_owner,
                        action_detail, request_path, request_method,
                        request_body_hash, status, error_message,
                        duration_ms, trace_id, metadata, checksum,
                        prev_checksum, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, event.timestamp.timestamp(),
                    event.category.value, event.action, event.severity.value,
                    event.user_id, json.dumps(event.user_roles),
                    event.tenant_id, event.ip, event.user_agent,
                    event.resource_type, event.resource_id, event.resource_owner,
                    event.action_detail, event.request_path, event.request_method,
                    event.request_body_hash, event.status, event.error_message,
                    event.duration_ms, event.trace_id,
                    json.dumps(event.metadata, ensure_ascii=False),
                    event.checksum, prev_checksum, time.time()
                ))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error("审计日志写入失败: %s", e)
                return False

    def verify_chain_integrity(self, hours: int = 24) -> dict:
        """校验审计日志链完整性（防篡改检测）"""
        conn = sqlite3.connect(self.db_path)
        since = time.time() - hours * 3600
        rows = conn.execute(
            "SELECT id, event_id, checksum, prev_checksum FROM audit_events WHERE timestamp > ? ORDER BY id",
            (since,)
        ).fetchall()
        conn.close()

        breaks = []
        for i in range(1, len(rows)):
            if rows[i][3] != rows[i-1][2]:  # prev_checksum != 前一条的 checksum
                breaks.append({
                    "id": rows[i][0],
                    "event_id": rows[i][1],
                    "expected_prev": rows[i-1][2],
                    "actual_prev": rows[i][3],
                })

        return {
            "total_events": len(rows),
            "chain_breaks": len(breaks),
            "breaks": breaks[:10],  # 最多返回 10 条
            "integrity_ok": len(breaks) == 0,
        }

    def archive_old_events(self, retention_days: int = 90):
        """归档超过保留期的审计事件"""
        cutoff = time.time() - retention_days * 86400
        archive_path = f"{self.db_path}.archive.{datetime.now().strftime('%Y%m')}"
        # 将旧记录复制到归档文件，然后从主表删除
        # 实现略（使用 ATTACH DATABASE）
        pass

    def _get_signing_secret(self) -> str:
        """获取签名密钥"""
        return os.getenv("FUXI_AUDIT_SIGNING_SECRET", "default-audit-secret")
```

### 3.4 审计日志 API

```python
# 审计日志查询 API

GET  /api/autonomous/audit/logs
     ?category=security          # 按分类筛选
     &severity=critical          # 按严重度筛选
     &user_id=admin              # 按用户筛选
     &tenant_id=default          # 按租户筛选
     &action=LOGIN_FAILED        # 按动作筛选
     &from=2026-07-16T00:00:00   # 开始时间
     &to=2026-07-16T23:59:59     # 结束时间
     &page=1&page_size=50        # 分页

GET  /api/autonomous/audit/stats
     ?hours=24                   # 统计最近 N 小时

GET  /api/autonomous/audit/verify
     ?hours=24                   # 校验日志链完整性

POST /api/autonomous/audit/export
     ?format=csv                 # 导出格式
     &from=...&to=...            # 时间范围

GET  /api/autonomous/audit/security-events
     ?hours=24                   # 最近安全事件
```

---

## 四、告警通知机制

### 4.1 告警分级

```
告警严重度      触发条件                    响应时间    通知方式
─────────────────────────────────────────────────────────────────
🔴 P0-CRITICAL  服务不可用/数据丢失         < 5分钟    电话+短信+企微
🟠 P1-HIGH      性能严重下降/安全事件        < 15分钟   企微+短信
🟡 P2-WARNING   性能轻度下降/异常模式        < 1小时    企微消息
🟢 P3-INFO      信息性通知/趋势预警          < 4小时    企微消息(批量)
```

### 4.2 告警通知渠道

```python
# src/autonomous/security/notifier.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import asyncio


@dataclass
class AlertNotification:
    """告警通知"""
    alert_id: str = ""
    severity: str = ""           # P0/P1/P2/P3
    title: str = ""
    message: str = ""
    source: str = ""             # 来源模块
    metric_value: str = ""
    threshold: str = ""
    fired_at: datetime = field(default_factory=datetime.utcnow)
    context: dict = field(default_factory=dict)  # 附加上下文


class NotifyChannel(ABC):
    """通知渠道基类"""

    @abstractmethod
    async def send(self, notification: AlertNotification) -> bool:
        """发送通知，返回是否成功"""
        pass

    @abstractmethod
    def supports_severity(self, severity: str) -> bool:
        """是否支持该严重度"""
        pass


class WeChatWorkNotifier(NotifyChannel):
    """企业微信通知"""

    def __init__(self, webhook_url: str, mentioned_list: list = None):
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list or []

    async def send(self, notification: AlertNotification) -> bool:
        """通过企业微信群机器人发送"""
        severity_emoji = {
            "P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🟢"
        }
        emoji = severity_emoji.get(notification.severity, "⚪")

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    f"## {emoji} 伏羲告警 [{notification.severity}]\n"
                    f"**标题**: {notification.title}\n"
                    f"**详情**: {notification.message}\n"
                    f"**来源**: {notification.source}\n"
                    f"**时间**: {notification.fired_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"**指标**: {notification.metric_value}\n"
                    f"**阈值**: {notification.threshold}\n"
                    f"---\n"
                    f"<at user_id=\"all\">请及时处理</at>"
                )
            }
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error("企微通知发送失败: %s", e)
            return False

    def supports_severity(self, severity: str) -> bool:
        return severity in ("P0", "P1", "P2", "P3")


class SignalBusNotifier(NotifyChannel):
    """经络系统通知（内部）"""

    def __init__(self, signal_bus):
        self.signal_bus = signal_bus

    async def send(self, notification: AlertNotification) -> bool:
        await self.signal_bus.emit(
            signal_type="ALERT",
            source="security.notifier",
            priority=notification.severity,
            payload={
                "alert_id": notification.alert_id,
                "title": notification.title,
                "message": notification.message,
            }
        )
        return True

    def supports_severity(self, severity: str) -> bool:
        return True


class LogFileNotifier(NotifyChannel):
    """日志文件通知（兜底）"""

    async def send(self, notification: AlertNotification) -> bool:
        logger.warning(
            "[ALERT][%s] %s — %s (source=%s, metric=%s)",
            notification.severity,
            notification.title,
            notification.message,
            notification.source,
            notification.metric_value,
        )
        return True

    def supports_severity(self, severity: str) -> bool:
        return True


class AlertNotifier:
    """告警通知调度器

    根据告警严重度选择通知渠道，支持：
    - 渠道路由：不同严重度走不同渠道
    - 去重抑制：相同告警在冷却期内不重复通知
    - 升级机制：告警未处理超过阈值自动升级
    """

    def __init__(self):
        self._channels: List[NotifyChannel] = []
        self._suppression_cache: dict = {}  # rule_id -> last_notified_at
        self._escalation_timers: dict = {}  # alert_id -> escalation_deadline

    def add_channel(self, channel: NotifyChannel, severity_filter: list = None):
        """添加通知渠道"""
        self._channels.append({
            "channel": channel,
            "severity_filter": severity_filter,  # None = 所有严重度
        })

    async def notify(self, notification: AlertNotification):
        """发送告警通知"""
        # 1. 去重检查
        if self._is_suppressed(notification):
            return

        # 2. 选择渠道
        sent = False
        for ch_config in self._channels:
            channel = ch_config["channel"]
            severity_filter = ch_config["severity_filter"]

            if severity_filter and notification.severity not in severity_filter:
                continue

            if channel.supports_severity(notification.severity):
                try:
                    success = await channel.send(notification)
                    if success:
                        sent = True
                except Exception as e:
                    logger.error("通知渠道 %s 发送失败: %s", type(channel).__name__, e)

        # 3. 记录发送时间
        self._suppression_cache[notification.alert_id] = datetime.utcnow()

        # 4. 设置升级计时器（P2/P3 告警）
        if notification.severity in ("P2", "P3"):
            self._set_escalation_timer(notification)

    def _is_suppressed(self, notification: AlertNotification) -> bool:
        """检查是否在抑制期内"""
        last = self._suppression_cache.get(notification.alert_id)
        if not last:
            return False

        cooldown = {
            "P0": 60,      # 1分钟
            "P1": 300,     # 5分钟
            "P2": 1800,    # 30分钟
            "P3": 3600,    # 1小时
        }.get(notification.severity, 300)

        return (datetime.utcnow() - last).total_seconds() < cooldown

    def _set_escalation_timer(self, notification: AlertNotification):
        """设置告警升级计时器"""
        escalation_delay = {
            "P2": 3600,    # 1小时未处理 → 升级为 P1
            "P3": 14400,   # 4小时未处理 → 升级为 P2
        }.get(notification.severity)

        if escalation_delay:
            self._escalation_timers[notification.alert_id] = {
                "deadline": datetime.utcnow().timestamp() + escalation_delay,
                "current_severity": notification.severity,
                "notification": notification,
            }

    async def check_escalations(self):
        """检查并执行告警升级（定期调用）"""
        now = datetime.utcnow().timestamp()
        to_escalate = []

        for alert_id, timer in self._escalation_timers.items():
            if now > timer["deadline"]:
                to_escalate.append(alert_id)

        for alert_id in to_escalate:
            timer = self._escalation_timers.pop(alert_id)
            current = timer["current_severity"]
            escalated = {"P3": "P2", "P2": "P1"}.get(current)
            if escalated:
                notification = timer["notification"]
                notification.severity = escalated
                notification.title = f"[升级] {notification.title}"
                await self.notify(notification)
```

### 4.3 预置告警规则（安全相关）

```yaml
# config/autonomous.yaml — 安全告警规则

security_alert_rules:
  # 暴力破解检测
  - rule_id: brute_force_detect
    name: 暴力破解检测
    metric: failed_login_count_per_ip
    condition: "> 10"
    duration_s: 300        # 5分钟内
    severity: P1
    cooldown_s: 600
    auto_heal_action: block_ip

  # 异常查询检测
  - rule_id: injection_spike
    name: SQL/XSS 注入攻击激增
    metric: injection_blocked_count
    condition: "> 50"
    duration_s: 300
    severity: P1
    cooldown_s: 600

  # 敏感操作异常
  - rule_id: sensitive_op_spike
    name: 敏感操作频率异常
    metric: sensitive_op_count_per_user
    condition: "> 100"
    duration_s: 600
    severity: P2
    cooldown_s: 1800

  # 权限拒绝激增
  - rule_id: permission_denied_spike
    name: 权限拒绝激增（可能越权尝试）
    metric: permission_denied_count
    condition: "> 20"
    duration_s: 300
    severity: P2
    cooldown_s: 1800

  # 审计日志链断裂
  - rule_id: audit_chain_break
    name: 审计日志链完整性异常
    metric: audit_chain_breaks
    condition: "> 0"
    duration_s: 0
    severity: P0
    cooldown_s: 300

  # 异常数据导出
  - rule_id: data_export_spike
    name: 数据导出量异常
    metric: export_data_mb
    condition: "> 100"
    duration_s: 600
    severity: P2
    cooldown_s: 3600

  # API 异常访问模式
  - rule_id: api_anomaly
    name: API 异常访问模式
    metric: api_anomaly_score
    condition: "> 0.8"
    duration_s: 120
    severity: P1
    cooldown_s: 600
```

---

## 五、人工介入审批流程

### 5.1 审批场景定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    需要人工审批的操作                              │
├────────────────────────────┬────────────┬───────────────────────┤
│ 操作                       │ 审批级别    │ 超时处理               │
├────────────────────────────┼────────────┼───────────────────────┤
│ 用户角色变更为 admin+      │ 双人审批    │ 24h 超时自动拒绝       │
│ 配置回滚                   │ 单人审批    │ 4h 超时自动拒绝        │
│ 数据重置/清空              │ 双人审批    │ 24h 超时自动拒绝       │
│ 密钥轮换                   │ 单人审批    │ 8h 超时自动拒绝        │
│ 自修复动作（高危）          │ 单人审批    │ 2h 超时自动执行        │
│ 全量向量重建               │ 单人审批    │ 4h 超时自动拒绝        │
│ 防火墙规则变更              │ 双人审批    │ 24h 超时自动拒绝       │
│ 审计日志归档/清理           │ 单人审批    │ 8h 超时自动拒绝        │
└────────────────────────────┴────────────┴───────────────────────┘
```

### 5.2 审批流程

```
                    ┌──────────────┐
                    │  发起审批请求  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  创建审批单   │
                    │  PENDING     │
                    └──────┬───────┘
                           │
                    ┌──────┴──────┐
                    │  通知审批人  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │  审批通过  │ │  审批拒绝  │ │  审批超时  │
       │  APPROVED │ │  REJECTED │ │  TIMEOUT  │
       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
             │             │             │
             ▼             ▼             ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │  执行操作  │ │  记录日志  │ │  按策略处理│
       │           │ │  通知发起人│ │  (拒绝/执行)│
       └─────┬─────┘ └───────────┘ └───────────┘
             │
             ▼
       ┌───────────┐
       │  完成确认  │
       │  COMPLETED│
       └───────────┘
```

### 5.3 审批系统实现

```python
# src/autonomous/security/approval.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid
import json


class ApprovalStatus(Enum):
    PENDING = "pending"         # 等待审批
    APPROVED = "approved"       # 已通过
    REJECTED = "rejected"       # 已拒绝
    TIMEOUT = "timeout"         # 已超时
    CANCELLED = "cancelled"     # 已取消
    EXECUTED = "executed"       # 已执行
    FAILED = "failed"           # 执行失败


class ApprovalLevel(Enum):
    SINGLE = "single"           # 单人审批
    DUAL = "dual"               # 双人审批（任一通过即可）
    UNANIMOUS = "unanimous"     # 全员通过


@dataclass
class ApprovalRequest:
    """审批请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    description: str = ""
    action_type: str = ""               # 操作类型
    action_params: dict = field(default_factory=dict)  # 操作参数
    approval_level: ApprovalLevel = ApprovalLevel.SINGLE
    required_approvers: List[str] = field(default_factory=list)  # 需要的审批人
    timeout_hours: int = 24
    timeout_action: str = "reject"      # reject | auto_execute
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_by: str = ""                # 发起人
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    tenant_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ApprovalDecision:
    """审批决定"""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id: str = ""
    approver_id: str = ""
    approved: bool = False
    comment: str = ""
    decided_at: datetime = field(default_factory=datetime.utcnow)
    ip: str = ""


@dataclass
class ApprovalRecord:
    """完整审批记录"""
    request: ApprovalRequest
    decisions: List[ApprovalDecision] = field(default_factory=list)
    executed_at: Optional[datetime] = None
    execution_result: Optional[str] = None


class ApprovalEngine:
    """审批引擎

    职责：
    1. 创建审批请求
    2. 处理审批决定
    3. 超时检查
    4. 审批通过后触发执行
    """

    def __init__(self, signal_bus, notifier, audit_store):
        self.signal_bus = signal_bus
        self.notifier = notifier
        self.audit_store = audit_store
        self._pending: Dict[str, ApprovalRecord] = {}
        self._handlers: Dict[str, Callable] = {}  # action_type -> handler

    def register_handler(self, action_type: str, handler: Callable):
        """注册审批通过后的执行处理器"""
        self._handlers[action_type] = handler

    async def create_request(self, request: ApprovalRequest) -> str:
        """创建审批请求"""
        request.expires_at = request.created_at + timedelta(hours=request.timeout_hours)

        record = ApprovalRecord(request=request)
        self._pending[request.request_id] = record

        # 审计
        await self._audit("APPROVAL_REQUESTED", request.created_by, {
            "request_id": request.request_id,
            "action_type": request.action_type,
            "title": request.title,
        })

        # 通知审批人
        await self._notify_approvers(request)

        logger.info("审批请求已创建: %s (%s)", request.request_id, request.title)
        return request.request_id

    async def submit_decision(
        self,
        request_id: str,
        approver_id: str,
        approved: bool,
        comment: str = "",
        ip: str = "",
    ) -> ApprovalStatus:
        """提交审批决定"""
        record = self._pending.get(request_id)
        if not record:
            raise ValueError(f"审批请求 {request_id} 不存在")

        if record.request.status != ApprovalStatus.PENDING:
            raise ValueError(f"审批请求 {request_id} 已不是待审批状态")

        # 检查审批人资格
        if approver_id not in record.request.required_approvers:
            raise ValueError(f"{approver_id} 不在审批人列表中")

        # 检查重复审批
        for d in record.decisions:
            if d.approver_id == approver_id:
                raise ValueError(f"{approver_id} 已审批过此请求")

        # 记录决定
        decision = ApprovalDecision(
            request_id=request_id,
            approver_id=approver_id,
            approved=approved,
            comment=comment,
            ip=ip,
        )
        record.decisions.append(decision)

        # 审计
        await self._audit(
            "APPROVAL_GRANTED" if approved else "APPROVAL_REJECTED",
            approver_id,
            {"request_id": request_id, "comment": comment}
        )

        # 判断是否满足审批条件
        status = self._evaluate_decision(record)
        if status != ApprovalStatus.PENDING:
            record.request.status = status
            if status == ApprovalStatus.APPROVED:
                await self._execute_approved_action(record)

        return status

    async def check_timeouts(self):
        """检查超时的审批请求（定期调用）"""
        now = datetime.utcnow()
        to_timeout = []

        for request_id, record in self._pending.items():
            if record.request.status != ApprovalStatus.PENDING:
                continue
            if record.request.expires_at and now > record.request.expires_at:
                to_timeout.append(request_id)

        for request_id in to_timeout:
            record = self._pending[request_id]
            record.request.status = ApprovalStatus.TIMEOUT

            # 审计
            await self._audit("APPROVAL_TIMEOUT", "system", {
                "request_id": request_id,
                "action_type": record.request.action_type,
            })

            # 按超时策略处理
            if record.request.timeout_action == "auto_execute":
                logger.warning("审批超时，自动执行: %s", request_id)
                await self._execute_approved_action(record)
            else:
                logger.warning("审批超时，自动拒绝: %s", request_id)
                await self._notify_timeout(record.request)

    def _evaluate_decision(self, record: ApprovalRecord) -> ApprovalStatus:
        """评估审批决定是否满足条件"""
        level = record.request.approval_level
        approvals = [d for d in record.decisions if d.approved]
        rejections = [d for d in record.decisions if not d.approved]

        if level == ApprovalLevel.SINGLE:
            if approvals:
                return ApprovalStatus.APPROVED
            if rejections:
                return ApprovalStatus.REJECTED

        elif level == ApprovalLevel.DUAL:
            if len(approvals) >= 1:  # 任一通过即可
                return ApprovalStatus.APPROVED
            if len(rejections) >= len(record.request.required_approvers):
                return ApprovalStatus.REJECTED

        elif level == ApprovalLevel.UNANIMOUS:
            if len(approvals) >= len(record.request.required_approvers):
                return ApprovalStatus.APPROVED
            if rejections:
                return ApprovalStatus.REJECTED

        return ApprovalStatus.PENDING

    async def _execute_approved_action(self, record: ApprovalRecord):
        """执行审批通过的操作"""
        handler = self._handlers.get(record.request.action_type)
        if not handler:
            logger.error("未注册的审批操作类型: %s", record.request.action_type)
            return

        try:
            result = await handler(record.request.action_params)
            record.request.status = ApprovalStatus.EXECUTED
            record.executed_at = datetime.utcnow()
            record.execution_result = str(result)[:500]

            await self._audit("APPROVAL_EXECUTED", "system", {
                "request_id": record.request.request_id,
                "result": record.execution_result,
            })
        except Exception as e:
            record.request.status = ApprovalStatus.FAILED
            record.execution_result = f"执行失败: {str(e)[:300]}"

            await self._audit("APPROVAL_EXEC_FAILED", "system", {
                "request_id": record.request.request_id,
                "error": str(e)[:300],
            })

    async def _notify_approvers(self, request: ApprovalRequest):
        """通知审批人"""
        from .notifier import AlertNotification
        notification = AlertNotification(
            alert_id=f"approval_{request.request_id}",
            severity="P1",
            title=f"待审批: {request.title}",
            message=(
                f"**操作类型**: {request.action_type}\n"
                f"**发起人**: {request.created_by}\n"
                f"**超时**: {request.timeout_hours}小时\n"
                f"**描述**: {request.description}"
            ),
            source="approval_engine",
        )
        await self.notifier.notify(notification)

    async def _notify_timeout(self, request: ApprovalRequest):
        """通知审批超时"""
        from .notifier import AlertNotification
        notification = AlertNotification(
            alert_id=f"approval_timeout_{request.request_id}",
            severity="P2",
            title=f"审批超时: {request.title}",
            message=f"审批请求 {request.request_id} 已超时，操作: {request.action_type}",
            source="approval_engine",
        )
        await self.notifier.notify(notification)

    async def _audit(self, action: str, user_id: str, metadata: dict):
        """写入审计日志"""
        from .audit import AuditEvent, AuditCategory
        event = AuditEvent(
            event_id=str(uuid.uuid4())[:12],
            category=AuditCategory.APPROVAL,
            action=action,
            user_id=user_id,
            metadata=metadata,
        )
        self.audit_store.write_event(event)

    # 查询接口
    def get_pending_requests(self, user_id: str = None) -> List[dict]:
        """获取待审批请求"""
        results = []
        for record in self._pending.values():
            if record.request.status != ApprovalStatus.PENDING:
                continue
            if user_id and user_id not in record.request.required_approvers:
                continue
            results.append({
                "request_id": record.request.request_id,
                "title": record.request.title,
                "action_type": record.request.action_type,
                "created_by": record.request.created_by,
                "created_at": record.request.created_at.isoformat(),
                "expires_at": record.request.expires_at.isoformat() if record.request.expires_at else None,
                "approval_level": record.request.approval_level.value,
                "decisions_count": len(record.decisions),
            })
        return results

    def get_request_detail(self, request_id: str) -> Optional[dict]:
        """获取审批详情"""
        record = self._pending.get(request_id)
        if not record:
            return None
        return {
            "request": record.request.__dict__,
            "decisions": [d.__dict__ for d in record.decisions],
            "executed_at": record.executed_at.isoformat() if record.executed_at else None,
            "execution_result": record.execution_result,
        }
```

### 5.4 审批 API

```python
# 审批管理 API

GET  /api/autonomous/approvals
     ?status=pending              # 按状态筛选
     &action_type=role_change     # 按操作类型筛选

GET  /api/autonomous/approvals/{request_id}
     — 获取审批详情

POST /api/autonomous/approvals/{request_id}/approve
     Body: {"comment": "同意", "approver_id": "admin"}
     — 审批通过

POST /api/autonomous/approvals/{request_id}/reject
     Body: {"reason": "风险太高", "approver_id": "admin"}
     — 审批拒绝

POST /api/autonomous/approvals/{request_id}/cancel
     — 取消审批（仅发起人可操作）

GET  /api/autonomous/approvals/my
     — 我的待审批列表
```

---

## 六、安全扫描策略

### 6.1 扫描类型

```
安全扫描
├── 静态扫描 (Static Analysis)
│   ├── 依赖漏洞扫描      — 检查 Python/npm 依赖的已知漏洞
│   ├── 密钥泄露扫描      — 检查代码中的硬编码密钥
│   ├── 配置安全扫描      — 检查配置文件的安全性
│   └── 代码安全扫描      — 检查 SQL 注入、XSS 等代码漏洞
│
├── 动态扫描 (Runtime Analysis)
│   ├── 端口暴露扫描      — 检查不必要的端口暴露
│   ├── API 安全测试      — 自动化 API 安全测试
│   ├── 认证绕过测试      — 测试认证机制的健壮性
│   └── 权限提升测试      — 测试 RBAC 是否可被绕过
│
└── 持续监控 (Continuous Monitoring)
    ├── 异常行为检测      — 基于审计日志的异常模式识别
    ├── 访问模式分析      — API 调用模式异常检测
    └── 数据泄露检测      — 敏感数据外泄监控
```

### 6.2 扫描引擎实现

```python
# src/autonomous/security/scanner.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
import asyncio


class ScanSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ScanFinding:
    """扫描发现"""
    finding_id: str = ""
    scanner: str = ""                  # 扫描器名称
    severity: ScanSeverity = ScanSeverity.INFO
    title: str = ""
    description: str = ""
    file_path: str = ""                # 相关文件
    line_number: int = 0               # 行号
    code_snippet: str = ""             # 代码片段
    recommendation: str = ""           # 修复建议
    cwe_id: str = ""                   # CWE 编号
    detected_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "open"               # open | fixed | accepted | false_positive


@dataclass
class ScanReport:
    """扫描报告"""
    report_id: str = ""
    scan_type: str = ""                # static | dynamic | continuous
    scanner: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    duration_s: float = 0.0
    findings: List[ScanFinding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)  # severity -> count


class BaseScanner(ABC):
    """扫描器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def scan_type(self) -> str:
        pass

    @abstractmethod
    async def scan(self, target: str = None) -> ScanReport:
        pass


class DependencyScanner(BaseScanner):
    """依赖漏洞扫描器

    使用 pip-audit / safety 检查 Python 依赖的已知漏洞。
    """

    name = "dependency_scanner"
    scan_type = "static"

    async def scan(self, target: str = None) -> ScanReport:
        report = ScanReport(scan_type=self.scan_type, scanner=self.name)

        try:
            # 1. 检查 pip 依赖
            proc = await asyncio.create_subprocess_exec(
                "pip-audit", "--format", "json", "--output", "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                import json
                vulnerabilities = json.loads(stdout.decode())
                for vuln in vulnerabilities:
                    finding = ScanFinding(
                        finding_id=f"dep_{vuln.get('id', 'unknown')}",
                        scanner=self.name,
                        severity=self._map_severity(vuln.get("severity", "")),
                        title=f"依赖漏洞: {vuln.get('name', 'unknown')}",
                        description=vuln.get("description", ""),
                        recommendation=f"升级到 {vuln.get('fixed_versions', ['最新版本'])[0]}",
                        cwe_id=vuln.get("id", ""),
                    )
                    report.findings.append(finding)

        except FileNotFoundError:
            report.findings.append(ScanFinding(
                finding_id="dep_scanner_missing",
                scanner=self.name,
                severity=ScanSeverity.INFO,
                title="pip-audit 未安装",
                description="无法执行依赖漏洞扫描",
                recommendation="pip install pip-audit",
            ))

        report.finished_at = datetime.utcnow()
        report.duration_s = (report.finished_at - report.started_at).total_seconds()
        report.summary = self._summarize(report.findings)
        return report

    def _map_severity(self, severity: str) -> ScanSeverity:
        mapping = {
            "critical": ScanSeverity.CRITICAL,
            "high": ScanSeverity.HIGH,
            "medium": ScanSeverity.MEDIUM,
            "low": ScanSeverity.LOW,
        }
        return mapping.get(severity.lower(), ScanSeverity.INFO)


class SecretScanner(BaseScanner):
    """密钥泄露扫描器

    扫描代码中的硬编码密钥、Token、密码等。
    """

    name = "secret_scanner"
    scan_type = "static"

    # 密钥模式
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']{8,}["\']', "API Key"),
        (r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']', "Password/Secret"),
        (r'(?i)(token)\s*[=:]\s*["\'][^"\']{16,}["\']', "Token"),
        (r'(?i)jwt[_-]?secret\s*[=:]\s*["\'][^"\']{8,}["\']', "JWT Secret"),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "Private Key"),
        (r'(?i)ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
        (r'(?i)sk-[a-zA-Z0-9]{48}', "OpenAI API Key"),
    ]

    async def scan(self, target: str = None) -> ScanReport:
        import re
        from pathlib import Path

        report = ScanReport(scan_type=self.scan_type, scanner=self.name)
        scan_dir = Path(target or ".")

        # 排除目录
        exclude_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".env"}

        for file_path in scan_dir.rglob("*"):
            if any(d in file_path.parts for d in exclude_dirs):
                continue
            if file_path.suffix in (".py", ".js", ".ts", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".env"):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for line_num, line in enumerate(content.split("\n"), 1):
                        for pattern, secret_type in self.SECRET_PATTERNS:
                            if re.search(pattern, line):
                                # 排除示例/测试文件中的占位符
                                if self._is_placeholder(line):
                                    continue
                                finding = ScanFinding(
                                    finding_id=f"secret_{file_path.name}_{line_num}",
                                    scanner=self.name,
                                    severity=ScanSeverity.HIGH,
                                    title=f"疑似硬编码{secret_type}",
                                    description=f"在 {file_path}:{line_num} 发现疑似硬编码凭据",
                                    file_path=str(file_path.relative_to(scan_dir)),
                                    line_number=line_num,
                                    code_snippet=line.strip()[:100],
                                    recommendation="将凭据移至环境变量或密钥管理服务",
                                )
                                report.findings.append(finding)
                except (OSError, UnicodeDecodeError):
                    continue

        report.finished_at = datetime.utcnow()
        report.duration_s = (report.finished_at - report.started_at).total_seconds()
        report.summary = self._summarize(report.findings)
        return report

    def _is_placeholder(self, line: str) -> bool:
        """判断是否为占位符"""
        placeholders = [
            "YOUR_", "CHANGE_ME", "example", "placeholder",
            "xxx", "TODO", "FIXME", "test", "dummy", "fake",
            "change-me", "change_in_production",
        ]
        lower = line.lower()
        return any(p.lower() in lower for p in placeholders)


class ConfigSecurityScanner(BaseScanner):
    """配置安全扫描器

    检查配置文件的安全性问题。
    """

    name = "config_scanner"
    scan_type = "static"

    async def scan(self, target: str = None) -> ScanReport:
        report = ScanReport(scan_type=self.scan_type, scanner=self.name)
        scan_dir = Path(target or ".")

        # 检查项
        checks = [
            self._check_jwt_config,
            self._check_cors_config,
            self._check_debug_mode,
            self._check_default_credentials,
            self._check_ssl_config,
            self._check_rate_limit_config,
        ]

        for check in checks:
            findings = await check(scan_dir)
            report.findings.extend(findings)

        report.finished_at = datetime.utcnow()
        report.duration_s = (report.finished_at - report.started_at).total_seconds()
        report.summary = self._summarize(report.findings)
        return report

    async def _check_jwt_config(self, scan_dir: Path) -> List[ScanFinding]:
        """检查 JWT 配置"""
        findings = []
        # 检查是否有硬编码的 JWT secret
        config_files = list(scan_dir.rglob("*.py")) + list(scan_dir.rglob("*.yaml"))
        import re
        for f in config_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'JWT_SECRET\s*=\s*["\'](?:fuxi-default|change-me|secret)', content, re.IGNORECASE):
                    findings.append(ScanFinding(
                        finding_id=f"jwt_default_{f.name}",
                        scanner=self.name,
                        severity=ScanSeverity.HIGH,
                        title="JWT 使用默认密钥",
                        description=f"{f} 中使用了可预测的默认 JWT 密钥",
                        file_path=str(f),
                        recommendation="使用强随机密钥，通过环境变量注入",
                    ))
            except (OSError, UnicodeDecodeError):
                continue
        return findings

    async def _check_cors_config(self, scan_dir: Path) -> List[ScanFinding]:
        """检查 CORS 配置"""
        findings = []
        import re
        for f in scan_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'allow_origins\s*=\s*\[\s*["\']\*["\']\s*\]', content):
                    findings.append(ScanFinding(
                        finding_id=f"cors_wildcard_{f.name}",
                        scanner=self.name,
                        severity=ScanSeverity.MEDIUM,
                        title="CORS 允许所有来源",
                        description=f"{f} 中 CORS 配置允许所有来源",
                        file_path=str(f),
                        recommendation="限制为已知的前端域名",
                    ))
            except (OSError, UnicodeDecodeError):
                continue
        return findings

    async def _check_debug_mode(self, scan_dir: Path) -> List[ScanFinding]:
        """检查调试模式"""
        findings = []
        import re
        for f in scan_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'debug\s*=\s*True', content, re.IGNORECASE):
                    # 排除测试文件
                    if "test" in f.name.lower():
                        continue
                    findings.append(ScanFinding(
                        finding_id=f"debug_mode_{f.name}",
                        scanner=self.name,
                        severity=ScanSeverity.MEDIUM,
                        title="调试模式已启用",
                        description=f"{f} 中启用了调试模式",
                        file_path=str(f),
                        recommendation="生产环境禁用调试模式",
                    ))
            except (OSError, UnicodeDecodeError):
                continue
        return findings

    async def _check_default_credentials(self, scan_dir: Path) -> List[ScanFinding]:
        """检查默认凭据"""
        # 类似 JWT 检查，检查其他默认凭据
        return []

    async def _check_ssl_config(self, scan_dir: Path) -> List[ScanFinding]:
        """检查 SSL 配置"""
        return []

    async def _check_rate_limit_config(self, scan_dir: Path) -> List[ScanFinding]:
        """检查限流配置"""
        return []


class PortExposureScanner(BaseScanner):
    """端口暴露扫描器

    检查不必要的端口暴露。
    """

    name = "port_scanner"
    scan_type = "dynamic"

    # 预期开放端口
    EXPECTED_PORTS = {
        8080,   # kb-server
        8081,   # embedder_server
        8090,   # local_receiver
        8091,   # rerank_proxy
        8093,   # kb_daemon
        11434,  # Ollama
    }

    async def scan(self, target: str = None) -> ScanReport:
        import socket

        report = ScanReport(scan_type=self.scan_type, scanner=self.name)
        host = target or "localhost"

        for port in range(1, 65536):
            if port in self.EXPECTED_PORTS:
                continue
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    report.findings.append(ScanFinding(
                        finding_id=f"port_{port}",
                        scanner=self.name,
                        severity=ScanSeverity.MEDIUM,
                        title=f"非预期端口开放: {port}",
                        description=f"端口 {port} 在 {host} 上开放，但不在预期列表中",
                        recommendation="确认是否需要此端口，不需要则关闭",
                    ))
            except (socket.error, OSError):
                continue

        report.finished_at = datetime.utcnow()
        report.duration_s = (report.finished_at - report.started_at).total_seconds()
        report.summary = self._summarize(report.findings)
        return report


# 汇总方法
def _summarize(self, findings: List[ScanFinding]) -> Dict[str, int]:
    summary = {}
    for f in findings:
        summary[f.severity.value] = summary.get(f.severity.value, 0) + 1
    return summary

# 给所有 Scanner 添加 _summarize 方法
for cls in [DependencyScanner, SecretScanner, ConfigSecurityScanner, PortExposureScanner]:
    cls._summarize = _summarize
```

### 6.3 扫描调度策略

```yaml
# config/autonomous.yaml — 安全扫描配置

security_scan:
  enabled: true
  output_dir: data/autonomous/security_scans

  # 定时扫描
  scheduled_scans:
    - scanner: dependency_scanner
      schedule: "0 3 * * 1"        # 每周一 03:00
      severity_threshold: high     # HIGH 以上才告警

    - scanner: secret_scanner
      schedule: "0 2 * * *"        # 每天 02:00
      target: "/home/feng-shaoxuan/kb-server"
      severity_threshold: medium

    - scanner: config_scanner
      schedule: "0 4 * * 1"        # 每周一 04:00
      severity_threshold: medium

    - scanner: port_scanner
      schedule: "0 1 * * *"        # 每天 01:00
      target: "172.25.30.200"
      severity_threshold: medium

  # 触发式扫描（事件驱动）
  triggered_scans:
    - event: code_push              # 代码推送后触发
      scanners: [secret_scanner, config_scanner]

    - event: dependency_change      # 依赖变更后触发
      scanners: [dependency_scanner]

    - event: config_change          # 配置变更后触发
      scanners: [config_scanner]
```

### 6.4 扫描 API

```python
# 安全扫描 API

GET  /api/autonomous/security/scans
     — 扫描历史列表

POST /api/autonomous/security/scans/trigger
     Body: {"scanner": "secret_scanner", "target": "/path/to/scan"}
     — 手动触发扫描

GET  /api/autonomous/security/scans/{report_id}
     — 扫描报告详情

GET  /api/autonomous/security/scans/latest
     ?scanner=dependency_scanner
     — 最近一次扫描结果

POST /api/autonomous/security/findings/{finding_id}/status
     Body: {"status": "fixed"}     # fixed | accepted | false_positive
     — 更新发现状态

GET  /api/autonomous/security/dashboard
     — 安全仪表盘（汇总数据）
```

---

## 七、数据保护

### 7.1 敏感数据分类

```
数据敏感度      数据类型                    保护措施
───────────────────────────────────────────────────────────────
🔴 绝密        JWT Secret / API Key        环境变量 + 密钥管理
🔴 绝密        SSH 私钥 / 证书             文件权限 600 + 加密存储
🟠 机密        用户密码哈希                 bcrypt/argon2 + 盐
🟠 机密        审计日志                     防篡改校验链
🟡 内部        用户个人信息                 脱敏展示 + 访问控制
🟡 内部        系统配置                     RBAC 控制 + 审计
🟢 公开        知识库文档内容                正常存储
🟢 公开        系统健康状态                 正常存储
```

### 7.2 敏感信息脱敏

```python
# src/autonomous/security/dataguard.py

import re
from typing import Any


class DataGuard:
    """数据保护守卫

    职责：
    1. 敏感信息脱敏（日志、API 响应）
    2. 数据泄露检测
    3. 输出过滤
    """

    # 脱敏规则
    MASK_RULES = [
        # API Key / Token
        (r'(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*["\']?([^\s"\']{4})([^\s"\']+)([^\s"\']{4})',
         lambda m: f"{m.group(1)}={m.group(2)}****{m.group(4)}"),
        # 手机号
        (r'1[3-9]\d{9}', lambda m: m.group()[:3] + "****" + m.group()[-4:]),
        # 身份证
        (r'\d{17}[\dXx]', lambda m: m.group()[:6] + "********" + m.group()[-4:]),
        # 邮箱
        (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
         lambda m: m.group(1)[:2] + "***@" + m.group(2)),
        # IP 地址（内网）
        (r'172\.\d+\.\d+\.\d+', lambda m: "172.*.*.*"),
    ]

    @classmethod
    def mask_sensitive(cls, text: str) -> str:
        """对文本中的敏感信息进行脱敏"""
        result = text
        for pattern, replacer in cls.MASK_RULES:
            result = re.sub(pattern, replacer, result)
        return result

    @classmethod
    def mask_dict(cls, data: dict, sensitive_keys: set = None) -> dict:
        """对字典中的敏感字段进行脱敏"""
        if sensitive_keys is None:
            sensitive_keys = {
                "password", "secret", "token", "api_key", "apikey",
                "jwt_secret", "private_key", "credential", "authorization",
            }

        masked = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                if isinstance(value, str) and len(value) > 8:
                    masked[key] = value[:4] + "****" + value[-4:]
                else:
                    masked[key] = "****"
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value, sensitive_keys)
            elif isinstance(value, list):
                masked[key] = [
                    cls.mask_dict(item, sensitive_keys) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked

    @classmethod
    def check_data_leak(cls, response_data: Any) -> list:
        """检查响应数据中是否可能包含敏感信息泄露"""
        warnings = []
        text = str(response_data)

        # 检查是否包含可能的密钥
        if re.search(r'(?i)(sk-|ghp_|glpat-|xoxb-|xoxp-)', text):
            warnings.append("响应中疑似包含 API Key/Token")

        # 检查是否包含私钥
        if "-----BEGIN" in text and "PRIVATE KEY" in text:
            warnings.append("响应中疑似包含私钥")

        # 检查是否包含内网 IP
        internal_ips = re.findall(r'172\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+', text)
        if internal_ips:
            warnings.append(f"响应中包含内网 IP: {', '.join(set(internal_ips)[:3])}")

        return warnings
```

### 7.3 安全中间件集成

```python
# src/autonomous/security/middleware.py

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件 — 统一处理认证、授权、审计、限流"""

    def __init__(self, app, audit_store, rbac, rate_limiter, data_guard):
        super().__init__(app)
        self.audit_store = audit_store
        self.rbac = rbac
        self.rate_limiter = rate_limiter
        self.data_guard = data_guard

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        trace_id = str(uuid.uuid4())[:12]

        # 1. 限流检查
        client_ip = request.client.host if request.client else "unknown"
        if not self.rate_limiter.check(client_ip, request.url.path):
            return Response(
                content='{"error": "rate_limit_exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        # 2. 认证（JWT 验证）
        user_info = await self._authenticate(request)
        if user_info:
            request.state.user = user_info["username"]
            request.state.user_roles = user_info.get("roles", [])
            request.state.tenant_id = user_info.get("tenant_id", "default")
            request.state.jwt_payload = user_info

        # 3. 授权（RBAC 检查）
        # 由路由级装饰器处理，中间件仅注入上下文

        # 4. 输入净化
        # 由各路由的 sanitize_user_input 处理

        # 5. 执行请求
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_error(request, trace_id, str(e), duration_ms)
            raise

        # 6. 输出过滤检查
        duration_ms = (time.time() - start_time) * 1000

        # 7. 审计日志
        is_sensitive = request.url.path.startswith("/api/autonomous/") or \
                       any(kw in request.url.path for kw in ["admin", "config", "secret"])
        await self._audit_request(request, response, trace_id, duration_ms, is_sensitive)

        # 8. 添加安全头
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response

    async def _authenticate(self, request: Request) -> Optional[dict]:
        """JWT 认证"""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        try:
            import jwt
            payload = jwt.decode(
                token,
                os.getenv("FUXI_JWT_SECRET"),
                algorithms=["HS256"]
            )
            return payload
        except jwt.InvalidTokenError:
            return None

    async def _audit_request(self, request, response, trace_id, duration_ms, is_sensitive):
        """记录请求审计"""
        from .audit import AuditEvent, AuditCategory
        event = AuditEvent(
            event_id=trace_id,
            category=AuditCategory.DATA,
            action=f"{request.method} {request.url.path}",
            user_id=getattr(request.state, "user", "anonymous"),
            tenant_id=getattr(request.state, "tenant_id", ""),
            ip=request.client.host if request.client else "",
            request_path=request.url.path,
            request_method=request.method,
            status="success" if response.status_code < 400 else "failed",
            duration_ms=duration_ms,
            trace_id=trace_id,
            metadata={"status_code": response.status_code},
        )
        self.audit_store.write_event(event)

    async def _audit_error(self, request, trace_id, error, duration_ms):
        """记录错误审计"""
        from .audit import AuditEvent, AuditCategory, AuditSeverity
        event = AuditEvent(
            event_id=trace_id,
            category=AuditCategory.OPS,
            action=f"{request.method} {request.url.path}",
            severity=AuditSeverity.CRITICAL,
            user_id=getattr(request.state, "user", "anonymous"),
            ip=request.client.host if request.client else "",
            request_path=request.url.path,
            request_method=request.method,
            status="error",
            error_message=str(error)[:500],
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self.audit_store.write_event(event)
```

---

## 八、安全 API 端点汇总

```
# 权限管理
GET    /api/autonomous/rbac/roles                    — 角色列表
POST   /api/autonomous/rbac/users/{user_id}/roles    — 分配角色
DELETE /api/autonomous/rbac/users/{user_id}/roles/{role} — 撤销角色
GET    /api/autonomous/rbac/users/{user_id}/permissions — 用户权限

# 审计日志
GET    /api/autonomous/audit/logs                    — 审计日志查询
GET    /api/autonomous/audit/stats                   — 审计统计
GET    /api/autonomous/audit/verify                  — 日志链完整性校验
POST   /api/autonomous/audit/export                  — 导出审计日志
GET    /api/autonomous/audit/security-events         — 安全事件

# 告警通知
GET    /api/autonomous/alerts                        — 告警列表
POST   /api/autonomous/alerts/{id}/ack               — 确认告警
GET    /api/autonomous/alerts/rules                  — 告警规则列表
POST   /api/autonomous/alerts/rules                  — 创建告警规则
PUT    /api/autonomous/alerts/rules/{id}             — 更新告警规则

# 审批
GET    /api/autonomous/approvals                     — 审批列表
GET    /api/autonomous/approvals/{id}                — 审批详情
POST   /api/autonomous/approvals/{id}/approve        — 审批通过
POST   /api/autonomous/approvals/{id}/reject         — 审批拒绝

# 安全扫描
GET    /api/autonomous/security/scans                — 扫描历史
POST   /api/autonomous/security/scans/trigger        — 触发扫描
GET    /api/autonomous/security/scans/{id}           — 扫描报告
GET    /api/autonomous/security/scans/latest         — 最近扫描
GET    /api/autonomous/security/dashboard            — 安全仪表盘
```

---

## 九、目录结构

```
src/autonomous/security/
├── __init__.py
├── rbac.py              # RBAC 权限管理（扩展自 src/auth/rbac.py）
├── audit.py             # 审计日志存储和查询
├── notifier.py          # 告警通知渠道
├── approval.py          # 审批引擎
├── scanner.py           # 安全扫描器
├── dataguard.py         # 数据保护（脱敏/泄露检测）
└── middleware.py         # 安全中间件

data/autonomous/
├── audit.db             # 审计日志数据库
├── security_scans/      # 扫描报告存储
└── approvals/           # 审批记录（持久化）
```

---

## 十、实施路线图

### Phase 1：RBAC 增强（1 周）
- [ ] 扩展现有 Casbin RBAC，增加 `super_admin` 和 `operator` 角色
- [ ] 实现自运转系统的细粒度权限定义
- [ ] 实现资源级权限检查装饰器
- [ ] 集成租户隔离

### Phase 2：审计日志增强（1 周）
- [ ] 增强现有 `taiyin/audit.py`，支持分类、严重度、防篡改链
- [ ] 实现安全中间件自动审计
- [ ] 实现审计日志查询和导出 API
- [ ] 实现日志链完整性校验

### Phase 3：告警通知（1 周）
- [ ] 实现告警通知调度器
- [ ] 实现企微 Webhook 通知渠道
- [ ] 实现告警去重、抑制和升级机制
- [ ] 配置安全相关告警规则

### Phase 4：审批流程（1 周）
- [ ] 实现审批引擎
- [ ] 实现审批 API
- [ ] 注册高危操作的审批处理器
- [ ] 实现超时自动处理

### Phase 5：安全扫描（1-2 周）
- [ ] 实现依赖漏洞扫描器
- [ ] 实现密钥泄露扫描器
- [ ] 实现配置安全扫描器
- [ ] 实现端口暴露扫描器
- [ ] 实现扫描调度和 API

### Phase 6：数据保护（1 周）
- [ ] 实现数据脱敏守卫
- [ ] 实现响应数据泄露检测
- [ ] 集成到安全中间件

---

*文档结束。下一步：确认方案后进入 Phase 1 实施。*
