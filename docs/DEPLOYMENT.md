# 伏羲系统部署指南

## 环境要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| Python | 3.10+ | 3.11+ |
| 内存 | 4GB+ | 8GB+ |
| 磁盘 | 10GB+ | 50GB+ |
| SQLite | 3.38+ | 3.40+ |
| 操作系统 | Linux / Windows | Ubuntu 22.04 |

## 快速部署

### 1. 克隆代码

```bash
git clone <repo-url>
cd 伏羲-v1.50
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，必须配置以下变量：

```env
# LLM 配置（必填）
MIMO_API_KEY=your_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5
MIMO_TIMEOUT=60

# Rerank 服务（可选，降级使用）
SILICONFLOW_API_KEY=your_siliconflow_key
DEEPSEEK_API_KEY=your_deepseek_key

# 服务配置
KB_HOST=0.0.0.0
KB_PORT=8080
KB_ADMIN_TOKEN=change_me_in_production
KB_EMBEDDER_URL=http://localhost:8081
KB_UPLOAD_MAX_MB=200

# 代理服务
LOADER_URL=http://127.0.0.1:8090
KB_RERANK_PROXY=http://127.0.0.1:8091

# 数据目录
FUXI_DATA_DIR=data
```

### 4. 启动服务

```bash
# 开发模式
python -m uvicorn src.server:app --host 0.0.0.0 --port 8080

# 或直接运行
python src/server.py
```

### 5. 验证部署

```bash
# 健康检查
curl http://localhost:8080/api/health

# 预期响应
{
  "status": "ok",
  "version": "1.50",
  "uptime_seconds": 123
}
```

访问浏览器：
- 主页：`http://localhost:8080`
- 管理面板：`http://localhost:8080/admin`
- API 文档：`http://localhost:8080/docs`
- 默认账号：`admin` / `fuxi2024`

## 生产环境部署

### 方式一：Uvicorn 多进程

```bash
python -m uvicorn src.server:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 4 \
  --timeout-keep-alive 120 \
  --log-level info
```

### 方式二：Docker 部署

```bash
# 构建镜像
docker build -t fuxi:v1.50 .

# 运行容器
docker run -d \
  --name fuxi \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  fuxi:v1.50
```

### 方式三：Systemd 服务

创建 `/etc/systemd/system/fuxi.service`：

```ini
[Unit]
Description=Fuxi Knowledge System
After=network.target

[Service]
Type=simple
User=fuxi
WorkingDirectory=/home/fuxi/kb-server
EnvironmentFile=/home/fuxi/kb-server/.env
ExecStart=/usr/bin/python3 -m uvicorn src.server:app --host 0.0.0.0 --port 8080 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable fuxi
sudo systemctl start fuxi
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name fuxi.example.com;

    client_max_body_size 200M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /api/chat {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_read_timeout 300s;
    }
}
```

## 部署拓扑

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   装载机         │     │   主服务         │     │   会话服务       │
│  172.25.30.16   │────▶│  172.25.30.200  │◀────│  172.25.30.10   │
│   :8090         │     │   :8080         │     │                 │
│  文件上传接收    │     │  FastAPI 主服务  │     │  EasyClaw 会话   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              ┌──────────┐ ┌──────┐ ┌──────────┐
              │Embedder  │ │Ollama│ │ChromaDB  │
              │  :8081   │ │:11434│ │ 向量存储  │
              └──────────┘ └──────┘ └──────────┘
```

## 服务组件

| 服务 | 端口 | 功能 |
|------|------|------|
| kb-server | 8080 | FastAPI 主服务 |
| local_receiver | 8090 | 文件上传接收 |
| embedder_server | 8081 | BGE 文本向量化 |
| Ollama | 11434 | 本地 LLM 推理 |
| rerank_proxy | 8091 | Rerank 代理 |

## Feature Flag 部署策略

### Phase 1：基础部署（所有 Flag 关闭）

```bash
# 通过 API 或环境变量设置
shaoyang_sag_extract=false
taiyang_multi_hop=false
taiyang_seed_score=false
enhanced_pipeline=false
```

### Phase 2：逐个开启

```bash
# Day 1: 开启 SAG 提取
curl -X PUT http://localhost:8080/api/feature-flags/shaoyang_sag_extract \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"value": true}'

# Day 2: 开启多跳检索
# Day 3: 开启 seed_score
# Day 4: 开启增强管线
```

### Phase 3：监控

- 错误率 < 5%
- P95 延迟 < 10s
- 四象状态正常

## 监控

```bash
# Prometheus 指标
curl http://localhost:8080/metrics

# 健康检查
curl http://localhost:8080/api/health

# 系统统计
curl http://localhost:8080/api/system/stats

# 四象状态
curl http://localhost:8080/api/symbols/status
```

## 日志

- 位置：`data/logs/`
- 格式：`伏羲·内世界.log`
- 轮转：10MB，保留 5 个备份
- 级别：通过 `FUXI_LOG_LEVEL` 环境变量控制（DEBUG / INFO / WARNING / ERROR）

## 回滚方案

### Level 1：关闭 Feature Flag

```bash
curl -X PUT http://localhost:8080/api/feature-flags/<flag_name> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"value": false}'
```

### Level 2：Git 回滚

```bash
git checkout <previous-version-tag>
# 重启服务
```

### Level 3：数据恢复

```bash
cp -r backup/data/ data/
```

## 常见问题

### 端口被占用

```bash
# Linux
lsof -i :8080
kill -9 <PID>

# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

### 依赖安装失败

```bash
# 升级 pip
pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 数据库初始化

首次启动时系统会自动创建数据库文件。如需手动初始化：

```bash
python -c "from src.db.memory_store import get_store; get_store()"
```

### Embedder 服务不可用

如果 `embedder_server` 未启动，系统会降级使用 BM25 关键词检索。启动方式：

```bash
# 需要单独部署 BGE 模型服务
# 默认地址：http://localhost:8081
```

## 性能优化

### SQLite 优化

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;
```

### 缓存配置

- L1 缓存：200 条，1 小时 TTL
- L2 缓存：100 条，语义相似度 > 0.92

### 并发控制

- 少阳（文档处理）：Semaphore(3)
- 太阳（检索）：Semaphore(10)
- 太阴（API）：Rate Limiting 60/分钟
