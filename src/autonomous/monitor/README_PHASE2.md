# 伏羲自运转 - 告警通知与日志分析模块

## 模块概述

Phase 2 在 Phase 1 的健康监控基础上，新增了告警通知和日志分析功能，实现了：

- **通知器 (Notifier)**: 支持企微、邮件等多种通知渠道，带模板管理和去重机制
- **日志分析器 (LogAnalyzer)**: 实时日志流分析、错误模式识别、异常检测

## 文件结构

```
src/autonomous/monitor/
├── __init__.py              # 模块导出
├── alert_engine.py          # 告警引擎
├── config.py                # 配置管理
├── health_checker.py        # 健康检查
├── log_analyzer.py          # 日志分析器 (NEW)
├── metrics_collector.py     # 指标采集
├── notifier.py              # 通知器 (NEW)
└── README.md                # 本文档
```

## 功能说明

### 1. 通知器 (notifier.py)

#### 核心功能

- **多渠道支持**: 企微 (wecom)、邮件 (email)、Webhook
- **模板管理**: 可配置的通知模板，支持变量替换
- **通知历史**: 完整的通知发送记录
- **去重机制**: 冷却期内不重复发送相同告警

#### 使用示例

```python
from src.autonomous.monitor.notifier import Notifier, NotifierConfig, NotificationChannel

# 配置
config = NotifierConfig(
    wecom_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    email_recipients=["admin@example.com"]
)

# 创建通知器
notifier = Notifier(config)

# 发送测试通知
record = await notifier.send_test_notification(
    channel=NotificationChannel.WECOM,
    message="测试通知"
)

# 发送告警通知
alert_data = {
    "alert_id": "test_001",
    "level": "P1",
    "rule_name": "CPU使用率过高",
    "current_value": 95.5,
    "threshold": 80.0,
    "message": "CPU使用率超过阈值"
}
records = await notifier.send_notification(alert_data)

# 获取通知历史
history = notifier.get_history(limit=50)
```

#### 通知模板

通知模板使用 Python 字符串格式化语法，支持以下变量：

- `{level}`: 告警级别 (P0, P1, P2, P3)
- `{level_color}`: 级别对应颜色
- `{rule_name}`: 告警规则名称
- `{current_value}`: 当前值
- `{threshold}`: 阈值
- `{message}`: 告警消息
- `{created_at}`: 创建时间
- `{timestamp}`: 当前时间

### 2. 日志分析器 (log_analyzer.py)

#### 核心功能

- **实时日志流分析**: 异步处理日志流
- **错误模式识别**: 基于正则表达式的模式匹配
- **异常检测**: 错误率突增、响应时间突增、日志量异常
- **日志聚合统计**: 多维度统计分析
- **分析报告生成**: 完整的分析报告

#### 预置分析规则

| 规则ID | 规则名称 | 类型 | 描述 | 告警级别 |
|--------|----------|------|------|----------|
| error_rate_spike | 错误率突增 | ERROR_RATE_SPIKE | 错误率突增超过50% | P1 |
| latency_spike | 响应时间突增 | LATENCY_SPIKE | 响应时间突增超过100% | P1 |
| critical_error_pattern | 严重错误模式 | PATTERN_MATCH | 匹配 FATAL/CRITICAL/OUT OF MEMORY 等 | P0 |
| database_error_pattern | 数据库错误模式 | PATTERN_MATCH | 匹配 deadlock/connection refused 等 | P1 |
| volume_anomaly | 日志量异常 | VOLUME_ANOMALY | 日志量超出正常范围 | P2 |

#### 使用示例

```python
from src.autonomous.monitor.log_analyzer import LogAnalyzer, LogEntry

# 创建分析器
analyzer = LogAnalyzer()

# 摄入日志
entry = LogEntry(
    timestamp=datetime.now(),
    level="ERROR",
    message="Database connection failed",
    source="api_server",
    metadata={"latency": 2.5}
)
analyzer.ingest_log(entry)

# 批量摄入
entries = [entry1, entry2, entry3]
analyzer.ingest_logs(entries)

# 执行分析
results = await analyzer.analyze()

# 获取统计
stats = analyzer.get_statistics(window_seconds=300)

# 获取日志模式
patterns = analyzer.get_patterns(min_count=2)

# 生成报告
report = analyzer.generate_report(window_seconds=3600)
```

## API 端点

### 通知管理

#### GET /api/ops/notifications/history

获取通知历史

**参数:**
- `channel` (可选): 通知渠道 (wecom, email, webhook)
- `status` (可选): 状态 (pending, sent, failed)
- `limit`: 返回数量 (默认 100)

**响应:**
```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "id": "alert_001_wecom_1234567890",
        "channel": "wecom",
        "template_id": "alert_wecom",
        "title": "🚨 [P1] 告警通知",
        "content": "...",
        "alert_id": "alert_001",
        "alert_level": "P1",
        "status": "sent",
        "created_at": "2026-07-16T16:00:00",
        "sent_at": "2026-07-16T16:00:01",
        "error": null
      }
    ],
    "total": 1
  },
  "message": "通知历史查询成功"
}
```

#### POST /api/ops/notifications/test

发送测试通知

**参数:**
- `channel` (必需): 通知渠道 (wecom, email, webhook)
- `message`: 测试消息 (默认: "这是一条测试通知")

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "test_wecom_1234567890",
    "channel": "wecom",
    "status": "sent",
    "created_at": "2026-07-16T16:00:00",
    "sent_at": "2026-07-16T16:00:01"
  },
  "message": "测试通知发送成功"
}
```

### 日志分析

#### GET /api/ops/logs/analysis

获取日志分析报告

**参数:**
- `window_seconds`: 分析窗口 (默认 3600)

**响应:**
```json
{
  "success": true,
  "data": {
    "report_time": "2026-07-16T16:00:00",
    "window_seconds": 3600,
    "statistics": {
      "total_count": 1000,
      "error_count": 50,
      "warning_count": 100,
      "error_rate": 5.0,
      "level_counts": {
        "INFO": 850,
        "WARNING": 100,
        "ERROR": 50
      },
      "avg_latency": 0.5,
      "p95_latency": 1.2,
      "p99_latency": 2.5
    },
    "patterns": [
      {
        "pattern": "Database connection failed",
        "count": 25,
        "first_seen": "2026-07-16T15:30:00",
        "last_seen": "2026-07-16T15:55:00"
      }
    ],
    "recent_alerts": [],
    "rules_status": [...]
  },
  "message": "日志分析报告生成成功"
}
```

#### GET /api/ops/logs/patterns

获取日志模式

**参数:**
- `min_count`: 最小匹配次数 (默认 1)

**响应:**
```json
{
  "success": true,
  "data": {
    "patterns": [
      {
        "pattern": "Database connection failed",
        "count": 25,
        "first_seen": "2026-07-16T15:30:00",
        "last_seen": "2026-07-16T15:55:00",
        "examples": ["Database connection failed: timeout", ...]
      }
    ],
    "total": 1
  },
  "message": "日志模式查询成功"
}
```

#### GET /api/ops/logs/statistics

获取日志统计

**参数:**
- `window_seconds`: 统计窗口 (默认 300)

#### GET /api/ops/logs/results

获取分析结果

**参数:**
- `rule_type` (可选): 规则类型
- `alert_level` (可选): 告警级别
- `limit`: 返回数量 (默认 100)

#### GET /api/ops/logs/rules

获取日志分析规则

## 配置说明

### 通知配置

在 `NotifierConfig` 中配置：

```python
config = NotifierConfig(
    # 企微配置
    wecom_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    wecom_mentioned_list=["@all"],
    
    # 邮件配置
    smtp_host="smtp.example.com",
    smtp_port=465,
    smtp_user="alert@example.com",
    smtp_password="password",
    email_recipients=["admin@example.com"],
    
    # 通用配置
    notification_cooldown=300,  # 通知冷却期（秒）
    max_history=1000,
    enable_async=True
)
```

### 日志分析配置

在 `MonitorConfig` 中配置：

```python
config = MonitorConfig(
    # 告警配置
    alert_check_interval=30,
    alert_cooldown=300,
    
    # 阈值配置
    api_error_rate_threshold=5.0,
    api_latency_threshold=5.0
)
```

## 集成说明

### 与告警引擎集成

```python
from src.autonomous.monitor.alert_engine import AlertEngine
from src.autonomous.monitor.notifier import Notifier
from src.autonomous.monitor.log_analyzer import LogAnalyzer

# 创建实例
alert_engine = AlertEngine()
notifier = Notifier()
log_analyzer = LogAnalyzer()

# 注册通知器到告警引擎
async def alert_callback(alert):
    alert_data = alert_engine.to_dict(alert)
    await notifier.send_notification(alert_data)

alert_engine.add_notifier(alert_callback)

# 注册告警回调到日志分析器
async def analysis_callback(result):
    if result.triggered:
        # 触发告警
        await alert_engine.evaluate({...})

log_analyzer.add_alert_callback(analysis_callback)
```

## 扩展指南

### 添加新的通知渠道

1. 继承 `BaseNotifier` 基类
2. 实现 `send()` 和 `get_channel()` 方法
3. 在 `Notifier._init_notifiers()` 中注册

### 添加新的分析规则

```python
from src.autonomous.monitor.log_analyzer import AnalysisRule, AnalysisRuleType

new_rule = AnalysisRule(
    id="custom_rule",
    name="自定义规则",
    rule_type=AnalysisRuleType.PATTERN_MATCH,
    description="自定义模式匹配",
    pattern=r"custom error pattern",
    alert_level="P1"
)

log_analyzer.add_rule(new_rule)
```

## 依赖项

- Python 3.8+
- aiohttp (可选，用于企微通知)
- aiosmtplib (可选，用于邮件通知)

## 注意事项

1. 通知渠道需要配置相应的凭据才能正常工作
2. 日志分析器需要持续接收日志才能产生有意义的分析结果
3. 通知冷却期可以防止告警风暴
4. 建议在生产环境中配置至少一种通知渠道
