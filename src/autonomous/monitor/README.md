# 伏羲健康监控模块

## 概述

健康监控模块是伏羲自运转系统的核心组件，负责系统健康检查、指标采集和告警管理。

## 功能特性

### 1. 健康检查器 (HealthChecker)
- **并行检查**: 使用 asyncio 并行检查所有服务状态
- **多维检查**: API服务、ChromaDB、Redis、磁盘空间、内存使用
- **状态分级**: healthy/degraded/unhealthy
- **历史记录**: 保留最近1000条健康检查记录

### 2. 指标采集器 (MetricsCollector)
- **系统指标**: CPU、内存、磁盘、网络、进程
- **业务指标**: QPS、延迟、错误率、活跃连接（需配置API）
- **时序存储**: SQLite存储，支持高效查询
- **数据聚合**: 支持1分钟/5分钟/1小时聚合

### 3. 告警引擎 (AlertEngine)
- **规则引擎**: 基于阈值的灵活告警规则
- **告警去重**: 相同告警在冷却期内不重复触发
- **告警抑制**: 高级别告警自动抑制低级别
- **通知接口**: 预留企微通知接口
- **历史记录**: 完整的告警历史追踪

## 预置告警规则

| 规则ID | 名称 | 指标 | 条件 | 阈值 | 级别 |
|--------|------|------|------|------|------|
| cpu_high | CPU使用率过高 | system.cpu.percent | > | 80% | P2 |
| memory_high | 内存使用率过高 | system.memory.percent | > | 85% | P2 |
| disk_high | 磁盘使用率过高 | system.disk.percent | > | 90% | P1 |
| api_latency_high | API响应时间过长 | business.latency_avg | > | 5s | P1 |
| api_error_rate_high | API错误率过高 | business.error_rate | > | 5% | P1 |
| service_unavailable | 服务不可用 | system.service.status | = | 0 | P0 |

## API 端点

### 健康检查
```
GET /api/ops/health
GET /api/ops/health/history?limit=100
```

### 指标查询
```
GET /api/ops/metrics?name=system.cpu.percent&limit=100
GET /api/ops/metrics/aggregated?name=system.cpu.percent&interval=60
```

### 告警管理
```
GET /api/ops/alerts
GET /api/ops/alerts/history
GET /api/ops/alerts/rules
POST /api/ops/alerts/rules
```

## 使用示例

### 获取系统健康状态
```bash
curl http://localhost:8080/api/ops/health
```

### 查询CPU指标
```bash
curl "http://localhost:8080/api/ops/metrics?name=system.cpu.percent&limit=10"
```

### 创建告警规则
```bash
curl -X POST http://localhost:8080/api/ops/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "id": "custom_rule",
    "name": "自定义规则",
    "metric": "custom.metric",
    "condition": "gt",
    "threshold": 100,
    "level": 2,
    "description": "自定义告警规则"
  }'
```

## 配置

通过 `MonitorConfig` 类配置监控参数：

```python
from src.autonomous.monitor import MonitorConfig

config = MonitorConfig(
    health_check_interval=30,
    metrics_collect_interval=60,
    alert_cooldown=300,
    api_base_url="http://localhost:8000",
    chromadb_url="http://localhost:8000",
    redis_url="redis://localhost:6379"
)
```

## 测试

运行测试脚本验证模块功能：

```bash
python src/autonomous/monitor/test_monitor.py
```

## 依赖

- aiohttp: 异步HTTP客户端
- psutil: 系统指标采集
- redis: Redis客户端
- sqlite3: 指标存储（Python内置）

## 文件结构

```
src/autonomous/monitor/
├── __init__.py           # 模块入口
├── config.py             # 配置类
├── health_checker.py     # 健康检查器
├── metrics_collector.py  # 指标采集器
├── alert_engine.py       # 告警引擎
├── test_monitor.py       # 测试脚本
└── README.md             # 本文档
```
