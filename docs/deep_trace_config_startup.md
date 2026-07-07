# 伏羲 v1.50 配置初始化与启动链路 — 深度全链路追踪报告

> 追踪时间：2026-07-06  
> 仓库路径：`E:\easyclaw\伏羲-v1.44\repo`  
> 追踪方法：逐文件/逐行读取源码，追踪 import 链确认实际引用，用代码行号作为证据

---

## 目录

1. [启动链路：从 `server.py:main()` 到伏羲苏醒](#1-启动链路从-serverpymain-到伏羲苏醒)
2. [config.py 完整配置项清单](#2-configpy-完整配置项清单)
3. [os.getenv/os.environ.get 全量扫描 → .env.example 差异分析](#3-osgetenvosenvironget-全量扫描--envexample-差异分析)
4. [config 导入使用追踪（谁用了哪个配置项）](#4-config-导入使用追踪谁用了哪个配置项)
5. [ChromaDB 初始化深度追踪](#5-chromadb-初始化深度追踪)
6. [FastAPI startup event / lifespan 分析](#6-fastapi-startup-event--lifespan-分析)
7. [问题汇总与风险清单](#7-问题汇总与风险清单)

---

## 1. 启动链路：从 `server.py:main()` 到伏羲苏醒

### 1.1 启动入口的物理执行顺序

`server.py` 末尾的 `if __name__ == "__main__":` 块调用 `uvicorn.run(app, ...)` 启动 FastAPI。**但是在此之前，整个 `server.py` 作为 Python 模块已被完整执行**。以下按代码行号追踪执行顺序：

#### 第一层：模块级初始化（import 时立即执行）

| 序号 | 行号 | 操作 | 说明 |
|------|------|------|------|
| 1 | L6-14 | `.env` 文件加载 | 手工解析 `_project_root / ".env"` 写入 `os.environ` |
| 2 | L17-19 | sys.path 设置 | 注入项目根目录和 `src/` |
| 3 | L22-37 | logging 初始化 | `RotatingFileHandler` → `src/logs/伏羲·内世界.log`，最多5备份，10MB轮转 |
| 4 | L39-42 | uvicorn + FastAPI 导入 | `import uvicorn` 等 |
| 5 | L44 | **Unresolved import** | `import aiohttp` — 未在文件顶部导入但后续 L462 使用 |
| 6 | L49 | **`from src.config import ...`** | ⚠️ 触发 `src/config.py` 的模块级执行（见下） |
| 7 | L53-59 | `FastAPI` 实例创建 | 创建 app 对象 |
| 8 | L90-94 | 中间件注册 | `AuthMiddleware` + `InputLimitMiddleware` 导入并注册 |
| 9 | L96-101 | CORS + GZip 中间件 | 使用 `CORS_ORIGINS`（来自 config） |
| 10 | L104-113 | 限流中间件 | `slowapi` 可选依赖，失败静默（`except ImportError: limiter = None`） |
| 11 | L115-133 | metrics_middleware | 注册 HTTP 中间件，内置 try/except 吞异常 |
| 12 | L135+ | **大量路由注册** | 共约 20 个路由模块被导入和注册 |
| 13 | L437+ | main() 调用 | `uvicorn.run(app, ...)` |

#### 第二层：`from src.config import ...` 触发的连锁导入执行

`src/config.py` 在模块级执行以下操作（行号 L13-L99）：

| 子步骤 | config.py 行号 | 操作 | 副作用 |
|--------|---------------|------|--------|
| a | L13 | `FUXI_DATA_DIR` 读取 | 无 |
| b | L14-L24 | 路径变量定义 | 无 |
| c | L32-33 | `CHUNK_SIZE/OVERLAP` | 无 |
| d | L44-49 | **目录自动创建** | 创建 `DATA_DIR`, `UPLOAD_DIR`, `LOG_DIR`, `BACKUP_DIR`, `STATIC_DIR`, `CONFIG_HISTORY_DIR`, `KB_IMAGES_DIR` 及 thumbs 子目录 |
| e | L52-57 | 网络配置 | 无 |
| f | L62-69 | **JWT_SECRET 检查** | `if not _JWT_SECRET_FROM_ENV: raise RuntimeError(...)` — **启动时必检查** |
| g | L70-76 | 安全配置 | 无 |
| h | L79-82 | MiMo API 配置 | 无 |
| i | L85-88 | DeepSeek API 配置 | 无 |
| j | L91-92 | SiliconFlow API 配置 | 无 |
| k | L97-99 | VERSION + START_TIME | `START_TIME = __import__("time").time()` — 记录进程启动时间 |

#### 第三层：FastAPI 生命周期（uvicorn 启动后）

| 序号 | 行号 | 操作 | 说明 |
|------|------|------|------|
| 1 | L76 | `@app.on_event("startup")` → `_start_fuxi()` | 异步执行 |
| 2 | L62-74 | `_start_fuxi()` 调用 `Fuxi.born()` | 见下文 |
| 3 | L81 | `@app.on_event("shutdown")` → `_stop_fuxi()` | |

### 1.2 `Fuxi.born()` 内部初始化顺序（`fuxi.py` L82-L132）

| 序号 | 操作 | 模块/类 | 是否可能失败 |
|------|------|---------|-------------|
| 1 | `self.meridian.start()` | `Meridian` | 失败会被 `_start_fuxi()` 的 try/except 吞掉 |
| 2 | `ShaoyangPipeline(self.meridian)` | 少阳·消化 | 仅调用 `SymbolBase.__init__`，不失败 |
| 3 | `TaiyangRetrieval(self.meridian)` | 太阳·筑基 | 同上 |
| 4 | `ShaoyinBrain(self.meridian)` | 少阴·炼化 | 同上 |
| 5 | `TaiyinServer(self.meridian)` | 太阴·显化 | 同上 |
| 6 | `HeartAgent(self.meridian)` | 心脏 | 同上 |
| 7 | `Brain(self.meridian)` | 大脑 | 同上 |
| 8 | `StomachAgent(self.meridian)` | **胃 — 可能失败！** | `try: from organs.stomach import StomachAgent` — 但 `stomach.py` **不存在**，目录 `stomach/` 下也**没有 `__init__.py`** |
| 9 | `SpleenAgent(self.meridian)` | 脾 | 正常 |
| 10 | `LungAgent(self.meridian)` | 肺 | 正常 |
| 11 | `LiverAgent(self.meridian)` | 肝 | 正常 |
| 12 | `SkeletonAgent(self.meridian)` | 骨骼 | 正常 |
| 13 | `LimbsAgent(self.meridian)` | 四肢 | 正常 |
| 14 | `KidneyAgent(self.meridian)` | 肾 | 正常 |
| 15 | `NoseAgent(self.meridian)` | 鼻 | 正常 |
| 16 | `SkinAgent(self.meridian)` | 皮肤 | 正常 |
| 17 | `SmallIntestineAgent(self.meridian)` | 小肠 | 正常 |
| 18 | `GallbladderAgent(self.meridian)` | 胆 | 正常 |
| 19 | `SanJiaoAgent(self.meridian)` | 三焦 | 正常 |
| 20 | `FiveElementsBalance(self)` + `.start()` | 五行平衡 | 可能失败 |
| 21 | `StemScheduler(self)` + `.start()` | 天干调度 | 可能失败 |
| 22 | `MeridianRhythm(self.meridian)` + `.start()` | 经络流注 | 可能失败 |
| 23 | `heart.start_beating()` | 心跳 | 可能失败 |
| 24 | `lung.start_breathing()` | 呼吸 | 可能失败 |
| 25 | `kidney.start_filtering()` | 肾过滤 | 可能失败 |
| 26 | `nose.start_sniffing()` | 鼻嗅 | 可能失败 |
| 27 | `stomach.start()` | 胃启动（条件） | 仅当 stomach 不为 None |
| 28 | `skeleton.start_scanning()` | 骨骼扫描 | 可能失败 |
| 29 | `brain.start_pulsing()` | 大脑脉动 | 可能失败 |
| 30 | `liver.start_filtering()` | 肝过滤 | 可能失败 |
| 31 | `spleen.start_working()` | 脾工作 | 可能失败 |
| 32 | `small_intestine.start_working()` | 小肠工作 | 可能失败 |
| 33 | `gallbladder.start_working()` | 胆工作 | 可能失败 |
| 34 | `sanjiao.start_working()` | 三焦工作 | 可能失败 |
| 35 | `skin.start_guarding()` | 皮肤守卫 | 可能失败 |

### 1.3 可能失败但被静默吞掉的初始化

**已确认风险：**

1. **StomachAgent 导入失败**（`fuxi.py` L22-24）：
   ```python
   try:
       from src.hypothalamus.organs.stomach import StomachAgent
   except ImportError:
       StomachAgent = None
   ```
   - 事实：`organs/stomach.py` **不存在**，`organs/stomach/` 目录下也**没有 `__init__.py`**
   - 结果：每次启动都会触发 ImportError，app.state.fuxi.stomach 永远为 None
   - 日志：静默吞掉 — 用户看到 "🍽️ 胃已就绪" 但实际上胃根本不存在

2. **`_start_fuxi()` 整体 try/except**（`server.py` L67-74）：
   ```python
   try:
       ...
       await _fuxi_instance.born()
   except Exception as e:
       logging.getLogger("server").error(f"[Fuxi] 启动失败: {e}")
   ```
   - 如果 born() 中任何一个 `await X.start_*()` 抛出异常，整个 born() 会失败
   - 失败后 `_fuxi_instance` 为模块级定义的 None（L61），app.state 中无 fuxi
   - **无重试机制**，无告警升级

3. **slowapi 导入失败静默**（L104-113）：
   ```python
   try:
       from slowapi import Limiter, ...
   except ImportError:
       limiter = None
   ```
   - 如果 slowapi 未安装，**全站无请求限流**（除了 InputLimitMiddleware 的空壳）

4. **metrics_middleware 内吞异常**（L115-133）：
   两次 try/except 都只打印 warning，不升级

5. **`src/services/__init__.py` 延迟加载隐患**：
   该文件 L33-L75 有大量 eager import，当任何模块 `from src.services.xxx import ...` 时会触发。但服务器启动路径中（server.py）**不直接**触发此文件 — 仅在运行时（organs 的懒加载 ORG 路由代码）触发。

---

## 2. `config.py` 完整配置项清单

### 2.1 路径配置

| 变量名 | 环境变量 | 默认值 | 类型 | 启动必设？ | 说明 |
|--------|---------|--------|------|-----------|------|
| `BASE_DIR` | `FUXI_DATA_DIR` | `_project_root / "data"` | Path | 否 | 数据根目录 |
| `DATA_DIR` | (alias of BASE_DIR) | 同 BASE_DIR | Path | 否 | |
| `FEEDBACK_DIR` | - | `BASE_DIR / "feedback_data"` | Path | 否 | |
| `UPLOAD_DIR` | - | `BASE_DIR / "uploads"` | Path | 否 | |
| `LOG_DIR` | - | `BASE_DIR / "logs"` | Path | 否 | |
| `BACKUP_DIR` | - | `BASE_DIR / "backups"` | Path | 否 | |
| `STATIC_DIR` | - | `_project_root / "frontend"` | Path | 否 | |
| `ADMIN_DIR` | - | `STATIC_DIR / "admin"` | Path | 否 | |
| `CONFIG_HISTORY_DIR` | - | `DATA_DIR / "config_history"` | Path | 否 | |
| `CHUNKS_DB_PATH` | - | `DATA_DIR / "chunks.db"` | Path | 否 | |
| `DB_PATH` | - | 同 CHUNKS_DB_PATH | Path | 否 | legacy alias |
| `WORLDTREE_DB_PATH` | - | `DATA_DIR / "worldtree.db"` | Path | 否 | |
| `WIKI_DB_PATH` | - | 同 WORLDTREE_DB_PATH | Path | 否 | legacy alias |
| **`CHROMA_PATH`** | - | `str(BASE_DIR / "chroma_db")` | str | 否 | ⚠️ 定义但**未被任何模块使用**（见第5章） |
| `CHUNKS_FILE` | - | `DATA_DIR / "chunks.json"` | Path | 否 | |
| `GRAPH_PATH` | - | `DATA_DIR / "knowledge_graph.json"` | Path | 否 | |
| `TERMS_FILE` | - | `DATA_DIR / "company_terms.json"` | Path | 否 | |
| `CONFIG_FILE` | - | `DATA_DIR / "config.json"` | Path | 否 | |
| `USER_PREFERENCES_FILE` | - | `DATA_DIR / "user_preferences.json"` | Path | 否 | |
| `KB_IMAGES_DIR` | - | `BASE_DIR / "kb-images"` | Path | 否 | |

**目录自动创建**（L44-48）：以下目录在 config.py 模块加载时自动创建：
- `DATA_DIR`, `UPLOAD_DIR`, `LOG_DIR`, `BACKUP_DIR`, `STATIC_DIR`, `CONFIG_HISTORY_DIR`, `KB_IMAGES_DIR`
- `KB_IMAGES_DIR / "thumbs"`

### 2.2 网络配置

| 变量名 | 环境变量 | 默认值 | 类型 | 启动必设？ |
|--------|---------|--------|------|-----------|
| `HOST` | `KB_HOST` | `"0.0.0.0"` | str | 否 |
| `PORT` | `KB_PORT` | `"8080"` → int | int | 否 |
| `EMBEDDER_URL` | `KB_EMBEDDER_URL` | `"http://localhost:8081"` | str | 否 |
| `RERANK_URL` | `KB_RERANK_PROXY` | `""` | str | 否 |
| `CORS_ORIGINS` | `KB_CORS_ORIGINS` | `localhost:{PORT},127.0.0.1:{PORT}` | List[str] | 否 |
| `LOADER_URL` | `LOADER_URL` | `"http://localhost:8090"` | str | 否 |
| `AI_TIMEOUT_SECONDS` | `KB_AI_TIMEOUT` | `"30"` → int | int | 否 |

### 2.3 安全配置

| 变量名 | 环境变量 | 默认值 | 启动必设？ | 说明 |
|--------|---------|--------|-----------|------|
| **`JWT_SECRET`** | `FUXI_JWT_SECRET` | **无默认值** | **是** ✅ | 启动时 `raise RuntimeError` |
| `JWT_EXPIRY_HOURS` | `JWT_EXPIRY_HOURS` | `"24"` → int | 否 | |
| `ADMIN_TOKEN` | `KB_ADMIN_TOKEN` | `""` | 否 | |
| `MAX_FILE_MB` | `KB_UPLOAD_MAX_MB` 或 `MAX_FILE_MB` | `"200"` → int | 否 | 双重重定向 |
| `UPLOAD_MAX_MB` | (alias of MAX_FILE_MB) | 同上 | 否 | |

### 2.4 LLM API 配置

| 类别 | 变量名 | 环境变量 | 默认值 |
|------|--------|---------|--------|
| MiMo | `MIMO_API_KEY` | `MIMO_API_KEY` | `""` |
| MiMo | `MIMO_BASE_URL` | `MIMO_BASE_URL` | `"https://token-plan-cn.xiaomimimo.com/v1"` |
| MiMo | `MIMO_MODEL` | `MIMO_MODEL` | `"mimo-v2.5"` |
| MiMo | `MIMO_TIMEOUT` | `MIMO_TIMEOUT` | `"60"` → int |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_KEY` | `""` |
| DeepSeek | `DEEPSEEK_BASE_URL` | `DEEPSEEK_BASE_URL` | `"https://api.deepseek.com"` |
| DeepSeek | `DEEPSEEK_MODEL` | `DEEPSEEK_MODEL` | `"deepseek-v4-pro"` |
| DeepSeek | `DEEPSEEK_TIMEOUT` | `DEEPSEEK_TIMEOUT` | `"60"` → int |
| SiliconFlow | `SILICONFLOW_API_KEY` | `SILICONFLOW_API_KEY` | `""` |
| SiliconFlow | `SILICONFLOW_BASE_URL` | `SILICONFLOW_BASE_URL` | `"https://api.siliconflow.cn/v1"` |

### 2.5 分块参数

| 变量名 | 环境变量 | 默认值 |
|--------|---------|--------|
| `CHUNK_SIZE` | `CHUNK_SIZE` | `"1000"` → int |
| `CHUNK_OVERLAP` | `CHUNK_OVERLAP` | `"100"` → int |

### 2.6 应用常量

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `VERSION` | `"1.50"` | 硬编码 |
| `START_TIME` | `time.time()` | 进程启动时间 |
| `TOOLS_DATA` | 12个工具条目 | 硬编码默认值 |
| `FAQ_DATA` | `[]` | 空列表 |
| `ALLOWED_EXTENSIONS` | 40+ 文件扩展名 | 硬编码 |
| `SENSITIVE_PATTERNS` | 4个正则 | 硬编码 |
| `PROMPTS` | 1个 `fuxi_persona` prompt | 硬编码 |

---

## 3. `os.getenv()` / `os.environ.get()` 全量扫描 → `.env.example` 差异分析

### 3.1 所有在代码中读取的环境变量（去重）

| # | 环境变量名 | 读取位置 | 方式 | .env.example 中有？ |
|---|-----------|---------|------|--------------------|
| 1 | `FUXI_DATA_DIR` | config.py:13, audit.py:11 | os.getenv | ✅ 有 |
| 2 | `CHUNK_SIZE` | config.py:32 | os.getenv | ✅ 有 |
| 3 | `CHUNK_OVERLAP` | config.py:33 | os.getenv | ✅ 有 |
| 4 | `KB_HOST` | config.py:52 | os.getenv | ✅ 有 |
| 5 | `KB_PORT` | config.py:53 | os.getenv | ✅ 有 |
| 6 | `KB_EMBEDDER_URL` | config.py:54 | os.getenv | ✅ 有 |
| 7 | `KB_RERANK_PROXY` | config.py:55, rerank.py:11 | os.getenv | ✅ 有 |
| 8 | `KB_CORS_ORIGINS` | config.py:57 | os.getenv | ✅ 有 |
| 9 | **`FUXI_JWT_SECRET`** | config.py:62, auth.py:12 | os.getenv/os.environ.get | ✅ 有 |
| 10 | `JWT_EXPIRY_HOURS` | config.py:70 | os.getenv | ✅ 有 |
| 11 | `FUXI_JWT_EXPIRE_HOURS` | auth.py:21 | os.environ.get | ❌ **缺失！** |
| 12 | `KB_ADMIN_TOKEN` | config.py:72 | os.getenv | ✅ 有 |
| 13 | `KB_UPLOAD_MAX_MB` | config.py:73 | os.getenv | ✅ 有 |
| 14 | `MAX_FILE_MB` | config.py:73 (fallback) | os.getenv | ✅ 有 |
| 15 | `LOADER_URL` | config.py:75 | os.getenv | ✅ 有 |
| 16 | `KB_AI_TIMEOUT` | config.py:76 | os.getenv | ✅ 有 |
| 17 | `MIMO_API_KEY` | config.py:79, ai_tools, evaluator, category_registry | os.getenv | ✅ 有 |
| 18 | `MIMO_BASE_URL` | config.py:80, ai_tools | os.getenv | ✅ 有 |
| 19 | `MIMO_MODEL` | config.py:81 | os.getenv | ✅ 有 |
| 20 | `MIMO_TIMEOUT` | config.py:82 | os.getenv | ✅ 有 |
| 21 | `DEEPSEEK_API_KEY` | config.py:85, core/__init__.py, heart.py, multimodal.py, rerank.py | os.getenv/os.environ.get | ✅ 有 |
| 22 | `DEEPSEEK_BASE_URL` | config.py:86 | os.getenv | ✅ 有 |
| 23 | `DEEPSEEK_MODEL` | config.py:87 | os.getenv | ✅ 有 |
| 24 | `DEEPSEEK_TIMEOUT` | config.py:88 | os.getenv | ✅ 有 |
| 25 | `SILICONFLOW_API_KEY` | config.py:91, core/__init__.py, rerank.py, ai_tools | os.getenv/os.environ.get | ✅ 有 |
| 26 | `SILICONFLOW_BASE_URL` | config.py:92, ai_tools | os.getenv | ✅ 有 |
| 27 | **`KB_CHROMA_DIR`** | vector_store.py:29, table_view.py:132 | os.getenv | ✅ 有 |
| 28 | `KB_MODEL` | embedder.py:19, services/embedder.py:19 | os.getenv | ✅ 有 |
| 29 | `KB_EMBEDDER_WORKERS` | embedder.py:20, services/embedder.py:20 | os.getenv | ✅ 有 |
| 30 | `BRAVE_API_KEY` | skin.py:103, skin/signal_layer.py:103 | os.getenv | ✅ 有 |
| 31 | `KB_ACCESS_COUNTS_PATH` | kidney.py:24, kidney/data_layer.py:17 | os.environ.get | ❌ **缺失！** |

### 3.2 .env.example 中定义了但代码未读取的变量

| # | .env.example 中的变量 | 默认值 | 状态 |
|---|----------------------|--------|------|
| 1 | `FUXI_ALLOW_REGISTRATION` | `true` | ❌ 代码中**未读取** — 定义了但 auth_routes.py 中不检查此变量 |
| 2 | `REDIS_URL` | (空) | ❌ 代码中**未读取** — 无 Redis 客户端初始化 |
| 3 | `FUXI_ENV` | `development` | ❌ 代码中**未读取** |
| 4 | `FUXI_LOG_LEVEL` | `INFO` | ❌ 代码中**未读取** — 日志级别硬编码为 `logging.INFO`（server.py L26） |
| 5 | `KB_CHROMA_DIR`（重复）| `data/chroma` | ✅ 代码读取，但 `.env.example` 中还存在第 7 行的 `KB_RERANK_PROXY=` 空值和第 198 行的 `KB_RERANK_PROXY=http://127.0.0.1:8091` — **重复定义，后值覆盖前值** |

### 3.3 环境变量命名不一致问题

| 问题 | 详情 |
|------|------|
| **JWT 过期时间双名** | `config.py:L70` 读取 `JWT_EXPIRY_HOURS`，而 `auth.py:L21` 读取 `FUXI_JWT_EXPIRE_HOURS` — 不同文件读取不同环境变量！ |
| **JWT 密钥重复读取** | `config.py:L62` 和 `auth.py:L12` 都独立读取 `FUXI_JWT_SECRET`，都做 `raise RuntimeError` — 如果 `.env` 加载顺序出问题，可能 config 通过但 auth 失败 |

### 3.4 .env 手动加载机制的脆弱性

`server.py` L8-14 手工解析 `.env`，存在以下问题：
- 不处理引号内的 `=` 符号
- 不处理多行值
- 不处理转义字符
- 建议使用 `python-dotenv` 库替代

---

## 4. Config 导入使用追踪（谁用了哪个配置项）

### 4.1 被实际引用的配置项

| 配置项 | 使用者（文件:行号） | 用途 |
|--------|-------------------|------|
| `HOST` | server.py:49 | uvicorn 监听地址 |
| `PORT` | server.py:49 | uvicorn 监听端口 |
| `VERSION` | server.py:49, server.py:56, data_analytics/routes.py:356 | API 版本号和响应 |
| `CORS_ORIGINS` | server.py:49 → L98 | CORS 中间件 |
| `LOADER_URL` | server.py:49 → L462, L478 | 代理转发到文档装载机 |
| `START_TIME` | admin.py:75, metrics.py:167, taiyin/metrics.py:151, data_analytics/routes.py:356 | 系统运行时间统计 |
| `WORLDTREE_DB_PATH` | core/db.py:11, retrieval.py:197, relation_builder.py:23/109/135, graph_router.py:279/328, wiki.py:54 | SQLite 数据库路径 |
| `CHUNKS_DB_PATH` | core/db.py:11, data_store.py:12, data_analytics/routes.py:138/513 | SQLite 分块数据库 |
| `LOG_DIR` | core/db.py:11, data_analytics/routes.py:27, eval_updater.py:19 | 日志目录 |
| `DATA_DIR` | data_store.py:12/269, memory_store.py:18, data_analytics/routes.py:27, eval_updater.py:19, evolver.py:11, learner.py:13, distiller.py:21, graph_router.py:10 | 数据根目录 |
| `USER_PREFERENCES_FILE` | data_store.py:269 | 用户偏好文件 |
| `FEEDBACK_DIR` | feedback_store.py:115 | 反馈数据目录 |
| `GRAPH_PATH` | graph_router.py:10 | 知识图谱 JSON 文件 |
| `EMBEDDER_URL` | vector_store.py:23, embedder.py:113, services/embedder.py:113, query_expansion.py:27, results_postprocess.py:26, retrieval.py:21, fusion.py:26, rerank.py:12 | Embedder 服务地址 |
| `PROMPTS` | brain.py:24 → L26 | 伏羲人格 prompt |
| `MIMO_API_KEY` | llm.py:11, services/llm.py:21, yang_agent.py:215, agentic_rag_v2.py:157, config_validation.py:58 | MiMo LLM 调用 |
| `MIMO_BASE_URL` | llm.py:11, services/llm.py:21, yang_agent.py:215, agentic_rag_v2.py:157, config_validation.py:58 | MiMo API 地址 |
| `MIMO_MODEL` | llm.py:11, services/llm.py:21, yang_agent.py:215, agentic_rag_v2.py:157 | MiMo 模型名 |
| `MIMO_TIMEOUT` | llm.py:11, services/llm.py:21, yang_agent.py:215, agentic_rag_v2.py:157 | MiMo 超时 |
| `DEEPSEEK_API_KEY` | llm.py:14, services/llm.py:24 | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | llm.py:14, services/llm.py:24, distiller.py:21, multimodal.py:57, rerank.py:12 | DeepSeek API URL |
| `DEEPSEEK_MODEL` | llm.py:14, services/llm.py:24 | DeepSeek 模型名 |
| `DEEPSEEK_TIMEOUT` | llm.py:14, services/llm.py:24 | DeepSeek 超时 |
| `SILICONFLOW_API_KEY` | llm.py:309/321, services/llm.py:274/286 | SiliconFlow API 密钥 |
| `SILICONFLOW_BASE_URL` | llm.py:309/321, services/llm.py:274/286, multimodal.py:57, rerank.py:12 | SiliconFlow API URL |
| `DB_PATH` | config_validation.py:48, connection_pool.py:85 | 数据库路径（legacy alias） |

### 4.2 已失效的配置项（定义但未被引用）

| 配置项 | 定义位置 | 说明 |
|--------|---------|------|
| **`CHROMA_PATH`** | config.py:L29 | `str(BASE_DIR / "chroma_db")` — **0 个模块引用此变量**。实际 ChromaDB 路径由 `vector_store.py` 和 `table_view.py` 各自通过 `KB_CHROMA_DIR` 确定。 |
| `RERANK_URL` | config.py:L55 | 定义为 `KB_RERANK_PROXY` 的值，但实际代码（rerank.py）**直接** `os.getenv("KB_RERANK_PROXY")` 而非使用此变量 |
| `CHUNKS_FILE` | config.py:L36 | 未搜到任何 import 引用 |
| `TERMS_FILE` | config.py:L37 | 未搜到任何 import 引用 |
| `CONFIG_FILE` | config.py:L38 | 未搜到任何 import 引用 |
| `WIKI_DB_PATH` | config.py:L28 | legacy alias → WORLDTREE_DB_PATH，但所有 wiki 相关代码直接 import WORLDTREE_DB_PATH |
| `ALLOWED_EXTENSIONS` | config.py:L112-121 | 未搜到任何 import 引用 |
| `SENSITIVE_PATTERNS` | config.py:L124-129 | 未搜到任何 import 引用 |
| `TOOLS_DATA` | config.py:L102-114 | 未搜到任何 import 引用 |
| `FAQ_DATA` | config.py:L115 | 空列表，未引用 |
| `ADMIN_DIR` | config.py:L19 | 未搜到任何 import 引用 |

---

## 5. ChromaDB 初始化深度追踪

### 5.1 初始化位置和路径

ChromaDB 在**两个独立位置**初始化，使用**不同的路径**：

#### 位置 1：`src/db/vector_store.py` L36-55

```python
CHROMA_DIR = os.getenv("KB_CHROMA_DIR", "data/chromadb")

class VectorStore:
    def __init__(self, db_dir: str = "data", collection_name: str = "kb_chunks"):
        persist_dir = os.path.join(db_dir, "chroma")        # "data/chroma"
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,                           # "kb_chunks"
            metadata={
                "hnsw:space": "cosine",
                "hnsw:M": 32,
                "hnsw:construction_ef": 200,
                "hnsw:search_ef": 100,
            },
        )
```

- **实际路径**：`data/chroma/`（不是 `data/chroma_db/`）
- **集合名**：`kb_chunks`
- 使用 `EmbeddingFunction=None`（外部 embedder 负责向量化）
- **初始化触发时机**：首次调用 `get_vector_store()` 时懒加载

#### 位置 2：`src/services/table_view.py` L130-144

```python
persist_dir = os.path.join(os.getenv("KB_CHROMA_DIR", "data/chroma"))
client = chromadb.PersistentClient(
    path=persist_dir,
    settings=ChromaSettings(anonymized_telemetry=False),
)
return client.get_or_create_collection(
    name=TABLE_COLLECTION,      # "kb_tables"
    metadata={
        "hnsw:space": "cosine",
        "hnsw:M": 16,
        "hnsw:construction_ef": 100,
        "hnsw:search_ef": 50,
    }
)
```

- **同一路径**：`data/chroma/`
- **不同集合**：`kb_tables`
- 每次调用 `get_table_store()` 都创建新的 PersistentClient（非单例）

### 5.2 路径差异对比

| 数据来源 | 路径值 | 实际存在？ |
|---------|--------|----------|
| `config.py` CHROMA_PATH | `data/chroma_db` | ❌ 不存在 — 且**未被使用** |
| `.env.example` KB_CHROMA_DIR | `data/chroma` | ✅ |
| `vector_store.py` 实际使用 | `data/chroma/` | ✅ `chroma.sqlite3` 存在（184KB） |
| `table_view.py` 实际使用 | `data/chroma/` | ✅ 同一个目录 |

### 5.3 重连/自愈机制

`VectorStore`（`vector_store.py`）有自愈机制：

- `_fail_count` 计数器：每次操作失败 +1
- **阈值**：`MAX_CONSECUTIVE_FAILS = 3`（L35）
- **触发**：达到 3 次连续失败 → `_reset_connection()`（L91-95）
- **重置逻辑**（L62-85）：
  ```python
  def _reset_connection(self) -> bool:
      persist_dir = os.path.join(self.db_dir, "chroma")
      self._client = chromadb.PersistentClient(path=persist_dir, ...)
      self._collection = self._client.get_collection(self.collection_name)
      self._fail_count = 0
      self._usable = True
  ```
  - 重连失败：仅打日志，返回 False，`_usable` 不更新
  - **成功时**：计数器和 `_usable` 标志都被重置

- `table_view.py` 的 `get_table_store()`：**无重连机制**，每次调用新建 client

### 5.4 ChromaDB 初始化不发生在启动时

重要发现：**ChromaDB 的 PersistentClient 不在 FastAPI 启动时创建**。

- `get_vector_store()` 是懒加载单例模式（L246-254）
- 只有在首次查询/写入操作时才会初始化
- 如果 ChromaDB 初始化失败，`get_vector_store()` 返回 None
- 启动时的 `health_check` 中 `check_vector_store()` 会触发首次初始化（health_check.py L65-70）

---

## 6. FastAPI Startup Event / Lifespan 分析

### 6.1 使用了旧的 `@app.on_event("startup")` 模式

`server.py` L76-80 使用 FastAPI 的旧式事件钩子（非 lifespan 上下文管理器）：

```python
@app.on_event("startup")
async def startup():
    await _start_fuxi()

@app.on_event("shutdown")
async def shutdown():
    await _stop_fuxi()
```

⚠️ **FastAPI 官方已废弃此 API**，推荐使用 `lifespan` 上下文管理器。

### 6.2 启动时 `_start_fuxi()` 实际做的事

按执行顺序：

1. **导入** `src.hypothalamus.fuxi` 模块 → 触发其顶层 import（meridian, brain, 四象模块, 14 个器官模块）
2. **创建** `Fuxi()` 实例 → 仅初始化 `__init__` 中的属性为 None/空
3. **设置** `app.state.fuxi`, `app.state.meridian`, `app.state.fuxi_version`, `app.state.fuxi_born_at`
4. **调用** `await _fuxi_instance.born()` → 真正的初始化（见 1.2 节）

### 6.3 启动时 NOT 发生的事

- ❌ ChromaDB PersistentClient **不**在启动时创建
- ❌ SQLite 数据库连接 **不**在启动时建立（懒加载）
- ❌ LLM API 连接 **不**在启动时测试（仅读取配置）
- ❌ Embedder 服务 **不**在启动时健康检查
- ❌ Redis 连接 **不**存在（代码中无 Redis 实现）
- ❌ `infra/config_validation.py` 的 `ConfigValidator` **不**在启动时自动调用 — 被定义为模块但未在 startup 中调用

### 6.4 停服时 `_stop_fuxi()` 实际做的事

1. `await heart.stop_beating()`
2. `await lung.stop_breathing()`
3. `await nose.stop_sniffing()`
4. `await kidney.stop_filtering()`
5. `await meridian.stop()`
6. 设置 `_born = False`

---

## 7. 问题汇总与风险清单

### 🔴 严重问题

| # | 问题 | 影响 | 建议修复 |
|---|------|------|----------|
| 1 | **StomachAgent 导入永远失败** — `organs/stomach.py` 不存在，也无 `stomach/__init__.py` | 每此启动默默地跳过胃的创建，日志显示"胃已就绪"但 stomach 为 None | 创建 `organs/stomach/__init__.py` 或从 born() 中移除 |
| 2 | **JWT 过期时间双环境变量** — `config.py` 读 `JWT_EXPIRY_HOURS`，`auth.py` 读 `FUXI_JWT_EXPIRE_HOURS` | 两个文件使用不同变量名，可能导致配置不一致 | 统一为一个变量名 |
| 3 | **启动失败全部被吞** — `_start_fuxi()` 的 try/except 只打 error log，不阻止启动 | 服务器可能在没有 Fuxi 生命体的情况下运行，所有 /api/chat 请求返回 500 | 在 startup 中加入 `sys.exit(1)` 或健康检查阻断 |
| 4 | **ChromaDB 路径定义冲突** — `config.py` 定义 `chroma_db`，`vector_store.py` 硬编码 `chroma`，`.env.example` 指定 `data/chroma` | 如果用户根据 config.py 的 CHROMA_PATH 创建目录，实际不会被使用 | 删除或修正 config.py 中的 CHROMA_PATH |
| 5 | **`KB_RERANK_PROXY` 在 .env.example 中重复定义** — 第一次为空值（L137），第二次为 `http://127.0.0.1:8091`（L198） | 手工 .env 解析器按顺序处理，后值覆盖前值 | 删除重复定义 |

### 🟡 中等问题

| # | 问题 | 影响 | 建议修复 |
|---|------|------|----------|
| 6 | **5 个 .env.example 变量未被代码读取**：`FUXI_ALLOW_REGISTRATION`, `REDIS_URL`, `FUXI_ENV`, `FUXI_LOG_LEVEL` | 配置了也不生效，用户困惑 | 实现对应功能或从 .env.example 中移除 |
| 7 | **11 个 config.py 变量未被引用**：`CHROMA_PATH`, `RERANK_URL`, `CHUNKS_FILE`, `TERMS_FILE`, `CONFIG_FILE`, `WIKI_DB_PATH`, `ALLOWED_EXTENSIONS`, `SENSITIVE_PATTERNS`, `TOOLS_DATA`, `FAQ_DATA`, `ADMIN_DIR` | 死代码膨胀 config.py | 清理或标注为 legacy |
| 8 | **`KB_ACCESS_COUNTS_PATH` 在代码中读取但 .env.example 中缺失** | 用户无法知道此配置的存在 | 添加到 .env.example |
| 9 | **手工 .env 解析脆弱** — 不处理复杂值 | 包含 `=` 的值会解析错误 | 使用 `python-dotenv` |
| 10 | **`slowapi` 可选依赖无任何告警** — 安装后在静默中无请求限流 | 用户以为有限流，实际没有 | 至少打 warning |
| 11 | **`table_view.py` 每次创建新的 ChromaDB PersistentClient**（非单例） | 文件句柄泄漏风险 | 改为单例 |

### 🟢 低风险/建议

| # | 问题 | 建议 |
|---|------|------|
| 12 | FastAPI 使用已废弃的 `@app.on_event` 而非 `lifespan` | 迁移到 lifespan |
| 13 | `ConfigValidator` 定义但未在启动时调用 | 在 startup 中加入 `config_validator.validate()` |
| 14 | 日志级别硬编码 `INFO`，不读 `FUXI_LOG_LEVEL` | 从环境变量读取 |
| 15 | `src/services/__init__.py` 有大量 eager import（L33-75），可能导致循环导入 | 渐进式改为懒加载 |
| 16 | vector_store.py 中 `CHROMA_DIR` 变量定义了但 `__init__` 中用的是硬编码路径拼接 | 统一使用 `CHROMA_DIR` |
| 17 | `load_chunks()` 在 `/api/metrics` 端点中每次全量加载 | 添加缓存 |

---

## 附录：启动时完整模块加载图

```
server.py (import time)
├── .env 手工加载
├── logging 初始化
├── from src.config import ...
│   ├── os.getenv 读取 25+ 个环境变量
│   ├── mkdir 创建 8 个目录
│   └── ASSERT: FUXI_JWT_SECRET 必须存在
├── FastAPI() 实例创建
├── AuthMiddleware 导入 → 再次 ASSERT FUXI_JWT_SECRET
├── slowapi 导入（可选）
├── 路由注册 (20+ 个路由模块被 import)
├── @app.on_event("startup") → _start_fuxi()
│   ├── import src.hypothalamus.fuxi
│   │   ├── import Meridian, Brain
│   │   ├── import ShaoyangPipeline, TaiyangRetrieval, ShaoyinBrain, TaiyinServer
│   │   └── import 14 个器官模块
│   ├── Fuxi()
│   └── await fuxi.born()
│       ├── meridian.start()
│       ├── 四象模块创建（4 个 SymbolBase 子类）
│       ├── 13 个器官创建（StomachAgent 导入失败）
│       ├── 3 个平衡模块启动
│       └── 12 个器官定时任务启动
└── uvicorn.run(app, ...)
```

---

*报告完毕。所有结论均有代码行号证据支持。*