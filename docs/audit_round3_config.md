# 🔍 伏羲 v1.50 · 第三轮审计报告：配置与依赖全维度扫描

> **审计时间**：2026-07-06  
> **仓库路径**：`E:\easyclaw\伏羲-v1.44\repo`  
> **扫描范围**：`src/` 目录下 296 个 Python 文件（34,466 行）、.env.example、requirements.txt、Dockerfile、docker-compose.yml、CI 配置  
> **审计人**：后端架构师 Agent

---

## 总体评估

| 维度 | 状态 | 风险等级 | 发现问题 |
|------|------|---------|---------|
| 1. 环境变量一致性 | ⚠️ 警告 | 🔴 高 | 2 个关键冲突 + 多个命名不一致 |
| 2. 配置冲突 | ⚠️ 警告 | 🔴 高 | src/config.py vs src/infra/config.py 严重不一致 |
| 3. 硬编码配置 | ⚠️ 警告 | 🟡 中 | 多个 URL/端口/超时硬编码 |
| 4. 依赖版本 | ✅ 良好 | 🟢 低 | 版本范围合理，无冲突 |
| 5. 未使用依赖 | ⚠️ 警告 | 🟡 中 | 3 个包在 src 中未直接使用 |
| 6. 缺失依赖 | 🔴 问题 | 🔴 高 | 1 个关键包缺失 + 2 个被注释 |
| 7. Docker 配置 | ⚠️ 警告 | 🟡 中 | root 运行 + 端口直接暴露 |
| 8. CI 配置 | ⚠️ 警告 | 🟡 中 | CI 仅语法检查，缺少 lint/类型/test |
| 9. 日志配置 | ⚠️ 警告 | 🟡 中 | 缺少环境变量控制 + 硬编码值 |
| 10. API 路由清单 | ✅ 完整 | 🟢 低 | 已生成完整路由清单 |

---

## 1. 🔴 环境变量一致性

### 1.1 对比维度

对比 `.env.example` 中定义的变量与代码中 `os.getenv()`/`os.environ` 实际读取的变量。

### 1.2 .env.example 已定义但代码中从未读取的变量

以下变量在 `.env.example` 中有说明但代码中没有任何 `os.getenv()` 读取：

| 变量名 | 在 .env.example 行 | 状态 |
|--------|-------------------|------|
| `JWT_EXPIRY_HOURS` | ✅ 有 | ⚠️ `src/api/auth.py` 硬编码 `JWT_EXPIRE_HOURS = 24`，未读环境变量 |
| `FUXI_ALLOW_REGISTRATION` | ✅ 有 | ❌ 代码中 `auth_routes.py` 直接允许注册，无控制开关 |
| `FUXI_ENV` | ✅ 有 | ❌ 全代码搜索无 `os.getenv("FUXI_ENV")` |
| `FUXI_LOG_LEVEL` | ✅ 有 | ❌ 全代码无 `os.getenv("FUXI_LOG_LEVEL")`，日志级别硬编码为 `INFO` |
| `REDIS_URL` | ✅ 有 | ❌ 无读取，Redis 缓存层可能未实际集成 |

### 1.3 代码中读取但 .env.example 未定义的变量

以下变量在代码中使用 `os.getenv()` 读取，但 **.env.example 中完全没有定义**：

| 变量名 | 读取位置 | 默认值 | 风险 |
|--------|---------|--------|------|
| `DEEPSEEK_API_KEY` | `src/api/__init__.py:14`, `src/hypothalamus/organs/heart/signal_layer.py:112`, `src/hypothalamus/organs/liver/llm.py:14`, `src/hypothalamus/organs/spleen/llm.py:14`, `src/services/multimodal.py:58`, `src/taiyang/rerank.py:10` | `""` | 🔴 已在 .env.example 中定义！此结果来自双 config 混淆 |

> **重要发现**：上述变量实际 **在 `.env.example` 中已有定义**（`DEEPSEEK_API_KEY`、`SILICONFLOW_API_KEY` 等），但因为 `src/infra/config.py` 使用了不同的变量名约定（如 `JWT_SECRET` vs `FUXI_JWT_SECRET`），导致维度分析产生混淆。**核心问题是两个 config 文件使用不同的变量名**，详见第 2 节。

### 1.4 实际代码中读取但 .env.example 缺失的变量（过滤重复后）

| 变量名 | 代码位置 | 默认值 | 影响 |
|--------|---------|--------|------|
| `JWT_SECRET` | `src/infra/config.py:23` | `change-me-in-production` | 🔴 `.env.example` 中叫 `FUXI_JWT_SECRET`，两份 config 用不同名 |
| `SILICONFLOW_BASE_URL` | `src/hypothalamus/organs/spleen/__init__.py:38` | 无默认值 | 🔴 `.env.example` 未定义此变量 |
| `HF_HUB_OFFLINE` | `src/hypothalamus/organs/liver/embedder.py:7` 和 `src/hypothalamus/organs/spleen/embedder.py:7` | `"1"` | 🟡 硬编码设置，用户可能想控制 |
| `TRANSFORMERS_OFFLINE` | 同上 `embedder.py:8` | `"1"` | 🟡 同上 |
| `KB_ROOT` | `src/shaoyin/graph_router.py:59` | 自动设为项目目录 | 🟡 内部使用 |

### 1.5 auth.py 的硬编码 JWT 过期时间

**文件**：`src/api/auth.py:12`
```python
JWT_EXPIRE_HOURS = 24  # 硬编码！未读取环境变量 JWT_EXPIRY_HOURS
```

虽然 `.env.example` 和 `docker-compose.yml` 都定义了 `JWT_EXPIRY_HOURS`，但 `auth.py` 中直接硬编码了值，导致环境变量无效。

---

## 2. 🔴 配置冲突 — 双配置中心问题

系统存在 **两个 config 文件** 定义了大量重叠的配置项，且默认值不同，这是严重的架构问题。

### 2.1 冲突对比表

| 配置项 | `src/config.py`（默认值） | `src/infra/config.py`（默认值） | 冲突？ |
|--------|--------------------------|-------------------------------|--------|
| `MIMO_BASE_URL` | `https://token-plan-cn.xiaomimimo.com/v1` | `https://api.mimo.ai/v1` | 🔴 **严重冲突** |
| `MIMO_MODEL` | `mimo-v2.5` | `mimo-v2.5-pro` | 🔴 **严重冲突** |
| `EMBEDDER_URL` | `http://localhost:8081` | `http://localhost:8091` | 🔴 **严重冲突** |
| `JWT_SECRET` 变量名 | `os.getenv("FUXI_JWT_SECRET")` → `src/api/auth.py` | `os.getenv("JWT_SECRET")` | 🔴 **不同变量名** |
| `DB_PATH` | `DATA_DIR / "chunks.db"` | `BASE_DIR / "memory.db"` | 🔴 **不同路径** |
| `CHROMA_PATH` | 未定义（用 `KB_CHROMA_DIR`） | `BASE_DIR / "chroma_db"` | 🟡 **不同命名** |
| `BASE_DIR` | `os.getenv("FUXI_DATA_DIR", ...)` | `os.getenv("FUXI_DATA_DIR", ...)` | ✅ 一致 |
| `HOST` | `os.getenv("KB_HOST", "0.0.0.0")` | `os.getenv("KB_HOST", "0.0.0.0")` | ✅ 一致 |
| `PORT` | `os.getenv("KB_PORT", "8080")` | `os.getenv("KB_PORT", "8080")` | ✅ 一致 |
| `MIMO_API_KEY` | `os.getenv("MIMO_API_KEY", "")` | `os.getenv("MIMO_API_KEY", "")` | ✅ 一致 |
| `MIMO_TIMEOUT` | `os.getenv("MIMO_TIMEOUT", "60")` | `os.getenv("MIMO_TIMEOUT", "60")` | ✅ 一致 |
| `MAX_FILE_MB` | 硬编码 `200`（非环境变量） | `os.getenv("MAX_FILE_MB", "200")` | 🟡 `src/config.py` 硬编码 |
| `CORS_ORIGINS` | `os.getenv("KB_CORS_ORIGINS", ...)` | `os.getenv("KB_CORS_ORIGINS", ...)` | ✅ 一致 |
| `LOADER_URL` | `os.getenv("LOADER_URL")` | `os.getenv("LOADER_URL")` | ✅ 一致 |

### 2.2 冲突影响分析

1. **`MIMO_BASE_URL` 不一致（最严重）**：
   - `src/config.py` 默认：`https://token-plan-cn.xiaomimimo.com/v1`（小米 Mimo 服务）
   - `src/infra/config.py` 默认：`https://api.mimo.ai/v1`（可能是旧地址或不同服务）
   - 哪个模块 import 哪个 config 决定了实际的 API 地址

2. **`EMBEDDER_URL` 不同**：
   - `src/config.py`：端口 8081
   - `src/infra/config.py`：端口 8091
   - embedder 自身代码中 `port=8081`（硬编码）

3. **JWT_SECRET 变量名分歧**：
   - `src/config.py` 未直接定义（由 `auth.py` 用 `FUXI_JWT_SECRET`）
   - `src/infra/config.py` 用 `JWT_SECRET`
   - `.env.example` 用 `FUXI_JWT_SECRET`
   - 如果用户设置 `JWT_SECRET`，`auth.py` 会使用默认值而非用户设置

4. **`src/config.py` 中 `MAX_FILE_MB` 硬编码 200**：
   - 未从环境变量读取，与 `.env.example` 的 `MAX_FILE_MB` 不一致
   - `src/infra/config.py` 正确地从环境变量读取

### 2.3 建议

🛠️ **强烈建议**：废弃 `src/infra/config.py`，将配置统一到 `src/config.py`，或让两者从同一来源读取。建议使用 Pydantic Settings 管理所有配置。

---

## 3. 🟡 硬编码配置

### 3.1 硬编码 URL

| 文件:行 | 硬编码值 | 应提取为 |
|---------|---------|---------|
| `src/hypothalamus/organs/spleen/llm.py:15` <br> `src/hypothalamus/organs/liver/llm.py:15` | `https://api.deepseek.com` | `DEEPSEEK_BASE_URL` 环境变量 |
| `src/hypothalamus/organs/spleen/llm.py:313` <br> `src/hypothalamus/organs/liver/llm.py:268` | `https://api.siliconflow.cn/v1` | `SILICONFLOW_BASE_URL` 环境变量 |
| `src/shaoyin/distiller.py:49` | `https://api.deepseek.com/v1/chat/completions` | `DEEPSEEK_BASE_URL` |
| `src/taiyang/rerank.py:36` | `https://api.deepseek.com/v1/chat/completions` | `DEEPSEEK_BASE_URL` |
| `src/taiyang/rerank.py:159` | `https://api.siliconflow.cn/v1/rerank` | `SILICONFLOW_BASE_URL` |
| `src/services/multimodal.py:57` | `https://api.deepseek.com/v1` | `DEEPSEEK_BASE_URL` |
| `src/hypothalamus/organs/skin/signal_layer.py:109` | `https://api.search.brave.com/res/v1/web/search` | 已有 `BRAVE_API_KEY`，但 URL 硬编码 |
| `src/category_registry.py:414` | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` | `MIMO_BASE_URL` + `/chat/completions` |

### 3.2 硬编码端口

| 文件:行 | 硬编码值 | 应提取为 |
|---------|---------|---------|
| `src/hypothalamus/organs/liver/embedder.py:101` <br> `src/hypothalamus/organs/spleen/embedder.py:101` | `port=8081`（embedder 服务启动端口） | 环境变量 `KB_EMBEDDER_PORT` |
| `src/fuxi_platform/registry.py:170` | `localhost` + 动态端口 | 使用配置 |

### 3.3 硬编码超时

| 文件 | 超时值 | 说明 |
|------|--------|------|
| `src/hypothalamus/organs/spleen/llm.py:17` <br> `src/hypothalamus/organs/liver/llm.py:17` | `DEEPSEEK_TIMEOUT = 60` | 模块级硬编码 |
| `src/shaoyin/distiller.py:34` | `LLM_TIMEOUT = 180` | 模块级硬编码 |
| `src/shaoyang/multimodal.py:125,166` | `timeout=30` | 行内硬编码 |
| `src/hypothalamus/organs/liver/evaluator.py:29` | `timeout=30` | 行内硬编码 |
| `src/hypothalamus/brain.py:332,348` | `timeout=10.0`, `timeout=15.0` | 行内硬编码 |
| `src/shaoyin/query_expansion.py:70,95` | `timeout=10.0` | 行内硬编码 |
| `src/taiyang/retrieval.py:191,212` | `timeout=10.0`, `timeout=15.0` | 行内硬编码 |
| 约 40+ 处 sqlite3 | `timeout=10` + `PRAGMA busy_timeout=5000` | 分散在 ~20 个文件中 |

### 3.4 硬编码路径

| 文件:行 | 硬编码值 | 应提取为 |
|---------|---------|---------|
| `src/api/auth_routes.py:33` | `Path("data/users.json")` | 应使用 `DATA_DIR / "users.json"` |
| `src/api/documents.py:39` | `Path("data/uploads")` | 应使用 `UPLOAD_DIR` |
| `src/db/vector_store.py:29` | `os.getenv("KB_CHROMA_DIR", "data/chromadb")` | 默认值与 `.env.example` 中的 `data/chroma` 不一致 |

### 3.5 worker 数量硬编码

| 文件:行 | 硬编码值 |
|---------|---------|
| `src/server.py:457` | `workers=1`（uvicorn 启动） |
| `Dockerfile:25` | `--workers 4`（Docker 启动命令） |

⚠️ Dockerfile 硬编码 4 workers，本地开发 hardcode 1 worker——不一致且不可配置。

---

## 4. ✅ 依赖版本检查

### 4.1 版本规范

`requirements.txt` 中的版本范围规范：

| 依赖 | 版本范围 | 评价 |
|------|---------|------|
| `fastapi>=0.104.0,<1.0.0` | 范围锁定 | ✅ 良好 |
| `uvicorn[standard]>=0.24.0,<1.0.0` | 范围锁定 | ✅ 良好 |
| `pydantic>=2.5.0,<3.0.0` | 范围锁定 | ✅ 良好 |
| `chromadb>=0.4.0,<1.0.0` | 范围锁定 | ✅ 良好 |
| `sentence_transformers>=2.2.0` | **未锁定上限** | ⚠️ 可能破坏兼容 |
| `Pillow>=10.0.0` | **未锁定上限** | ⚠️ 可能破坏兼容 |
| `numpy>=1.26.0` | **未锁定上限** | ⚠️ 可能破坏兼容 |
| `pandas>=2.0.0` | **未锁定上限** | ⚠️ 可能破坏兼容 |
| `PyYAML>=6.0.0` | **未锁定上限** | ⚠️ 可能破坏兼容 |
| 其他未定义上限的 | 共 12 个包 | ⚠️ 建议全部加 `<N+1.0` 上限 |

### 4.2 依赖冲突检查

无明显依赖冲突。`starlette` 由 `fastapi` 自动引入，版本由 fastapi 决定。

### 4.3 requirements-dev.txt

✅ 包含 `pytest-cov`、`mypy`、`ruff`、`pre-commit`、`pip-audit`，质量工具配置良好。

---

## 5. 🟡 未使用依赖

以下 `requirements.txt` 中的包在 `src/` 目录的 `.py` 文件中 **未直接 import**：

| 包名 | 状态 | 分析 |
|------|------|------|
| `python-dotenv` | ❌ 未使用 | 代码中通过手动解析 `.env` 文件加载（`server.py:10-17`），未 import `dotenv` |
| `pytest` | ❌ 未使用 | 只在 `tests/` 目录使用（正确位置），不应在 `requirements.txt` |
| `pytest-asyncio` | ❌ 未使用 | 同上，只在测试中使用 |

### 建议

将 `pytest`、`pytest-asyncio` 从 `requirements.txt` 移至 `requirements-dev.txt`（后者已包含）。`requirements.txt` 应只包含运行时依赖。

`python-dotenv` 可以保留（作为备选加载方式），但建议统一使用 `python-dotenv` 的 `load_dotenv()` 替代 `server.py` 中的手动解析。

---

## 6. 🔴 缺失依赖

### 6.1 `knowledge_evolver` — 完全缺失 🚨

| 文件 | 引用行 | 影响 |
|------|--------|------|
| `src/services/auto_classifier.py:167` | `from knowledge_evolver import EntityGraph` | 🔴 运行时必崩溃 |

- `pip show knowledge_evolver` → **Not Found**
- 这是第三方包还是内部模块？项目中有 `src/services/evolver.py`，但 import 是从外部包导入
- 如果 `EntityGraph` 有 try/except 保护则可能降级，但代码中未见保护

### 6.2 被注释的可选依赖

| 包名 | 使用位置 | 状态 |
|------|---------|------|
| `unstructured>=0.15.0` | `src/shaoyang/mineru.py`（try/except ImportError） | ⚠️ 被注释 |
| `magic-pdf>=0.6.0` | `src/shaoyang/mineru.py`（try/except ImportError） | ⚠️ 被注释 |

代码中 import 了 `unstructured` 和 `magic_pdf`，但 requirements.txt 中将它们注释掉了。如果有 try/except 降级则安全，但需确认。

---

## 7. 🟡 Docker 配置安全检查

### 7.1 Dockerfile

| 检查项 | 状态 | 问题 |
|--------|------|------|
| 基础镜像 | Python 3.10-slim | ✅ 良好 |
| 非 root 用户 | ❌ 默认 root | 🔴 安全风险 — 未创建非 root 用户 |
| 系统依赖 | 只安装 `libsqlite3-dev` | ✅ 最小化 |
| pip 缓存 | `--no-cache-dir` | ✅ 良好 |
| EXPOSE 8080 | 单一端口 | ✅ 清晰 |
| ENV 硬编码 | `DEEPSEEK_API_KEY=""` 写在 Dockerfile | ⚠️ 无意义，只在构建时生效 |
| 多阶段构建 | ❌ 单阶段 | 🟡 可优化镜像大小 |
| workers 硬编码 | `--workers 4` | 🟡 不可配置 |

### 7.2 docker-compose.yml

| 检查项 | 状态 | 问题 |
|--------|------|------|
| fuxi-server 端口暴露 | `8080:8080` | ✅ 合理（需对外服务） |
| ChromaDB 端口暴露 | `8000:8000` | 🔴 直接暴露到宿主机！ |
| Redis 端口暴露 | `6379:6379` | 🔴 直接暴露到宿主机！ |
| fuxi-server 用户 | ❌ 未指定 user | 🔴 root 运行 |
| ChromaDB 用户 | 未指定 | ⚠️ Chroma 镜像默认用户 |
| Redis | 使用 `redis:7-alpine` | ✅ 良好 |
| Redis 密码 | ❌ 无密码 | 🔴 无认证 |
| healthcheck | ✅ 三个服务都有 | ✅ 良好 |
| volumes | 具名卷持久化 | ✅ 良好 |
| 资源限制 | ❌ 未设置 | 🟡 建议添加 `deploy.resources.limits` |
| version | `3.8` | ⚠️ 已弃用（Docker Compose V2 忽略此字段） |

### 7.3 安全改进建议

```yaml
# 建议在 docker-compose.yml 的 fuxi-server 服务中添加：
services:
  fuxi-server:
    user: "1000:1000"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  chromadb:
    # 不建议对外暴露 8000
    # ports:  # 仅内部使用
    expose:
      - "8000"

  redis:
    # 不建议对外暴露 6379
    # ports:
    expose:
      - "6379"
    command: redis-server --appendonly yes --maxmemory 256mb --requirepass ${REDIS_PASSWORD:-redispass}
```

---

## 8. 🟡 CI 配置检查

### 8.1 `.github/workflows/ci.yml` 分析

| 步骤 | 内容 | 评价 |
|------|------|------|
| 触发器 | push/PR 到 master/main | ✅ 标准 |
| Python 版本 | 3.10 | ✅ 与项目一致 |
| 安装依赖 | `pip install fastapi uvicorn chromadb requests pytest pytest-asyncio` | ⚠️ **手动枚举依赖**，未使用 `-r requirements.txt` |
| 单元测试 | `python -m pytest tests/` | ✅ 但依赖不完整（未安装所有测试依赖） |
| Smoke test | `python scripts/eval_smoke_lite.py` | ✅ 有冒烟测试 |
| Security check | 检查硬编码密钥 | ✅ 良好 |
| Lint job | 仅 `py_compile` 语法检查 | ❌ **太弱** |

### 8.2 CI 缺失项

| 缺失内容 | 重要性 |
|---------|--------|
| 类型检查（mypy） | 🔴 开发依赖已包含但 CI 未运行 |
| 代码风格检查（ruff） | 🔴 同上 |
| 依赖安全扫描（pip-audit） | 🟡 同上 |
| 代码覆盖率报告 | 🟡 |
| 依赖安装应使用 `pip install -r requirements.txt` | 🔴 当前手动枚举可能遗漏 |
| Python 多版本矩阵测试 | 🟡 如 3.10/3.11/3.12 |
| Docker 镜像构建验证 | 🟡 |
| 环境变量注入 | ⚠️ 缺少 `MIMO_API_KEY` 等 secrets |

---

## 9. 🟡 日志配置检查

### 9.1 当前日志配置

**文件**：`src/server.py:30-45`

```python
logging.basicConfig(
    level=logging.INFO,  # 硬编码
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            os.path.join(_log_dir, '伏羲·内世界.log'),
            maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
```

### 9.2 问题

| 问题 | 详情 |
|------|------|
| 日志级别硬编码 | `level=logging.INFO` — `.env.example` 定义了 `FUXI_LOG_LEVEL` 但未使用 |
| 轮转大小硬编码 | `maxBytes=10*1024*1024`（10MB），不可配置 |
| 备份数量硬编码 | `backupCount=5`，不可配置 |
| 日志路径 | 使用 `os.path.dirname` 拼接而非 `LOG_DIR` from config |
| FUXI_ENV 未使用 | `.env.example` 定义了 `FUXI_ENV` 但代码未读取，无法按环境切换日志级别 |
| 无 JSON 格式选项 | 生产环境建议支持 JSON 格式日志（便于采集） |

### 9.3 建议

```python
import logging, os
level = getattr(logging, os.getenv("FUXI_LOG_LEVEL", "INFO"))
log_format = os.getenv("FUXI_LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
max_bytes = int(os.getenv("FUXI_LOG_MAX_BYTES", "10485760"))  # 10MB
backup_count = int(os.getenv("FUXI_LOG_BACKUP_COUNT", "5"))
```

---

## 10. 📋 API 路由清单

### 10.1 路由总览

**总计**：47 个端点（不包括嵌入器服务的 3 个端点 和 doc_tools 服务的 18 个端点）

### 10.2 完整路由列表

#### 🔓 公开端点（无认证要求）

| 端点 | 方法 | 认证 | 文件 | 说明 |
|------|------|------|------|------|
| `/` | GET | ❌ | `src/server.py:379` | 前端入口 index.html |
| `/login` | GET | ❌ | `src/server.py:373` | 登录页 login.html |
| `/admin` | GET | ❌ | `src/server.py:385` | 管理面板（前端路由） |
| `/api/health` | GET | ❌ | `src/server.py:303` | 健康检查 |
| `/api/metrics` | GET | ❌ | `src/server.py:193` | Prometheus 指标 |
| `/metrics` | GET | ❌ | `src/server.py:401` | Prometheus 指标（裸路径） |
| `/api/auth/login` | POST | ❌ | `src/api/auth_routes.py:27` | 用户登录 |
| `/api/auth/register` | POST | ❌ | `src/api/auth_routes.py:55` | 用户注册 |
| 静态文件 | GET | ❌ | `src/server.py:393` | `/static/*` |

#### 🔒 需认证端点（AuthMiddleware 白名单以外）

| 端点 | 方法 | 认证 | 文件 | 说明 |
|------|------|------|------|------|
| `/api/auth/me` | GET | 🔒 | `src/server.py:365` | 获取当前用户信息 |
| `/api/search` | GET | 🔒 | `src/api/search.py:6` | 混合搜索 |
| `/api/search-history` | GET | 🔒 | `src/api/search.py:25` | 搜索历史 |
| `/api/chat` | POST | 🔒 | `src/api/chat.py:13` | AI 对话 |
| `/api/chat/agent` | POST | 🔒 | `src/api/chat.py:33` | Agent 对话 |
| `/api/documents` | GET | 🔒 | `src/api/documents.py:7` | 文档列表 |
| `/api/upload` | POST | 🔒 | `src/api/documents.py:31` | 文件上传 |
| `/api/view/{file_hash}` | GET | 🔒 | `src/api/files_view.py:17` | 文件预览 |
| `/api/download/{file_hash}` | GET | 🔒 | `src/api/files_view.py:50` | 文件下载 |
| `/api/antenna/search` | GET | 🔒 | `src/api/files_view.py:79` | 天线搜索 |
| `/api/graph` | GET | 🔒 | `src/api/graph.py:6` | 知识图谱 |
| `/api/metadata` | GET | 🔒 | `src/api/metadata.py:6` | 元数据 |
| `/api/feedback` | POST | 🔒 | `src/api/feedback.py:12` | 提交反馈 |
| `/api/feedback/weekly` | GET | 🔒 | `src/api/feedback.py:6` | 每周反馈报告 |
| `/api/dashboard` | GET | 🔒 | `src/api/dashboard.py:6` | 评测仪表板 |
| `/api/wiki/pages` | GET | 🔒 | `src/api/wiki.py:6` | Wiki 页面列表 |
| `/api/wiki/search` | GET | 🔒 | `src/api/wiki.py:12` | Wiki 搜索 |
| `/api/wiki/page/{page_id}` | GET | 🔒 | `src/api/wiki.py:18` | Wiki 页面详情 |
| `/api/worldtree/stats` | GET | 🔒 | `src/api/worldtree.py:6` | WorldTree 统计 |
| `/api/worldtree/wiki/tree` | GET | 🔒 | `src/api/worldtree.py:12` | WorldTree Wiki 树 |
| `/api/worldtree/entities` | GET | 🔒 | `src/api/worldtree.py:18` | WorldTree 实体 |
| `/api/v2/status` | GET | 🔒 | `src/api/v2_routes.py:6` | v2 状态 |
| `/api/admin/stats` | GET | 🔒 | `src/api/admin.py:6` | 管理：统计 |
| `/api/admin/server-status` | GET | 🔒 | `src/api/admin.py:12` | 管理：服务器状态 |
| `/api/admin/metrics-summary` | GET | 🔒 | `src/server.py:409` | 管理：可观测性摘要 |
| `/api/evaluation/overview` | GET | 🔒 | `src/api/evaluation.py:6` | 评测概览 |
| `/api/evolution/overview` | GET | 🔒 | `src/api/evolution.py:6` | 进化概览 |
| `/api/eval/run` | POST | 🔒 | `src/server.py:269` | 运行评测 |
| `/api/eval/report` | GET | 🔒 | `src/server.py:275` | 评测报告 |
| `/api/eval/history` | GET | 🔒 | `src/server.py:281` | 评测历史 |
| `/api/mcp` | POST | 🔒 | `src/server.py:225` | MCP 协议入口 |
| `/api/mcp/tools` | GET | 🔒 | `src/server.py:232` | MCP 工具列表 |
| `/api/mcp/sag_search` | POST | 🔒 | `src/server.py:239` | MCP 搜索 |
| `/api/mcp/sag_ingest` | POST | 🔒 | `src/server.py:246` | MCP 入库 |
| `/api/mcp/sag_explain` | POST | 🔒 | `src/server.py:253` | MCP 解释 |
| `/api/mcp/sag_status` | GET | 🔒 | `src/server.py:260` | MCP 状态 |
| `/api/symbols/status` | GET | 🔒 | `src/server.py:290` | 四象状态 |
| `/api/growth/overview` | GET | 🔒 | `src/server.py:296` | 成长概览 |
| `/api/system/stats` | GET | 🔒 | `src/server.py:314` | 系统统计 |
| `/api/cache/stats` | GET | 🔒 | `src/server.py:324` | 缓存统计 |
| `/api/errors/stats` | GET | 🔒 | `src/server.py:334` | 错误统计 |
| `/api/feature-flags` | GET | 🔒 | `src/server.py:347` | Feature Flag 列表 |
| `/api/feature-flags/{name}` | PUT | 🔒 | `src/server.py:353` | 更新 Feature Flag |
| `/api/proxy/loader/files` | GET | 🔒 | `src/server.py:421` | 代理：装载机文件列表 |
| `/api/proxy/loader/upload` | POST | 🔒 | `src/server.py:432` | 代理：上传到装载机 |

#### 内部服务端点（不通过主路由注册）

| 端点 | 方法 | 服务 | 说明 |
|------|------|------|------|
| `/embed` | POST | Embedder（端口 8081） | 文本嵌入 |
| `/rerank` | POST | Embedder（端口 8081） | 结果重排 |
| `/health` | GET | Embedder（端口 8081） | 嵌入器健康检查 |
| `/health` | GET | Doc Tools | 文档工具健康检查 |
| `/summarize` | POST | Doc Tools | 文档摘要 |
| `/translate` | POST | Doc Tools | 翻译 |
| `/keywords` | POST | Doc Tools | 关键词提取 |
| `/entities` | POST | Doc Tools | 实体提取 |
| `/classify` | POST | Doc Tools | 分类 |
| `/convert` | POST | Doc Tools | 文档转换 |
| `/merge` | POST | Doc Tools | PDF 合并 |
| `/split` | POST | Doc Tools | PDF 分割 |
| `/compress` | POST | Doc Tools | 压缩 |
| `/image-info` | POST | Doc Tools | 图片信息 |
| `/compress-image` | POST | Doc Tools | 图片压缩 |
| `/text-extract` | POST | Doc Tools | 文本提取 |
| `/trends` | POST/GET | Doc Tools | 趋势分析 |
| `/report` | POST/GET | Doc Tools | 报告生成 |
| `/storage` | POST/GET | Doc Tools | 存储管理 |
| `/export` | POST/GET | Doc Tools | 导出 |
| `/stats` | GET/POST | Doc Tools | 统计 |
| `/health` | GET | Fuxi Platform | 平台健康检查 |
| `/upload` | POST | Fuxi Platform | 文件上传（内部） |
| `/files` | GET | Fuxi Platform |