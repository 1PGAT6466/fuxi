# 伏羲 RAG 4.0 部署指南

## 环境要求

- Python 3.11+
- SQLite 3.38+
- 内存: 4GB+
- 磁盘: 10GB+

## 安装步骤

### 1. 克隆代码

```bash
git clone <repo-url>
cd 伏羲-v1.44
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置以下变量：
# MIMO_API_KEY=your_api_key
# JWT_SECRET=your_secret
# KB_PORT=8080
```

### 4. 初始化数据库

```bash
python -c "from src.db.memory_store import get_store; get_store()"
```

### 5. 启动服务

```bash
python -m src.server
```

## 部署拓扑

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   装载机         │     │   主服务         │     │   会话服务       │
│  172.25.30.16   │────▶│  172.25.30.200  │◀────│  172.25.30.10   │
│   :8090         │     │   :8080         │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Feature Flag 部署策略

### Phase 1: 基础部署
```bash
# 所有新Flag关闭
shaoyang_sag_extract=false
taiyang_multi_hop=false
taiyang_seed_score=false
enhanced_pipeline=false
```

### Phase 2: 逐个开启
```bash
# Day 1: 开启SAG提取
shaoyang_sag_extract=true

# Day 2: 开启多跳检索
taiyang_multi_hop=true

# Day 3: 开启seed_score
taiyang_seed_score=true

# Day 4: 开启增强管线
enhanced_pipeline=true
```

### Phase 3: 监控
- 监控错误率 < 5%
- 监控P95延迟 < 10s
- 监控四象状态

## 回滚方案

### Level 1: 关闭Flag
```bash
# 关闭所有新Flag
shaoyang_sag_extract=false
taiyang_multi_hop=false
taiyang_seed_score=false
enhanced_pipeline=false
```

### Level 2: Git回滚
```bash
git checkout four-symbols-start
```

### Level 3: 数据恢复
```bash
# 从备份恢复data/
cp -r backup/data/ data/
```

## 监控

### Prometheus指标
```
GET /metrics
```

### 健康检查
```
GET /api/health
```

### 四象状态
```
GET /api/symbols/status
```

## 日志

- 位置: `data/logs/`
- 格式: `伏羲·内世界.log`
- 轮转: 10MB, 5个备份

## 性能优化

### SQLite优化
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;
```

### 缓存配置
- L1缓存: 200条，1小时TTL
- L2缓存: 100条，语义相似度>0.92

### 并发控制
- 少阳: Semaphore(3)
- 太阳: Semaphore(10)
- 太阴: Rate Limiting 60/分钟
