# 伏羲 v1.50 架构腐化根因分析（全链路追踪精简版）

> 基于全链路启动追踪数据 + 静态代码分析，聚焦 5 个核心腐化模式。

---

## 模式 1：接口契约断裂

### 问题
调用方使用不存在的方法名，运行时 `AttributeError` 被外层 `except Exception` 吞掉，表现为静默数据丢失。

### 证据

| 调用方 | 调用代码 | 实际方法名 | 文件:行 |
|--------|---------|-----------|---------|
| `pipeline/unified.py` | `store.insert_many(chunk_dicts)` | **不存在**，正确方法是 `add_batch()` | unified.py:380 |
| `shaoyang/pipeline.py` | `store.insert_many(chunk_dicts)` | **不存在**，正确方法是 `add_batch()` | pipeline.py:230 |
| `balance/meridian_rhythm.py` | `self.meridian.send_raw(oid, ...)` | **不存在**，正确方法是 `send()` | meridian_rhythm.py:78,89 |
| `balance/stem_scheduler.py` | `organ.meridian.send_raw(oid, ...)` | **不存在**，正确方法是 `send()` | stem_scheduler.py:96 |

> MemoryStore 公开 API 是 `add()` / `add_batch()`（memory_store.py:246），没有 `insert_many()`。
> Meridian 公开 API 是 `send(signal: Signal)`（meridian.py:174），没有 `send_raw()`。

### 影响
- `insert_many()`：2 处调用均被 `except Exception` 捕获，chunk 静默不写入
- `send_raw()`：3 处调用均被 `except Exception: logger.warning` 捕获，脉冲/心跳信号静默丢失

---

## 模式 2：双版本并存（Dead Alias Trap）

### 问题
器官模块同时存在根级 `.py` 单体文件和 `/<organ>/signal_layer.py` 子包两个版本，各自独立定义 `XxxAgent`，import 路径不统一。

### 证据

| 导入路径 | 导入方 | 目标类 |
|---------|-------|--------|
| `src.hypothalamus.organs.heart import HeartAgent` | fuxi.py:29, limbs.py:92 | → `organs/heart.py`（旧版单体） |
| `src.hypothalamus.organs.heart.signal_layer import HeartAgent` | organs/heart/__init__.py | → `organs/heart/signal_layer.py`（新版分层） |
| `src.hypothalamus.organs.gallbladder import GallbladderAgent` | fuxi.py:39 | → `organs/gallbladder.py`（旧版单体） |
| `src.hypothalamus.organs.gallbladder.signal_layer import GallbladderAgent` | organs/gallbladder/__init__.py | → `organs/gallbladder/signal_layer.py`（新版分层） |

> 两个文件各自定义了同名类：`heart.py:21` 和 `heart/signal_layer.py:21` 都定义 `class HeartAgent`。
> `fuxi.py` 直接导入旧版 `.py`，新版的 `__init__.py` 重导出新版 `signal_layer.py`，两者行为可能不同。

### 影响
- 13 个器官都有 `/organs/<name>.py` + `/organs/<name>/signal_layer.py` 双份
- `stomach.py` 完全缺失：`fuxi.py:23-25` 用 `try/except ImportError: StomachAgent = None` 兜底
- `services/__init__.py:69` 导出 `from src.infra.llm import call_ai` 同时 `services/llm.py` 自身也提供 LLM API，调用方同时使用 `services.llm` 和 `infra.llm`，接口版本分裂

---

## 模式 3：Feature Flag 死锁（双 Flag 源不一致）

### 问题
两个独立的 Flag 模块各自维护 `DEFAULT_FLAGS`，读写同一个文件但默认值不同，导致 Flag 判断不可预测。

### 证据

**源 A**: `services/feature_flags.py`
```python
DEFAULT_FLAGS = {
    "graphrag_multi_hop": False, "self_rag_check": True, "crag_rewrite": True,
    ...  # 9 个 key
}
FLAG_FILE = os.path.join(os.path.dirname(__file__), "../../data/feature_flags.json")
```

**源 B**: `taiyin/flags.py`
```python
DEFAULT_FLAGS = {
    "shaoyang_sag_extract": False, "taiyang_multi_hop": False,
    "enhanced_pipeline": False, "query_rewrite": False,
    "self_rag_check": False,   # ← 与 源A 不同！
    "crag_rewrite": False,     # ← 与 源A 不同！
    ...  # 14 个 key
}
FLAGS_FILE = Path("data/feature_flags.json")  # ← 同一个文件！
```

| 调用方 | 导入来源 | 影响的 Flag 集 |
|--------|---------|---------------|
| `server.py:353` | `services.feature_flags` → `DEFAULT_FLAGS` A | graphrag_multi_hop 等 9 个 |
| `pipeline/unified.py:610` | `services.feature_flags` | 同上 |
| `services/__init__.py:56` | `taiyin.flags` → `DEFAULT_FLAGS` B | shaoyang_sag_extract 等 14 个 |
| `taiyang/retrieval.py:55` | `taiyin.flags` → `is_enabled("taiyang_multi_hop")` | 只在 B 中存在 |
| `taiyin/mcp_protocol.py:213` | `taiyin.flags` | 同上 |

### 冲突分析
1. **`self_rag_check`** 在源A 默认 `True`，在源B 默认 `False` — 同一文件只能有一个真相
2. **`taiyang_multi_hop`** 只存在于源B — 如果被源A 调用将永远返回 `False`
3. 两个模块都写 `data/feature_flags.json`，读写无锁，存在竞态条件

---

## 模式 4：静默失败（异常吞咽链）

### 问题
启动链路上的异常被 `except Exception` 吞掉，仅打日志，系统在"看起来正常"的状态下缺胳膊少腿。

### 证据

**链 1：StomachAgent 导入失败被静默**
```python
# fuxi.py:23-25
try:
    from src.hypothalamus.organs.stomach import StomachAgent
except ImportError:
    StomachAgent = None       # ← 不报错，不告警

# fuxi.py:114
if StomachAgent:
    self.stomach = StomachAgent(self.meridian)
logger.info("🍽️ 胃已就绪")   # ← 即使 stomach 是 None 也打印"就绪"
```

**链 2：启动异常被全量捕获**
```python
# server.py:79
try:
    from src.hypothalamus.fuxi import Fuxi
    _fuxi_instance = Fuxi()
    await _fuxi_instance.born()
except Exception as e:
    logging.getLogger("server").error(f"[Fuxi] 启动失败: {e}")
    # ← 服务器继续运行，但伏羲未启动
```

**链 3：Flag 加载失败静默回退**
```python
# services/feature_flags.py:42
except Exception as e:
    logger.warning("加载 feature flags 失败: %s", e, exc_info=True)
    _flags = dict(DEFAULT_FLAGS)   # ← 静默回退到默认值
```

### 影响
- `stomach` 为 None 但日志仍打印"胃已就绪"，运维无法察觉
- 全系统共 30+ 处 `except Exception` 模式，其中 `server.py` 独占 11 处
- Flag 文件 JSON 损坏时静默回退，不会触发任何告警

---

## 模式 5：配置漂移（命名分裂）

### 问题
同一配置项在不同模块使用不同的环境变量名和默认值。

### 证据

**JWT 过期时间：两个变量名，两个默认值**

| 位置 | 变量名 | 默认值 | 文件:行 |
|------|--------|--------|---------|
| `config.py` | `JWT_EXPIRY_HOURS`（读 `JWT_EXPIRY_HOURS`） | 24 | config.py:71 |
| `api/auth.py` | `JWT_EXPIRE_HOURS`（读 `FUXI_JWT_EXPIRE_HOURS`） | 24 | auth.py:21 |

> `config.py` 读 `JWT_EXPIRY_HOURS`，`auth.py` 读 `FUXI_JWT_EXPIRE_HOURS`。
> 运维设置 `FUXI_JWT_EXPIRE_HOURS=1` 期望 1 小时过期，但 `config.py` 不受影响仍按 24h 读。

**Chroma 路径：三个模块，三个路径**

| 位置 | 路径 | 文件:行 |
|------|------|---------|
| `config.py` | `data/chroma_db` | config.py:29 |
| `db/vector_store.py` | `data/chromadb`（环境变量 `KB_CHROMA_DIR`） | vector_store.py:29 |
| `services/table_view.py` | `data/chroma`（环境变量 `KB_CHROMA_DIR`） | table_view.py:132 |
| `services/data_analytics/routes.py` | `data/chroma`（硬编码） | routes.py:88 |
| 实际存在目录 | `data/chroma/` ✅ | — |

> 只有 `data/chroma` 实际存在。`config.py` 指向不存在的 `data/chroma_db`，`vector_store.py` 指向不存在的 `data/chromadb`。

---

## 5 项预防建议

| # | 建议 | 对应模式 |
|---|------|---------|
| 1 | **接口契约自动化验证**：对 `@published_api` 方法生成 stub 测试，CI 中检查所有调用方引用的方法名是否在目标类中存在（可用 `ast` 静态分析） | 模式 1 |
| 2 | **移除旧版代码 + `import-linter`**：删除 `organs/<name>.py` 单体文件，统一使用 `/<name>/signal_layer.py` 分层；添加 `import-linter` 合约禁止跨版本 import | 模式 2 |
| 3 | **单一 Flag 源 + 对账检查**：删除 `services/feature_flags.py`，统一使用 `taiyin/flags.py`；启动时打印 Flag 摘要并对比实际文件值与默认值的一致性 | 模式 3 |
| 4 | **异常分级与启动熔断**：区分 `FatalError`（必须 abort）和 `DegradedWarning`（可降级）；`except ImportError` 必须记录告警且写入 `/health` 端点 | 模式 4 |
| 5 | **配置项注册表 + 漂移检测**：所有配置项集中注册到 `config.py` 的 `CONFIG_SCHEMA`，启动时扫描全代码库 `os.getenv/os.environ.get`，检测未注册的环境变量读取并告警 | 模式 5 |

---

*报告生成时间：2026-07-06 | 版本：v1.50 全链路精简分析*
